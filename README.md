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
See [Installing and Updating](custom_updater.md) to use Custom Updater. The name of this `"element"` is `"sensor.illuminance"`.

Alternatively, place a copy of:

[`illuminance/__init__.py`](../custom_components/illuminance/__init__.py) at `<config>/custom_components/illuminance/__init__.py`  
[`illuminance/sensor.py`](../custom_components/illuminance/sensor.py) at `<config>/custom_components/illuminance/sensor.py`  
[`illuminance/manifest.json`](../custom_components/illuminance/manifest.json) at `<config>/custom_components/illuminance/manifest.json`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly. Rather, click on it, then on the page that comes up use the `Raw` button.

Then add the desired configuration. Here is an example of a typical configuration:
```yaml
sensor:
  - platform: illuminance
    entity_id: sensor.yr_symbol
```
### Home Assistant before 0.86
For manual installation, place a copy of:

[`illuminance/sensor.py`](../custom_components/illuminance/sensor.py) at `<config>/custom_components/sensor/illuminance.py`
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
## Release Notes
Date | Version | Notes
-|:-:|-
20180907 | [1.0.0](https://github.com/pnbruckner/homeassistant-config/blob/d767bcce0fdff0c9298dc7a010d27af88817eac2/custom_components/sensor/illuminance.py) | Initial support for Custom Updater.
20181028 | [2.0.0](https://github.com/pnbruckner/homeassistant-config/blob/e4fbbfe5ccc48cc08045226197c5c27767ec081e/custom_components/sensor/illuminance.py) | Add support for using Dark Sky or YR entity as source of weather conditions. For WU, no longer get sunrise/sunset data from the server, just use HA’s sun data.
20190111 | [2.0.1](https://github.com/pnbruckner/homeassistant-config/blob/be6879c5ff4c4ae67e9b082229a53fc133642d2f/custom_components/sensor/illuminance.py) | Adapt to change in Dark Sky Sensor in HA 0.85 release (see [PR #19492](https://github.com/home-assistant/home-assistant/pull/19492).)
20190307 | [2.0.2](https://github.com/pnbruckner/homeassistant-config/blob/3a5676b8108fe3aaaf6676019cb19b128e6dec07/custom_components/illuminance/sensor.py) | Adapt to change in Yr Sensor in HA 0.89 release (see [PR #21069](https://github.com/home-assistant/home-assistant/pull/21069).)
20190406 | [2.0.3](https://github.com/pnbruckner/homeassistant-config/blob/70f78675abdd27bafb46a20bebbb53718c8356bc/custom_components/illuminance/sensor.py) | Adapt to last pieces of Great Migration in HA 0.91 release.
20190419 | [2.0.4](https://github.com/pnbruckner/homeassistant-config/blob/4f638d1ac9abd12f7bc1e8080763b545fd2385fa/custom_components/illuminance/sensor.py) | Add manifest.json required by 0.92.
20190419 | [2.0.5](https://github.com/pnbruckner/homeassistant-config/blob/ee936e61fecd2a7f81ccacc86ff7a0c7dea8aabc/custom_components/illuminance) | ... and apparently custom_updater needs an `__init__.py` file, too.
