"This modules managed communications with the XAir mixer"
import time
import threading
import socket
import netifaces
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

class OSCClientServer(BlockingOSCUDPServer):
    "The OSC communications agent"
    def __init__(self, address, dispatcher):
        super().__init__(('', 0), dispatcher)
        self.xr_address = address

    def send_message(self, address, value):
        "Packs a message for sending via OSC over UDB."
        builder = OscMessageBuilder(address=address)
        if value is None:
            values = []
        elif isinstance(value, list):
            values = value
        else:
            values = [value]
        for val in values:
            builder.add_arg(val)
        msg = builder.build()
        self.socket.sendto(msg.dgram, self.xr_address)

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
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self.msg_handler)
        self.server = OSCClientServer((address, self.XAIR_PORT), dispatcher)
        worker = threading.Thread(target=self.run_server)
        worker.daemon = True
        worker.start()

    def validate_connection(self):
        "Confirm that the connection to the XAir is live, otherwise initiaties shutdown."
        self.send('/xinfo')
        time.sleep(self._CONNECT_TIMEOUT)
        if len(self.info_response) > 0:
            print('Successfully connected to %s with firmware %s at %s.' % (self.info_response[2],
                    self.info_response[3], self.info_response[0]))
        else:
            print('Error: Failed to setup OSC connection to mixer.',
                  'Please check for correct ip address.')
            self.state.quit_called = True
            if self.server is not None:
                self.server.shutdown()
                self.server = None

    def run_server(self):
        "Start the OSC communications agent in a seperate thread."
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.quit()

    def stop_server(self):
        if self.server is not None:
            self.server.shutdown()
            self.server = None

    def quit(self):
        if self.state is not None:
            self.state.shutdown()
        else:
            self.stop_server()

    def msg_handler(self, addr, *data):
        "Dispatch received OSC messages based on message type."
        if self.state is None or self.state.quit_called:
            self.stop_server()
            return
        #print 'OSCReceived("%s", %s, %s)' % (addr, tags, data)
        if addr.endswith('/fader') or addr.endswith('/on') or addr.endswith('/level') or \
                addr.startswith('/config/mute') or addr.endswith('/gain'):
            self.state.received_osc(addr, data[0])
        elif addr == '/xinfo':
            self.info_response = data[:]
        elif addr.startswith('/meters'):
            self.state.received_meters(addr, data)
        else:         #if self.state.debug and addr.start:
            print('OSCReceived("%s", %s)' % (addr, data))

    def refresh_connection(self): # the main loop
        """
        Tells mixer to send changes in state that have not been received from this OSC Client
          /xremote        - all parameter changes are broadcast to all active clients (Max 4)
          /xremotefnb     - No Feed Back. Parameter changes are only sent to the active clients
                                                                which didn't initiate the change
        """
        if self.state.debug:
            print("Refresh Connection %s" % self.state.levels)
        try:
            while not self.state.quit_called and self.server is not None:
                self.server.send_message("/xremotenfb", None)
                if self.state.levels:
                    # using input levels, as these match the headamps when channels are remapped
                    time.sleep(0.002)
                    self.send(address="/meters", param=["/meters/2"])
                if self.state.clip: # seems to crash if clipping protection runs for too long
                    if self.state.debug:
                        print("start auto level")
                    self.state.clip = False
                    if self.state.screen_obj is not None:
                        self.state.screen_obj.gpio_button[1].disable[0] = 1
                time.sleep(self._REFRESH_TIMEOUT)
                if self.state.quit_called:
                    self.quit()
                    return
        except KeyboardInterrupt:
            self.quit()
        except socket.error:
            self.quit()

    def send(self, address, param=None):
        "Call the OSC agent to send a message"
        self.server.send_message(address, param)

def find_mixer():
    "Search for the IP address of the XAir mixer"
    print('Searching for mixer...')
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    client.settimeout(5)
    for iface in netifaces.interfaces():
        try:
            bcast = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['broadcast']
            client.sendto("/xinfo\0\0".encode(), (bcast, XAirClient.XAIR_PORT))
        except:
            pass
    try:
        response = OscMessage(client.recv(512))
    except socket.timeout:
        print('No server found')
        return None
    client.close()

    if response.address != '/xinfo':
        print('Unknown response')
        return None
    else:
        print('Found ' + response.params[2] + ' with firmware ' + response.params[3] + ' on IP ' + response.params[0])
        return response.params[0]
