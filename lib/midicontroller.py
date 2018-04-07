import thread
from mixerstate import MixerState
from mido import Message, open_input, open_output, get_input_names

def print_ports():
    """
    Print out the names of all connected midi controllers
    """
    print 'Connected MIDI Ports:'
    for name in get_input_names():
        print '    %s' % name

class MidiController:
    """
    Handles communication with the MIDI surface
    """
    midi_channel = 10
    
    midi_cmds_layer = [19, 20, 21, 22, 23]
    midi_cmds_on = [8, 9, 10, 11, 12, 13, 14, 15]
    midi_cmds_fader = [1, 2, 3, 4, 5, 6, 7, 8]
    midi_cmds_lr = 9
    
    def __init__(self, devicename, state):
        self.state = state
        self.state.midi_sender = self.update_callback
        
        try:
            self.inport = open_input(devicename)
            self.outport = open_output(devicename)
        except IOError:
            print 'Error: MIDI port %s does not exist!' % devicename
            exit()
            
        self.activate_layer(0)
        thread.start_new_thread(self.midi_listener, ())
        print 'Successfully setup MIDI port %s.' % devicename
        
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
                    else:
                        # unassigned buttons should stay off
                        self.outport.send(Message('note_off', channel = self.midi_channel,
                                                  note = msg.note, velocity = 0))
                elif msg.type == 'note_off':
                    if msg.note in self.midi_cmds_layer:
                        self.activate_layer(self.midi_cmds_layer.index(msg.note))
                    elif msg.note in self.midi_cmds_on:
                        self.state.received_midi(channel = self.midi_cmds_on.index(msg.note), on = 1)
                else:
                    print 'Received unknown {}'.format(msg)
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
                                              
    def update_callback(self, channel, fader = None, on = None):
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
                                          