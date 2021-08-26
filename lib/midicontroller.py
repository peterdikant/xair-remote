"See class docstring"
import threading
import time
import os
from mido import Message, open_input, open_output, get_input_names, get_output_names

class TempoDetector:
    """
    Detect song tempo via a tap button
    """
    _MAX_TAP_DURATION = 3.0
    
    current_tempo = 0.5
    
    def __init__(self, midi_controller):
        self.midi_controller = midi_controller
        self.last_tap = 0
        self.tap_num = 0
        self.tap_delta = 0
        worker = threading.Thread(target = self.blink)
        worker.daemon = True
        worker.start()
    
    def tap(self):
        current_time = time.time()
        if current_time - self.last_tap > self._MAX_TAP_DURATION:
            # Start with new tap cycle
            self.tap_num = 0
            self.tap_delta = 0
        else:
            self.tap_num += 1
            self.tap_delta += current_time - self.last_tap
            if self.tap_num > 0:
                # Update tempo in mixer after at least 2 taps
                self.midi_controller.update_tempo(self.tap_delta / self.tap_num, True)
                self.current_tempo = self.tap_delta / self.tap_num
        self.last_tap = current_time
        
    def blink(self):
        try:
            while True:
                self.midi_controller.tempo_led(True)
                time.sleep(self.current_tempo * 0.2)
                self.midi_controller.tempo_led(False)
                time.sleep(self.current_tempo * 0.8)
        except KeyboardInterrupt:
            exit()

class MidiController:
    """
    Handles communication with the MIDI surface.
    X-Touch Mini must be in MC mode!

    LA/LB: Note 84/85
    Fader 1-8: CC16 - CC23, Note 32 - 39 on push
    Turn right: Values 1 - 10 (Increment)
    Turn left: Values 65 - 72 (Decrement)
    Buttons 1-8: Note 89, 90, 40, 41, 42, 43, 44, 45
    Buttons 9-16: Note 87, 88, 91, 92, 86, 93, 94, 95
    Master Fader: Pitch Wheel
    """
    MC_CHANNEL = 0

#    MIDI_BUTTONS = [89, 90, 40, 41, 42, 43, 44, 45, 87, 88, 91, 92, 86, 93, 94, 95]
    MIDI_BUTTONS = [89, 90, 40, 41, 42, 43, 44, 45, 87, 88, 91, 92, 86, 93, 94, 95, 84, 85]
    MIDI_PUSH = [32, 33, 34, 35, 36, 37, 38, 39]
    MIDI_ENCODER = [16, 17, 18, 19, 20, 21, 22, 23]
    MIDI_RING = [48, 49, 50, 51, 52, 53, 54, 55]
