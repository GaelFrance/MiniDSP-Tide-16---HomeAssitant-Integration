"""A WebSocket client for the miniDSP Tide16.

Deliberately free of Home Assistant imports: it runs from a terminal
(`cd custom_components/minidsp_tide16 && python3 -m api <host>`), which is what makes the
protocol testable without a Home Assistant at all.  Everything above this file
turns its callbacks into entities.

Three facts about the device shape the design:

* **Standby takes it off the network entirely.**  Port 5555 stops answering and
  the unit leaves the LAN, so a dropped connection is normal operation rather
  than an error.  The supervisor reconnects forever, quietly.
* **Setters usually don't reply.**  The unit confirms a write by pushing a
  notification instead, so `send()` returns once the frame is on the wire and
  the caller learns the outcome from the push.
* **There is no request id.**  Replies carry the endpoint name in `req` and
  nothing else, so correlation is by endpoint: one reply resolves every caller
  currently waiting on that endpoint.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import (
    DEFAULT_PORT,
    ENVELOPE_NOTIFICATIONS,
    MAX_VOLUME_DB,
    MIN_VOLUME_DB,
    POLL,
)

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 10
REQUEST_TIMEOUT = 8
BACKOFF_START = 2
BACKOFF_MAX = 30


class Tide16Error(Exception):
    """The unit could not be reached or refused a request."""


class Tide16Client:
    """One supervised connection to one Tide16."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        session: aiohttp.ClientSession | None = None,
        on_notification: Callable[[str, Any], None] | None = None,
        on_reply: Callable[[str, Any], None] | None = None,
        on_connected: Callable[[bool], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._session = session
        self._owns_session = session is None
        self._on_notification = on_notification
        self._on_reply = on_reply
        self._on_connected = on_connected

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._waiters: dict[str, list[asyncio.Future]] = {}
        self._closing = False
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    # --- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Begin supervising the connection.  Returns immediately."""
        if self._task is None or self._task.done():
            self._closing = False
            self._task = asyncio.ensure_future(self._supervise())

    async def stop(self) -> None:
        self._closing = True
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
        self._set_connected(False)

    async def probe(self) -> dict[str, Any]:
        """One-shot reachability check, for the config flow.

        Deliberately not part of the supervised connection: a config flow that
        left a reconnect loop running behind a failed step would keep talking
        to an address the user just told us was wrong.
        """
        session = self._session or aiohttp.ClientSession()
        try:
            async with session.ws_connect(self.url, timeout=CONNECT_TIMEOUT) as ws:
                await ws.send_str(json.dumps({"endpoint": POLL}))
                deadline = asyncio.get_event_loop().time() + REQUEST_TIMEOUT
                while asyncio.get_event_loop().time() < deadline:
                    msg = await asyncio.wait_for(ws.receive(), timeout=REQUEST_TIMEOUT)
                    if msg.type is not aiohttp.WSMsgType.TEXT:
                        continue
                    obj = _loads(msg.data)
                    if obj and obj.get("req") == POLL:
                        return obj
                raise Tide16Error("no reply to poll")
        except Tide16Error:
            raise
        except Exception as err:
            raise Tide16Error(str(err) or type(err).__name__) from err
        finally:
            if self._session is None:
                await session.close()

    # --- the wire ----------------------------------------------------------

    async def send(self, endpoint: str, **args: Any) -> bool:
        """Fire a request.  True if it reached the wire.

        Not "true if it worked": most setters never reply, and waiting for a
        confirmation that structurally cannot arrive is how a UI ends up
        hanging on a button press.
        """
        ws = self._ws
        if ws is None or ws.closed:
            return False
        try:
            await ws.send_str(json.dumps({"endpoint": endpoint, **args}))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("send %s failed: %s", endpoint, err)
            return False
        return True

    async def request(self, endpoint: str, **args: Any) -> Any:
        """Fire a request and wait for the matching reply's `data`.

        Each call owns its own future and removes it again on the way out, so
        a future only ever carries an exception while someone is still waiting
        to receive it - no orphaned "exception was never retrieved" noise.
        """
        waiter: asyncio.Future = asyncio.get_event_loop().create_future()
        self._waiters.setdefault(endpoint, []).append(waiter)
        try:
            if not await self.send(endpoint, **args):
                raise Tide16Error(f"not connected, dropped {endpoint}")
            return await asyncio.wait_for(waiter, REQUEST_TIMEOUT)
        except asyncio.TimeoutError as err:
            raise Tide16Error(f"timed out waiting for {endpoint}") from err
        finally:
            pending = self._waiters.get(endpoint)
            if pending and waiter in pending:
                pending.remove(waiter)
            if not pending:
                self._waiters.pop(endpoint, None)

    async def set_volume_db(self, db: float) -> bool:
        clamped = max(MIN_VOLUME_DB, min(MAX_VOLUME_DB, float(db)))
        return await self.send("set_volume_db", value=round(clamped, 2))

    # --- internals ---------------------------------------------------------

    def _set_connected(self, value: bool) -> None:
        if value == self._connected:
            return
        self._connected = value
        if self._on_connected is not None:
            self._on_connected(value)

    async def _supervise(self) -> None:
        backoff = BACKOFF_START
        while not self._closing:
            try:
                await self._run_once()
                backoff = BACKOFF_START
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                # Standby is indistinguishable from a pulled cable, and both
                # are ordinary here, so this is debug rather than a warning
                # that would fill a log every night.
                _LOGGER.debug("tide16 %s: %s", self.host, err)
            finally:
                self._set_connected(False)
                self._fail_waiters()
            if self._closing:
                break
            await asyncio.sleep(backoff)
            backoff = min(BACKOFF_MAX, backoff * 2)

    async def _run_once(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        async with self._session.ws_connect(self.url, timeout=CONNECT_TIMEOUT) as ws:
            self._ws = ws
            self._set_connected(True)
            try:
                async for msg in ws:
                    if msg.type is not aiohttp.WSMsgType.TEXT:
                        continue
                    obj = _loads(msg.data)
                    if obj is not None:
                        self._dispatch(obj)
            finally:
                self._ws = None

    def _dispatch(self, obj: dict[str, Any]) -> None:
        if "notification" in obj:
            name = obj["notification"]
            # Two envelopes are in use: `value` for scalars, `data` for
            # structures, and at least one undocumented notification uses
            # whichever it feels like - so hand over the one that is present.
            payload = obj.get("value")
            if payload is None:
                payload = obj.get("data")
            if name in ENVELOPE_NOTIFICATIONS:
                payload = obj
            if self._on_notification is not None:
                self._on_notification(name, obj if payload is None else payload)
            return

        req = obj.get("req")
        if not req:
            return  # the greeting, and anything else without a request name

        data = obj.get("data")
        for waiter in self._waiters.pop(req, []):
            if not waiter.done():
                waiter.set_result(data)
        if self._on_reply is not None:
            self._on_reply(req, data)

    def _fail_waiters(self) -> None:
        for endpoint, waiters in list(self._waiters.items()):
            for waiter in waiters:
                if not waiter.done():
                    waiter.set_exception(
                        Tide16Error(f"connection lost before {endpoint}")
                    )
        self._waiters.clear()


def _loads(raw: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(raw)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None
