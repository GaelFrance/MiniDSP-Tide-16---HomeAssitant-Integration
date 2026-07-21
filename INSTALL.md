# Installing the miniDSP Tide16 integration

## What you need

- Home Assistant running (any install type: HAOS, Docker, Core...)
- Access to the `config` folder of your Home Assistant install (via
  Samba, SSH, the File editor add-on, or the Studio Code Server add-on)
- Your Tide16's address on the network: normally `minidsp-tide.local`
  works, but if not, use its IP address instead

## Step 1: Copy the integration files

1. Unzip the file you received.
2. Inside your Home Assistant `config` folder, check if a folder called
   `custom_components` already exists. If not, create it.
3. Copy the whole `custom_components/minidsp_tide16` folder from the zip
   into your `config/custom_components/` folder.

When done, the path should look like:
`config/custom_components/minidsp_tide16/__init__.py` (and several other
`.py` files next to it).

## Step 2: Restart Home Assistant

Go to Settings > System > Restart, and restart Home Assistant once so it
notices the new integration files. No need to touch `configuration.yaml`
- since v18, the integration has a real setup screen.

## Step 3: Add the integration from the UI

1. Go to Settings > Devices & services > "+ Add integration".
2. Search for "miniDSP Tide16".
3. Enter the Tide16's address (`minidsp-tide.local`, or its IP address if
   that doesn't resolve for you - find it in your router's device list).
4. Submit. That's it - no YAML editing needed.

(Already had this integration set up via `configuration.yaml` before
v18? Keep your `minidsp_tide16:` block in place for one restart - it
gets imported into the new setup screen automatically, and a
notification will tell you once that's done and it's safe to delete.
All your entities, automations, and dashboards keep working unchanged
either way.)

## Step 4: Check it worked

1. Go to Settings > Devices & services > Entities.
2. Search for "tide16".
3. You should see entities like `sensor.tide16_status`,
   `media_player.tide16`, `button.tide16_shutdown`, and so on.
4. Open `sensor.tide16_status` - it should say "ready" if the Tide16 is
   powered on and reachable on the network.

## Step 5 (optional): Add the dashboard

The zip also includes two ready-made dashboard files:
  `dashboard_iphone_basic.yaml` and `dashboard_iphone_advanced.yaml` - no
  extra setup needed (no HACS card required).

To use one:

1. Go to Settings > Dashboards.
2. Click "+ Add dashboard" > "New dashboard from scratch".
3. Give it a name, then open it and click the three-dot menu (top right)
   > "Edit dashboard" > three-dot menu again > "Edit in YAML".
4. Delete everything there and paste the full contents of the
   `dashboard_iphone_basic.yaml` (or `_advanced.yaml`) file instead.
5. Save.

## Notes

- The Tide16 cannot be woken up over the network once it's in standby -
  only the front panel, IR remote, a 12V trigger, or a smart plug can do
  that. This is a hardware limitation, not a bug in the integration.
- Full details and troubleshooting notes are in `README.md` inside the
  zip.
