import time

"""
This module holds the mixer state of the X-Air device
"""

class Channel:
    """ 
    Represents a single channel strip 
    """
    def __init__(self, addr):
        self.fader = 0.0
        self.on = 1
        self.osc_base_addr = addr
        

class MixerState:
    """
    This stores the mixer state in the application. It also keeps
    track of the current selected layer on the midi controller to
    decide whether state changes from the X-Air device need to be
    sent to the midi controller.
    """
    
    _DLY_TEMPO_INDEX = { 'D/RV': 1, 'D/CR': 1, 'D/FL': 1, 'MODD': 1, 'DLY': 2, '3TAP': 1, '4TAP': 1 }
    
    active_layer = -1
    # Each layer has 8 encoders and 8 buttons
    layers = [
        [
            Channel('/ch/01/mix'),
            Channel('/ch/02/mix'),
            Channel('/ch/03/mix'),
            Channel('/ch/04/mix'),
            Channel('/ch/05/mix'),
            Channel('/ch/06/mix'),
            Channel('/ch/07/mix'),
            Channel('/ch/08/mix')
        ],
        [
            Channel('/ch/09/mix'),
            Channel('/ch/10/mix'),
            Channel('/ch/11/mix'),
            Channel('/ch/12/mix'),
            Channel('/ch/13/mix'),
            Channel('/ch/14/mix'),
            Channel('/ch/15/mix'),
            Channel('/ch/16/mix')
        ],
        [
            Channel('/rtn/aux/mix'),
            None,
            None,
            None,
            Channel('/dca/1'),
            Channel('/dca/2'),
            Channel('/dca/3'),
            Channel('/dca/4')
        ],
        [
            Channel('/fxsend/1/mix'),
            Channel('/fxsend/2/mix'),
            Channel('/fxsend/3/mix'),
            Channel('/fxsend/4/mix'), 
            Channel('/rtn/1/mix'),
            Channel('/rtn/2/mix'),
            Channel('/rtn/3/mix'),
            Channel('/rtn/4/mix')
        ],
        [
            Channel('/bus/1/mix'),
            Channel('/bus/2/mix'),
            Channel('/bus/3/mix'),
            Channel('/bus/4/mix'), 
            Channel('/bus/5/mix'),
            Channel('/bus/6/mix'),
            None,
            None
        ]
    ]

    lr = Channel('/lr/mix')

    mute_groups = [
        Channel('/config/mute/1'),
        Channel('/config/mute/2'),
        Channel('/config/mute/3'),
        Channel('/config/mute/4')
    ]
    
    midi_sender = None
    osc_sender = None
    
    def received_midi(self, channel = None, mute_group = None, fader = None, on = None):
        if channel != None:
            if channel < 9 and self.layers[self.active_layer][channel] != None:
                if fader != None:
                    self.layers[self.active_layer][channel].fader = fader / 127.0
                    if self.osc_sender != None:
                        self.osc_sender(base_addr = self.layers[self.active_layer][channel].osc_base_addr, 
                            fader = self.layers[self.active_layer][channel].fader)
                elif on != None:
                    self.layers[self.active_layer][channel].on = on
                    if self.osc_sender != None:
                        self.osc_sender(base_addr = self.layers[self.active_layer][channel].osc_base_addr, 
                            on = self.layers[self.active_layer][channel].on)
                return True
            elif channel == 9:
                if fader != None:
                    self.lr.fader = fader / 127.0
                    if self.osc_sender != None:
                        self.osc_sender(base_addr = self.lr.osc_base_addr, fader = self.lr.fader)
                return True
        elif mute_group != None:
            self.mute_groups[mute_group].on = on
            if self.osc_sender != None:
                self.osc_sender(base_addr = self.mute_groups[mute_group].osc_base_addr, on = self.mute_groups[mute_group].on)
        return False
    
    def received_osc(self, addr, value):
        if addr.startswith('/config/mute'):
            group = int(addr[-1:]) - 1
            self.mute_groups[group].on = value
            if self.midi_sender != None:
                self.midi_sender(mute_group = group, on = self.mute_groups[group].on)
            return
            
        for i in range(0, 5):
            for j in range(0, 8):
                if self.layers[i][j] != None and addr.startswith(self.layers[i][j].osc_base_addr):
                    if addr.endswith('/fader'):
                        self.layers[i][j].fader = value
                        if self.midi_sender != None and i == self.active_layer:
                            self.midi_sender(channel = j, fader = int(self.layers[i][j].fader * 127))
                    elif addr.endswith('/on'):
                        self.layers[i][j].on = value
                        if self.midi_sender != None and i == self.active_layer:
                            self.midi_sender(channel = j, on = self.layers[i][j].on)
                    break
            else:
                continue
            break
    
    def read_initial_state(self):
        if self.osc_sender == None:
            return
        
        # Refresh state for all faders and mutes
        for i in range(0, 5):
            for j in range(0, 8):
                if self.layers[i][j] != None:
                    self.osc_sender(base_addr = self.layers[i][j].osc_base_addr)
                    # mixer might drop packets withou sleep
                    time.sleep(0.01)
                    
        # get all mute groups
        for i in range(0, 4):
            self.osc_sender(base_addr = self.mute_groups[i].osc_base_addr)
            time.sleep(0.01)
        
        # 