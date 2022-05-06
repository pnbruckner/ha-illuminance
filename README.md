# Illuminance Sensor
Estimates outdoor illuminance based on current weather conditions and time of day. At night the value is 10. From a little before sunrise to a little after the value is ramped up to whatever the current conditions indicate. The same happens around sunset, except the value is ramped down. Below is an example of what that might look like over a three day period.

<p align="center">
  <img src=images/illuminance_history.png>
</p>

The following sources of weather data are supported:

* [Dark Sky Sensor (icon)](https://www.home-assistant.io/components/sensor.darksky/)
* [Dark Sky Weather](https://www.home-assistant.io/components/weather.darksky/)
* Weather Underground
* YR (symbol) NOTE: Removed in HA 0.115
* [Meteorologisk institutt (Met.no)](https://www.home-assistant.io/integrations/met/)
* [AccuWeather](https://www.home-assistant.io/integrations/accuweather/)
* [ecobee](https://www.home-assistant.io/integrations/ecobee/)
* [OpenWeatherMap](https://www.home-assistant.io/integrations/openweathermap/)

Follow the installation instructions below.
Then add the desired configuration. Here is an example of a typical configuration:
```yaml
sensor:
  - platform: illuminance
    entity_id: weather.home
```
## Installation

### Manual
Place a copy of:

[`__init__.py`](custom_components/illuminance/__init__.py) at `<config>/custom_components/illuminance/__init__.py`  
[`sensor.py`](custom_components/illuminance/sensor.py) at `<config>/custom_components/illuminance/sensor.py`  
[`manifest.json`](custom_components/illuminance/manifest.json) at `<config>/custom_components/illuminance/manifest.json`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly. Rather, click on it, then on the page that comes up use the `Raw` button.

### With HACS
You can use [HACS](https://hacs.xyz/) to manage installation and updates by adding this repo as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) and then searching for and installing the "Illuminance" integration.

## Configuration variables
- **api_key**: Weather Underground API key. Required when using WU.
- **entity_id**: Entity ID of entity that indicates current weather conditions. See examples below. Required when not using WU.
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
### Met.no, AccuWeather or ecobee
```
sensor:
  - platform: illuminance
    name: Estimated Illuminance
    entity_id: weather.home
```
### OpenWeatherMap
```
sensor:
  - platform: illuminance
    name: Estimated Illuminance
    entity_id: weather.openweathermap
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
## Releases Before 2.1.0
See https://github.com/pnbruckner/homeassistant-config/blob/master/docs/illuminance.md.
