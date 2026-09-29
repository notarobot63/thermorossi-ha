"""Tests for setup, entities and the coordinator."""
from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from custom_components.thermorossi.const import CMD_OFF, DOMAIN

from .conftest import GET_URL, HOST, SET_URL, make_registers


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _set_count(aioclient_mock) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == SET_URL)


def _get_count(aioclient_mock) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == GET_URL)


async def test_entities_are_named_in_english(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """translations/en.json must exist, otherwise every entity is just 'Thermorossi'."""
    aioclient_mock.post(GET_URL, json=make_registers())
    await _setup(hass, config_entry)

    assert hass.states.get("switch.thermorossi_stove").state == STATE_ON
    assert hass.states.get("sensor.thermorossi_state").state == "work"
    assert hass.states.get("sensor.thermorossi_ambient_temperature").state == "20.0"
    assert hass.states.get("sensor.thermorossi_flue_temperature").state == "120"
    assert hass.states.get("sensor.thermorossi_alarm_message").state == "ok"
    assert hass.states.get("binary_sensor.thermorossi_alarm").state == STATE_OFF
    assert hass.states.get("binary_sensor.thermorossi_chrono_active").state == STATE_ON
    assert hass.states.get("number.thermorossi_power_level").state == "3.0"
    assert hass.states.get("number.thermorossi_temperature_setpoint").state == "22.0"

    rtc = hass.states.get("sensor.thermorossi_internal_clock")
    assert rtc.state == "14:05"
    assert rtc.attributes["weekday"] == 3

    # Read-only duplicates of the number entities are disabled by default
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get("sensor.thermorossi_power_level").disabled_by is not None


async def test_status_and_alarm_are_enums(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    aioclient_mock.post(GET_URL, json=make_registers(r6=8, r8=0b10))
    await _setup(hass, config_entry)

    status = hass.states.get("sensor.thermorossi_state")
    assert status.state == "stop"
    assert "stop" in status.attributes["options"]
    alarm = hass.states.get("sensor.thermorossi_alarm_message")
    assert alarm.state == "start_failed"
    assert "start_failed" in alarm.attributes["options"]
    assert hass.states.get("binary_sensor.thermorossi_alarm").attributes[
        "active_alarms"
    ] == ["start_failed"]


async def test_stale_data_makes_entities_unavailable(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    aioclient_mock.post(GET_URL, json=make_registers())
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.thermorossi_ambient_temperature").state == "20.0"

    aioclient_mock.clear_requests()
    aioclient_mock.post(GET_URL, status=500)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.thermorossi_ambient_temperature",
        "sensor.thermorossi_flue_temperature",
        "switch.thermorossi_stove",
        "number.thermorossi_power_level",
    ):
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE, entity_id


async def test_setup_retries_when_stove_unreachable(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    aioclient_mock.post(GET_URL, status=500)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_fast_poll_after_command(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """After a write, the state must be re-read every second, not every 10s."""
    aioclient_mock.post(GET_URL, json=make_registers())
    aioclient_mock.post(SET_URL, json={"result": True})
    await _setup(hass, config_entry)

    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.thermorossi_fan_speed", "value": 4},
        blocking=True,
    )
    reads_before = _get_count(aioclient_mock)
    now = dt_util.utcnow()
    for second in range(1, 6):
        async_fire_time_changed(hass, now + timedelta(seconds=second))
        await hass.async_block_till_done()
    assert _get_count(aioclient_mock) - reads_before >= 4

    set_call = next(c for c in aioclient_mock.mock_calls if str(c[1]) == SET_URL)
    assert set_call[2] == "key=002&regId=13&value=4&result=false"


async def test_setpoint_conversion(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    aioclient_mock.post(GET_URL, json=make_registers())
    aioclient_mock.post(SET_URL, json={"result": True})
    await _setup(hass, config_entry)

    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.thermorossi_temperature_setpoint", "value": 21.5},
        blocking=True,
    )
    set_call = next(c for c in aioclient_mock.mock_calls if str(c[1]) == SET_URL)
    assert set_call[2] == "key=002&regId=15&value=158&result=false"


async def test_rejected_write_raises(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    aioclient_mock.post(GET_URL, json=make_registers())
    aioclient_mock.post(SET_URL, json={"result": False})
    await _setup(hass, config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": "switch.thermorossi_stove"}, blocking=True
        )


async def test_error_stop_can_be_acknowledged(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """In STOP error state the switch stays usable so the alarm can be cleared."""
    aioclient_mock.post(GET_URL, json=make_registers(r6=8))
    aioclient_mock.post(SET_URL, json={"result": True})
    await _setup(hass, config_entry)

    switch = hass.states.get("switch.thermorossi_stove")
    assert switch.state == STATE_ON
    assert hass.states.get("number.thermorossi_power_level").state == STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.thermorossi_stove"}, blocking=True
        )
    assert _set_count(aioclient_mock) == 0

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.thermorossi_stove"}, blocking=True
    )
    set_call = next(c for c in aioclient_mock.mock_calls if str(c[1]) == SET_URL)
    assert set_call[2] == f"key=002&regId=1&value={CMD_OFF}&result=false"


async def test_device_identifier_migrated(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """Devices created by <= 1.1 (keyed on the host) are re-keyed, not duplicated."""
    aioclient_mock.post(GET_URL, json=make_registers())
    config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    old = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, HOST)},
        name="Thermorossi",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id)
    assert [d.id for d in devices] == [old.id]
    assert devices[0].identifiers == {(DOMAIN, config_entry.entry_id)}


async def test_unload(hass: HomeAssistant, aioclient_mock, config_entry) -> None:
    aioclient_mock.post(GET_URL, json=make_registers())
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


def _by_category(chrono_status: int = 200):
    """Mock side effect answering category=1 and category=2 differently."""
    chrono = {reg: 0 for reg in range(24, 66)}
    for day in range(7):
        chrono[24 + 6 * day] = 0x0600  # 06:00
        chrono[25 + 6 * day] = 0x081E  # 08:30
    chrono[34], chrono[35] = 0x1200, 0x1600  # Tuesday slot 3: 18:00-22:00
    calls = {"chrono": 0}

    async def side_effect(method, url, data):
        if "category=2" in str(data):
            calls["chrono"] += 1
            if chrono_status != 200:
                return AiohttpClientMockResponse(method, url, status=chrono_status)
            return AiohttpClientMockResponse(
                method, url, json={"registers": [[k, v] for k, v in chrono.items()]}
            )
        return AiohttpClientMockResponse(method, url, json=make_registers())

    return side_effect, calls


async def test_weekly_schedule_sensor(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    side_effect, calls = _by_category()
    aioclient_mock.post(GET_URL, side_effect=side_effect)
    await _setup(hass, config_entry)

    state = hass.states.get("sensor.thermorossi_weekly_schedule")
    assert state.state == "8"
    assert state.attributes["monday"] == ["06:00-08:30"]
    assert state.attributes["tuesday"] == ["06:00-08:30", "18:00-22:00"]

    # The schedule is cached between regular polls
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert calls["chrono"] == 1


async def test_weekly_schedule_failure_keeps_other_entities(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    side_effect, _ = _by_category(chrono_status=500)
    aioclient_mock.post(GET_URL, side_effect=side_effect)
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.thermorossi_ambient_temperature").state == "20.0"
    assert hass.states.get("sensor.thermorossi_weekly_schedule").state == STATE_UNAVAILABLE