#    MIDI_LAYER = [84, 85]

    LED_OFF = 0
    LED_BLINK = 1
    LED_ON = 127

    active_layer = 0

    inport = None
    outport = None

    def __init__(self, state):
        self.state = state

        for name in get_input_names():
            if "x-touch mini" in name.lower():
                print('Using MIDI input: ' + name)
                try:
                    self.inport = open_input(name)
                except IOError:
                    print('Error: Can not open MIDI input port ' + name)
                    self.state.quit_called = True
                    self.state = None
                    #exit()
                    return
                break

        for name in get_output_names():
            if "x-touch mini" in name.lower():
                print('Using MIDI output: ' + name)
                try:
                    self.outport = open_output(name)
                except IOError:
                    print('Error: Can not open MIDI input port ' + name)
                    self.state.quit_called = True
                    self.state = None
                    #exit()
                    return
                break

        if self.inport is None or self.outport is None:
            print('X-Touch Mini not found. Make sure device is connected!')
            self.state.quit_called = True
            self.cleanup_controller()
            #exit()
            return

        for i in range(0, 18):
            self.set_button(i, self.LED_OFF)    # clear all buttons

        worker = threading.Thread(target=self.midi_listener)
        worker.daemon = True
        worker.start()

        if self.state.monitor:
            print('Monitoring X-Touch connection enabled')
            monitor = threading.Thread(target=self.monitor_ports)
            monitor.daemon = True
            monitor.start()

    def cleanup_controller(self):
        "Cleanup mixer state if we see a quit call. Called from _init_ or worker thread."
        for i in range(0, 18):
            self.set_button(i, self.LED_OFF)    # clear all buttons
        for i in range(0,8):
            self.set_ring(i,-1)
        if self.inport is not None:
            self.inport.close()
        if self.outport is not None:
            self.outport.close()

    def monitor_ports(self):
        "Method to exit if / when the X Touch disconnects"
        try:
            while not self.state.quit_called:
                if self.inport.name not in get_input_names():
                    print("X-Touch disconnected - Exiting")
                    #os._exit(1)
                    self.state.quit_called = True
                    return
                if self.state.quit_called:
                    return # end the thread if other threads have signed exit
                time.sleep(1)
        except KeyboardInterrupt:
            if self.state is not None:
                self.state.quit_called = True
            exit()

    def midi_listener(self):
        "Listen to midit inputs and respond."
        try:
            for msg in self.inport:
                if self.state is None or self.state.quit_called:
                    self.cleanup_controller()
                    return
                #print('Received {}'.format(msg))
                if msg.type == 'control_change':
                    if msg.control in self.MIDI_ENCODER:
                        delta = msg.value
                        if delta > 64:
                            delta = (delta - 64) * -1
                        if self.state.active_bus < 7: # one of the 7 AUX bus
                            self.state.change_bus_send( \
                                self.state.active_bus, self.MIDI_ENCODER.index(msg.control), delta)
                        elif self.state.active_bus == 7: # preamp gain
                            self.state.change_headamp(self.MIDI_ENCODER.index(msg.control), delta)
                        else: # channels faders and output faders
                            self.state.change_fader(self.MIDI_ENCODER.index(msg.control), delta)
                    else:
                        print('Received unknown {}'.format(msg))
                elif msg.type == 'note_on' and msg.velocity == 127:
                    if self.state.debug:
                        print('Note {} pushed'.format(msg.note))
                    if msg.note in self.MIDI_PUSH:
                        self.knob_pushed(self.MIDI_PUSH.index(msg.note))
                    elif msg.note in self.MIDI_BUTTONS:
                        self.button_pushed(self.MIDI_BUTTONS.index(msg.note))
