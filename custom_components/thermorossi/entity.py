"""Common base entity for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThermorossiCoordinator


class ThermorossiEntity(CoordinatorEntity[ThermorossiCoordinator]):
    """Base entity: wires up coordinator + device_info for every platform."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["host"])},
            name="Thermorossi",
            manufacturer="Thermorossi",
            model="WiNET",
        )
