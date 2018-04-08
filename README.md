# xair-remote

Use a Behringer X-Touch Mini MIDI controller to remote control a Behringer X-Air digital mixer via the OSC network protocol. Multiple layers allow you to control volume and mute for every input and output channel with only 8 physical encoders. Changes on the mixer will also be displayed accurately on the X-Touch controller.

## Installing

Make sure that you are running Python 2.7. Now install the module dependencies via:

	$ sudo pip install -r requirements.txt

## Running

To get help run:

	$ python xair-remote.py -h

Connect your X-Touch Mini controller and identify the name of the MIDI port this controller uses:

	$ python xair-remote.py -l

On MacOS, the output might look like this:

	Connected MIDI Ports:
	    X-TOUCH MINI
	    X18/XR18

You need to start the app with the port name of your X-Touch Mini and the ip address of your X-Air mixer. If the port name contains whitespace characters (like it does in this example) you need to enclose it in double quotes.

Run the app:

	$ python xair-remote.py "X-TOUCH MINI" 192.168.178.37

If the app can not find your controller or connect to the X-Air mixer, it will terminate with an error message explaining the problem. If everything started up successfully, the X-Touch mini will reflect the current mixer state and the console output will look like this:

	Successfully setup MIDI port X-TOUCH MINI.
	Successfully connected to XR18 with firmware 1.16 at 192.168.178.37.

## Using

The following image is a schematic of all available controls on the X-Touch Mini:

![X-Touch Mini controls](img/xtm-layout.png)

You need to configure the device to have **toggle** buttons. Apart from that you can use the encoder mode you prefer (my favorite is **fan**). Make sure you don't change the default controller and note numbers. My current X-Touch Mini configuration is attached in the file [xtouch-config.bin](xtouch-config.bin).

Currently only layer A is used. So make sure you have the button `LA` selected. The main volume is always mapped to the Fader `F1`. The buttons `B12` to `B16` are used to switch the different layers. Buttons `B10` to `B11` are currently unassigned.

The other buttons and the encoders are used to control different channels depending on the selected layer:

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

- [ ] Tap Tempo button on `B10` with automatic detection of FX slot for delay plugin
- [ ] Think about possible ways to use layer B. Maybe edit channel details for the first 16 channels. For example: Gain, Low Cut, Gate Threshold, Compressor Threshold, 4x EQ Gain (low priority)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details