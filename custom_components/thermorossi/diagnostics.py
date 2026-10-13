"""Diagnostics for the Thermorossi integration.

The raw module replies are what is needed to support another WiNET firmware.
"""
from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import ThermorossiConfigEntry

TO_REDACT = {CONF_HOST, "currentIp", "currentGw", "currentMask", "network", "name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ThermorossiConfigEntry
) -> dict[str, Any]:
    """Return the module status, raw replies and decoded registers."""
    coordinator = entry.runtime_data
    try:
        module_status: Any = await coordinator.async_get_module_status()
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        module_status = {"error": repr(err)}

    return async_redact_data(
        {
            "entry": dict(entry.data),
            "module_status": module_status,
            "raw_replies": coordinator.last_payloads,
            "registers": coordinator.data,
        },
        TO_REDACT,
    )
