import mido
import sys
import time

from mido import Message

def print_ports(heading, port_names):
    print(heading)
    for name in port_names:
        print("    '{}'".format(name))
    print()

#print_ports('Input Ports:', mido.get_input_names())
#print_ports('Output Ports:', mido.get_output_names())

#with mido.open_output('nanoKONTROL MIDI 1') as port:
#	print('Using {}'.format(port))
#	for i in range(0, 10):
#		port.send(Message('control_change', channel = 0, control = 41, value = 127))
#		time.sleep(0.1)
#		port.send(Message('control_change', channel = 0, control = 41, value = 0))
#		time.sleep(0.4)

try:
    with mido.open_input('nanoKONTROL MIDI 1') as port:
        print('Using {}'.format(port))
        print('Waiting for message...')
        for message in port:
            if message.type == 'control_change' and message.control == 2:
                print('Sending: {}'.format(message.value / 127.0))
                #osc_client.send_message('/ch01/mix/fader', 0.5)
            else:
                print('Received {}'.format(message))
        sys.stdout.flush()
except KeyboardInterrupt:
    pass

