"""Integration setup and event-update tests."""

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.when_to_ventilate.const import (
    CONF_AREA_ID,
    CONF_HUMIDITY_ENTITY_ID,
    CONF_MINIMUM_TEMPERATURE,
    CONF_REFERENCE_ID,
    CONF_REFERENCES,
    CONF_ROOMS,
    CONF_TEMPERATURE_ENTITY_ID,
    DOMAIN,
)


async def test_setup_and_push_updates(hass: HomeAssistant) -> None:
    """Entities load and react to input state changes without polling."""
    area_registry = ar.async_get(hass)
    room_area = area_registry.async_create("Living Room")
    reference_area = area_registry.async_create("Balcony")

    hass.states.async_set(
        "sensor.living_room_temperature",
        "22",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    hass.states.async_set(
        "sensor.living_room_humidity", "65", {ATTR_DEVICE_CLASS: "humidity"}
    )
    hass.states.async_set(
        "sensor.balcony_temperature",
        "10",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    hass.states.async_set(
        "sensor.balcony_humidity", "50", {ATTR_DEVICE_CLASS: "humidity"}
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="When to Ventilate",
        data={},
        options={
            CONF_REFERENCES: {
                reference_area.id: {
                    CONF_AREA_ID: reference_area.id,
                    CONF_TEMPERATURE_ENTITY_ID: "sensor.balcony_temperature",
                    CONF_HUMIDITY_ENTITY_ID: "sensor.balcony_humidity",
                }
            },
            CONF_ROOMS: {
                room_area.id: {
                    CONF_AREA_ID: room_area.id,
                    CONF_TEMPERATURE_ENTITY_ID: "sensor.living_room_temperature",
                    CONF_HUMIDITY_ENTITY_ID: "sensor.living_room_humidity",
                    CONF_REFERENCE_ID: reference_area.id,
                    CONF_MINIMUM_TEMPERATURE: 18.0,
                }
            },
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    room_devices = [
        device
        for device in dr.async_get(hass).devices.values()
        if (DOMAIN, f"area:{room_area.id}") in device.identifiers
    ]
    assert len(room_devices) == 1
    assert room_devices[0].area_id == room_area.id
    assert not any(
        (DOMAIN, f"reference:{reference_area.id}") in device.identifiers
        for device in dr.async_get(hass).devices.values()
    )

    assert hass.states.get("sensor.living_room_ventilate").state == "recommended"
    assert hass.states.get("binary_sensor.when_to_ventilate").state == STATE_ON
    assert hass.states.get("sensor.when_to_ventilate_room_count").state == "1"
    assert (
        hass.states.get("sensor.living_room_absolute_humidity").state
        != STATE_UNAVAILABLE
    )

    assert hass.states.get("sensor.living_room_dew_point").state != STATE_UNAVAILABLE
    difference = hass.states.get("sensor.living_room_humidity_difference")
    assert float(difference.state) > 0.3

    hass.states.async_set(
        "sensor.balcony_temperature",
        "25",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    hass.states.async_set(
        "sensor.balcony_humidity", "90", {ATTR_DEVICE_CLASS: "humidity"}
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.living_room_ventilate").state == "not_recommended"
    assert hass.states.get("binary_sensor.when_to_ventilate").state == STATE_OFF
    assert hass.states.get("sensor.when_to_ventilate_room_count").state == "0"

    hass.states.async_set(
        "sensor.balcony_temperature",
        "10",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    hass.states.async_set(
        "sensor.balcony_humidity", "50", {ATTR_DEVICE_CLASS: "humidity"}
    )
    hass.states.async_set(
        "sensor.living_room_humidity", "50", {ATTR_DEVICE_CLASS: "humidity"}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.living_room_ventilate").state == "not_needed"

    hass.states.async_set("sensor.balcony_humidity", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.living_room_ventilate").state == STATE_UNAVAILABLE
    assert (
        hass.states.get("sensor.living_room_humidity_difference").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.living_room_absolute_humidity").state
        != STATE_UNAVAILABLE
    )

    hass.config_entries.async_update_entry(
        entry,
        options={CONF_REFERENCES: {}, CONF_ROOMS: entry.options[CONF_ROOMS]},
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.balcony_reference_absolute_humidity") is None
    assert hass.states.get("sensor.balcony_reference_dew_point") is None
