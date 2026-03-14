"""DataUpdateCoordinator for the Thermorossi integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    API_GET_REGISTERS,
    API_SET_REGISTER,
    GET_PAYLOAD,
    CMD_ON,
    CMD_OFF,
    SET_KEY,
    SET_REG_ID,
)

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}


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
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=GET_PAYLOAD,
                    headers=HEADERS,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    payload = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Erreur de connexion au poêle ({self.host}): {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Erreur inattendue: {err}") from err

        registers = payload.get("registers", [])
        return {entry[0]: entry[1] for entry in registers}

    async def async_turn_on(self) -> bool:
        """Send the ON command."""
        return await self._send_command(CMD_ON)

    async def async_turn_off(self) -> bool:
        """Send the OFF command."""
        return await self._send_command(CMD_OFF)

    async def _send_command(self, value: int) -> bool:
        url = f"{self._base_url}{API_SET_REGISTER}"
        payload = f"key={SET_KEY}&regId={SET_REG_ID}&value={value}&result=false"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=payload,
                    headers=HEADERS,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    result = await resp.json(content_type=None)
                    return result.get("result", False) is True
        except Exception as err:
            _LOGGER.error("Erreur envoi commande au poêle: %s", err)
            return False
