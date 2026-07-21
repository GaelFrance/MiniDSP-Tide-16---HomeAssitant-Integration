# Home Assistant integration for the miniDSP Tide16

A custom (unofficial) integration that controls the Tide16 through the
WebSocket API officially documented by miniDSP
(docs.minidsp.com/product-manuals/tide16/websocket-api/), exposed on
`ws://<tide>:5555` - the same channel used internally by the stock web
UI (`http://<tide>:5050`).

The state shown in Home Assistant (volume, mute, source, Bluetooth,
incoming stream, preset, Dirac Live...) updates almost instantly no
matter where the change comes from (the API, the remote, the front
panel, or another client such as the stock site), thanks to the
notifications the Tide16 pushes automatically on every setting change.

The full version history (bugs found, fixes, decisions) lives in
`CHANGELOG.md`.

## Installation

**Fresh install:**

1. Copy `custom_components/minidsp_tide16` into your `config` folder.
2. Restart Home Assistant.
3. Settings > Devices & services > Add integration > search for
   "miniDSP Tide16".
4. Enter the address (`minidsp-tide.local` or the Tide16's static IP).
   No need to touch `configuration.yaml`.

**Upgrading from a version older than v18 (YAML-based):**

1. Replace the `custom_components/minidsp_tide16` folder with this one -
   keep your existing `minidsp_tide16:` block in `configuration.yaml`
   for now, don't remove it yet.
2. Restart Home Assistant.
3. A "miniDSP Tide16 migrated" notification confirms the automatic
   migration created a real config entry (Settings > Devices & services
   > miniDSP Tide16) from your YAML - no entity, automation, or
   dashboard is affected (see `CHANGELOG.md`, v18, for the technical
   detail).
4. Once you've seen the notification, remove the `minidsp_tide16:` block
   from `configuration.yaml` and restart one more time. No rush - leaving
   it in place longer is harmless, the migration doesn't run twice.
5. To change the IP later: Settings > Devices & services > miniDSP
   Tide16 > ⋮ > Reconfigure - no need to remove and re-add the
   integration.

Either way, if you're coming from a very old version (before v9),
consider cleaning up orphaned entities (see below).

## Entities

- `button.tide16_source_<name>` x 12
- `button.tide16_volume_up` / `button.tide16_volume_down`
- `button.tide16_shutdown`, `button.tide16_reboot`,
  `button.tide16_bluetooth_pair`
- `switch.tide16_mute`
- `switch.tide16_dirac_live`
- `number.tide16_volume` (slider, in dB)
- `sensor.tide16_status` (connection state - always visible even when
  disconnected, on purpose, so it can be used as an automation
  condition)
- `sensor.tide16_source`
- `sensor.tide16_bluetooth` (pairing state + current track)
- `sensor.tide16_stream` (incoming stream format)
- `sensor.tide16_speaker_config` (e.g. "5.1")
- `sensor.tide16_preset` (active preset)
- `sensor.tide16_ip_address` (diagnostic - not in the bundled
  dashboards, but visible in the entity list)
- `media_player.tide16` (volume, mute, source, power off - in addition
  to the buttons above, not instead of them)
- `binary_sensor.tide16_audio_signal` (audio-signal detection)
- `binary_sensor.tide16_dirac_measuring` (Dirac measurement in progress)

All grouped under a single "Tide16" device in Home Assistant.

## Bundled dashboards

- `dashboard_iphone_basic.yaml`: a classic "masonry" grid, native
  Lovelace cards only (`entities`, `button`, `markdown`,
  `media-control`).
- `dashboard_iphone_advanced.yaml`: a modern `type: sections` view with
  `tile`/`button` cards, 100% native - no HACS dependency.

To use either one: Settings > Dashboards > "+ Add dashboard" > "New
dashboard from scratch", open it, ⋮ menu > "Edit dashboard" > ⋮ menu >
"Edit in YAML", replace everything with the contents of the file you
chose.

## Enabling debug logs

```yaml
logger:
  default: warning
  logs:
    custom_components.minidsp_tide16: debug
```

Then Settings > System > Logs, search for `Tide16 raw message: ...`.
Note: very long replies may be truncated around 16 KB depending on how
you export the logs.

## Cleaning up orphaned entities (if coming from a version older than v9)

Home Assistant never automatically deletes an entity when it disappears
from the code, it just marks it "unavailable". If you still see old
entities (an old "media player", "Left Front", "Right Front", "Ch7"
through "Ch16"...):

1. Settings > Devices & services > Entities.
2. Search "tide16".
3. Click each stale entity.
4. In the dialog that opens, click the gear icon (⚙️) top right, then
   "Delete" at the bottom.

## Known limitations

- **Only one WebSocket client at a time (observed, not officially
  documented).** On the tested firmware, using the stock site and Home
  Assistant at the same time can drop one of the two connections - avoid
  running both simultaneously as a precaution.
- **Only one Tide16 per install.** If you have more than one physical
  unit, entities would collide - open an issue if you need this
  supported.

## Waking from standby

Confirmed by a live test: in standby, the Tide16 fully shuts down its
network stack. There's no way to send a wake command over the network -
only the front-panel encoder, IR, a 12V trigger, or a smart plug work.

## Contributing

Issues and pull requests are welcome. See `CHANGELOG.md` for the
reasoning behind past decisions before proposing a change to behavior
that was deliberately chosen (e.g. the optimistic-update removal at v17,
or the single-instance design).
