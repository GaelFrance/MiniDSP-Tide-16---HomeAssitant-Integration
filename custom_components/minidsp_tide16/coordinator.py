"""State for one Tide16, assembled from replies and pushes.

The unit pushes most of what changes - volume, mute, source, status, stream,
preset, Dirac - so this is not a polling coordinator with a scrape interval.
It keeps one supervised connection open, applies whatever arrives, and only
re-asks on two schedules:

    slow sweep    every 60s, a safety net in case a push was missed across a
                  reconnect, plus get_settings, which nothing ever pushes
    metering      every 1s idle, every 100ms while something is watching

Metering is the reason the split exists.  `get_rms_block_db` is the one thing
with no push behind it, and the front-panel card draws it as a live bar meter,
where 5s between samples reads as a broken meter rather than a slow one.  So
the card subscribes over the websocket API while it is on screen and the fast
cadence runs only while subscribers exist - see websocket.py.

The idle cadence is not free either, even with nobody watching: it is the only
thing feeding the audio-signal sensor, and how often it looks sets how late
that sensor can be - see _apply_signal.

The 16 levels deliberately never become entity state.  Four updates a second
of a sixteen-float attribute is a database problem, and the previous design
needed a `recorder:` exclusion in the user's own configuration.yaml to stay out
of trouble.  Here they go straight to the subscribed connections, and the only
entity derived from them is a binary sensor that changes when audio starts or
stops.
"""

from __future__ import annotations

import asyncio
import email.utils
import logging
import math
import re
import statistics
import time
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import Tide16Client, Tide16Error
from .api.const import (
    CHANNEL_COUNT,
    CHECK_FOR_UPDATE,
    GET_DIRAC_FILTER,
    GET_FRONT_PANEL_FW,
    GET_FRONT_PANEL_PACKAGED_FW,
    GET_IP,
    GET_RMS_DB,
    GET_SETTINGS,
    GET_STATUS,
    MAX_VOLUME_DB,
    MIN_VOLUME_DB,
    N_BLUETOOTH,
    N_DIRAC_MEASURING,
    N_DIRAC_STATE,
    N_FRONT_PANEL_FW,
    N_MUTE,
    N_PRESET,
    N_SOURCE,
    N_SOURCE_NAMES,
    N_SPEAKER_CONFIG,
    N_STATUS,
    N_STREAM,
    N_UPDATE,
    N_VOLUME_DB,
    REFRESH_ENDPOINTS,
    SET_VOLUME_DB,
    SILENCE_DB,
    UPDATE_PROGRESS_CODES,
    UPDATE_PROGRESS_TEXTS,
    WEB_PORT,
)
from .const import (
    DEFAULT_SIGNAL_RELATIVE,
    DEFAULT_SILENCE_HOLD,
    DEFAULT_SILENCE_LEVEL,
    DEFAULT_UPDATE_CHECK,
    DOMAIN,
    MAX_SILENCE_LEVEL,
    MIN_SILENCE_LEVEL,
    SIGNAL_FLOOR_DB,
)

_LOGGER = logging.getLogger(__name__)

FULL_REFRESH = 60.0
# Nobody is watching the meter at this cadence, but the audio-signal sensor is
# still fed from it, so this is that sensor's resolution: how soon it can say
# audio started, and the grain the release below is counted in.  At the old 5s
# every transition it reported landed on a five-second grid, which is what gave
# the flapping away.  One request a second on a socket that answers 89 of them
# a second is not a load worth optimising against.
IDLE_METERING = 1.0
# Matched to the unit, measured rather than assumed: it answers
# get_rms_block_db 89 times a second with a 5ms round trip, but the numbers it
# returns only change about every 90ms - so that is how often it recomputes
# the block, and anything faster than this just re-reads the same values.
#
# At the old 250ms this under-sampled the hardware by nearly three to one, and
# every reading could be a quarter-second old before it was even asked for.
FAST_METERING = 0.1

# get_settings gets its own loop, because it is the only source for things the
# user can change WITHOUT Home Assistant - the upmixer, the Dolby profile, the
# source map - and nothing pushes any of them. Left on the 60s sweep, a change
# made on the front panel, the remote or the unit's own web page took up to a
# minute to show, which reads as the panel being out of sync with the device.
#
# It is a big reply, so it is on its own timer rather than pulling the whole
# 14-endpoint sweep up with it.
SETTINGS_REFRESH = 5.0

# How often to ask miniDSP's update server, by way of the unit - it is the unit
# that goes out to the internet, not Home Assistant - and to read its clock.  A unit that was in
# standby when a check fell due is checked when it comes back instead, so the
# hour is a floor on how often, not a promise of when.
UPDATE_CHECK = 3600.0

