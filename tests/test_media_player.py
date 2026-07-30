"""Tests for the v29 HomeKit/Siri-compatibility changes to media_player.tide16.

Scope, matching the v29 changelog entry:
  - device_class is MediaPlayerDeviceClass.RECEIVER
  - supported_features gained VOLUME_STEP, kept VOLUME_SET/VOLUME_MUTE/
    SELECT_SOURCE/TURN_OFF, and still excludes TURN_ON/PLAY/PAUSE/STOP
  - async_volume_up/async_volume_down delegate to the coordinator's
    existing async_nudge_volume() - the same method the standalone
    Volume Up/Down buttons already use - instead of reimplementing
    anything in media_player.py
  - the accumulated-pending-volume behavior in the coordinator (repeated
    fast volume-up/down calls must not collapse onto the same stale
    confirmed value) still works when driven through the media_player
    entity, not just through the buttons
  - nothing about volume_level's linear dB-range mapping, unique_id, or
    source selection regressed

homeassistant.components.media_player is imported for real (see
conftest.py for why a small stub is needed to get there); FakeCoordinator
below stands in for Tide16Coordinator except in
TestVolumeStepAccumulation, which exercises the real
custom_components.minidsp_tide16.coordinator.Tide16Coordinator to prove
the accumulation behavior itself - not just that media_player.py calls
some method - is unchanged.
"""
from __future__ import annotations

import pytest
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)

from custom_components.minidsp_tide16 import media_player as mp_module
from custom_components.minidsp_tide16.const import (
    MAX_VOLUME_DB,
    MIN_VOLUME_DB,
    VOLUME_STEP_DB,
)
from custom_components.minidsp_tide16.coordinator import Tide16Coordinator

Tide16MediaPlayer = mp_module.Tide16MediaPlayer


class FakeCoordinator:
    """Minimal stand-in for Tide16Coordinator's public surface.

    Records every call made to it so tests can assert media_player.py
    delegates to the coordinator instead of reimplementing anything, and
    exposes the same `.data` dict shape entities read from.
    """

    def __init__(self, **data_overrides):
        self.data = {
            "connected": True,
            "volume_db": -30.0,
            "muted": False,
            "source": "hdmi1",
            "source_names": {},
            "status": "ready",
        }
        self.data.update(data_overrides)
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))

    async def async_set_volume_db(self, db):
        self._record("async_set_volume_db", db)
        return True

    async def async_nudge_volume(self, delta_db):
        self._record("async_nudge_volume", delta_db)

    async def async_set_mute(self, muted):
        self._record("async_set_mute", muted)

    async def async_select_source(self, source_id):
        self._record("async_select_source", source_id)

    async def async_shutdown(self):
        self._record("async_shutdown")


@pytest.fixture
def entity():
    return Tide16MediaPlayer(FakeCoordinator())


# --- Device class / feature declaration -------------------------------


def test_device_class_is_receiver(entity):
    assert entity.device_class is MediaPlayerDeviceClass.RECEIVER


def test_supported_features_includes_volume_step(entity):
    assert entity.supported_features & MediaPlayerEntityFeature.VOLUME_STEP


@pytest.mark.parametrize(
    "feature",
    [
        MediaPlayerEntityFeature.VOLUME_SET,
        MediaPlayerEntityFeature.VOLUME_MUTE,
        MediaPlayerEntityFeature.SELECT_SOURCE,
        MediaPlayerEntityFeature.TURN_OFF,
    ],
)
def test_supported_features_retains_existing_features(entity, feature):
    assert entity.supported_features & feature


@pytest.mark.parametrize(
    "feature",
    [
        MediaPlayerEntityFeature.TURN_ON,
        MediaPlayerEntityFeature.PLAY,
        MediaPlayerEntityFeature.PAUSE,
        MediaPlayerEntityFeature.STOP,
    ],
)
def test_supported_features_excludes_unsupported_controls(entity, feature):
    # TURN_ON: the Tide16 has no network wake path on current firmware.
    # PLAY/PAUSE/STOP: the Tide16 is a receiver, not the playback source.
    assert not (entity.supported_features & feature)


def test_unique_id_unchanged(entity):
    # The receiver device_class must not have touched the entity's
    # long-term identity in the entity registry.
    assert entity.unique_id == "minidsp_tide16_media_player_v2"


def test_entity_id_unchanged(entity):
    assert entity.entity_id == "media_player.tide16"


# --- Volume up/down delegate to the coordinator, not reimplemented -----


async def test_async_volume_up_delegates_to_coordinator_nudge(entity):
    await entity.async_volume_up()
    assert entity._coordinator.calls == [("async_nudge_volume", (VOLUME_STEP_DB,), {})]


async def test_async_volume_down_delegates_to_coordinator_nudge(entity):
    await entity.async_volume_down()
    assert entity._coordinator.calls == [("async_nudge_volume", (-VOLUME_STEP_DB,), {})]


