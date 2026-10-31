"""The unit's multiple-choice controls: Dolby profile, upmixer, filter preset.

The Dolby profile is read from `get_settings` -> dolby.profile and written
with `set_dolby_profile`.  Both used to be a python script shelled out to by a
`command_line` sensor and a `shell_command`, because no integration spoke
either one.

`set_dolby_profile` is not in the endpoint list the unit's own control page
publishes - it was found by watching the device - so a firmware that does not
have it simply will not change, and the read-back is what tells us.
"""

from __future__ import annotations

import asyncio

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.const import (
    GET_PRESET_INDEX,
    SET_DOLBY_PROFILE,
    SET_FORCED_UPMIXER,
    SET_PRESET,
)
from .const import DOLBY_PROFILES, DOMAIN, UPMIXERS
from .coordinator import Tide16Coordinator
from .entity import Tide16Entity, Tide16SettingEntity
from .settings import SELECT, Tide16Setting, of_kind


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Tide16Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            Tide16DolbyProfile(coordinator),
            Tide16Upmixer(coordinator),
            Tide16Preset(coordinator),
        ]
        + [Tide16SettingSelect(coordinator, s) for s in of_kind(SELECT)]
    )


# Measured on the unit: it accepts the frame in about 3ms and the profile
# actually changes about 570ms later. A single read-back fired straight after
# the send therefore reads the OLD value every time.
CONFIRM_INTERVAL = 0.25
CONFIRM_ATTEMPTS = 12  # 3s, comfortably past the ~570ms the unit takes


class Tide16DolbyProfile(Tide16Entity, SelectEntity):
    _attr_options = list(DOLBY_PROFILES)  # noqa: RUF012 - HA reads a list
    _attr_icon = "mdi:dolby"

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "dolby_profile", "Dolby Profile")
        self._pending: str | None = None

    @property
    def current_option(self) -> str | None:
        # While a write is in flight the requested value is shown, so a tap
        # gets an answer now rather than in half a second.
        if self._pending is not None:
            return self._pending
        profile = self.coordinator.data.get("dolby_profile")
        return profile if profile in DOLBY_PROFILES else None

    async def async_select_option(self, option: str) -> None:
        """Write the profile, then wait for the unit to actually agree.

        Nothing pushes the profile, so a read-back is the only confirmation -
        and the unit applies the change ~570ms after accepting the request.
        Refreshing immediately (which is what this used to do) read the old
        value and left the entity one step behind until the next periodic
        poll, so changing profile appeared to need two taps: the second tap's
        read-back was what finally reported the first tap's change.

        So: show the requested value at once, then poll the read-back until
        the device agrees. If it never does, the pending value is dropped and
        the device's own reading stands - `set_dolby_profile` is not in the
        endpoint list the unit publishes, so a firmware without it has to snap
        visibly back rather than leave a lie on screen.
        """
        await self.coordinator.async_send(SET_DOLBY_PROFILE, profile=option)

        self._pending = option
        self.async_write_ha_state()
        try:
            for _ in range(CONFIRM_ATTEMPTS):
                await asyncio.sleep(CONFIRM_INTERVAL)
                await self.coordinator.async_refresh_settings()
                if self.coordinator.data.get("dolby_profile") == option:
                    break
        finally:
            self._pending = None
            self.async_write_ha_state()


class Tide16Upmixer(Tide16Entity, SelectEntity):
    """Which upmixer the unit is forced to use - Native, Dolby or DTS-X.

    The unit calls this the "decoder" in `set_forced_upmixer` and the
    "upmixer" in `get_settings`, and its own control page labels the values
    Dolby / Neural:X / Native. It is also the only field that distinguishes
    native from the rest: in native mode the decoder names carry straight on
    reporting whatever they last decoded.

    Same write-then-confirm dance as the profile above, for the same reason -
    nothing pushes this, so a read-back is the only confirmation there is.
    """

    _attr_options = list(UPMIXERS.values())  # noqa: RUF012 - HA reads a list
    _attr_icon = "mdi:surround-sound"

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "upmixer", "Upmixer")
        self._pending: str | None = None

    @property
    def current_option(self) -> str | None:
        if self._pending is not None:
            return self._pending
        return UPMIXERS.get(self.coordinator.data.get("upmixer"))

    async def async_select_option(self, option: str) -> None:
        wire = next((k for k, label in UPMIXERS.items() if label == option), None)
        if wire is None:
            return
        await self.coordinator.async_send(SET_FORCED_UPMIXER, decoder=wire)

        self._pending = option
        self.async_write_ha_state()
        try:
            for _ in range(CONFIRM_ATTEMPTS):
                await asyncio.sleep(CONFIRM_INTERVAL)
                await self.coordinator.async_refresh_settings()
                if self.coordinator.data.get("upmixer") == wire:
                    break
        finally:
            self._pending = None
            self.async_write_ha_state()


