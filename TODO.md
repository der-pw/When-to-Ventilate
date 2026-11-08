# Release and HACS TODOs

## Future feature: window sensors

- Add an optional list of window sensors to each room configuration.
- Show when a room window is open and suppress the usual ventilation advice
  while the room is already being ventilated.
- Detect ventilation from an open window and a sufficient drop in absolute
  humidity; expose states such as “ventilating” and “ventilation complete”.
- Warn when a window stays open too long or the room approaches its minimum
  temperature.
- Consider outside absolute humidity and the room's cooling threshold when
  recommending that a window be opened.
- Handle unavailable window sensors gracefully and keep the existing advice
  available.
- Optionally track ventilation duration and frequency for statistics and
  automations.


## Planned Home Assistant API modernization

- [ ] Defer the config-entry API modernization until Home Assistant 2026.11
  becomes the integration's minimum supported version. Keep the existing
  boolean setup/unload return values for now to preserve older-version support.
- [ ] Change `async_setup_entry` to return `None` and remove `return True`.
- [ ] Change `async_unload_entry` to return `None` and await
  `hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)`.
- [ ] Declare Home Assistant 2026.11 as the minimum supported version in the
  distribution metadata and documentation when making this change.
- [ ] Verify setup, unload/reload, room creation and reconfiguration, option
  changes, and recommendation restoration after a restart under Home Assistant
  2026.11 or newer.

## Development verification

- Test installation and upgrade from the published GitHub release through HACS.
