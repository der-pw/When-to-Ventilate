"""Binary sensor platform for When to Ventilate."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import WhenToVentilateConfigEntry
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
from .entity import GlobalEntity, RoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WhenToVentilateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ventilation recommendation binary sensors."""
    coordinator = entry.runtime_data
    for area_id in coordinator.rooms:
        async_add_entities(
            [RoomVentilationBinarySensor(coordinator, area_id)],
            config_subentry_id=coordinator.room_subentry_id(area_id),
        )
    async_add_entities(
        [
            GlobalVentilationBinarySensor(coordinator),
        ]
    )


class RoomVentilationBinarySensor(RoomEntity, RestoreEntity, BinarySensorEntity):
    """Ventilation recommendation for one area."""

    _attr_translation_key = "ventilate"
    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: WhenToVentilateCoordinator, area_id: str) -> None:
        """Initialize the binary sensor."""
        RoomEntity.__init__(self, coordinator, area_id, "ventilate", "binary_sensor")

    async def async_added_to_hass(self) -> None:
        """Restore the previous recommendation to seed hysteresis."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.coordinator.async_restore_recommendation(
                self.area_id, last_state.state == STATE_ON
            )

    @property
    def available(self) -> bool:
        """Return whether the decision can currently be calculated."""
        return super().available and self.room.available

    @property
    def is_on(self) -> bool:
        """Return whether ventilation is recommended."""
        return self.room.ventilate

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return concise decision context."""
        room = self.room
        attributes: dict[str, Any] = {
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


class GlobalVentilationBinarySensor(GlobalEntity, BinarySensorEntity):
    """Global ventilation recommendation."""

    _attr_translation_key = "global_ventilate"
    _attr_icon = "mdi:home-export-outline"

    def __init__(self, coordinator: WhenToVentilateCoordinator) -> None:
        """Initialize the binary sensor."""
        GlobalEntity.__init__(
            self,
            coordinator,
            "global_ventilate",
            "binary_sensor",
            "when_to_ventilate",
        )

    @property
    def is_on(self) -> bool:
        """Return whether any room should be ventilated."""
        return bool(self.coordinator.data.ventilating_rooms)
