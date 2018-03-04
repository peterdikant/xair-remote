import OSC
import threading
import time

# Defaults
XR18_ADDRESS = "192.168.178.37"
XR18_PORT = 10024
REFRESH_TIME = 3

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
				#client.connect((XR18_ADDRESS, XR18_PORT))
				client.send(OSC.OSCMessage("/xremote"))
				print "Sending refresh..."
			time.sleep(REFRESH_TIME)
	except KeyboardInterrupt:
		exit()
	exit()
	
	
server = OSC.OSCServer(("", 44424))
server.addMsgHandler("default", msg_handler)
client = OSC.OSCClient(server = server)
client.connect(("192.168.178.37", 10024))
#lient.send(OSC.OSCMessage("/xinfo"))

threading.Thread(target = refresh_connection).start()


try:
	server.serve_forever()
except KeyboardInterrupt:
	terminate = True
	exit()

