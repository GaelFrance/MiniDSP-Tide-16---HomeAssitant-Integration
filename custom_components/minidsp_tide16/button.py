"""Buttons: power, volume steps, one per input, reboot, pairing, scenes.

The scenes, reboot and pairing come from the ControlCard integration; the
shutdown, volume and input buttons from minidsp_tide16 0.x, with their old
unique ids (minidsp_tide16_shutdown, minidsp_tide16_volume_up,
minidsp_tide16_source_spotify...) so automations, scripts and the HomeKit
scripts that press them keep working.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.const import REBOOT, SET_BT_PAIRING, SET_SCENE, SET_SOURCE, SHUTDOWN
from .const import DOMAIN, SCENES, SOURCE_LABEL_TO_ID, VOLUME_STEP_DB, slugify_label
from .coordinator import Tide16Coordinator
from .entity import Tide16Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Tide16Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [
        Tide16Button(coordinator, "shutdown", "Shutdown", SHUTDOWN, {}, "mdi:power"),
        Tide16Button(coordinator, "reboot", "Reboot", REBOOT, {}, "mdi:restart"),
        Tide16Button(
            coordinator,
            "bluetooth_pair",
            "Bluetooth Pair",
            SET_BT_PAIRING,
            {},
            "mdi:bluetooth-settings",
        ),
        Tide16ActionButton(
            coordinator,
            "volume_up",
            "Volume Up",
            "mdi:volume-plus",
            lambda: coordinator.async_nudge_volume(VOLUME_STEP_DB),
        ),
        Tide16ActionButton(
            coordinator,
            "volume_down",
            "Volume Down",
            "mdi:volume-minus",
            lambda: coordinator.async_nudge_volume(-VOLUME_STEP_DB),
        ),
        Tide16ActionButton(
            coordinator,
            "check_for_update",
            "Check for Update",
            "mdi:update",
            coordinator.async_check_for_update,
            category=EntityCategory.DIAGNOSTIC,
        ),
    ]
    entities += [
        Tide16SourceButton(coordinator, label, source_id)
        for label, source_id in SOURCE_LABEL_TO_ID.items()
    ]
    # The device stores four scenes against the colours on its own remote, so
    # the panel's coloured buttons recall the slot of the same name.  A slot
    # that was never saved recalls nothing, which is not a fault.
    for index, colour in enumerate(SCENES, start=1):
        entities.append(
            Tide16Button(
                coordinator,
                f"scene_{colour}",
                f"Scene {colour.title()}",
                SET_SCENE,
                {"index": index},
                "mdi:palette",
            )
        )
    async_add_entities(entities)


class Tide16Button(Tide16Entity, ButtonEntity):
    """Sends one fixed command."""

    def __init__(
        self,
        coordinator: Tide16Coordinator,
        key: str,
        name: str,
        endpoint: str,
        args: dict,
        icon: str,
    ) -> None:
        super().__init__(coordinator, key, name)
        self._endpoint = endpoint
        self._args = args
        self._attr_icon = icon

    async def async_press(self) -> None:
        await self.coordinator.async_send(self._endpoint, **self._args)


class Tide16ActionButton(Tide16Entity, ButtonEntity):
    """Runs a coordinator method."""

    def __init__(
        self,
        coordinator: Tide16Coordinator,
        key: str,
        name: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
        *,
        category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator, key, name)
        self._action = action
        self._attr_icon = icon
        self._attr_entity_category = category

    async def async_press(self) -> None:
        await self._action()


class Tide16SourceButton(Tide16Entity, ButtonEntity):
    """Select one input. The id and slug never change; the name follows the unit."""

    _attr_icon = "mdi:import"

    def __init__(self, coordinator: Tide16Coordinator, label: str, source_id: str) -> None:
        super().__init__(coordinator, f"source_{slugify_label(label)}", f"Source: {label}")
        self._source_id = source_id
        self._fallback_label = label

    @property
    def name(self) -> str:
        live = (self.coordinator.data.get("source_names") or {}).get(self._source_id)
        return f"Source: {live or self._fallback_label}"

    async def async_press(self) -> None:
        await self.coordinator.async_send(SET_SOURCE, value=self._source_id)
