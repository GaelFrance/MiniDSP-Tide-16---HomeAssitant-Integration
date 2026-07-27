"""Persistent WebSocket coordinator for the miniDSP Tide16.

Talks to ws://<host>:5555, the same control channel used internally by the
stock web UI at http://<host>:5050. Since v15 this follows the OFFICIAL
protocol docs published by miniDSP at
https://docs.minidsp.com/product-manuals/tide16/websocket-api/.

  Outgoing (request):       {"endpoint": "<name>", ...params}
  Incoming (request reply): {"req": "<name>", "status": "OK"|"ERROR", "data": <payload>}
  Incoming (notification):  {"notification": "<name>", "value"|"data": <payload>}

Notifications are pushed by the device on its own whenever something
changes - from the API, the front-panel knob, the remote, or another
client - so a well-behaved client reads the state once on connect and then
lets notifications keep it in sync, rather than only polling. Confirmed
pushed as notifications: volume (both scales), mute, source, coordinator
status, bluetooth status, incoming stream properties, active preset, and
Dirac Live state/measurement mode. get_rms_block(_db) (metering) is NOT
in the official notification list, so it is still actively re-requested
on a timer.

v16 fixes (found by an independent review, credited in README):
  - _send() now returns whether the message was actually sent - a first
    pass at not showing state changes that never reached the device.
  - The connection no longer claims status "ready" the instant the
    WebSocket opens (before the device has said anything) - it now says
    "connecting" until get_coordinator_status or the coordinator_status
    notification actually confirms readiness.
  - Polling is split into two cadences: get_rms_block_db (no push
    notification exists for it) stays on a short timer, while the
    already-pushed fields (status/volume/mute/source) only get a much
    less frequent safety-net resync instead of being re-requested on the
    same short timer as the metering data.
  - A lock guards each periodic refresh so two requests for the same
    thing can't be in flight at once (it covers the send only, not the
    round-trip - see _request_rms_state/_request_resync_state).
  - Source display names are now pulled from get_source_names /
    source_names_change instead of being purely hardcoded - see
    const.py's SOURCE_LABEL_TO_ID docstring for what this does and does
    not change.
  - Failed (status != "OK") request replies are now logged as warnings
    instead of silently discarded.

v17 fix (a second independent review, credited in README): the v16 fix
above was incomplete. "the send succeeded" only means the JSON reached
the socket, not that the Tide16 accepted the command - a command it
rejects (status "ERROR") could still leave Home Assistant showing a
state the device never actually adopted. Every async_set_*() below now
sends the command and stops there; it no longer touches self.data at
all. State is set exclusively by _apply_*(), called either from a
request's successful reply or - far more often, since the Tide16 also
broadcasts these as notifications - from the matching push notification
(mute_change, volume_change_db, source_change, dirac_state...). This
means Home Assistant's state is always what the Tide16 itself last
confirmed, never a guess about what it probably did. The visible
trade-off is a small delay between pressing a button and the entity
updating (one local network round-trip), instead of an instant-but-
sometimes-wrong update.

v20 fix (a follow-up review, credited in CHANGELOG.md): the v19 fix to
async_nudge_volume (see its docstring) still had a race - any volume
confirmation cleared the pending target, even one that didn't actually
match it, which could still drop a rapid button press in the right
timing window. _apply_volume_db now only clears it on a matching
confirmation, and async_nudge_volume rolls the pending target back if
the command failed to send, plus treats it as stale after a few seconds
as a safety net against a confirmation that never arrives at all.

v22: the linear-gain (0.0-1.0) side of the volume API - get_volume,
volume_change, async_set_volume_linear - has been removed. The Tide16
does push both a linear and a dB volume notification, but nothing in
this integration reads the linear one anymore: media_player.tide16 (the
only thing that ever did) now derives its 0-1 slider position directly
from volume_db, on the same linear-over-the-dB-range scale as
number.tide16_volume - see media_player.py's docstring for why a true
linear-gain conversion made that slider nearly unusable.

The Tide16 fully shuts down its network stack (both port 5050 and 5555)
when put in standby via the "shutdown" endpoint. There is no known way to
wake it back up over the network - only the front panel encoder, an IR
remote, a 12V trigger, or power-cycling a smart plug can do that.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import time
from datetime import timedelta

import aiohttp
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    FAST_METERING_HOLD,
    FAST_RMS_INTERVAL,
    FULL_REFRESH_INTERVAL,
    MAX_VOLUME_DB,
    MIN_VOLUME_DB,
    RECONNECT_INTERVAL,
    RMS_REFRESH_INTERVAL,
    SIGNAL_TIDE16_UPDATE,
    SOURCE_LABEL_TO_ID,
)

_LOGGER = logging.getLogger(__name__)

_KNOWN_SOURCE_IDS = frozenset(SOURCE_LABEL_TO_ID.values())

# v20: how long a _pending_volume_db target is trusted for. Normally it's
# cleared within one local-network round-trip by a matching confirmation
# (see _apply_volume_db). This is only a safety net for the rare case
# where that confirmation never arrives at all (send failed silently,
# notification lost, command rejected) - past this many seconds, a nudge
# falls back to the last confirmed value instead of compounding on a
# target that may never be reached. The 60s full resync would eventually
# correct self.data anyway; this just avoids acting on a stale guess for
# that long.
_PENDING_VOLUME_TIMEOUT = 5.0


def _peak_db(entries) -> float | None:
    """Highest dB value found in a get_rms_block_db 'out' array.

    Only "out" is used: miniDSP's own docs state the "in" array is not
    currently populated with live metering data.
    """
    if not isinstance(entries, list):
        return None
    best: float | None = None
    for item in entries:
        if not isinstance(item, dict):
            continue
        val = item.get("val")
        if not isinstance(val, (int, float)):
            continue
        if best is None or val > best:
            best = val
    return best


def _channels_db(entries) -> list[float] | None:
    """Per-channel dB from a get_rms_block_db 'out' array, ordered by the
    device's own 1-based "index" field rather than by array position.

    v22: this data was always being fetched - _peak_db above just collapsed
    all 16 channels down to the single loudest one and threw the rest away.
    The front-panel card's bar meter needs them individually, so they're
    kept here too. Same "out only" reasoning as _peak_db applies.

    Sorting by "index" rather than trusting array order costs nothing and
    means a bar can never end up attached to the wrong channel if the
    device ever returns them out of order.
    """
    if not isinstance(entries, list):
        return None
    vals: dict[int, float] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        val = item.get("val")
        idx = item.get("index")
        if not isinstance(val, (int, float)) or not isinstance(idx, int):
            continue
        vals[idx] = float(val)
    if not vals:
        return None
    return [vals[k] for k in sorted(vals)]


class Tide16Coordinator:
    """Owns the persistent WebSocket connection and the last-known state."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._unsub_rms_refresh = None
        self._unsub_full_refresh = None
        self._unsub_hass_stop = None
        self._rms_lock = asyncio.Lock()
        self._resync_lock = asyncio.Lock()

        # v22: fast-metering hold. _fast_until is a loop timestamp, not a
        # flag - see async_request_fast_metering for why that's what makes
        # this impossible to leave stuck in fast mode.
        self._unsub_fast_refresh = None
        self._fast_until: float = 0.0

        # v22: the two sources that feed data["channel_names"]. Kept
        # separate rather than merged on arrival because they arrive in
        # either order and custom names must win regardless.
        self._output_speakers: dict[str, str] = {}
        self._custom_port_names: dict[str, str] = {}

        # v19: separate from self.data["volume_db"] (the last CONFIRMED
        # value) - this tracks the target of a volume command that hasn't
        # been confirmed yet, so back-to-back Volume +/- button presses
        # accumulate correctly instead of each one computing its "+2 dB"
        # from the same stale confirmed value while the first press's
        # confirmation is still in flight. Cleared once a matching
        # volume_change_db notification (or resync) confirms it, or on
        # disconnect - see _apply_volume_db and async_nudge_volume for the
        # v20 fix to a race that was still possible here.
        self._pending_volume_db: float | None = None
        self._pending_volume_db_ts: float | None = None

        # Public state, read by entities via coordinator.data.
        self.data: dict = {
            "connected": False,
            "status": "not connected",
            "volume_db": None,
            "muted": None,
            "source": None,
            "source_names": {},  # source id -> live display name (get_source_names)
            "signal_peak_db": None,
            "channel_db": None,  # v22: per-channel output levels, 16 floats
            "channel_names": [],  # v22: 1-based output index -> speaker name
            "bt_paired": None,
            "bt_track_title": None,
            "bt_track_artist": None,
            "bt_track_album": None,
            "bt_track_playing": None,
            "stream_format": None,
            "stream_channel_config": None,
            "stream_sample_rate": None,
            "stream_decoder_type": None,
            "ip_address": None,
            "speaker_config": None,
            "preset_index": None,
            "preset_name": None,
            "presets": {},
            "dirac_enabled": None,
            "dirac_selected_slot": None,
            "dirac_gain": None,
            "dirac_delay": None,
            "dirac_measuring": None,
            "raw": {},
        }

        # Request replies: req name -> applier(data).
        self._response_handlers = {
            "get_coordinator_status": self._apply_status,
            "get_volume_db": self._apply_volume_db,
            "get_mute": self._apply_mute,
            "get_source": self._apply_source,
            "get_source_names": self._apply_source_names,
            "get_output_speakers": self._apply_output_speakers,
            "get_custom_out_port_names": self._apply_custom_out_port_names,
            "get_bluetooth_status": self._apply_bluetooth,
            "get_stream_properties": self._apply_stream,
            "get_speaker_config_number": self._apply_speaker_config,
            "get_ip": self._apply_ip,
            "get_current_preset_index": self._apply_preset_index,
            "get_all_presets": self._apply_all_presets,
            "get_dirac_state": self._apply_dirac_state,
            "get_dirac_measuring_mode": self._apply_dirac_measuring,
            "get_rms_block_db": self._apply_rms_block_db,
        }

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    def async_connect(self) -> None:
        """Start the background connect/listen/reconnect loop.

        This is an intentionally never-ending task (it loops for the whole
        HA process lifetime, reconnecting as needed). hass.async_create_task
        is meant for tasks that finish as part of setup - HA's bootstrap
        waits for those and prints a "Something is blocking Home Assistant
        from wrapping up the start up phase" warning if they take too long,
        which is exactly what happened here. async_create_background_task
        is the correct API for a genuinely long-running task: HA tracks it
        for clean shutdown but does not wait on it during startup.
        """
        self._task = self.hass.async_create_background_task(
            self._run(), name="minidsp_tide16_coordinator"
        )
        self._unsub_hass_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_hass_stop
        )
        self._unsub_rms_refresh = async_track_time_interval(
            self.hass, self._async_rms_refresh, timedelta(seconds=RMS_REFRESH_INTERVAL)
        )
        self._unsub_full_refresh = async_track_time_interval(
            self.hass, self._async_full_refresh, timedelta(seconds=FULL_REFRESH_INTERVAL)
        )

    async def _async_hass_stop(self, _event) -> None:
        await self.async_stop()

    async def async_stop(self) -> None:
        """Idempotent: safe to call more than once (e.g. both from an
        integration unload/reload AND, later, real Home Assistant
        shutdown) without erroring or double-unsubscribing."""
        self._stopping = True
        if self._unsub_hass_stop is not None:
            self._unsub_hass_stop()
            self._unsub_hass_stop = None
        if self._unsub_rms_refresh is not None:
            self._unsub_rms_refresh()
            self._unsub_rms_refresh = None
        if self._unsub_fast_refresh is not None:
            self._unsub_fast_refresh()
            self._unsub_fast_refresh = None
        if self._unsub_full_refresh is not None:
            self._unsub_full_refresh()
            self._unsub_full_refresh = None
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    @callback
    def _async_rms_refresh(self, _now) -> None:
        if self._ws is not None and not self._ws.closed:
            self.hass.async_create_task(self._request_rms_state())

    @callback
    def async_request_fast_metering(self, duration: float = FAST_METERING_HOLD) -> None:
        """Grant FAST_RMS_INTERVAL polling for `duration` seconds.

        Called (repeatedly, as a keepalive) by the front-panel card while
        its bar meter is actually on screen. Extending a deadline rather
        than setting a flag is what makes this safe: every path out of fast
        mode is the deadline lapsing, so a card that goes away without
        telling us - closed tab, switched view, crashed, throttled by the
        browser - costs at most FAST_METERING_HOLD seconds of extra polling
        rather than leaving the device being hammered forever.

        Repeated calls just push the deadline out; the timer itself is
        created once and tears itself down in _async_fast_refresh.
        """
        self._fast_until = max(self._fast_until, self.hass.loop.time() + duration)
        if self._unsub_fast_refresh is None:
            self._unsub_fast_refresh = async_track_time_interval(
                self.hass,
                self._async_fast_refresh,
                timedelta(seconds=FAST_RMS_INTERVAL),
            )

    @callback
    def _async_fast_refresh(self, _now) -> None:
        # Self-cancelling: the moment the hold lapses this timer removes
        # itself, and the normal RMS_REFRESH_INTERVAL timer (which was
        # never touched) carries on as the idle cadence.
        if self.hass.loop.time() >= self._fast_until:
            if self._unsub_fast_refresh is not None:
                self._unsub_fast_refresh()
                self._unsub_fast_refresh = None
            return
        if self._ws is not None and not self._ws.closed:
            self.hass.async_create_task(self._request_rms_state())

    @callback
    def _async_full_refresh(self, _now) -> None:
        if self._ws is not None and not self._ws.closed:
            self.hass.async_create_task(self._request_resync_state())

    async def _run(self) -> None:
        while not self._stopping:
            try:
                await self._connect_and_listen()
            except Exception:  # noqa: BLE001 - this loop must never die
                # exc_info=True: this is meant to catch expected network
                # hiccups (device asleep, Wi-Fi blip), but without the
                # traceback an actual bug in this loop would be very hard
                # to diagnose from the logs alone.
                _LOGGER.debug("Tide16 connection error", exc_info=True)
            self._set_connected(False, status="not connected")
            if self._stopping:
                return
            await asyncio.sleep(RECONNECT_INTERVAL)

    async def _connect_and_listen(self) -> None:
        _LOGGER.debug("Connecting to Tide16 coordinator at %s", self.url)
        session = async_get_clientsession(self.hass)
        async with session.ws_connect(self.url, heartbeat=15, timeout=10) as ws:
            self._ws = ws
            # "connecting", not "ready": the device hasn't confirmed
            # anything yet at this point, only the TCP/WS handshake
            # succeeded. get_coordinator_status (requested right below) or
            # its notification will set the real status once known.
            self._set_connected(True, status="connecting")
            await self._request_rms_state()
            await self._request_resync_state()
            await self._request_startup_state()

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._handle_message(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        self._ws = None

    async def _request_rms_state(self) -> None:
        """get_rms_block_db has no push notification, so it's the only
        thing that genuinely needs a short polling interval."""
        if self._rms_lock.locked():
            return
        async with self._rms_lock:
            await self._send({"endpoint": "get_rms_block_db"})

    async def _request_resync_state(self) -> None:
        """Safety-net resync for fields that are normally kept in sync by
        push notifications (status/volume/mute/source) - runs much less
        often than the RMS polling since it's just a fallback in case a
        notification was ever missed (e.g. right after a reconnect)."""
        if self._resync_lock.locked():
            return
        async with self._resync_lock:
            for endpoint in (
                "get_coordinator_status",
                "get_volume_db",
                "get_mute",
                "get_source",
            ):
                await self._send({"endpoint": endpoint})

    async def _request_startup_state(self) -> None:
        """Ask once for the fields that rarely change and/or have their own
        push notification (no need to keep re-requesting these)."""
        for endpoint in (
            "get_source_names",
            "get_output_speakers",
            "get_custom_out_port_names",
            "get_ip",
            "get_bluetooth_status",
            "get_stream_properties",
            "get_speaker_config_number",
            "get_current_preset_index",
            "get_all_presets",
            "get_dirac_state",
            "get_dirac_measuring_mode",
        ):
            await self._send({"endpoint": endpoint})

    def _handle_message(self, raw: str) -> None:
        _LOGGER.debug("Tide16 raw message: %s", raw)
        try:
            obj = json.loads(raw)
        except ValueError:
            _LOGGER.debug("Tide16 sent a non-JSON payload: %s", raw)
            return
        if not isinstance(obj, dict):
            return

        if "notification" in obj:
            self._handle_notification(obj)
        elif "req" in obj:
            self._handle_response(obj)
        else:
            return

        async_dispatcher_send(self.hass, SIGNAL_TIDE16_UPDATE)

    def _handle_response(self, obj: dict) -> None:
        req = obj.get("req")
        status = obj.get("status")
        data = obj.get("data")

        if req:
            self.data["raw"][req] = obj

        if status is not None and status != "OK":
            _LOGGER.warning("Tide16 request %s failed: status=%s data=%s", req, status, data)
            return

        handler = self._response_handlers.get(req)
        if handler is not None:
            handler(data)

    def _handle_notification(self, obj: dict) -> None:
        name = obj.get("notification")
        value = obj.get("value")
        data = obj.get("data")

        # miniDSP's own docs: "your code should allow for unrecognized
        # notifications, as the Tide16 will send more than are documented
        # here" - hence the plain if/elif with a silent fallthrough below,
        # instead of a strict lookup table.
        if name == "coordinator_status":
            self._apply_status(value)
        elif name == "volume_change":
            pass  # linear-gain scale, deliberately unused since v22 - see
            # the module docstring's v22 note.
        elif name == "volume_change_db":
            self._apply_volume_db(value)
        elif name == "mute_change":
            self._apply_mute(value)
        elif name == "source_change":
            self._apply_source(value)
        elif name == "source_names_change":
            self._apply_source_names(data)
        elif name == "preset_change":
            self.data["preset_index"] = obj.get("index")
            self.data["preset_name"] = obj.get("name")
        elif name == "dirac_state":
            self._apply_dirac_state(value)
        elif name == "dirac_measurement_mode":
            self._apply_dirac_measuring(value)
        elif name == "stream_changes":
            self._apply_stream(data)
        elif name == "bluetooth_status":
            self._apply_bluetooth(data)
        elif name == "speaker_config_number_change":
            # Undocumented in the Notifications page, but present in
            # miniDSP's own official example client (script.js), which
            # itself defensively reads `msg.data ?? msg.value` for this
            # one - mirrored here since we can't be 100% sure which
            # envelope field an undocumented notification uses.
            self._apply_speaker_config(value if value is not None else data)
        # else: unrecognized notification, ignored on purpose.

    # --- State appliers, shared between request replies and notifications ---

    def _apply_status(self, value) -> None:
        if isinstance(value, str):
            self.data["status"] = value

    def _apply_volume_db(self, value) -> None:
        if not isinstance(value, (int, float)):
            return
        confirmed = float(value)
        self.data["volume_db"] = confirmed

        # v20 fix (a follow-up review caught this): v19 cleared
        # _pending_volume_db as soon as ANY confirmation arrived, even one
        # that didn't actually match the pending target. That's wrong if
        # an older command's notification arrives after a newer command
        # already moved the target further (e.g. press 1 -> -28, press 2
        # -> -26 while press 1's own confirmation is still in flight; that
        # -28 confirmation must not wipe out the still-pending -26). Only
        # clear it when the confirmed value actually matches what we're
        # waiting for.
        if self._pending_volume_db is not None and math.isclose(
            confirmed, self._pending_volume_db, abs_tol=0.05
        ):
            self._pending_volume_db = None
            self._pending_volume_db_ts = None

    def _apply_mute(self, value) -> None:
        if isinstance(value, bool):
            self.data["muted"] = value

    def _apply_source(self, value) -> None:
        if isinstance(value, str):
            self.data["source"] = value

    def _apply_source_names(self, data) -> None:
        """Live display names from the device (get_source_names /
        source_names_change) - used to keep entity friendly names in sync
        with whatever the user has renamed on the Tide16 itself, WITHOUT
        touching entity_id/unique_id (those stay pinned to the fixed
        source ids in const.py so existing automations never break)."""
        if isinstance(data, dict):
            self.data["source_names"] = {k: v for k, v in data.items() if isinstance(v, str)}

    def _apply_output_speakers(self, data) -> None:
        """Which speaker each physical output is assigned to
        (get_output_speakers), e.g. {"1": "LeftFront", ..., "11": "Sub2"}.

        This is the real assignment, not an inference from
        speaker_config: on a 7.2.2 setup the device returns exactly 11
        entries and outputs 12-16 are simply absent from the map. That
        distinction matters - an absent output is unassigned, which is
        not the same as an assigned one that happens to be silent, and
        both read -122.5 in the metering.

        Keys are the same 1-based index _channels_db() sorts by, so the
        two line up positionally without any further mapping.
        """
        if not isinstance(data, dict):
            return
        self._output_speakers = {
            str(k): v for k, v in data.items() if isinstance(v, str) and v
        }
        self._rebuild_channel_names()

    def _apply_custom_out_port_names(self, data) -> None:
        """User-assigned output port names (get_custom_out_port_names).

        Empty on a stock unit. When set, these are what the owner called
        the port on the Tide16 itself, so they win over the stock
        speaker name - same reasoning as _apply_source_names.
        """
        if not isinstance(data, dict):
            return
        self._custom_port_names = {
            str(k): v for k, v in data.items() if isinstance(v, str) and v
        }
        self._rebuild_channel_names()

    def _rebuild_channel_names(self) -> None:
        """Flatten the two name sources into a positional list.

        A list rather than a dict because it is consumed alongside
        channel_db, which is already a positional list - handing a
        dashboard two structures it has to correlate by key would just
        move this join into every consumer. Unassigned outputs are None,
        never a placeholder string, so a consumer can tell "no speaker
        here" from "a speaker called something".
        """
        stock = getattr(self, "_output_speakers", {})
        custom = getattr(self, "_custom_port_names", {})
        if not stock and not custom:
            return
        count = max(
            (int(k) for k in list(stock) + list(custom) if k.isdigit()),
            default=0,
        )
        self.data["channel_names"] = [
            custom.get(str(i)) or stock.get(str(i)) or None
            for i in range(1, count + 1)
        ]

    def _apply_bluetooth(self, data) -> None:
        if not isinstance(data, dict):
            return
        if "paired" in data:
            self.data["bt_paired"] = bool(data["paired"])
        music = data.get("music")
        if isinstance(music, dict):
            self.data["bt_track_title"] = music.get("title") or None
            self.data["bt_track_artist"] = music.get("artist") or None
            self.data["bt_track_album"] = music.get("album") or None
            self.data["bt_track_playing"] = bool(music.get("playing"))

    def _apply_stream(self, data) -> None:
        if not isinstance(data, dict):
            return
        self.data["stream_format"] = data.get("decoder_stream_src_format") or None
        self.data["stream_channel_config"] = data.get("channel_config") or None
        self.data["stream_sample_rate"] = data.get("sample_rate") or None
        self.data["stream_decoder_type"] = data.get("decoder_type") or None

    def _apply_speaker_config(self, value) -> None:
        if isinstance(value, str):
            self.data["speaker_config"] = value

    def _apply_ip(self, data) -> None:
        if isinstance(data, dict):
            self.data["ip_address"] = data.get("wired")

    def _apply_preset_index(self, value) -> None:
        if isinstance(value, (int, float, str)):
            self.data["preset_index"] = value
            self._resolve_preset_name()

    def _apply_all_presets(self, data) -> None:
        if isinstance(data, list):
            self.data["presets"] = {
                str(item.get("id")): item.get("name")
                for item in data
                if isinstance(item, dict)
            }
            self._resolve_preset_name()

    def _resolve_preset_name(self) -> None:
        index = self.data.get("preset_index")
        presets = self.data.get("presets") or {}
        if index is None:
            return
        name = presets.get(str(index))
        if name:
            self.data["preset_name"] = name

    def _apply_dirac_state(self, data) -> None:
        if not isinstance(data, dict):
            return
        if "enabled" in data:
            self.data["dirac_enabled"] = bool(data["enabled"])
        if "selected_slot" in data:
            self.data["dirac_selected_slot"] = data["selected_slot"]
        if "gain" in data:
            self.data["dirac_gain"] = bool(data["gain"])
        if "delay" in data:
            self.data["dirac_delay"] = bool(data["delay"])

    def _apply_dirac_measuring(self, value) -> None:
        if isinstance(value, bool):
            self.data["dirac_measuring"] = value

    def _apply_rms_block_db(self, data) -> None:
        if isinstance(data, dict):
            out = data.get("out")
            self.data["signal_peak_db"] = _peak_db(out)
            self.data["channel_db"] = _channels_db(out)

    def _set_connected(self, connected: bool, status: str) -> None:
        self.data["connected"] = connected
        self.data["status"] = status
        if not connected:
            # Entities go "unavailable" based on "connected" (see
            # entity.py), so this is mostly hygiene: clear fields that are
            # genuinely misleading if left stale (a "signal present"
            # reading from before the device went offline, or a nudge
            # target aimed at a connection that no longer exists).
            self.data["signal_peak_db"] = None
            self._pending_volume_db = None
            self._pending_volume_db_ts = None
        async_dispatcher_send(self.hass, SIGNAL_TIDE16_UPDATE)

    async def _send(self, payload: dict) -> bool:
        """Send a request to the Tide16. Returns True once the JSON has
        been written to the socket - NOT proof the Tide16 accepted it
        (that's what the "OK"/"ERROR" status in its reply, or the
        matching notification, is for). Public command methods therefore
        no longer branch on this return value to decide whether to touch
        self.data - see the v17 note in the module docstring."""
        if self._ws is None or self._ws.closed:
            _LOGGER.warning("Tide16 unreachable (standby?) - not sent: %s", payload)
            return False
        try:
            await self._ws.send_json(payload)
        except (aiohttp.ClientError, ConnectionError, RuntimeError) as err:
            _LOGGER.warning("Unable to send Tide16 command %s: %s", payload, err)
            return False
        return True

    # --- Public commands, used by the entities ---------------------------
    #
    # v17: none of these touch self.data anymore. They only send the
    # command; the Tide16's own confirmation (a notification, almost
    # always, or the resync fallback) is what actually updates state, via
    # the _apply_*() methods above. See the v17 note in the module
    # docstring for why.

    async def async_set_volume_db(self, db: float) -> bool:
        """Set volume via the officially documented set_volume_db endpoint.

        Range confirmed on docs.minidsp.com: -127.5 dB (effectively
        silent) to 0.0 dB (maximum).

        v20: returns whether the command was actually sent (see _send),
        so async_nudge_volume can roll back its pending target if it
        wasn't - this doesn't reintroduce the v17 optimistic-update bug,
        since self.data is still never touched here, only
        _pending_volume_db bookkeeping.
        """
        db = max(MIN_VOLUME_DB, min(MAX_VOLUME_DB, db))
        return await self._send({"endpoint": "set_volume_db", "value": round(db, 2)})

    async def async_nudge_volume(self, delta_db: float) -> None:
        """Base the nudge on the last requested-but-unconfirmed target if
        one is already in flight, otherwise the last confirmed volume.

        v19 fix: basing every nudge purely on the last CONFIRMED volume
        (the v17 approach) sounds right - "don't compound a command the
        device might not have accepted" - but it has a real side effect:
        three quick presses of Volume + before the first notification
        comes back would each compute "+2 dB" from the same stale
        confirmed value and all send the same target, silently dropping
        two of the three presses. Tracking the pending target separately
        fixes that while keeping the original goal.

        v20 fixes two gaps a follow-up review found in that mechanism:
          - A pending target could be cleared by ANY volume confirmation,
            even one that didn't match it (see _apply_volume_db) - fixed
            there, not here, but it's what makes trusting
            _pending_volume_db here safe again.
          - The pending target used to be recorded before knowing whether
            the command actually reached the Tide16 (async_set_volume_db
            didn't report failure). If _send() fails outright, the
            pending target is now rolled back instead of being left
            pointing at a command that never left Home Assistant.
        A pending target is also only trusted for _PENDING_VOLUME_TIMEOUT
        seconds, as a safety net against a confirmation that never
        arrives at all (e.g. the command was rejected, or a notification
        was dropped) - past that, a nudge falls back to the last confirmed
        value rather than compounding on a guess indefinitely.
        """
        now = time.monotonic()
        pending = self._pending_volume_db
        if pending is not None and (
            self._pending_volume_db_ts is None
            or now - self._pending_volume_db_ts > _PENDING_VOLUME_TIMEOUT
        ):
            pending = None

        confirmed = self.data.get("volume_db")
        base = pending if pending is not None else confirmed
        if base is None:
            base = MIN_VOLUME_DB
        target = max(MIN_VOLUME_DB, min(MAX_VOLUME_DB, base + delta_db))

        previous_pending, previous_ts = self._pending_volume_db, self._pending_volume_db_ts
        self._pending_volume_db = target
        self._pending_volume_db_ts = now

        if not await self.async_set_volume_db(target):
            # Never actually sent - don't leave a pending target aimed at
            # a command the Tide16 will never see.
            self._pending_volume_db = previous_pending
            self._pending_volume_db_ts = previous_ts

    async def async_set_mute(self, muted: bool) -> None:
        await self._send({"endpoint": "set_mute", "value": muted})

    async def async_select_source(self, source_id: str) -> None:
        if source_id not in _KNOWN_SOURCE_IDS:
            _LOGGER.warning(
                "Refusing to select unknown Tide16 source %r (known: %s)",
                source_id,
                sorted(_KNOWN_SOURCE_IDS),
            )
            return
        await self._send({"endpoint": "set_source", "value": source_id})

    async def async_shutdown(self) -> None:
        await self._send({"endpoint": "shutdown"})

    async def async_reboot(self) -> None:
        await self._send({"endpoint": "reboot"})

    async def async_bluetooth_pair(self) -> None:
        await self._send({"endpoint": "set_bt_pairing_mode"})

    async def async_set_dirac_enabled(self, enabled: bool) -> None:
        """Enable/disable Dirac Live room correction.

        gain/delay are left unchanged (omitted - both are optional per the
        official docs, and default to "unchanged" server-side).
        """
        await self._send({"endpoint": "set_dirac_state", "enabled": enabled})
