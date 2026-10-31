"""Everything else the unit knows.

`get_settings` returns the whole configuration of the processor - the Dolby
and DTS blocks, bass management, the crossovers, the routing matrix, the PEQ,
the speaker table - and the coordinator already asks for it every five
seconds.  Until now all but four fields of that reply were thrown away.

This is the table that gives the rest of it entities.  One row per setting,
read by dotted path out of the stored reply, and where the unit has a setter
for it, the endpoint and the argument name to write it back with.  The
platforms are then almost nothing: each one filters this table by `kind` and
builds its entities from the rows it gets.

The argument names are not guesses.  They were read out of the unit's own
control page at http://<host>:5050, which is a single HTML file with all of
its javascript inline - `set_dts_settings`, for instance, is sent one field at
a time as `{"endpoint": "set_dts_settings", "dialog_control": 3}`, so a row
only ever has to name the field it owns.

Nothing here is required by the panel card.  It is here because a processor
this configurable should not make its owner choose between Home Assistant and
the unit's own web page for the settings nobody got round to wiring up.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.const import EntityCategory

# --- reading -----------------------------------------------------------------


def value_at(settings: Any, path: str) -> Any:
    """Walk a dotted path into the settings reply.

    Returns None for anything missing rather than raising: firmware versions
    differ in what they report, and a row for a field this unit does not have
    should leave an unknown entity, not break the platform.
    """
    node = settings
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


# --- the table ---------------------------------------------------------------

SENSOR: Final = "sensor"
BINARY: Final = "binary"
SWITCH: Final = "switch"
NUMBER: Final = "number"
SELECT: Final = "select"


@dataclass(frozen=True, kw_only=True)
class Tide16Setting:
    """One field of `get_settings`, and how to write it if it can be written."""

    path: str
    key: str
    name: str
    kind: str

    # Writing. `endpoint` with `field` sends {field: value}; a `payload`
    # callable is for the few that need more than that.
    endpoint: str | None = None
    field: str | None = None
    payload: Callable[[Any, dict[str, Any]], dict[str, Any]] | None = None

    # Presentation
    options: tuple[str, ...] | None = None
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    icon: str | None = None
    category: EntityCategory | None = EntityCategory.DIAGNOSTIC
    # Attributes to hang off a sensor - how the 16-wide tables are exposed
    # without turning one of them into sixteen entities.
    attributes: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    def build(self, value: Any, settings: dict[str, Any]) -> dict[str, Any]:
        if self.payload is not None:
            return self.payload(value, settings)
        return {self.field or "value": value}


def _table(path: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Expose a 16-wide block as attributes, keyed by output number."""

    def attrs(settings: dict[str, Any]) -> dict[str, Any]:
        node = value_at(settings, path)
        if not isinstance(node, dict):
            return {}
        out: dict[str, Any] = {}
        for k, v in node.items():
            try:
                out[f"output_{int(k)}"] = v
            except (TypeError, ValueError):
                out[str(k)] = v
        return out

    return attrs


def _count_set(path: str, default: Any) -> Callable[[dict[str, Any]], Any]:
    """How many entries of a 16-wide block are not at their default.

    The state of a table sensor: a number that says "something in here is not
    stock" at a glance, with the values themselves in the attributes.
    """

    def value(settings: dict[str, Any]) -> Any:
        node = value_at(settings, path)
        if not isinstance(node, dict):
            return None
        return sum(1 for v in node.values() if v != default)

    return value


CONFIG: Final = EntityCategory.CONFIG
DIAG: Final = EntityCategory.DIAGNOSTIC

# Dolby's dynamic range control and speaker virtualizing take a mode name; the
# lists come from the unit's own <select> options.
DRC_MODES: Final = ("enable", "disable", "auto", "heavy",
                    "portable_8", "portable_11", "portable_14")
VIRTUALIZE_MODES: Final = ("disable", "speaker", "headphone")


