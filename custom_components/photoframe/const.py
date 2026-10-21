"""Constants for the photoframe integration."""

from datetime import timedelta

DOMAIN = "photoframe"

DEFAULT_PORT = 7777
SCAN_INTERVAL = timedelta(seconds=30)
REQUEST_TIMEOUT = 15

ALL_ALBUMS = "All albums"

IMAGE_SIZING_OPTIONS = ["blur", "zoom", "auto", "none"]
# Option keys must be valid translation keys, so the frame's "sensor+schedule"
# is "sensor_schedule" in HA.
POWERSAVE_OPTIONS = ["none", "sensor", "schedule", "sensor_schedule"]
OFFLINE_BEHAVIOR_OPTIONS = ["wait", "ignore"]
ROTATION_OPTIONS = ["0", "90", "180", "270"]
