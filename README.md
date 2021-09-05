# xair-remote

Use a Behringer X-Touch Mini MIDI controller to remote control a Behringer X-Air
digital mixer via the OSC network protocol. Multiple layers allow you to control
volume, mute and bus sends for every input and output channel with only 8
physical encoders. Changes on the mixer will also be displayed accurately on the
X-Touch controller.

## Installing

You need Python 3.5 or later. Please make sure to install required libraries:

    $ python3 -m pip install -r requirements.txt

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

The general operation is fully defined in a config file in JSON format. Three
examples config files are provided and described below. The default is to use peterdikant.jason as it matches the operation of the original project.

### Config File Format

The config file uses JSON for easy parsing and reasonably easy editing. The file
is structured as a sequence of dictionaries each representing a "layer" that
defines all buttons, encoders, and the fader of the X-Touch Mini. Each layer
contains three dictionaries named 'encoders', 'buttons', and 'fader' that define
the respective elements of the X-Touch. Each control specifies the "channel"
that control effects and the command sent to the channel. The "channel" is
technically defined as an OSC address supported by the X-Air protocol that takes
an argument. The most common case in the X-Air command set is an address that is
a common prefix of a set of addresses defining how an audio source is to be
processed. Many aspects of the X-Air follow this pattern even though they are
aspects of the mixer that would not be considered a channel in an analog mixer.
In a large number of cases the channel not only has a level in the main mix but
also a level on each of the auxiliary bus or effects processor the source can
'send' to.

The **encoders** dictionary is a list of 8 lists each specifying the operation of
one encoder from `E1` to `E8`. These lists contain two elements:

* channel, one of:
  * an X-AIR OSC address
  * 'none' - if turning the encoder is to have no effect
* a list defining the function of pressing the encoder as a button supporting
  three commands:
  * 'none' - if pressing the encoder has no effect
  * 'mute' followed by a 'channel' and 'send' to mute
  * 'reset' followed by a 'value' to set the encoder channel to
  * 'subprocess' - as the first element of a list defining a set of external
    commands to cycle through formatted as ['subprocess', 'external call',
    ['command', 'command', ...]]

The **buttons** dictionary is a list of 18 lists each specifying the operation of
one button from `B01` to `B16` followed by `LA` and `LB`. These lists contain a
variable number of elements based on the command:

* 'none' followed by a 'comment' which defines if the button LED is to be on or off
* 'mute' which is followed by the 'channel' to mute, the light matches the mute state
* 'send' followed by number of the send with 0 defined as the main mix for this layer
* 'quit' followed by a 'comment' which defines if the button LED is on or off
* 'layer' followed by the destination 'layer' the max 'send level' and the LED status
* 'clip' followed by the LED state
* 'tap' followed by the LED state

The **fader** dictionary is a list of one list specifying the operation of the
fader. The list is formatted the same as an encoder without the press function
or 'quit' if setting the fader to 100% quits.

## Example Configuraitons

### peterdikant.json

This file configures the X-Touch to operate as defined by Peter Dikant to
support live sound mixing. The description is his original definition of the
xair-remote and thus does not match the organization of the config file.

### Layer A

Layer A is used to control the main mix.

This layer is active when the button `LA` is selected. The main volume is always mapped to the Fader `F1`. The lower button row is assigned globally with the following functions:

Button | Function
------ | ------------------------------------------------
B09    | Mute Group 4 (this is always my FX mute group)
B10    | Tap Tempo (will set tempo for all delay effects)
B11    | Unassigned
B12    | Fader Bank 1
B13    | Fader Bank 2
B14    | Fader Bank 3
B15    | Fader Bank 4
B16    | Fader Bank 5 

The upper row buttons and the top encoders are used to control volume and mute for different channels depending on the selected fader bank:

Bank | Encoders (Volume) & Buttons (Mute)
---- | ----------------------------------
1    | Channels 1 - 8
2    | Channels 9 - 16
3    | Aux, 3 unassigned, DCA 1 - 4
4    | FX Sends 1 - 4, FX Returns 1 - 4
5    | Bus 1 - 6, 2 unassigned

The Push function of encoders `E1` to `E4` can be used to toggle mute groups 1 to 4 in all fader banks. I always use mute group 4 for FX mute, therefore I have placed this mute group on button `B09`. This way I also get visual feedback on the status of my FX returns.

