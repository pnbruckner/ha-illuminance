"""Constants for Illumiance integration."""
from datetime import timedelta

DOMAIN = "illuminance"
DEFAULT_NAME = "Illuminance"
MIN_SCAN_INTERVAL_MIN = 5
MIN_SCAN_INTERVAL = timedelta(minutes=MIN_SCAN_INTERVAL_MIN)
DEFAULT_SCAN_INTERVAL_MIN = 5
DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MIN)
DEFAULT_FALLBACK = 10

CONF_FALLBACK = "fallback"
