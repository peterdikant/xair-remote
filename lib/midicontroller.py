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

    Fader 1-8: CC16 - CC23, Note 32 - 39 on push
    Turn right: Values 1 - 10 (Increment)
    Turn left: Values 65 - 72 (Decrement)
    Buttons 1-8: Note 89, 90, 40, 41, 42, 43, 44, 45
    Buttons 9-16: Note 87, 88, 91, 92, 86, 93, 94, 95
    Buttons LA/LB (aka 17/18): Note 84/85
    Master Fader: Pitch Wheel
    """
    MC_CHANNEL = 0

    MIDI_BUTTONS = [89, 90, 40, 41, 42, 43, 44, 45, 87, 88, 91, 92, 86, 93, 94, 95, 84, 85]
    MIDI_PUSH = [32, 33, 34, 35, 36, 37, 38, 39]
    MIDI_ENCODER = [16, 17, 18, 19, 20, 21, 22, 23]
    MIDI_RING = [48, 49, 50, 51, 52, 53, 54, 55]

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
                    return
                break

        if self.inport is None or self.outport is None:
            print('X-Touch Mini not found. Make sure device is connected!')
            self.state.quit_called = True
            self.cleanup_controller()
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
                self.state.shutdown()
            else:
                self.cleanup_controller()
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
                        encoder_num = self.MIDI_ENCODER.index(msg.control)
                        LED = self.state.encoder_turn(encoder_num, delta)
                        self.set_ring(encoder_num, LED)
                    else:
                        print('Received unknown {}'.format(msg))
                elif msg.type == 'note_on' and msg.velocity == 127:
                    if self.state.debug:
                        print('Note {} pushed'.format(msg.note))
                    if msg.note in self.MIDI_PUSH:
                        encoder_num = self.MIDI_PUSH.index(msg.note)
                        LED = self.state.encoder_press(encoder_num)
                        self.set_ring(encoder_num, LED)
                    elif msg.note in self.MIDI_BUTTONS:
                        button_num = self.MIDI_BUTTONS.index(msg.note)
                        LED = self.state.button_press(button_num)
                        self.set_channel_mute(button_num, LED)
                    else:
                        print('Received unknown {}'.format(msg))
                elif msg.type == 'pitchwheel':
                    value = (msg.pitch + 8192) / 16384
                    if self.state.debug:
                        print('Wheel set to {}'.format(msg))
                    if msg.pitch > 8000:
                        if self.state is not None:
                            self.state.shutdown()
                        else:
                            self.cleanup_controller()
                        exit()
                elif msg.type != 'note_off' and msg.type != 'note_on':
                    print('Received unknown {}'.format(msg))
                if self.state.quit_called:
                    self.state.shutdown()
                    return
        except KeyboardInterrupt:
            if self.state is not None:
                self.state.shutdown()
            else:
                self.cleanup_controller()
            exit()

    def activate_bus(self):
        "refresh the lights for the current layer"
        # reset lights
        for i in range(0, 8):
            self.set_ring(i, self.state.get_encoder(i))
            self.set_channel_mute(i, self.state.get_button(i))
        for i in range(8, 18):
            self.set_channel_mute(i, self.state.get_button(i))

    def set_channel_mute(self, channel, LED):
        "Send the mute value to the button"
        if LED == "On" or LED == 0: # LED is sense Negative for mute
            self.set_button(channel, self.LED_ON)
        elif LED == "Off" or LED == 1: # LED is sense Negative for mute
            self.set_button(channel, self.LED_OFF)
        else:
            self.set_button(channel, self.LED_BLINK)

    def set_ring(self, ring, value):
        "Send the fader value to the encoder ring"
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
