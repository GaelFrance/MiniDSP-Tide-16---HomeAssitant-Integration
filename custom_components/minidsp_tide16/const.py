"""Constants for the miniDSP Tide16 integration."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo

DOMAIN = "minidsp_tide16"

CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_PORT = 5555

SIGNAL_TIDE16_UPDATE = "minidsp_tide16_update"

RECONNECT_INTERVAL = 10  # seconds between reconnect attempts while offline

# v15: miniDSP published the official WebSocket API docs for the Tide16
# (docs.minidsp.com/product-manuals/tide16/websocket-api/). Confirmed there:
# volume, mute, source, coordinator status, bluetooth status, incoming
# stream info, active preset, and Dirac Live state are all pushed
# automatically as "notification" messages (a different envelope from
# request replies: {"notification": "<name>", "value"|"data": ...}).
#
# v16: split into two cadences instead of one. get_rms_block_db is NOT in
# the official notification list, so it's the only thing that genuinely
# needs frequent (re-)requesting. Everything else (status/volume/mute/
# source) is already kept in sync by the push notifications above - the
# slower interval below is just a safety-net resync in case a
# notification was ever missed (e.g. right after a reconnect), not the
# primary way state gets updated. This cuts steady-state request volume
# roughly 5x compared to re-requesting all 6 endpoints every 5 seconds.
RMS_REFRESH_INTERVAL = 5  # seconds - metering only, no push notification exists
FULL_REFRESH_INTERVAL = 60  # seconds - safety-net resync of the pushed fields

# Official range, confirmed on docs.minidsp.com: set_volume_db /
# get_volume_db use -127.5 dB (effectively silent) to 0.0 dB (maximum).
# Previously guessed as -100.0 before the official docs were published -
# corrected here. The 0.0-1.0 normalized scale (get_volume) is also
# available but there is no official documented setter for it; we always
# set volume via the documented set_volume_db endpoint (converting from
# linear when needed, e.g. for the media_player entity).
MIN_VOLUME_DB = -127.5
MAX_VOLUME_DB = 0.0
VOLUME_STEP_DB = 2.0  # size of one +/- button press

# Confirmed on docs.minidsp.com: get_rms_block / get_rms_block_db report
# input AND output channel levels, but "the input channels are not
# currently being populated with live metering data" per miniDSP's own
# docs - so only the "out" array is meaningful, which is what we now use
# (previously we mixed in+out, harmless but pointless since "in" is always
# 0). get_rms_block_db already reports in dB directly, no conversion
# needed. -125.5 dB was the observed silence floor on live hardware; tune
# this threshold if it's too sensitive/insensitive for your setup.
SIGNAL_THRESHOLD_DB = -70.0

# Confirmed on docs.minidsp.com (get_source_names / set_source): source
# label -> id mapping. Matches what was previously reverse-engineered live,
# now cross-checked against the official docs.
#
# These labels are the fallback/default names, and drive the fixed part of
# every entity_id and unique_id (button.tide16_source_spotify, etc.) - that
# part deliberately never changes, so existing automations keep working
# even if you rename a source on the device later. What DOES update live
# is the *displayed* name: since v16, the coordinator also fetches
# get_source_names (and listens for source_names_change) to learn
# whatever custom names are actually configured on your Tide16, and the
# source buttons/media_player show those instead of the labels below
# whenever they're available. Think of this dict as "the names this
# integration was built against", not "the only names it understands".
SOURCE_LABEL_TO_ID = {
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
SOURCE_ID_TO_LABEL = {v: k for k, v in SOURCE_LABEL_TO_ID.items()}

# Ordered list of display labels, used as the media_player entity's
# source_list (dict insertion order preserved, matches the order the
# individual source buttons are created in).
SOURCES = list(SOURCE_LABEL_TO_ID.keys())


def slugify_label(label: str) -> str:
    """Turn a display label into the same slug used for entity object_ids."""
    return label.lower().replace(" / ", "_").replace(" ", "_")


def tide16_device_info() -> DeviceInfo:
    """Group every entity under a single 'Tide16' device in HA."""
    return DeviceInfo(
        identifiers={(DOMAIN, "tide16")},
        name="Tide16",
        manufacturer="miniDSP",
        model="Tide16",
    )
