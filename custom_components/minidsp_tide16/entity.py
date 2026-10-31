"""Shared base for every Tide16 entity."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_IDENTIFIER,
    DEVICE_NAME,
    DOMAIN,
    LEGACY_UNIQUE_IDS,
    MANUFACTURER,
    MODEL,
)
from .coordinator import Tide16Coordinator
from .settings import Tide16Setting, value_at


def unique_id_for(key: str) -> str:
    """The registry identity of one entity, stable across versions."""
    return LEGACY_UNIQUE_IDS.get(key, f"{DOMAIN}_{key}")


class Tide16Entity(CoordinatorEntity[Tide16Coordinator]):
    """Device identity, availability and naming, in one place.

    `has_entity_name` with a fixed device name is what keeps the entity_ids
    the panel is written against - sensor.tide16_status, number.tide16_volume
    and the rest - stable whatever the user calls the device afterwards.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: Tide16Coordinator, key: str, name: str | None) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        # Not keyed on the host: an entity keeps its identity when the unit
        # changes address. Entities that existed in minidsp_tide16 0.x keep
        # their old unique_id - see const.LEGACY_UNIQUE_IDS.
        self._attr_unique_id = unique_id_for(key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DEVICE_IDENTIFIER)},
            name=DEVICE_NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{coordinator.host}:5050",
        )

    @property
    def available(self) -> bool:
        """Unavailable while the unit is away, so the panel dashes.

        Standby takes the Tide16 off the network entirely; a reading held over
        from before it went is worse than no reading, because the panel would
        print it as if it were current.
        """
        return self.coordinator.connected


# The unit accepts a write in about 3ms and applies it a few hundred
# milliseconds later - measured at ~570ms for the Dolby profile. Nothing
# pushes `get_settings`, so a read-back is the only confirmation there is, and
# one fired straight after the send reads the OLD value every time.
CONFIRM_INTERVAL = 0.25
CONFIRM_ATTEMPTS = 8  # 2s, comfortably past the ~570ms the unit takes


class Tide16SettingEntity(Tide16Entity):
    """An entity backed by one row of the settings table - see settings.py.

    Everything these have in common: where to read the value from, how to
    write it, and showing the requested value while the unit catches up so a
    toggle does not spring back under the finger.
    """

    def __init__(self, coordinator: Tide16Coordinator, setting: Tide16Setting) -> None:
        super().__init__(coordinator, setting.key, setting.name)
        self._setting = setting
        self._attr_entity_category = setting.category
        self._attr_icon = setting.icon
        self._pending: Any = None

    @property
    def _settings(self) -> dict[str, Any]:
        return self.coordinator.data.get("settings") or {}

    @property
    def _value(self) -> Any:
        """The value to display: what was asked for, else what the unit says."""
        if self._pending is not None:
            return self._pending
        return value_at(self._settings, self._setting.path)

    async def _write(self, value: Any) -> None:
        setting = self._setting
        if not setting.endpoint:
            return
        await self.coordinator.async_send(
            setting.endpoint, **setting.build(value, self._settings)
        )

        self._pending = value
        self.async_write_ha_state()
        try:
            for _ in range(CONFIRM_ATTEMPTS):
                await asyncio.sleep(CONFIRM_INTERVAL)
                await self.coordinator.async_refresh_settings()
                if value_at(self._settings, setting.path) == value:
                    break
        finally:
            # Dropped either way. If the unit never agreed - a firmware
            # without that endpoint, or a value it clamped - its own reading
            # stands rather than leaving a lie on screen.
            self._pending = None
            self.async_write_ha_state()
