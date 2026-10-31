"""The Tide16's WebSocket vocabulary.

Every name here was read off a live unit (Tide FW 1.16.6, HDMI 1.48/1.d) -
either from the endpoint list the processor's own control page on port 5050
builds its UI from, or from a recorded session against the hardware.  Nothing
is inherited from another implementation.

The wire format is small enough to state completely:

    request       {"endpoint": "<name>", ...args}
    reply         {"req": "<name>", "status": "OK", "data": <payload>}
    notification  {"notification": "<name>", "value"|"data": <payload>}
    greeting      {"val": "Hi from coordinator", "endpoint": ""}

Replies carry the endpoint back in `req`, which is what makes correlation
possible at all - there is no request id.  Setters mostly do NOT reply; the
unit confirms them by pushing a notification instead, so a setter that waits
for a reply waits forever.
"""

from __future__ import annotations

from typing import Final

DEFAULT_PORT: Final = 5555
# The unit's own control page.  Besides serving the page, its `Date` header is
# the only view there is of the unit's clock - nothing on the WebSocket reports
# the time.
WEB_PORT: Final = 5050

# --- reads -----------------------------------------------------------------
GET_STATUS: Final = "get_coordinator_status"
GET_VOLUME_DB: Final = "get_volume_db"
GET_MUTE: Final = "get_mute"
GET_SOURCE: Final = "get_source"
GET_SOURCE_NAMES: Final = "get_source_names"
GET_STREAM: Final = "get_stream_properties"
GET_PRESET_INDEX: Final = "get_current_preset_index"
GET_PRESETS: Final = "get_all_presets"
GET_SPEAKER_CONFIG: Final = "get_speaker_config_number"
GET_OUTPUT_SPEAKERS: Final = "get_output_speakers"
GET_CUSTOM_PORT_NAMES: Final = "get_custom_out_port_names"
GET_DIRAC_STATE: Final = "get_dirac_state"
GET_DIRAC_MEASURING: Final = "get_dirac_measuring_mode"
# The loaded filter's own record - its name and, the reason it is read at all,
# its type: plain Dirac Live, Bass Control, or ART.  Nothing pushes it.
GET_DIRAC_FILTER: Final = "get_dirac_filter"
GET_BLUETOOTH: Final = "get_bluetooth_status"
GET_RMS_DB: Final = "get_rms_block_db"
GET_SETTINGS: Final = "get_settings"
GET_IP: Final = "get_ip"
POLL: Final = "poll"

# The front-panel controller's firmware, as installed and as packaged inside
# the Tide firmware.  The installed one does not come back in the reply - the
# reply is a bare OK, and the version follows as a front_panel_fw_version push.
# The packaged one is the reply's data, as a list: [1, 11] for "1.11".
GET_FRONT_PANEL_FW: Final = "front_panel_get_fw_ver"
GET_FRONT_PANEL_PACKAGED_FW: Final = "front_panel_get_packaged_fw_ver"

# Asks the unit to ask miniDSP's update server.  Only asks: the unit's own
# control page puts it next to "Force update", which is a separate endpoint and
# the one that installs.  The answer arrives as `update` pushes - progress
# first, then the result - and the reply lands last, after the result:
#
#     update  "Checking for updates..."    code 2
#     update  "Reaching update server..."  code 0
#     update  "No updates available"       code 1
#
# That is the whole of what has been seen, from a unit with nothing to install.
# What it says when there IS something is not known yet.
CHECK_FOR_UPDATE: Final = "check_for_update"
# Everything these do is install or start installing.  Named so that nothing
# here can send them by accident: this integration looks, it never updates.
#   force_update, start_update_server, front_panel_start_firmware_update

# Everything the unit pushes on its own is still requested once at connect,
# and re-requested on the slow safety-net sweep in case a push was missed
# across a reconnect.  get_settings is the odd one out: nothing pushes it, and
# it is the only source for the input table, the Dolby profile and firmware.
REFRESH_ENDPOINTS: Final = (
    GET_STATUS,
    GET_VOLUME_DB,
    GET_MUTE,
    GET_SOURCE,
    GET_SOURCE_NAMES,
    GET_STREAM,
    GET_PRESET_INDEX,
    GET_PRESETS,
    GET_SPEAKER_CONFIG,
    GET_OUTPUT_SPEAKERS,
    GET_CUSTOM_PORT_NAMES,
    GET_DIRAC_STATE,
    GET_DIRAC_MEASURING,
    GET_DIRAC_FILTER,
    GET_BLUETOOTH,
    GET_SETTINGS,
)

