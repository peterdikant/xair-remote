"""
This module holds the mixer state of the X-Air device
"""

import time
import subprocess
import struct
from collections import deque
from lib.xair import XAirClient, find_mixer
from lib.midicontroller import MidiController

class Channel:
    """
    Represents a single channel strip
    """
    def __init__(self, addr):
        self.fader = 0.0
        if addr.startswith('/ch'):
            # the 6 aux bus followed by the 4 effects
            self.sends = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            self.enables = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        else:
            self.sends = None
            self.enables = None
        self.ch_on = 1
        self.osc_base_addr = addr

class Meter:
    """
    Calculates the .2 second running average of the value of a channel meter
    """
    values = 4
    def __init__(self):
        self.levels = deque(maxlen=self.values)
        for _ in range(self.values):
            self.levels.append(-102400)
        self.mean = -102400 * self.values

    def insert_level(self, value):
        'push a vlue into the fixed FIFO and update the mean'
        self.mean = self.mean - self.levels.popleft() + value
        self.levels.append(value)
        return self.mean

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
    active_bus = -1

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

    meters = []
    for i in range(16):
        meters.append(Meter())

    def __init__(self, args) -> None:
        # split the arguments out to useful values
        self.debug = args.debug
        self.xair_address = args.xair_address
        self.monitor = args.monitor
        self.clip = args.clip
        self.mac = args.mac
        self.levels = args.levels

        # initialize internal data structures
        if self.clip: # clipping protection doesn't work without level info
            self.levels = True

        # Each layer has 8 encoders and 8 buttons
        if self.mac: # only a single layer, use second row of buttons as transport control
            self.banks = [[
                Channel('/ch/08/mix'),
                Channel('/ch/07/mix'),
                Channel('/ch/06/mix'),
                Channel('/ch/05/mix'),
                Channel('/bus/1/mix'),
                Channel('/bus/2/mix'),
                Channel('/rtn/aux/mix'),
                Channel('/lr/mix')
            ]]
        else:
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
                Channel('/headamp/01'),
                Channel('/headamp/02'),
                Channel('/headamp/03'),
                Channel('/headamp/04'),
                Channel('/headamp/05'),
                Channel('/headamp/06'),
                Channel('/headamp/07'),
                Channel('/headamp/08')
            ])
        self.banks.append(
            [
                Channel('/headamp/09'),
                Channel('/headamp/10'),
                Channel('/headamp/11'),
                Channel('/headamp/12'),
                Channel('/headamp/13'),
                Channel('/headamp/14'),
                Channel('/headamp/15'),
                Channel('/headamp/16')
            ])
        self.banks.append(
            [
                Channel('/bus/1/mix'),
                Channel('/bus/2/mix'),
                Channel('/bus/3/mix'),
                Channel('/bus/4/mix'),
                Channel('/bus/5/mix'),
                Channel('/bus/6/mix'),
                Channel('/rtn/aux/mix'),
                Channel('/lr/mix')
            ])

    def initialize_state(self):
        self.quit_called = False
        # determine the mixer address
        if self.xair_address is None:
            self.xair_address = find_mixer()
            if self.xair_address is None:
                print('Error: Could not find any mixers in network.',
                      'Using default ip address.')
                self.xair_address = "192.168.50.146"

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
        self.midi_controller.activate_bus(0)     # in case of reset
        self.midi_controller.activate_bus(8)     # set chanel level as initial bus
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

    def toggle_send_mute(self, channel, bus):
        """Toggle the state of a send mute."""
        if self.debug:
            print('Toggle Send Mute %d %d' % (channel, bus))
        if ((self.banks[self.active_bank][channel] is not None)
                and self.banks[self.active_bank][channel].enables is not None):
            if self.banks[self.active_bank][channel].enables[bus] == 1:
                self.banks[self.active_bank][channel].enables[bus] = 0
                self.xair_client.send(
                    address=self.banks[self.active_bank][channel].osc_base_addr +
                    '/{:0>2d}/level'.format(bus + 1),
                    param=0.0)
            else:
                self.banks[self.active_bank][channel].enables[bus] = 1
                self.xair_client.send(
                    address=self.banks[self.active_bank][channel].osc_base_addr +
                    '/{:0>2d}/level'.format(bus + 1),
                    param=self.banks[self.active_bank][channel].sends[bus])
            self.midi_controller.set_channel_mute(channel, \
                self.banks[self.active_bank][channel].enables[bus])

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

    def set_fader(self, fader, value):
        """Set the level of a fader."""
        if self.banks[self.active_bank][fader] is not None:
            self.banks[self.active_bank][fader].fader = value
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
            self.midi_controller.set_channel_fader(channel, \
                self.banks[self.active_bank][channel].sends[bus])

    def set_bus_send(self, bus, channel, value):
        """Set the level of a bus send."""
        if ((self.banks[self.active_bank][channel] is not None)
                and self.banks[self.active_bank][channel].sends is not None):
            self.banks[self.active_bank][channel].sends[bus] = value
            self.xair_client.send(
                address=self.banks[self.active_bank][channel].osc_base_addr + \
                    '/{:0>2d}/level'.format(bus + 1),
                param=self.banks[self.active_bank][channel].sends[bus])
            self.midi_controller.set_channel_fader(channel, \
                self.banks[self.active_bank][channel].sends[bus])

    def change_headamp(self, fader, delta): # aka mic pre
        """Change the level of a mic pre aka headamp."""
        if self.banks[self.active_bank][fader] is not None:
            self.banks[self.active_bank][fader].fader = \
                min(max(0.0, self.banks[self.active_bank][fader].fader + (delta / 200)), 1.0)
            self.xair_client.send(
                address=self.banks[self.active_bank][fader].osc_base_addr + '/gain',
                param=self.banks[self.active_bank][fader].fader)
            self.midi_controller.set_channel_fader(fader, self.banks[self.active_bank][fader].fader)

    def set_lr_fader(self, value):
        self.xair_client.send(address = self.lr.osc_base_addr + '/fader', param = value)

    def received_osc(self, addr, value):
        """Process an OSC input."""
