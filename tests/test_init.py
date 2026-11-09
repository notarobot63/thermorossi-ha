"""Tests for setup, entities and the coordinator."""
from __future__ import annotations

from datetime import timedelta

import asyncio

import pytest
from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from custom_components.thermorossi import _get_entry_device
from custom_components.thermorossi.const import CMD_OFF, DOMAIN
from custom_components.thermorossi.diagnostics import async_get_config_entry_diagnostics

from .conftest import GET_URL, HOST, SET_URL, STATUS_URL, make_params, make_registers


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


def test_get_entry_device_prefers_new_api() -> None:
    """async_get_device is deprecated (breaks in HA 2027.8): use its replacement when present."""
    calls = []

    class Registry:
        def async_get_device_by_identifier(self, identifier, config_entry_id):
            calls.append((identifier, config_entry_id))
            return "device"

        def async_get_device(self, **kwargs):
            raise AssertionError("deprecated API used")

    assert _get_entry_device(Registry(), (DOMAIN, HOST), "entry") == "device"
    assert calls == [((DOMAIN, HOST), "entry")]


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


async def test_unknown_register_layout_names_firmware(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    aioclient_mock.post(GET_URL, json={"registers": [[0, 39], [50, 21]]})
    aioclient_mock.post(STATUS_URL, json={"fwVer": "0.79"})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "WiNET firmware 0.79" in config_entry.reason
    assert "[6, 15, 16]" in config_entry.reason


async def test_diagnostics(hass: HomeAssistant, aioclient_mock, config_entry) -> None:
    aioclient_mock.post(GET_URL, json=make_registers())
    aioclient_mock.post(
        STATUS_URL,
        json={"fwVer": "0.73", "currentIp": "192.168.1.100", "network": "MonReseau"},
    )
    await _setup(hass, config_entry)

    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"][CONF_HOST] == REDACTED
    assert diag["module_status"]["fwVer"] == "0.73"
    assert diag["module_status"]["currentIp"] == REDACTED
    assert diag["module_status"]["network"] == REDACTED
    assert diag["raw_replies"]["key=020&category=1"] == make_registers()
    assert diag["registers"][6] == 3


async def test_diagnostics_when_setup_failed(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """After a firmware update breaks setup, diagnostics must still hold the raw reply."""
    body = {"key": "020", "params": [[0, 39]], "cat": 1}
    aioclient_mock.post(GET_URL, json=body)
    aioclient_mock.post(STATUS_URL, json={"fwVer": "0.79"})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["module_status"]["fwVer"] == "0.79"
    assert diag["raw_replies"]["key=020&category=1"] == body
    assert diag["registers"] is None


# --- "params" dialect (WiNET firmware 0.79) ---------------------------------


class ParamsStove:
    """Mock of a "params" dialect module: answers reads, counts toggles."""

    def __init__(self, **overrides) -> None:
        self.reply = make_params(**overrides)
        self.toggles = 0
        self.settings: dict = {}
        self.settings_reads = 0

    async def side_effect(self, method, url, data):
        data = str(data)
        if data == "key=022":
            self.toggles += 1
            await asyncio.sleep(0.01)  # let a concurrent call reach its state check
            return AiohttpClientMockResponse(method, url, json={"result": True})
        if data == "key=019":
            self.settings_reads += 1
            return AiohttpClientMockResponse(method, url, json=self.settings)
        if "category=1" in data:
            # Some modules answer category 1 with an empty list
            return AiohttpClientMockResponse(
                method, url, json={"params": [], "cat": 1, "signal": 2}
            )
        return AiohttpClientMockResponse(method, url, json=self.reply)

    def set(self, **overrides) -> None:
        self.reply = make_params(**overrides)


async def _setup_params(hass, aioclient_mock, config_entry, **overrides) -> ParamsStove:
    stove = ParamsStove(**overrides)
    aioclient_mock.post(GET_URL, side_effect=stove.side_effect)
    aioclient_mock.post(SET_URL, json={"result": True})
    await _setup(hass, config_entry)
    return stove


async def _refresh(hass: HomeAssistant, config_entry) -> None:
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_params_entities(hass: HomeAssistant, aioclient_mock, config_entry) -> None:
    await _setup_params(hass, aioclient_mock, config_entry)
    assert config_entry.runtime_data.dialect == "params"

    assert hass.states.get("switch.thermorossi_stove").state == STATE_OFF
    status = hass.states.get("sensor.thermorossi_state")
    assert status.state == "off"
    assert "final_cleaning" in status.attributes["options"]
    assert "sunout" not in status.attributes["options"]
    assert hass.states.get("sensor.thermorossi_ambient_temperature").state == "23.0"
    assert hass.states.get("sensor.thermorossi_alarm_message").state == "ok"
    assert hass.states.get("binary_sensor.thermorossi_alarm").state == STATE_OFF
    assert hass.states.get("binary_sensor.thermorossi_error_stop").state == STATE_OFF

    setpoint = hass.states.get("number.thermorossi_temperature_setpoint")
    assert setpoint.state == "23.0"
    assert (setpoint.attributes["min"], setpoint.attributes["max"]) == (5, 40)
    power = hass.states.get("number.thermorossi_power_level")
    assert power.state == "3.0"
    assert (power.attributes["min"], power.attributes["max"]) == (1, 5)

    rtc = hass.states.get("sensor.thermorossi_internal_clock")
    assert rtc.state == "16:02"
    assert rtc.attributes["weekday"] == 7

    # Nothing decoded for these on this firmware: not created
    assert hass.states.get("number.thermorossi_fan_speed") is None
    assert hass.states.get("binary_sensor.thermorossi_pellets_low") is None
    assert hass.states.get("sensor.thermorossi_weekly_schedule") is None
    assert hass.states.get("sensor.thermorossi_flue_temperature") is None


async def test_params_reads_category_2(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    await _setup_params(hass, aioclient_mock, config_entry)
    reads = [str(c[2]) for c in aioclient_mock.mock_calls if str(c[1]) == GET_URL]
    assert reads == ["key=020&category=1", "key=020&category=2"]

    aioclient_mock.mock_calls.clear()
    await _refresh(hass, config_entry)
    reads = [str(c[2]) for c in aioclient_mock.mock_calls if str(c[1]) == GET_URL]
    assert reads == ["key=020&category=2"]


async def test_params_writes(hass: HomeAssistant, aioclient_mock, config_entry) -> None:
    await _setup_params(hass, aioclient_mock, config_entry)

    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.thermorossi_temperature_setpoint", "value": 24},
        blocking=True,
    )
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.thermorossi_power_level", "value": 2},
        blocking=True,
    )
    writes = [str(c[2]) for c in aioclient_mock.mock_calls if str(c[1]) == SET_URL]
    assert writes == [
        "key=002&memory=1&regId=50&value=24",
        "key=002&memory=1&regId=51&value=2",
    ]


async def test_params_half_degree_setpoint(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """With setTempDiv 0.5 the raw setpoint is in half degrees."""
    stove = ParamsStove(p50=43)
    stove.reply["setTempDiv"] = 0.5
    aioclient_mock.post(GET_URL, side_effect=stove.side_effect)
    aioclient_mock.post(SET_URL, json={"result": True})
    await _setup(hass, config_entry)

    setpoint = hass.states.get("number.thermorossi_temperature_setpoint")
    assert setpoint.state == "21.5"
    assert setpoint.attributes["step"] == 0.5
    # The official page's bounds are in °C, whatever the step
    assert (setpoint.attributes["min"], setpoint.attributes["max"]) == (5, 40)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.thermorossi_temperature_setpoint", "value": 19.5},
        blocking=True,
    )
    set_call = next(c for c in aioclient_mock.mock_calls if str(c[1]) == SET_URL)
    assert set_call[2] == "key=002&memory=1&regId=50&value=39"


async def test_params_settings_from_key_019(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """Firmware 0.43 sends the scale factors only in the key=019 settings reply."""
    stove = ParamsStove(p0=51, p50=48)
    for field in ("tempDiv", "setTempDiv", "numPower", "custom"):
        del stove.reply[field]
    stove.settings = {"key": "019", "tempDiv": 0.5, "setTempDiv": 0.5, "numPower": 4,
                      "custom": 65535, "name": "NO NAME"}
    aioclient_mock.post(GET_URL, side_effect=stove.side_effect)
    aioclient_mock.post(SET_URL, json={"result": True})
    await _setup(hass, config_entry)

    assert hass.states.get("sensor.thermorossi_ambient_temperature").state == "25.5"
    assert hass.states.get("number.thermorossi_temperature_setpoint").state == "24.0"
    assert hass.states.get("number.thermorossi_power_level").attributes["max"] == 4
    await _refresh(hass, config_entry)
    assert stove.settings_reads == 1


async def test_params_settings_read_failure_fails_update(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """Without the scale factors, no value is shown rather than a doubled one."""
    stove = ParamsStove()
    del stove.reply["tempDiv"]
    stove.settings = None  # key=019 answers with a server error

    async def side_effect(method, url, data):
        if str(data) == "key=019":
            return AiohttpClientMockResponse(method, url, status=500)
        return await stove.side_effect(method, url, data)

    aioclient_mock.post(GET_URL, side_effect=side_effect)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_params_settings_in_reply_skip_key_019(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    stove = await _setup_params(hass, aioclient_mock, config_entry)
    assert stove.settings_reads == 0


async def _switch(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(
        "switch", service, {"entity_id": "switch.thermorossi_stove"}, blocking=True
    )


async def test_params_toggle_only_when_needed(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """On/off is a toggle: it must never be sent when it would do the opposite."""
    stove = await _setup_params(hass, aioclient_mock, config_entry)

    await _switch(hass, "turn_off")  # already off
    assert stove.toggles == 0

    await _switch(hass, "turn_on")
    assert stove.toggles == 1
    # Not reflected in the state yet: a second toggle would undo the first
    await _switch(hass, "turn_on")
    assert stove.toggles == 1
    # The opposite request is refused loudly rather than silently dropped
    with pytest.raises(HomeAssistantError, match="previous on command"):
        await _switch(hass, "turn_off")
    assert stove.toggles == 1

    stove.set(p2=1)  # waiting for flame
    await _refresh(hass, config_entry)
    assert hass.states.get("switch.thermorossi_stove").state == STATE_ON
    await _switch(hass, "turn_on")  # already on
    assert stove.toggles == 1
    await _switch(hass, "turn_off")
    assert stove.toggles == 2


async def test_params_final_cleaning(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    stove = await _setup_params(hass, aioclient_mock, config_entry, p2=6)
    assert hass.states.get("sensor.thermorossi_state").state == "final_cleaning"
    assert hass.states.get("switch.thermorossi_stove").state == STATE_ON

    await _switch(hass, "turn_off")  # already stopping
    with pytest.raises(HomeAssistantError):
        await _switch(hass, "turn_on")
    assert stove.toggles == 0


async def test_params_alarm(hass: HomeAssistant, aioclient_mock, config_entry) -> None:
    # Bit 2 flickers during ignition: not an alarm while the stove runs
    stove = await _setup_params(hass, aioclient_mock, config_entry, p2=1, p3=0b100)
    assert hass.states.get("binary_sensor.thermorossi_alarm").state == STATE_OFF
    assert hass.states.get("sensor.thermorossi_alarm_message").state == "ok"

    stove.set(p2=8, p3=0b10000)
    await _refresh(hass, config_entry)
    assert hass.states.get("sensor.thermorossi_state").state == "alarm"
    assert hass.states.get("sensor.thermorossi_alarm_message").state == "no_pellets"
    alarm = hass.states.get("binary_sensor.thermorossi_alarm")
    assert alarm.state == STATE_ON
    assert alarm.attributes["active_alarms"] == ["no_pellets"]
    assert hass.states.get("binary_sensor.thermorossi_error_stop").state == STATE_ON
    assert hass.states.get("number.thermorossi_power_level").state == STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError):
        await _switch(hass, "turn_on")
    assert stove.toggles == 0
    await _switch(hass, "turn_off")  # acknowledges the alarm
    assert stove.toggles == 1


async def test_params_missing_values_names_firmware(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    aioclient_mock.post(GET_URL, json={"params": [[0, 39]], "cat": 2})
    aioclient_mock.post(STATUS_URL, json={"fwVer": "0.43"})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "WiNET firmware 0.43" in config_entry.reason
    assert "[2, 50, 51]" in config_entry.reason


async def test_params_diagnostics_redact_ssid(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    await _setup_params(hass, aioclient_mock, config_entry)
    aioclient_mock.post(STATUS_URL, json={"fwVer": "0.79"})
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["dialect"] == "params"
    assert diag["raw_replies"]["key=020&category=2"]["ssid"] == REDACTED
    assert diag["registers"][50] == 23


async def test_firmware_update_switches_dialect(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """A module updated to 0.79 while running gets its entities rebuilt."""
    aioclient_mock.post(GET_URL, json=make_registers())
    await _setup(hass, config_entry)
    assert hass.states.get("number.thermorossi_fan_speed") is not None

    aioclient_mock.clear_requests()
    stove = ParamsStove(p2=4)
    aioclient_mock.post(GET_URL, side_effect=stove.side_effect)
    aioclient_mock.post(SET_URL, json={"result": True})
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.dialect == "params"
    assert hass.states.get("sensor.thermorossi_state").state == "work"
    assert hass.states.get("number.thermorossi_fan_speed").state == STATE_UNAVAILABLE


async def test_firmware_downgrade_switches_dialect(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """A "params" module that starts answering "registers" gets its entities rebuilt."""
    await _setup_params(hass, aioclient_mock, config_entry)
    assert hass.states.get("number.thermorossi_fan_speed") is None

    aioclient_mock.clear_requests()
    aioclient_mock.post(GET_URL, json=make_registers())
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.dialect == "registers"
    assert hass.states.get("number.thermorossi_fan_speed").state == "2.0"


async def test_params_toggle_guard_expires(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """A toggle the stove ignored must not lock the switch for good."""
    stove = await _setup_params(hass, aioclient_mock, config_entry)
    coordinator = config_entry.runtime_data
    await _switch(hass, "turn_on")
    assert stove.toggles == 1
    coordinator._toggle_sent_at -= 14
    await _switch(hass, "turn_on")
    assert stove.toggles == 1
    coordinator._toggle_sent_at -= 2  # 16 s later, state still off: the toggle was lost
    await _switch(hass, "turn_on")
    assert stove.toggles == 2


async def test_params_simultaneous_turn_on_sends_one_toggle(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    stove = await _setup_params(hass, aioclient_mock, config_entry)
    await asyncio.gather(_switch(hass, "turn_on"), _switch(hass, "turn_on"))
    assert stove.toggles == 1


async def test_params_rejected_toggle(
    hass: HomeAssistant, aioclient_mock, config_entry
) -> None:
    """A refused toggle raises and does not arm the guard."""
    stove = ParamsStove()
    calls = {"toggle": 0}

    async def side_effect(method, url, data):
        if str(data) == "key=022":
            calls["toggle"] += 1
            return AiohttpClientMockResponse(method, url, json={"result": False})
        return await stove.side_effect(method, url, data)

    aioclient_mock.post(GET_URL, side_effect=side_effect)
    await _setup(hass, config_entry)

    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await _switch(hass, "turn_on")
    assert calls["toggle"] == 2


async def test_params_num_power_from_reply(
    hass: HomeAssistant, aioclient_mock, config_entry, caplog
) -> None:
    stove = ParamsStove()
    stove.reply["numPower"] = 3
    stove.reply["custom"] = 5619
    aioclient_mock.post(GET_URL, side_effect=stove.side_effect)
    await _setup(hass, config_entry)

    assert hass.states.get("number.thermorossi_power_level").attributes["max"] == 3
    # Another model variant: decoded with the default tables, but flagged
    assert "customization code 5619" in caplog.text


@pytest.mark.parametrize(("state", "key"), [(8, "alarm"), (9, "alarm_memory")])
async def test_params_alarm_states(
    hass: HomeAssistant, aioclient_mock, config_entry, state, key
) -> None:
    stove = await _setup_params(
        hass, aioclient_mock, config_entry, p2=state, p3=0b1000
    )
    assert hass.states.get("sensor.thermorossi_state").state == key
    assert hass.states.get("binary_sensor.thermorossi_error_stop").state == STATE_ON
    assert hass.states.get("sensor.thermorossi_alarm_message").state == "start_failed"
    with pytest.raises(HomeAssistantError):
        await _switch(hass, "turn_on")
    assert stove.toggles == 0
