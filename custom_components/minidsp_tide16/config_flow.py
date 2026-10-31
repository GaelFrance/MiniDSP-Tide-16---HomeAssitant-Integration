"""Set the Tide16 up from the UI.

The unit announces itself nowhere - measured on a live one, it answers no
SSDP, advertises no mDNS service, and its only name on a network is whatever
that network's DHCP server decided to call it, which is a fact about the
network rather than the device. So there is nothing for Home Assistant's own
discovery to catch, and this goes looking instead: one port across the local
subnet, then a WebSocket handshake to confirm that whatever answered really is
a Tide16 and not something else that happens to listen on 5555.

Typing an address by hand is always available. The sweep is bounded to a small
subnet, and a unit in standby leaves the network entirely - so "nothing found"
is a perfectly ordinary answer that has to lead somewhere useful.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import network
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import Tide16Client, Tide16Error, async_scan, candidate_hosts
from .api.const import DEFAULT_PORT
from .const import (
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
    DEVICE_NAME,
    DOMAIN,
    MAX_SIGNAL_RELATIVE,
    MAX_SILENCE_HOLD,
    MAX_SILENCE_LEVEL,
    MIN_SIGNAL_RELATIVE,
    MIN_SILENCE_HOLD,
    MIN_SILENCE_LEVEL,
)

_LOGGER = logging.getLogger(__name__)


class Tide16ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Tide16OptionsFlow:
        return Tide16OptionsFlow(config_entry)

    def __init__(self) -> None:
        self._found: list[dict[str, Any]] = []
        self._scanned = False

    async def _async_local_hosts(self) -> list[str]:
        """Every address worth trying, taken from Home Assistant's own adapters.

        Bounded by candidate_hosts(): a /24 is 254 addresses and sweeps in
        about a second, a /16 is 65534 and is refused outright. On a network
        that large the user types the address.
        """
        hosts: list[str] = []
        try:
            adapters = await network.async_get_adapters(self.hass)
        except Exception:
            _LOGGER.debug("could not read network adapters", exc_info=True)
            return []

        for adapter in adapters:
            if not adapter.get("enabled"):
                continue
            for ip in adapter.get("ipv4", []):
                address, prefix = ip.get("address"), ip.get("network_prefix")
                if not address or prefix is None:
                    continue
                for host in candidate_hosts(f"{address}/{prefix}"):
                    if host != address and host not in hosts:
                        hosts.append(host)
        return hosts

    async def _async_search(self) -> None:
        """Look once, on first entry to the form."""
        if self._scanned:
            return
        self._scanned = True
        hosts = await self._async_local_hosts()
        if not hosts:
            return
        try:
            self._found = await async_scan(
                hosts, session=async_get_clientsession(self.hass)
            )
        except Exception:
            _LOGGER.debug("scan failed", exc_info=True)
            self._found = []
        _LOGGER.debug("found %d Tide16(s) of %d addresses", len(self._found), len(hosts))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is None:
            await self._async_search()
        else:
            host = str(user_input[CONF_HOST]).strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            # One unit per host: re-adding the same address should offer to
            # reconfigure it rather than build a second set of entities.
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            client = Tide16Client(host, port)
            try:
                await client.probe()
            except Tide16Error:
                # The unit answers on port 5555 only while it is awake, so this
                # is as likely to mean "it is in standby" as "wrong address".
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=DEVICE_NAME, data={CONF_HOST: host, CONF_PORT: port}
                )

        configured = {
            entry.data.get(CONF_HOST) for entry in self._async_current_entries()
        }
        options = [
            SelectOptionDict(
                value=found["host"],
                label=(
                    f"{found['host']} - Tide16"
                    + (f" (firmware {found['version']})" if found.get("version") else "")
                ),
            )
            for found in self._found
            if found["host"] not in configured
        ]

        # custom_value: the list is a shortcut, not a restriction. A unit on
        # another subnet, or asleep when the scan ran, is still reachable by
        # typing its address.
        default = (user_input or {}).get(CONF_HOST) or (
            options[0]["value"] if options else ""
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=default): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                            sort=False,
                        )
                    ),
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
            description_placeholders={"found": self._found_message(len(options))},
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """The 0.x `minidsp_tide16:` YAML key, turned into an entry once.

        Not probed: the unit may well be in standby while Home Assistant
        starts, and that must not lose the configuration.
        """
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        host = str(import_data[CONF_HOST]).strip()
        port = int(import_data.get(CONF_PORT, DEFAULT_PORT))
        return self.async_create_entry(
            title=DEVICE_NAME, data={CONF_HOST: host, CONF_PORT: port}
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point the entry at a new address without losing anything."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
            unchanged = host == entry.data.get(CONF_HOST) and port == entry.data.get(
                CONF_PORT, DEFAULT_PORT
            )
            if not unchanged:
                try:
                    await Tide16Client(host, port).probe()
                except Tide16Error:
                    errors["base"] = "cannot_connect"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host, CONF_PORT: port}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                    vol.Optional(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def _found_message(count: int) -> str:
        if count == 1:
            return (
                "Found a Tide16 on this network. Pick it below, or type another "
                "address."
            )
        if count > 1:
            return (
                f"Found {count} Tide16 units on this network. Pick one below, or "
                "type another address."
            )
        return (
            "No Tide16 found on this network. A Tide16 in standby leaves the "
            "network entirely, so switch it on and try again - or type its "
            "address below if it is on a different subnet."
        )


class Tide16OptionsFlow(OptionsFlow):
    """Audio detection, for the systems the defaults do not fit.

    Both defaults were measured on real material rather than chosen, and most
    installs will never open this.  It exists because "silent" is a different
    level on every system - an analog input, or a source that keeps a low-level
    signal alive between tracks, sits far above digital silence - and the two
    ways that goes wrong are both invisible from inside the integration.

    The entry reloads on save, so a change applies without a restart.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        # Deliberately not `self.config_entry`: assigning that is deprecated on
        # newer cores and this has to run on 2024.7 as well.
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SIGNAL_RELATIVE: float(user_input[CONF_SIGNAL_RELATIVE]),
                    CONF_SILENCE_LEVEL: float(user_input[CONF_SILENCE_LEVEL]),
                    CONF_SILENCE_HOLD: float(user_input[CONF_SILENCE_HOLD]),
                    CONF_UPDATE_CHECK: bool(user_input[CONF_UPDATE_CHECK]),
                }
            )

        options = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SIGNAL_RELATIVE,
                        default=float(
                            options.get(CONF_SIGNAL_RELATIVE, DEFAULT_SIGNAL_RELATIVE)
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SIGNAL_RELATIVE,
                            max=MAX_SIGNAL_RELATIVE,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="dB",
                        )
                    ),
                    vol.Required(
                        CONF_SILENCE_LEVEL,
                        default=float(
                            options.get(CONF_SILENCE_LEVEL, DEFAULT_SILENCE_LEVEL)
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SILENCE_LEVEL,
                            max=MAX_SILENCE_LEVEL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="dB",
                        )
                    ),
                    vol.Required(
                        CONF_SILENCE_HOLD,
                        default=float(
                            options.get(CONF_SILENCE_HOLD, DEFAULT_SILENCE_HOLD)
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SILENCE_HOLD,
                            max=MAX_SILENCE_HOLD,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="seconds",
                        )
                    ),
                    vol.Required(
                        CONF_UPDATE_CHECK,
                        default=bool(options.get(CONF_UPDATE_CHECK, DEFAULT_UPDATE_CHECK)),
                    ): BooleanSelector(),
                }
            ),
        )
