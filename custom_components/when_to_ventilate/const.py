"""Constants for When to Ventilate."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "when_to_ventilate"
PLATFORMS: Final = (Platform.SENSOR, Platform.BINARY_SENSOR)

CONF_REFERENCES: Final = "references"
CONF_ROOMS: Final = "rooms"
CONF_AREA_ID: Final = "area_id"
CONF_TEMPERATURE_ENTITY_ID: Final = "temperature_entity_id"
CONF_HUMIDITY_ENTITY_ID: Final = "humidity_entity_id"
CONF_REFERENCE_ID: Final = "reference_id"
CONF_MINIMUM_TEMPERATURE: Final = "minimum_temperature"
CONF_HYSTERESIS: Final = "hysteresis"
CONF_RELATIVE_HUMIDITY_ON: Final = "relative_humidity_on"
CONF_RELATIVE_HUMIDITY_OFF: Final = "relative_humidity_off"
CONF_ABSOLUTE_HUMIDITY_ON: Final = "absolute_humidity_on"
CONF_ABSOLUTE_HUMIDITY_OFF: Final = "absolute_humidity_off"
CONF_TEMPERATURE_PROTECTION_HYSTERESIS: Final = (
    "temperature_protection_hysteresis"
)

DEFAULT_MINIMUM_TEMPERATURE: Final = 18.0
MINIMUM_TEMPERATURE_MIN: Final = 5.0
MINIMUM_TEMPERATURE_MAX: Final = 25.0

DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS: Final = 0.5
DEFAULT_ABSOLUTE_HUMIDITY_ON: Final = 0.3
DEFAULT_ABSOLUTE_HUMIDITY_OFF: Final = 0.2
DEFAULT_RELATIVE_HUMIDITY_ON: Final = 60.0
DEFAULT_RELATIVE_HUMIDITY_OFF: Final = 55.0

ATTR_REFERENCE: Final = "reference"
ATTR_REFERENCE_AREA_ID: Final = "reference_area_id"
ATTR_REASON_CODE: Final = "reason_code"
ATTR_REASON_CODES: Final = "reason_codes"
ATTR_ABSOLUTE_HUMIDITY_INDOOR: Final = "absolute_humidity_indoor"
ATTR_ABSOLUTE_HUMIDITY_REFERENCE: Final = "absolute_humidity_reference"
ATTR_HUMIDITY_DIFFERENCE: Final = "humidity_difference"

ROOM_SUBENTRY_TYPE: Final = "room"
