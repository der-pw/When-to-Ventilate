"""Tests for the integration's config flow."""

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.when_to_ventilate.const import (
    CONF_HYSTERESIS,
    CONF_REFERENCES,
    CONF_ROOMS,
    DEFAULT_ABSOLUTE_HUMIDITY_OFF,
    DEFAULT_ABSOLUTE_HUMIDITY_ON,
    DEFAULT_RELATIVE_HUMIDITY_OFF,
    DEFAULT_RELATIVE_HUMIDITY_ON,
    DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS,
    DOMAIN,
)


async def test_minimal_setup(hass: HomeAssistant) -> None:
    """The user can create a minimal entry without YAML or a reference."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "When to Ventilate"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_REFERENCES: {},
        CONF_ROOMS: {},
        CONF_HYSTERESIS: {
            "relative_humidity_on": DEFAULT_RELATIVE_HUMIDITY_ON,
            "relative_humidity_off": DEFAULT_RELATIVE_HUMIDITY_OFF,
            "absolute_humidity_on": DEFAULT_ABSOLUTE_HUMIDITY_ON,
            "absolute_humidity_off": DEFAULT_ABSOLUTE_HUMIDITY_OFF,
            "temperature_protection_hysteresis": (
                DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS
            ),
        },
    }

    options_result = await hass.config_entries.options.async_init(
        result["result"].entry_id
    )
    assert options_result["type"] is FlowResultType.MENU
    assert options_result["step_id"] == "init"


async def test_single_config_entry(hass: HomeAssistant) -> None:
    """The manifest restricts the integration to one config entry."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        first["flow_id"], {"next_step_id": "finish"}
    )

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "single_instance_allowed"