# --- writes ----------------------------------------------------------------
SET_VOLUME_DB: Final = "set_volume_db"
SET_MUTE: Final = "set_mute"
SET_SOURCE: Final = "set_source"
SET_SCENE: Final = "set_scene"
SET_PRESET: Final = "set_preset"
SET_DIRAC_STATE: Final = "set_dirac_state"
SET_BT_PAIRING: Final = "set_bt_pairing_mode"
# Not in the endpoint list the unit's own control page publishes - that page
# has no brightness control at all - and found by probing. Takes {"value":
# 0-100}; any other argument name is rejected with "Key value should be
# present".
SET_BRIGHTNESS: Final = "set_brightness"
SET_DOLBY_PROFILE: Final = "set_dolby_profile"
# Takes a `decoder` key, not a `value` - the unit says so when it is
# missing. Values are the three the unit's own control page offers.
SET_FORCED_UPMIXER: Final = "set_forced_upmixer"
REBOOT: Final = "reboot"
SHUTDOWN: Final = "shutdown"

# set_dolby_profile is NOT in the control page's endpoint list - it was found
# by watching the unit - so a rejection means "this firmware doesn't have it",
# not "the request was malformed".
OBSERVED_ONLY: Final = frozenset({SET_DOLBY_PROFILE})

# --- pushes ----------------------------------------------------------------
# miniDSP's own docs warn that the unit sends more notifications than are
# documented, so unknown names are dropped rather than treated as errors.
N_STATUS: Final = "coordinator_status"
N_VOLUME_DB: Final = "volume_change_db"
N_MUTE: Final = "mute_change"
N_SOURCE: Final = "source_change"
N_SOURCE_NAMES: Final = "source_names_change"
N_PRESET: Final = "preset_change"
N_DIRAC_STATE: Final = "dirac_state"
N_DIRAC_MEASURING: Final = "dirac_measurement_mode"
N_STREAM: Final = "stream_changes"
N_BLUETOOTH: Final = "bluetooth_status"
N_SPEAKER_CONFIG: Final = "speaker_config_number_change"
N_UPDATE: Final = "update"
N_FRONT_PANEL_FW: Final = "front_panel_fw_version"

# Handed over as the whole envelope rather than just its value, because the
# part that matters sits beside it: `update` carries its `code` there.
ENVELOPE_NOTIFICATIONS: Final = frozenset({N_UPDATE})

# The `update` codes that mean "still going" rather than "here is the answer".
UPDATE_PROGRESS_CODES: Final = frozenset({0, 2})
# While it checks, the unit also sets its own status to the progress text and
# never sets it back - the next status read does.  These are the texts seen
# doing it; any other progress text is learned as it arrives.
UPDATE_PROGRESS_TEXTS: Final = frozenset(
    {"Checking for updates...", "Reaching update server..."}
)

# --- ranges ----------------------------------------------------------------
# The documented set_volume_db range: -127.5 dB is effectively silent, 0.0 is
# maximum.  Anything outside it is clamped before it reaches the wire.
MIN_VOLUME_DB: Final = -127.5
MAX_VOLUME_DB: Final = 0.0

# The unit reports 16 output channels whatever the speaker layout; unused ones
# sit at the floor.  Measured silence on this hardware is about -125 dB.
CHANNEL_COUNT: Final = 16
SILENCE_DB: Final = -70.0

# The audio-signal detector's threshold.  Numerically the same as the meter's
# floor and deliberately a separate name anyway: one is how low a bar may draw,
# the other is whether anything is playing, and they are free to diverge.
#
# Measured on real program material at 10Hz before choosing it: at -70 the peak
# of the sixteen outputs falls below the line twice a minute for one 100ms block
# each, and at -60 it does so twenty-one times with the longest run 3.2 seconds -
# four fifths of a second short of the release below, on ordinary content.  The
# quiet end of the scale is where the headroom is, and there is no floor noise
# up here to reject: real silence on this hardware reads -120.
SIGNAL_DB: Final = -70.0
