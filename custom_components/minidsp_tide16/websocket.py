"""The metering channel.

Sixteen channel levels, four times a second, is a live meter's worth of data
and a database's worth of trouble.  As entity state it needed a `recorder:`
exclusion in the user's own configuration.yaml, a service to raise the poll
rate, and a keepalive from the card to hold it there.

Here the card subscribes to a websocket command instead.  Frames go straight to
the subscribed connections, the fast cadence runs only while at least one
subscriber exists, and closing the tab is the unsubscribe - there is no state
anywhere that can get stuck fast, and nothing to keep out of the recorder.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

# Kept as "tide16/..." whatever the domain: it is the card's wire protocol.
CMD_SUBSCRIBE = "tide16/levels/subscribe"

# Matched to the coordinator's fast cadence, which is itself matched to how
# often the unit recomputes its RMS block (~90ms, measured). Left at 4 Hz this
# was the real limit on the meter no matter how fast anything upstream ran:
# frames went out on this timer, so two out of every three readings were
# fetched and then dropped, and a bar could be a quarter-second behind the
# hardware before it was drawn.
#
# Anything the coordinator reads while nobody is watching is still dropped
# rather than pushed - the subscription is what turns this on at all.
PUSH_INTERVAL = 0.1


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    if hass.data.get(f"{DOMAIN}_ws"):
        return
    hass.data[f"{DOMAIN}_ws"] = True
    websocket_api.async_register_command(hass, websocket_subscribe_levels)


@websocket_api.websocket_command(
    {
        vol.Required("type"): CMD_SUBSCRIBE,
        vol.Optional("entry_id"): str,
    }
)
@callback
def websocket_subscribe_levels(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Stream one unit's channel levels for as long as the client listens."""
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        connection.send_error(msg["id"], "not_found", "no Tide16 is configured")
        return

    entry_id = msg.get("entry_id")
    coordinator = coordinators.get(entry_id) if entry_id else next(
        iter(coordinators.values())
    )
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", f"unknown entry {entry_id}")
        return

    coordinator.add_meter_subscriber()

    @callback
    def _push(_now: Any = None) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "levels": coordinator.levels,
                    "names": coordinator.data.get("channel_names_held") or [],
                    "connected": coordinator.connected,
                },
            )
        )

    cancel_timer = async_track_time_interval(
        hass, _push, timedelta(seconds=PUSH_INTERVAL)
    )

    @callback
    def _unsubscribe() -> None:
        cancel_timer()
        coordinator.remove_meter_subscriber()

    connection.subscriptions[msg["id"]] = _unsubscribe
    connection.send_result(msg["id"])
    # first frame immediately, so a card that has just appeared draws something
    # rather than waiting out an interval with empty bars
    _push()
