"""
Illuminance Sensor.

A Sensor platform that estimates outdoor illuminance from current weather conditions.
"""
import asyncio
import datetime as dt
import logging
from math import asin, cos, exp, radians, sin

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN, PLATFORM_SCHEMA)
try:
    from homeassistant.components.darksky.sensor import (
        ATTRIBUTION as DSS_ATTRIBUTION)
except:
    DSS_ATTRIBUTION = "no_dss"
try:
    from homeassistant.components.yr.sensor import ATTRIBUTION as YRS_ATTRIBUTION
except:
    YRS_ATTRIBUTION = "no_yrs"
try:
    from homeassistant.components.darksky.weather import (
        ATTRIBUTION as DSW_ATTRIBUTION, MAP_CONDITION as DSW_MAP_CONDITION)
except:
    DSW_ATTRIBUTION = "no_dsw"
try:
    from homeassistant.components.met.weather import ATTRIBUTION as MET_ATTRIBUTION
except:
    MET_ATTRIBUTION = "no_met"
try:
    from homeassistant.components.accuweather.weather import ATTRIBUTION as AW_ATTRIBUTION
except:
    AW_ATTRIBUTION = "no_aw"
try:
    from homeassistant.components.openweathermap.weather import ATTRIBUTION as OWM_ATTRIBUTION
except:
    OWM_ATTRIBUTION = "no_owm"
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_ENTITY_ID, CONF_API_KEY, CONF_MODE, CONF_NAME,
    CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.sun import get_astral_event_date, get_astral_location
import homeassistant.util.dt as dt_util

DEFAULT_NAME = 'Illuminance'
MIN_SCAN_INTERVAL = dt.timedelta(minutes=5)
DEFAULT_SCAN_INTERVAL = dt.timedelta(minutes=5)

WU_MAPPING = (
    (10, ('tstorms',)),
    (5, ('cloudy', 'fog', 'rain', 'sleet', 'snow', 'flurries',
            'chanceflurries', 'chancerain', 'chancesleet',
            'chancesnow', 'chancetstorms')),
    (3, ('mostlycloudy',)),
    (2, ('partlysunny', 'partlycloudy', 'mostlysunny', 'hazy')),
    (1, ('sunny', 'clear')))
YR_MAPPING = (
    (10, (6, 11, 14, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
           33, 34)),
    (5, (5, 7, 8, 9, 10, 12, 13, 15, 40, 41, 42, 43, 44, 45, 46, 47, 48,
            49, 50)),
    (3, (4, )),
    (2, (2, 3)),
    (1, (1, )))
DARKSKY_MAPPING = (
    (10, ('hail', 'lightning')),
    (5, ('fog', 'rainy', 'snowy', 'snowy-rainy')),
    (3, ('cloudy', )),
    (2, ('partlycloudy', )),
    (1, ('clear-night', 'sunny', 'windy')))
MET_MAPPING = (
    (10, ('lightning-rainy', 'pouring')),
    (5, ('fog', 'rainy', 'snowy', 'snowy-rainy')),
    (3, ('cloudy', )),
    (2, ('partlycloudy', )),
    (1, ('clear-night', 'sunny')),
)
AW_MAPPING = (
    (10, ('lightning', 'lightning-rainy', 'pouring')),
    (5, ('cloudy', 'fog', 'rainy', 'snowy', 'snowy-rainy', 'hail', 'exceptional', 'windy')),
    (3, ('mostlycloudy', )),
    (2, ('partlycloudy', )),
    (1, ('sunny', 'clear-night')),
)
ECOBEE_MAPPING = (
    (10, ('pouring', 'snowy-heavy', 'lightning-rainy')),
    (5, ('cloudy', 'fog', 'rainy', 'snowy', 'snowy-rainy', 'hail', 'windy', 'tornado')),
    (2, ('partlycloudy', 'hazy')),
    (1, ('sunny', )),
)
OWM_MAPPING = (
    (10, ('lightning', 'lightning-rainy', 'pouring')),
    (5, ('cloudy', 'fog', 'rainy', 'snowy', 'snowy-rainy', 'hail', 'exceptional', 'windy', 'windy-variant')),
    (2, ('partlycloudy', )),
    (1, ('sunny', 'clear-night')),
)

CONF_QUERY = 'query'

