"""Master volume, and every numeric setting the unit reports."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api.const import MAX_VOLUME_DB, MIN_VOLUME_DB
from .const import DOMAIN
from .coordinator import Tide16Coordinator
from .entity import Tide16Entity, Tide16SettingEntity
from .settings import NUMBER, Tide16Setting, of_kind


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Tide16Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [Tide16Volume(coordinator)]
        + [Tide16SettingNumber(coordinator, s) for s in of_kind(NUMBER)]
        + [Tide16AutoDimNumber(coordinator, d) for d in AUTO_DIM_NUMBERS]
    )


class Tide16Volume(Tide16Entity, NumberEntity):
    """The documented range is -127.5 dB (silent) to 0.0 dB (maximum)."""

    _attr_native_min_value = MIN_VOLUME_DB
    _attr_native_max_value = MAX_VOLUME_DB
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator: Tide16Coordinator) -> None:
        super().__init__(coordinator, "volume", "Volume")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("volume_db")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_volume_db(value)


class Tide16SettingNumber(Tide16SettingEntity, NumberEntity):
    """One of the unit's numeric settings - see settings.py."""

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: Tide16Coordinator, setting: Tide16Setting) -> None:
        super().__init__(coordinator, setting)
        self._attr_native_min_value = setting.min_value
        self._attr_native_max_value = setting.max_value
        self._attr_native_step = setting.step
        self._attr_native_unit_of_measurement = setting.unit

    @property
    def native_value(self) -> float | None:
        value = self._value
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        # Whole numbers go over the wire as integers. Several of these are
        # indexes or millisecond counts, and the unit's own page sends them
        # through Math.floor - a float where it expects a count is not worth
        # finding out about at runtime.
        step = self._setting.step
        if step is not None and float(step).is_integer():
            await self._write(round(value))
        else:
            await self._write(value)


# The four values that shape the auto-dim ramp. All of them are ours rather
# than the unit's - the Tide16 has nowhere to keep a schedule - so they are
# restored across a restart instead of read back from the device.
#
# The rate is not one of them: it falls out of the range and the window. 80 to
# 20 across 30 minutes before sunset and 15 after is 60 points in 45 minutes,
# which is 1% every 45 seconds. Widening the window slows the walk down.
AUTO_DIM_NUMBERS: tuple[tuple[str, str, str, float, float, float, str], ...] = (
    ("auto_dim_max", "Auto Dim Day Brightness", "max_pct", 0, 100, 1, "%"),
    ("auto_dim_min", "Auto Dim Night Brightness", "min_pct", 0, 100, 1, "%"),
    ("auto_dim_lead", "Auto Dim Lead", "lead_min", 0, 240, 1, "min"),
    ("auto_dim_trail", "Auto Dim Trail", "trail_min", 0, 240, 1, "min"),
)


class Tide16AutoDimNumber(Tide16Entity, NumberEntity, RestoreEntity):
    """One of the auto-dim settings - see autodim.py."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Tide16Coordinator, spec) -> None:
        key, name, self._field, lo, hi, step, unit = spec
        super().__init__(coordinator, key, name)
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

    @property
    def available(self) -> bool:
        # Ours, not the unit's: adjustable while the Tide16 is in standby.
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            try:
                await self.coordinator.autodim.async_set(**{self._field: float(last.state)})
            except (TypeError, ValueError):
                pass  # unknown/unavailable from a restart with no history
        self.async_on_remove(
            self.coordinator.autodim.add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> float:
        return float(getattr(self.coordinator.autodim, self._field))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.autodim.async_set(**{self._field: float(value)})
        self.async_write_ha_state()
