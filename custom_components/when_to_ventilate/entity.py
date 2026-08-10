"""Shared entity helpers for When to Ventilate."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import WhenToVentilateCoordinator
from .models import RoomResult


class WhenToVentilateEntity(CoordinatorEntity[WhenToVentilateCoordinator]):
    """Base entity backed by the integration coordinator."""

    _attr_has_entity_name = True


class RoomEntity(WhenToVentilateEntity):
    """Base entity for one configured Home Assistant area."""

    def __init__(
        self,
        coordinator: WhenToVentilateCoordinator,
        area_id: str,
        key: str,
        entity_domain: str,
    ) -> None:
        """Initialize a room entity."""
        super().__init__(coordinator)
        self.area_id = area_id
        area_name = coordinator.data.rooms[area_id].area_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{area_id}_{key}"
        subentry_id = coordinator.room_subentry_id(area_id)
        if subentry_id:
            self._attr_config_subentry_id = subentry_id
        self.entity_id = f"{entity_domain}.{slugify(area_name)}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"area:{area_id}")},
            name=area_name,
            suggested_area=area_name,
            manufacturer="When to Ventilate",
            model="Room climate assessment",
        )

    @property
    def room(self) -> RoomResult:
        """Return the latest result for this room."""
        return self.coordinator.data.rooms[self.area_id]


class GlobalEntity(WhenToVentilateEntity):
    """Base entity for integration-wide values."""

    def __init__(
        self,
        coordinator: WhenToVentilateCoordinator,
        key: str,
        entity_domain: str,
        object_id: str,
    ) -> None:
        """Initialize a global entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self.entity_id = f"{entity_domain}.{object_id}"


class ReferenceEntity(WhenToVentilateEntity):
    """Base entity for global calculated values of a reference area."""

    def __init__(
        self,
        coordinator: WhenToVentilateCoordinator,
        reference_id: str,
        key: str,
        entity_domain: str,
        area_name: str,
    ) -> None:
        """Initialize a reference entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_reference_{reference_id}_{key}"
        )
        self.entity_id = f"{entity_domain}.{slugify(area_name)}_reference_{key}"
        self._attr_translation_placeholders = {"reference_name": area_name}
