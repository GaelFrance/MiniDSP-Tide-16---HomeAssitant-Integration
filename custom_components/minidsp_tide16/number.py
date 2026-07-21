"""Tide16 volume slider (native dB, matches the device's own get/set_volume_db)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_VOLUME_DB, MIN_VOLUME_DB
from .entity import Tide16Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Tide16VolumeNumber(coordinator)])


class Tide16VolumeNumber(Tide16Entity, NumberEntity):
    _attr_name = "Volume"
    _attr_unique_id = "minidsp_tide16_volume"
    _attr_icon = "mdi:volume-high"
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "dB"
    _attr_native_min_value = MIN_VOLUME_DB
    _attr_native_max_value = MAX_VOLUME_DB
    _attr_native_step = 0.5  # API accepts decimal dB values

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = "number.tide16_volume"

    @property
    def native_value(self) -> float | None:
        return self._coordinator.data.get("volume_db")

    async def async_set_native_value(self, value: float) -> None:
        await self._coordinator.async_set_volume_db(value)
