"""Tide16 binary sensors: audio signal detection (original) + Dirac Live
measuring mode (v15, new).

Audio signal detection watches get_rms_block_db, which is NOT pushed
automatically (unlike most other state - see coordinator.py) so the
coordinator actively re-requests it on a timer. Per miniDSP's official
docs, only the "out" (post-DSP output) array is populated with live data,
the "in" array is not - so only "out" is used here. If the loudest output
channel is above SIGNAL_THRESHOLD_DB, a real signal is considered present.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_THRESHOLD_DB
from .entity import Tide16Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            Tide16AudioSignalBinarySensor(coordinator),
            Tide16DiracMeasuringBinarySensor(coordinator),
        ]
    )


class Tide16AudioSignalBinarySensor(Tide16Entity, BinarySensorEntity):
    _attr_name = "Audio Signal"
    _attr_unique_id = "minidsp_tide16_audio_signal"
    _attr_device_class = BinarySensorDeviceClass.SOUND

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = "binary_sensor.tide16_audio_signal"

    @property
    def is_on(self) -> bool | None:
        peak = self._coordinator.data.get("signal_peak_db")
        if peak is None:
            return None
        return peak > SIGNAL_THRESHOLD_DB

    @property
    def extra_state_attributes(self) -> dict:
        return {"peak_db": self._coordinator.data.get("signal_peak_db")}


class Tide16DiracMeasuringBinarySensor(Tide16Entity, BinarySensorEntity):
    """True while the Tide16 is playing Dirac Live calibration sweeps - a
    good condition to gate automations that would otherwise interfere
    (e.g. don't auto-switch source or nudge volume during a measurement).
    From get_dirac_measuring_mode / the dirac_measurement_mode
    notification."""

    _attr_name = "Dirac Measuring"
    _attr_unique_id = "minidsp_tide16_dirac_measuring"
    _attr_icon = "mdi:tune-variant"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = "binary_sensor.tide16_dirac_measuring"

    @property
    def is_on(self) -> bool | None:
        return self._coordinator.data.get("dirac_measuring")
