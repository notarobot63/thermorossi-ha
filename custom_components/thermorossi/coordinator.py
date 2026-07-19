"""DataUpdateCoordinator for the Thermorossi integration."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    FAST_POLL_DELAYS,
    API_GET_REGISTERS,
    API_SET_REGISTER,
    API_HEADERS,
    GET_PAYLOAD,
    CMD_ON,
    CMD_OFF,
    SET_KEY,
    SET_REG_ID,
    REG_ALARM_LSB,
    REG_ALARM_MSB,
)
from .parsing import compute_alarm_code, parse_registers

_LOGGER = logging.getLogger(__name__)


class ThermorossiCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Polls the Thermorossi WiNET API and exposes register data."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        self.host = host
        self._base_url = f"http://{host}"
        self._fast_poll_cancels: list[Callable[[], None]] = []
        self._write_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def alarm_code(self) -> int:
        """Return the 32-bit alarm code (0 = no alarm)."""
        if self.data is None:
            return 0
        return compute_alarm_code(
            self.data.get(REG_ALARM_MSB, 0), self.data.get(REG_ALARM_LSB, 0)
        )

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
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Connection error to stove ({self.host}): {err}") from err
        except ValueError as err:
            raise UpdateFailed(f"Invalid response from stove ({self.host}): {err}") from err

        try:
            return parse_registers(payload)
        except ValueError as err:
            raise UpdateFailed(f"Invalid register data from stove ({self.host}): {err}") from err

    def _schedule_fast_poll(self) -> None:
        """Schedule rapid refreshes after a command: every 1s for 10s, then every 2s up to 30s."""
        self._cancel_fast_poll()

        @callback
        def _do_refresh(_now=None) -> None:
            self.hass.async_create_task(self.async_request_refresh())

        for delay in FAST_POLL_DELAYS:
            self._fast_poll_cancels.append(async_call_later(self.hass, delay, _do_refresh))

    def _cancel_fast_poll(self) -> None:
        """Cancel any pending fast-poll callbacks."""
        for cancel in self._fast_poll_cancels:
            cancel()
        self._fast_poll_cancels.clear()

    async def async_shutdown(self) -> None:
        """Cancel pending fast-poll callbacks on unload, then run normal shutdown."""
        self._cancel_fast_poll()
        await super().async_shutdown()

    async def async_turn_on(self) -> bool:
        """Send the ON command."""
        result = await self._send_command(CMD_ON)
        if result:
            self._schedule_fast_poll()
        return result

    async def async_turn_off(self) -> bool:
        """Send the OFF command."""
        result = await self._send_command(CMD_OFF)
        if result:
            self._schedule_fast_poll()
        return result

    async def async_set_register(self, reg_id: int, value: int) -> bool:
        """Public API to write an arbitrary register (used by number entities)."""
        return await self._send_command_reg(reg_id, value)

    async def _send_command(self, value: int) -> bool:
        return await self._send_command_reg(SET_REG_ID, value)

    async def _send_command_reg(self, reg_id: int, value: int) -> bool:
        url = f"{self._base_url}{API_SET_REGISTER}"
        payload = f"key={SET_KEY}&regId={reg_id}&value={value}&result=false"
        async with self._write_lock:
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
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.error("Error sending command to stove: %s", err)
                return False
        return isinstance(result, dict) and result.get("result") is True
