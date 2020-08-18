import threading
import time
from .mixerstate import MixerState
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

    MIDI_BUTTONS = [89, 90, 40, 41, 42, 43, 44, 45, 87, 88, 91, 92, 86, 93, 94, 95]
    MIDI_PUSH = [32, 33, 34, 35, 36, 37, 38, 39]
    MIDI_ENCODER = [16, 17, 18, 19, 20, 21, 22, 23]
    MIDI_RING = [48, 49, 50, 51, 52, 53, 54, 55]
    MIDI_LAYER = [84, 85]

    LED_OFF = 0
    LED_BLINK = 1
    LED_ON = 127

    active_layer = 0
    active_bus = 0

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
                    exit()
                break

        for name in get_output_names():
            if "x-touch mini" in name.lower():
                print('Using MIDI output: ' + name)
                try:
                    self.outport = open_output(name)
                except IOError:
                    print('Error: Can not open MIDI input port ' + name)
                    exit()
                break
        
        if self.inport is None or self.outport is None:
            print('X-Touch Mini not found. Make sure device is connected!')
            exit()

        self.tempo_detector = TempoDetector(self)
        self.change_layer(0)
        self.activate_bank(0)
        #self.activate_bus(0)

        worker = threading.Thread(target = self.midi_listener)
        worker.daemon = True
        worker.start()
        
    def midi_listener(self):
        try:
            for msg in self.inport:
                #print('Received {}'.format(msg))
                if msg.type == 'control_change':
                    if msg.control in self.MIDI_ENCODER:
                        delta = msg.value
                        if delta > 64:
                            delta = (delta - 64) * -1
                        if self.active_layer == 0:
                            self.state.change_fader(self.MIDI_ENCODER.index(msg.control), delta)
                        else:
                            self.state.change_bus_send(self.active_bus, self.MIDI_ENCODER.index(msg.control), delta)
                    else:
                        print('Received unknown {}'.format(msg))
                elif msg.type == 'note_on' and msg.velocity == 127:
                    if msg.note in self.MIDI_PUSH:
                        self.knob_pushed(self.MIDI_PUSH.index(msg.note))
                    elif msg.note in self.MIDI_BUTTONS:
                        self.button_pushed(self.MIDI_BUTTONS.index(msg.note))
                    elif msg.note in self.MIDI_LAYER:
                        self.change_layer(self.MIDI_LAYER.index(msg.note))
                    else:
                        print('Received unknown {}'.format(msg))
                elif msg.type == 'pitchwheel':
                    value = (msg.pitch + 8192) / 16384
                    self.state.set_lr_fader(value)
                elif msg.type != 'note_off' and msg.type != 'note_on':
                    print('Received unknown {}'.format(msg))
        except KeyboardInterrupt:
            self.inport.close()
            self.outport.close()
            exit()
    
    def button_pushed(self, button):
        if self.active_layer == 0:
            if button >= 11 and button <= 15:
                # bank select buttons pressed
                self.activate_bank(button - 11)
            elif button == 9:
                # tempo button pressed
                self.tempo_detector.tap()
            elif button == 8:
                # mute grp 4 pressed
                self.state.toggle_mute_group(3)
            else:
                # mute buttons pressed
                self.state.toggle_channel_mute(button)
        else:
            if button >= 11 and button <= 13:
                # bank select buttons pressed
                self.activate_bank(button - 11)
            elif button == 9:
                # tempo button pressed
                self.tempo_detector.tap()
            elif button == 8:
                # mute grp 4 pressed
                self.state.toggle_mute_group(3)
            else:
                self.active_bus = button if button < 8 else button - 6
                self.refresh_controls(self.state.active_bank)

    def knob_pushed(self, knob):
        if knob >= 0 and knob <= 3:
            self.state.toggle_mute_group(knob)
        elif knob == 7:
            self.state.toggle_mpc()

    def activate_bank(self, bank):
        #print("Switching to fader bank %d" % (bank + 1))
        for i in range(0, 5):
            if i == bank:
                self.set_button(11 + i, True)
            else:
                self.set_button(11 + i, False)
        if self.state.active_bank != bank:
            self.refresh_controls(bank)
            self.state.active_bank = bank
        
    def change_layer(self, layer):
        if layer == 0:
            self.outport.send(Message('note_on', channel = self.MC_CHANNEL, note = self.MIDI_LAYER[0], velocity = self.LED_ON))
            self.outport.send(Message('note_on', channel = self.MC_CHANNEL, note = self.MIDI_LAYER[1], velocity = self.LED_OFF))
            self.activate_bank(self.state.active_bank)
        else:
            self.outport.send(Message('note_on', channel = self.MC_CHANNEL, note = self.MIDI_LAYER[0], velocity = self.LED_OFF))
            self.outport.send(Message('note_on', channel = self.MC_CHANNEL, note = self.MIDI_LAYER[1], velocity = self.LED_ON))
            if self.state.active_bank > 2:
                self.activate_bank(2)
        self.active_layer = layer
        self.refresh_controls(self.state.active_bank)
    
    def refresh_controls(self, bank):
        if self.active_layer == 0:
            for i in range(0, 8):
                if self.state.banks[bank][i] != None:
                    # send fader for Layer A
                    self.set_ring(i, self.state.banks[bank][i].fader)
                    self.set_channel_mute(i, self.state.banks[bank][i].on)
                else:
                    # unassigned channel, disbale encoder and button
                    self.set_ring(i, -1)
                    self.set_button(i, False)
        else:
            for i in range(0, 10):
                if i < 8:
                    btn = i
                else:
                    # sends 9 & 10 need other button numbers
                    btn = i + 6
                if i != self.active_bus:
                    self.set_button(btn, False)
                else:
                    self.set_button(btn, True)
            for i in range(0, 8):
                if self.state.banks[bank][i] != None and self.state.banks[bank][i].sends != None:
                    self.set_ring(i, self.state.banks[bank][i].sends[self.active_bus])
                else:
                    self.set_ring(i, -1)
        # set indicator for mute group 4
        self.set_mute_grp(3, self.state.mute_groups[3].on)

    def set_mute_grp(self, group, on):
        if group == 3:
            # we only need to update this group as all others have no led indicator
            self.set_button(8, on == 1)

    def set_channel_mute(self, channel, on):
        if self.active_layer == 0:
            self.set_button(channel, on == 0)

    def set_channel_fader(self, channel, value):
        if self.active_layer == 0:
            self.set_ring(channel, value)

    def set_bus_send(self, bus, knob, value):
        if self.active_layer == 1 and self.active_bus == bus:
            self.set_ring(knob, value)

    def set_ring(self, ring, value):
        # 0 = off, 1-11 = single, 17-27 = trim, 33-43 = fan, 49-54 = spread
        # normalize value (0.0 - 1.0) to 0 - 11 range
        # values below 0 mean disabled
        if value >= 0.0:
            self.outport.send(Message('control_change', channel = self.MC_CHANNEL, 
                                  control = self.MIDI_RING[ring], 
                                  value = 33 + round(value * 11)))
        else:
            self.outport.send(Message('control_change', channel = self.MC_CHANNEL, 
                                  control = self.MIDI_RING[ring], 
                                  value = 0))

    def set_button(self, button, on):
        if on == True:
            self.outport.send(Message('note_on', channel = self.MC_CHANNEL, note = self.MIDI_BUTTONS[button], velocity = self.LED_ON))
        else:
            self.outport.send(Message('note_on', channel = self.MC_CHANNEL, note = self.MIDI_BUTTONS[button], velocity = self.LED_OFF))

    def tempo_led(self, on):
        self.set_button(9, on)
    
    def update_tempo(self, tempo, detected = False):
        if detected == True:
            self.state.update_tempo(tempo)
        else:
            self.tempo_detector.current_tempo = tempo
        