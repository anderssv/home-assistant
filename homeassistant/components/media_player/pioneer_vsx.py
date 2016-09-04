"""
Support for Pioneer Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.pioneer_vsx/

Pioneer VSX receivers has a bug where telnet stops responding. So we need to support UNKNOWN state and keep checking
to catch when the reciver is back.

"""
import logging
import telnetlib

from homeassistant.components.media_player import (
    DOMAIN, SUPPORT_PAUSE, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNKNOWN,
    CONF_NAME)

_LOGGER = logging.getLogger(__name__)

SUPPORT_PIONEER = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

MAX_VOLUME = 185
MAX_SOURCE_NUMBERS = 60

INPUT_SOURCES = {
    "01": "CD",
    "06": "SAT/CABLE",
    "15": "DVR/BDR"
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Pioneer platform."""
    if not config.get(CONF_HOST):
        _LOGGER.error(
            "Missing required configuration items in %s: %s",
            DOMAIN,
            CONF_HOST)
        return False

    pioneer = PioneerDevice(
        config.get(CONF_NAME, "Pioneer AVR"),
        config.get(CONF_HOST),
        config.get(CONF_PORT)
    )
    if pioneer.update():
        add_devices([pioneer])
        return True
    else:
        return False


class PioneerDevice(MediaPlayerDevice):
    """Representation of a Pioneer device."""

    # pylint: disable=too-many-public-methods, abstract-method
    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, host, port):
        """Initialize the Pioneer device."""
        self._name = name
        self._host = host
        self._port = port if port else 8102
        self._pwstate = "UNKNOW"
        self._selected_source = ''

    @classmethod
    def telnet_request(cls, telnet, command, expected_prefix):
        """Execute `command` and return the response."""
        telnet.write(command.encode("ASCII") + b"\r")

        # The receiver will randomly send state change updates, make sure
        # we get the response we are looking for
        for _ in range(3):
            result = telnet.read_until(b"\r\n", timeout=0.2).decode("ASCII") \
                .strip()
            if result.startswith(expected_prefix):
                return result

        return None

    def telnet_command(self, command):
        """Establish a telnet connection and sends `command`."""
        try:
            telnet = telnetlib.Telnet(self._host, self._port, timeout=10)
            telnet.write(command.encode("ASCII") + b"\r")
            telnet.read_very_eager()  # skip response
        except Exception as e:
            self.set_unknown_state()
        finally:
            if telnet:
                telnet.close()

    def update(self):
        """Get the latest details from the device."""
        try:
            telnet = telnetlib.Telnet(self._host, self._port, timeout=5)

            self._pwstate = self.telnet_request(telnet, "?P", "PWR")

            self._selected_source = self.telnet_request(telnet, "?F", "FN")

            return True
        except Exception as e:
            self.set_unknown_state()
            return True
        finally:
            if telnet:
                telnet.close()

    def set_unknown_state(self):
        self._pwstate = "UNKNOWN"
        self._selected_source = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == "PWR1" or self._pwstate == "PWR2":
            return STATE_OFF
        elif self._pwstate == "PWR0":
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_PIONEER

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._selected_source:
            return self._source_resolve(self._selected_source[2:])
        return "Unknown"

    def turn_off(self):
        """Turn off media player."""
        self.telnet_command("PF")

    def turn_on(self):
        """Turn the media player on."""
        self.telnet_command("PO")

    def select_source(self, source):
        """Select input source."""
        set_source = source
        for source_key, source_name in INPUT_SOURCES.items():
            if source_name == source:
                set_source = source_key
                break

        self.telnet_command(set_source + "FN")


    @property
    def source(self):
        """Return the current input source."""
        return self._source_resolve(self._selected_source[2:])


    def _source_resolve(self, source):
        """Do some fuzzy resolving to handle unknown sources as we don't have the complete list"""
        if source in INPUT_SOURCES:
            return INPUT_SOURCES[source]
        else:
            return source

    @property
    def source_list(self):
        """List of available input sources."""
        return list(INPUT_SOURCES.values())