async def test_volume_up_down_use_same_step_as_the_standalone_buttons():
    # button.tide16_volume_up/down (button.py) call
    # coordinator.async_nudge_volume(+/-VOLUME_STEP_DB) directly - the
    # media_player entity must produce the exact same physical step.
    import custom_components.minidsp_tide16.button as button_module

    assert button_module  # imported to confirm it still exists/loads
    coordinator = FakeCoordinator()
    entity = Tide16MediaPlayer(coordinator)
    await entity.async_volume_up()
    await entity.async_volume_down()
    assert coordinator.calls == [
        ("async_nudge_volume", (VOLUME_STEP_DB,), {}),
        ("async_nudge_volume", (-VOLUME_STEP_DB,), {}),
    ]


# --- volume_level mapping unchanged (v22/v23 linear-over-dB-range) -----


@pytest.mark.parametrize(
    "db,expected",
    [
        (MIN_VOLUME_DB, 0.0),
        (MAX_VOLUME_DB, 1.0),
        (-63.75, pytest.approx(0.5, abs=1e-6)),
    ],
)
def test_volume_level_linear_mapping_unchanged(db, expected):
    entity = Tide16MediaPlayer(FakeCoordinator(volume_db=db))
    assert entity.volume_level == expected


def test_volume_level_none_when_unknown():
    entity = Tide16MediaPlayer(FakeCoordinator(volume_db=None))
    assert entity.volume_level is None


async def test_async_set_volume_level_clamps_and_uses_linear_mapping():
    coordinator = FakeCoordinator()
    entity = Tide16MediaPlayer(coordinator)

    await entity.async_set_volume_level(1.5)  # out-of-range high
    assert coordinator.calls[-1] == ("async_set_volume_db", (MAX_VOLUME_DB,), {})

    await entity.async_set_volume_level(-0.5)  # out-of-range low
    assert coordinator.calls[-1] == ("async_set_volume_db", (MIN_VOLUME_DB,), {})

    await entity.async_set_volume_level(0.5)
    got_db = coordinator.calls[-1][1][0]
    assert got_db == pytest.approx(MIN_VOLUME_DB + 0.5 * (MAX_VOLUME_DB - MIN_VOLUME_DB))


# --- Mute --------------------------------------------------------------


async def test_mute_and_unmute_delegate_to_coordinator():
    coordinator = FakeCoordinator()
    entity = Tide16MediaPlayer(coordinator)
    await entity.async_mute_volume(True)
    await entity.async_mute_volume(False)
    assert coordinator.calls == [
        ("async_set_mute", (True,), {}),
        ("async_set_mute", (False,), {}),
    ]


def test_is_volume_muted_reflects_coordinator_state():
    assert Tide16MediaPlayer(FakeCoordinator(muted=True)).is_volume_muted is True
    assert Tide16MediaPlayer(FakeCoordinator(muted=False)).is_volume_muted is False


# --- Source selection still works (live names, fallback, disambiguation) ---


def test_source_list_uses_fallback_labels_when_no_live_names():
    entity = Tide16MediaPlayer(FakeCoordinator(source_names={}))
    assert "Spotify" in entity.source_list
    assert "Apple TV" in entity.source_list
    assert len(entity.source_list) == 12


def test_source_reflects_live_name_when_available():
    entity = Tide16MediaPlayer(
        FakeCoordinator(source="hdmi1", source_names={"hdmi1": "Living Room TV"})
    )
    assert entity.source == "Living Room TV"


def test_source_disambiguates_duplicate_live_names():
    entity = Tide16MediaPlayer(
        FakeCoordinator(
            source_names={"hdmi1": "Apple TV", "hdmi2": "Apple TV"},
        )
    )
    labels = entity._source_labels()
    assert labels["hdmi1"] == "Apple TV (hdmi1)"
    assert labels["hdmi2"] == "Apple TV (hdmi2)"


async def test_async_select_source_resolves_label_to_source_id():
    coordinator = FakeCoordinator()
    entity = Tide16MediaPlayer(coordinator)
    await entity.async_select_source("Spotify")
    assert coordinator.calls == [("async_select_source", ("spdif1",), {})]


# --- Power state design (intentionally unchanged) -----------------------


def test_state_on_when_connected():
    assert Tide16MediaPlayer(FakeCoordinator(connected=True)).state == MediaPlayerState.ON


def test_state_off_when_disconnected():
    assert Tide16MediaPlayer(FakeCoordinator(connected=False)).state == MediaPlayerState.OFF


def test_entity_always_available():
    # Deliberately never "unavailable" - see the class docstring/property.
    assert Tide16MediaPlayer(FakeCoordinator(connected=False)).available is True


async def test_async_turn_off_maps_to_shutdown():
    coordinator = FakeCoordinator()
    entity = Tide16MediaPlayer(coordinator)
    await entity.async_turn_off()
    assert coordinator.calls == [("async_shutdown", (), {})]


