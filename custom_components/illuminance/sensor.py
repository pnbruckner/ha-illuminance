"""
Illuminance Sensor.

A Sensor platform that estimates outdoor illuminance from current weather conditions.
"""
import datetime as dt
import logging
from math import asin, cos, exp, radians, sin

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, PLATFORM_SCHEMA

try:
    from homeassistant.components.darksky.sensor import ATTRIBUTION as DSS_ATTRIBUTION
except:
    DSS_ATTRIBUTION = "no_dss"
try:
    from homeassistant.components.darksky.weather import (
        ATTRIBUTION as DSW_ATTRIBUTION,
        MAP_CONDITION as DSW_MAP_CONDITION,
    )
except:
    DSW_ATTRIBUTION = "no_dsw"
try:
    from homeassistant.components.met.weather import ATTRIBUTION as MET_ATTRIBUTION
except:
    MET_ATTRIBUTION = "no_met"
try:
    from homeassistant.components.accuweather.weather import (
        ATTRIBUTION as AW_ATTRIBUTION,
    )
except:
    AW_ATTRIBUTION = "no_aw"
try:
    from homeassistant.components.openweathermap.weather import (
        ATTRIBUTION as OWM_ATTRIBUTION,
    )
except:
    OWM_ATTRIBUTION = "no_owm"
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_ENTITY_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    EVENT_CORE_CONFIG_UPDATE,
    LIGHT_LUX,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.sun import get_astral_location
import homeassistant.util.dt as dt_util

DEFAULT_NAME = "Illuminance"
MIN_SCAN_INTERVAL = dt.timedelta(minutes=5)
DEFAULT_SCAN_INTERVAL = dt.timedelta(minutes=5)

DARKSKY_MAPPING = (
    (10, ("hail", "lightning")),
    (5, ("fog", "rainy", "snowy", "snowy-rainy")),
    (3, ("cloudy",)),
    (2, ("partlycloudy",)),
    (1, ("clear-night", "sunny", "windy")),
)
MET_MAPPING = (
    (10, ("lightning-rainy", "pouring")),
    (5, ("fog", "rainy", "snowy", "snowy-rainy")),
    (3, ("cloudy",)),
    (2, ("partlycloudy",)),
    (1, ("clear-night", "sunny")),
)
AW_MAPPING = (
    (10, ("lightning", "lightning-rainy", "pouring")),
    (
        5,
        (
            "cloudy",
            "fog",
            "rainy",
            "snowy",
            "snowy-rainy",
            "hail",
            "exceptional",
            "windy",
        ),
    ),
    (3, ("mostlycloudy",)),
    (2, ("partlycloudy",)),
    (1, ("sunny", "clear-night")),
)
ECOBEE_MAPPING = (
    (10, ("pouring", "snowy-heavy", "lightning-rainy")),
    (5, ("cloudy", "fog", "rainy", "snowy", "snowy-rainy", "hail", "windy", "tornado")),
    (2, ("partlycloudy", "hazy")),
    (1, ("sunny",)),
)
OWM_MAPPING = (
    (10, ("lightning", "lightning-rainy", "pouring")),
    (
        5,
        (
            "cloudy",
            "fog",
            "rainy",
            "snowy",
            "snowy-rainy",
            "hail",
            "exceptional",
            "windy",
            "windy-variant",
        ),
    ),
    (2, ("partlycloudy",)),
    (1, ("sunny", "clear-night")),
)
BR_MAPPING = (
    (10, ("lightning", "lightning-rainy", "pouring")),
    (
        5,
        (
            "cloudy",
            "fog",
            "rainy",
            "snowy",
            "snowy-rainy",
        ),
    ),
    (2, ("partlycloudy",)),
    (1, ("sunny",)),
)

_LOGGER = logging.getLogger(__name__)

MODE_NORMAL = "normal"
MODE_SIMPLE = "simple"
MODES = (MODE_NORMAL, MODE_SIMPLE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            cv.time_period, vol.Range(min=MIN_SCAN_INTERVAL)
        ),
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_MODE, default=MODE_NORMAL): vol.In(MODES),
    }
)

