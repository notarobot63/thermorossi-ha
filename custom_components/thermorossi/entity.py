"""Common base entity for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ERROR_STATE
from .coordinator import ThermorossiConfigEntry, ThermorossiCoordinator


class ThermorossiEntity(CoordinatorEntity[ThermorossiCoordinator]):
    """Base entity: wires up coordinator + device_info for every platform."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ThermorossiCoordinator, entry: ThermorossiConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Thermorossi",
            manufacturer="Thermorossi",
            model="WiNET",
            configuration_url=f"{coordinator.base_url}/management.html",
        )

    @property
    def in_error(self) -> bool:
        """Return True when the stove is in the STOP error state."""
        return self.coordinator.status_code == ERROR_STATE