def test_no_turn_on_override_exists():
    # No network wake path on current Tide16 firmware - see README.md.
    # MediaPlayerEntity's base class always defines *a* async_turn_on
    # (it's part of the base API surface), so the meaningful check is
    # that Tide16MediaPlayer itself never overrides it with a real
    # implementation - combined with TURN_ON being absent from
    # supported_features (tested above), Home Assistant never exposes a
    # working "turn on" control for this entity.
    assert "async_turn_on" not in Tide16MediaPlayer.__dict__


# --- Accumulated-volume behavior, exercised through the REAL coordinator ---


class _FakeWebSocket:
    """Stands in for aiohttp.ClientWebSocketResponse: records every
    payload sent, never actually touches a network."""

    def __init__(self):
        self.closed = False
        self.sent: list[dict] = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.fixture
def real_coordinator():
    coordinator = Tide16Coordinator(hass=None, host="minidsp-tide.local", port=5555)
    coordinator._ws = _FakeWebSocket()
    coordinator.data["volume_db"] = -30.0
    return coordinator


async def test_repeated_volume_up_accumulates_without_waiting_for_confirmation(
    real_coordinator,
):
    """Three fast Siri/HomeKit "volume up" calls, none of them followed by
    a simulated device confirmation in between (the exact scenario the
    v19 coordinator fix - see coordinator.py's async_nudge_volume
    docstring - was written for), must each build on the last REQUESTED
    target, not the same stale confirmed value three times over."""
    entity = Tide16MediaPlayer(real_coordinator)

    await entity.async_volume_up()
    await entity.async_volume_up()
    await entity.async_volume_up()

    sent_values = [msg["value"] for msg in real_coordinator._ws.sent]
    assert sent_values == [
        pytest.approx(-30.0 + VOLUME_STEP_DB),
        pytest.approx(-30.0 + 2 * VOLUME_STEP_DB),
        pytest.approx(-30.0 + 3 * VOLUME_STEP_DB),
    ]
    # Every step must be distinct - none of the three presses may have
    # been silently dropped/collapsed.
    assert len(set(sent_values)) == 3


async def test_repeated_volume_down_accumulates_without_waiting_for_confirmation(
    real_coordinator,
):
    entity = Tide16MediaPlayer(real_coordinator)

    await entity.async_volume_down()
    await entity.async_volume_down()
    await entity.async_volume_down()

    sent_values = [msg["value"] for msg in real_coordinator._ws.sent]
    assert sent_values == [
        pytest.approx(-30.0 - VOLUME_STEP_DB),
        pytest.approx(-30.0 - 2 * VOLUME_STEP_DB),
        pytest.approx(-30.0 - 3 * VOLUME_STEP_DB),
    ]
    assert len(set(sent_values)) == 3


async def test_volume_up_clamps_at_maximum(real_coordinator):
    real_coordinator.data["volume_db"] = MAX_VOLUME_DB - 0.5
    entity = Tide16MediaPlayer(real_coordinator)

    await entity.async_volume_up()
    await entity.async_volume_up()  # would overshoot 0.0 dB without clamping

    sent_values = [msg["value"] for msg in real_coordinator._ws.sent]
    assert sent_values[-1] == MAX_VOLUME_DB
    assert all(v <= MAX_VOLUME_DB for v in sent_values)


async def test_volume_down_clamps_at_minimum(real_coordinator):
    real_coordinator.data["volume_db"] = MIN_VOLUME_DB + 0.5
    entity = Tide16MediaPlayer(real_coordinator)

    await entity.async_volume_down()
    await entity.async_volume_down()  # would undershoot -127.5 dB without clamping

    sent_values = [msg["value"] for msg in real_coordinator._ws.sent]
    assert sent_values[-1] == MIN_VOLUME_DB
    assert all(v >= MIN_VOLUME_DB for v in sent_values)


async def test_button_and_media_player_share_the_same_accumulated_target(
    real_coordinator,
):
    """button.tide16_volume_up and media_player.tide16's volume-up must
    accumulate on the SAME pending target (they share one coordinator
    instance in real Home Assistant) - alternating between the two must
    still add up correctly, proving media_player.py didn't introduce a
    second, independent tracking mechanism."""
    import custom_components.minidsp_tide16.button as button_module

    media_player_entity = Tide16MediaPlayer(real_coordinator)
    button_entity = button_module.Tide16VolumeUpButton(real_coordinator)

    await media_player_entity.async_volume_up()
    await button_entity.async_press()
    await media_player_entity.async_volume_up()

    sent_values = [msg["value"] for msg in real_coordinator._ws.sent]
    assert sent_values == [
        pytest.approx(-30.0 + VOLUME_STEP_DB),
        pytest.approx(-30.0 + 2 * VOLUME_STEP_DB),
        pytest.approx(-30.0 + 3 * VOLUME_STEP_DB),
    ]
