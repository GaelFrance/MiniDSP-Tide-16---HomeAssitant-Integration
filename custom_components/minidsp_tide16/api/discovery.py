"""Find Tide16 units by asking port 5555 who it is.

The unit announces itself nowhere. Measured on a live one: it answers no SSDP,
advertises no mDNS service, and the only name it has on a network is whatever
the DHCP server chose to call it - which is a fact about that network, not
about the device, so it is useless for identifying one on anybody else's.

So this asks instead. Open the WebSocket, call `get_settings`, and see whether
what comes back is shaped like a Tide16. A whole /24 takes about 1.5 seconds,
because the TCP pass is what costs and almost every address refuses instantly.

No Home Assistant imports, like the rest of this package: the scan runs from a
terminal with `python3 -m api --scan`.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import logging
from typing import Any

import aiohttp

from .const import DEFAULT_PORT, GET_SETTINGS

_LOGGER = logging.getLogger(__name__)

# A refused connection comes back in about a millisecond on a LAN; this only
# has to be generous enough for a device that is slow to accept.
CONNECT_TIMEOUT = 0.5
# The handshake plus one reply. The unit sends a greeting frame first, so this
# has to outlast a frame we are going to ignore.
IDENTIFY_TIMEOUT = 6.0
FANOUT = 64

# Anything bigger and this stops being a quick look and starts being a network
# scan. A /24 is 254 addresses; a /16 would be 65534.
MAX_ADDRESSES = 512

# Keys `get_settings` returns that together mean Tide16 rather than "something
# that speaks WebSocket on 5555". Two is enough - requiring the whole set would
# make this brittle against a firmware that drops one.
FINGERPRINT = frozenset(
    {
        "concord_version",
        "hdmi_xmos_firmware_version",
        "hdmi_card_firmware_version",
        "hdmi_kernel_version",
        "current_preset_index",
        "slicer",
    }
)
FINGERPRINT_MIN = 2


def candidate_hosts(cidr: str) -> list[str]:
    """Usable addresses in a network, or [] if it is too big to sweep."""
    net = ipaddress.ip_network(cidr, strict=False)
    if net.version != 4 or net.num_addresses > MAX_ADDRESSES:
        return []
    return [str(h) for h in net.hosts()]


async def _port_open(host: str, port: int, sem: asyncio.Semaphore) -> str | None:
    async with sem:
        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
            )
            return host
        except (OSError, asyncio.TimeoutError):
            return None
        finally:
            if writer is not None:
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()


async def identify(
    host: str, port: int = DEFAULT_PORT, session: aiohttp.ClientSession | None = None
) -> dict[str, Any] | None:
    """Return details if `host` is a Tide16, else None.

    Positive identification, not "the port was open": something else listening
    on 5555 will fail the WebSocket upgrade, or answer nothing that looks like
    this, and gets dropped either way.
    """
    owned = session is None
    session = session or aiohttp.ClientSession()
    try:
        async with session.ws_connect(
            f"ws://{host}:{port}", timeout=IDENTIFY_TIMEOUT
        ) as ws:
            await ws.send_str(json.dumps({"endpoint": GET_SETTINGS}))
            loop = asyncio.get_event_loop()
            deadline = loop.time() + IDENTIFY_TIMEOUT
            while loop.time() < deadline:
                msg = await asyncio.wait_for(
                    ws.receive(), timeout=max(0.1, deadline - loop.time())
                )
                if msg.type is not aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    obj = json.loads(msg.data)
                except ValueError:
                    continue
                # The greeting frame arrives first and carries no `req`.
                if obj.get("req") != GET_SETTINGS:
                    continue
                data = obj.get("data")
                if obj.get("status") != "OK" or not isinstance(data, dict):
                    return None
                if len(FINGERPRINT & set(data)) < FINGERPRINT_MIN:
                    return None
                return {
                    "host": host,
                    "port": port,
                    "version": data.get("version"),
                    "preset": data.get("current_preset_index"),
                }
    except (aiohttp.ClientError, OSError, asyncio.TimeoutError):
        return None
    finally:
        if owned:
            await session.close()
    return None


async def async_scan(
    hosts: list[str],
    port: int = DEFAULT_PORT,
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, Any]]:
    """Every Tide16 among `hosts`, cheapest test first."""
    if not hosts:
        return []

    sem = asyncio.Semaphore(FANOUT)
    reachable = [
        host
        for host in await asyncio.gather(*(_port_open(h, port, sem) for h in hosts))
        if host
    ]
    _LOGGER.debug("port %s open on %d of %d", port, len(reachable), len(hosts))
    if not reachable:
        return []

    owned = session is None
    session = session or aiohttp.ClientSession()
    try:
        found = await asyncio.gather(
            *(identify(h, port, session) for h in reachable)
        )
    finally:
        if owned:
            await session.close()

    return sorted(
        (f for f in found if f), key=lambda f: tuple(int(p) for p in f["host"].split("."))
    )
