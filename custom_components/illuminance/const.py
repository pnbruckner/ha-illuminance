"""Constants for Illumiance integration."""
from datetime import timedelta

DOMAIN = "illuminance"
DEFAULT_NAME = "Illuminance"
MIN_SCAN_INTERVAL_MIN = 0.5
MIN_SCAN_INTERVAL = timedelta(minutes=MIN_SCAN_INTERVAL_MIN)
DEFAULT_SCAN_INTERVAL_MIN = 5
DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MIN)
DEFAULT_FALLBACK = 10
# Lux per Watts/M²
LUX_PER_WPSM = 120

CONF_FALLBACK = "fallback"
#add precision / rounding toggle
CONF_PRECISION = "precision"
DEFAULT_PRECISION = 0