#                    elif msg.note in self.MIDI_LAYER:
#                       self.change_layer(self.MIDI_LAYER.index(msg.note))
                    else:
                        print('Received unknown {}'.format(msg))
                elif msg.type == 'pitchwheel':
                    value = (msg.pitch + 8192) / 16384
                    if self.state.debug:
                        print('Wheel set to {}'.format(msg))
                    if msg.pitch > 8000:
                        self.cleanup_controller()
                        if self.state is not None:
                            self.state.quit_called = True
                            if self.state.screen_obj is not None:
                                self.state.screen_obj.quit()
                        else:
                            # we can't assert a quit signal so simply exit
                            exit()
                elif msg.type != 'note_off' and msg.type != 'note_on':
                    print('Received unknown {}'.format(msg))
                if self.state.quit_called:
                    self.cleanup_controller()
                    return
        except KeyboardInterrupt:
            if self.state is not None:
                self.state.quit_called = True
            self.cleanup_controller()
            exit()

    def button_pushed(self, button):
        "On button press, call the relevant function"
        if self.state.debug:
            print('Button {} pushed'.format(button))
        if button < 8: # mute button pressed, upper row
            if self.state.active_bus < 7: # sending to a bus
                self.state.toggle_send_mute(button, self.state.active_bus)
            # skip preamps as meaningless
            elif self.state.active_bus > 7: # sending to a channel
                self.state.toggle_channel_mute(button)
        else: # bank select button
            if(self.state.mac and (button in [10, 11, 12, 13, 14])):
                self.mac_button(button)
            else:
                self.activate_bus(button - 8)

    def mac_button(self, button):
        "call a function for transport buttons on mac"
        if button == 10:
            os.system("""osascript -e 'tell application "music" to previous track'""")
        elif button == 11:
            os.system("""osascript -e 'tell application "music" to next track'""")
        elif button == 12:
            self.state.shutdown()
            self.cleanup_controller()
            exit()
        elif button == 13:
            os.system("""osascript -e 'tell application "music" to pause'""")
        elif button == 14:
            os.system("""osascript -e 'tell application "music" to play'""")

    def knob_pushed(self, knob):
        "On knob push reset the correct value"
        # reset to unity gain
        if self.state.active_bus < 7:
            self.state.set_bus_send(self.state.active_bus, knob, 0.750000)
        elif self.state.active_bus == 8:    # channel levels
            if self.state.mac and knob in [4, 5, 7]:
                self.state.set_fader(knob, 0.375367)
            else:
                self.state.set_fader(knob, 0.750000)
        elif self.state.active_bus == 9:
            if knob == 6:                   # USB Return
                self.state.set_fader(knob, 0.750000)
            else:                           # output levels -20 db
                self.state.set_fader(knob, 0.375367)
        #elif self.state.active_bus == 7:   # no obvious default for mic pre
            #self.state.toggle_mpc()

    def activate_bus(self, bus):
        "chagne the active bus"
        if self.state.debug:
            print('Activating bus {}'.format(bus))
        # set LEDs and layer
        if self.state.active_bus == bus and bus != 9: # button 9 has only one layer
            # switch layers for buttons with layers
            if self.active_layer == 0:
                self.set_button(bus + 8, self.LED_BLINK)
                self.active_layer = 1
            else:
                self.set_button(bus + 8, self.LED_ON)
                self.active_layer = 0
        else: # switching to a different bus, or one that only has a single layer
            self.set_button(self.state.active_bus + 8, self.LED_OFF)
            self.set_button(bus + 8, self.LED_ON)
            self.active_layer = 0
        # set bus and bank
        self.state.active_bus = bus
        if bus == 7: # set mic pre banks
            self.state.active_bank = self.active_layer + 2
        elif bus == 9: # set outputs bank
            self.state.active_bank = 4
        else:
            self.state.active_bank = self.active_layer

        # reset lights
        for i in range(0, 8):
            if self.state.banks[self.state.active_bank][i] is not None:
                if self.state.active_bus > 6: # send fader or preamp level
                    self.set_channel_fader(i, self.state.banks[self.state.active_bank][i].fader)
                    self.set_channel_mute(i, self.state.banks[self.state.active_bank][i].ch_on)
                else:                         # send bus send
                    if self.state.banks[self.state.active_bank][i].sends is not None:
                        self.set_channel_fader(i, self.state.banks[ \
                            self.state.active_bank][i].sends[self.state.active_bus])
                        self.set_channel_mute(i, self.state.banks[ \
                            self.state.active_bank][i].enables[self.state.active_bus])
            else:                             # unassigned channel, disbale encoder and button
                self.set_channel_fader(i, -1)
                self.set_button(i, self.LED_OFF)

    def set_channel_mute(self, channel, ch_on):
        "Send the mute value to the button"
        self.set_button(channel, self.LED_ON if ch_on == 0 else self.LED_OFF)

    def set_channel_fader(self, channel, value):
        "Send the fader value to the encoder ring"
        self.set_ring(channel, value)

    def set_ring(self, ring, value):
        "Turn on the appropriate LEDs on the encoder ring."
        # 0 = off, 1-11 = single, 17-27 = pan, 33-43 = fan, 49-54 = spread
        # normalize value (0.0 - 1.0) to 0 - 11 range
        # values below 0 mean disabled
        if value >= 0.0:
            self.outport.send(Message('control_change', channel=self.MC_CHANNEL,
                                      control=self.MIDI_RING[ring],
                                      value=self.map_lights(value)))
#                                      value=33 + round(value * 11)))
        else:
            self.outport.send(Message('control_change', channel=self.MC_CHANNEL,
                                      control=self.MIDI_RING[ring],
                                      value=0))

    def map_lights(self, value):
        "map the (0:1) range of fader values to ring light patterns"
        # for faders -oo to -10.2db map to single lights while -10 to +10 map to the fan
        value = 1 + round(value * 21)
        if value > 11:
            value = value + 22
        return value

    def set_button(self, button, ch_on):
        "Turn the button LED on or off"
        self.outport.send(Message('note_on', channel=self.MC_CHANNEL,
                                  note=self.MIDI_BUTTONS[button], velocity=ch_on))
