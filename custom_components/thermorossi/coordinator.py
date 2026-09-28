"""DataUpdateCoordinator for the Thermorossi integration."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    FAST_POLL_DELAYS,
    REFRESH_COOLDOWN,
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
    REG_STATUS,
)
from .parsing import build_base_url, compute_alarm_code, parse_registers

_LOGGER = logging.getLogger(__name__)

type ThermorossiConfigEntry = ConfigEntry[ThermorossiCoordinator]


class ThermorossiCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Polls the Thermorossi WiNET API and exposes register data."""

    config_entry: ThermorossiConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ThermorossiConfigEntry) -> None:
        self.host: str = entry.data[CONF_HOST]
        self.base_url = build_base_url(self.host)
        self._fast_poll_cancels: list[Callable[[], None]] = []
        # The WiNET module is a tiny single-threaded HTTP server: serialize
        # every request (reads and writes) to it.
        self._io_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            # The default 10s cooldown would swallow the 1s fast-poll requests.
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REFRESH_COOLDOWN, immediate=True
            ),
        )

    def get(self, index: int) -> int | None:
        """Return the raw value of a register, or None if unknown."""
        if self.data is None:
            return None
        return self.data.get(index)

    @property
    def status_code(self) -> int | None:
        """Return the stove status code (register 6 & 0xFF), or None if unknown."""
        raw = self.get(REG_STATUS)
        return None if raw is None else raw & 0xFF

    @property
    def alarm_code(self) -> int:
        """Return the 32-bit alarm code (0 = no alarm)."""
        return compute_alarm_code(
            self.get(REG_ALARM_MSB) or 0, self.get(REG_ALARM_LSB) or 0
        )

    async def _post(self, path: str, payload: str) -> Any:
        """POST a form payload to the stove and return the decoded JSON body."""
        session = async_get_clientsession(self.hass)
        async with self._io_lock, session.post(
            f"{self.base_url}{path}",
            data=payload,
            headers=API_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _async_update_data(self) -> dict[int, int]:
        """Fetch registers from the stove."""
        try:
            payload = await self._post(API_GET_REGISTERS, GET_PAYLOAD)
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
            self.config_entry.async_create_background_task(
                self.hass, self.async_request_refresh(), f"{DOMAIN}_fast_poll"
            )

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
        return await self.async_set_register(SET_REG_ID, CMD_ON)

    async def async_turn_off(self) -> bool:
        """Send the OFF command."""
        return await self.async_set_register(SET_REG_ID, CMD_OFF)

    async def async_set_register(self, reg_id: int, value: int) -> bool:
        """Write a register, then poll quickly so the new state shows up fast."""
        payload = f"key={SET_KEY}&regId={reg_id}&value={value}&result=false"
        try:
            result = await self._post(API_SET_REGISTER, payload)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.error("Error writing register %s on stove (%s): %s", reg_id, self.host, err)
            return False

        if not (isinstance(result, dict) and result.get("result") is True):
            _LOGGER.error(
                "Stove (%s) rejected write of register %s: %r", self.host, reg_id, result
            )
            return False

        # The first fast poll (1s) picks up the new state.
        self._schedule_fast_poll()
        return True
