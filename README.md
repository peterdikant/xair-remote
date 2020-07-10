# xair-remote

Use a Behringer X-Touch Mini MIDI controller to remote control a Behringer X-Air digital mixer via the OSC network protocol. Multiple layers allow you to control volume and mute for every input and output channel with only 8 physical encoders. Changes on the mixer will also be displayed accurately on the X-Touch controller.

## Installing

You need Python 3.5 or later. Please make sure to install required libraries:

	$ sudo pip3 install -r requirements.txt

## Update

If you update from a previous version, please make sure that you run at least Python 3.5 and install all required libraries as described in the previous section.

## Running

To get help run:

	$ python3 xair-remote.py -h

The app will automatically detect both your X-Touch controller and the XR18. So connect the controller and make sure the XR18 is reachable on your network. Now you can start the app:

	$ python3 xair-remote.py

If the app can not find your controller or connect to the X-Air mixer, it will terminate with an error message explaining the problem. If everything started up successfully, the X-Touch mini will reflect the current mixer state and the console output will look like this:

	Found XR18 with firmware 1.17 on IP 192.168.178.31
	Using MIDI input: X-TOUCH MINI
	Using MIDI output: X-TOUCH MINI
	Successfully connected to XR18 with firmware 1.17 at 192.168.178.31.

Startup will fail if the X-Touch controller is not connected or the XR18 could not be located on the network. In the latter case you could try to specify the IP address of the mixer on the command line:

	$ python3 xair-remote.py 192.168.178.37


## Using

The following image is a schematic of all available controls on the X-Touch Mini:

![X-Touch Mini controls](img/xtm-layout.png)

You need to configure the device to have **toggle** buttons. Apart from that you can use the encoder mode you prefer (my favorite is **fan**). Make sure you don't change the default controller and note numbers. My current X-Touch Mini configuration is attached in the file [xtouch-config.bin](xtouch-config.bin).

Currently only layer A is used. So make sure you have the button `LA` selected. The main volume is always mapped to the Fader `F1`. The lower button row is assigned globally with the following functions:

Button | Function
------ | ------------------------------------------------
B09    | Mute Group 4 (this is always my FX mute group)
B10    | Tap Tempo (will set tempo for all delay effects)
B11    | Unassigned
B12    | Layer 1
B13    | Layer 2
B14    | Layer 3
B15    | Layer 4
B16    | Layer 5 

The upper row buttons and the top encoders are used to control volume and mute for different channels depending on the selected layer:

Layer | Encoders (Volume) & Buttons (Mute)
----- | ----------------------------------
1     | Channels 1 - 8
2     | Channels 9 - 16
3     | Aux, 3 unassigned, DCA 1 - 4
4     | FX Sends 1 - 4, FX Returns 1 - 4
5     | Bus 1 - 6, 2 unassigned

The Push function of encoders `E1` to `E3` can be used to toggle mute groups 1 to 3 in all layers. I always use mute group 4 for FX mute, therefore I have placed this mute group on button `B09`. This way I also get a visual feedback on the status of my FX returns.

To exit press `CTRL + C`.

## TODOs

Following features are currently on my todo list:

- [x] Tap Tempo button on `B10` with automatic detection of FX slot for delay plugin
- [x] Automatically find mixer on the network
- [ ] Think about possible ways to use layer B. Maybe edit channel details for the first 16 channels. For example: Gain, Low Cut, Gate Threshold, Compressor Threshold, 4x EQ Gain (low priority)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
