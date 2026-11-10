"""DataUpdateCoordinator for the Thermorossi integration."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any, NoReturn

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
    API_GET_STATUS,
    API_SET_REGISTER,
    API_HEADERS,
    GET_PAYLOAD,
    GET_CHRONO_PAYLOAD,
    CHRONO_REFRESH_INTERVAL,
    CMD_ON,
    CMD_OFF,
    SET_KEY,
    SET_REG_ID,
    REG_ALARM_LSB,
    REG_ALARM_MSB,
    REG_STATUS,
    REQUIRED_REGISTERS,
    ALARM_CODES,
    ALARM_OPTIONS,
    ERROR_STATE,
    STATUS_CODES,
    STATUS_OPTIONS,
    DIALECT_PARAMS,
    DIALECT_REGISTERS,
    PARAMS_ALARM_CODES,
    PARAMS_ALARM_OPTIONS,
    PARAMS_DEFAULT_CUSTOM,
    PARAMS_DEFAULT_NUM_POWER,
    PARAMS_DEFAULT_TEMP_DIV,
    PARAMS_ERROR_STATES,
    PARAMS_GET_PAYLOAD,
    PARAMS_REQUIRED,
    PARAMS_SETTINGS_PAYLOAD,
    PARAMS_STATUS_CODES,
    PARAMS_STATUS_OPTIONS,
    PARAMS_TOGGLE_GUARD,
    PARAMS_TOGGLE_PAYLOAD,
    PARAM_ALARM,
    PARAM_STATUS,
)
from .parsing import (
    build_base_url,
    check_register_layout,
    compute_alarm_code,
    detect_dialect,
    parse_registers,
    positive_number,
)

_LOGGER = logging.getLogger(__name__)

type ThermorossiConfigEntry = ConfigEntry[ThermorossiCoordinator]


class ThermorossiCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Polls the Thermorossi WiNET API and exposes register data."""

    config_entry: ThermorossiConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ThermorossiConfigEntry) -> None:
        self.host: str = entry.data[CONF_HOST]
        self.base_url = build_base_url(self.host)
        self._fast_poll_cancels: list[Callable[[], None]] = []
        self._chrono_registers: dict[int, int] = {}
        self._chrono_fetched_at: float | None = None
        self.firmware: str | None = None
        # API dialect of the module, known after the first successful read
        self.dialect: str | None = None
        # "params" dialect: scale factors sent along with the values
        self.temp_div: float = 1
        self.set_temp_div: float = 1
        self.num_power: int = PARAMS_DEFAULT_NUM_POWER
        self._toggle_sent_at: float | None = None
        self._toggle_status: int | None = None
        self._toggle_turn_on: bool | None = None
        # Held from the state check to the end of the toggle, so two
        # simultaneous calls cannot both decide to send it.
        self.toggle_lock = asyncio.Lock()
        self._warned_custom = False
        self._params_settings: dict[str, Any] | None = None
        # Raw get-registers replies, by request payload, for diagnostics
        self.last_payloads: dict[str, Any] = {}
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
    def is_params(self) -> bool:
        """Return True if the module speaks the "params" dialect (firmware 0.79)."""
        return self.dialect == DIALECT_PARAMS

    @property
    def status_code(self) -> int | None:
        """Return the stove status code, or None if unknown."""
        if self.is_params:
            return self.get(PARAM_STATUS)
        raw = self.get(REG_STATUS)
        return None if raw is None else raw & 0xFF

    @property
    def status_codes(self) -> dict[int, str]:
        """Return the status code -> state key table of this module."""
        return PARAMS_STATUS_CODES if self.is_params else STATUS_CODES

    @property
    def status_options(self) -> list[str]:
        """Return every state key the status sensor can take on this module."""
        return PARAMS_STATUS_OPTIONS if self.is_params else STATUS_OPTIONS

    @property
    def in_error(self) -> bool:
        """Return True when the stove is stopped on an alarm."""
        if self.is_params:
            return self.status_code in PARAMS_ERROR_STATES
        return self.status_code == ERROR_STATE

    @property
    def alarm_code(self) -> int:
        """Return the alarm bit field (0 = no alarm)."""
        if self.is_params:
            # The bit field briefly flickers during ignition; the official page
            # only shows it once the stove is stopped on an alarm.
            return (self.get(PARAM_ALARM) or 0) if self.in_error else 0
        return compute_alarm_code(
            self.get(REG_ALARM_MSB) or 0, self.get(REG_ALARM_LSB) or 0
        )

    @property
    def alarm_codes(self) -> dict[int, str]:
        """Return the alarm bit -> translation key table of this module."""
        return PARAMS_ALARM_CODES if self.is_params else ALARM_CODES

    @property
    def alarm_options(self) -> list[str]:
        """Return every state key the alarm message sensor can take on this module."""
        return PARAMS_ALARM_OPTIONS if self.is_params else ALARM_OPTIONS

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

    async def async_get_module_status(self) -> dict[str, Any]:
        """Read the WiNET module status (network, firmware version)."""
        status = await self._post(API_GET_STATUS, "")
        if not isinstance(status, dict):
            raise ValueError(f"unexpected get-status reply: {status!r}")
        return status

    async def _firmware_version(self) -> str:
        """Return the module firmware version, best effort (only used in messages)."""
        if self.firmware is None:
            try:
                self.firmware = str((await self.async_get_module_status())["fwVer"])
            except (aiohttp.ClientError, TimeoutError, ValueError, KeyError) as err:
                _LOGGER.debug("Could not read the WiNET firmware version: %s", err)
                return "unknown"
        return self.firmware

    async def _read(self, payload: str) -> Any:
        """POST a get-registers payload and return the decoded reply."""
        try:
            body = await self._post(API_GET_REGISTERS, payload)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Connection error to stove ({self.host}): {err}") from err
        except ValueError as err:
            raise UpdateFailed(f"Invalid response from stove ({self.host}): {err}") from err
        self.last_payloads[payload] = body
        return body

    async def _unsupported(self, err: ValueError) -> UpdateFailed:
        return UpdateFailed(
            f"Unsupported data from stove ({self.host}, WiNET firmware "
            f"{await self._firmware_version()}): {err}"
        )

    async def _parse(
        self, body: Any, field: str, required: tuple[int, ...] = ()
    ) -> dict[int, int]:
        try:
            registers = parse_registers(body, field)
            check_register_layout(registers, required)
        except ValueError as err:
            raise await self._unsupported(err) from err
        return registers

    async def _fetch_registers(
        self, payload: str, required: tuple[int, ...] = ()
    ) -> dict[int, int]:
        """Read one register category from a "registers" dialect module."""
        return await self._parse(await self._read(payload), DIALECT_REGISTERS, required)

    async def _async_update_data(self) -> dict[int, int]:
        """Fetch the runtime values, in the dialect the module speaks."""
        if self.is_params:
            body = await self._read(PARAMS_GET_PAYLOAD)
            if isinstance(body, dict) and isinstance(body.get(DIALECT_REGISTERS), list):
                # Firmware changed while running: the entities no longer match.
                self._dialect_changed()
            return await self._update_params(body)

        body = await self._read(GET_PAYLOAD)
        try:
            dialect = detect_dialect(body)
        except ValueError as err:
            raise await self._unsupported(err) from err
        if dialect == DIALECT_PARAMS:
            if self.dialect is not None:
                self._dialect_changed()
            self.dialect = DIALECT_PARAMS
            # The official page reads category 2: category 1 may come back empty.
            return await self._update_params(await self._read(PARAMS_GET_PAYLOAD))
        return await self._update_registers(body)

    async def _update_registers(self, body: Any) -> dict[int, int]:
        """Decode the runtime registers, plus the weekly schedule when it is due."""
        registers = await self._parse(body, DIALECT_REGISTERS, REQUIRED_REGISTERS)
        self.dialect = DIALECT_REGISTERS

        now = time.monotonic()
        if (
            self._chrono_fetched_at is None
            or now - self._chrono_fetched_at >= CHRONO_REFRESH_INTERVAL
        ):
            # The schedule is secondary: a failed read keeps the last known
            # program and must not make every other entity unavailable.
            try:
                self._chrono_registers = await self._fetch_registers(GET_CHRONO_PAYLOAD)
                self._chrono_fetched_at = now
            except UpdateFailed as err:
                _LOGGER.debug("Could not read the weekly schedule: %s", err)

        return {**self._chrono_registers, **registers}

    async def _update_params(self, body: Any) -> dict[int, int]:
        """Decode a "params" dialect reply and its scale factors."""
        params = await self._parse(body, DIALECT_PARAMS, PARAMS_REQUIRED)
        settings = body if "tempDiv" in body else await self._read_params_settings()
        self.temp_div = positive_number(settings, "tempDiv", PARAMS_DEFAULT_TEMP_DIV)
        self.set_temp_div = positive_number(
            settings, "setTempDiv", PARAMS_DEFAULT_TEMP_DIV
        )
        self.num_power = max(
            1, int(positive_number(settings, "numPower", PARAMS_DEFAULT_NUM_POWER))
        )
        custom = settings.get("custom")
        if custom not in (None, PARAMS_DEFAULT_CUSTOM) and not self._warned_custom:
            self._warned_custom = True
            _LOGGER.warning(
                "Stove (%s) reports WiNET customization code %s: only the default "
                "code %s has been decoded, states and alarms may be named wrongly. "
                "Please open an issue with a recording of the module's web page",
                self.host, custom, PARAMS_DEFAULT_CUSTOM,
            )
        return params

    async def _read_params_settings(self) -> dict[str, Any]:
        """Read the module settings once, for firmwares that leave them out of the values."""
        if self._params_settings is not None:
            return self._params_settings
        # A failed read fails the update: unscaled values would be shown
        # doubled and a setpoint written at the wrong scale.
        body = await self._read(PARAMS_SETTINGS_PAYLOAD)
        if not isinstance(body, dict):
            # Unreadable: read again at the next poll, default divisors meanwhile
            return {}
        # Kept even without divisors: firmware 0.43 always answers {"result": false}
        self._params_settings = body
        return body

    def _dialect_changed(self) -> NoReturn:
        """The module switched API (firmware update): reload to rebuild the entities."""
        _LOGGER.warning(
            "Stove (%s) changed WiNET API dialect, probably after a firmware update: reloading",
            self.host,
        )
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
        raise UpdateFailed(f"Stove ({self.host}) changed WiNET API dialect")

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

    @property
    def toggle_pending(self) -> bool:
        """Return True if the last on/off toggle has not shown in the state yet."""
        return (
            self._toggle_sent_at is not None
            and time.monotonic() - self._toggle_sent_at < PARAMS_TOGGLE_GUARD
            and self.status_code == self._toggle_status
        )

    @property
    def toggle_pending_turn_on(self) -> bool | None:
        """Return the direction of the pending toggle (True = on), or None."""
        return self._toggle_turn_on if self.toggle_pending else None

    async def async_toggle_power(self, turn_on: bool) -> bool:
        """Send the "params" dialect on/off TOGGLE.

        The caller must hold toggle_lock and have checked the current state:
        the same command turns a stopped stove on and a running stove off.
        """
        try:
            result = await self._post(API_GET_REGISTERS, PARAMS_TOGGLE_PAYLOAD)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.error("Error sending on/off to stove (%s): %s", self.host, err)
            return False
        if not (isinstance(result, dict) and result.get("result") is True):
            _LOGGER.error("Stove (%s) rejected on/off: %r", self.host, result)
            return False
        self._toggle_sent_at = time.monotonic()
        self._toggle_status = self.status_code
        self._toggle_turn_on = turn_on
        self._schedule_fast_poll()
        return True

    async def async_set_register(self, reg_id: int, value: int) -> bool:
        """Write a register, then poll quickly so the new state shows up fast."""
        if self.is_params:
            payload = f"key={SET_KEY}&memory=1&regId={reg_id}&value={value}"
        else:
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
