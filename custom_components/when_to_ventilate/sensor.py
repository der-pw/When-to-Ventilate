"""Sensor platform for When to Ventilate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import WhenToVentilateConfigEntry
from .calculations import VentilationStatus
from .const import (
    ATTR_ABSOLUTE_HUMIDITY_INDOOR,
    ATTR_ABSOLUTE_HUMIDITY_REFERENCE,
    ATTR_HUMIDITY_DIFFERENCE,
    ATTR_REASON_CODE,
    ATTR_REASON_CODES,
    ATTR_REFERENCE,
    ATTR_REFERENCE_AREA_ID,
)
from .coordinator import WhenToVentilateCoordinator
from .entity import GlobalEntity, ReferenceEntity, RoomEntity
from .models import RoomResult

GRAMS_PER_CUBIC_METER = "g/m³"


@dataclass(frozen=True, kw_only=True)
class RoomSensorEntityDescription(SensorEntityDescription):
    """Describe a calculated room sensor."""

    value_fn: Callable[[RoomResult], float | None]


ROOM_SENSOR_DESCRIPTIONS = (
    RoomSensorEntityDescription(
        key="absolute_humidity",
        translation_key="absolute_humidity",
        device_class=SensorDeviceClass.ABSOLUTE_HUMIDITY,
        native_unit_of_measurement=GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda room: room.absolute_humidity,
    ),
    RoomSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda room: room.dew_point,
    ),
    RoomSensorEntityDescription(
        key="humidity_difference",
        translation_key="humidity_difference",
        native_unit_of_measurement=GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda room: room.humidity_difference,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WhenToVentilateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up calculated sensors."""
    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)
    reference_unique_id_prefix = f"{entry.entry_id}_reference_"
    configured_reference_unique_ids = {
        f"{entry.entry_id}_reference_{reference_id}_{key}"
        for reference_id in coordinator.references
        for key in ("absolute_humidity", "dew_point")
    }
    for registry_entry in list(entity_registry.entities.values()):
        if (
            registry_entry.config_entry_id == entry.entry_id
            and registry_entry.unique_id.startswith(reference_unique_id_prefix)
            and registry_entry.unique_id not in configured_reference_unique_ids
        ):
            entity_registry.async_remove(registry_entry.entity_id)
    for area_id in coordinator.rooms:
        async_add_entities(
            [
                RoomVentilationStatusSensor(coordinator, area_id),
                *(
                    RoomCalculatedSensor(coordinator, area_id, description)
                    for description in ROOM_SENSOR_DESCRIPTIONS
                ),
            ],
            config_subentry_id=coordinator.room_subentry_id(area_id),
        )
    async_add_entities((VentilatingRoomCountSensor(coordinator),))
    area_registry = ar.async_get(hass)
    for reference_id in coordinator.references:
        area = area_registry.async_get_area(reference_id)
        if area is None:
            continue
        async_add_entities(
            [
                ReferenceCalculatedSensor(
                    coordinator, reference_id, "absolute_humidity", area.name
                ),
                ReferenceCalculatedSensor(
                    coordinator, reference_id, "dew_point", area.name
                ),
            ]
        )


class RoomVentilationStatusSensor(RoomEntity, RestoreEntity, SensorEntity):
    """Three-state ventilation recommendation for one area."""

    _attr_translation_key = "ventilate"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [status.value for status in VentilationStatus]
    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: WhenToVentilateCoordinator, area_id: str) -> None:
        """Initialize the status sensor."""
        RoomEntity.__init__(self, coordinator, area_id, "ventilate", "sensor")

    async def async_added_to_hass(self) -> None:
        """Restore whether the recommendation was active to seed hysteresis."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.coordinator.async_restore_recommendation(
                self.area_id,
                last_state.state == VentilationStatus.RECOMMENDED,
            )

    @property
    def available(self) -> bool:
        """Return whether the decision can currently be calculated."""
        return super().available and self.room.available

    @property
    def native_value(self) -> VentilationStatus | None:
        """Return the current three-state recommendation."""
        return self.room.ventilation_status

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return concise decision context."""
        room = self.room
        attributes: dict[str, object] = {
            ATTR_REFERENCE: room.reference_name,
            ATTR_REFERENCE_AREA_ID: room.reference_area_id,
            ATTR_REASON_CODE: room.reason.value,
            ATTR_REASON_CODES: [reason.value for reason in room.reasons],
        }
        for key, value in (
            (ATTR_ABSOLUTE_HUMIDITY_INDOOR, room.absolute_humidity),
            (ATTR_ABSOLUTE_HUMIDITY_REFERENCE, room.reference_absolute_humidity),
            (ATTR_HUMIDITY_DIFFERENCE, room.humidity_difference),
        ):
            if value is not None:
                attributes[key] = round(value, 3)
        return attributes


class RoomCalculatedSensor(RoomEntity, SensorEntity):
    """A calculated climate value for one area."""

    entity_description: RoomSensorEntityDescription

    def __init__(
        self,
        coordinator: WhenToVentilateCoordinator,
        area_id: str,
        description: RoomSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        RoomEntity.__init__(self, coordinator, area_id, description.key, "sensor")
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return whether this specific calculation is available."""
        return (
            super().available
            and self.entity_description.value_fn(self.room) is not None
        )

    @property
    def native_value(self) -> float | None:
        """Return the calculated value."""
        value = self.entity_description.value_fn(self.room)
        return round(value, 3) if value is not None else None


class VentilatingRoomCountSensor(GlobalEntity, SensorEntity):
    """Count rooms with a current ventilation recommendation."""

    _attr_translation_key = "room_count"
    _attr_native_unit_of_measurement = "rooms"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: WhenToVentilateCoordinator) -> None:
        """Initialize the sensor."""
        GlobalEntity.__init__(
            self,
            coordinator,
            "room_count",
            "sensor",
            "when_to_ventilate_room_count",
        )

    @property
    def native_value(self) -> int:
        """Return the number of rooms currently recommended for ventilation."""
        return len(self.coordinator.data.ventilating_rooms)


class ReferenceCalculatedSensor(ReferenceEntity, SensorEntity):
    """Calculated humidity or dew point for a reference area."""

    def __init__(
        self,
        coordinator: WhenToVentilateCoordinator,
        reference_id: str,
        key: str,
        area_name: str,
    ) -> None:
        """Initialize a reference sensor."""
        ReferenceEntity.__init__(
            self, coordinator, reference_id, key, "sensor", area_name
        )
        self._reference_id = reference_id
        self._key = key
        self._attr_translation_key = f"reference_{key}"
        if key == "absolute_humidity":
            self._attr_device_class = SensorDeviceClass.ABSOLUTE_HUMIDITY
            self._attr_native_unit_of_measurement = GRAMS_PER_CUBIC_METER
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 2
        else:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return the calculated reference value."""
        absolute, dew_point_value = self.coordinator.reference_metrics(
            self._reference_id
        )
        value = absolute if self._key == "absolute_humidity" else dew_point_value
        return round(value, 3) if value is not None else None
