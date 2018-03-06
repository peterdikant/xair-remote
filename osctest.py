import OSC
import threading
import time

# Defaults
#XR18_ADDRESS = "192.168.178.37"
#XR18_PORT = 10024
XR18_ADDRESS = "192.168.77.1"
XR18_PORT = 10023
REFRESH_TIME = 4

# Global variables
client = None
terminate = False

def msg_handler(addr, tags, data, client_address):
    print 'OSCMessage("%s", %s, %s)' % (addr, tags, data)

def refresh_connection():
    global terminate

    try:
        while terminate == False:
            if client != None:
                client.send(OSC.OSCMessage("/renew"))
                print "Sending refresh..."
            time.sleep(REFRESH_TIME)
    except KeyboardInterrupt:
        exit()
    exit()


server = OSC.OSCServer(("", 44424))
server.addMsgHandler("default", msg_handler)
client = OSC.OSCClient(server = server)
client.connect((XR18_ADDRESS, XR18_PORT))

# setup subscriptions
msg = OSC.OSCMessage("/formatsubscribe")
msg.extend(['/chmutes', '/ch/**/mix/on', 1, 16])
client.send(msg)
#client.send(OSC.OSCMessage("/formatsubscribe").extend(['/chmutes', '/ch/**/mix/on', 1, 16]))

threading.Thread(target = refresh_connection).start()


try:
    server.serve_forever()
except KeyboardInterrupt:
    client.send(OSC.OSCMessage("/unsubscribe"))
    terminate = True
    exit()