SETTINGS: Final[tuple[Tide16Setting, ...]] = (
    # --- Dolby ---------------------------------------------------------------
    Tide16Setting(
        path="dolby.loudness_management", key="dolby_loudness_management",
        name="Dolby Loudness Management", kind=SWITCH, category=CONFIG,
        endpoint="set_loudness_management", field="enabled", icon="mdi:volume-equal",
    ),
    Tide16Setting(
        path="dolby.center_spread", key="dolby_center_spread",
        name="Dolby Center Spread", kind=SWITCH, category=CONFIG,
        endpoint="set_center_spreading", field="enabled", icon="mdi:arrow-expand-horizontal",
    ),
    Tide16Setting(
        path="dolby.upmixing", key="dolby_upmixing",
        name="Dolby Upmixing", kind=SWITCH, category=CONFIG,
        endpoint="set_dolby_upmixing", field="enabled", icon="mdi:surround-sound",
    ),
    Tide16Setting(
        path="dolby.direct_decoding", key="dolby_direct_decoding",
        name="Dolby Direct Decoding", kind=SWITCH, category=CONFIG,
        endpoint="set_direct_decoding", field="enabled", icon="mdi:transit-connection-variant",
    ),
    Tide16Setting(
        path="dolby.volume_leveler_output_amp", key="dolby_volume_leveler",
        name="Dolby Volume Leveler", kind=SWITCH, category=CONFIG,
        endpoint="set_volume_leveler", field="enabled", icon="mdi:tune-vertical",
    ),
    Tide16Setting(
        path="dolby.height_speakers", key="dolby_height_speakers",
        name="Dolby Height Speakers", kind=BINARY,
    ),
    Tide16Setting(
        path="dolby.dynamic_range_control.mode", key="dolby_drc_mode",
        name="Dolby DRC Mode", kind=SELECT, category=CONFIG,
        endpoint="set_dynamic_range_control", field="mode", options=DRC_MODES,
        icon="mdi:arrow-collapse-vertical",
    ),
    Tide16Setting(
        path="dolby.dynamic_range_control.cut", key="dolby_drc_cut",
        name="Dolby DRC Cut", kind=NUMBER, category=CONFIG,
        endpoint="set_dynamic_range_control", field="cut",
        min_value=0, max_value=100, step=1, unit="%",
    ),
    Tide16Setting(
        path="dolby.dynamic_range_control.boost", key="dolby_drc_boost",
        name="Dolby DRC Boost", kind=NUMBER, category=CONFIG,
        endpoint="set_dynamic_range_control", field="boost",
        min_value=0, max_value=100, step=1, unit="%",
    ),
    Tide16Setting(
        path="dolby.speaker_virtualizing.mode", key="dolby_virtualizer_mode",
        name="Dolby Speaker Virtualizer", kind=SELECT, category=CONFIG,
        endpoint="set_speaker_virtualizing", field="mode", options=VIRTUALIZE_MODES,
        icon="mdi:speaker-multiple",
    ),
    Tide16Setting(
        path="dolby.speaker_virtualizing.front_angle", key="dolby_virtualizer_front_angle",
        name="Virtualizer Front Angle", kind=NUMBER, category=CONFIG,
        endpoint="set_speaker_virtualizing", field="front_angle",
        min_value=0, max_value=30, step=1, unit="°",
    ),
    Tide16Setting(
        path="dolby.speaker_virtualizing.surround_angle", key="dolby_virtualizer_surround_angle",
        name="Virtualizer Surround Angle", kind=NUMBER, category=CONFIG,
        endpoint="set_speaker_virtualizing", field="surround_angle",
        min_value=0, max_value=180, step=1, unit="°",
    ),
    Tide16Setting(
        path="dolby.speaker_virtualizing.height_angle", key="dolby_virtualizer_height_angle",
        name="Virtualizer Height Angle", kind=NUMBER, category=CONFIG,
        endpoint="set_speaker_virtualizing", field="height_angle",
        min_value=0, max_value=30, step=1, unit="°",
    ),
    Tide16Setting(
        path="dolby.speaker_virtualizing.rear_surround_angle",
        key="dolby_virtualizer_rear_angle",
        name="Virtualizer Rear Surround Angle", kind=NUMBER, category=CONFIG,
        endpoint="set_speaker_virtualizing", field="rear_surround_angle",
        min_value=0, max_value=180, step=1, unit="°",
    ),

    # --- DTS -----------------------------------------------------------------
    Tide16Setting(
        path="dts.direct_mode", key="dts_direct_mode",
        name="DTS Direct Mode", kind=SWITCH, category=CONFIG,
        endpoint="set_dts_settings", field="direct_mode",
    ),
    Tide16Setting(
        path="dts.upmix", key="dts_upmix",
        name="DTS Upmix", kind=SWITCH, category=CONFIG,
        endpoint="set_dts_settings", field="upmix", icon="mdi:surround-sound",
    ),
    Tide16Setting(
        path="dts.analog_comp", key="dts_analog_comp",
        name="DTS Analog Compensation", kind=SWITCH, category=CONFIG,
        endpoint="set_dts_settings", field="analog_comp",
    ),
    Tide16Setting(
        path="dts.disable_type1_relabel", key="dts_disable_type1_relabel",
        name="DTS Disable Type 1 Relabel", kind=SWITCH, category=CONFIG,
        endpoint="set_dts_settings", field="disable_type1_relabel",
    ),
    Tide16Setting(
        path="dts.dialog_control", key="dts_dialog_control",
        name="DTS Dialog Control", kind=NUMBER, category=CONFIG,
        endpoint="set_dts_settings", field="dialog_control",
        min_value=0, max_value=6, step=1, unit="dB", icon="mdi:account-voice",
    ),
    Tide16Setting(
        path="dts.drc_percent", key="dts_drc_percent",
        name="DTS DRC", kind=NUMBER, category=CONFIG,
        endpoint="set_dts_settings", field="drc_percent",
        min_value=0, max_value=100, step=1, unit="%",
    ),
    Tide16Setting(
        path="dts.mask", key="dts_mask", name="DTS Mask", kind=NUMBER, category=CONFIG,
        endpoint="set_dts_mask", field="value", min_value=0, max_value=255, step=1,
    ),

    # --- bass management -----------------------------------------------------
    Tide16Setting(
        path="bass_management.enabled", key="bass_management",
        name="Bass Management", kind=SWITCH, category=CONFIG,
        endpoint="set_bass_management", field="enabled", icon="mdi:speaker",
    ),
    Tide16Setting(
        path="bass_management.primary_to_sub", key="bass_primary_to_sub",
        name="Bass Primary to Sub", kind=SWITCH, category=CONFIG,
        endpoint="set_bass_management", field="primary_to_sub",
    ),
    Tide16Setting(
        path="bass_management.primary_to_lfe", key="bass_primary_to_lfe",
        name="Bass Primary to LFE", kind=SWITCH, category=CONFIG,
        endpoint="set_bass_management", field="primary_to_lfe",
    ),
    Tide16Setting(
        path="bass_management.center_to_lr", key="bass_center_to_lr",
        name="Bass Center to L/R", kind=SWITCH, category=CONFIG,
        endpoint="set_bass_management", field="center_to_lr",
    ),
    Tide16Setting(
        path="bass_management.height_to_primary", key="bass_height_to_primary",
        name="Bass Height to Primary", kind=SWITCH, category=CONFIG,
        endpoint="set_bass_management", field="height_to_primary",
    ),
    Tide16Setting(
        path="bass_management.lfe_to_primary", key="bass_lfe_to_primary",
        name="Bass LFE to Primary", kind=SWITCH, category=CONFIG,
        endpoint="set_bass_management", field="lfe_to_primary",
    ),
    Tide16Setting(
        path="bass_management.cutoff", key="bass_cutoff",
        name="Bass Crossover", kind=NUMBER, category=CONFIG,
        endpoint="set_bass_management", field="cutoff",
        min_value=40, max_value=250, step=1, unit="Hz", icon="mdi:sine-wave",
    ),
    Tide16Setting(
        path="bass_management.gain_to_lfe_db", key="bass_gain_to_lfe",
        name="Bass Gain to LFE", kind=NUMBER, category=CONFIG,
        endpoint="set_bass_management", field="gain_to_lfe_db",
        min_value=-20, max_value=20, step=0.5, unit="dB",
    ),
    Tide16Setting(
        path="bass_management.gain_from_lfe_db", key="bass_gain_from_lfe",
        name="Bass Gain from LFE", kind=NUMBER, category=CONFIG,
        endpoint="set_bass_management", field="gain_from_lfe_db",
        min_value=-20, max_value=20, step=0.5, unit="dB",
    ),
    Tide16Setting(
        path="bass_management.manager", key="bass_manager",
        name="Bass Manager", kind=SENSOR,
    ),
    Tide16Setting(
        path="bass_management.lfe_gain", key="bass_lfe_gain",
        name="Bass LFE Gain", kind=SENSOR,
    ),

    # --- Dirac ---------------------------------------------------------------
    Tide16Setting(
        path="dirac.gain", key="dirac_gain",
        name="Dirac Gain", kind=SWITCH, category=CONFIG,
        endpoint="set_dirac_state", field="gain",
    ),
    Tide16Setting(
        path="dirac.delay", key="dirac_delay",
        name="Dirac Delay", kind=SWITCH, category=CONFIG,
        endpoint="set_dirac_state", field="delay",
    ),
    Tide16Setting(
        path="dirac.selected_slot", key="dirac_slot",
        name="Dirac Slot", kind=SENSOR,
    ),
    Tide16Setting(
        path="dirac_filter_index", key="dirac_filter_index",
        name="Dirac Filter Index", kind=NUMBER, category=CONFIG,
        endpoint="set_dirac_filter", field="index",
        min_value=0, max_value=9, step=1,
    ),
    Tide16Setting(
        path="has_dirac_filter", key="has_dirac_filter",
        name="Dirac Filter Loaded", kind=BINARY,
    ),

    # --- the unit itself -----------------------------------------------------
    Tide16Setting(
        path="bypass_mode", key="bypass_mode",
        name="Bypass Mode", kind=SWITCH, category=CONFIG,
        endpoint="set_bypass_mode", field="value", icon="mdi:call-split",
    ),
    Tide16Setting(
        path="flip_center_and_sub", key="flip_center_and_sub",
        name="Flip Center and Sub", kind=SWITCH, category=CONFIG,
        endpoint="set_flip_center_and_sub", field="value",
    ),
    Tide16Setting(
        path="display.sleep_time", key="display_sleep_time",
        name="Display Sleep Time", kind=NUMBER, category=CONFIG,
        endpoint="set_display_sleep_time", field="value",
        min_value=0, max_value=3600000, step=1000, unit="ms",
        icon="mdi:monitor-off",
    ),
    Tide16Setting(
        path="ui.darkmode", key="ui_darkmode",
        name="Web UI Dark Mode", kind=SWITCH, category=CONFIG,
        endpoint="set_ui", field="darkmode", icon="mdi:theme-light-dark",
    ),
    Tide16Setting(
        path="update.automatic", key="automatic_updates",
        name="Automatic Updates", kind=SWITCH, category=CONFIG,
        endpoint="set_update_settings", field="automatic",
    ),
    Tide16Setting(
        path="display.brightness", key="display_brightness",
        name="Display Brightness", kind=SENSOR, unit="%",
    ),
    Tide16Setting(path="sample_rate", key="dsp_sample_rate",
                  name="DSP Sample Rate", kind=SENSOR, unit="Hz"),
    Tide16Setting(path="bit_depth", key="dsp_bit_depth",
                  name="DSP Bit Depth", kind=SENSOR, unit="bit"),
    Tide16Setting(path="channel_count", key="channel_count",
                  name="Channel Count", kind=SENSOR),
    Tide16Setting(path="usb.sample_rate", key="usb_sample_rate",
                  name="USB Sample Rate", kind=SENSOR, unit="Hz"),
    Tide16Setting(path="usb.bit_depth", key="usb_bit_depth",
                  name="USB Bit Depth", kind=SENSOR, unit="bit"),
    Tide16Setting(path="usb.channels", key="usb_channels",
                  name="USB Channels", kind=SENSOR),
    # Read-only on this firmware: there is no setter for either, and the only
    # thing that writes a gain at all is set_channel_gain, per output.
    Tide16Setting(path="sub_gain", key="sub_gain", name="Sub Gain", kind=SENSOR),
    Tide16Setting(path="dialog_gain", key="dialog_gain", name="Dialog Gain", kind=SENSOR),
    Tide16Setting(path="lipsync_delay", key="lipsync_delay",
                  name="Lipsync Delay", kind=SENSOR, unit="ms"),
    Tide16Setting(path="max_volume", key="max_volume", name="Max Volume", kind=SENSOR),
    Tide16Setting(path="is_locked", key="is_locked", name="Locked", kind=BINARY),
    Tide16Setting(path="cec_enabled", key="cec_enabled", name="CEC Enabled", kind=BINARY),
    Tide16Setting(path="settings_name", key="settings_name",
                  name="Settings File", kind=SENSOR),
    Tide16Setting(path="concord_version", key="concord_version",
                  name="Concord Version", kind=SENSOR),
    Tide16Setting(path="src.enabled", key="src_enabled",
                  name="Sample Rate Conversion", kind=BINARY),
    Tide16Setting(path="src.target", key="src_target",
                  name="SRC Target Rate", kind=SENSOR, unit="Hz"),
    Tide16Setting(path="src.quality", key="src_quality",
                  name="SRC Quality", kind=SENSOR),

    # --- the 16-wide tables --------------------------------------------------
    #
    # One entity each, with the values in the attributes. Sixteen outputs times
    # gain, mute, phase, delay and crossover would be eighty entities for
    # something almost nobody adjusts from Home Assistant, and the attribute
    # form is what a template or a script wants anyway.
    Tide16Setting(
        path="channels_gain", key="channel_gains", name="Channel Gains", kind=SENSOR,
        attributes=_table("channels_gain"),
        payload=None, icon="mdi:tune-vertical-variant",
    ),
    Tide16Setting(
        path="channels_mute", key="channel_mutes", name="Channels Muted", kind=SENSOR,
        attributes=_table("channels_mute"), icon="mdi:volume-mute",
    ),
    Tide16Setting(
        path="channels_phase", key="channel_phase", name="Channels Inverted",
        kind=SENSOR, attributes=_table("channels_phase"), icon="mdi:sine-wave",
    ),
    Tide16Setting(
        path="delays", key="channel_delays", name="Channel Delays", kind=SENSOR,
        attributes=_table("delays"), icon="mdi:timer-outline",
    ),
    Tide16Setting(
        path="crossover", key="crossovers", name="Crossovers", kind=SENSOR,
        attributes=_table("crossover"), icon="mdi:sine-wave",
    ),
    Tide16Setting(
        path="peq", key="peq", name="Parametric EQ", kind=SENSOR,
        attributes=_table("peq"), icon="mdi:equalizer",
    ),
    Tide16Setting(
        path="availableSpeakers", key="available_speakers",
        name="Available Speakers", kind=SENSOR, icon="mdi:speaker-multiple",
        attributes=lambda s: {
            name: spec for name, spec in (value_at(s, "availableSpeakers") or {}).items()
            if isinstance(spec, dict) and spec.get("isAvailable")
        },
    ),
    Tide16Setting(
        path="sources", key="source_settings", name="Source Settings", kind=SENSOR,
        attributes=_table("sources"), icon="mdi:import",
    ),
    Tide16Setting(
        path="matrix", key="matrix", name="Routing Matrix", kind=SENSOR,
        icon="mdi:grid",
        attributes=lambda s: {
            f"input_{i + 1}": row for i, row in enumerate(value_at(s, "matrix") or [])
        },
    ),
)


