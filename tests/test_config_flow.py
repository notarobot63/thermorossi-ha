"""Tests for the Thermorossi config flow."""
from __future__ import annotations

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.thermorossi.const import DOMAIN

from .conftest import GET_URL, HOST, make_registers


async def _start(hass: HomeAssistant, host: str) -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host}
    )


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(GET_URL, json=make_registers())
    result = await _start(hass, f"  {HOST} ")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == HOST


@pytest.mark.parametrize(
    ("mock_kwargs", "error"),
    [
        ({"exc": aiohttp.ClientConnectionError()}, "cannot_connect"),
        ({"exc": TimeoutError()}, "cannot_connect"),
        ({"status": 404, "text": "<html>Not found</html>"}, "http_error"),
        ({"text": "<html>router login</html>"}, "not_json"),
        ({"json": {"other": 1}}, "unexpected_payload"),
        ({"json": {"registers": [[0, "x"]]}}, "unexpected_payload"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, aioclient_mock, mock_kwargs, error, caplog
) -> None:
    aioclient_mock.post(GET_URL, **mock_kwargs)
    result = await _start(hass, HOST)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    # Every failure must leave something in the logs to diagnose it
    assert GET_URL in caplog.text


async def test_user_flow_invalid_host(hass: HomeAssistant) -> None:
    result = await _start(hass, "not a host!")
    assert result["errors"] == {"base": "invalid_host"}


async def test_user_flow_ipv6(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post("http://[fd00::10]/ajax/get-registers", json=make_registers())
    result = await _start(hass, "[FD00::10]")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "fd00::10"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    result = await _start(hass, HOST)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(hass: HomeAssistant, aioclient_mock, config_entry) -> None:
    aioclient_mock.post(GET_URL, json=make_registers())
    aioclient_mock.post("http://192.168.1.200/ajax/get-registers", json=make_registers())
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.200"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "192.168.1.200"
    assert config_entry.unique_id == "192.168.1.200"
    assert config_entry.title == "Thermorossi (192.168.1.200)"
