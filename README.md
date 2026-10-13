# When to Ventilate

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=der-pw&repository=When-to-Ventilate&category=integration)

When to Ventilate is a Home Assistant custom integration that compares indoor
air with a configurable reference climate and recommends ventilation only when
it can meaningfully reduce indoor moisture without cooling the room below a
configured minimum temperature.

> **Development status:** `0.1.6` is an alpha release. Test it on a
> non-critical Home Assistant installation before relying on its output.

## Features

- UI-only setup through Config Entries and an Options Flow; no YAML required
- Uses existing Home Assistant Areas as rooms and stable `area_id` values for
  persistence
- Reusable reference climates, such as a balcony or outdoor area
- Strongly filtered temperature and relative-humidity entity selectors
- Automatic defaults from an Area's preferred temperature and humidity entities
- Absolute humidity, dew point, and indoor/reference humidity difference
- Per-room and integration-wide ventilation recommendations
- Global default threshold hysteresis with optional per-room humidity overrides
- Configurable per-room minimum temperature with global cooling-protection hysteresis
- Event-driven updates without polling or external network access
- Graceful handling of missing, invalid, `unknown`, and `unavailable` states
- English and German Home Assistant UI translations

## Screenshots

The following screenshots illustrate the setup flow, the room device, and the
three-state ventilation recommendation. Add the images under
`docs/screenshots/` and uncomment the corresponding image line.

### Integration overview

Show the **When to Ventilate** integration page with the hub and its configured
room subentries.

<!-- ![Integration overview](docs/screenshots/01-integration-overview.png) -->

### Room device and calculated entities

Show a configured room device with its ventilation recommendation, absolute
humidity, dew point, and humidity difference entities.

<!-- ![Room device and calculated entities](docs/screenshots/02-room-device-entities.png) -->

### Three-state ventilation recommendation

Show the recommendation in the states **Ventilation recommended**, **Ventilation
not needed**, and **Ventilation not recommended**.

<!-- ![Three-state ventilation recommendation](docs/screenshots/03-three-state-recommendation.png) -->

### Recommendation reason in a dashboard

Show a dashboard card displaying the recommendation together with its
`reason_code` attribute.

<!-- ![Recommendation reason in a dashboard](docs/screenshots/04-dashboard-reason-code.png) -->

### Room configuration

Show the room configuration flow with the temperature sensor, humidity sensor,
reference area, and minimum temperature.

<!-- ![Room configuration](docs/screenshots/05-room-configuration.png) -->

## Requirements

- Python `3.13.2` or newer for development and tests
- A current Home Assistant version compatible with the APIs used by release
  `0.1.6`
- At least one reference Area with temperature and relative-humidity sensors
- For every monitored room, an Area with temperature and relative-humidity
  sensors
- Input sensors should expose the Home Assistant `temperature` or `humidity`
  device class. Temperature values in °F or K are normalized to °C internally.

## Installation

### HACS custom repository

1. Open HACS in Home Assistant.
2. Open **Custom repositories**.
3. Add
   `https://github.com/der-pw/When-to-Ventilate` as an
   **Integration** repository.
4. Install **When to Ventilate** and restart Home Assistant.

The repository is hosted at `https://github.com/der-pw/When-to-Ventilate`.

### Manual installation

1. Copy `custom_components/when_to_ventilate` into the `custom_components`
   directory in your Home Assistant configuration directory.
2. Restart Home Assistant.

## Setup and configuration

Go to **Settings → Devices & services → Add integration**, search for
**When to Ventilate**, and choose one of the initial paths:

- Configure a default reference immediately; or
- Create a minimal empty entry and configure it later.

Open **Configure** on the integration to perform one task at a time:

- configure the global ventilation thresholds;
- add or edit a reference;
- remove an unused reference;
- add or edit a room; or
- disable a room.

A **reference** is an existing Home Assistant Area plus one temperature sensor
and one relative-humidity sensor. It can be reused by any number of rooms.

A **room** is also an existing Area. Its configuration contains only:

1. temperature sensor;
2. relative-humidity sensor;
3. reference; and
4. minimum temperature.

The hub stores global defaults for the relative-humidity and absolute-humidity
on/off thresholds and for the cooling-protection hysteresis. A room inherits
these values unless **Use custom hysteresis values** is enabled for that room.
Room overrides are stored only for that room; changing the global defaults then
updates every room that still inherits them. The minimum temperature remains an
individual room setting.

There is deliberately no enable switch. Removing a room's sensor assignment
through **Disable a room** stops processing it. Renaming an Area does not break
configuration because the integration persists its stable `area_id`, not its
display name.

The integration creates one logical device per configured room to group its four
derived entities and associate them with the corresponding Area. These devices do
not represent hardware and perform no I/O. The two global entities remain
device-less because they do not belong to a physical Area.

Calculated reference values are also global entities. They intentionally do not
create a second virtual reference device; the original reference sensors remain
under the Home Assistant Area where they are configured.

