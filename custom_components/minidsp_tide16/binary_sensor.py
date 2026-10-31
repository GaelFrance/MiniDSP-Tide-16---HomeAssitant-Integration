"""Atmos, audio signal, Dirac measuring, firmware update."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import Tide16Coordinator
from .entity import Tide16Entity
from .settings import BINARY, Tide16Setting, of_kind, value_at


@dataclass(frozen=True, kw_only=True)
class Tide16BinaryDescription(BinarySensorEntityDescription):
    value: Callable[[dict[str, Any]], bool | None]
    attributes: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    always_available: bool = False


def _atmos(data: dict[str, Any]) -> bool:
    """Atmos is not a flag the unit sets - it is a word in what it decoded.

    Both the source format and the decoder name are checked, because which one
    names it depends on how the stream arrived.

    The negations have to go first, and this is not hypothetical: the unit
    reports "Dolby Digital Plus without Dolby Atmos" for a plain DD+ stream,
    and a plain substring test lights the Atmos badge on exactly the stream
    that is telling you it has none.
    """
    stream = data.get("stream") or {}
    haystack = " ".join(
        str(stream.get(field) or "")
        for field in ("decoder_stream_src_format", "decoder_type", "decoder_stream_type")
    ).lower()
    for denial in ("without dolby atmos", "without atmos", "no atmos"):
        haystack = haystack.replace(denial, "")
    return "atmos" in haystack


def _upmixed(data: dict[str, Any]) -> bool:
    """Whether the output is an UPMIX rather than what arrived.

    The unit's own panel prints "Upmixed" under the output layout only when
    this is set, and nothing at all otherwise - a native Atmos bitstream is
    decoded to 7.2.4, not upmixed to it, and the panel says nothing.

    Inferring it from the selected upmixer is wrong for exactly that case: the
    upmixer can be Dolby while the stream needs no upmixing at all.
    """
    return bool((data.get("stream") or {}).get("is_lpcm_upmixed"))


def _version_key(text: str) -> tuple[int, ...] | None:
    """'1.11' as (1, 11), so 1.11 sorts after 1.9; None if it is not numeric."""
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError:
        return None


def _front_panel_behind(data: dict[str, Any]) -> bool | None:
    """Whether the front panel runs older firmware than the Tide carries for it.

    No server is involved: the Tide firmware packages the front panel's, and
    installing it is a separate step on the unit's own page.  So this can be
    true with the server saying there is nothing new.

    Strictly older, not merely different: a front panel AHEAD of the package -
    flashed from a beta, say - has nothing to install, and saying otherwise is
    a false alarm.  A version that does not read as numbers is None.
    """
    versions = data.get("versions") or {}
    installed = versions.get("front_panel")
    packaged = versions.get("front_panel_packaged")
    if installed is None or packaged is None:
        return None
    have, ship = _version_key(installed), _version_key(packaged)
    if have is None or ship is None:
        return None
    return ship > have


def _firmware_update(data: dict[str, Any]) -> bool | None:
    """On if anything has something newer; off only if everything is known."""
    tide = (data.get("update_check") or {}).get("available")
    front_panel = _front_panel_behind(data)
    if tide or front_panel:
        return True
    if tide is None or front_panel is None:
        return None
    return False


def _firmware_update_attributes(data: dict[str, Any]) -> dict[str, Any]:
    versions = data.get("versions") or {}
    check = data.get("update_check") or {}
    return {
        "tide": versions.get("tide"),
        "hdmi_card": versions.get("hdmi_card"),
        "hdmi_xmos": versions.get("hdmi_xmos"),
        "hdmi_kernel": versions.get("hdmi_kernel"),
        "front_panel": versions.get("front_panel"),
        "front_panel_packaged": versions.get("front_panel_packaged"),
        "tide_update_available": check.get("available"),
        "front_panel_update_available": _front_panel_behind(data),
        # the server's answer word for word, since what it says when there IS
        # an update has not been seen yet
        "server_result": check.get("result"),
        "checked_at": check.get("checked_at"),
    }


BINARY_SENSORS: tuple[Tide16BinaryDescription, ...] = (
    Tide16BinaryDescription(key="atmos", name="Atmos", value=_atmos),
    Tide16BinaryDescription(key="upmixed", name="Upmixed", value=_upmixed),
    Tide16BinaryDescription(
        key="bitstream",
        name="Bitstream",
        # Two different signal paths with two different gain stagings, and the
        # meter has to scale for whichever one is running - see tide16-bars.
        value=lambda d: bool((d.get("stream") or {}).get("is_bitstream")),
    ),
    Tide16BinaryDescription(
        key="audio_signal",
        name="Audio Signal",
        # The only entity fed by metering, and it follows the envelope rather
        # than the sample: it lights the moment audio starts and clears only
        # after several seconds with none - see _apply_signal in the
        # coordinator. Compared to the master volume (minidsp_tide16 0.30):
        # level_db = peak_db - volume, threshold_db is what it must clear.
        device_class=BinarySensorDeviceClass.SOUND,
        value=lambda d: bool(d.get("signal")),
        attributes=lambda d: {
            "peak_db": d.get("signal_peak_db"),
            "level_db": d.get("signal_level_db"),
            "threshold_db": d.get("signal_threshold_db"),
        },
    ),
    Tide16BinaryDescription(
        key="dirac_measuring",
        name="Dirac Measuring",
        value=lambda d: d.get("dirac_measuring"),
    ),
    Tide16BinaryDescription(
        key="firmware_update",
        name="Firmware Update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Checked hourly, and the answer holds while the unit is in standby -
        # nothing can be installed on a unit that is off.
        always_available=True,
        value=_firmware_update,
        attributes=_firmware_update_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Tide16Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [Tide16BinarySensor(coordinator, d) for d in BINARY_SENSORS]
        + [Tide16SettingBinary(coordinator, s) for s in of_kind(BINARY)]
    )


class Tide16BinarySensor(Tide16Entity, BinarySensorEntity):
    entity_description: Tide16BinaryDescription

    def __init__(
        self, coordinator: Tide16Coordinator, description: Tide16BinaryDescription
    ) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.always_available:
            return True
        return super().available

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)


class Tide16SettingBinary(Tide16Entity, BinarySensorEntity):
    """A read-only flag out of `get_settings` - see settings.py."""

    def __init__(self, coordinator: Tide16Coordinator, setting: Tide16Setting) -> None:
        super().__init__(coordinator, setting.key, setting.name)
        self._setting = setting
        self._attr_entity_category = setting.category
        self._attr_icon = setting.icon

    @property
    def is_on(self) -> bool | None:
        value = value_at(self.coordinator.data.get("settings") or {}, self._setting.path)
        return None if value is None else bool(value)
