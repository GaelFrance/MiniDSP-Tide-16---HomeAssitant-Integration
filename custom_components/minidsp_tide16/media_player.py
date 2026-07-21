"""Tide16 media_player entity: power (via shutdown), volume, mute, source.

Kept alongside the individual button/switch/number entities (both are
kept - this gives a compact all-in-one control for cards like
"media-control", while the individual entities remain for granular
dashboard tiles/automations).

entity_id is set explicitly to avoid the sticky-entity-registry trap that
bit the other entities early on - see button.py's docstring for the full
story; unique_id, not this line, is what Home Assistant actually treats
as this entity's long-term identity across restarts.

v22 fix (part 1): volume_level used to read straight from the
coordinator's "volume_linear" field, kept in sync by a separate channel
(the get_volume request/volume_change notification) from the "volume_db"
field that every other volume-related entity (number.tide16_volume, the
volume +/- buttons) relies on exclusively - and which was confirmed, in
practice, to update reliably and near-instantly on every change.
"volume_linear" only got refreshed by the 60s safety-net resync in
between, since every command this integration ever sends goes through
the documented set_volume_db endpoint, never the linear one - so there
was no guarantee the Tide16 pushed a fresh volume_change (linear)
notification for a change that was requested in dB.

v22 fix (part 2, same day - the first pass wasn't the whole story): even
after deriving volume_level from volume_db, it was still converted via
the physical gain formula linear = 10**(db/20) - mathematically the
correct inverse of the dB<->gain relationship, but a bad fit for a UI
slider. That formula compresses almost the entire useful dB range into
a sliver near 0%: -43 dB (an ordinary listening level) is already down
at ~0.7%, so the slider looked pinned to the far left no matter the
actual volume, and small drags produced huge dB jumps. volume_level now
maps the dB range LINEARLY to 0.0-1.0 instead (same scale
number.tide16_volume already uses) - -127.5 dB -> 0%, 0 dB -> 100%,
-43 dB -> ~66% - so both volume controls in this integration now move in
lockstep. This does change what a given volume_level fraction MEANS
compared to pre-v22 (it's a position in the dB range now, not a linear
amplitude gain) - noted here in case anything external (HomeKit, an
automation) was reading media_player.tide16's volume percentage
expecting the old scale.

The now-unused linear-gain plumbing (volume_linear, get_volume,
async_set_volume_linear) has been removed from coordinator.py - nothing
else in this integration ever used it.
"""
from __future__ import annotations

import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_VOLUME_DB, MIN_VOLUME_DB, SOURCE_ID_TO_LABEL, SOURCE_LABEL_TO_ID
from .entity import Tide16Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Tide16MediaPlayer(coordinator)])


class Tide16MediaPlayer(Tide16Entity, MediaPlayerEntity):
    _attr_name = None  # represents the device itself -> entity_id media_player.tide16
    _attr_unique_id = "minidsp_tide16_media_player_v2"
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = "media_player.tide16"

    @property
    def available(self) -> bool:
        # Unlike most entities, media_player.tide16's whole job is to
        # report on/off - "unavailable" would defeat that purpose, since
        # "unreachable" and "off" are the same thing for this device (it
        # fully drops off the network in standby). Same reasoning as
        # sensor.tide16_status.
        return True

    @property
    def state(self) -> MediaPlayerState:
        return (
            MediaPlayerState.ON
            if self._coordinator.data.get("connected")
            else MediaPlayerState.OFF
        )

    @property
    def volume_level(self) -> float | None:
        # v22: derived from volume_db (see the module docstring), mapped
        # LINEARLY over the dB range - not the physical gain formula -
        # so this slider tracks number.tide16_volume's position exactly.
        db = self._coordinator.data.get("volume_db")
        if db is None:
            return None
        return max(0.0, min(1.0, (db - MIN_VOLUME_DB) / (MAX_VOLUME_DB - MIN_VOLUME_DB)))

    @property
    def is_volume_muted(self) -> bool | None:
        return self._coordinator.data.get("muted")

    @property
    def source(self) -> str | None:
        source_id = self._coordinator.data.get("source")
        if source_id is None:
            return None
        return self._source_labels().get(source_id, source_id)

    @property
    def source_list(self) -> list[str]:
        labels = self._source_labels()
        return [labels[source_id] for source_id in SOURCE_LABEL_TO_ID.values()]

    def _source_labels(self) -> dict[str, str]:
        """source_id -> display label, preferring the live name from
        get_source_names/source_names_change over the fallback baked in
        at build time (falls back to it if live names haven't loaded
        yet). Disambiguated with the source id itself for any names that
        collide - e.g. if you've renamed both HDMI 1 and HDMI 2 to "Apple
        TV" on the device, they show up as "Apple TV (hdmi1)" and
        "Apple TV (hdmi2)" instead of two identical, unselectable-by-name
        dropdown entries."""
        live_names = self._coordinator.data.get("source_names") or {}
        raw = {
            source_id: live_names.get(source_id) or SOURCE_ID_TO_LABEL.get(source_id, source_id)
            for source_id in SOURCE_LABEL_TO_ID.values()
        }
        counts: dict[str, int] = {}
        for name in raw.values():
            counts[name] = counts.get(name, 0) + 1
        return {
            source_id: name if counts[name] == 1 else f"{name} ({source_id})"
            for source_id, name in raw.items()
        }

    def _resolve_source_id(self, source_label: str) -> str:
        """Map a source_list entry (possibly disambiguated) back to its
        stable source id."""
        for source_id, label in self._source_labels().items():
            if label == source_label:
                return source_id
        return source_label  # already a raw id, or unrecognized - let the
        # coordinator's own validation reject it if so.

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "volume_db": self._coordinator.data.get("volume_db"),
            "status": self._coordinator.data.get("status"),
            "source_id": self._coordinator.data.get("source"),
        }

    async def async_set_volume_level(self, volume: float) -> None:
        # v22: same linear-over-dB-range mapping as volume_level above,
        # inverted - sent straight to async_set_volume_db (which already
        # clamps to MIN/MAX_VOLUME_DB), no linear-gain conversion.
        volume = max(0.0, min(1.0, volume))
        db = MIN_VOLUME_DB + volume * (MAX_VOLUME_DB - MIN_VOLUME_DB)
        await self._coordinator.async_set_volume_db(db)

    async def async_mute_volume(self, mute: bool) -> None:
        await self._coordinator.async_set_mute(mute)

    async def async_select_source(self, source: str) -> None:
        await self._coordinator.async_select_source(self._resolve_source_id(source))

    async def async_turn_off(self) -> None:
        """Mapped to the Tide16 'shutdown' (standby) command."""
        await self._coordinator.async_shutdown()
