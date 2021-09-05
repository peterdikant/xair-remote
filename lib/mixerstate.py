"This module holds the mixer state of the X-Air device"
# part of xair-remote.py
# Copyright (c) 2018, 2021 Peter Dikant
# Additions Copyright (c) 2021 Ross Dickson
# Some rights reserved. See LICENSE.

import time
import subprocess
import struct
import json
from collections import deque
from lib.xair import XAirClient, find_mixer
from lib.midicontroller import MidiController, TempoDetector

class Channel:
    """
    Represents a single channel or bus
    """
    def __init__(self, addr):
        # LR then 6 aux bus followed by the 4 effects
        self.sends = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.enables = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        self.osc_base_addr = addr

    def get_m_addr(self, bus):
        if bus == 0:
            if self.osc_base_addr.startswith('/config'):
                return(self.osc_base_addr)
            else:
                return(self.osc_base_addr + "/on")
        else:
            return(self.osc_base_addr + '/{:0>2d}/level'.format(bus))

    def get_l_addr(self, bus):
        if bus == 0:
            if self.osc_base_addr.startswith('/head'):
                return(self.osc_base_addr + "/gain")
            else:
                return(self.osc_base_addr + "/fader")
        else:
            return(self.osc_base_addr + '/{:0>2d}/level'.format(bus))

    def toggle_mute(self, bus):
        """Toggle a mute on or off."""
#        print("toggle mute of %s bus %s from %s" % (self.get_m_addr(bus), bus, self.enables[bus]))
        if self.enables[bus] == 1:
            self.enables[bus] = 0
            param=0.0
        else:
            self.enables[bus] = 1
            param=self.sends[bus]
        if bus == 0:
           return(self.get_m_addr(bus), self.enables[bus], self.enables[bus])
        else:
            return(self.get_m_addr(bus), param, self.enables[bus])

    def set_mute(self, bus, value):
        """Set the state of the channel mute."""
        self.enables[bus] = value
        return(self.get_m_addr(bus), self.enables[bus], self.enables[bus])

    def get_mute(self, bus):
        return(self.enables[bus])

    def change_level(self, bus, delta):
        """Change the level of a fader, mic pre, or bus send."""
#        print("changing %s bus %s by %s" % (self.osc_base_addr, bus, delta))
        if bus == "gain":
            bus = 0
        self.sends[bus] = min(max(0.0, self.sends[bus] + (delta / 200)), 1.0)
        return(self.get_l_addr(bus), self.sends[bus], self.sends[bus])

    def set_level(self, bus, value):
        """Set the level of a fader, mic pre, or bus send."""
        if bus == "gain":
            bus = 0
        self.sends[bus] = value
        return(self.get_l_addr(bus),
                    self.sends[bus], self.sends[bus])

    def get_level(self, bus):
        """Return the current level of a fader, mic pre, or bus send."""
        if bus == "gain":
            bus = 0
        return(self.sends[bus])

class SubProc:
    """
    Manages a subprocess
    """
    def __init__(self, call_type, proc_name, args) -> None:
        self.call_type = call_type
        self.proc_name = proc_name
        self.args = args
        self.max = len(args)
        self.current = 0

    def toggle(self):
        if self.call_type == "subprocess":
            try:
                subprocess.call([self.proc_name, self.args[self.current]])
            except OSError:
                pass
            self.current += (self.current + 1) % self.max

# the config json file specifies a number of layers each idendified by a name
# within the layer there are currently two sections: encoders and buttons
# there are 8 encoders per section with three parts: channel, send/fader/gain, button

# fader, channel, [button]
# gain, channel
# level, channel, bus, [button]
# There are 18 buttons per section to types: lengths
button_def = {'quit': 3, 'none': 2, 'layer': 4, 'clip': 2, 'mute': 3, 'tap': 2, "send": 3}
button_types = set(button_def.keys())