## Entities

For every configured room, the initial suggested entity IDs are:

| Entity | Meaning | Unit |
| --- | --- | --- |
| `sensor.<area>_absolute_humidity` | Indoor absolute humidity | g/m³ |
| `sensor.<area>_dew_point` | Indoor dew point | °C |
| `sensor.<area>_humidity_difference` | Indoor minus reference absolute humidity | g/m³ |
| `sensor.<area>_ventilate` | Three-state ventilation recommendation | — |

Home Assistant's Entity Registry keeps entity IDs stable after creation, even
when an Area is later renamed. Existing temperature and relative-humidity input
sensors are not duplicated.

The global entities are:

| Entity | Meaning |
| --- | --- |
| `binary_sensor.when_to_ventilate` | `on` if any room should be ventilated |
| `sensor.when_to_ventilate_room_count` | Number of rooms with a recommendation |

The room recommendation sensor has three stable, machine-readable states:

- `recommended`: ventilation should meaningfully reduce moisture;
- `not_needed`: only the room humidity is already below the active threshold;
  the outside air and room temperature do not block ventilation; and
- `not_recommended`: ventilation is currently blocked by insufficient drying
  potential or cooling protection.

It also exposes the reference, stable reference Area ID, reason
code, indoor and reference absolute humidity, and their difference. Reason codes
are stable machine-readable values:

- `ventilate`
- `temperature_protection`
- `humidity_ok`
- `insufficient_difference`
- `unavailable`

The entity state values and `reason_code` attribute remain language-independent
so automations are reliable; their UI labels are localized. For a complete
explanation when several blocking conditions apply at once, use the
`reason_codes` list; `reason_code` remains the first (primary) reason for
backwards compatibility.

## How the calculation works

Absolute humidity and dew point are calculated from each sensor pair. The key
comparison is:

```text
humidity difference = indoor absolute humidity - reference absolute humidity
```

A positive value means the indoor air contains more water per volume than the
reference air.

### Starting a recommendation

When the room is currently not recommended for ventilation, all conditions must
hold:

- indoor relative humidity is at least the configured start threshold (60% by
  default);
- the absolute-humidity difference is at least the configured start threshold
  (1.0 g/m³ by default); and
- room temperature is at least the room minimum temperature plus the global
  cooling-protection hysteresis (0.5 K by default).

### Keeping a recommendation active

Once active, the relaxed off thresholds provide hysteresis. All conditions must
continue to hold:

- indoor relative humidity is at least the configured stop threshold (55% by
  default);
- the absolute-humidity difference is at least the configured stop threshold
  (0.6 g/m³ by default); and
- room temperature is at least the configured minimum temperature.

For every on/off pair, the stop threshold must remain below the start
threshold. This prevents a room recommendation from chattering around one
boundary while allowing each room to use appropriate humidity criteria.

The per-room recommendation sensor restores its prior Home Assistant state after
a restart and uses it to seed this hysteresis. If input data is unavailable, the
recommendation becomes unavailable rather than producing a false positive; the
last valid hysteresis state is retained for the next valid calculation.

## Sensor corrections and offsets

This integration intentionally has no sensor-offset settings. If a sensor needs
calibration, create a corrected Home Assistant Template Sensor or another helper
and select that entity in When to Ventilate.

## Troubleshooting

### A sensor is not offered

Check that it:

- belongs to the `sensor` domain;
- has the `temperature` or `humidity` device class; and
- is assigned directly, or through its device, to the Area being configured.

When an Area has matching local sensors, the selector intentionally hides sensors
from other Areas. If no local match exists, matching sensors from all Areas are
shown as a fallback.

### Calculated entities are unavailable

Inspect both room input sensors and both reference input sensors. `unknown`,
`unavailable`, deleted entities, invalid numbers, and temperature sensors without
a usable unit are handled as unavailable input.

### A reference cannot be removed

Change the reference of every room that uses it, or disable those rooms, then
remove the reference.

### Entity IDs do not change after renaming an Area

This is normal Entity Registry behavior. Rename the entity manually in Home
Assistant if desired. The integration continues to use the stable Area ID.

## Development

Install the test dependencies in a Python `3.13.2+` environment and run:

```bash
python -m pytest
ruff check .
ruff format --check .
```

GitHub workflows validate the repository with HACS, Hassfest, pytest, and Ruff.
Core calculation tests cover absolute humidity, dew point, all hysteresis
boundaries, temperature protection, insufficient humidity difference, low
relative humidity, and invalid input. Config-flow smoke tests cover minimal
setup and the single-entry rule.

### HACS publication

The repository is prepared for HACS validation and can be added as a custom
repository. Official HACS listing additionally requires a public GitHub
repository with a description, topics, enabled issues, a passing HACS action,
a passing Hassfest action, and at least one published GitHub release. Inclusion
in the HACS default repository list requires a separate pull request to
`hacs/default`.

## License

MIT. See [LICENSE](LICENSE).
