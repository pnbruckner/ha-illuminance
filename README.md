# Illuminance Sensor
Estimates outdoor illuminance based on current weather conditions and time of day. At night the value is 10. From a little before sunrise to a little after the value is ramped up to whatever the current conditions indicate. The same happens around sunset, except the value is ramped down. Below is an example of what that might look like over a three day period.

<p align="center">
  <img src=images/illuminance_history.png>
</p>

The following sources of weather data are supported:

* [Dark Sky Sensor (icon)](https://www.home-assistant.io/components/sensor.darksky/)
* [Dark Sky Weather](https://www.home-assistant.io/components/weather.darksky/)
* Weather Underground
* [YR (symbol)](https://www.home-assistant.io/components/sensor.yr/)
## Installation
Follow either the HACS or manual installation instructions below.
Then add the desired configuration. Here is an example of a typical configuration:
```yaml
sensor:
  - platform: illuminance
    entity_id: sensor.yr_symbol
```
### HACS
See [HACS](https://github.com/custom-components/hacs), especially [Add custom repos](https://custom-components.github.io/hacs/#add-custom-repos).
### Manual
Alternatively, place a copy of:

[`__init__.py`](custom_components/illuminance/__init__.py) at `<config>/custom_components/illuminance/__init__.py`  
[`sensor.py`](custom_components/illuminance/sensor.py) at `<config>/custom_components/illuminance/sensor.py`  
[`manifest.json`](custom_components/illuminance/manifest.json) at `<config>/custom_components/illuminance/manifest.json`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly. Rather, click on it, then on the page that comes up use the `Raw` button.

## Configuration variables
- **api_key**: Weather Underground API key. Required when using WU.
- **entity_id**: Entity ID of Dark Sky or YR entity. See examples below. Required when using Dark Sky or YR.
- **name** (*Optional*): Name of the sensor. Default is `Illuminance`.
- **scan_interval** (*Optional*): Polling interval.  For non-WU configs only applies during ramp up period around sunrise and ramp down period around sunset. Minimum is 5 minutes. Default is 5 minutes.
- **query**: Weather Underground query. See https://www.wunderground.com/weather/api/d/docs?d=data/index. Required when using WU.
## Examples
### Dark Sky Sensor
```
sensor:
  - platform: darksky
    api_key: !secret ds_api_key
    monitored_conditions:
      - icon
  - platform: illuminance
    name: DSS Illuminance
    entity_id: sensor.dark_sky_icon
```
### Dark Sky Weather
```
weather:
  - platform: darksky
    api_key: !secret ds_api_key
sensor:
  - platform: illuminance
    name: DSW Illuminance
    entity_id: weather.dark_sky
```
### YR Sensor
```
sensor:
  - platform: yr
    monitored_conditions:
      - symbol
  - platform: illuminance
    name: YRS Illuminance
    entity_id: sensor.yr_symbol
```
### Weather Underground
```
sensor:
  - platform: illuminance
    name: WU Illuminance
    api_key: !secret wu_api_key
    query: !secret wu_query
    scan_interval:
      minutes: 30
```
## Caveats
Weather Underground no long provides free API keys. In fact, as of this writing they have notified that the REST API will be discontinued.
## Releases Before 2.1.0
See https://github.com/pnbruckner/homeassistant-config/blob/master/docs/illuminance.md.
