# mycroft-hue
A Mycroft skill for controlling Phillips Hue lights

## Setup

1. Clone this repo into your third party skills folder
  * `cd ~/.mycroft/third_party_skills && git clone https://github.com/ChristopherRogers1991/mycroft-hue.git`
2. `cd` into the resulting `mycroft-hue` directory
  * `cd ~/.mycroft/third_party_skills/mycroft-hue`
3. If your mycroft instance runs in a virtual environment, activate it
  * `source ~/.virtualenvs/mycroft/bin/activate`
4. Install the required python libraries
  * `pip install -r requirements.txt`
5. Add the block below to your mycoft.ini file (`~/.mycroft/mycroft.ini`)
```
[PhillipsHueSkill]
verbose = False  # True if you want mycroft to acknowledge succesful actions
brightness_step = 50  # Brightness ranges from 0-254
color_temperature_step = 1000  # degrees Kelvin. Ranges from 2000-6500
default_group = 0  # Integer id or string name of group. Group 0 = All lights
ip = ""
username = ""
```
If you know the ip address of your hub, or have a user that you would like to use, you may add either or both
on the relevant lines above. Otherwise, the skill will attempt to find the hub on your network (if you have
multiple, it will take the first one it finds), and will create a user.

On your first run, if you did not supply a username, when you say any phrase that gets routed to this
skill (e.e. "turn off my lights"), you will be asked to push the button on the top of your Phillips Hue hub.
This will create a user on the hub for this application.

## Sample phrases
1. Turn on my lights
2. Set my lights to \<scene name\>, e.g. Set my lights to tropical twilight
3. Turn the lights down
4. Decrease the color temperature of the lights

The list above is non-exhaustive, but covers the bulk of the functionality. The phrasing is very flexible; as
long as you hit a few key words (e.g. "lights" and "off") mycroft should be able to figure out what you want.
You can add in a group name to any of the phrases as well, e.g. 'Shut the kitchen lights off'.

All groups and scenes are loaded from the hub, meaning any scenes or groups available to you in the hue app will
be available through mycroft. If you do not specify a group name in your phrase, the default group (specified
in the ini block above) will be used for the given action. These are loaded when mycroft lauches; if you want
to pick up changes to your groups or scenes without relauching mycroft, you can say "reconnect my lights."