### Layer B

Layer B can control your bus sends.

This layer is active when the button `LB` is selected. The main volume is always mapped to the Fader `F1`.

In this layer all buttons have a static assignment:

Button | Function
------ | ------------------------------------------------
B01    | Bus 1
B02    | Bus 2
B03    | Bus 3
B04    | Bus 4
B05    | Bus 5
B06    | Bus 6
B07    | FX 1
B08    | FX 2
B09    | Mute Group 4 (this is always my FX mute group)
B10    | Tap Tempo (will set tempo for all delay effects)
B11    | Unassigned
B12    | Fader Bank 1
B13    | Fader Bank 2
B14    | Fader Bank 3
B15    | FX 3
B16    | FX 4

The top encoders control the volume for different channels depending on the selected fader bank and bus/FX:

Layer | Encoders (Volume)
----- | ----------------------------------
1     | Channels 1 - 8
2     | Channels 9 - 16
3     | Aux, 7 unassigned

The Push function of encoders `E1` to `E4` can be used to toggle mute groups 1 to 4 in all fader banks.
### rossdickson.json

This file configures the X-Touch to operate as defined by Ross Dickson to
support live sound mixing. The basic concept of the design is to conceive of the
encoders `E1` through `E8` and top row of buttons `B01` through `B08` as a set
of channel strips where the each encoder adjusts a channel level on turn, resets
the level on press, and the button mutes the channel. The rings around the
encoders and lights of the mute buttons show the values of the selected
channels. The lower row of buttons and the layer buttons control what channels
the channel strips control.

The Fader `F1` is used used as a master quit signal when set to the top.

### Layer A and A'

Pressing `LA` configures the channel strips to control the first 8 channels and
is indicated by a lighted button. The reset value is the equivalent of the 0db
level on a fader. Pressing `LA` again switches to the second 8 channels and is
indicated by a blinking button. Further presses toggle between the two.

Buttons, `B09` through `B15`, the first 7 buttons of the lower row define which
'send' bus is being controlled by the channel strips. When no lights are lit the
encoders control the main LR mix bus. Pressing a send button switches to the
corresponding aux bus and the first FX processor. Pressing the same send agains
reverts to the main LR Mix.

### Layer B

Pressing `LB` configures the channel strips to control the output levels on the
6 AUX ports, the level of the USB return, and the main LR output level. The
reset level is -20db for outputs and 0db for the USB return. -20db is used as it
is about 6db lower than max level for something assuming consumer audio line
level rather than pro audio line levels and thus is generally safe no matter
what sort of amp or speakers you might be driving.

Buttons, `B09` through `B15`, are unused as there are no "sends" for outputs.

### Layer `Gain` and `Gain'`

Pressing `B16` configured the channel strips to control the gain levels of the
mic preamps on the first 8 channels and is indicated by a lighted button.
Similar to `LA` pressing `E16` again toggles to the second 8 mic preamps. As
preamps have neither mute nor sends most of the buttons are unused though a few
are used to control additional functions, `B03` and `B04` blink and are used to
quit while `B07` also blinks and is used to enable the clipping protection
function. When enabled, any channel that has more than 3 sequential samples
within 3db of max it will lower the gain of the mic preamp by on step out of a
16 bit range.

Somewhat graphically this configures the X-Touch as:



1/9  | 2/10 | ... | 5/14 | 7/15 | 8/16 | |
---  | ---- | --- | ---- | ---- | ---- | --- |
Mute | Mute | ... | Mute | Mute | Mute | Mix Channels |
AUX 1| AUX 2| ... | AUX 6| Fx 1 | Pre  | Outputs |

### simple.json

This file configures the X-Touch to operate as a simple set of levels and mutes
for the X-Air to support a "dumb mixer" install. The basic concept of the design
is to conceive of the encoders `E1` through `E8` as levels and the buttons `B01`
through `B16` as a mutes for the 16 channels of the X-Air. The buttons `LA` and
`LB` switch the levels to match the upper or lower row of buttons. The rings
around the encoders show the levels while pressing the encoders returns the level
to 0db to quickly reset the mixer. The main fader `F1` is not used.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
