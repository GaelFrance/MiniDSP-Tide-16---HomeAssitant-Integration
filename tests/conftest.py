"""Fixtures: a real Home Assistant (pytest-homeassistant-custom-component)
with the Tide16 replaced by an in-memory fake, so the whole integration -
config entry, registry, platforms, services - runs as it does on a real
system, without a network."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.minidsp_tide16.const import DOMAIN

HOST = "192.168.10.242"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations, hass):
    # The frontend needs the hass_frontend wheel, which these tests do not
    # install; the card registration is patched out anyway (fake_client).
    hass.config.components.update({"frontend", "http", "websocket_api", "network"})
    # media_player registers a proxy view at setup; no real HTTP server here.
    hass.http = MagicMock()
    yield


class FakeClient:
    """Stands in for api.Tide16Client: records what is sent, replays pushes."""

    instances: ClassVar[list[FakeClient]] = []

    def __init__(self, host, port=5555, session=None, on_notification=None,
                 on_reply=None, on_connected=None) -> None:
        self.host = host
        self.port = port
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._on_notification = on_notification
        self._on_reply = on_reply
        self._on_connected = on_connected
        self._connected = False
        FakeClient.instances.append(self)

    @property
    def connected(self) -> bool:
        return self._connected

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        self.set_connected(False)

    async def probe(self) -> dict[str, Any]:
        return {"req": "poll", "status": "OK"}

    async def send(self, endpoint: str, **args: Any) -> bool:
        if not self._connected:
            return False
        self.sent.append((endpoint, args))
        return True

    async def request(self, endpoint: str, **args: Any) -> Any:
        await self.send(endpoint, **args)
        return None

    async def set_volume_db(self, db: float) -> bool:
        return await self.send("set_volume_db", value=round(float(db), 2))

    # --- test helpers ---
    def set_connected(self, value: bool) -> None:
        if value == self._connected:
            return
        self._connected = value
        if self._on_connected:
            self._on_connected(value)

    def push(self, name: str, payload: Any) -> None:
        self._on_notification(name, payload)

    def reply(self, endpoint: str, data: Any) -> None:
        self._on_reply(endpoint, data)

    def sent_endpoints(self) -> list[str]:
        return [e for e, _ in self.sent]


@pytest.fixture
def fake_client():
    FakeClient.instances.clear()
    with patch(
        "custom_components.minidsp_tide16.coordinator.Tide16Client", FakeClient
    ), patch(
        "custom_components.minidsp_tide16._async_register_frontend",
        new_callable=AsyncMock,
    ), patch(
        "custom_components.minidsp_tide16.websocket.async_register_websocket_api",
        return_value=None,
    ), patch(
        "custom_components.minidsp_tide16.async_register_websocket_api",
        return_value=None,
    ), patch(
        "custom_components.minidsp_tide16.coordinator.Tide16Coordinator._read_clock",
        new_callable=AsyncMock,
    ):
        yield FakeClient


@pytest.fixture
def entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="miniDSP Tide16 (192.168.10.242)",
        data={"host": HOST, "port": 5555},
        version=1,
    )
    entry.add_to_hass(hass)
    return entry
