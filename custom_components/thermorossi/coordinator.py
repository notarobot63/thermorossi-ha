"""DataUpdateCoordinator for the Thermorossi integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    API_GET_REGISTERS,
    API_SET_REGISTER,
    API_HEADERS,
    GET_PAYLOAD,
    CMD_ON,
    CMD_OFF,
    SET_KEY,
    SET_REG_ID,
)

_LOGGER = logging.getLogger(__name__)


class ThermorossiCoordinator(DataUpdateCoordinator[dict]):
    """Polls the Thermorossi WiNET API and exposes register data."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        self.host = host
        self._base_url = f"http://{host}"
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def get_register(self, index: int) -> int | None:
        """Return the value of a register by index, or None if unavailable."""
        if self.data is None:
            return None
        return self.data.get(index)

    async def _async_update_data(self) -> dict[int, int]:
        """Fetch registers from the stove."""
        url = f"{self._base_url}{API_GET_REGISTERS}"
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                url,
                data=GET_PAYLOAD,
                headers=API_HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error to stove ({self.host}): {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        registers = payload.get("registers", [])
        return {entry[0]: entry[1] for entry in registers}

    def _schedule_fast_poll(self) -> None:
        """Schedule rapid refreshes after a command: every 1s for 10s, then every 2s up to 30s."""
        @callback
        def _do_refresh(_now=None) -> None:
            self.hass.async_create_task(self.async_request_refresh())

        for delay in [*range(1, 11), *range(12, 32, 2)]:
            async_call_later(self.hass, delay, _do_refresh)

    async def async_turn_on(self) -> bool:
        """Send the ON command."""
        result = await self._send_command(CMD_ON)
        self._schedule_fast_poll()
        return result

    async def async_turn_off(self) -> bool:
        """Send the OFF command."""
        result = await self._send_command(CMD_OFF)
        self._schedule_fast_poll()
        return result

    async def _send_command(self, value: int) -> bool:
        return await self._send_command_reg(SET_REG_ID, value)

    async def _send_command_reg(self, reg_id: int, value: int) -> bool:
        url = f"{self._base_url}{API_SET_REGISTER}"
        payload = f"key={SET_KEY}&regId={reg_id}&value={value}&result=false"
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                url,
                data=payload,
                headers=API_HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                result = await resp.json(content_type=None)
                return result.get("result", False) is True
        except Exception as err:
            _LOGGER.error("Error sending command to stove: %s", err)
            return False
