"""Config and options flows for When to Ventilate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    AreaSelector,
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ABSOLUTE_HUMIDITY_OFF,
    CONF_ABSOLUTE_HUMIDITY_ON,
    CONF_AREA_ID,
    CONF_HUMIDITY_ENTITY_ID,
    CONF_HYSTERESIS,
    CONF_MINIMUM_TEMPERATURE,
    CONF_REFERENCE_ID,
    CONF_REFERENCES,
    CONF_RELATIVE_HUMIDITY_OFF,
    CONF_RELATIVE_HUMIDITY_ON,
    CONF_ROOMS,
    CONF_TEMPERATURE_ENTITY_ID,
    CONF_TEMPERATURE_PROTECTION_HYSTERESIS,
    DEFAULT_ABSOLUTE_HUMIDITY_OFF,
    DEFAULT_ABSOLUTE_HUMIDITY_ON,
    DEFAULT_MINIMUM_TEMPERATURE,
    DEFAULT_RELATIVE_HUMIDITY_OFF,
    DEFAULT_RELATIVE_HUMIDITY_ON,
    DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS,
    DOMAIN,
    MINIMUM_TEMPERATURE_MAX,
    MINIMUM_TEMPERATURE_MIN,
    ROOM_SUBENTRY_TYPE,
)


def _default_hysteresis() -> dict[str, float]:
    """Return the default ventilation thresholds."""
    return {
        CONF_RELATIVE_HUMIDITY_ON: DEFAULT_RELATIVE_HUMIDITY_ON,
        CONF_RELATIVE_HUMIDITY_OFF: DEFAULT_RELATIVE_HUMIDITY_OFF,
        CONF_ABSOLUTE_HUMIDITY_ON: DEFAULT_ABSOLUTE_HUMIDITY_ON,
        CONF_ABSOLUTE_HUMIDITY_OFF: DEFAULT_ABSOLUTE_HUMIDITY_OFF,
        CONF_TEMPERATURE_PROTECTION_HYSTERESIS: (
            DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS
        ),
    }


def _empty_options() -> dict[str, dict[str, Any]]:
    """Return a new empty options structure."""
    return {
        CONF_REFERENCES: {},
        CONF_ROOMS: {},
        CONF_HYSTERESIS: _default_hysteresis(),
    }


def _copy_options(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    """Copy persisted options before editing."""
    return {
        CONF_REFERENCES: {
            key: dict(value)
            for key, value in entry.options.get(CONF_REFERENCES, {}).items()
        },
        CONF_ROOMS: {
            key: dict(value) for key, value in entry.options.get(CONF_ROOMS, {}).items()
        },
        CONF_HYSTERESIS: {
            **_default_hysteresis(),
            **entry.options.get(CONF_HYSTERESIS, {}),
        },
    }


def _hysteresis_schema(
    defaults: Mapping[str, Any], *, include_temperature: bool = True
) -> dict[vol.Marker, Any]:
    """Build selectors for ventilation threshold values."""
    schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_RELATIVE_HUMIDITY_ON,
            default=defaults[CONF_RELATIVE_HUMIDITY_ON],
        ): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=100,
                step=1,
                unit_of_measurement="%",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_RELATIVE_HUMIDITY_OFF,
            default=defaults[CONF_RELATIVE_HUMIDITY_OFF],
        ): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=100,
                step=1,
                unit_of_measurement="%",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_ABSOLUTE_HUMIDITY_ON,
            default=defaults[CONF_ABSOLUTE_HUMIDITY_ON],
        ): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=20,
                step=0.05,
                unit_of_measurement="g/m³",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_ABSOLUTE_HUMIDITY_OFF,
            default=defaults[CONF_ABSOLUTE_HUMIDITY_OFF],
        ): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=20,
                step=0.05,
                unit_of_measurement="g/m³",
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
    if include_temperature:
        schema[
            vol.Required(
                CONF_TEMPERATURE_PROTECTION_HYSTERESIS,
                default=defaults[CONF_TEMPERATURE_PROTECTION_HYSTERESIS],
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=5,
                step=0.1,
                unit_of_measurement="°C",
                mode=NumberSelectorMode.BOX,
            )
        )
    return schema


def _hysteresis_errors(values: Mapping[str, Any]) -> dict[str, str]:
    """Validate hysteresis on/off ordering."""
    errors: dict[str, str] = {}
    if values[CONF_RELATIVE_HUMIDITY_OFF] >= values[CONF_RELATIVE_HUMIDITY_ON]:
        errors[CONF_RELATIVE_HUMIDITY_OFF] = "invalid_hysteresis"
    if values[CONF_ABSOLUTE_HUMIDITY_OFF] >= values[CONF_ABSOLUTE_HUMIDITY_ON]:
        errors[CONF_ABSOLUTE_HUMIDITY_OFF] = "invalid_hysteresis"
    return errors


def _area_name(hass: HomeAssistant, area_id: str) -> str:
    """Return an area name with a stable fallback."""
    area = ar.async_get(hass).async_get_area(area_id)
    return area.name if area else area_id


def _entity_device_class(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the effective device class for an entity."""
    registry_entry = er.async_get(hass).async_get(entity_id)
    if registry_entry and registry_entry.original_device_class:
        return registry_entry.original_device_class
    state = hass.states.get(entity_id)
    return state.attributes.get(ATTR_DEVICE_CLASS) if state else None


