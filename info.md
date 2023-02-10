# Illuminance Sensor

Creates a `sensor` entity that estimates outdoor illuminance based on either sun elevation or time of day.
In either case, the value is adjusted based on current weather conditions obtained from another, existing entity.
The weather data can be from any entity whose state is either a
[weather condition](https://www.home-assistant.io/integrations/weather/#condition-mapping)
or a cloud coverage percentage.

For now configuration is done strictly in YAML.
Created entities will appear on the Entities page in the UI.
There will be no entries on the Integrations page in the UI.
