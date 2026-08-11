"""Data models for When to Ventilate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, TypedDict

from .calculations import ReasonCode, VentilationStatus


class ReferenceConfig(TypedDict):
    """Persisted reference configuration."""

    area_id: str
    temperature_entity_id: str
    humidity_entity_id: str


class HysteresisConfig(TypedDict):
    """Ventilation threshold configuration."""

    relative_humidity_on: float
    relative_humidity_off: float
    absolute_humidity_on: float
    absolute_humidity_off: float
    temperature_protection_hysteresis: float


class RoomHysteresisOverride(TypedDict):
    """Room-specific humidity threshold overrides."""

    relative_humidity_on: float
    relative_humidity_off: float
    absolute_humidity_on: float
    absolute_humidity_off: float


class RoomConfig(TypedDict):
    """Persisted room configuration."""

    area_id: str
    temperature_entity_id: str
    humidity_entity_id: str
    reference_id: str
    minimum_temperature: float
    hysteresis: NotRequired[RoomHysteresisOverride]


@dataclass(frozen=True, slots=True)
class RoomResult:
    """Calculated values for one room."""

    area_id: str
    area_name: str
    reference_area_id: str
    reference_name: str
    available: bool
    absolute_humidity: float | None
    dew_point: float | None
    reference_absolute_humidity: float | None
    humidity_difference: float | None
    ventilate: bool
    ventilation_status: VentilationStatus | None
    reason: ReasonCode
    reasons: tuple[ReasonCode, ...]


@dataclass(frozen=True, slots=True)
class IntegrationData:
    """Coordinator data for all rooms."""

    rooms: dict[str, RoomResult]

    @property
    def ventilating_rooms(self) -> list[RoomResult]:
        """Return rooms where ventilation is recommended."""
        return [room for room in self.rooms.values() if room.ventilate]
