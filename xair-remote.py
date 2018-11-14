#!/usr/bin/env python
import argparse
from lib.midicontroller import MidiController, print_ports
from lib.xair import XAirClient, find_mixer
from lib.mixerstate import MixerState

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Remote controll X-Air mixers with a midi controller')
    parser.add_argument('midi_port', help = 'port name of your midi controller (quote if name hase whitespaces)', 
                        nargs = '?')
    parser.add_argument('xair_address', help = 'ip address of your X-Air mixer (optional)', nargs = '?')
    parser.add_argument('-l', '--list', help = 'list connected midi ports', action = 'store_true')
    args = parser.parse_args()
    
    if args.list:
        print_ports()
        exit()
    elif args.midi_port is None:
        print 'Error: You need to specify a midi_port'
        exit()

    if args.xair_address is None:
        address = find_mixer()
        if address is None:
            print 'Error: Could not find any mixers in network. Please specify ip address manually.'
        else:
            args.xair_address = address
        
    state = MixerState()
    midi = MidiController(args.midi_port, state)
    state.midi_controller = midi
    xair = XAirClient(args.xair_address, state)
    state.xair_client = xair
    xair.validate_connection()
    
    state.read_initial_state()
    
    # now refresh /xremote command while running
    xair.refresh_connection()