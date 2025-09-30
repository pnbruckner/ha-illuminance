"""Illuminance Sensor.

A Sensor platform that estimates outdoor illuminance from current weather conditions.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum, IntEnum, auto
from functools import cached_property  # pylint: disable=hass-deprecated-import
import logging
from math import asin, cos, exp, radians, sin
import re
from typing import Any, cast

from astral import Elevation
from astral.location import Location
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_ENTITY_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    LIGHT_LUX,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfIrradiance,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback, EntityPlatform
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_FALLBACK,
    DEFAULT_FALLBACK,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LUX_PER_WPSM,
    MIN_SCAN_INTERVAL,
)

# Standard sk to conditions mapping

MAPPING = (
    (
        10,
        (
            ATTR_CONDITION_LIGHTNING,
            ATTR_CONDITION_LIGHTNING_RAINY,
            ATTR_CONDITION_POURING,
        ),
    ),
    (
        5,
        (
            ATTR_CONDITION_CLOUDY,
            ATTR_CONDITION_FOG,
            ATTR_CONDITION_RAINY,
            ATTR_CONDITION_SNOWY,
            ATTR_CONDITION_SNOWY_RAINY,
            ATTR_CONDITION_HAIL,
            ATTR_CONDITION_EXCEPTIONAL,
        ),
    ),
    (2, (ATTR_CONDITION_PARTLYCLOUDY, ATTR_CONDITION_WINDY_VARIANT)),
    (1, (ATTR_CONDITION_SUNNY, ATTR_CONDITION_CLEAR_NIGHT, ATTR_CONDITION_WINDY)),
)

# Weather sources that require special treatment

AW_PATTERN = re.compile(r"(?i).*accuweather.*")
AW_MAPPING = ((3, ("mostlycloudy",)),)

ECOBEE_PATTERN = re.compile(r"(?i).*ecobee.*")
ECOBEE_MAPPING = (
    (10, ("snowy-heavy",)),
    (5, ("tornado",)),
    (2, ("hazy",)),
)

ADDITIONAL_MAPPINGS = ((AW_PATTERN, AW_MAPPING), (ECOBEE_PATTERN, ECOBEE_MAPPING))

LOC_ELEV: HassKey[tuple[Location, Elevation]] = HassKey(DOMAIN)

_LOGGER = logging.getLogger(__name__)


class Mode(Enum):
    """Illuminance mode."""

    normal = auto()
    simple = auto()
    irradiance = auto()


MODES = list(Mode.__members__)

ILLUMINANCE_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        cv.time_period, vol.Range(min=MIN_SCAN_INTERVAL)
    ),
    vol.Optional(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_MODE, default=MODES[0]): vol.In(MODES),
    vol.Optional(CONF_FALLBACK): vol.All(vol.Coerce(float), vol.Range(1, 10)),
}
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(ILLUMINANCE_SCHEMA)

_20_MIN = timedelta(minutes=20)
_40_MIN = timedelta(minutes=40)

Num = float | int


@dataclass
class IlluminanceSensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """Illuminance sensor entity description."""

    weather_entity: str | None = None
    mode: Mode | None = None
    fallback: float | None = None
    unique_id: str | None = None
    scan_interval: timedelta | None = None


def _sensor(config: ConfigType, unique_id: str, scan_interval: timedelta) -> Entity:
    """Create entity to add."""
    weather_entity = config.get(CONF_ENTITY_ID)
    fallback = cast(
        float, config.get(CONF_FALLBACK, DEFAULT_FALLBACK if weather_entity else 1)
    )
    if (mode := Mode.__getitem__(cast(str, config[CONF_MODE]))) is Mode.irradiance:
        device_class = SensorDeviceClass.IRRADIANCE
        native_unit_of_measurement: str = UnitOfIrradiance.WATTS_PER_SQUARE_METER
        suggested_display_precision = 1
    else:
        device_class = SensorDeviceClass.ILLUMINANCE
        native_unit_of_measurement = LIGHT_LUX
        suggested_display_precision = 0
    entity_description = IlluminanceSensorEntityDescription(
        key=DOMAIN,
        device_class=device_class,
        name=cast(str, config[CONF_NAME]),
        native_unit_of_measurement=native_unit_of_measurement,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=suggested_display_precision,
        weather_entity=weather_entity,
        mode=mode,
        fallback=fallback,
        unique_id=unique_id,
        scan_interval=scan_interval,
    )

    return IlluminanceSensor(entity_description)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    config = dict(entry.options)
    config[CONF_NAME] = entry.title
    unique_id = entry.unique_id or entry.entry_id
    scan_interval = timedelta(minutes=config[CONF_SCAN_INTERVAL])
    async_add_entities([_sensor(config, unique_id, scan_interval)], True)


def _illumiance(elev: Num) -> float:
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
    OK_CLOUD = 2
    OK_CONDITION = 3


class IlluminanceSensor(SensorEntity):
    """Illuminance sensor."""

    entity_description: IlluminanceSensorEntityDescription
    _attr_device_info = DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, DOMAIN)},
        translation_key="service",
    )
    _entity_status = EntityStatus.NOT_SEEN
    _sk_mapping: Sequence[tuple[Num, Sequence[str]]] | None = None
    _sk: Num
    _cond_desc: str | None = None
    _warned = False
    _sun_data: tuple[date, tuple[datetime, datetime, datetime, datetime]] | None = None

    def __init__(self, entity_description: IlluminanceSensorEntityDescription) -> None:
        """Initialize sensor."""
        self.entity_description = entity_description
        if entity_description.unique_id:
            self._attr_unique_id = entity_description.unique_id
        else:
            self._attr_unique_id = cast(str, entity_description.name)

    @cached_property
    def weather_entity(self) -> str | None:
        """Input weather entity ID."""
        return self.entity_description.weather_entity

    @cached_property
    def mode(self) -> Mode:
        """Illuminance calculation mode."""
        return cast(Mode, self.entity_description.mode)

    @cached_property
    def fallback(self) -> float:
        """Fallback illuminance divisor."""
        return cast(float, self.entity_description.fallback)

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        # This method is called before first call to async_update.

        if (scan_interval := self.entity_description.scan_interval) is not None:
            platform.scan_interval = scan_interval
            if hasattr(platform, "scan_interval_seconds"):
                platform.scan_interval_seconds = scan_interval.total_seconds()
        super().add_to_platform_start(hass, platform, parallel_updates)

        # Now that parent method has been called, self.hass has been initialized.

        self._get_divisor_from_weather_data(
            hass.states.get(self.weather_entity) if self.weather_entity else None
        )
        if not self.weather_entity:
            return

        @callback
        def sensor_state_listener(event: Event[EventStateChangedData]) -> None:
            """Process input entity state update."""
            new_state: State | None = event.data["new_state"]
            old_state: State | None = event.data["old_state"]
            if (
                self._entity_status <= EntityStatus.NO_ATTRIBUTION
                or not old_state
                or not new_state
                or new_state.state != old_state.state
            ):
                self._get_divisor_from_weather_data(new_state)
                self.async_schedule_update_ha_state(True)

        # When source entity changes check to see if we should update.
        self.async_on_remove(
            async_track_state_change_event(
                hass, self.weather_entity, sensor_state_listener
            )
        )

    async def async_update(self) -> None:
        """Update state."""
        if (
            self.weather_entity
            and self._entity_status <= EntityStatus.NO_ATTRIBUTION
            and not self.hass.is_running
        ):
            return

        try:
            value = self._calculate_illuminance(dt_util.utcnow().replace(microsecond=0))
        except AbortUpdate:
            return

        if self.mode is Mode.irradiance:
            value /= LUX_PER_WPSM

        # Calculate final value.

        self._attr_native_value = value / self._sk
        display_precision = self._sensor_option_display_precision or 0
        _LOGGER.debug(
            "%s: Updating %s -> %s / %0.2f = %s",
            self.name,
            self._cond_desc,
            f"{value:0.{display_precision}f}",
            self._sk,
            f"{self._attr_native_value:0.{display_precision}f}",
        )

    def _get_divisor_from_weather_data(self, entity_state: State | None) -> None:
        """Get weather data from input entity."""

        # Use fallback unless divisor can be successfully determined from weather data.
        self._cond_desc = "without weather data"
        self._sk = self.fallback

        if not self.weather_entity:
            return

        condition = entity_state and entity_state.state
        if condition in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            condition = None

        # If entity type, and potentially assocated mappings, have not been determined
        # yet, try to determine them.
        if self._entity_status <= EntityStatus.NO_ATTRIBUTION:
            if condition:
                assert entity_state
                try:
                    float(condition)
                    self._entity_status = EntityStatus.OK_CLOUD
                    _LOGGER.info(
                        "%s: Supported sensor %s: cloud coverage",
                        self.name,
                        self.weather_entity,
                    )
                except ValueError:
                    attribution = cast(
                        str | None, entity_state.attributes.get(ATTR_ATTRIBUTION)
                    )
                    self._get_mappings(attribution, entity_state.domain)
                    if self._entity_status == EntityStatus.OK_CONDITION:
                        _LOGGER.info(
                            "%s: Supported sensor %s: %s is %s",
                            self.name,
                            self.weather_entity,
                            ATTR_ATTRIBUTION,
                            attribution,
                        )

            if self._entity_status <= EntityStatus.NO_ATTRIBUTION:
                if self.hass.is_running:
                    _LOGGER.debug(
                        "%s: Sensor %s: "
                        "not a number, no %s attribute, or doesn't exist"
                        "; will use standard condition mappings",
                        self.name,
                        self.weather_entity,
                        ATTR_ATTRIBUTION,
                    )
                    self._warned = True
                    self._sk_mapping = MAPPING
                    self._entity_status = EntityStatus.OK_CONDITION
                else:
                    return

        if condition:
            self._warned = False
        else:
            if not self._warned:
                _LOGGER.warning("%s: Weather data not available", self.name)
                self._warned = True
            return

        if self._entity_status == EntityStatus.OK_CLOUD:
            try:
                cloud = min(max(0, float(condition)), 100)
            except ValueError:
                _LOGGER.error(
                    "%s: Cloud coverage sensor state is not a number: %s",
                    self.name,
                    condition,
                )
            else:
                self._cond_desc = f"({round(cloud)}%)"
                self._sk = 10 ** (cloud / 100)
            return

        assert self._entity_status == EntityStatus.OK_CONDITION
        assert self._sk_mapping

        for sk, conditions in self._sk_mapping:
            if condition in conditions:
                self._cond_desc = f"({condition})"
                self._sk = sk
                return
        _LOGGER.error("%s: Unexpected current condition: %s", self.name, condition)

    def _get_mappings(self, attribution: str | None, domain: str) -> None:
        """Get sk -> conditions mappings."""
        if not attribution:
            self._entity_status = EntityStatus.NO_ATTRIBUTION
            return

        self._sk_mapping = MAPPING
        for pat, mapping in ADDITIONAL_MAPPINGS:
            if pat.fullmatch(attribution):
                self._sk_mapping += mapping
        self._entity_status = EntityStatus.OK_CONDITION

    def _calculate_illuminance(self, now: datetime) -> Num:
        """Calculate sunny illuminance."""
        if self.mode is not Mode.simple:
            return _illumiance(cast(Num, self._astral_event("solar_elevation", now)))

        sun_factor = self._sun_factor(now)

        # No point in getting division factor because zero divided by anything is
        # still zero. I.e., it's nighttime.
        if sun_factor == 0:
            # For historic reasons, return a value of 10.
            _LOGGER.debug("%s: Updating -> 10", self.name)
            self._attr_native_value = 10
            raise AbortUpdate

        return 10000 * sun_factor

    def _astral_event(self, event: str, date_or_dt: date | datetime) -> Any:
        """Get astral event."""
        loc, elev = self.hass.data[LOC_ELEV]
        if event == "solar_elevation":
            return getattr(loc, event)(date_or_dt, observer_elevation=elev)
        return getattr(loc, event)(date_or_dt, local=False, observer_elevation=elev)

    def _sun_factor(self, now: datetime) -> Num:
        """Calculate sun factor."""
        now_date = dt_util.as_local(now).date()

        if self._sun_data and self._sun_data[0] == now_date:
            (sunrise_begin, sunrise_end, sunset_begin, sunset_end) = self._sun_data[1]
        else:
            sunrise = cast(datetime, self._astral_event("sunrise", now_date))
            sunset = cast(datetime, self._astral_event("sunset", now_date))
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
