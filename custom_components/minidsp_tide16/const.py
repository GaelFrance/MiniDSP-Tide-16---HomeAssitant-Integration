"""Constants for the miniDSP Tide16 integration.

v1.0.0 merges two integrations: the device/settings/card code of
speedtoys/Minidsp-Tide16-ControlCard (MIT, see NOTICE) and the entity ids,
unique ids, volume handling and signal detection of minidsp_tide16 0.30.
The domain stays minidsp_tide16 so every existing entity keeps its
entity_id, history, area and HomeKit accessory.
"""

from __future__ import annotations

from typing import Final

from .api.const import SIGNAL_DB

DOMAIN: Final = "minidsp_tide16"

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"

# The panel and its art are served by the integration itself, so there is no
# resource to register by hand and nothing to copy into `www/`.
STATIC_URL: Final = "/tide16_static"
PANEL_JS: Final = "tide16-panel.js"

MANUFACTURER: Final = "miniDSP"
MODEL: Final = "Tide16"

# The device name decides every entity_id on the panel (sensor.tide16_status
# and the rest), so it is fixed rather than user-supplied.
DEVICE_NAME: Final = "Tide16"

SERVICE_VOLUME_STEP: Final = "volume_step"
ATTR_DELTA: Final = "delta"

SERVICE_MEASURE_LEVEL: Final = "measure_output_level"
ATTR_DURATION: Final = "duration"

# Recall a preset by its id.  `select.select_option` is core Home Assistant
# and can only take a string that is already in the option list, so naming a
# preset on the unit - which turns the option "2" into "2: Movie" - breaks
# every automation that stored the number.  This takes the id and nothing
# else, so a rename cannot reach it.
SERVICE_SET_PRESET: Final = "set_preset"
ATTR_PRESET: Final = "preset"

# --- audio detection -------------------------------------------------------
# What counts as silence is not the same level on every system, which is why
# these are settable at all: an analog input, or a source that keeps a
# low-level signal alive between tracks, sits far above digital silence.  The
# defaults are measured rather than chosen - see api/const.SIGNAL_DB and
# coordinator._apply_signal.
CONF_SILENCE_LEVEL: Final = "silence_level"
CONF_SILENCE_HOLD: Final = "silence_hold"

DEFAULT_SILENCE_LEVEL: Final = SIGNAL_DB
# 15 s rather than 4: one quiet passage of classical music must not turn the
# sensor off, and the "1 h without signal" standby automation does not care
# about a few extra seconds.
DEFAULT_SILENCE_HOLD: Final = 15.0

# Signal detection compensated for the master volume (from minidsp_tide16
# 0.30). The output meters are measured AFTER the volume, so a fixed level
# reads quiet music at low volume as silence (-80 dB out at -44 dB volume is
# -36 dB of programme). Detection compares peak - volume_db to this level;
# the raw peak must still clear SIGNAL_FLOOR_DB so the hardware noise floor
# (~-125 dB) never reads as signal with the volume near its minimum.
# silence_level above stays the fallback while the volume is not known yet.
CONF_SIGNAL_RELATIVE: Final = "signal_relative_level"
DEFAULT_SIGNAL_RELATIVE: Final = -60.0
MIN_SIGNAL_RELATIVE: Final = -90.0
MAX_SIGNAL_RELATIVE: Final = -20.0
SIGNAL_FLOOR_DB: Final = -110.0

# The hourly check_for_update makes the unit push "Reaching update server..."
# as its coordinator status for up to a minute. Scripts that wait for status
# "ready" stall on it, so the periodic check is OFF by default; the Check for
# update button asks on demand.
CONF_UPDATE_CHECK: Final = "update_check"
DEFAULT_UPDATE_CHECK: Final = False

# One press of Volume Up/Down, the media player's volume_up/volume_down
# (HomeKit, Siri, the iPhone volume webhooks) - all go through the same
# pending-target accumulation in the coordinator.
VOLUME_STEP_DB: Final = 2.0

# Guard rails, and they are not decoration.  Under the lower bound an input's
# own noise floor can hold the sensor on for ever, so it never reports silence
# and an automation waiting for it never fires - the worse of the two failures.
# Over the upper bound ordinary quiet material reads as silence, which is the
# flapping this whole design exists to stop.
MIN_SILENCE_LEVEL: Final = -110.0
MAX_SILENCE_LEVEL: Final = -45.0
MIN_SILENCE_HOLD: Final = 1.0
MAX_SILENCE_HOLD: Final = 60.0

# --- identities kept from minidsp_tide16 0.x -------------------------------
# The device keeps its old identifier, so its area and the entities' areas
# are untouched.
DEVICE_IDENTIFIER: Final = "tide16"

# Entities that existed in minidsp_tide16 0.x keep their unique_id, so Home
# Assistant's registry hands them back their entity_id (media_player.tide16,
# sensor.tide16_status, ...) and HomeKit keeps the same accessory. Every other
# entity gets f"{DOMAIN}_{key}", which is what 0.x used for all the others
# (minidsp_tide16_status, minidsp_tide16_mute, minidsp_tide16_volume...).
LEGACY_UNIQUE_IDS: Final = {
    "media_player": "minidsp_tide16_media_player_v2",
    "bluetooth_pair": "minidsp_tide16_bt_pair",
}

# Fallback names for the inputs, used only until the unit has sent its own
# (get_source_names). They also fix the slug of every source button's
# entity_id and unique_id (button.tide16_source_spotify...), which therefore
# never changes when an input is renamed on the unit.
SOURCE_LABEL_TO_ID: Final = {
    "Spotify": "spdif1",
    "Apple TV": "hdmi1",
    "SPDIF 2": "spdif2",
    "TOSLINK 1": "toslink1",
    "TOSLINK 2": "toslink2",
    "HDMI 2": "hdmi2",
    "HDMI 3": "hdmi3",
    "ARC / eARC": "arc_earc",
    "XLR": "xlr",
    "RCA": "rca",
    "USB": "usb",
    "Bluetooth": "bluetooth",
}
SOURCE_ID_TO_LABEL: Final = {v: k for k, v in SOURCE_LABEL_TO_ID.items()}


def slugify_label(label: str) -> str:
    """'ARC / eARC' -> 'arc_earc', 'Apple TV' -> 'apple_tv'."""
    return label.lower().replace(" / ", "_").replace(" ", "_")


DOLBY_PROFILES: Final = ("off", "movie", "music", "night")

# The upmixer, which the unit calls the "decoder". Its own control page labels
# datmos "Dolby" and dts "Neural:X"; the front panel shows the Dolby AUDIO and
# dts:x lockups for them, and nothing at all for native.
UPMIXERS: Final = {"native": "Native", "datmos": "Dolby", "dts": "DTS-X"}
SCENES: Final = ("red", "green", "yellow", "blue")
