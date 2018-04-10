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
    
    # ID numbers for all available delay effects
    _DELAY_FX_IDS = [10, 11, 12, 21, 24, 25, 26]
    
    fx_slots = [0, 0, 0, 0]
    
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
    
    midi_controller = None
    xair_client = None
    
    def received_midi(self, channel = None, mute_group = None, fader = None, on = None):
        if channel != None:
            if channel < 9 and self.layers[self.active_layer][channel] != None:
                if fader != None:
                    self.layers[self.active_layer][channel].fader = fader / 127.0
                    self.xair_client.send(address = self.layers[self.active_layer][channel].osc_base_addr + '/fader', 
                            param = self.layers[self.active_layer][channel].fader)
                elif on != None:
                    self.layers[self.active_layer][channel].on = on
                    self.xair_client.send(address = self.layers[self.active_layer][channel].osc_base_addr + '/on', 
                            param = self.layers[self.active_layer][channel].on)
                return True
            elif channel == 9:
                if fader != None:
                    self.lr.fader = fader / 127.0
                    self.xair_client.send(address = self.lr.osc_base_addr + '/fader', param = self.lr.fader)
                return True
        elif mute_group != None:
            self.mute_groups[mute_group].on = on
            self.xair_client.send(address = self.mute_groups[mute_group].osc_base_addr, 
                    param = self.mute_groups[mute_group].on)
        return False
    
    def received_osc(self, addr, value):
        if addr.startswith('/config/mute'):
            group = int(addr[-1:]) - 1
            self.mute_groups[group].on = value
            self.midi_controller.send(mute_group = group, on = self.mute_groups[group].on)
        elif addr.startswith('/fx') and (addr.endswith('/par/01') or addr.endswith('/par/02')):
            if self.fx_slots[int(addr[4:5]) - 1] in self._DELAY_FX_IDS:
                self.midi_controller.update_tempo(value * 3)
        elif addr.startswith('/fx/') and addr.endswith('/type'):
            self.fx_slots[int(addr[4:5]) - 1] = value
            if value in self._DELAY_FX_IDS:
                # slot contains a delay, get current time value
                param_id = '01'
                if value == 10:
                    param_id = '02'
                self.xair_client.send(address = '/fx/%s/par/%s' % (addr[4:5], param_id))
        else:
            for i in range(0, 5):
                for j in range(0, 8):
                    if self.layers[i][j] != None and addr.startswith(self.layers[i][j].osc_base_addr):
                        if addr.endswith('/fader'):
                            self.layers[i][j].fader = value
                            if i == self.active_layer:
                                self.midi_controller.send(channel = j, fader = int(self.layers[i][j].fader * 127))
                        elif addr.endswith('/on'):
                            self.layers[i][j].on = value
                            if i == self.active_layer:
                                self.midi_controller.send(channel = j, on = self.layers[i][j].on)
                        break
                else:
                    continue
                break
    
    def read_initial_state(self):
        # Refresh state for all faders and mutes
        for i in range(0, 5):
            for j in range(0, 8):
                if self.layers[i][j] != None:
                    self.xair_client.send(address = self.layers[i][j].osc_base_addr + '/fader')
                    time.sleep(0.01)
                    self.xair_client.send(address = self.layers[i][j].osc_base_addr + '/on')
                    time.sleep(0.01)
                    
        # get all mute groups
        for i in range(0, 4):
            self.xair_client.send(address = self.mute_groups[i].osc_base_addr)
            time.sleep(0.01)
        
        # get all fx types
        for i in range(1, 5):
            self.xair_client.send(address = '/fx/%d/type' % i)
            time.sleep(0.01)
    
    def update_tempo(self, tempo):
        for i in range(0, 4):
            if self.fx_slots[i] in self._DELAY_FX_IDS:
                param_id = '01'
                if self.fx_slots[i] == 10:
                    # only delay where time is set as parameter 02
                    param_id = '02'
                self.xair_client.send(address = '/fx/%d/par/%s' % (i + 1, param_id), param = tempo / 3)
        