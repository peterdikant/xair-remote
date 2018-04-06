
"""
This module holds the mixer state of the X-Air device
"""

class Channel:
    fader = 0.0
    mute = False
    osc_base_path = ''
    
    def __init__(self, path):
        self.osc_base_path = path
        

class MixerState:
    """docstring for Mixer"""
    
    active_layer = -1
    # Each layer has 8 encoders and 8 buttons
    layers = [
        [
            Channel('/ch/01/mix/'),
            Channel('/ch/02/mix/'),
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
    
    def __init__(self):
        pass
    
    def received_midi(self, channel, fader = None, mute = None):
        if channel < 9 and self.layers[self.active_layer][channel] != None:
            if fader != None:
                self.layers[self.active_layer][channel].fader = fader / 127.0
                if self.osc_sender != None:
                    self.osc_sender(path = self.layers[self.active_layer][channel].osc_base_path, 
                        fader = self.layers[self.active_layer][channel].fader)
            elif mute != None:
                self.layers[self.active_layer][channel].mute = mute
                if self.osc_sender != None:
                    self.osc_sender(path = self.layers[self.active_layer][channel].osc_base_path, 
                        mute = self.layers[self.active_layer][channel].mute)
            return True
        elif channel == 9:
            if fader != None:
                self.lr.fader = fader / 127.0
                if self.osc_sender != None:
                    self.osc_sender(path = self.lr.osc_base_path, 
                        fader = self.lr.fader)
        else:
            return False
    
    def received_osc(self, path, value):
        for i in range(0, 5):
            for j in range(0, 8):
                if self.layers[i][j] != None and path.startswith(self.layers[i][j]):
                    if path.endswith('/fader'):
                        self.layers[i][j].fader = value
                        if self.midi_sender != None and i == self.active_layer:
                            self.midi_sender(channel = j, fader = int(self.layers[i][j].fader * 127))
                    elif path.endswith('/on'):
                        self.layers[i][j].mute = value
                        if self.midi_sender != None and i == self.active_layer:
                            self.midi_sender(channel = j, mute = self.layers[i][j].mute)
                    break
            else:
                continue
            break