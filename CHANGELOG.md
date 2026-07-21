# Changelog

Full version history of the miniDSP Tide16 integration, from the very
first cut (reverse-engineered against the stock site) to today. For the
current state (features, installation, entities), see `README.md`.

## v28: published on GitHub

Repository scaffolding added for the public GitHub repo
([GaelFrance/MiniDSP-Tide-16---HomeAssitant-Integration](https://github.com/GaelFrance/MiniDSP-Tide-16---HomeAssitant-Integration)):

- `LICENSE` (MIT).
- `.gitignore` (Python caches, editor files, OS cruft).
- `hacs.json`, so this repo can be added as a HACS custom repository.
- `manifest.json`: `documentation` now points at the GitHub repo instead
  of miniDSP's device manual (the manual is still linked from
  `README.md`'s intro), added `issue_tracker`, and `codeowners` is no
  longer empty.

The zip distribution's wrapping folder (`minidsp_tide16_ha/`) is gone on
GitHub - the repo root itself now holds `custom_components/`, matching
what HACS and most HA custom-integration repos expect.

## v27: documentation translated to English, ahead of publishing on GitHub

`README.md` and this changelog were originally written in French. All
Python code (docstrings, inline comments) was already English throughout
- confirmed by scanning every `.py` file for accented characters, none
found. This release:

- Translated `CHANGELOG.md` in full, v7 through v26.
- Rewrote `README.md` in English as the primary, GitHub-facing readme.
- Removed `README_EN.md`: it existed specifically to give an English
  summary to people who'd received an earlier, French-only copy of this
  integration - now redundant since `README.md` itself is English.
- Translated the comment header and the v25 inline comment in
  `dashboard_iphone_advanced.yaml`.
- `INSTALL.md` needed no changes - it was already written in English.

**Deliberately left as-is**: the actual card names/labels visible in
both dashboard YAML files (e.g. "État", "Muet", "Redémarrer") stay in
French - those are UI text for day-to-day use, not comments, and
translating them would change the dashboard itself rather than just its
documentation. `translations/fr.json` also stays - it's the intentional
French localization of the config flow, not something tied to the
maintainer's own language.

## v26: removed configuration_snippet.yaml

This file only ever served the YAML -> config entry migration (v18) for
installs predating that version - no current documentation (`README.md`,
`INSTALL.md`) has referenced it since the docs were restructured at v19.
Removed from the zip.

This changes nothing functionally: `__init__.py` still auto-detects a
`minidsp_tide16:` block in `configuration.yaml` if it finds one and
kicks off the migration - that capability stays in place for anyone
still on a pre-v18 install. Only the shipped example file is gone.

## v25: media_player.tide16 was missing from the advanced dashboard

While checking that both bundled dashboards cover every current entity:
`dashboard_iphone_basic.yaml` has had `media_player.tide16` (an all-in-one
volume/mute/source/power card) since v9, but
`dashboard_iphone_advanced.yaml` never did - dropped during its full
rewrite at v14 (the move to `custom:button-card`, then to native cards).
Added in a new "Media" section, right after the "Tide16" section.

Only remaining gap, and this one's intentional: `sensor.tide16_ip_address`
isn't in either dashboard (a diagnostic-only sensor, not much use
day-to-day - still visible in the entity list if you need it, see
`README.md`).

## v24: integration icon

The "miniDSP Tide16" page showed "icon not available" for lack of an
icon - until now, a custom integration had to open a pull request against
the public `home-assistant/brands` repository to get one. Starting with
Home Assistant 2026.3, a custom integration can ship its own icon
locally, in a `brand/` folder next to `manifest.json` - no external
submission needed.

Added: `custom_components/minidsp_tide16/brand/icon.png` and `logo.png`
(an original icon - an equalizer glyph, not the miniDSP logo, to avoid
reproducing a registered trademark). If your Home Assistant is older
than 2026.3, these files are simply ignored and the screen will show
"icon not available" as before - no risk in shipping them regardless.

## v23: the media_player.tide16 slider stayed pinned to the left

v22 fixed the desync, but not the whole story: `volume_level` converted
`volume_db` into a physical linear gain (`10**(db/20)`), the
mathematically correct inverse of the formula already used for the old
linear endpoint - but a very poor fit for a UI slider. That scale
compresses almost the entire useful dB range into the first few percent
of the slider: at -43 dB (a perfectly ordinary listening level), the
linear gain is about 0.7% - so the media_player slider stayed pinned to
the far left regardless of the actual volume, wildly different from
where `number.tide16_volume`'s slider sat for the exact same value.

Fixed: `volume_level` (and `async_set_volume_level` in the other
direction) now maps the dB range **linearly** to 0-100% - the same scale
`number.tide16_volume` already uses - instead of converting to physical
gain. -127.5 dB -> 0%, -63.75 dB -> 50%, -43 dB -> about 66%, 0 dB ->
100%. Both volume sliders in the integration now track each other
exactly. Verified programmatically that the round-trip conversion is
exact across the whole range.

This changes what a given volume percentage means for
`media_player.tide16` compared to earlier versions (a position within
the dB range now, not a linear amplitude gain) - worth keeping in mind
if anything external (HomeKit, an automation) was reading that
percentage expecting the old scale.

The now-unused linear-gain code (`volume_linear`, the `get_volume`
endpoint, `async_set_volume_linear`) has been removed from the
coordinator - nothing else in the integration used it.

Still no `entity_id`/`unique_id` changes.

## v22: media_player.tide16's volume responded poorly

Reported after real-world use: `number.tide16_volume` and the Volume
+/- buttons react instantly (confirmed by the activity log), but
`media_player.tide16`'s volume slider felt slow/desynchronized.

**Cause**: `volume_level` read the coordinator's `volume_linear` field,
kept in sync by a separate channel (the `get_volume` request and the
`volume_change` notification, on the 0.0-1.0 linear-gain scale) from the
`volume_db` field every other volume display depends on. This
integration never sends the linear `set_volume` endpoint though - every
volume command, including ones issued from `media_player.tide16` itself,
goes through `set_volume_db` (converted to dB). Nothing guaranteed the
Tide16 would push a fresh `volume_change` (linear) notification for a
change that was requested in dB, so in practice `volume_linear` only got
refreshed by the 60-second safety-net resync.

Fixed: `volume_level` is now computed directly from `volume_db` (the
exact inverse of the dB->linear conversion `async_set_volume_linear`
already used), so it updates on the same reliable notifications as
`number.tide16_volume`. Verified programmatically that the round-trip
conversion is exact across the whole range (-127.5 to 0 dB).

Still no `entity_id`/`unique_id` changes.

## v21: real startup crash on a recent Home Assistant install

First test on an actual instance after v20 (Home Assistant running under
Python 3.14): the integration wouldn't start up at all.

**Cause found in the full traceback you provided** (not in the warning
shown first in the log, which turned out to be a red herring - see
below): `sensor.py` imported `SensorEntityCategory` from
`homeassistant.components.sensor`, a long-deprecated alias for the
generic `EntityCategory` type (`homeassistant.helpers.entity`),
apparently removed in this Home Assistant version -
`ImportError: cannot import name 'SensorEntityCategory'`. Since
`async_forward_entry_setups()` imports every platform together and one
of them failed, the whole integration refused to start. Switched to the
non-deprecated import.

**The red herring**: the log also showed a "Detected blocking call to
import_module ... inside the event loop" warning at the same timestamp,
which at first glance suggested the failure came from there (a blocking
call escalated into an error). That turned out to be an unrelated second
issue - fixed anyway while we were at it, by preloading all 6 platform
modules on Home Assistant's dedicated import executor thread before
`async_forward_entry_setups()`, so the warning stops reappearing on
every startup.

Still no `entity_id`/`unique_id` changes.

## v20: the volume race was still possible, config flow refined

A fourth review audited v19 in detail and found that two of its fixes
were still incomplete. Nothing broken entity-side - still no
`entity_id`/`unique_id` changes (43/43 identical to the v15 baseline).

**Rapid Volume +/- presses could still lose one.** v19 fixed the simple
case, but `_apply_volume_db` cleared `_pending_volume_db` as soon as
*any* volume confirmation arrived, even one that didn't match the
actually-pending target. Concrete scenario starting at -30 dB: press 1
-> target -28; press 2 before confirmation -> target -26 (based on the
pending -28); press 1's delayed confirmation arrives (-28) and wrongly
cleared the pending -26; press 3 then re-based on the confirmed -28
instead of the pending -26, re-requesting -26 instead of -24 - one press
still lost. Fixed: `_apply_volume_db` now only clears the pending target
when the confirmed value actually matches it (within 0.05 dB). Also
added: the pending target is now rolled back if the command genuinely
fails to send (instead of staying pointed at a command that never left
Home Assistant), and it expires after 5 seconds without confirmation (a
safety net in case a command was rejected or a notification was lost -
the 60s resync would eventually have corrected the state anyway). The
exact scenario from the report was replayed in an isolated test after
the fix: the three presses now correctly accumulate to -24 dB.

**The config flow's connection test only checked a WebSocket
handshake**, not an actual Tide16 reply - any WebSocket server listening
on that port would have been accepted. Fixed: `_test_connection` now
sends `get_coordinator_status` (the same endpoint the coordinator
already uses to confirm readiness on connect) and requires
`status: "OK"` back, reading several messages in case a notification
arrives before the reply to the request.

**Reconfiguring could conflict with the already-active connection.** The
Tide16 appears to accept only one WebSocket client at a time (observed,
not guaranteed by the official docs); since the coordinator stays
connected for the whole duration of the reconfigure flow, testing a new
connection to the same address could fail because of that limit, not a
real network problem. Fixed: `async_step_reconfigure` skips the
connection test when the submitted host/port match the ones already on
record - a genuinely different address is still tested normally.

**Small fixes:** corrected a misleading `__init__.py` comment about
cleanup on platform failure (the coordinator isn't started yet at that
point, so there's nothing to stop, just a reference to remove from
`hass.data`); the connection-error log now passes `exc_info=True` to
keep the full traceback for real bugs; removed a stale block from
`configuration_snippet.yaml` still referencing per-channel level sensors
that no longer exist in this version; fixed a typo in `INSTALL.md`
("a ready-made dashboard files" -> "two ready-made dashboard files");
the README's "single WebSocket client" limitation is now presented as an
empirical observation rather than an absolute fact, since it isn't
confirmed in miniDSP's official docs.

## v19: fixes from a third independent review

A new review looked at the Config Flow added in v18 and found one real
functional bug plus several robustness gaps. Fixed (still no entity
`entity_id`/`unique_id` changes - verified programmatically):

**Real bug: rapid Volume +/- presses could get lost.** Removing
optimistic updates in v17 was the right call, but `async_nudge_volume`
based every press on the last *confirmed* volume - press "+2 dB" three
times quickly before the first confirmation came back, and all three
presses computed "+2 dB" from the same starting value, netting only one
increment instead of three. Fixed by keeping a pending command target
(`_pending_volume_db`), used as the base while no confirmation has
arrived yet, and cleared once a real confirmation (notification or
resync) arrives - or on disconnect.

**The Config Flow allowed multiple entries even though the integration
is single-device.** `manifest.json` now declares
`"single_config_entry": true`, which makes Home Assistant itself block a
second "add integration" attempt.

**`host` was used as a permanent identity (the config entry's
`unique_id`) even though it can change.** After reconfiguring the IP,
that identifier became stale and misleading. Removed entirely - not
needed for a deliberately single-instance integration; replaced with a
plain "does an entry already exist?" check in the `user` and `import`
flow steps.

**The migration notification could reappear on every restart.** It was
fired from `async_setup_entry()`, gated on `entry.source ==
SOURCE_IMPORT` - a condition that stays true forever for an imported
entry, not just the first time. Moved to the config flow's
`async_step_import()`, which only runs once, at the moment the entry is
actually created.

**No connectivity validation at creation/reconfiguration.** The form
accepted any IP or port without checking a Tide16 actually replied -
`async_step_reconfigure` could silently replace a working configuration
with a broken one. Fixed: `cv.port` instead of a plain `int` (rejects
out-of-range ports), plus a real WebSocket connection test (5s) before
creating or updating the entry, showing a "cannot_connect" error on
failure. The automatic YAML import deliberately skips the blocking test
- the Tide16 may legitimately be off when Home Assistant starts.

**Lifecycle best practices:**

- The `Tide16Entity` mixin now calls `await super().async_added_to_hass()`
  before its own code, as any entity mixin should.
- The coordinator's `EVENT_HOMEASSISTANT_STOP` listener is now properly
  unsubscribed in `async_stop()`, which is also made idempotent (the
  other unsubscribe callbacks and the background task are reset to
  `None` after use).
- `async_setup_entry()` now starts the coordinator's connection only
  after platforms have loaded successfully (entities show "unavailable"
  while connecting, which they're already designed to do), and cleans
  up `hass.data` + stops the coordinator if platform loading fails,
  instead of risking a coordinator left running in the background for a
  failed entry.

**Documentation:** this file exists for exactly that reason - the full
history now lives here, and `README.md` only describes the current
state (it still had a line from the very first version claiming "no
media_player," long since untrue). Also added `translations/fr.json` so
the config form displays in French, and bumped `manifest.json`'s version
from `0.1.0` (never updated) to `0.19.0`.

**Not changed, differing opinion**: the point about polling tasks not
being formally tied to the config entry (`entry.runtime_data`) remains a
quality improvement, not a bug - the tasks are short-lived and the timer
that triggers them is itself properly unsubscribed on stop, so there's
no real leak. Same for the unnecessary global-update dispatch on an
error reply: correct, but probably not worth optimizing for a
single-device integration.

## v18: config flow + automatic migration from YAML

Added a real `config_flow` (instead of YAML only):

- **`config_flow.py`** (new): three entry points. `async_step_user` to
  add the integration from the UI (Settings > Devices & services > Add
  integration). `async_step_import`, invisible, triggered once by
  `__init__.py` if it still finds the `minidsp_tide16:` YAML block -
  automatically creates a config entry from that YAML, no prompts.
  `async_step_reconfigure` to change the IP later without deleting and
  recreating the integration.
- **`manifest.json`**: `config_flow` set to `true`.
- **`__init__.py`**: `async_setup()` now only triggers the YAML import if
  it finds one; all the real logic (creating the coordinator, loading
  platforms) now lives in `async_setup_entry()`, called by Home
  Assistant for each config entry. `async_unload_entry()` was added too
  (needed for "Reconfigure" to work properly).
- **The 6 platform files** (`button.py`, `switch.py`, `number.py`,
  `sensor.py`, `media_player.py`, `binary_sensor.py`):
  `async_setup_platform` becomes `async_setup_entry`, and the coordinator
  is fetched via `hass.data[DOMAIN][entry.entry_id]` instead of a single
  global variable. **No entity class was modified** - same `unique_id`,
  same hardcoded `entity_id`, same properties. Only the function that
  registers them with Home Assistant changes mechanism.
- **`strings.json`/`translations/en.json`** (new): proper labels for the
  configuration form (host/port).

Home Assistant's entity registry identifies each entity by its
`unique_id`, not by how it was registered (YAML or config entry). Since
no `unique_id` changed, the migration doesn't recreate any entity: same
`entity_id`, same custom names, same areas, same automations, same
dashboards.

## v17: optimistic updates removed entirely

An independent review pointed out that the v16 fix was incomplete:
`_send()` returns `True` as soon as the message is written to the
WebSocket, which doesn't prove the Tide16 accepted it. If the device
replied `status: "ERROR"`, Home Assistant had already shown the new
state (source, volume, mute, Dirac) - the error ended up in the logs,
but the displayed state stayed wrong.

Fixed by removing optimistic updates entirely, rather than trying to
reconcile them after the fact: `async_set_mute`, `async_set_volume_db`,
`async_set_volume_linear`, `async_select_source`, and
`async_set_dirac_enabled` now just send the command. It's exclusively
the Tide16's own confirmation - a notification (`mute_change`,
`volume_change_db`, `source_change`, `dirac_state`...), or failing that
the 60s safety-net resync - that updates what's displayed in Home
Assistant.

Other fixes from this review: disambiguated duplicate source names in
`media_player.tide16` ("Apple TV (hdmi1)" / "Apple TV (hdmi2)"), volume
slider step changed to 0.5 dB, a fixed comment about the locks, a
shortened log message.

## v16: fixes from an independent review

An independent review raised several valid points, all fixed without
changing any `entity_id`/`unique_id`:

- **Optimistic states even when the send failed**: `_send()` now returns
  `True`/`False`, and each command only applies its optimistic update if
  the send actually succeeded (completed later at v17, see above - this
  first pass was incomplete).
- **`status="ready"` forced the instant the WebSocket opened**, before
  the Tide16 confirmed anything. Now goes through "connecting" first.
- **Entities stayed available indefinitely** even when the Tide16 was
  unreachable. All entities now go "unavailable" when `connected` is
  false (new shared mixin, `entity.py`), except `sensor.tide16_status`
  and `media_player.tide16`, whose whole job is to report
  unreachability.
- **Polling 6 endpoints every 5 seconds**, redundant with push
  notifications: split into two cadences (metering at 5s, safety-net
  resync at 60s for everything else).
- **Error replies silently discarded**: now logged as warnings.
- **Source names entirely hardcoded**: `get_source_names` now used to
  display the name actually configured on the Tide16, without touching
  the technical identifier that determines `entity_id`.
- Small fixes: a `volume=0` edge case, a duplicate dispatch removed,
  `send_json` instead of `send_str(json.dumps(...))`, validation of the
  requested source.

## v15: switch to the official miniDSP API + new entities

miniDSP published official documentation for the Tide16's WebSocket
protocol. Until then, everything had been reverse-engineered by
intercepting traffic on the stock site - broadly correct, but with some
approximations.

- Volume now set via the officially documented `set_volume_db` endpoint
  (official range -127.5 to 0.0 dB, corrected from an assumed -100/0)
  instead of the undocumented `set_volume` (linear gain) found by
  sniffing traffic.
- The undocumented `get_settings` endpoint replaced with the real
  documented ones: `get_volume`, `get_volume_db`, `get_mute`,
  `get_source`.
- `get_rms_block_db`: only the `out` array is populated with real data
  (confirmed by the docs), so `binary_sensor.tide16_audio_signal` now
  only uses that.
- **Notifications**: the Tide16 automatically pushes notifications
  whenever a setting changes (volume, mute, source, status, Bluetooth,
  incoming stream, preset, Dirac Live), regardless of where the change
  came from (API, remote, front panel, another client). The coordinator
  now listens for these in addition to its own request replies.
- New entities: Bluetooth (pairing + current track), incoming stream
  info, speaker configuration, active preset, IP address, Dirac Live
  (enable/disable + measurement-in-progress detection).

## v14: advanced dashboard replaced, no more button-card dependency

After several failed attempts with `custom:button-card` (v10 to v13 -
missing default action, then wrong action format, then wrong entity
reference syntax), the advanced dashboard was replaced with an entirely
native version, with no HACS card at all: `type: sections` view, `tile`
and `button` cards, with `tap_action` in the current format
(`perform-action`/`perform_action`/`target`).

## v13: "configuration error" on every button of the advanced dashboard

A different cause from v12: `target.entity_id: this.entity_id` in the
`tide16_press`/`tide16_source` templates isn't syntax `custom:button-card`
recognizes (recalled from memory, incorrectly). The project's official
docs show it needs a JavaScript template instead:
`entity_id: '[[[ return entity.entity_id ]]]'`. Fixed in both templates.
The simple dashboard wasn't affected (every button there has its
`entity_id` spelled out).

## v12: the actual cause of the popup - `call-service` no longer exists

The `tap_action` added in v10/v11 had no effect: the format used
(`action: call-service` + `service: button.press`) is no longer a valid
action in recent Home Assistant versions (valid actions are `more-info`,
`toggle`, `perform-action`, `navigate`, `url`, `assist`, `none`). Fixed
everywhere with the current format (`action: perform-action` /
`perform_action:` / `target:`).

## v11: the simple dashboard also opened the popup

Same bug as v10, but on `dashboard_iphone_basic.yaml`: tapping a native
`type: button` card opened the "more info" dialog instead of acting
directly - the native card also has no default "press" behavior for the
`button` domain. Fixed by adding `tap_action` to all 17 buttons of the
simple dashboard.

## v10: fixed button taps + a silent audio sensor

- Buttons on the advanced dashboard opened a popup instead of acting
  directly (`custom:button-card` has no special behavior for the
  `button` domain without an explicit `tap_action`). Fixed with a
  `tap_action` in the `tide16_press`/`tide16_source` templates.
- `binary_sensor.tide16_audio_signal` kept showing "Silence": it turns
  out `get_rms_block` is only pushed by the Tide16 to clients that have
  requested it at least once - it isn't an unconditional automatic
  stream. Fixed by requesting it explicitly, on a loop.

## v9: media_player + audio-signal detection

Reintroduced a `media_player.tide16` (an all-in-one entity for
"media-control"-style cards, in addition to the individual entities, not
instead of them) and added `binary_sensor.tide16_audio_signal`
(audio-signal detection via `get_rms_block`, converted to dB, with a
threshold configurable in `const.py`).

## v7-v8: reliable entity_id, corrected sources, fixed volume

- **Unpredictable entity_id**: dashboards widely showed "Entity not
  found" because Home Assistant auto-generated entity_id values that
  didn't match what had been guessed while writing the dashboards. Fixed
  by explicitly pinning `self.entity_id` in each entity's code.
- **Spotify / Apple TV landed on the wrong source**: those buttons are
  custom names given to real hardware inputs (visible under the stock
  site's Settings tab). Fixed: Spotify -> `spdif1` (confirmed), Apple TV
  -> `hdmi1` (inferred). Later cross-checked against the official docs
  at v15. The dynamic-names mechanism added at v16 makes this kind of
  manual correction unnecessary going forward.
- **Volume +/- and the slider did nothing**: confirmed live by
  intercepting the actual frame sent by the stock site
  (`{"endpoint":"set_volume","value":0.0625}`) - the "value" expected by
  the endpoint used at the time (`set_volume`) is a linear gain from
  0.0-1.0, not dB. The code was sending values like `-58` (in dB),
  out of range, silently ignored. Replaced at v15 with the officially
  documented `set_volume_db` endpoint.

## Beginnings: initial reverse-engineering

The very first versions of this integration were built by intercepting
WebSocket traffic from the Tide16's stock control site
(`http://<tide>:5050`), since miniDSP hadn't published any documentation
yet at the time. Several bugs in v7 through v15 came from approximations
introduced by that method - all fixed once the official docs existed
(v15+).

Confirmed from this early stage onward, and still true: the Tide16 fully
shuts down its network stack in standby - no network wake command is
possible, only the front-panel encoder, IR, a 12V trigger, or a smart
plug work.
