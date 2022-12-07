"""
Illuminance Sensor.

A Sensor platform that estimates outdoor illuminance from current weather conditions.
"""
import datetime as dt
from enum import IntEnum
import logging
from math import asin, cos, exp, radians, sin
import re

import voluptuous as vol

from homeassistant.components.darksky.weather import MAP_CONDITION as DSW_MAP_CONDITION
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_ENTITY_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    EVENT_CORE_CONFIG_UPDATE,
    LIGHT_LUX,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
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
DEFAULT_FALLBACK = 10

CONF_FALLBACK = "fallback"

DARKSKY_PATTERN = r"(?i).*dark\s*sky.*"
DARKSKY_MAPPING = (
    (10, ("hail", "lightning")),
    (5, ("fog", "rainy", "snowy", "snowy-rainy")),
    (3, ("cloudy",)),
    (2, ("partlycloudy",)),
    (1, ("clear-night", "sunny", "windy")),
)
MET_PATTERN = r".*met\.no.*"
MET_MAPPING = (
    (10, ("lightning-rainy", "pouring")),
    (5, ("fog", "rainy", "snowy", "snowy-rainy")),
    (3, ("cloudy",)),
    (2, ("partlycloudy",)),
    (1, ("clear-night", "sunny")),
)
AW_PATTERN = r"(?i).*accuweather.*"
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
ECOBEE_PATTERN = r"(?i).*ecobee.*"
ECOBEE_MAPPING = (
    (10, ("pouring", "snowy-heavy", "lightning-rainy")),
    (5, ("cloudy", "fog", "rainy", "snowy", "snowy-rainy", "hail", "windy", "tornado")),
    (2, ("partlycloudy", "hazy")),
    (1, ("sunny",)),
)
OWM_PATTERN = r"(?i).*openweathermap.*"
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
BR_PATTERN = r"(?i).*buienradar.*"
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

