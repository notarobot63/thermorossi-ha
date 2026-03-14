"""Config flow for the Thermorossi integration."""
from __future__ import annotations

import ipaddress
import re

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, API_GET_REGISTERS, API_HEADERS, GET_PAYLOAD

_HOSTNAME_RE = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
)


def _is_valid_host(host: str) -> bool:
    """Return True if host is a valid IPv4/IPv6 address or hostname."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    return bool(_HOSTNAME_RE.match(host)) and len(host) <= 253


class ThermorossiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Thermorossi."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            if not _is_valid_host(host):
                errors["base"] = "invalid_host"
            else:
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
            session = async_get_clientsession(self.hass)
            async with session.post(
                url,
                data=GET_PAYLOAD,
                headers=API_HEADERS,
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
