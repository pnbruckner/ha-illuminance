# Illuminance Sensor
Estimates outdoor illuminance based on either sun elevation or time of day. In either case, the value is adjusted based on current weather conditions.

## Modes of operation
Two modes are available: normal & simple. The desired mode is selected via the [configuration](#configuration-variables).

### Normal mode - Sun elevation
This mode uses an algorithm from the US Naval Observatory[^1] for estimating sun illuminance based on the sun's elevation (aka altitude.) The maximum value is about 150,000 lx. Below is an example of what that might look like over a three day period.

<p align="center">
  <img src=images/normal.png>
</p>

[^1]: Janiczek, P. M., and DeYoung, J. A. _Computer Programs for Sun and Moon Illuminance With Contingent Tables and Diagrams_. Circular No. 171. Washington, D. C.: United States Naval Observatory, 1987 [Google Scholar](https://scholar.google.com/scholar_lookup?title=Computer%20programs%20for%20sun%20and%20moon%20illuminance%20with%20contingent%20tables%20and%20diagrams&author=P.%20M.%20Janiczek&author=J.%20A.%20Deyoung&publication_year=1987&book=Computer%20programs%20for%20sun%20and%20moon%20illuminance%20with%20contingent%20tables%20and%20diagrams)

### Simple mode - Time of day
At night the value is 10 lx. From a little before sunrise to a little after the value is ramped up to whatever the current conditions indicate. The same happens around sunset, except the value is ramped down. The maximum value is 10,000 lx. Below is an example of what that might look like over a three day period.

<p align="center">
  <img src=images/simple.png>
</p>

## Supported weather sources
The following sources of weather data are supported:

* [Dark Sky Sensor (icon)](https://www.home-assistant.io/components/sensor.darksky/)
* [Dark Sky Weather](https://www.home-assistant.io/components/weather.darksky/)
* [Meteorologisk institutt (Met.no)](https://www.home-assistant.io/integrations/met/)
* [AccuWeather](https://www.home-assistant.io/integrations/accuweather/)
* [ecobee](https://www.home-assistant.io/integrations/ecobee/)
* [OpenWeatherMap](https://www.home-assistant.io/integrations/openweathermap/)
* [Buienradar](https://www.home-assistant.io/integrations/buienradar/)

## Setup
Follow the installation instructions below.
Then add the desired configuration. Here is an example of a typical configuration:
```yaml
sensor:
  - platform: illuminance
    entity_id: weather.home
```

## Installation
### With HACS
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

You can use HACS to manage the installation and provide update notifications.

1. Add this repo as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/):

```text
https://github.com/pnbruckner/ha-illuminance
```

2. Install the integration using the appropriate button on the HACS Integrations page. Search for "illuminance".

### Manual
Place a copy of:

[`__init__.py`](custom_components/illuminance/__init__.py) at `<config>/custom_components/illuminance/__init__.py`  
[`sensor.py`](custom_components/illuminance/sensor.py) at `<config>/custom_components/illuminance/sensor.py`  
[`manifest.json`](custom_components/illuminance/manifest.json) at `<config>/custom_components/illuminance/manifest.json`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly. Rather, click on it, then on the page that comes up use the `Raw` button.

### Versions

This custom integration supports HomeAssistant versions 2021.12 or newer, using Python 3.9 or newer.

## Configuration variables
- **entity_id**: Entity ID of entity that indicates current weather conditions. See examples below.
- **mode** (*Optional*): Mode of operation. Choices are `normal` (default) which uses sun elevation, and `simple` which uses time of day.
- **name** (*Optional*): Name of the sensor. Default is `Illuminance`.
- **scan_interval** (*Optional*): Update interval. Minimum is 5 minutes. Default is 5 minutes.
- **fallback** (*Optional*): Illuminance divisor to use when weather data is not available. Must be in the range of 1 (sunny) through 10 (dark.) Default is 10.
## Examples
### Using Fallback Divisor
```yaml
sensor:
  - platform: illuminance
    entity_id: weather.home
    fallback: 5
```
### Dark Sky Sensor
```yaml
sensor:
  - platform: darksky
    api_key: !secret ds_api_key
    monitored_conditions:
      - icon
  - platform: illuminance
    entity_id: sensor.NAME
```
### Dark Sky Weather
```yaml
weather:
  - platform: darksky
    api_key: !secret ds_api_key
sensor:
  - platform: illuminance
    entity_id: weather.NAME
```
### Other Sensor Entities
```yaml
sensor:
  - platform: illuminance
    entity_id: sensor.NAME
```
### Other Weather Entities
```yaml
sensor:
  - platform: illuminance
    entity_id: weather.NAME
```
## Releases Before 2.1.0
See https://github.com/pnbruckner/homeassistant-config/blob/master/docs/illuminance.md.
