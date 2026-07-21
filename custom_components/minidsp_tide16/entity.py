"""Shared base mixin for every Tide16 entity.

v16: previously each platform file (button/switch/number/sensor/
media_player/binary_sensor) duplicated the same device_info property and
dispatcher-update wiring. Factored out here, plus a new `available`
property tied to the coordinator's connection state - entities now show
as "unavailable" in Home Assistant when the Tide16 can't be reached
(standby, network issue, reconnecting) instead of silently keeping their
last-known value forever, which could otherwise look like a real reading.

Usage: mix this in FIRST, before the platform's own entity base class, so
its properties/methods aren't shadowed:

    class Tide16MuteSwitch(Tide16Entity, SwitchEntity):
        ...
"""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_TIDE16_UPDATE, tide16_device_info


class Tide16Entity:
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator

    @property
    def device_info(self):
        return tide16_device_info()

    @property
    def available(self) -> bool:
        """False whenever the coordinator can't reach the Tide16.

        Subclasses that should stay visible even when offline (e.g. the
        status sensor, which needs to be able to display "not connected")
        override this to return True unconditionally.
        """
        return bool(self._coordinator.data.get("connected"))

    async def async_added_to_hass(self) -> None:
        # v19: call the parent implementation first - good practice for
        # any entity that overrides this hook, and matters in particular
        # for platform base classes (e.g. RestoreEntity, used by some HA
        # entity types) that rely on their own async_added_to_hass()
        # running. This mixin is meant to be listed before the platform's
        # entity class (see the docstring above), so without this call
        # the platform class's own hook would never run.
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_TIDE16_UPDATE, self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
