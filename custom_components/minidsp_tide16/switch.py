"""Tide16 switches: mute (original) + Dirac Live enable (v15, new)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import Tide16Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Tide16MuteSwitch(coordinator), Tide16DiracSwitch(coordinator)])


class Tide16MuteSwitch(Tide16Entity, SwitchEntity):
    """A toggle switch is used instead of a plain button so the current mute
    state is visible on the dashboard, not just togglable."""

    _attr_name = "Mute"
    _attr_unique_id = "minidsp_tide16_mute"
    _attr_icon = "mdi:volume-mute"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = "switch.tide16_mute"

    @property
    def is_on(self) -> bool | None:
        return self._coordinator.data.get("muted")

    async def async_turn_on(self, **kwargs) -> None:
        await self._coordinator.async_set_mute(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_set_mute(False)


class Tide16DiracSwitch(Tide16Entity, SwitchEntity):
    """Enable/disable Dirac Live room correction (set_dirac_state /
    get_dirac_state / the dirac_state notification). New in v15, now that
    miniDSP's official docs confirm this endpoint."""

    _attr_name = "Dirac Live"
    _attr_unique_id = "minidsp_tide16_dirac_live"
    _attr_icon = "mdi:auto-fix"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = "switch.tide16_dirac_live"

    @property
    def is_on(self) -> bool | None:
        return self._coordinator.data.get("dirac_enabled")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "selected_slot": self._coordinator.data.get("dirac_selected_slot"),
            "gain_correction": self._coordinator.data.get("dirac_gain"),
            "delay_correction": self._coordinator.data.get("dirac_delay"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self._coordinator.async_set_dirac_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_set_dirac_enabled(False)