_20_MIN = dt.timedelta(minutes=20)
_40_MIN = dt.timedelta(minutes=40)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up platform."""

    def get_loc_elev(event=None):
        """Get HA Location object & elevation."""
        try:
            loc, elev = get_astral_location(hass)
        except TypeError:
            loc = get_astral_location(hass)
            elev = None
        hass.data["illuminance"] = loc, elev

    if "illuminance" not in hass.data:
        get_loc_elev()
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, get_loc_elev)

    async_add_entities([IlluminanceSensor(config)], True)


def _illumiance(elev):
    """Calculate illuminance from sun at given elevation."""
    elev_rad = radians(elev)
    u = sin(elev_rad)
    x = 753.66156
    s = asin(x * cos(elev_rad) / (x + 1))
    m = x * (cos(s) - u) + cos(s)
    m = exp(-0.2 * m) * u + 0.0289 * exp(-0.042 * m) * (
        1 + (elev + 90) * u / 57.29577951
    )
    return 133775 * m


class IlluminanceSensor(Entity):
    """Illuminance sensor."""

    def __init__(self, config):
        """Initialize."""
        self._entity_id = config[CONF_ENTITY_ID]
        self._name = config[CONF_NAME]
        self._mode = config[CONF_MODE]
        if self._mode == MODE_SIMPLE:
            self._sun_data = None
        self._state = None
        self._unsub = None
        self._sk_mapping = None
        self._cd_mapping = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""

        def get_mappings(state):
            if not state:
                if self.hass.is_running:
                    _LOGGER.error("%s: State not found: %s", self.name, self._entity_id)
                return False

            if "buienradar" in self._entity_id:
                self._sk_mapping = BR_MAPPING
                return True

            attribution = state.attributes.get(ATTR_ATTRIBUTION)
            if not attribution:
                _LOGGER.error(
                    "%s: No %s attribute: %s",
                    self.name,
                    ATTR_ATTRIBUTION,
                    self._entity_id,
                )
                return False

            if attribution in (DSS_ATTRIBUTION, DSW_ATTRIBUTION):
                if state.domain == SENSOR_DOMAIN:
                    self._cd_mapping = DSW_MAP_CONDITION
                self._sk_mapping = DARKSKY_MAPPING
            elif attribution == MET_ATTRIBUTION:
                self._sk_mapping = MET_MAPPING
            elif attribution == AW_ATTRIBUTION:
                self._sk_mapping = AW_MAPPING
            elif "Ecobee" in attribution:
                self._sk_mapping = ECOBEE_MAPPING
            elif attribution == OWM_ATTRIBUTION:
                self._sk_mapping = OWM_MAPPING
            elif "buienradar" in attribution.lower():
                self._sk_mapping = BR_MAPPING
            else:
                _LOGGER.error(
                    "%s: Unsupported sensor: %s, attribution: %s",
                    self.name,
                    self._entity_id,
                    attribution,
                )
                return False

            _LOGGER.info("%s: Supported attribution: %s", self.name, attribution)
            return True

        if not get_mappings(self.hass.states.get(self._entity_id)):
            _LOGGER.info("%s: Waiting for %s", self.name, self._entity_id)

        @callback
        def sensor_state_listener(event):
            new_state = event.data["new_state"]
            old_state = event.data["old_state"]
            if not self._sk_mapping:
                if not get_mappings(new_state):
                    return
            if new_state and (not old_state or new_state.state != old_state.state):
                self.async_schedule_update_ha_state(True)

        # Update whenever source entity changes.
        self._unsub = async_track_state_change_event(
            self.hass, self._entity_id, sensor_state_listener
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def state(self):
        """Return state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return LIGHT_LUX

    async def async_update(self):
        """Update state."""
        if not self._sk_mapping:
            return

        _LOGGER.debug("Updating %s", self.name)

        now = dt_util.now().replace(microsecond=0)

        if self._mode == MODE_SIMPLE:
            sun_factor = self._sun_factor(now)

            # No point in getting conditions because estimated illuminance derived
            # from it will just be multiplied by zero. I.e., it's nighttime.
            if sun_factor == 0:
                self._state = 10
                return

        state = self.hass.states.get(self._entity_id)
        if state is None:
            if self.hass.is_running:
                _LOGGER.error("%s: State not found: %s", self.name, self._entity_id)
            return

        raw_conditions = state.state
        if self._cd_mapping:
            conditions = self._cd_mapping.get(raw_conditions)
        else:
            conditions = raw_conditions

        sk = None
        for _sk, _conditions in self._sk_mapping:
            if conditions in _conditions:
                sk = _sk
                break
        if not sk:
            if self.hass.is_running:
                _LOGGER.error(
                    "%s: Unexpected current observation: %s", self.name, raw_conditions
                )
            return

        if self._mode == MODE_SIMPLE:
            illuminance = 10000 * sun_factor
        else:
            illuminance = _illumiance(self._astral_event("solar_elevation", now))
        self._state = round(illuminance / sk)

    def _astral_event(self, event, date_or_dt):
        loc, elev = self.hass.data["illuminance"]
        if elev is None:
            return getattr(loc, event)(date_or_dt)
        return getattr(loc, event)(date_or_dt, observer_elevation=elev)

    def _sun_factor(self, now):
        now_date = now.date()

        if self._sun_data and self._sun_data[0] == now_date:
            (sunrise_begin, sunrise_end, sunset_begin, sunset_end) = self._sun_data[1]
        else:
            sunrise = self._astral_event("sunrise", now_date)
            sunset = self._astral_event("sunset", now_date)
            sunrise_begin = sunrise - _20_MIN
            sunrise_end = sunrise + _40_MIN
            sunset_begin = sunset - _40_MIN
            sunset_end = sunset + _20_MIN
            self._sun_data = (
                now_date,
                (sunrise_begin, sunrise_end, sunset_begin, sunset_end),
            )

        if sunrise_end < now < sunset_begin:
            # Daytime
            return 1
        if now < sunrise_begin or sunset_end < now:
            # Nighttime
            return 0
        if now <= sunrise_end:
            # Sunrise
            return (now - sunrise_begin).total_seconds() / (60 * 60)
        # Sunset
        return (sunset_end - now).total_seconds() / (60 * 60)
