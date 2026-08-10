# Release TODOs

Before publishing the first release:

- Confirm that the GitHub repository is available at
  `https://github.com/der-pw/When-to-Ventilate`.
- Decide whether to submit branding to the official Home Assistant brands
  repository before requesting inclusion in HACS defaults.
- Run HACS validation and Hassfest in GitHub Actions on the public repository.
- Create and test a Home Assistant installation package/release for `0.1.0`.
- Verify the global and per-room hysteresis options flow, Area/device assignment,
  restored hysteresis, entity
  translations, and Entity Registry behavior in a real current Home Assistant
  instance.

Implementation note: `strings.json` is intentionally absent. Current Home
Assistant custom-integration guidance requires complete `translations/en.json`
and language files instead of the core-only `strings.json` build input.
