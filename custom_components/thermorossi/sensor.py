"""Sensors for the Thermorossi integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    REG_STATUS,
    REG_SET_TEMP,
    REG_AIR_TEMP,
    REG_FIRE_LEVEL,
    REG_FAN_SPEED,
    STATUS_CODES,
    STATUS_LABELS,
    TEMP_MUL,
    TEMP_OFFSET,
)
from .coordinator import ThermorossiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ThermorossiCoordinator = entry.runtime_data
    async_add_entities([
        ThermorossiStatusSensor(coordinator, entry),
        ThermorossiSetTempSensor(coordinator, entry),
        ThermorossiAirTempSensor(coordinator, entry),
        ThermorossiFireLevelSensor(coordinator, entry),
        ThermorossiFanSpeedSensor(coordinator, entry),
    ])


class ThermorossiBaseSensor(CoordinatorEntity[ThermorossiCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {("thermorossi", entry.data["host"])},
            "name": f"Thermorossi ({entry.data['host']})",
            "manufacturer": "Thermorossi",
            "model": "WiNET",
        }


class ThermorossiStatusSensor(ThermorossiBaseSensor):
    _attr_name = "État"
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        raw = coordinator_get(self.coordinator, REG_STATUS)
        if raw is None:
            return "Inconnu"
        code = STATUS_CODES.get(raw & 0xFF, "unknown")
        return STATUS_LABELS.get(code, f"État {raw & 0xFF}")

    @property
    def icon(self) -> str:
        raw = coordinator_get(self.coordinator, REG_STATUS)
        if raw is None:
            return "mdi:fire-off"
        code = (raw & 0xFF)
        if code == 8:
            return "mdi:fire-alert"
        if code in (2, 3, 4, 5):
            return "mdi:fire"
        return "mdi:fire-off"


class ThermorossiSetTempSensor(ThermorossiBaseSensor):
    _attr_name = "Consigne température"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_set_temp"

    @property
    def native_value(self) -> float | None:
        raw = coordinator_get(self.coordinator, REG_SET_TEMP)
        if raw is None:
            return None
        return round(raw * TEMP_MUL + TEMP_OFFSET, 1)


class ThermorossiAirTempSensor(ThermorossiBaseSensor):
    _attr_name = "Température ambiante"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_air_temp"

    @property
    def available(self) -> bool:
        raw = coordinator_get(self.coordinator, REG_AIR_TEMP)
        return raw is not None and raw != 0

    @property
    def native_value(self) -> float | None:
        raw = coordinator_get(self.coordinator, REG_AIR_TEMP)
        if raw is None or raw == 0:
            return None
        return round(raw * TEMP_MUL + TEMP_OFFSET, 1)


class ThermorossiFireLevelSensor(ThermorossiBaseSensor):
    _attr_name = "Niveau de puissance"
    _attr_icon = "mdi:speedometer"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fire_level"

    @property
    def native_value(self) -> int | None:
        return coordinator_get(self.coordinator, REG_FIRE_LEVEL)


class ThermorossiFanSpeedSensor(ThermorossiBaseSensor):
    _attr_name = "Vitesse ventilateur"
    _attr_icon = "mdi:fan"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fan_speed"

    @property
    def native_value(self) -> int | None:
        return coordinator_get(self.coordinator, REG_FAN_SPEED)


def coordinator_get(coordinator: ThermorossiCoordinator, index: int) -> int | None:
    if coordinator.data is None:
        return None
    return coordinator.data.get(index)
