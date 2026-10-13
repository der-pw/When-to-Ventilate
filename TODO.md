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


## Development verification

- Test installation and upgrade from the published GitHub release through HACS.