#        if addr.startswith('/config/mute'):
#            group = int(addr[-1:]) - 1
#            self.mute_groups[group].ch_on = value
#            self.midi_controller.set_mute_grp(group, value)
#        elif addr.startswith('/fx') and (addr.endswith('/par/01') or addr.endswith('/par/02')):
#            if self.fx_slots[int(addr[4:5]) - 1] in self._DELAY_FX_IDS:
#                self.midi_controller.update_tempo(value * 3)
#        elif addr.startswith('/fx/') and addr.endswith('/type'):
#            self.fx_slots[int(addr[4:5]) - 1] = value
#            if value in self._DELAY_FX_IDS:
#                # slot contains a delay, get current time value
#                param_id = '01'
#                if value == 10:
#                    param_id = '02'
#                self.xair_client.send(address = '/fx/%s/par/%s' % (addr[4:5], param_id))
        if True:
            for i in range(0, 5):
                for j in range(0, 8):
                    if self.banks[i][j] is not None and addr.startswith(self.banks[i][j].osc_base_addr):
                        if addr.endswith('/fader'):     # chanel fader level
                            if self.debug:
                                print('Channel %s level %f' % (addr, value))
                            self.banks[i][j].fader = value
                            if i == self.active_bank and self.active_bus in [8, 9]:
                                self.midi_controller.set_channel_fader(j, value)
                        elif addr.endswith('/on'):      # channel enable
                            if self.debug:
                                print('%s unMute %d' % (addr, value))
                            self.banks[i][j].ch_on = value
                            if i == self.active_bank and self.active_bus in [8, 9]:
                                self.midi_controller.set_channel_mute(j, value)
                        elif self.banks[i][j].sends is not None and addr.endswith('/level'):
                            if self.debug:
                                print('%s level %f' % (addr, value))
                            bus = int(addr[-8:-6]) - 1
                            self.banks[i][j].sends[bus] = value
                            if i == self.active_bank and bus == self.active_bus:
                                self.midi_controller.set_channel_fader(j, value)
                        elif addr.endswith('/gain'):
                            if self.debug:
                                print('%s Gain level %f' % (addr, value))
                            self.banks[i][j].fader = value
                            if i == self.active_bank:   #doesn't need a bus check as only on one bus
                                self.midi_controller.set_channel_fader(j, value)
                        break
                else:
                    continue
                break

    def read_initial_state(self):
        """ Refresh state for all faders and mutes."""
        for i in range(0, 5):
            for j in range(0, 8):
                if self.banks[i][j] is not None:
                    if self.banks[i][j].osc_base_addr.startswith('/head'):
                        self.xair_client.send(address=self.banks[i][j].osc_base_addr + '/gain')
                        time.sleep(0.002)
                    else:
                        self.xair_client.send(address=self.banks[i][j].osc_base_addr + '/fader')
                        time.sleep(0.002)
                        self.xair_client.send(address=self.banks[i][j].osc_base_addr + '/on')
                        time.sleep(0.002)
                        if self.banks[i][j].sends is not None:
                            for k in range(len(self.banks[i][j].sends)):
                                self.xair_client.send(address=self.banks[i][j].osc_base_addr + \
                                    '/{:0>2d}/level'.format(k + 1))
                                time.sleep(0.002)
           
        # get all mute groups
        #for i in range(0, 4):
        #    self.xair_client.send(address = self.mute_groups[i].osc_base_addr)
        #    time.sleep(0.01)
        
        # get all fx types
        #for i in range(1, 5):
        #    self.xair_client.send(address = '/fx/%d/type' % i)
        #    time.sleep(0.01)
    
    def update_tempo(self, tempo):
        for i in range(0, 4):
            if self.fx_slots[i] in self._DELAY_FX_IDS:
                param_id = '01'
                if self.fx_slots[i] == 10:
                    # only delay where time is set as parameter 02
                    param_id = '02'
                self.xair_client.send(address = '/fx/%d/par/%s' % (i + 1, param_id), param = tempo / 3)

