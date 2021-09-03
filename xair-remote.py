"Starts an xAir remote, see main help string for more"
#!/usr/bin/env python3
import argparse
from lib.mixerstate import MixerState

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(description="""
    Remote control X-Air mixers with an X-Touch midi controller.

    The X-Touch is setup so that the encoders are configured as faders on any of
    10 banks with the first row of button configured as mutes for the selected
    bank. Banks are selected with the buttons in the lower row and the layer
    buttons. Most banks have two layers, the second access by pressing the
    button a second time, causing the button to blink. The fader is used as a
    master exit control. Pressing an encoder returns the level to unity gain,
    not used for mic pre.
    """,
                                     epilog="""
    Bank 1-6 - Aux Bus 1-6 levels for Channels 1-8 and 9-16.
    Bank 7 - Aux Bus 7 aka FX 1 for Channels 1-8 and 9-16.
    Bank 8 - Mic PreAmp levels for Channels 1-8 and 9-16.
    Layer A - Main LR Mix levels of Channels 1-8 and 9-16 on second layer.
    Layer B - Aux Bus 1-6 output levels, USB IN Gain, Main/LR Bus output level.
    """,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    PARSER.add_argument('xair_address', help='ip address of your X-Air mixer (optional)', nargs='?')
    PARSER.add_argument('-m', '--monitor',
                        help='monitor X-Touch connection and exit when disconnected',
                        action="store_true")
    PARSER.add_argument('-d', '--debug', help='enable debug output', action="store_true")
    PARSER.add_argument('-l', '--levels', help='get levels from the mixer', action="store_true")
    PARSER.add_argument('-c', '--clip', help='enabling auto leveling to avoid clipping',
                        action="store_true")
    PARSER.add_argument('-f', '--config_file', help="JSON formated config file", nargs=1)
    ARGS = PARSER.parse_args()

    STATE = MixerState(ARGS)
    if STATE.initialize_state():
        # now start polling refresh /xremote command while running
        STATE.xair_client.refresh_connection()
