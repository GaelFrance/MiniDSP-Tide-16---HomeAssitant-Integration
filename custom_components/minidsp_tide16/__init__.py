"""miniDSP Tide16 - device, entities and the front-panel card.

v1.0.0 is the ControlCard integration (speedtoys, MIT) merged into
minidsp_tide16: its device and settings coverage and its card, under this
domain and with the 0.x entity identities, volume stepping and
volume-compensated signal detection. See CHANGELOG.md.

One HACS install gets all of it.  The card and its plate art ship inside this
package and are registered with the frontend on setup, so there is no Lovelace
resource to add, no files to copy into `www/`, and no cache-buster to bump by
hand - the URL carries the manifest version.
"""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api.const import SET_PRESET
from .autodim import Tide16AutoDim
from .const import (
    ATTR_DELTA,
    ATTR_DURATION,
    ATTR_PRESET,
    CONF_HOST,
    CONF_PORT,
    CONF_SIGNAL_RELATIVE,
    CONF_SILENCE_HOLD,
    CONF_SILENCE_LEVEL,
    CONF_UPDATE_CHECK,
    DEFAULT_SIGNAL_RELATIVE,
    DEFAULT_SILENCE_HOLD,
    DEFAULT_SILENCE_LEVEL,
    DEFAULT_UPDATE_CHECK,
    DOMAIN,
    PANEL_JS,
    SERVICE_MEASURE_LEVEL,
    SERVICE_SET_PRESET,
    SERVICE_VOLUME_STEP,
    STATIC_URL,
)
from .coordinator import Tide16Coordinator
from .websocket import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)

# The legacy `minidsp_tide16:` YAML key (host, port) of 0.x is still read,
# once, to create a config entry if none exists - see async_setup.
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=5555): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

VOLUME_STEP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DELTA): vol.All(
            vol.Coerce(float), vol.Range(min=-60, max=60)
        ),
    }
)

MEASURE_LEVEL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DURATION, default=10): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=120)
        ),
    }
)


def preset_id(value: object) -> str:
    """The id the unit wants, from whatever a caller passed.

    `set_preset` takes the id as a string, and a dashboard, a script and the
    UI's own number field each hand it over differently - 2, 2.0, "2".  All
    three mean the same slot, so they are folded to one spelling here rather
    than left to fail as a mismatch nobody can see.  An id that is not a
    number at all is passed through untouched: the ids are the unit's, not
    ours, and it is not this function's business to have opinions about them.
    """
    text = str(value).strip()
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def preset_sort(pid: str) -> tuple[int, float, str]:
    """Order ids the way a person reads them: 2 before 10, names last."""
    try:
        return (0, float(pid), "")
    except ValueError:
        return (1, 0.0, pid)


SET_PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRESET): vol.All(preset_id, vol.Length(min=1)),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the card once, whether or not a unit is configured yet."""
    await _async_register_frontend(hass)
    if DOMAIN in config and not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config[DOMAIN])
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = Tide16Coordinator(
        hass,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, 5555),
        silence_level=float(
            entry.options.get(CONF_SILENCE_LEVEL, DEFAULT_SILENCE_LEVEL)
        ),
        silence_hold=float(entry.options.get(CONF_SILENCE_HOLD, DEFAULT_SILENCE_HOLD)),
        signal_relative=float(
            entry.options.get(CONF_SIGNAL_RELATIVE, DEFAULT_SIGNAL_RELATIVE)
        ),
        update_check=bool(entry.options.get(CONF_UPDATE_CHECK, DEFAULT_UPDATE_CHECK)),
    )
    await coordinator.async_start()

    coordinator.autodim = Tide16AutoDim(hass, coordinator)
    coordinator.autodim.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_register_websocket_api(hass)
    _async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: Tide16Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if coordinator.autodim:
            coordinator.autodim.async_stop()
        await coordinator.async_stop()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_VOLUME_STEP)
            hass.services.async_remove(DOMAIN, SERVICE_MEASURE_LEVEL)
            hass.services.async_remove(DOMAIN, SERVICE_SET_PRESET)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card from this package and load it on every dashboard."""
    if hass.data.get(f"{DOMAIN}_frontend"):
        return
    hass.data[f"{DOMAIN}_frontend"] = True

    root = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(root), False)]
    )

    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version or "dev")
    # The version in the URL is the whole cache-busting story: update the
    # integration and every browser fetches the new module, with nothing for
    # anyone to remember to bump.
    frontend.add_extra_js_url(hass, f"{STATIC_URL}/{PANEL_JS}?v={version}")


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_VOLUME_STEP):
        return

    async def _volume_step(call: ServiceCall) -> None:
        """Relative dB, clamped, applied to every configured unit.

        Server-side because a dashboard tap carries literal data and cannot
        read the current level to add to it - which is exactly why this used to
        be a hand-written script in the user's own YAML.
        """
        delta = float(call.data[ATTR_DELTA])
        for coordinator in hass.data.get(DOMAIN, {}).values():
            # Same path as the Volume Up/Down buttons, so quick taps on the
            # card's volume keys accumulate instead of all reading the same
            # unconfirmed level.
            await coordinator.async_nudge_volume(delta)

    async def _measure_output_level(call: ServiceCall) -> ServiceResponse:
        """Report what the output is doing, so a threshold can be chosen.

        It returns rather than stores.  This is something a user runs once
        while deciding on a number, and an entity holding it would put the very
        levels this design keeps out of the recorder straight back into it.
        """
        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            raise HomeAssistantError("No Tide16 is configured.")
        return await coordinators[0].async_measure_levels(
            float(call.data[ATTR_DURATION])
        )

    async def _set_preset(call: ServiceCall) -> None:
        """Recall a preset by id, whatever the slot happens to be named.

        The select entity carries the name in its option strings, because a
        dropdown that says "2" and nothing else is no use to a person.  That
        is exactly what makes it unusable from an automation: naming a preset
        on the unit rewrites every option, and `select.select_option` then
        rejects the number that used to work.  This reads the id and only the
        id, so a rename cannot reach it.

        An id no unit holds raises rather than passing quietly to a device
        that would ignore it - a silent no-op is the failure being reported.
        """
        wanted = preset_id(call.data[ATTR_PRESET])
        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            raise HomeAssistantError("No Tide16 is configured.")

        known: set[str] = set()
        sent = False
        for coordinator in coordinators:
            slots = {
                str(slot.get("id"))
                for slot in coordinator.data.get("presets") or []
                if isinstance(slot, dict) and slot.get("id") is not None
            }
            known |= slots
            if wanted in slots:
                await coordinator.async_send(SET_PRESET, id=wanted)
                sent = True

        if not sent:
            # Ids are not contiguous - units answer 1, 3..12 - so listing the
            # ones that exist is more use than saying how many there are.
            offered = ", ".join(sorted(known, key=preset_sort)) or "none"
            raise HomeAssistantError(
                f"No Tide16 has preset {wanted}. Presets on this system: {offered}."
            )

    hass.services.async_register(
        DOMAIN, SERVICE_VOLUME_STEP, _volume_step, schema=VOLUME_STEP_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PRESET, _set_preset, schema=SET_PRESET_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEASURE_LEVEL,
        _measure_output_level,
        schema=MEASURE_LEVEL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
