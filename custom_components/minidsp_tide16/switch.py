"""Mute, Dirac Live, and every on/off setting the unit reports."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api.const import SET_DIRAC_STATE, SET_MUTE
from .const import DOMAIN
from .coordinator import Tide16Coordinator
from .entity import Tide16Entity, Tide16SettingEntity
from .settings import SWITCH, of_kind


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Tide16Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [Tide16Mute(coordinator), Tide16Dirac(coordinator)]
        + [Tide16SettingSwitch(coordinator, s) for s in of_kind(SWITCH)]
        + [Tide16AutoDimSwitch(coordinator), Tide16QuotesSwitch(coordinator)]
    )


class Tide16Mute(Tide16Entity, SwitchEntity):
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "mute", "Mute")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("muted")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(SET_MUTE, value=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(SET_MUTE, value=False)


class Tide16Dirac(Tide16Entity, SwitchEntity):
    """Dirac Live on/off.

    The unit reports a whole Dirac block - selected slot, gain and delay flags
    - but only `enabled` is settable from here, which is the switch the panel
    draws.
    """

    _attr_icon = "mdi:tune-variant"

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "dirac_live", "Dirac Live")

    @property
    def is_on(self) -> bool | None:
        return (self.coordinator.data.get("dirac") or {}).get("enabled")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dirac = self.coordinator.data.get("dirac") or {}
        return {
            "selected_slot": dirac.get("selected_slot"),
            "gain": dirac.get("gain"),
            "delay": dirac.get("delay"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(SET_DIRAC_STATE, enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(SET_DIRAC_STATE, enabled=False)


class Tide16SettingSwitch(Tide16SettingEntity, SwitchEntity):
    """One of the unit's on/off settings - see settings.py."""

    @property
    def is_on(self) -> bool | None:
        value = self._value
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(False)


class Tide16AutoDimSwitch(Tide16Entity, SwitchEntity, RestoreEntity):
    """Walk the display's brightness with the sun - see autodim.py.

    Restored across a restart rather than defaulted off: this is a preference,
    and a preference that quietly forgets itself every time Home Assistant
    updates is worse than one that was never offered.
    """

    _attr_icon = "mdi:brightness-auto"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "auto_dim", "Auto Dim")

    @property
    def available(self) -> bool:
        # The setting is ours, not the unit's: it can be changed while the
        # Tide16 is in standby, and takes effect when it comes back.
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            await self.coordinator.autodim.async_set(enabled=last.state == "on")
        self.async_on_remove(
            self.coordinator.autodim.add_listener(self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.autodim.enabled)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dim = self.coordinator.autodim
        return {"target_brightness": dim.target}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.autodim.async_set(enabled=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.autodim.async_set(enabled=False)
        self.async_write_ha_state()


class Tide16QuotesSwitch(Tide16Entity, SwitchEntity, RestoreEntity):
    """The idle panel's audiophile quotes, on or off.

    Nothing here reaches the unit. With the Tide16 in standby the meter window
    is dead space, and the card scrolls a line of audiophile nonsense across
    it rather than leaving a black hole in the middle of the plate. It is a
    joke, and a joke is exactly the kind of thing somebody wants turned off -
    so it is a switch rather than a card option, reachable from the plate
    itself and from a script, without anybody editing YAML.

    Restored across a restart for the same reason Auto Dim is: a preference
    that forgets itself every update is worse than one never offered.
    """

    _attr_icon = "mdi:comment-quote-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "idle_quotes", "Audiophile Quotes")
        # On is how the panel has always behaved, so that is the default for
        # anyone who never touches this.
        self._on = True

    @property
    def available(self) -> bool:
        # The quotes are only ever on screen while the unit is AWAY, so a
        # switch that followed the unit's availability would be unavailable
        # at precisely the moment somebody reaches for it.
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self._on = last.state == "on"

    @property
    def is_on(self) -> bool:
        return self._on

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._on = False
        self.async_write_ha_state()
