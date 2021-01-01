#!/usr/bin/env python3
import argparse
import threading
from lib.midicontroller import MidiController
from lib.xair import XAirClient, find_mixer
from lib.mixerstate import MixerState

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Remote control X-Air mixers with a midi controller')
    parser.add_argument('xair_address', help = 'ip address of your X-Air mixer (optional)', nargs = '?')
    parser.add_argument('-m', '--monitor', help='monitor X-Touch connection and exit when disconnected', action="store_true")
    args = parser.parse_args()

    if args.xair_address is None:
        address = find_mixer()
        if address is None:
            print('Error: Could not find any mixers in network. Please specify ip address manually.')
            exit()
        else:
            args.xair_address = address

    state = MixerState()
    midi = MidiController(state)
    state.midi_controller = midi
    xair = XAirClient(args.xair_address, state)
    state.xair_client = xair
    xair.validate_connection()

    if args.monitor:
        print('Monitoring X-Touch connection enabled')
        monitor = threading.Thread(target = midi.monitor_ports)
        monitor.daemon = True
        monitor.start()
    
    state.read_initial_state()
    
    # now refresh /xremote command while running
    xair.refresh_connection()