class Layer:
    """
    Represents a logical layer as defined by the config file
    """
    encoders = []
    buttons = []
    faders = []
    channels = {}
    proc_list = {}
    active_bus = 0

    def __init__(self, layer_name, config_layer, channels, layer_names, proc_list) -> None:
        "Initialize a Layer"
        # first check for gross configurations errors
        number = len(config_layer.keys())
        if number > 3:
            print("Warning: expected exactly three types of controls %d found" % number)

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
            elif encoder[2][0] == "subprocess" and encoder[2][1] not in proc_list.keys():
                proc_list[encoder[2][1]] = SubProc(encoder[2][0], encoder[2][1], encoder[2][2])

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
            if button[0] == "mute" and button[1] not in channels.keys():
                channels[button[1]] = Channel(button[1])

        # Process the fader
        self.faders = config_layer["fader"]
        if len(self.faders) != 1:
            print("Layer %s does not contain 1 'fader' definitions." % layer_name)
        for fader in self.faders:
            if len(fader) != 2:
                print("Error: Fader %s of layer %s does not contain 2 elements, exiting." % \
                    (fader[0], layer_name))
                exit()
            if fader[0] != "none" and fader[0] != "quit" and fader[0] not in channels.keys():
                channels[fader[0]] = Channel(fader[0])

        self.channels = channels
        self.proc_list = proc_list

    def encoder_turn(self, number, value):
        encoder = self.encoders[number]
        if encoder[0] == "none":
            return(None, None, 0.0)
        return(self.channels[encoder[0]].change_level(self.active_bus, value))

    def encoder_press(self, number):
        encoder = self.encoders[number]
        if encoder[2][0] == "reset":
            return(self.channels[encoder[0]].set_level(self.active_bus, float(encoder[2][1])))
        elif encoder[2][0] == "mute":
            (address, param, LED) = self.channels[encoder[2][1]].toggle_mute(int(encoder[2][2]))
            return(address, param, self.channels[encoder[0]].get_level(self.active_bus))
        elif encoder[2][0] == "subprocess":
            self.proc_list[encoder[2][1]].toggle()
            return(None, None, self.channels[encoder[0]].get_level(self.active_bus))
        if encoder[0] == "none":
            return(None, None, 0.0)
        return(None, None, self.channels[encoder[0]].get_level(self.active_bus))

    def encoder_state(self, number):
        encoder = self.encoders[number]
        if encoder[0] == "none":
            return 0.0
        return(self.channels[encoder[0]].get_level(self.active_bus))

    def toggle_button(self, number):
        button = self.buttons[number]
        if button[0] == "mute":
            return (self.channels[button[1]].toggle_mute(self.active_bus))
        if button[0] == "layer":
            max_bus = int(button[2])
            return ("layer", button[1], max_bus if self.active_bus > max_bus else self.active_bus)
        if button[0] == "send":
            if self.active_bus == int(button[1]):
                self.active_bus = 0
                return ("send", None, "Off")
            else:
                self.active_bus = int(button[1])
                return ("send", None, "On")
        # return the relevant action for the non mixer based button
        return (button[0], button[1], button[-1])

    def button_state(self, number):
        button = self.buttons[number]
        if button[0] == "mute":
            return(self.channels[button[1]].get_mute(self.active_bus))
        elif button[0] == "send":
            return("On" if self.active_bus == int(button[1]) else "Off")
        else:
            return(button[-1])

    def fader_move(self, value):
        if self.faders[0][0] == "quit":
            return("quit", "none", "none")
        else:
            return(self.channels[self.faders[0][0]].set_level(int(self.faders[0][1]), value))

    def encoder_number(self, name):
        number = 0
        for encoder in self.encoders:
            if name == encoder[0]:
                return number
            number += 1
        return -1

    def button_number(self, name):
        number = 0
        for button in self.buttons:
            if len(button) > 1 and name == button[1]:
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
    proc_list = {}
    current_layer = None

    # ID numbers for all available delay effects
    _DELAY_FX_IDS = [10, 11, 12, 21, 24, 25, 26]
    
    fx_slots = [0, 0, 0, 0]

    lr = Channel('/lr/mix')

    mpd_playing = True

    midi_controller = None
    xair_client = None
    tempo_detector = None

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
        config_json = "peterdikant.json"
        if args.config_file is not None:
            config_json = args.config_file[0]
        with open(config_json) as config_file:
            config = json.load(config_file)

        layer_names = config.keys()

        for layer_name in layer_names:
            if self.current_layer == None:
                self.current_layer = layer_name
            self.layers[layer_name] = Layer(layer_name, config[layer_name],
                                            self.channels, layer_names, self.proc_list)

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
        self.tempo_detector = TempoDetector(self)

        self.read_initial_state()
        self.midi_controller.activate_bus()
        self.tempo_detector.number = self.layers[self.current_layer].button_number("tap")
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

    def button_press(self, number):
        """Handle a button press."""
        if self.debug:
            print('Button %d pressed' % number)
        (address, param, LED) = self.layers[self.current_layer].toggle_button(number)
        if address == 'layer':
            self.current_layer = param
            self.layers[self.current_layer].active_bus = LED
            self.midi_controller.activate_bus()
            self.tempo_detector.number = self.layers[self.current_layer].button_number("tap")
            return self.get_button(number)
        elif address == 'send':
            self.midi_controller.activate_bus()
            return LED
        elif address == 'clip':
            self.clip = not self.clip
            return "On" if self.clip else "Off"
        elif address == 'quit':
            self.shutdown()
            exit()
        elif address == 'record':
            pass
            return "Off"
        elif address == 'tap':
            self.tempo_detector.tap()
            return "none"
        if address != None:
            if address.startswith('/config/mute'):
                param = 1 if param == 0 else 0
            self.xair_client.send(address=address, param=param)
        return LED

    def get_button(self, number):
        if self.debug:
            print('Getting state of button number %d' % number)
        return(self.layers[self.current_layer].button_state(number))

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
            print("sending %s %s" % (address, param))
            if address.startswith('/config/mute'):
                invert = 1 if param == 0 else 0
                self.xair_client.send(address=address, param=invert)
                number = self.layers[self.current_layer].button_number(address)
                if number != -1:
                    self.midi_controller.set_channel_mute(number, param)
            else:
                self.xair_client.send(address=address, param=param)
        return LED

    def get_encoder(self, number):
        if self.debug:
            print('Getting state of encoder number %d' % number)
        return(self.layers[self.current_layer].encoder_state(number))

    def fader_move(self, msg):
        value = (msg.pitch + 8192) / 16384
        if self.debug:
            print('Wheel set to {}'.format(msg))
        (address, param, LED) = self.layers[self.current_layer].fader_move(value)
        if address == "quit":
            if value > .98:
                self.shutdown()
                exit()
        elif address != None:
            self.xair_client.send(address=address, param=param)

    def received_osc(self, addr, value):
        """Process an OSC input."""
        prefix = None
        three_element = '/'.join(addr.split('/',4)[:-1]) # first three parts of the OSC path
        two_element = '/'.join(addr.split('/',3)[:-1]) # first two parts of the OSC path
        if self.debug:
            print('processing OSC message with %s and %s value.' % (addr, value))
        if three_element in self.channels.keys():
            prefix = three_element
        elif two_element in self.channels.keys():
            prefix = two_element
        elif addr in self.channels.keys():
            prefix = addr
        if prefix is not None:
            if addr.startswith('/config/mute'):
                invert = 1 if value == 0 else 0
                if self.debug:
                    print ("  received mute channel %s" % prefix)
                self.channels[prefix].set_mute(0, invert)
                number = self.layers[self.current_layer].button_number(prefix)
                if number != -1:
                    self.midi_controller.set_channel_mute(number, invert)
            elif addr.endswith('/fader'):     # chanel fader level
                if self.debug:
                    print('  Channel %s level %f' % (addr, value))
                self.channels[prefix].set_level(0, value)
                number = self.layers[self.current_layer].encoder_number(prefix)
                if number != -1:
                    self.midi_controller.set_ring(number, value)
            elif addr.endswith('/on'):      # channel enable
                if self.debug:
                    print('  %s unMute %d' % (addr, value))
                self.channels[prefix].set_mute(0, value)
                number = self.layers[self.current_layer].button_number(prefix)
                if number != -1:
                    self.midi_controller.set_channel_mute(number, value)
            elif addr.endswith('/level'):
                if self.debug:
                    print('  %s level %f' % (addr, value))
                bus = int(addr[-8:-6])
                self.channels[prefix].set_level(bus, value)
                number = self.layers[self.current_layer].encoder_number(prefix)
                if number != -1:
                    self.midi_controller.set_ring(number, value)
            elif addr.endswith('/gain'):
                if self.debug:
                    print('  %s Gain level %f' % (addr, value))
                self.channels[prefix].set_level("gain", value)
                number = self.layers[self.current_layer].encoder_number(prefix)
                if number != -1:
                    self.midi_controller.set_ring(number, value)
            elif addr.startswith('/fx') and (addr.endswith('/par/01') or addr.endswith('/par/02')):
                if self.fx_slots[int(addr[4:5]) - 1] in self._DELAY_FX_IDS:
                    self.tempo_detector.current_tempo = value * 3
            elif addr.startswith('/fx/') and addr.endswith('/type'):
                self.fx_slots[int(addr[4:5]) - 1] = value
                if value in self._DELAY_FX_IDS:
                    # slot contains a delay, get current time value
                    param_id = '01'
                    if value == 10:
                        param_id = '02'
                    self.xair_client.send(address = '/fx/%s/par/%s' % (addr[4:5], param_id))
            elif self.debug:
                print('processing unknown OSC message with %s and %s value.' % (addr, value))

    def read_initial_state(self):
        """ Refresh state for all faders and mutes."""
        for channel in self.channels.values():
            addr = channel.osc_base_addr
            if addr.startswith('/head'):
                self.xair_client.send(address=addr + '/gain')
                time.sleep(self.xair_client._WAIT_TIME)
            elif addr.startswith('/config'):
                self.xair_client.send(address=addr)
                time.sleep(self.xair_client._WAIT_TIME)
            else:
                self.xair_client.send(address=addr + '/fader')
                time.sleep(self.xair_client._WAIT_TIME)
                self.xair_client.send(address=addr + '/on')
                time.sleep(self.xair_client._WAIT_TIME)
                if channel.sends is not None:
                    for k in range(len(channel.sends)):
                        self.xair_client.send(address=addr + 
                            '/{:0>2d}/level'.format(k + 1))
                        time.sleep(self.xair_client._WAIT_TIME)
        # get all fx types
        for i in range(1, 5):
            self.xair_client.send(address = '/fx/%d/type' % i)
            time.sleep(self.xair_client._WAIT_TIME)
    
    def update_tempo(self, tempo):
        for i in range(0, 4):
            if self.fx_slots[i] in self._DELAY_FX_IDS:
                param_id = '01'
                if self.fx_slots[i] == 10:
                    # only delay where time is set as parameter 02
                    param_id = '02'
                self.xair_client.send(address = '/fx/%d/par/%s' % (i + 1, param_id), param = tempo / 3)

# the meter subscription is setup in the xair_client in the refresh method that runs every 5s
# a subscription sends values every 50ms for 10s
#
# meters 1 provide data per channel and bus
# meters 2, input levels, as these will match the headamps even if mapped to other channels
# layout below assumes meters 2

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
            print('Meters %s ch 8 %s %s %s' % (addr, values[7], short[7], med[7]))
#        if self.screen_obj is not None:
#            self.screen_obj.screen_loop()
