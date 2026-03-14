"""Binary sensors for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ERROR_STATE, REG_PELLET, REG_STATUS
from .coordinator import ThermorossiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ThermorossiCoordinator = entry.runtime_data
    async_add_entities([
        ThermorossiErrorSensor(coordinator, entry),
        ThermorossiPelletSensor(coordinator, entry),
    ])


class ThermorossiBaseBinarySensor(
    CoordinatorEntity[ThermorossiCoordinator], BinarySensorEntity
):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {("thermorossi", entry.data["host"])},
            "name": f"Thermorossi ({entry.data['host']})",
            "manufacturer": "Thermorossi",
            "model": "WiNET",
        }


class ThermorossiErrorSensor(ThermorossiBaseBinarySensor):
    _attr_name = "Erreur"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_error"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        raw = self.coordinator.data.get(REG_STATUS, 1)
        return (raw & 0xFF) == ERROR_STATE


class ThermorossiPelletSensor(ThermorossiBaseBinarySensor):
    _attr_name = "Pellets insuffisants"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:grain"

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pellet"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.get(REG_PELLET, 0) != 0
