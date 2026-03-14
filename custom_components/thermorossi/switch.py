"""Switch entity for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACTIVE_STATES, ERROR_STATE, REG_STATUS
from .coordinator import ThermorossiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ThermorossiCoordinator = entry.runtime_data
    async_add_entities([ThermorossiSwitch(coordinator, entry)])


class ThermorossiSwitch(CoordinatorEntity[ThermorossiCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Poêle"
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_switch"
        self._attr_device_info = {
            "identifiers": {("thermorossi", entry.data["host"])},
            "name": f"Thermorossi ({entry.data['host']})",
            "manufacturer": "Thermorossi",
            "model": "WiNET",
        }

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        raw = self.coordinator.data.get(REG_STATUS, 1)
        return (raw & 0xFF) in ACTIVE_STATES

    @property
    def available(self) -> bool:
        if not super().available or self.coordinator.data is None:
            return False
        # Disable switch when stove is in error state
        raw = self.coordinator.data.get(REG_STATUS, 1)
        return (raw & 0xFF) != ERROR_STATE

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_turn_off()
        await self.coordinator.async_request_refresh()
