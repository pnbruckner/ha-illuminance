# <img src="https://brands.home-assistant.io/illuminance/icon.png" alt="Sun2 Sensor" width="50" height="50"/> Illuminance Sensor
Creates a `sensor` entity that estimates outdoor illuminance based on either sun elevation or time of day.
In either case, the value can be further adjusted based on current weather conditions or cloud coverage obtained from another, existing entity.


## Modes of operation
Three modes are available: normal, irradiance & simple.

### Normal/Irradiance modes - Sun elevation
These modes use an algorithm from the US Naval Observatory[^1] for estimating sun illuminance or irradiance based on the sun's elevation (aka altitude.) The maximum illuminance value is about 150,000 lx, and the maximum irradiance value is about 1,250 Watts/M².
Below is an example of what the illuminance might look like over a three day period.

<p align="center">
  <img src=images/normal.png>
</p>

[^1]: Janiczek, P. M., and DeYoung, J. A. _Computer Programs for Sun and Moon Illuminance With Contingent Tables and Diagrams_. Circular No. 171. Washington, D. C.: United States Naval Observatory, 1987 [Google Scholar](https://scholar.google.com/scholar_lookup?title=Computer%20programs%20for%20sun%20and%20moon%20illuminance%20with%20contingent%20tables%20and%20diagrams&author=P.%20M.%20Janiczek&author=J.%20A.%20Deyoung&publication_year=1987&book=Computer%20programs%20for%20sun%20and%20moon%20illuminance%20with%20contingent%20tables%20and%20diagrams)

### Simple mode - Time of day
At night the value is 10 lx. From a little before sunrise to a little after the value is ramped up to whatever the current conditions indicate. The same happens around sunset, except the value is ramped down. For historical reasons, the maximum value is 10,000 lx. Below is an example of what that might look like over a three day period.

<p align="center">
  <img src=images/simple.png>
</p>

## Supported weather sources
Any weather entity that uses the [standard list of conditions](https://www.home-assistant.io/integrations/weather/#condition-mapping), or that provides a cloud coverage percentage, should work with this integration.
The following sources of weather data are known to be supported:

Integration | Notes
-|-
[AccuWeather](https://www.home-assistant.io/integrations/accuweather/) | `weather`
[Buienradar Sensor](https://www.home-assistant.io/integrations/buienradar/#sensor) | Condition `sensor`
[ecobee](https://www.home-assistant.io/integrations/ecobee/) |
[Meteorologisk institutt (Met.no)](https://www.home-assistant.io/integrations/met/) | `weather`
[OpenWeatherMap](https://www.home-assistant.io/integrations/openweathermap/) | `weather`; cloud_coverage & condition `sensor`

## Installation

The integration software must first be installed as a custom component.
You can use HACS to manage the installation and provide update notifications.
Or you can manually install the software.

<details>
<summary>With HACS</summary>

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

1. Add this repo as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/):
   It should then appear as a new integration. Click on it. If necessary, search for "illuminance".
   ```text
   https://github.com/pnbruckner/ha-illuminance
   ```
   Or use this button:
  
   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pnbruckner&repository=ha-illuminance&category=integration)

1. Download the integration using the appropriate button.

</details>

<details>
<summary>Manual Installation</summary>

Place a copy of the files from [`custom_components/illuminance`](custom_components/illuminance)
in `<config>/custom_components/illuminance`,
where `<config>` is your Home Assistant configuration directory.

>__NOTE__: When downloading, make sure to use the `Raw` button from each file's page.

</details>

### Post Installation

After it has been downloaded you will need to restart Home Assistant.

### Versions

This custom integration supports HomeAssistant versions 2023.4.0 or newer.

## Services

### `illuminance.reload`

Reloads Illuminance from the YAML-configuration. Also adds `ILLUMINANCE` to the Developers Tools -> YAML page.

## Configuration variables

A list of configuration options for one or more sensors. Each sensor is defined by the following options.

> Note: This defines configuration via YAML. However, the same sensors can be added in the UI.

Key | Optional | Description
-|-|-
`unique_id` | no | Unique identifier for sensor. This allows any of the remaining options to be changed without looking like a new sensor. (Only required for YAML-based configuration.)
`entity_id` | yes | Entity ID of another entity that indicates current weather conditions or cloud coverage percentage
`fallback` | yes | Illuminance divisor to use when weather data is not available. Must be in the range of 1 (clear) through 10 (dark.) Default is 10 if `entity_id` is used, or 1 if not.
`mode` | yes | Mode of operation. Choices are `normal` (default) which uses sun elevation, `simple` which uses time of day and `irradiance` which is the same as `normal`, except the value is expressed as irradiance in Watts/M².
`name` | yes | Name of the sensor. Default is `Illuminance`.
`scan_interval` | yes | Update interval. Minimum is 30 seconds. Default is 5 minutes.

## Converting from `platform` configuration

In previous versions, configuration was done under `sensor`.
This is now deprecated and will generate a warning at startup.
It should be converted to the new `illuminance` format as described above.
Or simply remove it and add the sensor(s) via the UI.

Here is an example of the old format:

```yaml
sensor:
  - platform: illuminance
    entity_id: weather.home_forecast
    fallback: 5
    mode: normal
    name: Weather-Based Sun Illuminance
    scan_interval:
      minutes: 10
```

This is the equivalent configuration in the new format:

```yaml
illuminance:
  - unique_id: 1
    entity_id: weather.home_forecast
    fallback: 5
    mode: normal
    name: Weather-Based Sun Illuminance
    scan_interval:
      minutes: 10
```

## Releases Before 2.1.0
See https://github.com/pnbruckner/homeassistant-config/blob/master/docs/illuminance.md.
