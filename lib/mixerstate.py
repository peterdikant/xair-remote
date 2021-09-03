"""
This module holds the mixer state of the X-Air device
"""

import time
import subprocess
import struct
import json
from collections import deque
from lib.xair import XAirClient, find_mixer
from lib.midicontroller import MidiController

class Channel:
    """
    Represents a single channel or bus
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

    def toggle_mute(self, bus):
        """Toggle a mute on or off."""
        if bus == "/on" or bus == "":
            """Toggle the state of the channel mute."""
            if self.ch_on == 1:
                self.ch_on = 0
            else:
                self.ch_on = 1
            return(self.osc_base_addr + bus,
                    self.ch_on, self.ch_on)
        else:
            """Toggle the state of a send mute."""
            bus_num = int(bus) - 1
            if self.enables is not None:
                if self.enables[bus_num] == 1:
                    self.enables[bus_num] = 0
                    param=0.0
                else:
                    self.enables[bus_num] = 1
                    param=self.sends[bus_num]
                return(self.osc_base_addr + '/' + bus + '/level',
                        param, self.enables[bus_num])
            return(None, None, "Off")

    def set_mute(self, bus, value):
        """Set the state of the channel mute."""
        self.ch_on = value
        return(self.osc_base_addr + bus,
                self.ch_on, self.ch_on)

    def get_mute(self, bus):
        """Return the curent mute on/off."""
        if bus == "/on":
            return(self.ch_on)
        else:
            if self.enables is not None:
                bus_num = int(bus) - 1
                return(self.enables[bus_num])
        return ("Off")

    def change_level(self, bus, delta):
        """Change the level of a fader, mic pre, or bus send."""
        print("changing %s bus %s by %s" % (self.osc_base_addr, bus, delta))
        if bus == "fader" or bus == "gain":
            self.fader = min(max(0.0, self.fader + (delta / 200)), 1.0)
            return(self.osc_base_addr + '/' + bus,
                    self.fader, self.fader)
        if self.sends is not None:
            bus_num = int(bus) - 1
#            print("   changing channel %s/%s by %s from %s %s" % \
#                (self.osc_base_addr, bus_num, delta, self.sends[bus_num], bus))
            self.sends[bus_num] = \
                min(max(0.0, self.sends[bus_num] + (delta / 200)), 1.0)
            return('%s/%s/level' %(self.osc_base_addr, bus),
                    self.sends[bus_num], self.sends[bus_num])
        return (None, None,"Off")

    def set_level(self, bus, value):
        """Set the level of a fader, mic pre, or bus send."""
        if bus == "fader" or bus == "gain":
            self.fader = value
            return(self.osc_base_addr + '/' + bus,
                    self.fader, self.fader)
        if self.sends is not None:
            bus_num = int(bus) - 1
#            print("   setting channel %s/%s to %s from %s %s" % \
#                (self.osc_base_addr, bus_num, value, self.sends[bus_num], bus))
            self.sends[bus_num] = value
            return('%s/%s/level' %(self.osc_base_addr, bus),
                    self.sends[bus_num], self.sends[bus_num])
        return (None, None,"Off")

    def get_level(self, bus):
        """Return the current level of a fader, mic pre, or bus send."""
        if bus == "fader" or bus == "gain":
            return(self.fader)
        if self.sends is not None:
            bus_num = int(bus) - 1
            return(self.sends[bus_num])
        return (0)


# the config json file specifies a number of layers each idendified by a name
# within the layer there are currently two sections: encoders and buttons
# there are 8 encoders per section with three parts: channel, send/fader/gain, button

# fader, channel, [button]
# gain, channel
# level, channel, bus, [button]
# There are 18 buttons per section to types: lengths
button_def = {'quit': 3, 'none': 2, 'layer': 3, 'clip': 2, 'record': 2, 'mute': 3}
button_types = set(button_def.keys())

class Layer:
    """
    Represents a logical layer as defined by the config file
    """
    encoders = []
    buttons = []
    channels = {}

    def __init__(self, layer_name, config_layer, channels, layer_names) -> None:
        "Initialize a Layer"
        # first check for gross configurations errors
        errors = 0
        if "encoders" not in config_layer.keys():
            print("Error: Layer %s does not contain an encoders section." % layer_name)
            errors += 1
        if "buttons" not in config_layer.keys():
            print("Error: Layer %s contains an unknown section %s." % layer_name)
            errors += 1
        if errors > 0:
            print("Errors in config file, exiting.")
            exit()
        number = len(config_layer.keys())
        if number > 2:
            print("Warning: expected exactly two types of controls %d found" % number)

        # Process the encoders
        self.encoders = config_layer["encoders"]
        if len(self.encoders) != 8:
            print("Layer %s does not contain 8 'encoder' definitions." % layer_name)
        for encoder in self.encoders:
            if len(encoder) != 3:
                print("Error: Encoder %s of layer %s does not contain 3 elements, exiting." % \
                    (encoder[0], layer_name))
                exit()
            if encoder[0] != "none" and encoder[0] not in channels.keys():
                channels[encoder[0]] = Channel(encoder[0])
            if encoder[2][0] == "mute" and encoder[2][1] not in channels.keys():
                channels[encoder[2][1]] = Channel(encoder[2][1])

        # Process the buttons
        self.buttons = config_layer["buttons"]
        if len(self.buttons) != 18:
            print("Layer %s does not contain 18 'button' definitions." % layer_name)
        for button in self.buttons:
            if button[0] not in button_types:
                print("Layer %s contains an unknown 'button' %s." % \
                    (layer_name, button[0]))
                exit()
            if len(button) != button_def[button[0]]:
                print("Error: Button %s of layer %s does not contain %d elements" % \
                    (button[0], layer_name, button_def[button[0]]))
            if button[0] == "layer" and button[1] not in layer_names:
                print("Error: Layer %s has a change to undefined layer %s." % \
                    (layer_name, button[1]))
            if button[1] == "mute" and button[1] not in channels.keys():
                channels[button[1]] = Channel(button[1])

        self.channels = channels

    def encoder_turn(self, number, value):
        encoder = self.encoders[number]
        if encoder[0] != "none":
            return(self.channels[encoder[0]].change_level(encoder[1], value))
        return(None, None,"Off")

    def encoder_press(self, number):
        encoder = self.encoders[number]
        if encoder[2][0] == "reset":
            return(self.channels[encoder[0]].set_level(encoder[1], float(encoder[2][1])))
        elif encoder[2][0] == "mute":
            (address, param, LED) = self.channels[encoder[2][1]].toggle_mute(encoder[2][2])
            return(address, param, self.channels[encoder[0]].get_level(encoder[1]))
        if encoder[0] == "none":
            return(None, None,"Off")
        else:
            return(None, None, self.channels[encoder[0]].get_level(encoder[1]))

    def encoder_state(self, number):
        encoder = self.encoders[number]
        return(self.channels[encoder[0]].get_level(encoder[1]))

    def toggle_mute(self, number):
        button = self.buttons[number]
        if button[0] == "mute":
            return(self.channels[button[1]].toggle_mute(button[2]))
        else:
            # return the relevant action for the non mixer based button
            return(button[0], button[1], button[2] if len(button) > 2 else None )

    def mute_state(self, number):
        button = self.buttons[number]
        if button[0] == "mute":
            return(self.channels[button[1]].get_mute(button[2]))
        else:
            return(button[-1])

    def encoder_number(self, name):
        number = 0
        for encoder in self.encoders:
            if name == encoder[1]:
                return number
            number += 1
        return -1

    def button_number(self, name):
        number = 0
        for button in self.buttons:
            if name == button[1]:
                return number
            number += 1
        return -1

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
    layers = {}
    channels = {}
    current_layer = None

    # ID numbers for all available delay effects
    _DELAY_FX_IDS = [10, 11, 12, 21, 24, 25, 26]
    
    fx_slots = [0, 0, 0, 0]

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
        self.mac = False # args.mac
        self.levels = args.levels

        # initialize internal data structures
        if self.clip: # clipping protection doesn't work without level info
            self.levels = True

        config_json = "simple.json"
        if args.config_file is not None:
            config_json = args.config_file[0]
        with open(config_json) as config_file:
            config = json.load(config_file)

        layer_names = config.keys()

        for layer_name in layer_names:
            if self.current_layer == None:
                self.current_layer = layer_name
            self.layers[layer_name] = Layer(layer_name, config[layer_name],
                                            self.channels, layer_names)

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
        self.midi_controller.activate_bus()
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
#        if self.screen_obj is not None:
#            self.screen_obj.quit()

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

    def button_press(self, number):
        """Handle a button press."""
        if self.debug:
            print('Button %d pressed' % number)
        (address, param, LED) = self.layers[self.current_layer].toggle_mute(number)
        if address == 'layer':
            self.current_layer = param
            self.midi_controller.activate_bus()
            return self.get_button(number)
        elif address == 'clip':
            self.clip = not self.clip
            if self.clip:
                self.levels = True
                return "Off"
            else:
                return "On"
        elif address == 'quit':
            self.shutdown()
            exit()
        elif address == 'record':
            pass
            return "Off"
        if address != None:
            self.xair_client.send(address=address, param=param)
        return LED

    def get_button(self, number):
        if self.debug:
            print('Getting state of button number %d' % number)
        return(self.layers[self.current_layer].mute_state(number))

#    def mac_button(self, button):
#        "call a function for transport buttons on mac"
#        if button == 10:
#           os.system("""osascript -e 'tell application "music" to previous track'""")
#        elif button == 11:
#           os.system("""osascript -e 'tell application "music" to next track'""")
#        elif button == 12:
#            self.state.shutdown()
#           self.cleanup_controller()
#            exit()
#        elif button == 13:
#           os.system("""osascript -e 'tell application "music" to pause'""")
#        elif button == 14:
#            os.system("""osascript -e 'tell application "music" to play'""")

    def encoder_turn(self, number, delta):
        """Change the level of an encoder."""
        (address, param, LED) = self.layers[self.current_layer].encoder_turn(number, delta)
        if address != None:
            self.xair_client.send(address=address, param=param)
        return LED

    def encoder_press(self, number):
        (address, param, LED) = self.layers[self.current_layer].encoder_press(number)
        if address != None:
            self.xair_client.send(address=address, param=param)
        return LED

    def get_encoder(self, number):
        if self.debug:
            print('Getting state of encoder number %d' % number)
        return(self.layers[self.current_layer].encoder_state(number))

    def received_osc(self, addr, value):
        """Process an OSC input."""
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

        prefix = None
        three_element = '/'.join(addr.split('/',4)[:-1]) # first three parts of the OSC path
        two_element = '/'.join(addr.split('/',3)[:-1]) # first two parts of the OSC path
        if self.debug:
            print('processing OSC message with %s and %s value.' % (addr, value))
        if three_element in self.channels.keys():
            prefix = three_element
        elif two_element in self.channels.keys():
            prefix = two_element
        if prefix is not None:
            if addr.startswith('/config/mute'):
                number = '/'.join(addr.split('/')[-1])
                self.channels[prefix].set_mute(number, value)
                number = self.layers[self.current_layer].encoder_number(prefix)
                if number != -1:
                    self.midi_controller.set_channel_mute(number, value)
            elif addr.endswith('/fader'):     # chanel fader level
                if self.debug:
                    print('Channel %s level %f' % (addr, value))
                self.channels[prefix].set_level("fader", value)
                number = self.layers[self.current_layer].encoder_number(prefix)
                if number != -1:
                    self.midi_controller.set_ring(number, value)
            elif addr.endswith('/on'):      # channel enable
                if self.debug:
                    print('%s unMute %d' % (addr, value))
                self.channels[prefix].set_mute("/on", value)
                number = self.layers[self.current_layer].button_number(prefix)
                if number != -1:
                    self.midi_controller.set_channel_mute(number, value)
            elif addr.endswith('/level'):
                if self.debug:
                    print('%s level %f' % (addr, value))
                bus = int(addr[-8:-6])
                self.channels[prefix].set_level(bus, value)
                number = self.layers[self.current_layer].encoder_number(prefix)
                if number != -1:
                    self.midi_controller.set_ring(number, value)
            elif addr.endswith('/gain'):
                if self.debug:
                    print('%s Gain level %f' % (addr, value))
                self.channels[prefix].set_level("gain", value)
                number = self.layers[self.current_layer].encoder_number(prefix)
                if number != -1:
                    self.midi_controller.set_ring(number, value)

    def read_initial_state(self):
        """ Refresh state for all faders and mutes."""
        for channel in self.channels.values():
            addr = channel.osc_base_addr
            if addr.startswith('/head'):
                self.xair_client.send(address=addr + '/gain')
                time.sleep(0.002)
            else:
                self.xair_client.send(address=addr + '/fader')
                time.sleep(0.002)
                self.xair_client.send(address=addr + '/on')
                time.sleep(0.002)
                if channel.sends is not None:
                    for k in range(len(channel.sends)):
                        self.xair_client.send(address=addr + 
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
# the actual call is located in xair.py in the refresh connecton method that runs every 5 s
#
# meters 1 provide data per channel and bus
# self.xair_client.send(address="/meters", param=["/meters/1"]) # pre faid ch levels
# time.sleep(0.002)
#
# using meters 2, input levels, as these will match the headamps even if mapped to other channels
#        self.xair_client.send(address="/meters", param=["/meters/2"])
#        time.sleep(0.002)

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
                self.change_level(fader, -1) ## needs FIXME
                if self.debug:
                    print("Clipping Detected headamp changed to %s" %
                          self.banks[self.active_bank][fader].fader)
                self.active_bank = active_bank
        if self.debug:
            #print('Meters("%s", %s) size %s length %s' % (addr, data[0], len(data[0]), data_size))
            print('Meters %s ch 8 %s %s %s' % (addr, values[7], short[7], med[7]))
            #print(values)
#        if self.screen_obj is not None:
#            self.screen_obj.screen_loop()
