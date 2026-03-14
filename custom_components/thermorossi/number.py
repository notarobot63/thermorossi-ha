"""Number entities (fire level, fan speed) for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACTIVE_STATES, REG_FIRE_LEVEL, REG_FAN_SPEED, REG_STATUS, SET_KEY
from .coordinator import ThermorossiCoordinator

SET_REG_FIRE = 12
SET_REG_FAN = 13


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ThermorossiCoordinator = entry.runtime_data
    async_add_entities([
        ThermorossiFireLevelNumber(coordinator, entry),
        ThermorossiFanSpeedNumber(coordinator, entry),
    ])


class ThermorossiBaseNumber(CoordinatorEntity[ThermorossiCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {("thermorossi", entry.data["host"])},
            "name": "Thermorossi",
            "manufacturer": "Thermorossi",
            "model": "WiNET",
        }


class ThermorossiFireLevelNumber(ThermorossiBaseNumber):
    _attr_name = "Niveau de puissance"
    _attr_icon = "mdi:fire"
    _attr_native_min_value = 1
    _attr_native_max_value = 5
    _attr_native_step = 1

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fire_level_set"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get(REG_FIRE_LEVEL, 0)
        return float(val) if val > 0 else 1.0

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator._send_command_reg(SET_REG_FIRE, int(value))
        await self.coordinator.async_request_refresh()


class ThermorossiFanSpeedNumber(ThermorossiBaseNumber):
    _attr_name = "Vitesse ventilateur"
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
        await self.coordinator._send_command_reg(SET_REG_FAN, int(value))
        await self.coordinator.async_request_refresh()
