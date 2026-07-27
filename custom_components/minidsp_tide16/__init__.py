"""The miniDSP Tide16 integration.

Added in v18: a proper config_flow (see config_flow.py), so the
integration can be set up from Settings > Devices & services > Add
integration, instead of only via YAML.

The legacy `minidsp_tide16:` YAML key still works, but now only as a
one-time migration trigger: on startup, if present, async_setup() below
kicks off an import flow that creates a real config entry from it (see
async_step_import in config_flow.py, which also fires the one-time
"migrated successfully" notification - NOT this file; see v19 note
below for why that distinction matters). From then on, the config entry
- not the YAML - is what's actually used; you can remove the YAML key
from configuration.yaml at your leisure (re-importing an
already-migrated config on a later restart is a harmless no-op, so
there's no rush and no risk in leaving both in place for a while).

v19 fixes (a third independent review, credited in CHANGELOG.md):
  - The migration notification used to be fired from async_setup_entry()
    below, gated on `entry.source == SOURCE_IMPORT`. That gate is true
    forever for an imported entry - not just the first time - so the
    notification was silently re-appearing on every single restart or
    reload. Moved to config_flow.py's async_step_import(), which only
    runs once, exactly when the entry is created.
  - async_setup_entry() now starts the coordinator's connection AFTER
    the platforms have loaded successfully (entities just show
    "unavailable" for the brief moment until the connection comes up,
    which is what they're designed to do anyway - see entity.py). If
    platform setup itself raises, the coordinator is removed from
    hass.data before re-raising - it was never started in the first
    place at that point (async_connect() only runs below, after this
    succeeds), so there's no background task or open connection left to
    stop; this just prevents a dangling, unstarted coordinator reference
    from lingering in hass.data for an entry Home Assistant considers
    failed.

v21 fix: Home Assistant logs a "Detected blocking call to import_module
... inside the event loop" warning the first time a platform module
(button.py, sensor.py, etc.) gets imported synchronously via
async_forward_entry_setups() below - importing a Python module involves
blocking file I/O, which isn't supposed to happen on the event loop
thread. Harmless on its own (this run's actual setup failure was a
separate, real bug - a deprecated import removed from newer Home
Assistant releases, fixed in sensor.py), but worth silencing anyway since
it fires on every single setup. Fixed by explicitly pre-importing all
platform modules in Home Assistant's dedicated import executor thread
before forwarding entry setup to them, so that by the time
async_forward_entry_setups() needs them, they're already cached in
sys.modules and no import happens on the event loop at all.

Nothing about the YAML migration touches any entity's unique_id or
entity_id - see button.py's docstring for why that's what actually
matters. Existing automations, dashboards, areas, and customizations are
unaffected.
"""
from __future__ import annotations

import asyncio
import importlib
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN
from .coordinator import Tide16Coordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.BINARY_SENSOR,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Only handles the legacy YAML key now, as a one-time import trigger.
    Real setup happens in async_setup_entry() below, once a config entry
    exists (either from this import or from adding the integration
    manually via the UI)."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=conf,
        )
    )
    return True


SERVICE_REQUEST_FAST_METERING = "request_fast_metering"


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register the fast-metering keepalive service (v22).

    The front-panel card calls this on a short repeat while its bar meter
    is visible, to temporarily raise the RMS poll rate (see
    coordinator.async_request_fast_metering). It is intentionally a plain
    service with no target: there is only ever one Tide16, and making the
    card resolve an entity_id or device_id just to ask "please meter
    faster" would buy nothing. Every loaded coordinator gets the request.

    Registered once - has_service() guards against re-registering when a
    second entry is added or an entry is reloaded.
    """
    if hass.services.has_service(DOMAIN, SERVICE_REQUEST_FAST_METERING):
        return

    @callback
    def _handle(call) -> None:
        for coordinator in hass.data.get(DOMAIN, {}).values():
            coordinator.async_request_fast_metering()

    hass.services.async_register(DOMAIN, SERVICE_REQUEST_FAST_METERING, _handle)


async def _async_preload_platforms(hass: HomeAssistant) -> None:
    """Import every platform module in Home Assistant's dedicated import
    executor thread, instead of letting async_forward_entry_setups()
    below import whichever ones aren't cached in sys.modules yet -
    directly on the event loop, which is what triggers the "Detected
    blocking call to import_module ... inside the event loop" warning.
    Once a module is imported once, Python caches it, so this makes the
    later async_forward_entry_setups() call a cheap no-op import for all
    six platforms instead of six blocking file-I/O imports."""
    import_job = getattr(hass, "async_add_import_executor_job", hass.async_add_executor_job)
    await asyncio.gather(
        *(
            import_job(importlib.import_module, f"{__name__}.{platform.value}")
            for platform in PLATFORMS
        )
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = Tide16Coordinator(
        hass, entry.data[CONF_HOST], entry.data.get(CONF_PORT, DEFAULT_PORT)
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    try:
        await _async_preload_platforms(hass)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise

    # Only start connecting once the platforms are up - if this failed
    # above, there'd be no entities around to receive the coordinator's
    # updates anyway. Entities show "unavailable" until the connection
    # comes up, which takes at most a couple of seconds on a local
    # network - see entity.py.
    coordinator.async_connect()
    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: Tide16Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return unload_ok
