"""Everything the panel prints.

The five entities that used to be `template:` blocks in the user's own
packages file - the split volume, the kHz rate, the held channel names - are
ordinary entities here.  So are the two that used to be `command_line` sensors
shelling out to python scripts: the firmware versions and the Dolby profile
both come from `get_settings`, which the coordinator already reads.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import Tide16Coordinator
from .entity import Tide16Entity
from .settings import SENSOR, TABLE_STATES, Tide16Setting, of_kind, value_at


@dataclass(frozen=True, kw_only=True)
class Tide16SensorDescription(SensorEntityDescription):
    """A sensor is a name and a function of coordinator data."""

    value: Callable[[dict[str, Any]], Any]
    attributes: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    always_available: bool = False


def _stream(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("stream") or {}


def _rate_khz(data: dict[str, Any]) -> str | None:
    """48000 -> "48 kHz", 44100 -> "44.1 kHz"."""
    raw = _stream(data).get("sample_rate") or _stream(data).get("dec_sample_rate")
    try:
        hz = float(raw)
    except (TypeError, ValueError):
        return None
    if hz <= 0:
        return None
    khz = hz / 1000
    # One decimal always, which is what the unit's own panel prints: 48.0 kHz,
    # not 48 kHz. %g drops the trailing zero and made the two disagree.
    return f"{khz:.1f} kHz"


# Names the unit reports that are too long for the Program cell. The row
# shrink-wraps and the decoder badge starts at x310, so anything much past
# thirty characters runs underneath the Dolby lockup.
#
# Exact matches only, keyed lower-case. A stream this does not know is passed
# through untouched - guessing at an abbreviation for a format nobody has seen
# is how a panel ends up asserting something the device never said.
STREAM_SHORT_FORMS: Final = {
    "dolby digital plus with dolby atmos": "DD+ W/Atmos",
    "dolby digital plus without dolby atmos": "DD+ W/O Atmos",
    # "channel-based" is the only kind of third-party PCM the unit reports,
    # so the qualifier distinguishes it from nothing and costs half the cell.
    "third-party channel-based pcm": "Third-party PCM",
}


def _stream_name(data: dict[str, Any]) -> str | None:
    """The stream description, shortened when it is one we know is too long."""
    raw = _stream(data).get("decoder_stream_src_format")
    if not isinstance(raw, str):
        return raw
    trimmed = raw.strip()
    return STREAM_SHORT_FORMS.get(trimmed.lower(), trimmed) or None


def _decoder(data: dict[str, Any]) -> str | None:
    """"LPCM decoder" -> "LPCM", "unknown decoder" -> "unknown".

    The unit suffixes the word onto every decoder name, which reads as
    "Decoder: unknown decoder" once the panel has already labelled the row.
    Names that carry no suffix (DTS_NEURAL_X) are left exactly as they are.
    """
    raw = _stream(data).get("decoder_type")
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    if trimmed.lower().endswith(" decoder"):
        trimmed = trimmed[: -len(" decoder")].strip()
    return trimmed or None


def _input_format(data: dict[str, Any]) -> str | None:
    """channel_config 2 -> "2.0", 6 -> "5.1", 8 -> "7.1", a bitstream -> "Bitstream".

    The unit prints this formatting on its own front panel, so the decimal is
    the device's convention rather than an invention here. It exists as a
    sensor because a dashboard can only read an attribute verbatim - and
    because doing it in a card template means a templating card re-rendering
    the whole panel every time the stream twitches.
    """
    # A bitstream has no channel count to report - the unit sends
    # channel_config "" and says so with is_bitstream, and its own panel
    # prints the word rather than a number.
    if _stream(data).get("is_bitstream"):
        return "Bitstream"

    raw = _stream(data).get("channel_config")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return f"{n}.0" if n <= 2 else f"{n - 1}.1"


def _bluetooth(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("bluetooth") or {}


def _bluetooth_state(data: dict[str, Any]) -> str | None:
    """not_paired / paired / playing, as in minidsp_tide16 0.x."""
    bt = _bluetooth(data)
    if "paired" not in bt:
        return None
    if not bt.get("paired"):
        return "not_paired"
    music = bt.get("music") if isinstance(bt.get("music"), dict) else {}
    return "playing" if music.get("playing") else "paired"


def _bluetooth_attributes(data: dict[str, Any]) -> dict[str, Any]:
    bt = _bluetooth(data)
    music = bt.get("music") if isinstance(bt.get("music"), dict) else {}
    return {
        "paired": bt.get("paired"),
        "playing": bool(music.get("playing")) if music else None,
        "title": music.get("title") or None,
        "artist": music.get("artist") or None,
        "album": music.get("album") or None,
    }


def _preset_fallback(data: dict[str, Any]) -> str | None:
    index = data.get("preset_index")
    return None if index is None else f"Preset {index}"


def _volume_parts(data: dict[str, Any]) -> tuple[str, str] | None:
    """-32.5 dB drawn as a big "-32" and a small ".5"."""
    db = data.get("volume_db")
    if db is None:
        return None
    negative = db < 0
    whole = int(abs(db))
    frac = round((abs(db) - whole) * 10)
    if frac == 10:  # -31.95 must read as -32.0, not -31.10
        whole += 1
        frac = 0
    return (f"-{whole}" if negative else f"{whole}", str(frac))


SENSORS: tuple[Tide16SensorDescription, ...] = (
    Tide16SensorDescription(
        key="status",
        name="Status",
        # The one sensor that survives the unit going away: "not connected" is
        # the answer, not the absence of one.
        always_available=True,
        value=lambda d: d.get("status"),
    ),
    Tide16SensorDescription(
        key="source",
        name="Source",
        value=lambda d: (d.get("source_names") or {}).get(d.get("source_id"))
        or d.get("source_id"),
    ),
    Tide16SensorDescription(
        key="stream",
        name="Stream",
        # "No signal" rather than unknown while nothing is playing, as in
        # minidsp_tide16 0.x.
        value=lambda d: _stream_name(d) or "No signal",
        attributes=lambda d: {
            "decoder_type": _decoder(d),
            "sample_rate": _stream(d).get("sample_rate"),
            "channel_config": _stream(d).get("channel_config") or None,
            "stream_type": _stream(d).get("decoder_stream_type"),
            "processing": _stream(d).get("decoder_stream_proc_type"),
        },
    ),
    Tide16SensorDescription(
        key="bluetooth",
        name="Bluetooth",
        icon="mdi:bluetooth-audio",
        value=_bluetooth_state,
        attributes=_bluetooth_attributes,
    ),
    Tide16SensorDescription(
        key="ip_address",
        name="IP Address",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.get("ip_address"),
    ),
    Tide16SensorDescription(
        key="input_format",
        name="Input Format",
        value=_input_format,
    ),
    Tide16SensorDescription(
        key="sample_rate_khz",
        name="Sample Rate kHz",
        value=_rate_khz,
    ),
    Tide16SensorDescription(
        key="speaker_config",
        name="Speaker Config",
        value=lambda d: d.get("speaker_config"),
    ),
    Tide16SensorDescription(
        key="preset",
        name="Preset",
        # The state is what the unit CALLS this preset; the panel prints it
        # under the number.  Every slot on this hardware reports an empty
        # name, so "Preset 2" is the fallback rather than a blank line.
        value=lambda d: d.get("preset_name") or _preset_fallback(d),
        attributes=lambda d: {
            "preset_index": d.get("preset_index"),
            "name": d.get("preset_name") or None,
        },
    ),
    Tide16SensorDescription(
        key="preset_id",
        name="Preset ID",
        # The bare id, which is the one thing about a preset that a rename
        # cannot move.  The Preset sensor above states the NAME and the
        # Filter Preset select states "2: Movie", both of which are for
        # people to read; an automation comparing against a stored number
        # needs a state that is only ever the number, and this is it.
        value=lambda d: d.get("preset_index"),
    ),
    Tide16SensorDescription(
        key="volume_integer",
        name="Volume Integer",
        value=lambda d: (_volume_parts(d) or (None, None))[0],
    ),
    Tide16SensorDescription(
        key="volume_decimal",
        name="Volume Decimal",
        value=lambda d: (_volume_parts(d) or (None, None))[1],
    ),
    Tide16SensorDescription(
        key="channel_names_held",
        name="Channel Names Held",
        # The state is the count; the names themselves are the attribute the
        # legend reads, held across a dropout so the meter stays labelled.
        value=lambda d: len(d.get("channel_names_held") or []),
        # `custom_channels` lists the outputs whose name was typed into the
        # unit's own web UI rather than assigned by the decoder. The legend
        # prints those verbatim: "RightRearOverhead" is an enum that has to be
        # abbreviated to fit, but a name somebody chose themselves is already
        # as short as they wanted it, and shortening it again turns "L-Mix"
        # into "LM".
        attributes=lambda d: {
            "channel_names": d.get("channel_names_held") or [],
            "custom_channels": d.get("custom_channels_held") or [],
        },
        always_available=True,
    ),
    Tide16SensorDescription(
        # "Dirac Live", "Dirac Live Bass Control" or "Dirac Active Room
        # Treatment" - the only way to tell an ART filter from a plain one,
        # which is what a front-panel ART badge needs to light from.
        key="dirac_filter_type",
        name="Dirac Filter Type",
        value=lambda d: (d.get("dirac_filter") or {}).get("type"),
        attributes=lambda d: {
            "filter_name": (d.get("dirac_filter") or {}).get("name"),
            "filter_index": (d.get("dirac_filter") or {}).get("index"),
        },
    ),
    Tide16SensorDescription(
        # The unit's clock less Home Assistant's.  A second or two either way
        # is measurement.  The plate's clock turns red past twelve hours - a
        # unit whose NTP never got through, not one that has drifted.
        key="clock_offset",
        name="Clock Offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="s",
        value=lambda d: d.get("clock_offset"),
    ),
    Tide16SensorDescription(
        key="versions",
        name="Versions",
        entity_category=EntityCategory.DIAGNOSTIC,
        always_available=True,
        value=lambda d: (d.get("versions") or {}).get("tide"),
        attributes=lambda d: {
            "tide": (d.get("versions") or {}).get("tide"),
            "hdmi": " / ".join(
                part
                for part in (
                    (d.get("versions") or {}).get("hdmi_card"),
                    (d.get("versions") or {}).get("hdmi_xmos"),
                )
                if part
            )
            or None,
            "hdmi_card": (d.get("versions") or {}).get("hdmi_card"),
            "hdmi_xmos": (d.get("versions") or {}).get("hdmi_xmos"),
            "hdmi_kernel": (d.get("versions") or {}).get("hdmi_kernel"),
            "front_panel": (d.get("versions") or {}).get("front_panel"),
            "front_panel_packaged": (d.get("versions") or {}).get(
                "front_panel_packaged"
            ),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Tide16Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [Tide16Sensor(coordinator, d) for d in SENSORS]
        + [
            (Tide16TableSensor if s.key in TABLE_STATES else Tide16SettingSensor)(
                coordinator, s
            )
            for s in of_kind(SENSOR)
        ]
        + [Tide16AutoDimTarget(coordinator)]
    )


class Tide16Sensor(Tide16Entity, SensorEntity):
    entity_description: Tide16SensorDescription

    def __init__(
        self, coordinator: Tide16Coordinator, description: Tide16SensorDescription
    ) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.always_available:
            return True
        return super().available

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)


class Tide16SettingSensor(Tide16Entity, SensorEntity):
    """A read-only field of `get_settings` - see settings.py.

    Everything the unit reports and nothing writes: the sample rate it is
    running at, the sub and dialog gains (which have no setter on this
    firmware), and the 16-wide tables, whose values are attributes rather than
    sixteen entities apiece.
    """

    def __init__(self, coordinator: Tide16Coordinator, setting: Tide16Setting) -> None:
        super().__init__(coordinator, setting.key, setting.name)
        self._setting = setting
        self._attr_entity_category = setting.category
        self._attr_native_unit_of_measurement = setting.unit
        self._attr_icon = setting.icon

    @property
    def _settings(self) -> dict[str, Any]:
        return self.coordinator.data.get("settings") or {}

    @property
    def native_value(self) -> Any:
        state = TABLE_STATES.get(self._setting.key)
        if state is not None:
            return state(self._settings)
        value = value_at(self._settings, self._setting.path)
        # A dict or a list is not a state; those rows carry their content in
        # the attributes and get their state from TABLE_STATES.
        return None if isinstance(value, (dict, list)) else value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._setting.attributes is None:
            return None
        return self._setting.attributes(self._settings)


class Tide16TableSensor(Tide16SettingSensor):
    """A 16-wide table, whose attributes the recorder is told not to store.

    These carry the whole block in their attributes - the PEQ is about 30 kB
    of it, the routing matrix about 19 - and the recorder refuses anything
    over 16 kB, so every write logged a warning and stored nothing:

        State attributes for sensor.tide16_parametric_eq exceed maximum size
        of 16384 bytes. Attributes will not be stored

    Saying so up front is what the warning is asking for.  The attributes are
    still live for templates, automations and the card; it is only the history
    that skips them, and a filter curve has no history worth keeping - it is
    configuration, and it changes when someone changes it.  The state is a
    count, so it is small, and it stays recorded.
    """

    # Keeps device class, state class, unit and friendly name; drops the rest.
    _unrecorded_attributes = frozenset({MATCH_ALL})


class Tide16AutoDimTarget(Tide16Entity, SensorEntity):
    """What the auto-dim ramp is aiming the display at right now.

    Unknown while auto dim is off, because then nothing is aiming at anything,
    and unknown on a day with no sunrise or sunset at all - which is the
    honest answer inside the polar circles rather than an invented one.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:brightness-percent"

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "auto_dim_target", "Auto Dim Target")

    @property
    def available(self) -> bool:
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.autodim.add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> int | None:
        return self.coordinator.autodim.target
