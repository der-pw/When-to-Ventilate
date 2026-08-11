"""Tests for the pure climate calculations."""

import pytest

from custom_components.when_to_ventilate.calculations import (
    ReasonCode,
    VentilationStatus,
    absolute_humidity,
    dew_point,
    ventilation_decision,
)


@pytest.mark.parametrize(
    ("temperature", "humidity", "expected"),
    [
        (20.0, 50.0, 8.64),
        (25.0, 60.0, 13.82),
        (0.0, 100.0, 4.85),
    ],
)
def test_absolute_humidity(
    temperature: float, humidity: float, expected: float
) -> None:
    """Absolute humidity matches known reference values."""
    assert absolute_humidity(temperature, humidity) == pytest.approx(expected, abs=0.02)


@pytest.mark.parametrize(
    ("temperature", "humidity", "expected"),
    [
        (20.0, 50.0, 9.26),
        (25.0, 60.0, 16.69),
        (-5.0, 80.0, -7.59),
    ],
)
def test_dew_point(temperature: float, humidity: float, expected: float) -> None:
    """Dew point matches known reference values."""
    assert dew_point(temperature, humidity) == pytest.approx(expected, abs=0.03)


def _decision(
    *,
    humidity: object = 65.0,
    difference: object = 1.0,
    temperature: object = 20.0,
    minimum: object = 18.0,
    previous: bool = False,
):
    return ventilation_decision(
        indoor_temperature=temperature,
        indoor_relative_humidity=humidity,
        humidity_difference=difference,
        minimum_temperature=minimum,
        previously_ventilating=previous,
    )


def test_ventilation_turns_on() -> None:
    """High humidity, useful reference air, and enough heat turn it on."""
    result = _decision()
    assert result.ventilate is True
    assert result.status is VentilationStatus.RECOMMENDED
    assert result.reason is ReasonCode.VENTILATE


def test_humidity_too_low() -> None:
    """Low relative humidity prevents ventilation."""
    result = _decision(humidity=59.9)
    assert result.ventilate is False
    assert result.status is VentilationStatus.NOT_NEEDED
    assert result.reason is ReasonCode.HUMIDITY_OK


def test_difference_too_small() -> None:
    """An insufficient absolute-humidity difference prevents ventilation."""
    result = _decision(difference=0.299)
    assert result.ventilate is False
    assert result.status is VentilationStatus.NOT_RECOMMENDED
    assert result.reason is ReasonCode.INSUFFICIENT_DIFFERENCE


def test_temperature_protection() -> None:
    """A cool room is protected from a new recommendation."""
    result = _decision(temperature=18.49, minimum=18.0)
    assert result.ventilate is False
    assert result.status is VentilationStatus.NOT_RECOMMENDED
    assert result.reason is ReasonCode.TEMPERATURE_PROTECTION


@pytest.mark.parametrize(
    ("humidity", "difference", "temperature", "previous", "expected"),
    [
        (60.0, 0.3, 18.5, False, True),
        (59.999, 0.3, 18.5, False, False),
        (55.0, 0.2, 18.0, True, True),
        (54.999, 0.2, 18.0, True, False),
        (60.0, 0.299, 18.5, False, False),
        (55.0, 0.199, 18.0, True, False),
        (60.0, 0.3, 18.499, False, False),
        (55.0, 0.2, 17.999, True, False),
    ],
)
def test_hysteresis_boundaries(
    humidity: float,
    difference: float,
    temperature: float,
    previous: bool,
    expected: bool,
) -> None:
    """All on/off hysteresis boundaries are explicit."""
    assert (
        _decision(
            humidity=humidity,
            difference=difference,
            temperature=temperature,
            previous=previous,
        ).ventilate
        is expected
    )


def test_custom_hysteresis_thresholds_are_used() -> None:
    """Room-specific thresholds override the calculation defaults."""
    result = ventilation_decision(
        indoor_temperature=20,
        indoor_relative_humidity=65,
        humidity_difference=0.4,
        minimum_temperature=18,
        previously_ventilating=False,
        relative_humidity_on=70,
        relative_humidity_off=62,
        absolute_humidity_on=0.5,
        absolute_humidity_off=0.4,
        temperature_protection_hysteresis=1.0,
    )
    assert result.ventilate is False
    assert result.reason is ReasonCode.HUMIDITY_OK


def test_multiple_blocking_reasons_are_reported() -> None:
    """All currently blocking conditions are returned, not only the first."""
    result = ventilation_decision(
        indoor_temperature=17,
        indoor_relative_humidity=40,
        humidity_difference=0.1,
        minimum_temperature=18,
        previously_ventilating=False,
    )

    assert result.reason is ReasonCode.HUMIDITY_OK
    assert result.status is VentilationStatus.NOT_RECOMMENDED
    assert result.reasons == (
        ReasonCode.HUMIDITY_OK,
        ReasonCode.INSUFFICIENT_DIFFERENCE,
        ReasonCode.TEMPERATURE_PROTECTION,
    )

    result = ventilation_decision(
        indoor_temperature=19,
        indoor_relative_humidity=70,
        humidity_difference=0.5,
        minimum_temperature=18,
        previously_ventilating=False,
        relative_humidity_on=70,
        relative_humidity_off=62,
        absolute_humidity_on=0.5,
        absolute_humidity_off=0.4,
        temperature_protection_hysteresis=1.0,
    )
    assert result.ventilate is True


@pytest.mark.parametrize(
    ("temperature", "humidity", "difference", "minimum"),
    [
        (None, 60, 1, 18),
        (20, None, 1, 18),
        (20, 60, None, 18),
        (20, 60, 1, None),
        ("unavailable", 60, 1, 18),
        (float("nan"), 60, 1, 18),
    ],
)
def test_unavailable_values_do_not_raise(
    temperature: object, humidity: object, difference: object, minimum: object
) -> None:
    """Missing or invalid values safely produce an unavailable decision."""
    result = _decision(
        temperature=temperature,
        humidity=humidity,
        difference=difference,
        minimum=minimum,
    )
    assert result.ventilate is False
    assert result.status is None
    assert result.reason is ReasonCode.UNAVAILABLE


@pytest.mark.parametrize(
    ("temperature", "humidity"),
    [(None, 50), (20, None), (20, "unknown"), (20, -1), (20, 101)],
)
def test_invalid_calculation_inputs_return_none(
    temperature: object, humidity: object
) -> None:
    """Calculation helpers never raise for unavailable sensor data."""
    assert absolute_humidity(temperature, humidity) is None
    assert dew_point(temperature, humidity) is None
