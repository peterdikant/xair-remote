import time
import threading
import socket
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_message import OscMessage
from .mixerstate import MixerState

class XAirClient:
    """
    Handles the communication with the X-Air mixer via the OSC protocol
    """
    _CONNECT_TIMEOUT = 0.5
    _WAIT_TIME = 0.02
    _REFRESH_TIMEOUT = 5

    XAIR_PORT = 10024

    info_response = []
    
    def __init__(self, address, state):
        self.state = state
        # First create a client and bind it to a network port
        self.client = SimpleUDPClient(address, self.XAIR_PORT)
        self.client._sock.bind(('', 0))
        client_address, client_port = self.client._sock.getsockname()
        # Now use that port for a server to receive responses from mixer
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self.msg_handler)
        self.server = BlockingOSCUDPServer(("0.0.0.0", client_port), dispatcher)
        worker = threading.Thread(target = self.run_server)
        worker.daemon = True
        worker.start()
    
    def validate_connection(self):
        self.send('/xinfo')
        time.sleep(self._CONNECT_TIMEOUT)
        if len(self.info_response) > 0:
            print('Successfully connected to %s with firmware %s at %s.' % (self.info_response[2], 
                    self.info_response[3], self.info_response[0]))
        else:
            print('Error: Failed to setup OSC connection to mixer. Please check for correct ip address.')
            exit()
        
    def run_server(self):
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            exit()
        
    def msg_handler(self, addr: str, *data: List[Any]) -> None:
            #print 'OSCReceived("%s", %s, %s)' % (addr, tags, data)
            if addr.endswith('/fader') or addr.endswith('/on') or addr.startswith('/config/mute') or addr.startswith('/fx/'):
                self.state.received_osc(addr, data[0])
            elif addr == '/xinfo':
                self.info_response = data[:]
    
    def refresh_connection(self):
        # Tells mixer to send changes in state that have not been recieved from this OSC Client
        #   /xremote        - all parameter changes are broadcast to all active clients (Max 4)
        #   /xremotefnb     - No Feed Back. Parameter changes are only sent to the active clients which didn't initiate the change
        try:
            while True:
                if self.client != None:
                    self.client.send_message("/xremotenfb")
                time.sleep(self._REFRESH_TIMEOUT)
        except KeyboardInterrupt:
            exit()
            
    def send(self, address, param = None):
        if self.client != None:
            self.client.send_message(address, param)
            
def find_mixer():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    client.sendto("/xinfo\0\0", ("<broadcast>", XAirClient.XAIR_PORT))
    try:
        response = OscMessage(client.recv(512))
    except socket.timeout:
        print('No server found')
        return None
    client.close()

    if response[0] != '/xinfo':
        print('Unknown response')
        return None
    else:
        print('Found ' + response[4] + ' with firmware ' + response[5] + ' on IP ' + response[2])
        return response[2]
