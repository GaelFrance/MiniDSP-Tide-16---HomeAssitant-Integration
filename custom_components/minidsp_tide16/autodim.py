"""Track the display's brightness to the sun.

The Tide16's front panel is bright enough to light a room, which is welcome in
daylight and not at all welcome once the lights are down and a film is on.
This walks the brightness between two levels across a window either side of
sunrise and sunset, using the sun at the Home Assistant location's own
coordinates - so it follows the season without anybody editing a schedule
twice a year.

It lives in the integration rather than in the card on purpose: the card runs
once per browser, so the same ramp would run several times over, and would not
run at all with no dashboard open. Here it runs once, headless, for as long as
Home Assistant does.

`set_brightness` is not in the endpoint list the unit's own control page
publishes - that page has no brightness control at all - and was found by
probing. `{"endpoint": "set_brightness", "value": 0-100}`; the unit answers
`{"status": "OK"}`, and rejects any other argument name with "Key value should
be present". A firmware without it will simply never dim, and the target
sensor is what says so.

Switching it off restores the day brightness; nothing else about the display
is touched, and in particular its sleep timeout is left alone - this is about
how bright the panel is, not how long it stays lit.

The ramp is linear across the window, and the rate therefore falls out of the
range and the window rather than being set directly: 80% to 20% across the
default 45 minutes is 1% every 45 seconds. Widen the window for a slower walk.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .api.const import SET_BRIGHTNESS
from .coordinator import Tide16Coordinator

_LOGGER = logging.getLogger(__name__)

# The ramp is recomputed rather than stepped, so this only has to be fine
# enough that the walk looks continuous - at the default rate a step is 45
# seconds, and the target is absolute, so a missed tick corrects itself.
TICK = timedelta(seconds=20)

DEFAULT_MAX = 80.0
DEFAULT_MIN = 20.0
DEFAULT_LEAD = 30.0  # minutes before the sun event the ramp starts
DEFAULT_TRAIL = 15.0  # minutes after it ends


class Tide16AutoDim:
    """The ramp, and the settings that shape it.

    Every setting is held here rather than on the device: they are about when
    Home Assistant should write a brightness, not about the unit, and the unit
    has nowhere to keep them. The entities that expose them restore their own
    values across a restart.
    """

    def __init__(self, hass: HomeAssistant, coordinator: Tide16Coordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator

        self.enabled = False
        self.max_pct = DEFAULT_MAX
        self.min_pct = DEFAULT_MIN
        self.lead_min = DEFAULT_LEAD
        self.trail_min = DEFAULT_TRAIL

        # What the ramp last decided, and what it last sent. They differ while
        # the unit is away: the target is still meaningful, the write is not.
        self.target: int | None = None
        self._sent: int | None = None
        self._cancel: Callable[[], None] | None = None
        self._listeners: list[Callable[[], None]] = []

    # --- lifecycle ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        self._cancel = async_track_time_interval(self.hass, self._async_tick, TICK)

    @callback
    def async_stop(self) -> None:
        if self._cancel:
            self._cancel()
            self._cancel = None

    @callback
    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Entities register here to redraw when the target moves."""
        self._listeners.append(cb)

        def remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return remove

    @callback
    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    # --- settings ----------------------------------------------------------

    async def async_set(self, **values: Any) -> None:
        """Change a setting and act on it at once.

        Waiting for the next tick would mean a slider that appears to do
        nothing for twenty seconds.
        """
        for key, value in values.items():
            setattr(self, key, value)
        self._notify()
        await self._async_apply(dt_util.now())

    # --- the ramp ----------------------------------------------------------

    def _event(self, event: str, day_offset: int, now: datetime) -> datetime | None:
        when = get_astral_event_date(
            self.hass, event, dt_util.as_local(now).date() + timedelta(days=day_offset)
        )
        return dt_util.as_local(when) if when else None

    def compute(self, now: datetime) -> int | None:
        """The brightness this moment calls for, or None if the sun is unknown.

        Somewhere inside the Arctic or Antarctic circles there are days with
        no sunrise or sunset at all, and the honest answer there is to leave
        the display alone rather than to invent an event.
        """
        lead = timedelta(minutes=max(0.0, self.lead_min))
        trail = timedelta(minutes=max(0.0, self.trail_min))
        top, bottom = float(self.max_pct), float(self.min_pct)

        # Yesterday, today and tomorrow, because a window reaches across
        # midnight as soon as it is wider than the gap between the event and
        # the end of the day - a 4am sunrise with a long lead starts the ramp
        # the previous evening, and looking only at today's events meant it
        # silently never started at all.
        events: list[tuple[datetime, str]] = []
        for offset in (-1, 0, 1):
            rise = self._event(SUN_EVENT_SUNRISE, offset, now)
            fall = self._event(SUN_EVENT_SUNSET, offset, now)
            if rise:
                events.append((rise, SUN_EVENT_SUNRISE))
            if fall:
                events.append((fall, SUN_EVENT_SUNSET))
        if not events:
            return None
        events.sort()

        def ramp(start: datetime, end: datetime, frm: float, to: float) -> float:
            span = (end - start).total_seconds()
            if span <= 0:
                return to
            k = (now - start).total_seconds() / span
            return frm + (to - frm) * min(1.0, max(0.0, k))

        for when, kind in events:
            start, end = when - lead, when + trail
            if start <= now <= end:
                value = (ramp(start, end, bottom, top) if kind == SUN_EVENT_SUNRISE
                         else ramp(start, end, top, bottom))
                return round(min(100.0, max(0.0, value)))

        # Between windows: whichever event happened last says which it is.
        past = [kind for when, kind in events if when <= now]
        if past:
            value = top if past[-1] == SUN_EVENT_SUNRISE else bottom
        else:
            # Before every event we know about - the opposite of whatever
            # comes first.
            value = bottom if events[0][1] == SUN_EVENT_SUNRISE else top
        return round(min(100.0, max(0.0, value)))

    async def _async_tick(self, now: datetime | None = None) -> None:
        await self._async_apply(dt_util.now())

    async def _async_apply(self, now: datetime) -> None:
        if not self.enabled:
            # The target is only meaningful while the ramp owns the display;
            # left set, it would claim credit for a brightness somebody else
            # chose.
            #
            # Switching off also hands the display back at the day level. The
            # alternative is leaving it wherever the ramp happened to have got
            # to, so turning auto dim off at midnight would strand the panel
            # at its dimmest and look like the switch had done nothing - or
            # worse, like it had broken the display.
            if self.target is not None:
                self.target = None
                self._sent = None
                self._notify()
                if self.coordinator.connected:
                    await self.coordinator.async_send(
                        SET_BRIGHTNESS, value=round(self.max_pct)
                    )
                    _LOGGER.debug(
                        "auto dim off: display brightness -> %s%%", round(self.max_pct)
                    )
            return

        target = self.compute(now)
        if target != self.target:
            self.target = target
            self._notify()
        if target is None or target == self._sent:
            return
        if not self.coordinator.connected:
            # Standby. Nothing to write to, and nothing to remember either -
            # the unit comes back at whatever brightness it kept, so the next
            # tick should write again rather than assume.
            self._sent = None
            return
        if await self.coordinator.async_send(SET_BRIGHTNESS, value=target):
            self._sent = target
            _LOGGER.debug("auto dim: display brightness -> %s%%", target)
