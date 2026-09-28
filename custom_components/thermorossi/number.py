"""Number entities (fire level, fan speed, setpoint) for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    REG_FAN_SPEED,
    REG_FIRE_LEVEL,
    REG_SET_TEMP,
    TEMP_MUL,
    TEMP_OFFSET,
)
from .coordinator import ThermorossiConfigEntry
from .entity import ThermorossiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermorossiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([
        ThermorossiFireLevelNumber(coordinator, entry, "fire_level_set"),
        ThermorossiFanSpeedNumber(coordinator, entry, "fan_speed_set"),
        ThermorossiSetTempNumber(coordinator, entry, "set_temp_set"),
    ])


class ThermorossiBaseNumber(ThermorossiEntity, NumberEntity):
    _attr_mode = NumberMode.SLIDER
    _register: int
    _error_message: str

    @property
    def available(self) -> bool:
        # Disable sliders when the stove is in error state
        return super().available and not self.in_error

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.get(self._register)
        return None if raw is None else float(raw)

    def _to_raw(self, value: float) -> int:
        return int(value)

    async def async_set_native_value(self, value: float) -> None:
        if not await self.coordinator.async_set_register(self._register, self._to_raw(value)):
            raise HomeAssistantError(self._error_message)


class ThermorossiFireLevelNumber(ThermorossiBaseNumber):
    _attr_translation_key = "fire_level"
    _attr_native_min_value = 0
    _attr_native_max_value = 5
    _attr_native_step = 1
    _register = REG_FIRE_LEVEL
    _error_message = "Failed to set fire level on the stove"


class ThermorossiFanSpeedNumber(ThermorossiBaseNumber):
    _attr_translation_key = "fan_speed"
    _attr_native_min_value = 1
    _attr_native_max_value = 6
    _attr_native_step = 1
    _register = REG_FAN_SPEED
    _error_message = "Failed to set fan speed on the stove"


class ThermorossiSetTempNumber(ThermorossiBaseNumber):
    """Target room temperature (reg[15], raw = (celsius + 18) / 0.25)."""

    _attr_translation_key = "set_temperature"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 7
    _attr_native_max_value = 30
    _attr_native_step = 0.5
    _register = REG_SET_TEMP
    _error_message = "Failed to set target temperature on the stove"

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.get(REG_SET_TEMP)
        if raw is None:
            return None
        return round(raw * TEMP_MUL + TEMP_OFFSET, 1)

    def _to_raw(self, value: float) -> int:
        return round((value - TEMP_OFFSET) / TEMP_MUL)