# How a table sensor's own state is computed - a count, so the entity says
# something useful on its own and the detail sits in the attributes.
TABLE_STATES: Final[dict[str, Callable[[dict[str, Any]], Any]]] = {
    "channel_gains": _count_set("channels_gain", 1),
    "channel_mutes": _count_set("channels_mute", False),
    "channel_phase": _count_set("channels_phase", False),
    "channel_delays": _count_set("delays", 0),
    "crossovers": lambda s: len(value_at(s, "crossover") or {}),
    "peq": lambda s: len(value_at(s, "peq") or {}),
    "available_speakers": lambda s: sum(
        1 for spec in (value_at(s, "availableSpeakers") or {}).values()
        if isinstance(spec, dict) and spec.get("isAvailable")
    ),
    "source_settings": lambda s: sum(
        1 for spec in (value_at(s, "sources") or {}).values()
        if isinstance(spec, dict) and not spec.get("hidden")
    ),
    "matrix": lambda s: sum(
        1 for row in (value_at(s, "matrix") or [])
        for cell in (row if isinstance(row, list) else [])
        if isinstance(cell, dict) and cell.get("on")
    ),
}


def of_kind(kind: str) -> tuple[Tide16Setting, ...]:
    return tuple(s for s in SETTINGS if s.kind == kind)
