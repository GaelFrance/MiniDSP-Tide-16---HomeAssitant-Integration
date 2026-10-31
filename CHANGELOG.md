# Changelog

## 1.0.0 - 2026-10-31 - one integration instead of two

minidsp_tide16 and speedtoys/Minidsp-Tide16-ControlCard (2.6.3) merged into
one integration, under the `minidsp_tide16` domain. The device code, the
settings table, the card and its art come from ControlCard (MIT, see NOTICE);
the identities and behaviours below come from minidsp_tide16 0.30.
Earlier history: [CHANGELOG-minidsp_tide16-0.x.md](CHANGELOG-minidsp_tide16-0.x.md)
and [CHANGELOG-controlcard-2.x.md](CHANGELOG-controlcard-2.x.md).

### Kept from minidsp_tide16 0.x
- **Every entity keeps its unique_id and entity_id**: `media_player.tide16`,
  `sensor.tide16_status`, `sensor.tide16_source`, `number.tide16_volume`,
  `button.tide16_volume_up`, the twelve `button.tide16_source_*`... The
  registry hands them back on upgrade, so automations, scripts, dashboards,
  history, areas and the HomeKit receiver accessory are untouched. The device
  keeps its identifier too.
- **Volume steps accumulate**: Volume Up/Down buttons, `media_player`
  volume_up/volume_down (HomeKit remote, Siri, the iPhone volume webhooks) and
  the `volume_step` action share one pending-target mechanism, so three quick
  presses give three steps. A step is ignored while the volume is unknown.
- **HomeKit receiver**: `media_player.tide16` is `receiver` with VOLUME_STEP.
- **Status semantics**: `not connected` while unreachable, `connecting` until
  the unit's first status, then the unit's own status. Update-check progress
  ("Reaching update server...") never replaces it.
- **Audio signal compensated for the volume** (0.30): peak minus volume must
  clear -60 dB (option), the raw peak -110 dB; silence after 15 s (option).
  Attributes `peak_db`, `level_db`, `threshold_db`, refreshed at most every 5 s.
- Shutdown button, one button per input, Bluetooth and IP Address sensors,
  "No signal" on the Stream sensor, YAML import, Reconfigure.

### Kept from ControlCard 2.6.3
- Upmixer, Dolby profile, DRC, virtualizer, DTS, bass management, presets,
  scenes, auto-dim, firmware status, about 90 entities from `get_settings`.
- The front-panel card (`custom:tide16-panel`, `custom:tide16-mini`), served
  by the integration, with the input-name and suffixed-entity fixes.
- Network discovery, options flow, `set_preset` and `measure_output_level`.

### Changed
- **No hourly firmware check by default** (option "Check for firmware updates
  every hour"); new button **Check for Update**.
- The source list hides the inputs the unit marks hidden (ALSA) and
  disambiguates duplicate names ("Apple TV (hdmi1)").
- The card's volume keys call `minidsp_tide16.volume_step`.

### Fixed
- Audio signal: the -70 dB padding the meter uses for outputs the unit did not
  report is no longer read as a level (it would have meant "signal" at any
  volume under -10 dB once compensated).
