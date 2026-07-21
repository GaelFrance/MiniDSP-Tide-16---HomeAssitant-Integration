"""Config flow for the miniDSP Tide16 integration.

Three entry points:
  - async_step_user: manually add a Tide16 from the UI (Settings >
    Devices & services > Add integration > miniDSP Tide16).
  - async_step_import: one-time automatic migration from the legacy YAML
    config (`minidsp_tide16: host: ...`) - triggered by __init__.py's
    async_setup() whenever it finds that key in configuration.yaml. Not
    shown to the user; the migrated-successfully notification is fired
    exactly once, right here, at the moment the entry is actually
    created - not from __init__.py's async_setup_entry(), which runs on
    every single startup/reload of the entry and would otherwise re-fire
    it forever (a real bug in the first cut of this file, per a second
    independent review - thank you).
  - async_step_reconfigure: change the host/IP of the already-configured
    Tide16 without deleting and recreating the integration (Settings >
    Devices & services > miniDSP Tide16 > ⋮ > Reconfigure).

v19: this integration only ever supports ONE Tide16 (see manifest.json's
"single_config_entry": true, which makes Home Assistant itself refuse a
second "Add integration" attempt). Earlier this used the host string as
the config entry's unique_id to prevent duplicates - which sounds
reasonable but is actually wrong for two reasons a review caught: (1)
"single_config_entry" already does that job, at the HA level, without
needing a fake per-entry identity at all; (2) a host isn't a stable
identity - reconfiguring the IP would silently leave a stale, misleading
unique_id behind, since updating it wasn't wired up. Replaced with a
plain "is there already an entry?" guard (_async_current_entries()) in
both async_step_user and async_step_import, and no config-entry-level
unique_id at all - it isn't needed for a deliberately single-instance
integration.

Also new in v19: async_step_user and async_step_reconfigure both
actually try to connect before accepting the form, so a typo'd IP or
wrong port surfaces immediately as a "can't connect" error instead of
silently creating (or worse, reconfiguring into) a non-working entry.
async_step_import deliberately skips this check - the Tide16 may
legitimately be off/asleep at the moment Home Assistant starts, and that
shouldn't block migrating an otherwise-correct YAML config.

v20 fixes (a follow-up review, credited in CHANGELOG.md):
  - _test_connection() used to just open and immediately close a
    WebSocket - that only proves *something* is listening on that port,
    not that it's actually a Tide16. It now sends a real
    get_coordinator_status request (the same endpoint the coordinator
    itself uses to confirm readiness on connect) and checks for a
    status: "OK" reply before accepting the form.
  - async_step_reconfigure now skips the connectivity test entirely when
    the submitted host/port are identical to the entry's current ones.
    The README documents that the Tide16 only accepts one WebSocket
    client at a time - the running coordinator already holds that slot,
    so a second test connection to the SAME address could plausibly be
    refused by the device itself, turning a no-op "reconfigure" into a
    spurious "cannot_connect" error. A change to a genuinely different
    address is still tested normally, since that's a different
    destination the coordinator isn't currently connected to.

None of this touches entity unique_id/entity_id (button.tide16_shutdown,
minidsp_tide16_volume, etc.), which live entirely in the platform files -
that separation is what keeps existing automations and dashboards
working across the YAML-to-config-entry migration.
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN

_MIGRATION_NOTIFICATION = (
    "miniDSP Tide16 was migrated from YAML to a config entry "
    "(Settings > Devices & services > miniDSP Tide16). You can now "
    "remove the `minidsp_tide16:` section from configuration.yaml and "
    "restart Home Assistant whenever convenient - all entities, "
    "automations, and dashboards keep working unchanged."
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST)): cv.string,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): cv.port,
        }
    )


async def _test_connection(hass, host: str, port: int) -> bool:
    """Open a WebSocket connection and ask get_coordinator_status,
    confirming an actual Tide16 replied (status "OK") rather than just
    some unrelated WebSocket server on that port - before creating or
    updating a config entry with it.

    Reads up to a few messages rather than just the first one: in theory
    an unsolicited notification could arrive before our request's reply
    does, and skipping straight past that would wrongly report
    "cannot_connect" on a perfectly healthy Tide16.
    """
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(5):
            async with session.ws_connect(f"ws://{host}:{port}") as ws:
                await ws.send_json({"endpoint": "get_coordinator_status"})
                for _ in range(5):
                    msg = await ws.receive()
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        return False
                    payload = msg.json()
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("req") == "get_coordinator_status":
                        return payload.get("status") == "OK"
                    # else: probably an unsolicited notification - keep
                    # waiting for the actual reply to our request.
    except Exception:  # noqa: BLE001 - any failure here just means "can't connect"
        return False
    return False


class Tide16ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            if await _test_connection(self.hass, host, port):
                return self.async_create_entry(
                    title=f"miniDSP Tide16 ({host})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        host = import_data[CONF_HOST]
        port = import_data.get(CONF_PORT, DEFAULT_PORT)

        # Fired here, once, exactly when the entry is actually created -
        # NOT from async_setup_entry() (see the module docstring for why
        # that was wrong).
        persistent_notification.async_create(
            self.hass,
            _MIGRATION_NOTIFICATION,
            title="miniDSP Tide16 migrated",
            notification_id="minidsp_tide16_yaml_migrated",
        )

        return self.async_create_entry(
            title=f"miniDSP Tide16 ({host})",
            data={CONF_HOST: host, CONF_PORT: port},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            unchanged = (
                host == entry.data.get(CONF_HOST)
                and port == entry.data.get(CONF_PORT, DEFAULT_PORT)
            )
            # v20: skip the connectivity test when nothing actually
            # changed - the running coordinator already holds the
            # Tide16's single WebSocket slot (see module docstring), so
            # re-testing the exact same address here could fail for a
            # reason that has nothing to do with whether the address is
            # correct.
            if unchanged or await _test_connection(self.hass, host, port):
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_HOST: host, CONF_PORT: port},
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(entry.data),
            errors=errors,
        )
