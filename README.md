# xair-remote

With thanks peterdikant who created the [xair-remote
project](https://github.com/peterdikant/xair-remote). This version is a seperate
fork as there is not obvious way to meet both my need and Peter's at the same time.

Use a Behringer X-Touch Mini MIDI controller to remote control a Behringer X-Air
digital mixer via the OSC network protocol. Multiple layers allow you to control
volume, mute and bus sends for every input and output channel with only 8
physical encoders. Changes on the mixer will also be displayed accurately on the
X-Touch controller.

## Installing

You need Python 3.5 or later. Please make sure to install required libraries:

	$ sudo pip3 install -r requirements.txt

## Update

If you update from a previous version, please make sure that you run at least
Python 3.5 and install all required libraries as described in the previous
section.

The X-Touch device needs to be running in MC mode. Make sure that the MC LED is
lit after connecting the device by pressing the MC button during startup.

## Running

To get help run:

	$ python3 xair-remote.py -h

The app will automatically detect both your X-Touch controller and the XR18. So
connect the controller and make sure the XR18 is reachable on your network. Now
you can start the app:

	$ python3 xair-remote.py

If the app can not find your controller or connect to the X-Air mixer, it will
terminate with an error message explaining the problem. If everything started up
successfully, the X-Touch mini will reflect the current mixer state and the
console output will look like this:

	Found XR18 with firmware 1.17 on IP 192.168.178.31
	Using MIDI input: X-TOUCH MINI
	Using MIDI output: X-TOUCH MINI
	Successfully connected to XR18 with firmware 1.17 at 192.168.178.31.

Startup will fail if the X-Touch controller is not connected or the XR18 could
not be located on the network. In the latter case you could try to specify the
IP address of the mixer on the command line:

	$ python3 xair-remote.py 192.168.178.37

The app can monitor the X-Touch connection and exit if the controller is
disconnected. This functionality is enabled by setting the parameter `-m`:

	$ python3 xair-remote.py -m
	
Note: Monitoring does not work on all platforms. Linux works fine while MacOS
does not detect disconnects.

## Using

The following image is a schematic of all available controls on the X-Touch Mini:

![X-Touch Mini controls](img/xtm-layout.png)

You need to configure the device to start in MC mode. If the MC mode LED is not
lighted, hold down the MC button while connecting the device.

To exit press `CTRL + C`.

The folder `labels` contains labels to print and attach to your X-Touch as PDF
and Excel files. You can change the labels to your specific setup. Make sure you
print them in 100% size.

### General Operation

The X-Touch is configured as a set of 8 channel strips that can control an 8
channel bank of the mixer. Each channel strip consists of a rotary encoder and
button, `E1` and `B1` through  `E8` and `B8`. The encoder sets the level or gain
of the channel and the ring of lights around the encoder indicate the level.
Pressing the encoder returns the channel to unity gain or a useful default where
one can be found. The button mutes the channel and lights to indicate the
channel is muted. The lower row of buttons, `B09` through `B16` and the two
layer buttons `LA` and `LB` control bank selection. The Fader `F1` is not used.

Pressing a bank select button selects the first layer of the bank and causes the
bank button to light. Pressing the bank button again selects the second layer
and causes the button to blink. Pressing a third time returns to the first
layer. Selecting another bank always selects the first layer even if the
previous bank was on the second layer. The banks are configured as follows:

Button | Bank Function
------ | -------------
`LA`   | Channel Send to Main LR Bus
`LB`   | Bus Output and USB AUX In Levels
`B09`  | Channel Send to AUX 1
`B10`  | Channel Send to AUX 2
`B11`  | Channel Send to AUX 3
`B12`  | Channel Send to AUX 4
`B13`  | Channel Send to AUX 5
`B14`  | Channel Send to AUX 6
`B15`  | Channel Send to Aux 7/Fx 1
`B16`  | Mic Preamps

### Bank A

Bank A is used to control the level of channels in the main mix and has two
layers. In the first layer the encoders and buttons map to channels 1 through 8,
and the second layer they map to channels 9 through 16. Pressing the encoders
returns the channel to unity gain, the top row of buttons (B01 through B08) mute
the channel.

### Bank B

Bank B is used to control the output levels and USB AUX in level, it has one
layer. The encoders and mute buttons are as per the table:

Channel | Encoders (Volume) & Buttons (Mute) | Encoder Push Value
------- | ---------------------------------- | ------------------
1-6     | Aux 1-6 Output Levels              | Return to -20 db
7       | USB/Aux Input Gain 				 | Return to 0 db
8       | Main L/R Output Level 			 | Return to -20 db

The Push function of encoders return to -20 db as most of the monitor and PA
speakers I use get over distort at 0db output.

### Banks 1 through 6

Banks 1 though 6 control the AUX Bus sends for each channel and have two layers.
Similar to Bank A layer 1 maps to channels 1 through 8 and layer 2 maps channels
9 through 16. As the X-Air does not have a mute function on sends, the mute is
implemented by setting the send value to -∞ while storing the current send
value. If you restart the application while a send is muted the stored send
level will be lost. Pressing the encoders returns the send to unity gain. These
banks have no effect for channels set to "Sub Group" send mode.

### Bank 7

Bank 7 works the same as Banks 1 through 6 though it sends the channels to AUX
Bus 7 which is also known as FX 1.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
