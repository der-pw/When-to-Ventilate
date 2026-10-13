# When to Ventilate – Agent Guide

## Project purpose

This repository contains the `when_to_ventilate` Home Assistant custom
integration. It calculates a room-specific ventilation recommendation from a
room's temperature and relative humidity, a configured reference climate, and
a minimum-temperature (cooling-protection) threshold.

The target repository is `der-pw/When-to-Ventilate`.

## User-facing configuration model

Keep this model intact unless the user explicitly requests an architectural
change:

1. There is exactly one hub config entry, **When to Ventilate**.
2. Reference areas and their temperature/humidity sensors are global hub
   configuration, managed through the hub's Configure action.
3. Each configured Home Assistant Area is a `room` config subentry.
4. A room subentry stores the room temperature sensor, humidity sensor,
   reference area, and minimum temperature.
5. Every room creates one virtual device with four room entities:
   ventilation recommendation, absolute humidity, dew point, and humidity
   difference.
6. The hub also exposes global summary entities.

The desired Devices & Services hierarchy is:

```text
When to Ventilate (hub)
├─ global entities and reference configuration
└─ Room subentry, e.g. Wohnzimmer
   └─ Wohnzimmer device
      ├─ Ventilation recommendation
      ├─ Absolute humidity
      ├─ Dew point
      └─ Humidity difference
```

`manifest.json` must keep `integration_type: "hub"` and
`single_config_entry: true`. The former makes the integration a regular hub in
Devices & Services; the latter prevents a second hub from being added.

## Critical config-subentry rule

Room entities **must be added per room subentry**. In both `sensor.py` and
`binary_sensor.py`, call the platform callback with the room's subentry ID:

```python
async_add_entities(room_entities, config_subentry_id=subentry_id)
```

Do not add all room entities in one shared `async_add_entities(...)` call.
Otherwise Home Assistant creates their device under the hub, shown as
“Devices that do not belong to a subentry”.

Do not manually move devices or entities in the device/entity registries to
repair grouping. A Home Assistant device belongs to one config subentry, and
registry moves can detach entities or trigger framework warnings. Devices must
be created in their final subentry context.

`RoomEntity` may expose `_attr_config_subentry_id`, but this is not a
replacement for passing `config_subentry_id` to `async_add_entities`.
Never include `config_subentry_id` in `DeviceInfo`; Home Assistant supplies it
from the platform callback and duplicate values raise an error.

## Configuration flow and translations

- The root config flow creates the hub and can create an initial reference.
- `WhenToVentilateOptionsFlow` manages global references only.
- `RoomSubentryFlowHandler` creates and reconfigures room subentries.
- Custom integration translations live in
  `custom_components/when_to_ventilate/translations/en.json` and `de.json`.
  Do not add `strings.json` for this custom integration.
- The label for the room-add button belongs at
  `config_subentries.room.initiate_flow.user`.

## Development and testing

- Python requirement: 3.13.2 or newer.
- Run `pytest` for tests and `ruff check .` / `ruff format --check .` for
  style when a suitable Home Assistant test environment is available.
- Use Home Assistant's current stable container for integration-level tests if
  the local Python environment does not include Home Assistant.
- Validate translations as JSON and run Hassfest when possible.

## Versioning and releases

- Version bumps must always be applied consistently to every version-bearing
  file, at minimum `custom_components/when_to_ventilate/manifest.json`,
  `pyproject.toml`, and the release/version reference in `README.md`.
- Do not leave mixed old and new version numbers in the repository.
- Before a release, verify the version references and run the complete test,
  Ruff, Hassfest, and HACS validation workflow.
- Use the version tag as the release title (for example, `v0.1.6`). Start the
  description with a short summary of the release, then list the notable changes
  as concise bullets. Group bullets under headings such as `Added`, `Changed`,
  `Fixed`, or `Important` when that makes the changes easier to scan.
- Describe user-visible behavior and call out breaking entity, configuration,
  or migration changes under `Important`, including any required upgrade steps.
- Report test, Ruff, Hassfest, and HACS checks only when they were actually run
  and passed for that release; name the checks accurately.

## Current product decision

There is intentionally no migration path for experimental configuration
layouts. The user has approved deleting and recreating the integration while
the project is still being developed. Do not add compatibility code merely to
preserve previous experimental hub/subentry layouts.

## Preserve user changes

- Do not overwrite or discard the user's existing code changes.
- Before editing files with existing changes, inspect the diff and preserve
  those changes.
- Modify existing user changes only when they block the latest user request;
  keep any such modification limited to what is needed for that request.