ATTR_CONDITIONS = 'conditions'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Exclusive(CONF_API_KEY, 'source'): cv.string,
        vol.Optional(CONF_QUERY): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
            vol.All(cv.time_period, vol.Range(min=MIN_SCAN_INTERVAL)),
        vol.Exclusive(CONF_ENTITY_ID, 'source'): cv.entity_id,
        vol.Optional(CONF_MODE, default="normal"): vol.In(["normal", "simple"]),
    }),
    cv.has_at_least_one_key(CONF_API_KEY, CONF_ENTITY_ID),
    cv.key_dependency(CONF_API_KEY, CONF_QUERY),
)

_WU_API_URL = 'http://api.wunderground.com/api/'\
              '{api_key}/{features}/q/{query}.json'

_20_MIN = dt.timedelta(minutes=20)
_40_MIN = dt.timedelta(minutes=40)


async def _async_get_wu_data(hass, session, api_key, features, query):
    try:
        with async_timeout.timeout(9, loop=hass.loop):
            resp = await session.get(_WU_API_URL.format(
                api_key=api_key, features='/'.join(features), query=query))
        resp.raise_for_status()
        resp = await resp.json()
        if 'error' in resp['response']:
            raise ValueError('Error from api.wunderground.com: {}'.format(
                resp['response']['error']['description']))
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        _LOGGER.error('%s: %s', exc.__class__.__name__, exc)
        return None

    return resp


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up platform."""
    using_wu = CONF_API_KEY in config
    session = None
    if using_wu:
        session = async_get_clientsession(hass)
        if not await _async_get_wu_data(
                hass, session, config[CONF_API_KEY], [], config[CONF_QUERY]):
            return False

    async_add_entities([IlluminanceSensor(using_wu, config, session)], True)


def _illumiance(elev):
    """Calculate illuminance from sun at given elevation."""
    elev_rad = radians(elev)
    u = sin(elev_rad)
    x = 753.66156
    s = asin(x * cos(elev_rad) / (x + 1))
    m = x * (cos(s) - u) + cos(s)
    m = exp(-0.2 * m) * u + 0.0289 * exp(-0.042 * m) * (1 + (elev + 90) * u / 57.29577951)
    return 133775 * m


# pylint: disable=too-many-instance-attributes
class IlluminanceSensor(Entity):
    """Illuminance sensor."""

    def __init__(self, using_wu, config, session):
        """Initialize."""
        self._using_wu = using_wu
        if using_wu:
            self._api_key = config[CONF_API_KEY]
            self._query = config[CONF_QUERY]
            self._session = session
            self._conditions = None
        else:
            self._entity_id = config[CONF_ENTITY_ID]
        self._name = config[CONF_NAME]
        self._state = None
        self._sun_data = None
        self._init_complete = False
        self._was_changing = False
        self._mode = config[CONF_MODE]

    async def async_added_to_hass(self):
        """Update after HA has started."""
        if self._using_wu:
            return

        @callback
        # pylint: disable=unused-argument
        def sensor_state_listener(entity, old_state, new_state):
            if new_state and (not old_state or
                              new_state.state != old_state.state):
                self.async_schedule_update_ha_state(True)

        @callback
        # pylint: disable=unused-argument
        def sensor_startup(event):
            self._init_complete = True

            # Update whenever source entity changes.
            async_track_state_change(
                self.hass, self._entity_id, sensor_state_listener)

            # Update now that source entity has had a chance to initialize.
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, sensor_startup)

    @property
    def should_poll(self):
        """Return if should poll for status."""
        # For the system (i.e., EntityPlatform) to configure itself to
        # periodically call our async_update method any call to this method
        # during initialization must return True. After that, when using normal
        # mode or for WU we'll always poll, and for simple mode with other
        # weather sources we'll only need to poll during the ramp
        # up and down periods around sunrise and sunset, and then once more
        # when period is done to make sure ramping is completed.
        if not self._init_complete or self._mode == "normal" or self._using_wu:
            return True
        changing = 0 < self._sun_factor(dt_util.now()) < 1
        if changing:
            self._was_changing = True
            return True
        if self._was_changing:
            self._was_changing = False
            return True
        return False

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def state(self):
        """Return state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device attributes."""
        if self._using_wu:
            attrs = {ATTR_CONDITIONS: self._conditions}
            return attrs
        return None

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return 'lux'

    # pylint: disable=too-many-return-statements
    # pylint: disable=too-many-branches
    async def async_update(self):
        """Update state."""
        _LOGGER.debug('Updating %s', self._name)

        now = dt_util.now().replace(microsecond=0)

        if self._mode == "simple":
            sun_factor = self._sun_factor(now)

            # No point in getting conditions because estimated illuminance derived
            # from it will just be multiplied by zero. I.e., it's nighttime.
            if sun_factor == 0:
                self._state = 10
                return

        if self._using_wu:
            features = ['conditions']

            resp = await _async_get_wu_data(
                self.hass, self._session, self._api_key, features,
                self._query)
            if not resp:
                return

            raw_conditions = resp['current_observation']['icon']
            conditions = self._conditions = raw_conditions
            mapping = WU_MAPPING
        else:
            state = self.hass.states.get(self._entity_id)
            if state is None:
                # If our initialization happens before the source entity has a
                # chance to initialize then we won't find its state. Don't log
                # that as an error.
                if self._init_complete:
                    _LOGGER.error('State not found: %s', self._entity_id)
                return
            attribution = state.attributes.get(ATTR_ATTRIBUTION)
            if not attribution:
                if self._init_complete:
                    _LOGGER.error('No %s attribute: %s',
                                  ATTR_ATTRIBUTION, self._entity_id)
                return
            raw_conditions = state.state
            if attribution in (DSS_ATTRIBUTION, DSW_ATTRIBUTION):
                if state.domain == SENSOR_DOMAIN:
                    conditions = DSW_MAP_CONDITION.get(raw_conditions)
                else:
                    conditions = raw_conditions
                mapping = DARKSKY_MAPPING
            elif attribution == YRS_ATTRIBUTION:
                try:
                    conditions = int(raw_conditions)
                except (TypeError, ValueError):
                    if self._init_complete:
                        _LOGGER.error('State of YR sensor not a number: %s',
                                      self._entity_id)
                    return
                mapping = YR_MAPPING
            elif attribution == MET_ATTRIBUTION:
                conditions = raw_conditions
                mapping = MET_MAPPING
            elif attribution == AW_ATTRIBUTION:
                conditions = raw_conditions
                mapping = AW_MAPPING
            elif 'Ecobee' in attribution:
                conditions = raw_conditions
                mapping = ECOBEE_MAPPING
            elif attribution == OWM_ATTRIBUTION:
                conditions = raw_conditions
                mapping = OWM_MAPPING
            else:
                if self._init_complete:
                    _LOGGER.error('Unsupported sensor: %s', self._entity_id)
                return

        sk = None
        for _sk, _conditions in mapping:
            if conditions in _conditions:
                sk = _sk
                break
        if not sk:
            if self._init_complete:
                _LOGGER.error('Unexpected current observation: %s',
                              raw_conditions)
            return

        if self._mode == "simple":
            illuminance = 10000 * sun_factor
        else:
            try:
                location, elevation = get_astral_location(self.hass)
                solar_elevation = location.solar_elevation(now, elevation)
            except TypeError:
                location = get_astral_location(self.hass)
                solar_elevation = location.solar_elevation(now)
            illuminance = _illumiance(solar_elevation)
        self._state = round(illuminance / sk)

    def _sun_factor(self, now):
        now_date = now.date()

        if self._sun_data and self._sun_data[0] == now_date:
            (sunrise_begin, sunrise_end,
             sunset_begin, sunset_end) = self._sun_data[1]
        else:
            sunrise = get_astral_event_date(self.hass, 'sunrise', now_date)
            sunset = get_astral_event_date(self.hass, 'sunset', now_date)
            sunrise_begin = sunrise - _20_MIN
            sunrise_end = sunrise + _40_MIN
            sunset_begin = sunset - _40_MIN
            sunset_end = sunset + _20_MIN
            self._sun_data = (
                now_date,
                (sunrise_begin, sunrise_end, sunset_begin, sunset_end))

        if sunrise_end < now < sunset_begin:
            # Daytime
            return 1
        if now < sunrise_begin or sunset_end < now:
            # Nighttime
            return 0
        if now <= sunrise_end:
            # Sunrise
            return (now-sunrise_begin).total_seconds() / (60*60)
        # Sunset
        return (sunset_end-now).total_seconds() / (60*60)
