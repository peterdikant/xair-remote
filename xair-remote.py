#!/usr/bin/env python3
import argparse
from lib.midicontroller import MidiController
from lib.xair import XAirClient, find_mixer
from lib.mixerstate import MixerState

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Remote controll X-Air mixers with a midi controller')
    parser.add_argument('xair_address', help = 'ip address of your X-Air mixer (optional)', nargs = '?')
    args = parser.parse_args()

    if args.xair_address is None:
        address = find_mixer()
        if address is None:
            print('Error: Could not find any mixers in network. Please specify ip address manually.')
        else:
            args.xair_address = address
        
    state = MixerState()
    midi = MidiController(state)
    state.midi_controller = midi
    xair = XAirClient(args.xair_address, state)
    state.xair_client = xair
    xair.validate_connection()
    
    state.read_initial_state()
    
    # now refresh /xremote command while running
    xair.refresh_connection()
