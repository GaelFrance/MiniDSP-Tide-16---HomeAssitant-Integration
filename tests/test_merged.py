"""The merged integration, end to end in a simulated Home Assistant."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.minidsp_tide16.const import DOMAIN

# What the 0.x registry holds on the live system (platform minidsp_tide16).
LEGACY = {
    "media_player.tide16": "minidsp_tide16_media_player_v2",
    "sensor.tide16_status": "minidsp_tide16_status",
    "sensor.tide16_source": "minidsp_tide16_source",
    "sensor.tide16_stream": "minidsp_tide16_stream",
    "sensor.tide16_preset": "minidsp_tide16_preset",
    "sensor.tide16_bluetooth": "minidsp_tide16_bluetooth",
    "sensor.tide16_ip_address": "minidsp_tide16_ip_address",
    "sensor.tide16_speaker_config": "minidsp_tide16_speaker_config",
    "switch.tide16_mute": "minidsp_tide16_mute",
    "switch.tide16_dirac_live": "minidsp_tide16_dirac_live",
    "number.tide16_volume": "minidsp_tide16_volume",
    "binary_sensor.tide16_audio_signal": "minidsp_tide16_audio_signal",
    "binary_sensor.tide16_dirac_measuring": "minidsp_tide16_dirac_measuring",
    "button.tide16_shutdown": "minidsp_tide16_shutdown",
    "button.tide16_reboot": "minidsp_tide16_reboot",
    "button.tide16_bluetooth_pair": "minidsp_tide16_bt_pair",
    "button.tide16_volume_up": "minidsp_tide16_volume_up",
    "button.tide16_volume_down": "minidsp_tide16_volume_down",
    "button.tide16_source_spotify": "minidsp_tide16_source_spotify",
    "button.tide16_source_apple_tv": "minidsp_tide16_source_apple_tv",
    "button.tide16_source_spdif_2": "minidsp_tide16_source_spdif_2",
    "button.tide16_source_toslink_1": "minidsp_tide16_source_toslink_1",
    "button.tide16_source_toslink_2": "minidsp_tide16_source_toslink_2",
    "button.tide16_source_hdmi_2": "minidsp_tide16_source_hdmi_2",
    "button.tide16_source_hdmi_3": "minidsp_tide16_source_hdmi_3",
    "button.tide16_source_arc_earc": "minidsp_tide16_source_arc_earc",
    "button.tide16_source_xlr": "minidsp_tide16_source_xlr",
    "button.tide16_source_rca": "minidsp_tide16_source_rca",
    "button.tide16_source_usb": "minidsp_tide16_source_usb",
    "button.tide16_source_bluetooth": "minidsp_tide16_source_bluetooth",
}

SOURCES_TABLE = {
    "hdmi1": {"name": "Apple Tv", "hidden": False, "volume_offset": 0},
    "spdif1": {"name": "Spotify", "hidden": False, "volume_offset": 0},
    "alsa": {"name": "ALSA", "hidden": True, "volume_offset": 0},
    "usb": {"name": "USB", "hidden": False, "volume_offset": 0},
}
SOURCE_NAMES = {"hdmi1": "Apple Tv", "spdif1": "Spotify", "alsa": "ALSA", "usb": "USB"}


async def _setup(hass: HomeAssistant, entry, legacy: bool = True):
    if legacy:
        reg = er.async_get(hass)
        for entity_id, uid in LEGACY.items():
            domain, object_id = entity_id.split(".")
            reg.async_get_or_create(
                domain, DOMAIN, uid, suggested_object_id=object_id,
                config_entry=entry,
            )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _connect(hass, client, *, ready=True, volume=-53.0):
    client.set_connected(True)
    await hass.async_block_till_done()
    client.reply("get_source_names", SOURCE_NAMES)
    client.reply("get_settings", {"sources": SOURCES_TABLE, "upmixer": "datmos"})
    client.reply("get_source", "hdmi1")
    client.reply("get_volume_db", volume)
    if ready:
        client.push("coordinator_status", "ready")
    await hass.async_block_till_done()


async def test_legacy_entity_ids_are_kept(hass, entry, fake_client):
    await _setup(hass, entry)
    reg = er.async_get(hass)
    for entity_id, uid in LEGACY.items():
        domain = entity_id.split(".")[0]
        assert reg.async_get_entity_id(domain, DOMAIN, uid) == entity_id, entity_id
        assert hass.states.get(entity_id) is not None, entity_id
    # nothing was suffixed
    assert not [
        e for e in hass.states.async_entity_ids()
        if e.endswith("_2") and e not in LEGACY
    ]
    # and the ControlCard entities are there under their usual ids
    for entity_id in (
        "select.tide16_upmixer",
        "select.tide16_dolby_profile",
        "binary_sensor.tide16_upmixed",
        "binary_sensor.tide16_atmos",
        "switch.tide16_auto_dim",
        "sensor.tide16_volume_integer",
        "binary_sensor.tide16_firmware_update",
        "button.tide16_scene_red",
        "button.tide16_check_for_update",
    ):
        assert hass.states.get(entity_id) is not None, entity_id


async def test_fresh_install_gets_the_same_ids(hass, entry, fake_client):
    await _setup(hass, entry, legacy=False)
    for entity_id in LEGACY:
        assert hass.states.get(entity_id) is not None, entity_id


async def test_status_semantics(hass, entry, fake_client):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    assert hass.states.get("sensor.tide16_status").state == "not connected"
    assert hass.states.get("media_player.tide16").state == "off"
    client.set_connected(True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tide16_status").state == "connecting"
    client.push("coordinator_status", "ready")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tide16_status").state == "ready"
    assert hass.states.get("media_player.tide16").state == "on"
    # update-check progress never replaces "ready"
    client.push("coordinator_status", "Reaching update server...")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tide16_status").state == "ready"
    client.set_connected(False)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tide16_status").state == "not connected"
    assert hass.states.get("button.tide16_shutdown").state == "unavailable"


async def test_no_update_check_by_default(hass, entry, fake_client):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    with patch("custom_components.minidsp_tide16.coordinator.asyncio.sleep"):
        await _connect(hass, client)
        await hass.async_block_till_done()
    assert "check_for_update" not in client.sent_endpoints()
    assert "get_ip" in client.sent_endpoints()
    with patch(
        "custom_components.minidsp_tide16.coordinator.Tide16Coordinator._read_clock"
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.tide16_check_for_update"},
            blocking=True,
        )
    assert "check_for_update" in client.sent_endpoints()


async def test_update_check_option(hass, fake_client):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "h", "port": 5555}, options={"update_check": True}
    )
    entry.add_to_hass(hass)
    await _setup(hass, entry, legacy=False)
    client = fake_client.instances[-1]
    with patch("custom_components.minidsp_tide16.coordinator.asyncio.sleep"), patch(
        "custom_components.minidsp_tide16.coordinator.Tide16Coordinator._read_clock"
    ):
        await _connect(hass, client)
        await hass.async_block_till_done()
    assert "check_for_update" in client.sent_endpoints()


async def test_volume_steps_accumulate_across_buttons_and_media_player(
    hass, entry, fake_client
):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    await _connect(hass, client, volume=-40.0)
    client.sent.clear()
    for _ in range(2):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.tide16_volume_up"}, blocking=True
        )
    await hass.services.async_call(
        "media_player", "volume_up", {"entity_id": "media_player.tide16"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "volume_step", {"delta": -1}, blocking=True
    )
    volumes = [a["value"] for e, a in client.sent if e == "set_volume_db"]
    assert volumes == [-38.0, -36.0, -34.0, -35.0]
    # the unit confirms the last target: the next step starts from it
    client.push("volume_change_db", -35.0)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.tide16_volume_down"}, blocking=True
    )
    assert client.sent[-1] == ("set_volume_db", {"value": -37.0})


async def test_volume_step_ignored_while_volume_unknown(hass, entry, fake_client):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    client.set_connected(True)
    await hass.async_block_till_done()
    client.sent.clear()
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.tide16_volume_up"}, blocking=True
    )
    assert "set_volume_db" not in client.sent_endpoints()


async def test_media_player_homekit_receiver(hass, entry, fake_client):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    await _connect(hass, client)
    state = hass.states.get("media_player.tide16")
    assert state.attributes["device_class"] == "receiver"
    features = state.attributes["supported_features"]
    assert features & MediaPlayerEntityFeature.VOLUME_STEP
    assert features & MediaPlayerEntityFeature.VOLUME_SET
    assert not features & MediaPlayerEntityFeature.TURN_ON
    assert state.attributes["source"] == "Apple Tv"
    # hidden inputs are left out
    assert state.attributes["source_list"] == ["Apple Tv", "Spotify", "USB"]
    assert state.attributes["volume_level"] == pytest.approx(0.5843, abs=1e-4)
    assert hass.states.get("sensor.tide16_source").state == "Apple Tv"


async def test_select_source_by_name_and_by_button(hass, entry, fake_client):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    await _connect(hass, client)
    client.sent.clear()
    await hass.services.async_call(
        "media_player", "select_source",
        {"entity_id": "media_player.tide16", "source": "Spotify"}, blocking=True,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.tide16_source_apple_tv"}, blocking=True
    )
    assert client.sent == [
        ("set_source", {"value": "spdif1"}),
        ("set_source", {"value": "hdmi1"}),
    ]
    # the button follows the unit's name for the input
    assert (
        hass.states.get("button.tide16_source_apple_tv").attributes["friendly_name"]
        == "Tide16 Source: Apple Tv"
    )


async def test_duplicate_input_names_stay_selectable(hass, entry, fake_client):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    await _connect(hass, client)
    client.reply("get_source_names", {**SOURCE_NAMES, "usb": "Apple Tv"})
    await hass.async_block_till_done()
    state = hass.states.get("media_player.tide16")
    assert state.attributes["source_list"] == [
        "Apple Tv (hdmi1)", "Spotify", "Apple Tv (usb)"
    ]
    client.sent.clear()
    await hass.services.async_call(
        "media_player", "select_source",
        {"entity_id": "media_player.tide16", "source": "Apple Tv (usb)"}, blocking=True,
    )
    assert client.sent == [("set_source", {"value": "usb"})]


async def test_signal_is_compensated_for_volume(hass, entry, fake_client):
    """Quiet music at low volume: -100.5 dB out at -65 dB is -35.5 dB of programme."""
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    await _connect(hass, client, volume=-65.0)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    clock = [1000.0]
    with patch(
        "custom_components.minidsp_tide16.coordinator.time.monotonic",
        side_effect=lambda: clock[0],
    ):
        client.reply("get_rms_block_db", {"out": [{"index": 1, "val": -100.5}]})
        await hass.async_block_till_done()
        state = hass.states.get("binary_sensor.tide16_audio_signal")
        assert state.state == "on"
        assert state.attributes["level_db"] == -35.5
        assert state.attributes["peak_db"] == -100.5
        assert state.attributes["threshold_db"] == -60.0

        # noise floor near minimum volume is never signal
        client.push("volume_change_db", -10.0)
        clock[0] += 1
        client.reply("get_rms_block_db", {"out": [{"index": 1, "val": -125.0}]})
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.tide16_audio_signal").state == "on"
        clock[0] += 13
        client.reply("get_rms_block_db", {"out": [{"index": 1, "val": -125.0}]})
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.tide16_audio_signal").state == "on"
        clock[0] += 1.5  # 15.5 s without signal
        client.reply("get_rms_block_db", {"out": [{"index": 1, "val": -125.0}]})
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.tide16_audio_signal").state == "off"
    assert coordinator.silence_hold == 15.0


async def test_card_volume_action_matches_domain():
    from pathlib import Path

    js = (
        Path(__file__).parent.parent
        / "custom_components" / DOMAIN / "frontend" / "tide16-panel.js"
    ).read_text()
    assert '"tide16.volume_step"' not in js
    assert f'"{DOMAIN}.volume_step"' in js


async def test_yaml_import_creates_entry_once(hass, fake_client):
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"host": "192.168.10.242"}}
    )
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {"host": "192.168.10.242", "port": 5555}


async def test_volume_clamps_at_zero_db(hass, entry, fake_client):
    await _setup(hass, entry)
    client = fake_client.instances[-1]
    await _connect(hass, client, volume=-1.0)
    client.sent.clear()
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.tide16_volume_up"}, blocking=True
    )
    assert client.sent == [("set_volume_db", {"value": 0.0})]


async def test_options_flow_saves_merged_options(hass, entry, fake_client):
    await _setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "signal_relative_level": -55,
            "silence_level": -70,
            "silence_hold": 20,
            "update_check": True,
        },
    )
    await hass.async_block_till_done()
    assert entry.options == {
        "signal_relative_level": -55.0,
        "silence_level": -70.0,
        "silence_hold": 20.0,
        "update_check": True,
    }
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.signal_relative == -55.0
    assert coordinator.update_check is True
