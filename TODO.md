# Release and HACS TODOs

## Repository owner actions

- Set a short repository description.
- Add searchable GitHub topics such as `home-assistant`, `hacs`, and
  `custom-integration`.
- Confirm that GitHub Issues are enabled.
- Run all GitHub Actions successfully on the default branch.
- Create a full GitHub release, not only a tag.
- Submit the integration branding to `home-assistant/brands`.
- Submit an inclusion pull request to `hacs/default` after the release exists.

## Development verification

- Verify the global and per-room hysteresis options flow, Area/device
  assignment, restored hysteresis, entity translations, and Entity Registry
  behavior in a current Home Assistant instance.
- Test installation and upgrade from the published GitHub release through HACS.

Implementation note: `strings.json` is intentionally absent. Current Home
Assistant custom-integration guidance requires complete `translations/en.json`
and language files instead of the core-only `strings.json` build input.
