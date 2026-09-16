"""Number entities (fire level, fan speed) for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ERROR_STATE,
    REG_FAN_SPEED,
    REG_FIRE_LEVEL,
    REG_SET_TEMP,
    REG_STATUS,
    TEMP_MUL,
    TEMP_OFFSET,
)
from .coordinator import ThermorossiCoordinator
from .entity import ThermorossiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ThermorossiCoordinator = entry.runtime_data
    async_add_entities([
        ThermorossiFireLevelNumber(coordinator, entry),
        ThermorossiFanSpeedNumber(coordinator, entry),
        ThermorossiSetTempNumber(coordinator, entry),
    ])


class ThermorossiBaseNumber(ThermorossiEntity, NumberEntity):
    _attr_mode = NumberMode.SLIDER

    @property
    def available(self) -> bool:
        if not super().available or self.coordinator.data is None:
            return False
        # Disable slider when stove is in error state, same as the switch
        raw = self.coordinator.data.get(REG_STATUS, 1)
        return (raw & 0xFF) != ERROR_STATE


class ThermorossiFireLevelNumber(ThermorossiBaseNumber):
    _attr_translation_key = "fire_level"
    _attr_icon = "mdi:fire"
    _attr_native_min_value = 0
    _attr_native_max_value = 5
    _attr_native_step = 1

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fire_level_set"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return float(self.coordinator.data.get(REG_FIRE_LEVEL, 0))

    async def async_set_native_value(self, value: float) -> None:
        if not await self.coordinator.async_set_register(REG_FIRE_LEVEL, int(value)):
            raise HomeAssistantError("Failed to set fire level on the stove")
        await self.coordinator.async_request_refresh()


class ThermorossiFanSpeedNumber(ThermorossiBaseNumber):
    _attr_translation_key = "fan_speed"
    _attr_icon = "mdi:fan"
    _attr_native_min_value = 1
    _attr_native_max_value = 6
    _attr_native_step = 1

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fan_speed_set"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return float(self.coordinator.data.get(REG_FAN_SPEED, 1))

    async def async_set_native_value(self, value: float) -> None:
        if not await self.coordinator.async_set_register(REG_FAN_SPEED, int(value)):
            raise HomeAssistantError("Failed to set fan speed on the stove")
        await self.coordinator.async_request_refresh()


class ThermorossiSetTempNumber(ThermorossiBaseNumber):
    """Target room temperature (reg[15], raw = (celsius + 18) / 0.25)."""

    _attr_translation_key = "set_temperature"
    _attr_icon = "mdi:thermometer"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 7
    _attr_native_max_value = 30
    _attr_native_step = 0.5

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_set_temp_set"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        raw = self.coordinator.data.get(REG_SET_TEMP)
        if raw is None:
            return None
        return round(raw * TEMP_MUL + TEMP_OFFSET, 1)

    async def async_set_native_value(self, value: float) -> None:
        raw = round((value - TEMP_OFFSET) / TEMP_MUL)
        if not await self.coordinator.async_set_register(REG_SET_TEMP, raw):
            raise HomeAssistantError("Failed to set target temperature on the stove")
        await self.coordinator.async_request_refresh()
