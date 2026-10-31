"""The Tide16 as a media player: source, volume, mute, power off.

Two deliberate choices here, both of which the front panel depends on:

* **It reports `off`, never `unavailable`.**  Standby takes the unit off the
  network, so "I cannot reach it" and "it is off" are the same fact - and a
  panel that wants to show a reboot in progress needs a state it can watch,
  not an entity that vanishes.
* **The input table rides along as an attribute.**  `sources` carries every
  input's live name and the device's own `hidden` flag, so a dashboard can grey
  out the inputs this unit is not using and follow a rename without a card
  edit.  It used to take a python script on a `command_line` sensor to get it.

Merged from minidsp_tide16 0.x (v1.0.0):

* unique_id minidsp_tide16_media_player_v2, so the entity stays
  media_player.tide16 and HomeKit keeps the same receiver accessory;
* VOLUME_STEP: volume_up/volume_down go through the coordinator's
  async_nudge_volume, shared with the Volume Up/Down buttons, so rapid presses
  from the iPhone, the HomeKit remote and the dashboard accumulate;
* the input list hides the inputs the unit itself marks hidden, falls back to
  built-in names until the unit has sent its own, and disambiguates two inputs
  given the same name ("Apple TV (hdmi1)").

There is no turn_on, and there cannot be: standby tears down the network stack,
so nothing this integration can reach is still listening once the unit is off.
Only an IR remote can wake it.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.const import MAX_VOLUME_DB, MIN_VOLUME_DB, SET_MUTE, SET_SOURCE, SHUTDOWN
from .const import DOMAIN, SOURCE_ID_TO_LABEL, VOLUME_STEP_DB
from .coordinator import Tide16Coordinator
from .entity import Tide16Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Tide16Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Tide16MediaPlayer(coordinator)])


def source_labels(data: dict[str, Any]) -> dict[str, str]:
    """{source_id: display name} for every input that is not hidden.

    Order: the unit's own (get_settings `sources`), else the order of its
    names, else the built-in table. Names the unit has not sent yet fall back
    to the built-in ones. Two inputs with the same name get their id appended,
    so each stays selectable by name.
    """
    names: dict[str, str] = dict(data.get("source_names") or {})
    table: dict[str, dict[str, Any]] = data.get("sources") or {}
    if table:
        ids = [sid for sid, entry in table.items() if not entry.get("hidden")]
    elif names:
        ids = list(names)
    else:
        ids = list(SOURCE_ID_TO_LABEL)
    raw = {
        sid: names.get(sid)
        or (table.get(sid) or {}).get("name")
        or SOURCE_ID_TO_LABEL.get(sid, sid)
        for sid in ids
    }
    counts: dict[str, int] = {}
    for name in raw.values():
        counts[name] = counts.get(name, 0) + 1
    return {
        sid: name if counts[name] == 1 else f"{name} ({sid})"
        for sid, name in raw.items()
    }


def resolve_source_id(data: dict[str, Any], source: str) -> str | None:
    """A display name (plain or disambiguated) or an id, back to the id."""
    labels = source_labels(data)
    for sid, label in labels.items():
        if label == source:
            return sid
    for sid, name in (data.get("source_names") or {}).items():
        if name == source:
            return sid
    if source in labels or source in (data.get("source_names") or {}):
        return source
    if source in SOURCE_ID_TO_LABEL:
        return source
    return None


class Tide16MediaPlayer(Tide16Entity, MediaPlayerEntity):
    # RECEIVER is what makes HomeKit Bridge expose it as an AV receiver.
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        # name None makes this the device's own entity: media_player.tide16
        super().__init__(coordinator, "media_player", None)

    @property
    def available(self) -> bool:
        return True

    @property
    def state(self) -> MediaPlayerState:
        return (
            MediaPlayerState.ON if self.coordinator.connected else MediaPlayerState.OFF
        )

    @property
    def source(self) -> str | None:
        data = self.coordinator.data
        source_id = data.get("source_id")
        if source_id is None:
            return None
        labels = source_labels(data)
        if source_id in labels:
            return labels[source_id]
        return (data.get("source_names") or {}).get(source_id) or SOURCE_ID_TO_LABEL.get(
            source_id, source_id
        )

    @property
    def source_list(self) -> list[str]:
        return list(source_labels(self.coordinator.data).values())

    @property
    def volume_level(self) -> float | None:
        # Linear over the dB range (-127.5 dB = 0, 0 dB = 1), the same scale
        # as number.tide16_volume - not the physical gain, which would pin
        # every listening level near 0 %.
        db = self.coordinator.data.get("volume_db")
        if db is None:
            return None
        return round(
            max(0.0, min(1.0, (float(db) - MIN_VOLUME_DB) / (MAX_VOLUME_DB - MIN_VOLUME_DB))),
            4,
        )

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.data.get("muted")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "volume_db": data.get("volume_db"),
            "status": data.get("status"),
            "source_id": data.get("source_id"),
            # The preset id sits beside the source id for the same reason:
            # the number the unit knows it by, next to the name a person
            # reads.
            "preset_id": data.get("preset_index"),
            # {id: {name, hidden, volume_offset}} straight off the device
            "sources": data.get("sources") or {},
        }

    async def async_select_source(self, source: str) -> None:
        """Sources are selected by id; the panel only knows display names."""
        source_id = resolve_source_id(self.coordinator.data, source)
        if source_id is not None:
            await self.coordinator.async_send(SET_SOURCE, value=source_id)

    async def async_set_volume_level(self, volume: float) -> None:
        volume = max(0.0, min(1.0, volume))
        await self.coordinator.async_set_volume_db(
            MIN_VOLUME_DB + volume * (MAX_VOLUME_DB - MIN_VOLUME_DB)
        )

    async def async_volume_up(self) -> None:
        await self.coordinator.async_nudge_volume(VOLUME_STEP_DB)

    async def async_volume_down(self) -> None:
        await self.coordinator.async_nudge_volume(-VOLUME_STEP_DB)

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_send(SET_MUTE, value=mute)

    async def async_turn_off(self) -> None:
        """A press while it is already off is a no-op, not an error."""
        if self.coordinator.connected:
            await self.coordinator.async_send(SHUTDOWN)
