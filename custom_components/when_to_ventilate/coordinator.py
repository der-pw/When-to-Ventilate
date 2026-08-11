"""Push coordinator for When to Ventilate."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.unit_conversion import TemperatureConverter

from .calculations import ReasonCode, absolute_humidity, dew_point, ventilation_decision
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
    CONF_TEMPERATURE_PROTECTION_HYSTERESIS,
    DEFAULT_ABSOLUTE_HUMIDITY_OFF,
    DEFAULT_ABSOLUTE_HUMIDITY_ON,
    DEFAULT_RELATIVE_HUMIDITY_OFF,
    DEFAULT_RELATIVE_HUMIDITY_ON,
    DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS,
    ROOM_SUBENTRY_TYPE,
    CONF_TEMPERATURE_ENTITY_ID,
    DOMAIN,
)
from .models import (
    HysteresisConfig,
    IntegrationData,
    ReferenceConfig,
    RoomConfig,
    RoomResult,
)

_LOGGER = logging.getLogger(__name__)


class WhenToVentilateCoordinator(DataUpdateCoordinator[IntegrationData]):
    """Coordinate calculations from Home Assistant state changes."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
            always_update=False,
        )
        self._entry = entry
        self._previous_recommendations: dict[str, bool] = {}

    @property
    def references(self) -> Mapping[str, ReferenceConfig]:
        """Return configured references."""
        return self._entry.options.get(CONF_REFERENCES, {})

    @property
    def rooms(self) -> Mapping[str, RoomConfig]:
        """Return configured rooms."""
        subentry_rooms = {
            str(subentry.data[CONF_AREA_ID]): dict(subentry.data)
            for subentry in self._entry.subentries.values()
            if subentry.subentry_type == ROOM_SUBENTRY_TYPE
            and CONF_AREA_ID in subentry.data
        }
        if subentry_rooms:
            return subentry_rooms
        return self._entry.options.get(CONF_ROOMS, {})

    def room_subentry_id(self, area_id: str) -> str | None:
        """Return the config subentry owning an area, if any."""
        for subentry in self._entry.subentries.values():
            if (
                subentry.subentry_type == ROOM_SUBENTRY_TYPE
                and subentry.data.get(CONF_AREA_ID) == area_id
            ):
                return subentry.subentry_id
        return None

    @property
    def hysteresis(self) -> HysteresisConfig:
        """Return the global threshold defaults with safe fallbacks."""
        configured = self._entry.options.get(CONF_HYSTERESIS, {})
        return {
            CONF_RELATIVE_HUMIDITY_ON: float(
                configured.get(
                    CONF_RELATIVE_HUMIDITY_ON, DEFAULT_RELATIVE_HUMIDITY_ON
                )
            ),
            CONF_RELATIVE_HUMIDITY_OFF: float(
                configured.get(
                    CONF_RELATIVE_HUMIDITY_OFF, DEFAULT_RELATIVE_HUMIDITY_OFF
                )
            ),
            CONF_ABSOLUTE_HUMIDITY_ON: float(
                configured.get(
                    CONF_ABSOLUTE_HUMIDITY_ON, DEFAULT_ABSOLUTE_HUMIDITY_ON
                )
            ),
            CONF_ABSOLUTE_HUMIDITY_OFF: float(
                configured.get(
                    CONF_ABSOLUTE_HUMIDITY_OFF, DEFAULT_ABSOLUTE_HUMIDITY_OFF
                )
            ),
            CONF_TEMPERATURE_PROTECTION_HYSTERESIS: float(
                configured.get(
                    CONF_TEMPERATURE_PROTECTION_HYSTERESIS,
                    DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS,
                )
            ),
        }

    def room_hysteresis(self, room: RoomConfig) -> HysteresisConfig:
        """Return global thresholds merged with this room's overrides."""
        values = self.hysteresis
        values.update(room.get(CONF_HYSTERESIS, {}))
        return values

    @property
    def tracked_entity_ids(self) -> set[str]:
        """Return every unique input entity."""
        entity_ids: set[str] = set()
        for config in (*self.references.values(), *self.rooms.values()):
            entity_ids.add(config[CONF_TEMPERATURE_ENTITY_ID])
            entity_ids.add(config[CONF_HUMIDITY_ENTITY_ID])
        return entity_ids

    def reference_metrics(
        self, reference_id: str
    ) -> tuple[float | None, float | None]:
        """Return absolute humidity and dew point for a reference area."""
        reference = self.references.get(reference_id)
        if reference is None:
            return None, None
        temperature = self._temperature_celsius(reference[CONF_TEMPERATURE_ENTITY_ID])
        humidity = self._numeric_state(reference[CONF_HUMIDITY_ENTITY_ID])
        return absolute_humidity(temperature, humidity), dew_point(temperature, humidity)

    async def async_start(self) -> None:
        """Perform initial calculation and register one indexed state listener."""
        await self.async_config_entry_first_refresh()
        if self.tracked_entity_ids:
            self._entry.async_on_unload(
                async_track_state_change_event(
                    self.hass,
                    sorted(self.tracked_entity_ids),
                    self._async_input_changed,
                )
            )

    @callback
    def _async_input_changed(self, event: Event[EventStateChangedData]) -> None:
        """Recalculate all affected data after an input state change."""
        self.async_set_updated_data(self._calculate())

    @callback
    def async_restore_recommendation(self, area_id: str, value: bool) -> None:
        """Seed hysteresis from a restored binary-sensor state."""
        self._previous_recommendations[area_id] = value
        self.async_set_updated_data(self._calculate())

    async def _async_update_data(self) -> IntegrationData:
        """Read the state machine without polling external resources."""
        return self._calculate()

    @callback
    def _calculate(self) -> IntegrationData:
        """Calculate every room independently."""
        area_registry = ar.async_get(self.hass)
        results: dict[str, RoomResult] = {}

        for area_id, room in self.rooms.items():
            reference_id = room.get(CONF_REFERENCE_ID, "")
            reference = self.references.get(reference_id)
            area = area_registry.async_get_area(area_id)
            reference_area = (
                area_registry.async_get_area(reference_id) if reference_id else None
            )
            area_name = area.name if area else area_id
            reference_name = reference_area.name if reference_area else reference_id

            if reference is None:
                results[area_id] = self._unavailable_result(
                    area_id, area_name, reference_id, reference_name
                )
                continue

            indoor_temperature = self._temperature_celsius(
                room[CONF_TEMPERATURE_ENTITY_ID]
            )
            indoor_humidity = self._numeric_state(room[CONF_HUMIDITY_ENTITY_ID])
            reference_temperature = self._temperature_celsius(
                reference[CONF_TEMPERATURE_ENTITY_ID]
            )
            reference_humidity = self._numeric_state(reference[CONF_HUMIDITY_ENTITY_ID])

            indoor_absolute = absolute_humidity(indoor_temperature, indoor_humidity)
            indoor_dew_point = dew_point(indoor_temperature, indoor_humidity)
            reference_absolute = absolute_humidity(
                reference_temperature, reference_humidity
            )
            difference = (
                indoor_absolute - reference_absolute
                if indoor_absolute is not None and reference_absolute is not None
                else None
            )
            hysteresis = self.room_hysteresis(room)
            decision = ventilation_decision(
                indoor_temperature=indoor_temperature,
                indoor_relative_humidity=indoor_humidity,
                humidity_difference=difference,
                minimum_temperature=room[CONF_MINIMUM_TEMPERATURE],
                previously_ventilating=self._previous_recommendations.get(
                    area_id, False
                ),
                relative_humidity_on=hysteresis[CONF_RELATIVE_HUMIDITY_ON],
                relative_humidity_off=hysteresis[CONF_RELATIVE_HUMIDITY_OFF],
                absolute_humidity_on=hysteresis[CONF_ABSOLUTE_HUMIDITY_ON],
                absolute_humidity_off=hysteresis[CONF_ABSOLUTE_HUMIDITY_OFF],
                temperature_protection_hysteresis=hysteresis[
                    CONF_TEMPERATURE_PROTECTION_HYSTERESIS
                ],
            )
            if decision.reason is not ReasonCode.UNAVAILABLE:
                self._previous_recommendations[area_id] = decision.ventilate

            results[area_id] = RoomResult(
                area_id=area_id,
                area_name=area_name,
                reference_area_id=reference_id,
                reference_name=reference_name,
                available=decision.reason is not ReasonCode.UNAVAILABLE,
                absolute_humidity=indoor_absolute,
                dew_point=indoor_dew_point,
                reference_absolute_humidity=reference_absolute,
                humidity_difference=difference,
                ventilate=decision.ventilate,
                ventilation_status=decision.status,
                reason=decision.reason,
                reasons=decision.reasons,
            )

        return IntegrationData(results)

    def _numeric_state(self, entity_id: str) -> float | None:
        """Read a finite numeric entity state."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        return value

    def _temperature_celsius(self, entity_id: str) -> float | None:
        """Read a temperature state and normalize it to Celsius."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit is None:
            if state.attributes.get(ATTR_DEVICE_CLASS) == "temperature":
                unit = self.hass.config.units.temperature_unit
            else:
                return None
        try:
            return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _unavailable_result(
        area_id: str,
        area_name: str,
        reference_id: str,
        reference_name: str,
    ) -> RoomResult:
        """Create an unavailable room result."""
        return RoomResult(
            area_id=area_id,
            area_name=area_name,
            reference_area_id=reference_id,
            reference_name=reference_name,
            available=False,
            absolute_humidity=None,
            dew_point=None,
            reference_absolute_humidity=None,
            humidity_difference=None,
            ventilate=False,
            ventilation_status=None,
            reason=ReasonCode.UNAVAILABLE,
            reasons=(ReasonCode.UNAVAILABLE,),
        )
