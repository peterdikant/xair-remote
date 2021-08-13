"Starts an xAir remote, see main help string for more"
#!/usr/bin/env python3
import argparse
from lib.mixerstate import MixerState

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(description="""
    Remote control X-Air mixers with an X-Touch midi controller.
    """)
    PARSER.add_argument('xair_address', help='ip address of your X-Air mixer (optional)', nargs='?')
    PARSER.add_argument('-m', '--monitor',
                        help='monitor X-Touch connection and exit when disconnected',
                        action="store_true")
    PARSER.add_argument('-d', '--debug', help='enable debug output', action="store_true")
    ARGS = PARSER.parse_args()

    STATE = MixerState(ARGS)
    if STATE.initialize_state():
        # now start polling refresh /xremote command while running
        STATE.xair_client.refresh_connection()
