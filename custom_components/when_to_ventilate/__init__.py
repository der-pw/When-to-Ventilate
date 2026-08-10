"""The When to Ventilate integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import WhenToVentilateCoordinator

WhenToVentilateConfigEntry = ConfigEntry[WhenToVentilateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: WhenToVentilateConfigEntry
) -> bool:
    """Set up When to Ventilate from a config entry."""
    coordinator = WhenToVentilateCoordinator(hass, entry)
    await coordinator.async_start()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WhenToVentilateConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: WhenToVentilateConfigEntry
) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
