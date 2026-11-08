"""Shared fixtures for the Home Assistant tests."""
from __future__ import annotations

import pytest
from homeassistant.const import CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermorossi.const import DOMAIN

HOST = "192.168.1.100"
GET_URL = f"http://{HOST}/ajax/get-registers"
SET_URL = f"http://{HOST}/ajax/set-register"
STATUS_URL = f"http://{HOST}/ajax/get-status"


def make_registers(**overrides: int) -> dict:
    """Return a get-registers payload for a stove heating normally."""
    regs = {
        6: 3,        # work
        7: 0x1,      # chrono on
        8: 0, 9: 0,  # no alarm
        10: 0,       # pellets OK
        12: 3,       # power level
        13: 2,       # fan speed
        15: 160,     # 22.0 °C setpoint
        16: 152,     # 20.0 °C ambient
        21: 120,     # flue °C
        22: (3 << 11) | (14 << 6) | 5,  # Wed 14:05
    }
    for key, value in overrides.items():
        regs[int(key.removeprefix("r"))] = value
    return {"registers": [[k, v] for k, v in regs.items()]}


def make_params(**overrides: int) -> dict:
    """Return a "params" dialect reply (firmware 0.79), taken from a real capture.

    The stove is off; ambient 23 °C (46 * tempDiv 0.5), setpoint 23 °C, power 3,
    clock Sunday 16:02 (BCD).
    """
    params = {0: 46, 2: 0, 3: 0, 4: 4, 50: 23, 51: 3, 59: 7, 60: 0x16, 61: 0x02,
              62: 8, 63: 17, 64: 38, 300: 1, 301: 128, 302: 0, 303: 0}
    for key, value in overrides.items():
        params[int(key.removeprefix("p"))] = value
    return {
        "key": "020", "params": [[k, v] for k, v in params.items()],
        "tsense": {"show": 0, "list": []}, "cat": 2, "signal": 4, "logTemp": 230,
        "tempDiv": 0.5, "setTempDiv": 1, "numPower": 5, "mode": 0, "modeThreeshold": 0,
        "tStart": 22, "tStop": 24, "model": 0, "isOld": False, "custom": 65535,
        "name": "NO NAME", "ssid": "MonReseau", "inetTime": [2026, 11, 8, 15, 57, 0, 0, 7],
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in every test."""
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}, unique_id=HOST)
