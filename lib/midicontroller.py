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
    Handles communication with the MIDI surface
    """
    midi_channel = 10
    
    midi_cmds_layer = [19, 20, 21, 22, 23]
    midi_cmds_on = [8, 9, 10, 11, 12, 13, 14, 15]
    midi_cmds_fader = [1, 2, 3, 4, 5, 6, 7, 8]
    midi_cmds_mgrp = [0, 1, 2, 16]
    midi_cmds_tempo = 17
    midi_cmds_lr = 9

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
        self.activate_layer(0)
        worker = threading.Thread(target = self.midi_listener)
        worker.daemon = True
        worker.start()
        
    def midi_listener(self):
        try:
            for msg in self.inport:
                if msg.type == 'control_change':
                    if msg.control in self.midi_cmds_fader:
                        self.state.received_midi(channel = self.midi_cmds_fader.index(msg.control), fader = msg.value)
                    elif msg.control == self.midi_cmds_lr:
                        self.state.received_midi(channel = 9, fader = msg.value)
                elif msg.type == 'note_on':
                    if msg.note in self.midi_cmds_layer:
                        self.activate_layer(self.midi_cmds_layer.index(msg.note), False)
                    elif msg.note in self.midi_cmds_on:
                        if self.state.received_midi(channel = self.midi_cmds_on.index(msg.note), on = 0) == False:
                            # unassigned buttons should stay off
                            self.outport.send(Message('note_off', channel = self.midi_channel, 
                                                      note = msg.note, velocity = 0))
                    elif msg.note in self.midi_cmds_mgrp:
                        self.state.received_midi(mute_group = self.midi_cmds_mgrp.index(msg.note), on = 1)
                    elif msg.note == self.midi_cmds_tempo:
                        self.tempo_detector.tap()
                    else:
                        # unassigned buttons should stay off
                        self.outport.send(Message('note_off', channel = self.midi_channel,
                                                  note = msg.note, velocity = 0))
                elif msg.type == 'note_off':
                    if msg.note in self.midi_cmds_layer:
                        self.activate_layer(self.midi_cmds_layer.index(msg.note))
                    elif msg.note in self.midi_cmds_on:
                        self.state.received_midi(channel = self.midi_cmds_on.index(msg.note), on = 1)
                    elif msg.note in self.midi_cmds_mgrp:
                        self.state.received_midi(mute_group = self.midi_cmds_mgrp.index(msg.note), on = 0)
                    elif msg.note == self.midi_cmds_tempo:
                        self.tempo_detector.tap()
                else:
                    print('Received unknown {}'.format(msg))
        except KeyboardInterrupt:
            inport.close()
            outport.close()
            exit()
            
    def activate_layer(self, layer, send_active = True):
        #print "Switching to layer %d" % layer
        for i in range(0, 5):
            if i != layer:
                self.outport.send(Message('note_off', channel = self.midi_channel, note = self.midi_cmds_layer[i], velocity = 0))
        if send_active == True:
            self.outport.send(Message('note_on', channel = self.midi_channel, note = self.midi_cmds_layer[layer], velocity = 127))
        if self.state.active_layer != layer:
            self.refresh_channels(layer)
            self.state.active_layer = layer
            
        
    def refresh_channels(self, layer):
        for i in range(0, 8):
            if self.state.layers[layer][i] != None:
                self.outport.send(Message('control_change', channel = self.midi_channel,
                                          control = self.midi_cmds_fader[i], 
                                          value = int(self.state.layers[layer][i].fader * 127)))
                if self.state.layers[layer][i].on == 0:
                    self.outport.send(Message('note_on', channel = self.midi_channel, 
                                              note = self.midi_cmds_on[i], velocity = 127))
                else:
                    self.outport.send(Message('note_off', channel = self.midi_channel, 
                                                   note = self.midi_cmds_on[i], velocity = 0))
            else:
                # unassigned channel, disbale encoder and button
                self.outport.send(Message('control_change', channel = self.midi_channel,
                                          control = self.midi_cmds_fader[i], 
                                          value = 0))
                self.outport.send(Message('note_off', channel = self.midi_channel, 
                                               note = self.midi_cmds_on[i], velocity = 0))
        for i in range(0, 4):
            if self.state.mute_groups[i].on == 0:
                self.outport.send(Message('note_off', channel = self.midi_channel,
                                          note = self.midi_cmds_mgrp[i], velocity = 0))
            else:
                self.outport.send(Message('note_on', channel = self.midi_channel,
                                          note = self.midi_cmds_mgrp[i], velocity = 127))
                                      
    def send(self, channel = None, mute_group = None, fader = None, on = None):
        if channel != None:
            if fader != None:
                self.outport.send(Message('control_change', channel = self.midi_channel,
                                          control = self.midi_cmds_fader[channel], 
                                          value = fader))
            if on != None:
                if on == 0:
                    self.outport.send(Message('note_on', channel = self.midi_channel, 
                                              note = self.midi_cmds_on[channel], velocity = 127))
                else:
                    self.outport.send(Message('note_off', channel = self.midi_channel, 
                                              note = self.midi_cmds_on[channel], velocity = 0))
        elif mute_group != None:
            if on == 0:
                self.outport.send(Message('note_off', channel = self.midi_channel,
                                          note = self.midi_cmds_mgrp[mute_group], velocity = 0))
            else:
                self.outport.send(Message('note_on', channel = self.midi_channel,
                                          note = self.midi_cmds_mgrp[mute_group], velocity = 127))
    
    def tempo_led(self, on):
        if on == True:
            self.outport.send(Message('note_on', channel = self.midi_channel, note = self.midi_cmds_tempo, velocity = 127))
        else:
            self.outport.send(Message('note_off', channel = self.midi_channel, note = self.midi_cmds_tempo, velocity = 0))
    
    def update_tempo(self, tempo, detected = False):
        if detected == True:
            self.state.update_tempo(tempo)
        else:
            self.tempo_detector.current_tempo = tempo
        