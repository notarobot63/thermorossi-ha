"""Shared fixtures for the Home Assistant tests."""
from __future__ import annotations

import pytest
from homeassistant.const import CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermorossi.const import DOMAIN

HOST = "192.168.1.100"
GET_URL = f"http://{HOST}/ajax/get-registers"
SET_URL = f"http://{HOST}/ajax/set-register"


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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in every test."""
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}, unique_id=HOST)
