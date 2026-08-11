"""Binary sensor platform for When to Ventilate."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WhenToVentilateConfigEntry
from .coordinator import WhenToVentilateCoordinator
from .entity import GlobalEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WhenToVentilateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ventilation recommendation binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            GlobalVentilationBinarySensor(coordinator),
        ]
    )


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
