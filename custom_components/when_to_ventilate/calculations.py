"""Pure climate calculations and ventilation decision logic."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from .const import (
    DEFAULT_ABSOLUTE_HUMIDITY_OFF,
    DEFAULT_ABSOLUTE_HUMIDITY_ON,
    DEFAULT_RELATIVE_HUMIDITY_OFF,
    DEFAULT_RELATIVE_HUMIDITY_ON,
    DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS,
)


class ReasonCode(StrEnum):
    """Structured reasons for a ventilation decision."""

    VENTILATE = "ventilate"
    TEMPERATURE_PROTECTION = "temperature_protection"
    HUMIDITY_OK = "humidity_ok"
    INSUFFICIENT_DIFFERENCE = "insufficient_difference"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class VentilationDecision:
    """Result of the ventilation decision."""

    ventilate: bool
    reason: ReasonCode
    reasons: tuple[ReasonCode, ...]


def _finite_number(value: object) -> float | None:
    """Return a finite float or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def absolute_humidity(temperature: object, relative_humidity: object) -> float | None:
    """Calculate absolute humidity in g/m³ from °C and percent RH."""
    temperature_value = _finite_number(temperature)
    humidity_value = _finite_number(relative_humidity)
    if (
        temperature_value is None
        or humidity_value is None
        or not 0 <= humidity_value <= 100
        or temperature_value <= -273.15
        or math.isclose(237.3 + temperature_value, 0.0)
    ):
        return None

    try:
        saturation_pressure = 6.1078 * 10 ** (
            (7.5 * temperature_value) / (237.3 + temperature_value)
        )
        vapor_pressure = saturation_pressure * humidity_value / 100
        temperature_kelvin = temperature_value + 273.15
        result = 1e5 * 18.016 / 8314.3 * vapor_pressure / temperature_kelvin
    except (OverflowError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) else None


def dew_point(temperature: object, relative_humidity: object) -> float | None:
    """Calculate the dew point in °C."""
    temperature_value = _finite_number(temperature)
    humidity_value = _finite_number(relative_humidity)
    if (
        temperature_value is None
        or humidity_value is None
        or not 0 < humidity_value <= 100
    ):
        return None

    coefficient = 17.62 if temperature_value >= 0 else 22.46
    temperature_constant = 243.12 if temperature_value >= 0 else 272.62
    if math.isclose(temperature_constant + temperature_value, 0.0):
        return None

    try:
        saturation_pressure = 6.112 * math.exp(
            (coefficient * temperature_value)
            / (temperature_constant + temperature_value)
        )
        vapor_pressure = (humidity_value / 100) * saturation_pressure
        logarithm = math.log(vapor_pressure / 6.112)
        result = temperature_constant * logarithm / (coefficient - logarithm)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) else None


def ventilation_decision(
    *,
    indoor_temperature: object,
    indoor_relative_humidity: object,
    humidity_difference: object,
    minimum_temperature: object,
    previously_ventilating: bool,
    relative_humidity_on: object = DEFAULT_RELATIVE_HUMIDITY_ON,
    relative_humidity_off: object = DEFAULT_RELATIVE_HUMIDITY_OFF,
    absolute_humidity_on: object = DEFAULT_ABSOLUTE_HUMIDITY_ON,
    absolute_humidity_off: object = DEFAULT_ABSOLUTE_HUMIDITY_OFF,
    temperature_protection_hysteresis: object = (
        DEFAULT_TEMPERATURE_PROTECTION_HYSTERESIS
    ),
) -> VentilationDecision:
    """Apply threshold hysteresis and temperature protection."""
    temperature = _finite_number(indoor_temperature)
    relative_humidity = _finite_number(indoor_relative_humidity)
    difference = _finite_number(humidity_difference)
    minimum = _finite_number(minimum_temperature)
    humidity_on = _finite_number(relative_humidity_on)
    humidity_off = _finite_number(relative_humidity_off)
    difference_on = _finite_number(absolute_humidity_on)
    difference_off = _finite_number(absolute_humidity_off)
    protection_hysteresis = _finite_number(temperature_protection_hysteresis)
    if None in (
        temperature,
        relative_humidity,
        difference,
        minimum,
        humidity_on,
        humidity_off,
        difference_on,
        difference_off,
        protection_hysteresis,
    ):
        return VentilationDecision(
            False, ReasonCode.UNAVAILABLE, (ReasonCode.UNAVAILABLE,)
        )

    humidity_threshold = (
        humidity_off if previously_ventilating else humidity_on
    )
    difference_threshold = (
        difference_off if previously_ventilating else difference_on
    )
    temperature_threshold = minimum + (
        0.0 if previously_ventilating else protection_hysteresis
    )

    reasons: list[ReasonCode] = []
    if relative_humidity < humidity_threshold:
        reasons.append(ReasonCode.HUMIDITY_OK)
    if difference < difference_threshold:
        reasons.append(ReasonCode.INSUFFICIENT_DIFFERENCE)
    if temperature < temperature_threshold:
        reasons.append(ReasonCode.TEMPERATURE_PROTECTION)
    if reasons:
        return VentilationDecision(False, reasons[0], tuple(reasons))
    return VentilationDecision(True, ReasonCode.VENTILATE, (ReasonCode.VENTILATE,))
