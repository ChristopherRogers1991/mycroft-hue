"""
mycroft-hue : A Mycroft skill for controlling Phillips Hue

Copyright (C) 2016  Christopher Rogers

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger
from os.path import dirname
from phue import Bridge
from phue import Group
from phue import PhueRegistrationException
from phue import PhueRequestTimeout
from time import sleep
from requests import ConnectionError
from requests import get

import os
import json
import socket

__author__ = 'ChristopherRogers1991'

LOGGER = getLogger(__name__)


DEFAULT_BRIGHTNESS_STEP = 50
DEFAULT_COLOR_TEMPERATURE_STEP = 1000


class DeviceNotFoundException(Exception):
    pass


class UnauthorizedUserException(Exception):

    def __init__(self, username):
        msg = "User '{0}' is not registered with the bridge"
        super(UnauthorizedUserException, self).__init__(msg.format(username))


def intent_handler(handler_function):
    """
    Decorate handler functions with connection and
    error handling.

    Parameters
    ----------
    handler_function : callable

    Returns
    -------
    callable

    """
    def handler(self, message):
        if message.type == 'ConnectLightsIntent' \
                or self.connected or self._connect_to_bridge():
            group = self.default_group
            if "Group" in message.data:
                name = message.data["Group"].lower()
                group_id = self.groups_to_ids_map[name]
                group = Group(self.bridge, group_id)
            try:
                handler_function(self, message, group)
            except PhueRequestTimeout:
                self.speak_dialog('unable.to.perform.action')
            except Exception as e:
                if 'No route to host' in e.args:
                    if self.user_supplied_ip:
                        self.speak_dialog('no.route')
                        return
                    else:
                        self.speak_dialog('could.not.communicate')
                        if self._connect_to_bridge(True):
                            self.handle_intent(message)
                else:
                    raise
    return handler


class PhillipsHueSkill(MycroftSkill):

    def __init__(self):
        super(PhillipsHueSkill, self).__init__(name="PhillipsHueSkill")
        self.brightness_step = int(self.settings.get('brightness_step',
                                                     DEFAULT_BRIGHTNESS_STEP))
        self.color_temperature_step = \
            int(self.settings.get('color_temperature_step',
                                  DEFAULT_COLOR_TEMPERATURE_STEP))

        verbose = self.settings.get('verbose', False)
        if type(verbose) == str:
            verbose = verbose.lower()
            verbose = True if verbose == 'true' else False
        self.verbose = verbose

        self.username = self.settings.get('username')
        if self.username == '':
            self.username = None

        self.ip = None  # set in _connect_to_bridge
        self.bridge = None
        self.default_group = None
        self.groups_to_ids_map = dict()
        self.scenes_to_ids_map = dict()
        self.colors_to_cie_color_map = self._map_colors_to_cie_colors()

    @property
    def connected(self):
        return self.bridge is not None

    @property
    def user_supplied_ip(self):
        return self.settings.get('ip') != ''

    @property
    def user_supplied_username(self):
        return self.settings.get('username') != ''

    def _register_with_bridge(self):
        """
        Helper for connecting to the bridge. If we don't
        have a valid username for the bridge (ip) we are trying
        to use, this will cause one to be generated.
        """
        self.speak_dialog('connect.to.bridge')
        i = 0
        while i < 30:
            sleep(1)
            try:
                self.bridge = Bridge(self.ip)
            except PhueRegistrationException:
                continue
            else:
                break
        if not self.connected:
            self.speak_dialog('failed.to.register')
        else:
            self.speak_dialog('successfully.registered')

    def _update_bridge_data(self):
        """
        This should be called any time a successful
        connection is established. It sets some
        member variables, and ensures that scenes and
        groups are registered as vocab.
        """
        self.username = self.bridge.username

        with self.file_system.open('username', 'w') as conf_file:
            conf_file.write(self.username)

        if not self.default_group:
            self._set_default_group(self.settings.get('default_group'))

        self._register_groups_and_scenes()
        self._register_colors()

    def _attempt_connection(self):
        """
        This will attempt to connect to the bridge,
        but will not handle any errors on it's own.

        Raises
        ------
        UnauthorizedUserException
            If self.username is not None, and is not registered with the bridge
        """
        if self.user_supplied_ip:
            self.ip = self.settings.get('ip')
        else:
            self.ip = _discover_bridge()
        if self.username:
            url = 'http://{ip}/api/{user}'.format(ip=self.ip,
                                                  user=self.username)
            data = get(url).json()
            data = data[0] if isinstance(data, list) else data
            error = data.get('error')
            if error:
                description = error.get('description')
                if description == "unauthorized user":
                    raise UnauthorizedUserException(self.username)
                else:
                    raise Exception('Unknown Error: {0}'.format(description))

        self.bridge = Bridge(self.ip, self.username)

    def _connect_to_bridge(self, acknowledge_successful_connection=False):
        """
        Calls _attempt_connection, handling various exceptions
        by either alerting the user to issues with the config/setup,
        or registering the application with the bridge.

        Parameters
        ----------
        acknowledge_successful_connection : bool
            Speak when a successful connection is established.

        Returns
        -------
        bool
            True if a connection is established.

        """
        try:
            self._attempt_connection()
        except DeviceNotFoundException:
            self.speak_dialog('bridge.not.found')
            return False
        except ConnectionError:
            self.speak_dialog('failed.to.connect')
            if self.user_supplied_ip:
                self.speak_dialog('ip.in.config')
            return False
        except socket.error as e:
            if 'No route to host' in e.args:
                self.speak_dialog('no.route')
            else:
                self.speak_dialog('failed.to.connect')
            return False
        except UnauthorizedUserException:
            if self.user_supplied_username:
                self.speak_dialog('invalid.user')
                return False
            else:
                self._register_with_bridge()
        except PhueRegistrationException:
            self._register_with_bridge()

        if not self.connected:
            return False

        if acknowledge_successful_connection:
            self.speak_dialog('successfully.connected')

        self._update_bridge_data()

        return True

    def _set_default_group(self, identifier):
        """
        Sets the group to which commands will be applied, when
        a group is not specified in the command.

        Parameters
        ----------
        identifier : str or int
            The name of the group, or it's integer id

        Notes
        -----
        If the group does not exist, 0 (all lights) will be
        used.

        """
        try:
            self.default_group = Group(self.bridge, identifier)
        except LookupError:
            self.speak_dialog('could.not.find.group', {'name': identifier})
            self.speak_dialog('using.group.0')
            self.default_group = Group(self.bridge, 0)

    def _register_groups_and_scenes(self):
        """
        Register group and scene names as vocab,
        and update our caches.
        """
        groups = self.bridge.get_group()
        for id, group in groups.items():
            name = group['name'].lower()
            self.groups_to_ids_map[name] = id
            self.register_vocabulary(name, "Group")

        scenes = self.bridge.get_scene()
        for id, scene in scenes.items():
            name = scene['name'].lower()
            self.scenes_to_ids_map[name] = id
            self.register_vocabulary(name, "Scene")

    def initialize(self):
        """
        Attempt to connect to the bridge,
        and build/register intents.
        """
        self.load_data_files(dirname(__file__))

        if self.file_system.exists('username'):
            if not self.user_supplied_username:
                with self.file_system.open('username', 'r') as conf_file:
                    self.username = conf_file.read().strip(' \n')
            try:
                self._attempt_connection()
                self._update_bridge_data()
            except (PhueRegistrationException,
                    DeviceNotFoundException,
                    UnauthorizedUserException,
                    ConnectionError,
                    socket.error):
                # Swallow it for now; _connect_to_bridge will deal with it
                pass

        toggle_intent = IntentBuilder("ToggleIntent") \
            .one_of("OffKeyword", "OnKeyword") \
            .one_of("Group", "LightsKeyword") \
            .build()
        self.register_intent(toggle_intent, self.handle_toggle_intent)

        activate_scene_intent = IntentBuilder("ActivateSceneIntent") \
            .require("Scene") \
            .one_of("Group", "LightsKeyword") \
            .build()
        self.register_intent(activate_scene_intent,
                             self.handle_activate_scene_intent)

        adjust_brightness_intent = IntentBuilder("AdjustBrightnessIntent") \
            .one_of("IncreaseKeyword", "DecreaseKeyword", "DimKeyword") \
            .one_of("Group", "LightsKeyword") \
            .optionally("BrightnessKeyword") \
            .build()
        self.register_intent(adjust_brightness_intent,
                             self.handle_adjust_brightness_intent)

        set_brightness_intent = IntentBuilder("SetBrightnessIntent") \
            .require("Value") \
            .one_of("Group", "LightsKeyword") \
            .optionally("BrightnessKeyword") \
            .build()
        self.register_intent(set_brightness_intent,
                             self.handle_set_brightness_intent)

        adjust_color_temperature_intent = \
            IntentBuilder("AdjustColorTemperatureIntent") \
            .one_of("IncreaseKeyword", "DecreaseKeyword") \
            .one_of("Group", "LightsKeyword") \
            .require("ColorTemperatureKeyword") \
            .build()
        self.register_intent(adjust_color_temperature_intent,
                             self.handle_adjust_color_temperature_intent)

        connect_lights_intent = \
            IntentBuilder("ConnectLightsIntent") \
            .require("ConnectKeyword") \
            .one_of("Group", "LightsKeyword") \
            .build()
        self.register_intent(connect_lights_intent,
                             self.handle_connect_lights_intent)

        #TODO: .require("Color") if registration issues solved
        change_color_intent = \
            IntentBuilder("ChangeLightColorIntent") \
            .require("ColorKeyword") \
            .require("Color") \
            .one_of("Group", "LightsKeyword") \
            .build()
        self.register_intent(change_color_intent,
                             self.handle_change_color_intent)

    @intent_handler
    def handle_toggle_intent(self, message, group):
        if "OffKeyword" in message.data:
            dialog = 'turn.off'
            group.on = False
        else:
            dialog = 'turn.on'
            group.on = True
        if self.verbose:
            self.speak_dialog(dialog)

    @intent_handler
    def handle_activate_scene_intent(self, message, group):
        scene_name = message.data['Scene'].lower()
        scene_id = self.scenes_to_ids_map[scene_name]
        if scene_id:
            if self.verbose:
                self.speak_dialog('activate.scene',
                                  {'scene': scene_name})
            self.bridge.activate_scene(group.group_id, scene_id)
        else:
            self.speak_dialog('scene.not.found',
                              {'scene': scene_name})

    @intent_handler
    def handle_adjust_brightness_intent(self, message, group):
        if "IncreaseKeyword" in message.data:
            brightness = group.brightness + self.brightness_step
            group.brightness = \
                brightness if brightness < 255 else 254
            dialog = 'increase.brightness'
        else:
            brightness = group.brightness - self.brightness_step
            group.brightness = brightness if brightness > 0 else 0
            dialog = 'decrease.brightness'
        if self.verbose:
            self.speak_dialog(dialog)

    @intent_handler
    def handle_set_brightness_intent(self, message, group):
        value = int(message.data['Value'].rstrip('%'))
        brightness = int(value / 100.0 * 254)
        group.on = True
        group.brightness = brightness
        if self.verbose:
            self.speak_dialog('set.brightness', {'brightness': value})

    @intent_handler
    def handle_adjust_color_temperature_intent(self, message, group):
        if "IncreaseKeyword" in message.data:
            color_temperature = \
                group.colortemp_k + self.color_temperature_step
            group.colortemp_k = \
                color_temperature if color_temperature < 6500 else 6500
            dialog = 'increase.color.temperature'
        else:
            color_temperature = \
                group.colortemp_k - self.color_temperature_step
            group.colortemp_k = \
                color_temperature if color_temperature > 2000 else 2000
            dialog = 'decrease.color.temperature'
        if self.verbose:
            self.speak_dialog(dialog)

    @intent_handler
    def handle_connect_lights_intent(self, message, group):
        if self.user_supplied_ip:
            self.speak_dialog('ip.in.config')
            return
        if self.verbose:
            self.speak_dialog('connecting')
        self._connect_to_bridge(acknowledge_successful_connection=True)
    
    @intent_handler
    def handle_change_color_intent(self, message, group):
        if "Color" in message.data and message.data["Color"] in self.colors_to_cie_color_map:
            group.xy = self.colors_to_cie_color_map[message.data["Color"]]

    def stop(self):
        pass

    def _map_colors_to_cie_colors(self):
        cie_colors_map = dict()
        try:
            colors_json = json.load(open(self._get_color_file_path()))
            for color_name, rgb_values in colors_json.items():
                cie_colors_map[color_name] = self._rgb_to_cie(rgb_values[0], rgb_values[1], rgb_values[2])
        except Exception as e:
            LOGGER.error(e)
        return cie_colors_map

    def _get_color_file_path(self):
        color_files_directory_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "colors")
        return os.path.join(color_files_directory_path, self.lang.split("-")[0] + "-colors.json")


    """
    This function is based on the project https://github.com/usolved/cie-rgb-converter which is licensed under MIT license.

    MIT License

    Copyright (c) 2017 www.usolved.net

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """
    def _rgb_to_cie(self, red, green, blue):
        red = pow((red + 0.055) / (1.0 + 0.055), 2.4) if (red > 0.04045) else (red / 12.92)
        green = pow((green + 0.055) / (1.0 + 0.055), 2.4) if (green > 0.04045) else (green / 12.92)
        blue = pow((blue + 0.055) / (1.0 + 0.055), 2.4) if (blue > 0.04045) else (blue / 12.92)

        X = red * 0.664511 + green * 0.154324 + blue * 0.162028
        Y = red * 0.283881 + green * 0.668433 + blue * 0.047685
        Z = red * 0.000088 + green * 0.072310 + blue * 0.986039

        x = round((X / (X + Y + Z)), 4)
        y = round((Y / (X + Y + Z)), 4)

        return [x, y]
    
    def _register_colors(self):
        for color_name in self.colors_to_cie_color_map:
            self.register_vocabulary(color_name, "Color")




def _discover_bridge():
    """
    Naive method to find a phillips hue bridge on
    the network, via UPNP.

    Raises
    ------
    DeviceNotFoundException
        If the bridge is not found.

    Returns
    -------
    str
        An IP address representing the bridge that was found
    """
    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    SSDP_MX = 1
    SSDP_ST = "urn:schemas-upnp-org:device:Basic:1"

    ssdpRequest = "M-SEARCH * HTTP/1.1\r\n" + \
                  "HOST: %s:%d\r\n" % (SSDP_ADDR, SSDP_PORT) + \
                  "MAN: \"ssdp:discover\"\r\n" + \
                  "MX: %d\r\n" % (SSDP_MX,) + \
                  "ST: %s\r\n" % (SSDP_ST,) + "\r\n"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    sock.sendto(ssdpRequest.encode(), (SSDP_ADDR, SSDP_PORT))
    try:
        result = sock.recv(4096).decode()
        lines = result.splitlines()
        for i in range(len(lines)):
            if lines[i].startswith('hue-bridgeid'):
                location_index = i - 2
                sock.close()
                return lines[location_index].split('/')[2]
    except:
        pass
    raise DeviceNotFoundException()


def create_skill():
    return PhillipsHueSkill()
