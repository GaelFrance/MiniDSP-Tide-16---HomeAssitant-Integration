"""Tide16 read-only sensors.

v15 added Bluetooth pairing/track info, incoming stream info, the device's
IP address, its speaker layout, and the active preset name. v16 makes all
sensors unavailable when the Tide16 is unreachable (see entity.py) -
except Status, which stays visible on purpose so it can actually display
"not connected".

v21 fix: `SensorEntityCategory` (from homeassistant.components.sensor) was
a long-deprecated alias for the platform-agnostic `EntityCategory` (from
homeassistant.helpers.entity), kept around for backwards compatibility for
years - removed entirely in newer Home Assistant releases, which broke
this module's import with "cannot import name 'SensorEntityCategory'".
Since importing one platform module fails the whole
async_forward_entry_setups() call for ALL platforms at once, this alone
was enough to make the entire integration fail to set up. Switched to the
current, non-deprecated EntityCategory import.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SOURCE_ID_TO_LABEL
from .entity import Tide16Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            Tide16StatusSensor(coordinator),
            Tide16ChannelLevelsSensor(coordinator),
            Tide16SourceSensor(coordinator),
            Tide16BluetoothSensor(coordinator),
            Tide16StreamSensor(coordinator),
            Tide16IpSensor(coordinator),
            Tide16SpeakerConfigSensor(coordinator),
            Tide16PresetSensor(coordinator),
        ]
    )


class _Tide16Sensor(Tide16Entity, SensorEntity):
    _object_id = "override_me"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = f"sensor.{self._object_id}"


class Tide16StatusSensor(_Tide16Sensor):
    _attr_name = "Status"
    _attr_unique_id = "minidsp_tide16_status"
    _attr_icon = "mdi:information-outline"
    _object_id = "tide16_status"

    @property
    def available(self) -> bool:
        # Deliberately always available: this is the one entity whose job
        # is to tell you the Tide16 is unreachable, so it needs to keep
        # showing "not connected" rather than going unavailable itself.
        return True

    @property
    def native_value(self) -> str | None:
        return self._coordinator.data.get("status")


class Tide16ChannelLevelsSensor(_Tide16Sensor):
    """Per-channel output levels for the front-panel bar meter (v22).

    The 16 values live in an attribute rather than in 16 separate sensors
    on purpose: the card wants them as one coherent frame, and while the
    meter is being watched this updates 4x/sec - one entity churning at
    that rate is very different from sixteen.

    `channel_names` is the speaker assigned to each output, positionally
    aligned with `channels`, with None for outputs the device has not
    assigned. It is shorter than `channels` whenever the layout uses
    fewer than 16 outputs - zip() the two rather than indexing blindly.

    The state itself is the peak, rounded to whole dB. That rounding is
    load-bearing: the state is what the recorder would store, and an
    unrounded peak changes on essentially every single poll. The attribute
    carries the real precision for the card.

    EXCLUDE THIS FROM THE RECORDER - see the recorder: block in
    configuration.yaml. Nothing here is worth 4 rows/sec of database.
    """

    _attr_name = "Channel Levels"
    _attr_unique_id = "minidsp_tide16_channel_levels"
    _attr_icon = "mdi:chart-bar"
    _attr_native_unit_of_measurement = "dB"
    _object_id = "tide16_channel_levels"

    @property
    def native_value(self) -> float | None:
        peak = self._coordinator.data.get("signal_peak_db")
        return None if peak is None else round(peak)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "channels": self._coordinator.data.get("channel_db"),
            "channel_names": self._coordinator.data.get("channel_names"),
            "peak_db": self._coordinator.data.get("signal_peak_db"),
        }


class Tide16SourceSensor(_Tide16Sensor):
    _attr_name = "Source"
    _attr_unique_id = "minidsp_tide16_source"
    _attr_icon = "mdi:import"
    _object_id = "tide16_source"

    @property
    def native_value(self) -> str | None:
        source_id = self._coordinator.data.get("source")
        if source_id is None:
            return None
        live_name = self._coordinator.data.get("source_names", {}).get(source_id)
        return live_name or SOURCE_ID_TO_LABEL.get(source_id, source_id)


class Tide16BluetoothSensor(_Tide16Sensor):
    """Bluetooth pairing state + now-playing track, from get_bluetooth_status
    / the bluetooth_status notification."""

    _attr_name = "Bluetooth"
    _attr_unique_id = "minidsp_tide16_bluetooth"
    _attr_icon = "mdi:bluetooth-audio"
    _object_id = "tide16_bluetooth"

    @property
    def native_value(self) -> str | None:
        paired = self._coordinator.data.get("bt_paired")
        if paired is None:
            return None
        if not paired:
            return "not_paired"
        return "playing" if self._coordinator.data.get("bt_track_playing") else "paired"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "paired": self._coordinator.data.get("bt_paired"),
            "playing": self._coordinator.data.get("bt_track_playing"),
            "title": self._coordinator.data.get("bt_track_title"),
            "artist": self._coordinator.data.get("bt_track_artist"),
            "album": self._coordinator.data.get("bt_track_album"),
        }


class Tide16StreamSensor(_Tide16Sensor):
    """Incoming audio stream info, from get_stream_properties / the
    stream_changes notification."""

    _attr_name = "Stream"
    _attr_unique_id = "minidsp_tide16_stream"
    _attr_icon = "mdi:waveform"
    _object_id = "tide16_stream"

    @property
    def native_value(self) -> str | None:
        return self._coordinator.data.get("stream_format") or "No signal"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "channel_config": self._coordinator.data.get("stream_channel_config"),
            "sample_rate": self._coordinator.data.get("stream_sample_rate"),
            "decoder_type": self._coordinator.data.get("stream_decoder_type"),
        }


class Tide16IpSensor(_Tide16Sensor):
    """Device's wired IP address, from get_ip. Diagnostic-only, no push
    notification for this one - fetched once at connect."""

    _attr_name = "IP Address"
    _attr_unique_id = "minidsp_tide16_ip_address"
    _attr_icon = "mdi:ip-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _object_id = "tide16_ip_address"

    @property
    def native_value(self) -> str | None:
        return self._coordinator.data.get("ip_address")


class Tide16SpeakerConfigSensor(_Tide16Sensor):
    """Speaker layout (e.g. "5.1", "9.1.6"), from get_speaker_config_number."""

    _attr_name = "Speaker Config"
    _attr_unique_id = "minidsp_tide16_speaker_config"
    _attr_icon = "mdi:speaker-multiple"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _object_id = "tide16_speaker_config"

    @property
    def native_value(self) -> str | None:
        return self._coordinator.data.get("speaker_config")


class Tide16PresetSensor(_Tide16Sensor):
    """Active preset name, from get_current_preset_index + get_all_presets
    (to resolve the name) / the preset_change notification (which carries
    both index and name directly)."""

    _attr_name = "Preset"
    _attr_icon = "mdi:tune-variant"
    _attr_unique_id = "minidsp_tide16_preset"
    _object_id = "tide16_preset"

    @property
    def native_value(self) -> str | None:
        name = self._coordinator.data.get("preset_name")
        if name:
            return name
        index = self._coordinator.data.get("preset_index")
        return f"Preset {index}" if index is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        return {"preset_index": self._coordinator.data.get("preset_index")}
