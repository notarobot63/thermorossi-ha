"""Config flow for the Thermorossi integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN, API_GET_REGISTERS, GET_PAYLOAD

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}


class ThermorossiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Thermorossi."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            error = await self._test_connection(host)
            if error is None:
                return self.async_create_entry(
                    title=f"Thermorossi ({host})",
                    data={CONF_HOST: host},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def _test_connection(self, host: str) -> str | None:
        """Try connecting to the stove. Returns an error key or None on success."""
        url = f"http://{host}{API_GET_REGISTERS}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=GET_PAYLOAD,
                    headers=HEADERS,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
                    if "registers" not in data:
                        return "invalid_response"
        except aiohttp.ClientConnectorError:
            return "cannot_connect"
        except Exception:
            return "cannot_connect"
        return None
