"""
This module holds the mixer state of the X-Air device
"""

import time
import subprocess
from lib.xair import XAirClient, find_mixer
from lib.midicontroller import MidiController

class Channel:
    """
    Represents a single channel strip
    """
    def __init__(self, addr):
        self.fader = 0.0
        if addr.startswith('/ch') or addr.startswith('/rtn'):
            self.sends = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        else:
            self.sends = None
        self.ch_on = 1
        self.osc_base_addr = addr

class MixerState:
    """
    This stores the mixer state in the application. It also keeps
    track of the current selected fader bank on the midi controller to
    decide whether state changes from the X-Air device need to be
    sent to the midi controller.
    """

    quit_called = False

    # ID numbers for all available delay effects
    _DELAY_FX_IDS = [10, 11, 12, 21, 24, 25, 26]
    
    fx_slots = [0, 0, 0, 0]

    active_bank = -1

    banks = []

    lr = Channel('/lr/mix')

    mute_groups = [
        Channel('/config/mute/1'),
        Channel('/config/mute/2'),
        Channel('/config/mute/3'),
        Channel('/config/mute/4')
    ]

    mpd_playing = True
    
    midi_controller = None
    xair_client = None

    def __init__(self, args) -> None:
        # split the arguments out to useful values
        self.debug = args.debug
        self.xair_address = args.xair_address
        self.monitor = args.monitor

        # Each layer has 8 encoders and 8 buttons
        if True: # enable addition of command line flags to alter bank layout
            self.banks = [[
                Channel('/ch/01/mix'),
                Channel('/ch/02/mix'),
                Channel('/ch/03/mix'),
                Channel('/ch/04/mix'),
                Channel('/ch/05/mix'),
                Channel('/ch/06/mix'),
                Channel('/ch/07/mix'),
                Channel('/ch/08/mix')
            ]]
        self.banks.append(
            [
                Channel('/ch/09/mix'),
                Channel('/ch/10/mix'),
                Channel('/ch/11/mix'),
                Channel('/ch/12/mix'),
                Channel('/ch/13/mix'),
                Channel('/ch/14/mix'),
                Channel('/ch/15/mix'),
                Channel('/ch/16/mix')
            ])
        self.banks.append(
            [
                Channel('/rtn/aux/mix'),
                None,
                None,
                None,
                Channel('/dca/1'),
                Channel('/dca/2'),
                Channel('/dca/3'),
                Channel('/dca/4')
            ])
        self.banks.append(
            [
                Channel('/fxsend/1/mix'),
                Channel('/fxsend/2/mix'),
                Channel('/fxsend/3/mix'),
                Channel('/fxsend/4/mix'),
                Channel('/rtn/1/mix'),
                Channel('/rtn/2/mix'),
                Channel('/rtn/3/mix'),
                Channel('/rtn/4/mix')
            ])
        self.banks.append(
            [
                Channel('/bus/1/mix'),
                Channel('/bus/2/mix'),
                Channel('/bus/3/mix'),
                Channel('/bus/4/mix'),
                Channel('/bus/5/mix'),
                Channel('/bus/6/mix'),
                None,
                None
            ])

    def initialize_state(self):
        self.quit_called = False
        # determine the mixer address
        if self.xair_address is None:
            self.xair_address = find_mixer()
            if self.xair_address is None:
                print('Error: Could not find any mixers in network.',
                      'Using default ip address.')
                return False

        # setup other modules
        self.midi_controller = MidiController(self)
        if self.quit_called:
            self.midi_controller = None
            return False
        self.xair_client = XAirClient(self.xair_address, self)
        self.xair_client.validate_connection()
        if self.quit_called:
            self.midi_controller = None
            self.xair_client = None
            return False

        self.read_initial_state()
        return True

    def shutdown(self):
        self.quit_called = True
        "safely shutdown all threads"
        if self.xair_client is not None:
            self.xair_client.stop_server()
            self.xair_client = None
        if self.midi_controller is not None:
            self.midi_controller.cleanup_controller()
            self.midi_controller = None

    def toggle_mute_group(self, group):
        if self.mute_groups[group].ch_on == 1:
            self.mute_groups[group].ch_on = 0
        else:
            self.mute_groups[group].ch_on = 1
        self.xair_client.send(
            address=self.mute_groups[group].osc_base_addr, 
            param=self.mute_groups[group].ch_on)
        self.midi_controller.set_mute_grp(group, self.mute_groups[group].ch_on)

    def toggle_channel_mute(self, channel):
        """Toggle the state of a channel mute button."""
        if self.banks[self.active_bank][channel] is not None:
            if self.banks[self.active_bank][channel].ch_on == 1:
                self.banks[self.active_bank][channel].ch_on = 0
            else:
                self.banks[self.active_bank][channel].ch_on = 1
            self.xair_client.send(
                address=self.banks[self.active_bank][channel].osc_base_addr + '/on',
                param=self.banks[self.active_bank][channel].ch_on)
            self.midi_controller.set_channel_mute(
                channel, self.banks[self.active_bank][channel].ch_on)

    def toggle_mpc(self):
        if self.mpd_playing:
            try:
                subprocess.call(['mpc', 'pause'])
            except OSError:
                pass
            self.mpd_playing = False
        else:
            try:
                subprocess.call(['mpc', 'play'])
            except OSError:
                pass
            self.mpd_playing = True

    def change_fader(self, fader, delta):
        """Change the level of a fader."""
        if self.banks[self.active_bank][fader] is not None:
            self.banks[self.active_bank][fader].fader = \
                min(max(0.0, self.banks[self.active_bank][fader].fader + (delta / 200)), 1.0)
            self.xair_client.send(
                address=self.banks[self.active_bank][fader].osc_base_addr + '/fader',
                param=self.banks[self.active_bank][fader].fader)
            self.midi_controller.set_channel_fader(fader, self.banks[self.active_bank][fader].fader)

    def change_bus_send(self, bus, channel, delta):
        """Change the level of a bus send."""
        if ((self.banks[self.active_bank][channel] is not None)
                and self.banks[self.active_bank][channel].sends is not None):
            self.banks[self.active_bank][channel].sends[bus] = \
                min(max(0.0, self.banks[self.active_bank][channel].sends[bus] + (delta / 200)), 1.0)
            self.xair_client.send(
                address=self.banks[self.active_bank][channel].osc_base_addr + \
                    '/{:0>2d}/level'.format(bus + 1),
                param=self.banks[self.active_bank][channel].sends[bus])
            self.midi_controller.set_bus_send(bus, channel, self.banks[self.active_bank][channel].sends[bus])

    def set_lr_fader(self, value):
        self.xair_client.send(address = self.lr.osc_base_addr + '/fader', param = value)

    def received_osc(self, addr, value):
        """Process an OSC input."""
        if addr.startswith('/config/mute'):
            group = int(addr[-1:]) - 1
            self.mute_groups[group].ch_on = value
            self.midi_controller.set_mute_grp(group, value)
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
                    if self.banks[i][j] is not None and addr.startswith(self.banks[i][j].osc_base_addr):
                        if addr.endswith('/fader'):     # chanel fader level
                            if self.debug:
                                print('Channel %s level %f' % (addr, value))
                            self.banks[i][j].fader = value
                            if i == self.active_bank:
                                self.midi_controller.set_ring(j, value)
                        elif addr.endswith('/on'):      # channel enable
                            if self.debug:
                                print('%s unMute %d' % (addr, value))
                            self.banks[i][j].ch_on = value
                            if i == self.active_bank:
                                self.midi_controller.set_channel_mute(j, value)
                        elif self.banks[i][j].sends is not None and addr.endswith('/level'):
                            if self.debug:
                                print('%s level %f' % (addr, value))
                            bus = int(addr[-8:-6]) - 1
                            self.banks[i][j].sends[bus] = value
                            if i == self.active_bank:
                                self.midi_controller.set_bus_send(bus, j, value)
                        break
                else:
                    continue
                break

    def read_initial_state(self):
        """ Refresh state for all faders and mutes."""
        for i in range(0, 5):
            for j in range(0, 8):
                if self.banks[i][j] is not None:
                    self.xair_client.send(address=self.banks[i][j].osc_base_addr + '/fader')
                    time.sleep(0.01)
                    self.xair_client.send(address=self.banks[i][j].osc_base_addr + '/on')
                    time.sleep(0.01)
                    if self.banks[i][j].sends is not None:
                        for k in range(len(self.banks[i][j].sends)):
                            self.xair_client.send(address = self.banks[i][j].osc_base_addr + '/{:0>2d}/level'.format(k + 1))
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
        