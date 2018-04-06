import mido
import mixerstate
from threading import Thread

class MidiSurface:
    """
    Handles communication with the MIDI surface
    """
    active_layer = -1
    midi_channel = 10
    
    midi_cmds_layer = [19, 20, 21, 22, 23]
    midi_cmds_mute = [8, 9, 10, 11, 12, 13, 14, 15]
    midi_cmds_fader = [1, 2, 3, 4, 5, 6, 7, 8]
    midi_cmds_lr = 9
    
    def __init__(self, devicename):
        self.inport = mido.open_input(devicename)
        self.outport = mido.open_output(devicename)
        self.activate_layer(0)
        Thread(target = self.midi_listener())
        
    def midi_listener(self):
        try:
            for msg in self.inport:
                if msg.type == 'control_change':
                    if msg.control in self.midi_cmds_fader:
                        self.set_fader(self.midi_cmds_fader.index(msg.control), msg.value)
                    elif msg.control == self.midi_cmds_lr:
                        mixerstate.lr_fader = msg.value / 127.0
                elif msg.type == 'note_on':
                    if msg.note in self.midi_cmds_layer:
                        self.activate_layer(self.midi_cmds_layer.index(msg.note), False)
                    elif msg.note in self.midi_cmds_mute:
                        self.set_on(self.midi_cmds_mute.index(msg.note), True)
                elif msg.type == 'note_off':
                    if msg.note in self.midi_cmds_layer:
                        self.activate_layer(self.midi_cmds_layer.index(msg.note))
                    elif msg.note in self.midi_cmds_mute:
                        self.set_on(self.midi_cmds_mute.index(msg.note), False)
                else:
                    print 'Received unknown {}'.format(msg)
        except KeyboardInterrupt:
            exit()
            
    def activate_layer(self, layer, send_active = True):
        print "Switching to layer %d" % layer
        for i in range(0, 5):
            if i != layer:
                self.outport.send(mido.Message('note_off', channel = self.midi_channel, note = 19 + i, velocity = 0))
        if send_active == True:
            self.outport.send(mido.Message('note_on', channel = self.midi_channel, note = 19 + layer, velocity = 127))
        if self.active_layer != layer:
            self.update_layer(layer)
            self.active_layer = layer
    
    def set_fader(self, fader, value):
        if self.active_layer == 0:
            mixerstate.channel_fader[fader] = value / 127.0
        elif self.active_layer == 1:
            mixerstate.channel_fader[fader + 8] = value / 127.0
        elif self.active_layer == 2:
            if fader == 0:
                mixerstate.aux_fader = value / 127.0
            elif fader > 3:
                mixerstate.dca_fader[fader - 4] = value / 127.0
        elif self.active_layer == 3:
            if fader < 4:
                mixerstate.fxsend_fader[fader] = value / 127.0
            else:
                mixerstate.fxret_fader[fader - 4] = value / 127.0
        else:
            if fader < 6:
                mixerstate.bus_fader[fader] = value / 127.0
    
    def set_on(self, button, value):
        if self.active_layer == 0:
            mixerstate.channel_on[button] = value
        elif self.active_layer == 1:
            mixerstate.channel_on[button + 8] = value
        elif self.active_layer == 2:
            if button == 0:
                mixerstate.aux_on = value
            elif button > 3:
                mixerstate.dca_on[button - 4] = value
        elif self.active_layer == 3:
            if button < 4:
                mixerstate.fxsend_on[button] = value
            else:
                mixerstate.fxret_on[button - 4] = value
        else:
            if button < 6:
                mixerstate.bus_on[button] = value
    
    def update_layer(self, layer):
        if layer == 0:
            self.update_faders(mixerstate.channel_fader[0:8])
            self.update_mutes(mixerstate.channel_on[0:8])
        elif layer == 1:
            self.update_faders(mixerstate.channel_fader[8:16])
            self.update_mutes(mixerstate.channel_on[8:16])
        elif layer == 2:
            self.update_faders([mixerstate.aux_fader, 0.0, 0.0, 0.0] + mixerstate.dca_fader[0:4])
            self.update_mutes([mixerstate.aux_on, False, False, False] + mixerstate.dca_on[0:4])
        elif layer == 3:
            self.update_faders(mixerstate.fxsend_fader[0:4] + mixerstate.fxret_fader[0:4])
            self.update_mutes(mixerstate.fxsend_on[0:4] + mixerstate.fxret_on[0:4])
        else:
            self.update_faders(mixerstate.bus_fader[0:6] + [0.0, 0.0])
            self.update_mutes(mixerstate.bus_on[0:6] + [False, False])
    
    def update_faders(self, faders):
        for i in range(0, 8):
            self.outport.send(mido.Message('control_change', channel = self.midi_channel, 
                                           control = self.midi_cmds_fader[i], value = int(faders[i] * 127)))
            
    def update_mutes(self, buttons):
        for i in range(0, 8):
            if buttons[i] == True:
                self.outport.send(mido.Message('note_on', channel = self.midi_channel, 
                                               note = self.midi_cmds_mute[i], velocity = 127))
            else:
                self.outport.send(mido.Message('note_off', channel = self.midi_channel, 
                                               note = self.midi_cmds_mute[i], velocity = 0))
                