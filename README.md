## Mycroft Hue
Control Phillips Hue Lights

## Description 
Turn your Phillips Hue lights on/off, activate scenes, adjust brightness/color temperature, etc.

## Examples 
* "Turn on my lights"
* "Set my lights to tropical twilight"
* "Turn the lights down"
* "Decrease the color temperature of the lights"

## Credits 
* @ChristopherRogers1991
* @WillJMurphy
* @gras64
* @VilterPD


## Short Demo
https://youtu.be/IQ58dPp8f3M

## Instalation

### MSM

You can install this skill by running: `msm install hue`.

### Manual install

1. Clone this repo into your third party skills folder (the current default is ~/.mycroft/skills, but it used to be ~/.mycroft/third_party_skills; check your global/local mycroft.conf files if you have issues)
  * `cd ~/.mycroft/skills && git clone https://github.com/ChristopherRogers1991/mycroft-hue.git`
2. `cd` into the resulting `mycroft-hue` directory
  * `cd ~/.mycroft/skills/mycroft-hue`
3. If your mycroft instance runs in a virtual environment, activate it
  * `source ~/.virtualenvs/mycroft/bin/activate`
4. Install the required python libraries
  * `pip install -r requirements.txt`

## Configuration

*Note:* You may need to restart Mycroft (or at least the skills service), for configuration changes to take effect.

If you need to adjust any settings of this skill, you can do so at https://home.mycroft.ai/#/skill. Alternatively:

Add the block below to your mycoft.conf file (`~/.mycroft/mycroft.conf`), and make any necessary adjustments there.
```
  "PhillipsHueSkill": {
    "ip": "",
    "username": "",
    "verbose": false,
    "brightness_step": 50,
    "color_temperature_step": 1000,
    "default_group": 0
  }
```

If that file did not already exist (this is the first third party skill you have added), wrap that entire block in { }. The finished file should be valid json. If you have issues, use http://jsonlint.com/ to validate the json.

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