DISCONNECTED_STATUS = "not connected"
# Between the socket opening and the unit's first status reply. Scripts that
# switch the unit on wait for anything other than "not connected" and then
# for "ready", so this must not be None (which would read as "unknown").
CONNECTING_STATUS = "connecting"

# A volume target sent but not yet confirmed by a volume_change_db push is
# trusted for this long when the next step is computed - see
# async_nudge_volume.
PENDING_VOLUME_TIMEOUT = 5.0

# Audio Signal attributes (peak_db, level_db): refreshed at most this often.
SIGNAL_ATTR_INTERVAL = 5.0


class Tide16Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns the connection and everything read off it."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        *,
        silence_level: float = DEFAULT_SILENCE_LEVEL,
        silence_hold: float = DEFAULT_SILENCE_HOLD,
        signal_relative: float = DEFAULT_SIGNAL_RELATIVE,
        update_check: bool = DEFAULT_UPDATE_CHECK,
    ) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN} {host}", update_interval=None)
        self.host = host
        self.port = port
        self.data = _blank()
        self.data["status"] = DISCONNECTED_STATUS

        # Both settable per install - see the options flow.  They arrive here
        # rather than being read from the entry, because the coordinator has no
        # business knowing what a config entry is.
        self.silence_level = silence_level
        self.silence_hold = silence_hold
        self.signal_relative = signal_relative
        self.update_check = update_check

        self._pending_volume_db: float | None = None
        self._pending_volume_ts: float | None = None

        # levels live outside `data` on purpose: they move at 4 Hz and must not
        # drag every entity through a state write with them
        self.levels: list[float] = [SILENCE_DB] * CHANNEL_COUNT
        self._signal = False
        self._signal_seen = 0.0
        self._signal_attr_ts = 0.0

        # The filter index get_settings last reported, so a change of filter -
        # made here, on the unit, or from miniDSP's own app - re-reads the
        # filter's record instead of waiting out the minute-long sweep.
        self._dirac_index: Any = None

        # When the last update check went out, on the monotonic clock; None
        # until the first one has.
        self._update_asked: float | None = None
        # Status texts that are really the update check talking - see
        # _apply_status.  Seeded with the ones seen, grown by any new ones.
        self._update_progress: set[str] = set(UPDATE_PROGRESS_TEXTS)

        # The two halves of the channel legend, kept apart because they arrive
        # in separate replies in no fixed order and either one has to be able
        # to rebuild the merged list on its own.
        self._speaker_names: dict[int, str] = {}
        self._custom_port_names: dict[int, str] = {}

        # Set by __init__ once the entry is up. Declared here so the type is
        # visible; it is not built in the coordinator because it needs the
        # coordinator, and the import would be a circle.
        self.autodim: Any = None

        self._subscribers = 0
        # Tripped when a subscriber arrives, so the metering loop can stop
        # waiting out an idle sleep it no longer needs - see _metering_loop.
        self._meter_wake = asyncio.Event()
        self._loops: list[asyncio.Task] = []
        self._client = Tide16Client(
            host,
            port,
            session=async_get_clientsession(hass),
            on_notification=self._on_notification,
            on_reply=self._on_reply,
            on_connected=self._on_connected,
        )

    @property
    def client(self) -> Tide16Client:
        return self._client

    @property
    def connected(self) -> bool:
        return self._client.connected

    # --- lifecycle ---------------------------------------------------------

    async def async_start(self) -> None:
        await self._client.start()
        self._loops = [
            self.hass.async_create_background_task(self._refresh_loop(), "tide16 sweep"),
            self.hass.async_create_background_task(self._metering_loop(), "tide16 meter"),
            self.hass.async_create_background_task(
                self._settings_loop(), "tide16 settings"
            ),
            self.hass.async_create_background_task(
                self._update_loop(), "tide16 update check"
            ),
        ]

    async def async_stop(self) -> None:
        for task in self._loops:
            task.cancel()
        self._loops = []
        await self._client.stop()

    # --- metering subscribers ---------------------------------------------

    @callback
    def add_meter_subscriber(self) -> None:
        self._subscribers += 1
        self._meter_wake.set()

    @callback
    def remove_meter_subscriber(self) -> None:
        # never below zero: a connection can drop after the entry is unloaded
        self._subscribers = max(0, self._subscribers - 1)

    @property
    def metering_fast(self) -> bool:
        return self._subscribers > 0

    # --- loops -------------------------------------------------------------

    async def _refresh_loop(self) -> None:
        while True:
            if self._client.connected:
                await self._sweep()
            await asyncio.sleep(FULL_REFRESH)

    async def _read_clock(self) -> None:
        """How far the unit's clock is from this one, in whole seconds.

        Read off the `Date` header of the unit's control page, which is to the
        second, so an offset of a second or two is only the header's rounding
        and the round trip.  A unit whose NTP has not reached a server sits at
        whatever it booted with, and that is minutes or years, not seconds.
        """
        session = async_get_clientsession(self.hass)
        try:
            async with session.head(
                f"http://{self.host}:{WEB_PORT}/",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                stamp = resp.headers.get("Date")
        except (aiohttp.ClientError, TimeoutError):
            return
        if not stamp:
            return
        try:
            unit = email.utils.parsedate_to_datetime(stamp)
        except (TypeError, ValueError):
            return
        offset = round((unit - dt_util.utcnow()).total_seconds())
        if offset != self.data.get("clock_offset"):
            self.data["clock_offset"] = offset
            self.async_set_updated_data(self.data)

    async def _settings_loop(self) -> None:
        """Keep the settings-only values following the device, not just us."""
        while True:
            if self._client.connected:
                await self._client.send(GET_SETTINGS)
            await asyncio.sleep(SETTINGS_REFRESH)

    async def _update_loop(self) -> None:
        """Ask for updates once an hour.

        The first check is not made here: at startup the connection is not up
        yet, so it is made on connecting instead - see _on_reconnect.
        """
        while True:
            await asyncio.sleep(UPDATE_CHECK)
            if not self.update_check:
                continue
            if self._client.connected and self._update_due:
                await self.async_check_for_update()

    @property
    def _update_due(self) -> bool:
        # A little short of the hour, so the loop's own check is never skipped
        # for landing a few milliseconds early against the last one.
        return (
            self._update_asked is None
            or time.monotonic() - self._update_asked >= UPDATE_CHECK - 60.0
        )

    async def async_check_for_update(self) -> None:
        """Every firmware level, whether miniDSP has anything newer, and the clock.

        The Tide, HDMI and XMOS versions need no asking here - get_settings
        carries them every five seconds.  The front-panel controller's two do
        not come from anywhere else, and neither does the server's answer.

        The clock rides along: a unit that cannot reach an NTP server most
        likely cannot reach miniDSP's update server either, so the two go
        wrong together and are worth looking at on the same schedule.
        """
        self._update_asked = time.monotonic()
        await self._read_clock()
        for endpoint in (GET_FRONT_PANEL_FW, GET_FRONT_PANEL_PACKAGED_FW, CHECK_FOR_UPDATE):
            if not await self._client.send(endpoint):
                return

    async def _metering_loop(self) -> None:
        """Poll the levels, fast while something is watching.

        The wait is interruptible on purpose. With nothing watching this sits
        idle for five seconds at a time, and a plain sleep cannot be cut short
        - so opening the view subscribed, and then waited out however much of
        that five seconds was left before the first frame of data arrived. The
        meter held its last values for up to five seconds and then sprang to
        life, which reads as the card being broken rather than idle.
        """
        while True:
            if self._client.connected:
                await self._client.send(GET_RMS_DB)
            delay = FAST_METERING if self.metering_fast else IDLE_METERING
            try:
                await asyncio.wait_for(self._meter_wake.wait(), delay)
            except TimeoutError:
                pass  # nothing arrived; this is the ordinary cadence
            else:
                # A subscriber turned up: go round now, at the fast cadence.
                self._meter_wake.clear()

    async def _sweep(self) -> None:
        for endpoint in REFRESH_ENDPOINTS:
            if endpoint == GET_SETTINGS:
                continue  # _settings_loop owns this one
            if not await self._client.send(endpoint):
                return
            # the unit answers in order; this keeps a burst of 14 requests from
            # arriving as one lump it has to queue
            await asyncio.sleep(0.05)

    # --- connection state --------------------------------------------------

    @callback
    def _on_connected(self, connected: bool) -> None:
        if connected:
            self.hass.async_create_task(self._on_reconnect())
            return
        # Standby: the unit is gone, and every reading with it, so the panel
        # dashes rather than printing a stale number.  Three things survive:
        # `status`, because "not connected" is itself the answer to print; the
        # held speaker names, so the meter's legend keeps naming the channels;
        # and the firmware versions and the last update check, which cannot
        # change while the unit is off.
        held = self.data.get("channel_names_held") or []
        versions = self.data.get("versions") or {}
        update_check = self.data.get("update_check") or {}
        self.data = _blank()
        self.data["status"] = DISCONNECTED_STATUS
        self.data["channel_names_held"] = held
        self.data["versions"] = versions
        self.data["update_check"] = update_check
        self._signal = False
        self._signal_seen = 0.0
        self._pending_volume_db = None
        self._pending_volume_ts = None
        self.levels = [SILENCE_DB] * CHANNEL_COUNT
        self.async_set_updated_data(self.data)

    async def _on_reconnect(self) -> None:
        if not self.data.get("status") or self.data["status"] == DISCONNECTED_STATUS:
            self.data["status"] = CONNECTING_STATUS
            self.async_set_updated_data(self.data)
        # a moment for the coordinator process on the unit to finish coming up
        await asyncio.sleep(0.5)
        await self._sweep()
        # The IP never changes while connected, so it is asked once here
        # rather than on every sweep.
        await self._client.send(GET_IP)
        if self.update_check and self._update_due:
            await self.async_check_for_update()
        else:
            # The clock is read with the update check upstream; with the
            # periodic check off it is still read once per connection (an
            # HTTP HEAD on the control page - it does not touch the status).
            await self._read_clock()

    # --- inbound -----------------------------------------------------------

    @callback
    def _on_reply(self, endpoint: str, data: Any) -> None:
        if endpoint == GET_RMS_DB:
            self._apply_levels(data)
            return
        handler = _REPLY_APPLIERS.get(endpoint)
        if handler is None:
            return
        handler(self, data)
        self.async_set_updated_data(self.data)

    @callback
    def _on_notification(self, name: str, payload: Any) -> None:
        # miniDSP's docs warn the unit sends more notifications than they
        # document, so an unknown name is dropped rather than logged as a fault
        handler = _PUSH_APPLIERS.get(name)
        if handler is None:
            return
        handler(self, payload)
        self.async_set_updated_data(self.data)

    # --- appliers ----------------------------------------------------------

    def _apply_levels(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        out = data.get("out")
        if not isinstance(out, list):
            return
        levels = [SILENCE_DB] * CHANNEL_COUNT
        reported: list[float] = []
        for entry in out:
            if not isinstance(entry, dict):
                continue
            index = entry.get("index")
            value = entry.get("val")
            if (
                isinstance(index, int)
                and 1 <= index <= CHANNEL_COUNT
                and isinstance(value, (int, float))
            ):
                levels[index - 1] = float(value)
                reported.append(float(value))
        self.levels = levels

        # The only entity fed by metering, and only when the envelope flips:
        # four state writes a second is exactly what this design exists to
        # avoid.
        # Only what the unit reported: the SILENCE_DB padding above is for the
        # card's meter, and -70 dB read as a level would be "signal" at any
        # volume under -10 dB once compensated.
        if reported:
            self._apply_signal(max(reported))

    def _apply_signal(self, peak: float) -> None:
        """Fast attack, slow release.

        One sample is not evidence that the audio stopped.  `get_rms_block_db`
        answers with a single ~90ms block, and program material puts every
        output under the threshold for a block at a time with the audio
        running - between words, across a scene cut, under a fade.

        Testing one sample and believing it turned those gaps into state
        changes.  Worse, it turned them into gaps the length of the poll: the
        sample that landed in a 90ms pause reported silence until the next poll
        five seconds later, so a listener hearing continuous audio watched the
        sensor report several hundred transitions across an evening, none of
        which happened.

        So audio starting is believed at once, and audio stopping only after
        `silence_hold` seconds in which no sample was heard.

        What counts as heard is relative to the master volume (from
        minidsp_tide16 0.30): the meters are post-volume, so the programme
        level is peak - volume_db, compared to `signal_relative`. The raw peak
        must also clear SIGNAL_FLOOR_DB. Until the volume is known, the fixed
        `silence_level` is the fallback.

        The peak and programme level are published for the Audio Signal
        sensor's attributes, but at most every SIGNAL_ATTR_INTERVAL seconds
        and only when they moved by a dB or more - the levels themselves
        must not become a once-a-second recorder write.
        """
        now = time.monotonic()
        volume = self.data.get("volume_db")
        level = None if volume is None else peak - float(volume)
        if level is None:
            heard = peak > self.silence_level
        else:
            heard = peak > SIGNAL_FLOOR_DB and level > self.signal_relative

        changed = False
        if now - self._signal_attr_ts >= SIGNAL_ATTR_INTERVAL and (
            _moved(self.data.get("signal_peak_db"), peak)
            or _moved(self.data.get("signal_level_db"), level)
        ):
            self._signal_attr_ts = now
            self.data["signal_peak_db"] = round(peak, 1)
            self.data["signal_level_db"] = None if level is None else round(level, 1)
            self.data["signal_threshold_db"] = (
                self.silence_level if level is None else self.signal_relative
            )
            changed = True

        if heard:
            self._signal_seen = now
            if not self._signal:
                self._signal = True
                self.data["signal"] = True
                changed = True
        elif self._signal and now - self._signal_seen >= self.silence_hold:
            self._signal = False
            self.data["signal"] = False
            changed = True

        if changed:
            self.async_set_updated_data(self.data)

    async def async_measure_levels(self, duration: float) -> dict[str, Any]:
        """Watch the output for a while and describe what it found.

        This is what makes the silence level settable with evidence rather than
        taste.  The number a user needs is somewhere in the gap between their
        own noise floor and the quietest thing their material actually does,
        and Home Assistant shows them neither - so a threshold field on its own
        is a slider nobody can reason about.

        It subscribes to metering exactly as the card does, so the sampling
        runs at the fast cadence and drops back to idle when it is finished.
        """
        if not self._client.connected:
            raise HomeAssistantError(
                "The Tide16 is not connected, so there is nothing to measure."
            )

        self.add_meter_subscriber()
        peaks: list[float] = []
        try:
            end = time.monotonic() + duration
            while time.monotonic() < end:
                peaks.append(max(self.levels))
                await asyncio.sleep(FAST_METERING)
        finally:
            self.remove_meter_subscriber()

        if not peaks:
            raise HomeAssistantError("No levels arrived from the Tide16.")

        floor = min(peaks)
        below = [p for p in peaks if p <= self.silence_level]
        longest = run = 0
        for p in peaks:
            run = run + 1 if p <= self.silence_level else 0
            longest = max(longest, run)

        # 30 dB over the quietest thing seen.  Run with nothing playing, that
        # floor is the system's own noise and this clears it comfortably; run
        # it with audio playing and the note below says so, because then the
        # floor is a gap in the programme and the suggestion means nothing.
        suggested = min(
            MAX_SILENCE_LEVEL, max(MIN_SILENCE_LEVEL, round(floor + 30.0))
        )

        result: dict[str, Any] = {
            "peak": round(max(peaks), 1),
            "median": round(statistics.median(peaks), 1),
            "floor": round(floor, 1),
            "below_threshold_percent": round(len(below) / len(peaks) * 100, 1),
            "longest_gap": round(longest * FAST_METERING, 2),
            "silence_level": self.silence_level,
            "silence_hold": self.silence_hold,
            "suggested_silence_level": float(suggested),
            "samples": len(peaks),
        }
        if statistics.median(peaks) > -90.0:
            result["note"] = (
                "Audio appears to have been playing. Run this again with "
                "nothing playing to measure your system's noise floor."
            )
        return result

    def _apply_status(self, value: Any) -> None:
        # An update check - ours, or one started from the unit's own page -
        # sets the status to its progress text and leaves it there until the
        # next read, a minute later.  That is not the unit's state, and an
        # hourly check would put a minute of it in the history every hour.
        if isinstance(value, str) and value not in self._update_progress:
            self.data["status"] = value

    def _apply_update(self, envelope: Any) -> None:
        """One `update` push: progress, or the server's answer."""
        if not isinstance(envelope, dict):
            return
        text = _clean(envelope.get("value"))
        code = envelope.get("code")
        if text is None:
            return
        if code in UPDATE_PROGRESS_CODES:
            self._update_progress.add(text)
            return
        available = _update_available(text)
        if available is None:
            # Worth seeing in the log: this is how the wording for an update
            # that IS there will first turn up.
            _LOGGER.info("Tide16 update check said %r (code %r)", text, code)
        self.data["update_check"] = {
            "result": text,
            "code": code,
            "available": available,
            "checked_at": dt_util.utcnow().isoformat(),
        }

    def _apply_update_done(self, _data: Any) -> None:
        # The reply comes after the answer.  The status the check left behind
        # is still the unit's, so read the real one back now rather than
        # holding the stale one until the next sweep.
        self._ask(GET_STATUS)

    def _apply_front_panel_fw(self, value: Any) -> None:
        version = _clean(value)
        if version is not None:
            self.data["versions"]["front_panel"] = version

    def _apply_front_panel_packaged_fw(self, data: Any) -> None:
        if isinstance(data, list) and data:
            self.data["versions"]["front_panel_packaged"] = ".".join(
                str(part) for part in data
            )

    def _apply_volume(self, value: Any) -> None:
        if not isinstance(value, (int, float)):
            return
        confirmed = float(value)
        self.data["volume_db"] = confirmed
        # Only the confirmation of the target being waited for clears it: an
        # older step's push arriving late must not wipe a newer target.
        if self._pending_volume_db is not None and math.isclose(
            confirmed, self._pending_volume_db, abs_tol=0.05
        ):
            self._pending_volume_db = None
            self._pending_volume_ts = None

    def _apply_mute(self, value: Any) -> None:
        if isinstance(value, bool):
            self.data["muted"] = value

    def _apply_source(self, value: Any) -> None:
        if isinstance(value, str):
            self.data["source_id"] = value

    def _apply_source_names(self, data: Any) -> None:
        if isinstance(data, dict):
            self.data["source_names"] = {str(k): str(v) for k, v in data.items()}

    def _apply_stream(self, data: Any) -> None:
        if isinstance(data, dict):
            self.data["stream"] = data

    def _apply_preset_index(self, data: Any) -> None:
        if isinstance(data, (int, str)):
            self.data["preset_index"] = data

    def _apply_preset_push(self, payload: Any) -> None:
        # preset_change carries its fields on the envelope itself
        if isinstance(payload, dict):
            if "index" in payload:
                self.data["preset_index"] = payload.get("index")
            if payload.get("name"):
                self.data["preset_name"] = payload.get("name")

    def _apply_presets(self, data: Any) -> None:
        if isinstance(data, list):
            self.data["presets"] = data

    def _apply_speaker_config(self, value: Any) -> None:
        if isinstance(value, str) and value:
            self.data["speaker_config"] = value

    def _apply_output_speakers(self, data: Any) -> None:
        if not isinstance(data, dict) or not data:
            return
        self._speaker_names = {int(k): v for k, v in data.items() if v}
        self._rebuild_channel_names()

    def _apply_custom_port_names(self, data: Any) -> None:
        """Names typed into the unit's own web UI, for ports it does not assign.

        `get_output_speakers` only reports what the decoder lays out - 13
        entries for 7.2.4 - so an output driven by hand through the routing
        matrix meters correctly and then sits in the legend with no name.  The
        unit does keep a name for those: `get_custom_out_port_names` is what
        its own control page writes, and it comes back empty until somebody
        names something, which is why this looked for a while like the device
        simply had nothing to offer.

        Unset ports come back as "" and are dropped rather than stored as a
        blank name, so an untouched unit behaves exactly as before.
        """
        if not isinstance(data, dict):
            return
        self._custom_port_names = {int(k): v for k, v in data.items() if v}
        self._rebuild_channel_names()

    def _rebuild_channel_names(self) -> None:
        """One list from both sources, indexed by output number.

        A custom name wins where there is one: it was typed deliberately,
        and it is what the unit's own UI shows for that port.
        """
        speakers = self._speaker_names
        custom = self._custom_port_names
        if not speakers and not custom:
            return
        top = max([*speakers, *custom])
        names = [custom.get(i) or speakers.get(i) or None for i in range(1, top + 1)]
        while names and names[-1] is None:
            names.pop()
        self.data["channel_names"] = names
        # Which of those are somebody's own words rather than the decoder's
        # enum, so the legend knows which ones not to abbreviate.
        chosen = sorted(n for n in custom if n <= len(names))
        self.data["custom_channels"] = chosen
        # Held across a dropout: the legend under the meter should keep naming
        # the speakers while the unit is away, rather than emptying out.
        if names:
            self.data["channel_names_held"] = names
            self.data["custom_channels_held"] = chosen

    def _apply_dirac(self, data: Any) -> None:
        if isinstance(data, dict):
            if data.get("selected_slot") != (self.data.get("dirac") or {}).get("selected_slot"):
                self._ask(GET_DIRAC_FILTER)
            self.data["dirac"] = data
        elif isinstance(data, bool):
            self.data["dirac"] = {**(self.data.get("dirac") or {}), "enabled": data}

    def _apply_dirac_filter(self, data: Any) -> None:
        """The loaded filter's record. An empty reply means no filter at all."""
        if not isinstance(data, dict):
            return
        self.data["dirac_filter"] = {
            "index": data.get("index"),
            "name": _clean(data.get("description") or data.get("name")),
            "type": _clean(data.get("filter_type")),
        } if data else {}

    def _ask(self, endpoint: str) -> None:
        """Send a request from inside a (synchronous) applier."""
        if self._client.connected:
            self.hass.async_create_task(self._client.send(endpoint))

    def _apply_dirac_measuring(self, value: Any) -> None:
        if isinstance(value, bool):
            self.data["dirac_measuring"] = value

    def _apply_ip(self, data: Any) -> None:
        if isinstance(data, dict):
            self.data["ip_address"] = _clean(data.get("wired"))

    def _apply_bluetooth(self, data: Any) -> None:
        if isinstance(data, dict):
            self.data["bluetooth"] = data

    def _apply_settings(self, data: Any) -> None:
        """get_settings is the only source for most of what the unit knows.

        The whole payload is kept, not just the fields the panel prints. It is
        one reply on a poll that already happens, so every setting in it is
        free to keep - the Dolby and DTS blocks, bass management, the
        crossovers, the matrix, the PEQ - and entities for the rest of it can
        read straight out of here without asking the unit for anything more.
        """
        if not isinstance(data, dict):
            return

        self.data["settings"] = data

        index = data.get("dirac_filter_index")
        if index != self._dirac_index:
            self._dirac_index = index
            self._ask(GET_DIRAC_FILTER)

        sources = data.get("sources")
        if isinstance(sources, dict):
            self.data["sources"] = {
                str(sid): {
                    "name": entry.get("name"),
                    # explicit bool: a missing flag means visible, not hidden
                    "hidden": bool(entry.get("hidden")),
                    "volume_offset": entry.get("volume_offset"),
                }
                for sid, entry in sources.items()
                if isinstance(entry, dict)
            }

        dolby = data.get("dolby")
        if isinstance(dolby, dict) and isinstance(dolby.get("profile"), str):
            self.data["dolby_profile"] = dolby["profile"]

        # The active upmixer. This is what the front panel's Dolby AUDIO /
        # dts:x badge is lit from, and it is the only field that tells native
        # apart from the others - the decoder names do not.
        if isinstance(data.get("upmixer"), str):
            self.data["upmixer"] = data["upmixer"]

        # Merged, not replaced: the front panel's two versions live here too,
        # and they arrive from their own endpoints once an hour, not from this.
        self.data["versions"] |= {
            "tide": _clean(data.get("version")),
            "hdmi_card": _clean(data.get("hdmi_card_firmware_version")),
            "hdmi_xmos": _clean(data.get("hdmi_xmos_firmware_version")),
            "hdmi_kernel": _clean(data.get("hdmi_kernel_version")),
        }

    # --- outbound ----------------------------------------------------------

    async def async_set_volume_db(self, db: float) -> bool:
        """Clamp to the unit's range and send; True if it left Home Assistant."""
        db = max(MIN_VOLUME_DB, min(MAX_VOLUME_DB, float(db)))
        return await self._client.send(SET_VOLUME_DB, value=round(db, 2))

    async def async_nudge_volume(self, delta_db: float) -> None:
        """Step the volume, counting steps that are still in flight.

        From minidsp_tide16 0.20+. Three quick presses of Volume + before the
        first volume_change_db push comes back must give +6 dB, not +2 dB
        three times from the same stale reading - so a step is based on the
        last target sent while it is unconfirmed (for at most
        PENDING_VOLUME_TIMEOUT seconds), else on the confirmed volume. The
        target is rolled back if the command never left Home Assistant.

        The Volume Up/Down buttons, the media player's volume_up/volume_down
        (HomeKit remote, Siri) and the volume_step action all come here, so
        presses from any of them accumulate together.
        """
        now = time.monotonic()
        pending = self._pending_volume_db
        if pending is not None and (
            self._pending_volume_ts is None
            or now - self._pending_volume_ts > PENDING_VOLUME_TIMEOUT
        ):
            pending = None

        confirmed = self.data.get("volume_db")
        base = pending if pending is not None else confirmed
        if base is None:
            # Nothing known yet: a step from an invented level could be loud.
            _LOGGER.debug("volume step ignored: volume not known yet")
            return
        target = max(MIN_VOLUME_DB, min(MAX_VOLUME_DB, float(base) + delta_db))

        previous = (self._pending_volume_db, self._pending_volume_ts)
        self._pending_volume_db = target
        self._pending_volume_ts = now
        if not await self.async_set_volume_db(target):
            self._pending_volume_db, self._pending_volume_ts = previous

    async def async_refresh_settings(self) -> None:
        """Re-read get_settings after we changed something only it reports."""
        await self._client.send(GET_SETTINGS)

    async def async_send(self, endpoint: str, **args: Any) -> bool:
        return await self._client.send(endpoint, **args)

    async def async_request(self, endpoint: str, **args: Any) -> Any:
        try:
            return await self._client.request(endpoint, **args)
        except Tide16Error as err:
            _LOGGER.debug("request %s failed: %s", endpoint, err)
            return None


def _moved(old: Any, new: float | None) -> bool:
    """True when a published level should be refreshed."""
    if old is None or new is None:
        return old != new
    return abs(float(old) - new) >= 1.0


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _blank() -> dict[str, Any]:
    return {
        "status": None,
        "volume_db": None,
        "muted": None,
        "source_id": None,
        "source_names": {},
        "sources": {},
        "stream": {},
        "preset_index": None,
        "preset_name": None,
        "presets": [],
        "speaker_config": None,
        "channel_names": [],
        # deliberately NOT cleared by _blank()'s callers on disconnect - see
        # _apply_output_speakers
        "channel_names_held": [],
        "custom_channels_held": [],
        "settings": {},
        "dirac": {},
        "dirac_measuring": None,
        "dirac_filter": {},
        "bluetooth": {},
        "dolby_profile": None,
        "upmixer": None,
        "versions": {},
        "update_check": {},
        "clock_offset": None,
        "signal": False,
        "signal_peak_db": None,
        "signal_level_db": None,
        "signal_threshold_db": None,
        "ip_address": None,
    }


# An answer that says any of these is not announcing an update, whatever else
# it says - "Update server not available" contains "available" too.
_NOT_AN_UPDATE = re.compile(
    r"\b(no|not|none|unavailable|error|fail\w*|unable|cannot|can't|couldn't|"
    r"timed?\s*out|unreachable)\b"
)
_AN_UPDATE = re.compile(
    r"\b(update|firmware|version)s?\b.*\bavailable\b|\bnew (firmware|version|update)\b"
)


def _update_available(text: str) -> bool | None:
    """What the server's answer says, or None when it is not clear.

    Read from the words, not the code: the only answer seen so far is "No
    updates available", code 1, and whether an available update shares that
    code is not known.

    True needs an answer that plainly announces one AND has no negation or
    failure in it; the panel alarms on True, and a false alarm is the thing to
    avoid.  Anything else that is not plainly "nothing new" - the server
    unreachable, a wording not seen before - is None, which alarms nothing.

    There is no update channel to reconcile this against: the unit has no
    stable/beta setting, and check_for_update sends none.  What the server
    offers this unit IS its channel.
    """
    lowered = text.lower()
    if lowered.startswith("no update") or "up to date" in lowered:
        return False
    if _NOT_AN_UPDATE.search(lowered):
        return None
    if _AN_UPDATE.search(lowered):
        return True
    return None


_REPLY_APPLIERS = {
    "get_coordinator_status": Tide16Coordinator._apply_status,
    "get_volume_db": Tide16Coordinator._apply_volume,
    "get_mute": Tide16Coordinator._apply_mute,
    "get_source": Tide16Coordinator._apply_source,
    "get_source_names": Tide16Coordinator._apply_source_names,
    "get_stream_properties": Tide16Coordinator._apply_stream,
    "get_current_preset_index": Tide16Coordinator._apply_preset_index,
    "get_all_presets": Tide16Coordinator._apply_presets,
    "get_speaker_config_number": Tide16Coordinator._apply_speaker_config,
    "get_output_speakers": Tide16Coordinator._apply_output_speakers,
    "get_custom_out_port_names": Tide16Coordinator._apply_custom_port_names,
    "get_dirac_state": Tide16Coordinator._apply_dirac,
    "get_dirac_measuring_mode": Tide16Coordinator._apply_dirac_measuring,
    "get_dirac_filter": Tide16Coordinator._apply_dirac_filter,
    "get_bluetooth_status": Tide16Coordinator._apply_bluetooth,
    GET_IP: Tide16Coordinator._apply_ip,
    "get_settings": Tide16Coordinator._apply_settings,
    GET_FRONT_PANEL_PACKAGED_FW: Tide16Coordinator._apply_front_panel_packaged_fw,
    CHECK_FOR_UPDATE: Tide16Coordinator._apply_update_done,
}

_PUSH_APPLIERS = {
    N_STATUS: Tide16Coordinator._apply_status,
    N_VOLUME_DB: Tide16Coordinator._apply_volume,
    N_MUTE: Tide16Coordinator._apply_mute,
    N_SOURCE: Tide16Coordinator._apply_source,
    N_SOURCE_NAMES: Tide16Coordinator._apply_source_names,
    N_STREAM: Tide16Coordinator._apply_stream,
    N_PRESET: Tide16Coordinator._apply_preset_push,
    N_DIRAC_STATE: Tide16Coordinator._apply_dirac,
    N_DIRAC_MEASURING: Tide16Coordinator._apply_dirac_measuring,
    N_BLUETOOTH: Tide16Coordinator._apply_bluetooth,
    N_SPEAKER_CONFIG: Tide16Coordinator._apply_speaker_config,
    N_UPDATE: Tide16Coordinator._apply_update,
    N_FRONT_PANEL_FW: Tide16Coordinator._apply_front_panel_fw,
}
