import mido
from midisurface import MidiSurface

def print_ports(heading, port_names):
    print(heading)
    for name in port_names:
        print("    '{}'".format(name))

print_ports('Input Ports:', mido.get_input_names())
print_ports('Output Ports:', mido.get_output_names())

if __name__ == '__main__':
    midi = MidiSurface('X-TOUCH MINI')