def _entity_area_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Resolve an entity's direct or inherited device area."""
    entity_entry = er.async_get(hass).async_get(entity_id)
    if entity_entry is None:
        return None
    if entity_entry.area_id:
        return entity_entry.area_id
    if entity_entry.device_id:
        device = dr.async_get(hass).async_get(entity_entry.device_id)
        if device:
            return device.area_id
    return None


def _matching_entities(
    hass: HomeAssistant,
    area_id: str,
    device_class: SensorDeviceClass,
    current: str | None = None,
) -> list[str]:
    """Return appropriate sensors, preferring a strict area subset."""
    entity_registry = er.async_get(hass)
    matching = sorted(
        entry.entity_id
        for entry in entity_registry.entities.values()
        if entry.domain == "sensor"
        and not entry.disabled
        and _entity_device_class(hass, entry.entity_id) == device_class
    )
    local = [
        entity_id
        for entity_id in matching
        if _entity_area_id(hass, entity_id) == area_id
    ]
    result = local or matching
    if current and current in matching and current not in result:
        result.append(current)
    return sorted(result)


def _entity_selector(
    hass: HomeAssistant,
    area_id: str,
    device_class: SensorDeviceClass,
    current: str | None = None,
) -> EntitySelector:
    """Build a strongly filtered entity selector."""
    return EntitySelector(
        EntitySelectorConfig(
            filter={"domain": "sensor", "device_class": device_class},
            include_entities=_matching_entities(hass, area_id, device_class, current),
        )
    )


def _validate_sensor(
    hass: HomeAssistant,
    entity_id: str,
    device_class: SensorDeviceClass,
) -> bool:
    """Validate selector input server-side."""
    return (
        entity_id.startswith("sensor.")
        and _entity_device_class(hass, entity_id) == device_class
    )


def _reference_selector(
    hass: HomeAssistant, references: Mapping[str, Any]
) -> SelectSelector:
    """Build a selector containing only configured references."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": reference_id, "label": _area_name(hass, reference_id)}
                for reference_id in sorted(
                    references, key=lambda item: _area_name(hass, item).casefold()
                )
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _configured_area_selector(
    hass: HomeAssistant, values: Mapping[str, Any]
) -> SelectSelector:
    """Build a labeled selector for configured areas."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": area_id, "label": _area_name(hass, area_id)}
                for area_id in sorted(
                    values, key=lambda item: _area_name(hass, item).casefold()
                )
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


class WhenToVentilateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._area_id: str | None = None
        self._room_sensors: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer a minimal setup or an optional default reference."""
        return self.async_show_menu(
            step_id="user", menu_options=("default_reference", "finish")
        )

    async def async_step_room_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the room's temperature and humidity sensors."""
        assert self._area_id is not None
        if user_input is not None:
            self._room_sensors = dict(user_input)
            return await self.async_step_reference_details()
        return self.async_show_form(
            step_id="room_sensors",
            data_schema=self._sensor_schema(self._area_id),
            description_placeholders={
                "area_name": _area_name(self.hass, self._area_id)
            },
        )

    async def async_step_reference_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the reference climate and threshold."""
        assert self._area_id is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_AREA_ID] == self._area_id:
                errors[CONF_AREA_ID] = "reference_must_differ"
            if not _validate_sensor(
                self.hass,
                user_input["reference_temperature_entity_id"],
                SensorDeviceClass.TEMPERATURE,
            ):
                errors["reference_temperature_entity_id"] = "invalid_temperature_sensor"
            if not _validate_sensor(
                self.hass,
                user_input["reference_humidity_entity_id"],
                SensorDeviceClass.HUMIDITY,
            ):
                errors["reference_humidity_entity_id"] = "invalid_humidity_sensor"
            if not errors:
                reference_id = user_input[CONF_AREA_ID]
                room = {
                    CONF_AREA_ID: self._area_id,
                    CONF_TEMPERATURE_ENTITY_ID: self._room_sensors[
                        CONF_TEMPERATURE_ENTITY_ID
                    ],
                    CONF_HUMIDITY_ENTITY_ID: self._room_sensors[
                        CONF_HUMIDITY_ENTITY_ID
                    ],
                    CONF_REFERENCE_ID: reference_id,
                    CONF_MINIMUM_TEMPERATURE: float(
                        user_input[CONF_MINIMUM_TEMPERATURE]
                    ),
                }
                reference = {
                    CONF_AREA_ID: reference_id,
                    CONF_TEMPERATURE_ENTITY_ID: user_input[
                        "reference_temperature_entity_id"
                    ],
                    CONF_HUMIDITY_ENTITY_ID: user_input["reference_humidity_entity_id"],
                }
                options = _empty_options()
                options[CONF_REFERENCES][reference_id] = reference
                options[CONF_ROOMS][self._area_id] = room
                return self.async_create_entry(
                    title=f"When to Ventilate {_area_name(self.hass, self._area_id)}",
                    data={},
                    options=options,
                )
        schema = {
            vol.Required(CONF_AREA_ID): AreaSelector(),
            vol.Required("reference_temperature_entity_id"): _entity_selector(
                self.hass, "", SensorDeviceClass.TEMPERATURE
            ),
            vol.Required("reference_humidity_entity_id"): _entity_selector(
                self.hass, "", SensorDeviceClass.HUMIDITY
            ),
            vol.Required(
                CONF_MINIMUM_TEMPERATURE, default=DEFAULT_MINIMUM_TEMPERATURE
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MINIMUM_TEMPERATURE_MIN,
                    max=MINIMUM_TEMPERATURE_MAX,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
        return self.async_show_form(
            step_id="reference_details", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_default_reference(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the area used by the initial reference."""
        errors: dict[str, str] = {}
        if user_input is not None:
            area_id = user_input[CONF_AREA_ID]
            if ar.async_get(self.hass).async_get_area(area_id) is None:
                errors[CONF_AREA_ID] = "area_not_found"
            else:
                self._area_id = area_id
                return await self.async_step_reference_sensors()

        return self.async_show_form(
            step_id="default_reference",
            data_schema=vol.Schema({vol.Required(CONF_AREA_ID): AreaSelector()}),
            errors=errors,
        )

    async def async_step_reference_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the initial reference sensors."""
        assert self._area_id is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._sensor_errors(user_input)
            if not errors:
                reference = {
                    CONF_AREA_ID: self._area_id,
                    CONF_TEMPERATURE_ENTITY_ID: user_input[CONF_TEMPERATURE_ENTITY_ID],
                    CONF_HUMIDITY_ENTITY_ID: user_input[CONF_HUMIDITY_ENTITY_ID],
                }
                options = _empty_options()
                options[CONF_REFERENCES][self._area_id] = reference
                return self.async_create_entry(
                    title="When to Ventilate", data={}, options=options
                )

        return self.async_show_form(
            step_id="reference_sensors",
            data_schema=self._sensor_schema(self._area_id),
            errors=errors,
            description_placeholders={
                "area_name": _area_name(self.hass, self._area_id)
            },
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a minimal entry without a reference."""
        return self.async_create_entry(
            title="When to Ventilate", data={}, options=_empty_options()
        )

    def _sensor_schema(
        self,
        area_id: str,
        temperature_default: str | None = None,
        humidity_default: str | None = None,
    ) -> vol.Schema:
        """Build a sensor schema for one area."""
        temperature_key: vol.Marker = vol.Required(CONF_TEMPERATURE_ENTITY_ID)
        humidity_key: vol.Marker = vol.Required(CONF_HUMIDITY_ENTITY_ID)
        if temperature_default:
            temperature_key = vol.Required(
                CONF_TEMPERATURE_ENTITY_ID, default=temperature_default
            )
        if humidity_default:
            humidity_key = vol.Required(
                CONF_HUMIDITY_ENTITY_ID, default=humidity_default
            )
        return vol.Schema(
            {
                temperature_key: _entity_selector(
                    self.hass,
                    area_id,
                    SensorDeviceClass.TEMPERATURE,
                    temperature_default,
                ),
                humidity_key: _entity_selector(
                    self.hass,
                    area_id,
                    SensorDeviceClass.HUMIDITY,
                    humidity_default,
                ),
            }
        )

    def _sensor_errors(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        """Validate temperature and humidity entities."""
        errors: dict[str, str] = {}
        if not _validate_sensor(
            self.hass,
            user_input[CONF_TEMPERATURE_ENTITY_ID],
            SensorDeviceClass.TEMPERATURE,
        ):
            errors[CONF_TEMPERATURE_ENTITY_ID] = "invalid_temperature_sensor"
        if not _validate_sensor(
            self.hass,
            user_input[CONF_HUMIDITY_ENTITY_ID],
            SensorDeviceClass.HUMIDITY,
        ):
            errors[CONF_HUMIDITY_ENTITY_ID] = "invalid_humidity_sensor"
        return errors

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return WhenToVentilateOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the room flow offered by the hub integration."""
        return {ROOM_SUBENTRY_TYPE: RoomSubentryFlowHandler}


class WhenToVentilateOptionsFlow(OptionsFlow):
    """Manage references and room assignments."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._options: dict[str, dict[str, Any]] = {}
        self._area_id: str | None = None
        self._room_values: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show available configuration tasks."""
        self._options = _copy_options(self.config_entry)
        return self.async_show_menu(
            step_id="init",
            menu_options=(
                "configure_hysteresis",
                "manage_reference",
                "remove_reference",
            ),
            description_placeholders={
                "reference_count": str(len(self._options[CONF_REFERENCES])),
            },
        )

    async def async_step_configure_hysteresis(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the global ventilation thresholds."""
        defaults = self._options[CONF_HYSTERESIS]
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _hysteresis_errors(user_input)
            if not errors:
                self._options[CONF_HYSTERESIS] = {
                    key: float(user_input[key]) for key in defaults
                }
                return self.async_create_entry(data=self._options)
        return self.async_show_form(
            step_id="configure_hysteresis",
            data_schema=vol.Schema(_hysteresis_schema(defaults)),
            errors=errors,
        )

    async def async_step_manage_reference(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a reference area to add or edit."""
        if user_input is not None:
            self._area_id = user_input[CONF_AREA_ID]
            return await self.async_step_reference_details()
        return self.async_show_form(
            step_id="manage_reference",
            data_schema=vol.Schema({vol.Required(CONF_AREA_ID): AreaSelector()}),
        )

    async def async_step_reference_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set sensors for a reference."""
        assert self._area_id is not None
        current = self._options[CONF_REFERENCES].get(self._area_id, {})
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._sensor_errors(user_input)
            if not errors:
                self._options[CONF_REFERENCES][self._area_id] = {
                    CONF_AREA_ID: self._area_id,
                    CONF_TEMPERATURE_ENTITY_ID: user_input[CONF_TEMPERATURE_ENTITY_ID],
                    CONF_HUMIDITY_ENTITY_ID: user_input[CONF_HUMIDITY_ENTITY_ID],
                }
                return self.async_create_entry(data=self._options)

        return self.async_show_form(
            step_id="reference_details",
            data_schema=self._sensor_schema(
                self._area_id,
                current.get(CONF_TEMPERATURE_ENTITY_ID),
                current.get(CONF_HUMIDITY_ENTITY_ID),
            ),
            errors=errors,
            description_placeholders={
                "area_name": _area_name(self.hass, self._area_id)
            },
        )

    async def async_step_remove_reference(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove an unused reference."""
        references = self._options[CONF_REFERENCES]
        if not references:
            return self.async_abort(reason="no_references")
        errors: dict[str, str] = {}
        if user_input is not None:
            reference_id = user_input[CONF_REFERENCE_ID]
            if any(
                subentry.data.get(CONF_REFERENCE_ID) == reference_id
                for subentry in self.config_entry.subentries.values()
            ):
                errors[CONF_REFERENCE_ID] = "reference_in_use"
            else:
                references.pop(reference_id, None)
                return self.async_create_entry(data=self._options)
        return self.async_show_form(
            step_id="remove_reference",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REFERENCE_ID): _reference_selector(
                        self.hass, references
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_configure_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose an area to configure as a room."""
        if not self._options[CONF_REFERENCES]:
            return self.async_abort(reason="no_references")
        if user_input is not None:
            self._area_id = user_input[CONF_AREA_ID]
            return await self.async_step_room_details()
        return self.async_show_form(
            step_id="configure_room",
            data_schema=vol.Schema({vol.Required(CONF_AREA_ID): AreaSelector()}),
        )

    async def async_step_room_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set the two sensors, reference, and minimum temperature."""
        assert self._area_id is not None
        current = self._options[CONF_ROOMS].get(self._area_id, {})
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._sensor_errors(user_input)
            if user_input[CONF_REFERENCE_ID] not in self._options[CONF_REFERENCES]:
                errors[CONF_REFERENCE_ID] = "reference_not_found"
            if not errors:
                room = {
                    CONF_AREA_ID: self._area_id,
                    CONF_TEMPERATURE_ENTITY_ID: user_input[CONF_TEMPERATURE_ENTITY_ID],
                    CONF_HUMIDITY_ENTITY_ID: user_input[CONF_HUMIDITY_ENTITY_ID],
                    CONF_REFERENCE_ID: user_input[CONF_REFERENCE_ID],
                    CONF_MINIMUM_TEMPERATURE: float(
                        user_input[CONF_MINIMUM_TEMPERATURE]
                    ),
                }
                if user_input.get("use_custom_hysteresis"):
                    self._room_values = room
                    return await self.async_step_room_hysteresis()
                self._options[CONF_ROOMS][self._area_id] = room
                return self.async_create_entry(data=self._options)

        area = ar.async_get(self.hass).async_get_area(self._area_id)
        temperature_default = current.get(CONF_TEMPERATURE_ENTITY_ID) or (
            area.temperature_entity_id if area else None
        )
        humidity_default = current.get(CONF_HUMIDITY_ENTITY_ID) or (
            area.humidity_entity_id if area else None
        )
        schema = dict(
            self._sensor_schema(
                self._area_id, temperature_default, humidity_default
            ).schema
        )
        schema[
            vol.Required(
                CONF_REFERENCE_ID,
                default=current.get(CONF_REFERENCE_ID)
                or next(iter(self._options[CONF_REFERENCES])),
            )
        ] = _reference_selector(self.hass, self._options[CONF_REFERENCES])
        schema[
            vol.Required(
                CONF_MINIMUM_TEMPERATURE,
                default=current.get(
                    CONF_MINIMUM_TEMPERATURE, DEFAULT_MINIMUM_TEMPERATURE
                ),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=MINIMUM_TEMPERATURE_MIN,
                max=MINIMUM_TEMPERATURE_MAX,
                step=0.5,
                unit_of_measurement="°C",
                mode=NumberSelectorMode.BOX,
            )
        )
        schema[
            vol.Required(
                "use_custom_hysteresis", default=bool(current.get(CONF_HYSTERESIS))
            )
        ] = BooleanSelector()
        return self.async_show_form(
            step_id="room_details",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "area_name": _area_name(self.hass, self._area_id),
                "global_relative_humidity_on": str(
                    self._options[CONF_HYSTERESIS][CONF_RELATIVE_HUMIDITY_ON]
                ),
                "global_relative_humidity_off": str(
                    self._options[CONF_HYSTERESIS][CONF_RELATIVE_HUMIDITY_OFF]
                ),
                "global_absolute_humidity_on": str(
                    self._options[CONF_HYSTERESIS][CONF_ABSOLUTE_HUMIDITY_ON]
                ),
                "global_absolute_humidity_off": str(
                    self._options[CONF_HYSTERESIS][CONF_ABSOLUTE_HUMIDITY_OFF]
                ),
            },
        )

    async def async_step_room_hysteresis(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure optional room-specific humidity thresholds."""
        current = self._options[CONF_ROOMS].get(self._area_id or "", {})
        custom_hysteresis = current.get(CONF_HYSTERESIS, {})
        defaults = {
            **self._options[CONF_HYSTERESIS],
            **custom_hysteresis,
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _hysteresis_errors(user_input)
            if not errors:
                self._room_values[CONF_HYSTERESIS] = {
                    key: float(user_input[key])
                    for key in (
                        CONF_RELATIVE_HUMIDITY_ON,
                        CONF_RELATIVE_HUMIDITY_OFF,
                        CONF_ABSOLUTE_HUMIDITY_ON,
                        CONF_ABSOLUTE_HUMIDITY_OFF,
                    )
                }
                self._options[CONF_ROOMS][self._area_id or ""] = self._room_values
                return self.async_create_entry(data=self._options)
        return self.async_show_form(
            step_id="room_hysteresis",
            data_schema=vol.Schema(
                _hysteresis_schema(defaults, include_temperature=False)
            ),
            errors=errors,
            description_placeholders={
                "area_name": _area_name(self.hass, self._area_id or ""),
            },
        )

    async def async_step_disable_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Disable a room by removing its sensor assignment."""
        rooms = self._options[CONF_ROOMS]
        if not rooms:
            return self.async_abort(reason="no_rooms")
        if user_input is not None:
            rooms.pop(user_input[CONF_AREA_ID], None)
            return self.async_create_entry(data=self._options)
        return self.async_show_form(
            step_id="disable_room",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AREA_ID): _configured_area_selector(
                        self.hass, rooms
                    )
                }
            ),
        )

    def _sensor_schema(
        self,
        area_id: str,
        temperature_default: str | None = None,
        humidity_default: str | None = None,
    ) -> vol.Schema:
        """Build a sensor schema for one area."""
        return WhenToVentilateConfigFlow._sensor_schema(
            self, area_id, temperature_default, humidity_default
        )

    def _sensor_errors(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        """Validate sensor input."""
        return WhenToVentilateConfigFlow._sensor_errors(self, user_input)


class RoomSubentryFlowHandler(ConfigSubentryFlow):
    """Configure one Home Assistant area as a ventilation room."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._area_id: str | None = None
        self._room_values: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select the area to configure."""
        errors: dict[str, str] = {}
        if user_input is not None:
            area_id = user_input[CONF_AREA_ID]
            if ar.async_get(self.hass).async_get_area(area_id) is None:
                errors[CONF_AREA_ID] = "area_not_found"
            elif any(
                subentry.data.get(CONF_AREA_ID) == area_id
                for subentry in self._get_entry().subentries.values()
                if subentry.subentry_type == ROOM_SUBENTRY_TYPE
                and subentry.subentry_id != self.context.get("subentry_id")
            ):
                errors[CONF_AREA_ID] = "area_already_configured"
            else:
                self._area_id = area_id
                return await self.async_step_details()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_AREA_ID): AreaSelector()}),
            errors=errors,
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure sensors and reference for the selected area."""
        assert self._area_id is not None
        entry = self._get_entry()
        references = entry.options.get(CONF_REFERENCES, {})
        if not references:
            return self.async_abort(reason="no_references")
        current = (
            self._get_reconfigure_subentry().data
            if self.context.get("subentry_id")
            else {}
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = WhenToVentilateConfigFlow._sensor_errors(self, user_input)
            if user_input[CONF_REFERENCE_ID] not in references:
                errors[CONF_REFERENCE_ID] = "reference_not_found"
            if not errors:
                data = {
                    CONF_AREA_ID: self._area_id,
                    CONF_TEMPERATURE_ENTITY_ID: user_input[CONF_TEMPERATURE_ENTITY_ID],
                    CONF_HUMIDITY_ENTITY_ID: user_input[CONF_HUMIDITY_ENTITY_ID],
                    CONF_REFERENCE_ID: user_input[CONF_REFERENCE_ID],
                    CONF_MINIMUM_TEMPERATURE: float(
                        user_input[CONF_MINIMUM_TEMPERATURE]
                    ),
                }
                if user_input.get("use_custom_hysteresis"):
                    self._room_values = data
                    return await self.async_step_hysteresis()
                if self.context.get("subentry_id"):
                    subentry = self._get_reconfigure_subentry()
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                    return self.async_update_and_abort(
                        entry,
                        subentry,
                        title=_area_name(self.hass, self._area_id),
                        data=data,
                    )
                return self.async_create_entry(
                    title=_area_name(self.hass, self._area_id),
                    data=data,
                    unique_id=self._area_id,
                )

        area = ar.async_get(self.hass).async_get_area(self._area_id)
        temperature_default = current.get(CONF_TEMPERATURE_ENTITY_ID) or (
            area.temperature_entity_id if area else None
        )
        humidity_default = current.get(CONF_HUMIDITY_ENTITY_ID) or (
            area.humidity_entity_id if area else None
        )
        schema = dict(
            WhenToVentilateConfigFlow._sensor_schema(
                self, self._area_id, temperature_default, humidity_default
            ).schema
        )
        schema[
            vol.Required(
                CONF_REFERENCE_ID,
                default=current.get(CONF_REFERENCE_ID) or next(iter(references)),
            )
        ] = _reference_selector(self.hass, references)
        schema[
            vol.Required(
                CONF_MINIMUM_TEMPERATURE,
                default=current.get(
                    CONF_MINIMUM_TEMPERATURE, DEFAULT_MINIMUM_TEMPERATURE
                ),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=MINIMUM_TEMPERATURE_MIN,
                max=MINIMUM_TEMPERATURE_MAX,
                step=0.5,
                unit_of_measurement="°C",
                mode=NumberSelectorMode.BOX,
            )
        )
        global_hysteresis = {
            **_default_hysteresis(),
            **entry.options.get(CONF_HYSTERESIS, {}),
        }
        schema[
            vol.Required(
                "use_custom_hysteresis", default=bool(current.get(CONF_HYSTERESIS))
            )
        ] = BooleanSelector()
        return self.async_show_form(
            step_id="details",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "area_name": _area_name(self.hass, self._area_id),
                "global_relative_humidity_on": str(
                    global_hysteresis[CONF_RELATIVE_HUMIDITY_ON]
                ),
                "global_relative_humidity_off": str(
                    global_hysteresis[CONF_RELATIVE_HUMIDITY_OFF]
                ),
                "global_absolute_humidity_on": str(
                    global_hysteresis[CONF_ABSOLUTE_HUMIDITY_ON]
                ),
                "global_absolute_humidity_off": str(
                    global_hysteresis[CONF_ABSOLUTE_HUMIDITY_OFF]
                ),
            },
        )

    async def async_step_hysteresis(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure optional room-specific humidity thresholds."""
        entry = self._get_entry()
        current = (
            self._get_reconfigure_subentry().data
            if self.context.get("subentry_id")
            else {}
        )
        global_hysteresis = {
            **_default_hysteresis(),
            **entry.options.get(CONF_HYSTERESIS, {}),
        }
        defaults = {
            **global_hysteresis,
            **current.get(CONF_HYSTERESIS, {}),
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _hysteresis_errors(user_input)
            if not errors:
                self._room_values[CONF_HYSTERESIS] = {
                    key: float(user_input[key])
                    for key in (
                        CONF_RELATIVE_HUMIDITY_ON,
                        CONF_RELATIVE_HUMIDITY_OFF,
                        CONF_ABSOLUTE_HUMIDITY_ON,
                        CONF_ABSOLUTE_HUMIDITY_OFF,
                    )
                }
                if self.context.get("subentry_id"):
                    subentry = self._get_reconfigure_subentry()
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                    return self.async_update_and_abort(
                        entry,
                        subentry,
                        title=_area_name(self.hass, self._area_id or ""),
                        data=self._room_values,
                    )
                return self.async_create_entry(
                    title=_area_name(self.hass, self._area_id or ""),
                    data=self._room_values,
                    unique_id=self._area_id,
                )
        return self.async_show_form(
            step_id="hysteresis",
            data_schema=vol.Schema(
                _hysteresis_schema(defaults, include_temperature=False)
            ),
            errors=errors,
            description_placeholders={
                "area_name": _area_name(self.hass, self._area_id or ""),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing room subentry."""
        subentry = self._get_reconfigure_subentry()
        self._area_id = str(subentry.data[CONF_AREA_ID])
        return await self.async_step_details(user_input)