def preset_label(entry: dict) -> str:
    """What one slot of `get_all_presets` is called.

    Every slot on this hardware reports an empty name, so today the options
    are bare ids - "1", "2".  A firmware or a loaded config that names them
    gives "1: Atmos", and the id stays the leading field either way: it is
    what `set_preset` takes, and the panel splits the label back apart on
    that first colon to draw the number and the name differently.

    Ids are NOT contiguous - miniDSP's own notes report units answering 1,
    3..12 - so they are opaque labels, never a position to count through.
    """
    pid = str(entry.get("id", "")).strip()
    name = str(entry.get("name") or "").strip()
    return f"{pid}: {name}" if name else pid


class Tide16Preset(Tide16Entity, SelectEntity):
    """Which filter preset the unit is on.

    Read from `get_all_presets` (the slots) plus `get_current_preset_index`
    (which one is live), and written with `set_preset`, whose argument is the
    slot's `id` as a STRING - not the position in the list.

    Unlike the two selects above, this one is pushed: the unit sends
    `preset_change` when the preset moves, including when it is changed from
    the front panel or its own web UI.  The read-back below is therefore a
    belt-and-braces confirmation rather than the only way to find out, and it
    is what makes a tap that the unit ignores snap visibly back.
    """

    _attr_icon = "mdi:tune-variant"

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "preset", "Filter Preset")
        self._pending: str | None = None

    @property
    def _slots(self) -> list[dict]:
        slots = self.coordinator.data.get("presets") or []
        return [s for s in slots if isinstance(s, dict) and s.get("id") is not None]

    @property
    def options(self) -> list[str]:
        return [preset_label(s) for s in self._slots]

    @property
    def current_option(self) -> str | None:
        # While a write is in flight the requested slot is shown, so a tap on
        # the panel's button gets an answer now rather than a round trip later.
        if self._pending is not None:
            return self._pending
        index = self.coordinator.data.get("preset_index")
        if index is None:
            return None
        for slot in self._slots:
            if str(slot.get("id")) == str(index):
                return preset_label(slot)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        # The panel draws the number and the name in different type - one
        # fixed, one scrolling if it is too wide for the button - so it needs
        # the id on its own, not only inside the label.
        return {"preset_index": self.coordinator.data.get("preset_index")}

    async def async_select_option(self, option: str) -> None:
        """Recall a preset, then wait for the unit to say it took.

        `set_preset` takes the id as a string.  Recalling a slot that holds
        nothing is a no-op on the device, which is exactly why the pending
        value has to be dropped again afterwards: without the confirm loop a
        dead slot would sit on the button looking selected.
        """
        wanted = option.split(":", 1)[0].strip()
        if not wanted or wanted not in [str(s.get("id")) for s in self._slots]:
            return
        await self.coordinator.async_send(SET_PRESET, id=wanted)

        self._pending = option
        self.async_write_ha_state()
        try:
            for _ in range(CONFIRM_ATTEMPTS):
                await asyncio.sleep(CONFIRM_INTERVAL)
                # `preset_change` usually beats this; asking costs one frame
                # and covers the firmware that does not push on a self-recall.
                await self.coordinator.async_send(GET_PRESET_INDEX)
                if str(self.coordinator.data.get("preset_index")) == wanted:
                    break
        finally:
            self._pending = None
            self.async_write_ha_state()


class Tide16SettingSelect(Tide16SettingEntity, SelectEntity):
    """One of the unit's multiple-choice settings - see settings.py.

    The options are the ones its own control page offers, read out of that
    page's <select> markup rather than guessed.
    """

    def __init__(self, coordinator: Tide16Coordinator, setting: Tide16Setting) -> None:
        super().__init__(coordinator, setting)
        self._attr_options = list(setting.options or ())

    @property
    def current_option(self) -> str | None:
        value = self._value
        if value is None:
            return None
        value = str(value)
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self._write(option)
