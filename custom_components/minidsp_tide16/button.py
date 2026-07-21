"""Tide16 buttons: sources, volume +/-, shutdown, reboot, Bluetooth pair.

Every entity_id is set explicitly (self.entity_id = ...) instead of relying
on Home Assistant's has_entity_name auto-slugging. That auto-slugging
turned out to not match what was assumed when the dashboards were written
(entities showed up as "Entite non trouvee"), so pinning the exact id here
keeps the dashboards matching reality on first creation. In practice, once
an entity is registered, Home Assistant's entity registry is what actually
decides the entity_id on every subsequent restart (keyed by unique_id) -
self.entity_id here only matters the first time. Unique_id, not this
line, is the real long-term identity of each entity.
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SOURCE_LABEL_TO_ID, VOLUME_STEP_DB, slugify_label
from .entity import Tide16Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [
        Tide16ShutdownButton(coordinator),
        Tide16RebootButton(coordinator),
        Tide16BluetoothPairButton(coordinator),
        Tide16VolumeUpButton(coordinator),
        Tide16VolumeDownButton(coordinator),
    ]
    entities += [
        Tide16SourceButton(coordinator, label, source_id)
        for label, source_id in SOURCE_LABEL_TO_ID.items()
    ]
    async_add_entities(entities)


class _Tide16Button(Tide16Entity, ButtonEntity):
    _object_id = "override_me"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self.entity_id = f"button.{self._object_id}"


class Tide16ShutdownButton(_Tide16Button):
    _attr_name = "Shutdown"
    _attr_unique_id = "minidsp_tide16_shutdown"
    _attr_icon = "mdi:power"
    _object_id = "tide16_shutdown"

    async def async_press(self) -> None:
        await self._coordinator.async_shutdown()


class Tide16RebootButton(_Tide16Button):
    _attr_name = "Reboot"
    _attr_unique_id = "minidsp_tide16_reboot"
    _attr_icon = "mdi:restart"
    _object_id = "tide16_reboot"

    async def async_press(self) -> None:
        await self._coordinator.async_reboot()


class Tide16BluetoothPairButton(_Tide16Button):
    _attr_name = "Bluetooth Pair"
    _attr_unique_id = "minidsp_tide16_bt_pair"
    _attr_icon = "mdi:bluetooth"
    _object_id = "tide16_bluetooth_pair"

    async def async_press(self) -> None:
        await self._coordinator.async_bluetooth_pair()


class Tide16VolumeUpButton(_Tide16Button):
    _attr_name = "Volume Up"
    _attr_unique_id = "minidsp_tide16_volume_up"
    _attr_icon = "mdi:volume-plus"
    _object_id = "tide16_volume_up"

    async def async_press(self) -> None:
        await self._coordinator.async_nudge_volume(VOLUME_STEP_DB)


class Tide16VolumeDownButton(_Tide16Button):
    _attr_name = "Volume Down"
    _attr_unique_id = "minidsp_tide16_volume_down"
    _attr_icon = "mdi:volume-minus"
    _object_id = "tide16_volume_down"

    async def async_press(self) -> None:
        await self._coordinator.async_nudge_volume(-VOLUME_STEP_DB)


class Tide16SourceButton(_Tide16Button):
    _attr_icon = "mdi:import"

    def __init__(self, coordinator, label: str, source_id: str) -> None:
        self._source_id = source_id
        self._fallback_label = label
        slug = slugify_label(label)
        self._object_id = f"tide16_source_{slug}"
        super().__init__(coordinator)
        self._attr_unique_id = f"minidsp_tide16_source_{slug}"

    @property
    def name(self) -> str:
        # v16: prefer the live display name from get_source_names /
        # source_names_change (whatever's actually configured on the
        # device right now) over the fallback label baked in at build
        # time - entity_id/unique_id above are unaffected either way.
        live_name = self._coordinator.data.get("source_names", {}).get(self._source_id)
        return f"Source: {live_name or self._fallback_label}"

    async def async_press(self) -> None:
        await self._coordinator.async_select_source(self._source_id)
