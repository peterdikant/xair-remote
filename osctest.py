#!/usr/bin/env python

import OSC
import threading
import time

# Defaults
#XR18_ADDRESS = "192.168.178.37"
#XR18_PORT = 10024
XR18_ADDRESS = "127.0.0.1"
XR18_PORT = 10023
REFRESH_TIME = 10

# Global variables
client = None
terminate = False

def msg_handler(addr, tags, data, client_address):
    print 'OSCReceived("%s", %s, %s)' % (addr, tags, data)

def refresh_connection():
    global terminate

    try:
        while terminate == False:
            if client != None:
                sendOsc("/xremote")
            time.sleep(REFRESH_TIME)
    except KeyboardInterrupt:
        exit()
    exit()
    
def sendOsc(address, param = None):
    if client != None:
        msg = OSC.OSCMessage(address)
        if param != None:
            if isinstance(param, list):
                msg.extend(param)
            else:
                msg.append(param)
        client.send(msg)
        print 'OSCSend(%s)' % (msg)
        
def setupSubscriptions():
    sendOsc("/unsubscribe")
    for i in range(1, 17):
        sendOsc("/subscribe", ["/ch/%02d/mix/fader" % i, 100])
    for i in range(1, 5):
        sendOsc("/subscribe", ["/rtn/%d/mix/fader" % i, 100])
        sendOsc("/subscribe", ["/fxsend/%d/mix/fader" % i, 100])
    for i in range(1, 7):
        sendOsc("/subscribe", ["/bus/%d/mix/fader" % i, 100])
    sendOsc("/subscribe", ["/rtn/aux/mix/fader", 100])
    sendOsc("/subscribe", ["/lr/mix/fader", 100])
            

server = OSC.OSCServer(("", 44424))
server.addMsgHandler("default", msg_handler)
client = OSC.OSCClient(server = server)
client.connect((XR18_ADDRESS, XR18_PORT))

# setup subscriptions
#setupSubscriptions()

threading.Thread(target = refresh_connection).start()


try:
    server.serve_forever()
except KeyboardInterrupt:
    sendOsc("/unsubscribe")
    terminate = True
    exit()