ATTRIBUTION_TO_MAPPING = (
    (DARKSKY_PATTERN, DARKSKY_MAPPING),
    (MET_PATTERN, MET_MAPPING),
    (AW_PATTERN, AW_MAPPING),
    (ECOBEE_PATTERN, ECOBEE_MAPPING),
    (OWM_PATTERN, OWM_MAPPING),
    (BR_PATTERN, BR_MAPPING),
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
        vol.Optional(CONF_FALLBACK, default=DEFAULT_FALLBACK): vol.All(
            vol.Coerce(float), vol.Range(1, 10)
        ),
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


class AbortUpdate(RuntimeError):
    """Abort update."""


class EntityStatus(IntEnum):
    """Status of input entity."""

    NOT_SEEN = 0
    NO_ATTRIBUTION = 1
    BAD_ATTRIBUTION = 2
    OK_CONDITION = 3
    OK_CLOUD = 4


class IlluminanceSensor(Entity):
    """Illuminance sensor."""

    _state = None
    _entity_status = EntityStatus.NOT_SEEN
    _sk_mapping = None
    _cd_mapping = None
    _warned = False

    def __init__(self, config):
        """Initialize."""
        self._entity_id = config[CONF_ENTITY_ID]
        self._name = config[CONF_NAME]
        self._mode = config[CONF_MODE]
        if self._mode == MODE_SIMPLE:
            self._sun_data = None
        self._fallback = config[CONF_FALLBACK]

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""

        @callback
        def sensor_state_listener(event):
            new_state = event.data["new_state"]
            old_state = event.data["old_state"]
            if new_state and (
                self._entity_status <= EntityStatus.NO_ATTRIBUTION
                or not old_state
                or new_state.state != old_state.state
            ):
                self.async_schedule_update_ha_state(True)

        # When source entity changes check to see if we should update.
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_id, sensor_state_listener
            )
        )

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
        try:
            raw_condition = self._get_weather_data()
            illuminance = self._calculate_illuminance(
                dt_util.now().replace(microsecond=0)
            )
        except AbortUpdate:
            return
        sk, cond_desc = self._determine_divider(raw_condition)

        # Calculate final illuminance.

        self._state = round(illuminance / sk)
        _LOGGER.debug(
            "%s: Updating %s -> %i / %0.1f = %i",
            self.name,
            cond_desc,
            round(illuminance),
            sk,
            self._state,
        )

    def _get_weather_data(self):
        """Get weather data from input entity."""
        raw_condition = None

        if self._entity_status != EntityStatus.BAD_ATTRIBUTION:
            entity_state = self.hass.states.get(self._entity_id)
            if entity_state:
                raw_condition = entity_state.state
                if raw_condition in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    raw_condition = None

                if self._entity_status <= EntityStatus.NO_ATTRIBUTION and raw_condition:
                    try:
                        float(raw_condition)
                        self._entity_status = EntityStatus.OK_CLOUD
                        _LOGGER.info(
                            "%s: Supported sensor %s, cloud coverage",
                            self.name,
                            self._entity_id,
                        )
                    except ValueError:
                        attribution = entity_state.attributes.get(ATTR_ATTRIBUTION)
                        self._get_mappings(attribution, entity_state.domain)
                        if self._entity_status == EntityStatus.BAD_ATTRIBUTION:
                            _LOGGER.error(
                                "%s: Unsupported sensor: %s, %s: %s",
                                self.name,
                                self._entity_id,
                                ATTR_ATTRIBUTION,
                                attribution,
                            )
                        elif self._entity_status == EntityStatus.OK_CONDITION:
                            _LOGGER.info(
                                "%s: Supported sensor %s, %s: %s",
                                self.name,
                                self._entity_id,
                                ATTR_ATTRIBUTION,
                                attribution,
                            )

            if self._entity_status <= EntityStatus.NO_ATTRIBUTION:
                if not self.hass.is_running:
                    # Give weather entity a chance to update so there's no unexpected
                    # "spike" initially.
                    raise AbortUpdate
                if self._entity_status == EntityStatus.NO_ATTRIBUTION:
                    _LOGGER.error(
                        "%s: Unsupported sensor: %s, not a number and no %s attribute",
                        self.name,
                        self._entity_id,
                        ATTR_ATTRIBUTION,
                    )
                    self._entity_status = EntityStatus.BAD_ATTRIBUTION

        if raw_condition:
            self._warned = False
        elif not self._warned:
            _LOGGER.warning("%s: Weather data not available", self.name)
            self._warned = True

        return raw_condition

    def _get_mappings(self, attribution, domain):
        """Get sk -> conditions mappings."""
        if not attribution:
            self._entity_status = EntityStatus.NO_ATTRIBUTION
            return

        for pat, mapping in ATTRIBUTION_TO_MAPPING:
            if re.fullmatch(pat, attribution):
                self._sk_mapping = mapping
                if pat == DARKSKY_PATTERN and domain == SENSOR_DOMAIN:
                    self._cd_mapping = DSW_MAP_CONDITION
                self._entity_status = EntityStatus.OK_CONDITION
                return

        self._entity_status = EntityStatus.BAD_ATTRIBUTION

    def _calculate_illuminance(self, now):
        """Calculate sunny illuminance."""
        if self._mode == MODE_NORMAL:
            return _illumiance(self._astral_event("solar_elevation", now))

        sun_factor = self._sun_factor(now)

        # No point in getting division factor because zero divided by anything is
        # still zero. I.e., it's nighttime.
        if sun_factor == 0:
            # For historic reasons, return a value of 10.
            _LOGGER.debug("%s: Updating -> 10", self.name)
            self._state = 10
            raise AbortUpdate

        return 10000 * sun_factor

    def _astral_event(self, event, date_or_dt):
        """Get astral event."""
        loc, elev = self.hass.data["illuminance"]
        if elev is None:
            return getattr(loc, event)(date_or_dt)
        return getattr(loc, event)(date_or_dt, observer_elevation=elev)

    def _sun_factor(self, now):
        """Calculate sun factor."""
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

    def _determine_divider(self, raw_condition):
        """Determine illuminance divider."""
        sk = None
        if raw_condition:
            if self._entity_status == EntityStatus.OK_CONDITION:
                if self._cd_mapping:
                    condition = self._cd_mapping.get(raw_condition)
                    cond_desc = f"({raw_condition} -> {condition})"
                else:
                    condition = raw_condition
                    cond_desc = f"({condition})"
                for _sk, conditions in self._sk_mapping:
                    if condition in conditions:
                        sk = _sk
                        break
                if not sk:
                    _LOGGER.error(
                        "%s: Unexpected current observation (%s)",
                        self.name,
                        cond_desc,
                        raw_condition,
                    )
            elif self._entity_status == EntityStatus.OK_CLOUD:
                cloud = float(raw_condition)
                cond_desc = f"({round(cloud)}%)"
                sk = 10 ** (cloud / 100)
        if not sk:
            cond_desc = "without weather data"
            sk = self._fallback
        return sk, cond_desc
