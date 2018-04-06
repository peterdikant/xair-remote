import time
import thread
from OSC import OSCServer, OSCClient, OSCMessage
from mixerstate import MixerState

class XAirClient:
    
    refresh_timeout = 5
    last_cmd_addr = ''
    last_cmd_time = 0
    wait_time = 0.02
    
    def __init__(self, address, state):
        self.state = state
        self.state.osc_sender = self.update_callback
        self.server = OSCServer(("", 0))
        self.server.addMsgHandler("default", self.msg_handler)
        self.client = OSCClient(server = self.server)
        self.client.connect((address, 10024))
        thread.start_new_thread(self.refresh_connection, ())
        
    def run_server(self):
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            exit()
        
    def msg_handler(self, addr, tags, data, client_address):
        if time.time() - self.last_cmd_time < self.wait_time and addr == self.last_cmd_addr:
            #print 'Ignoring %s' % addr
            self.last_cmd_addr = ''
        else:
            #print 'OSCReceived("%s", %s, %s)' % (addr, tags, data)
            if addr.endswith('/fader') or addr.endswith('/on'):
                self.state.received_osc(addr, data[0])
    
    def refresh_connection(self):
        try:
            while True:
                if self.client != None:
                    self.send("/xremote")
                time.sleep(self.refresh_timeout)
        except KeyboardInterrupt:
            exit()
            
    def send(self, address, param = None):
        if self.client != None:
            msg = OSCMessage(address)
            if param != None:
                # when sending values, ignore ACK response
                self.last_cmd_time = time.time()
                self.last_cmd_addr = address
                if isinstance(param, list):
                    msg.extend(param)
                else:
                    msg.append(param)
            else:
                # sending parameter request, don't ignore response
                self.last_cmd_time = 0
                self.last_cmd_addr = ''
            self.client.send(msg)
            #print 'sending: %s' % (msg)
            
    def update_callback(self, base_addr, fader = None, on = None):
        if fader != None:
            self.send(base_addr + '/fader', fader)
        if on != None:
            self.send(base_addr + '/on', on)