# how to set up a meter subscription
# values send every 50ms for 10s
# the actual call is located in xair.py in the refresch connecton method that runs every 5 s
#
# meters 1 provide data per channel and bus
# self.xair_client.send(address="/meters", param=["/meters/1"]) # pre faid ch levels
# time.sleep(0.002)
#
# using meters 2, input levels, as these will match the headamps even if mapped to other channels
#        self.xair_client.send(address="/meters", param=["/meters/2"])
#        time.sleep(0.002)
# channel levels, not entirely clear
#        self.xair_client.send(address="/meters", param=["/meters/0", 7])
#        time.sleep(0.002)
#self.xair_client.send(address="/meters/13")
#time.sleep(0.002)

    def received_meters(self, addr, data):
        "receive an OSC Meters packet"
        data_size = struct.unpack("<L", data[0][0:4])[0]
        values = []
        short = []
        med = []
        for i in range(data_size):
            if i > 15:
                break
            # get the current meter as a 16bit signed int mapped to -128db to 128db
            # 1/256 db resolution, aka .004 dB
            # realistic values max at 0db
            value = struct.unpack("<h", data[0][(4+(i*2)):4+((i+1)*2)])[0]
            # push the value into the fixed length fifo and get the smoothed value
            smooth = self.meters[i].insert_level(value)/1024
            if self.debug:
                values.append("%0.2f" % smooth)
                short.append(value)
                med.append(value/256)
            if self.clip and smooth > -3 and (i < 8 or i > 11):
                # if clip protection is enabled and not a drum and above -3 db
                active_bank = self.active_bank
                fader = i
                if fader < 8:
                    self.active_bank = 2
                else:
                    self.active_bank = 3
                    fader = fader - 8
                self.change_headamp(fader, -1)
                if self.debug:
                    print("Clipping Detected headamp changed to %s" %
                          self.banks[self.active_bank][fader].fader)
                self.active_bank = active_bank
        if self.debug:
            #print('Meters("%s", %s) size %s length %s' % (addr, data[0], len(data[0]), data_size))
            print('Meters %s ch 8 %s %s %s' % (addr, values[7], short[7], med[7]))
            #print(values)
        if self.screen_obj is not None:
            self.screen_obj.screen_loop()
