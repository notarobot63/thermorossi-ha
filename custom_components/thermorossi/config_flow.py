"""Config flow for the Thermorossi integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, API_GET_REGISTERS, API_HEADERS, GET_PAYLOAD
from .parsing import build_base_url, is_valid_host, normalize_host, parse_registers

_LOGGER = logging.getLogger(__name__)

STEP_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class ThermorossiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Thermorossi."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])

            if not is_valid_host(host):
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
            data_schema=self.add_suggested_values_to_schema(STEP_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the stove address (e.g. after a DHCP lease change)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])

            if not is_valid_host(host):
                errors["base"] = "invalid_host"
            else:
                if host != entry.unique_id:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()

                error = await self._test_connection(host)
                if error is None:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=host,
                        title=f"Thermorossi ({host})",
                        data={**entry.data, CONF_HOST: host},
                    )
                errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def _test_connection(self, host: str) -> str | None:
        """Try connecting to the stove. Returns an error key or None on success.

        Every failure is logged with the details needed to diagnose it.
        """
        url = f"{build_base_url(host)}{API_GET_REGISTERS}"
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                url,
                data=GET_PAYLOAD,
                headers=API_HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.text(errors="replace")
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Cannot connect to %s: %r", url, err)
            return "cannot_connect"

        if status >= 400:
            _LOGGER.warning(
                "%s answered HTTP %s (is this really a WiNET module?): %.300s",
                url, status, body,
            )
            return "http_error"

        try:
            payload = json.loads(body)
        except ValueError:
            _LOGGER.warning(
                "%s did not answer with JSON (is this really a WiNET module?): %.300s",
                url, body,
            )
            return "not_json"

        try:
            parse_registers(payload)
        except ValueError as err:
            _LOGGER.warning(
                "Unexpected reply from %s (%s), body: %.300s", url, err, body
            )
            return "unexpected_payload"
        return None
