"""Binary sensors for the Thermorossi integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import REG_FLAGS, REG_PELLET
from .coordinator import ThermorossiConfigEntry
from .entity import ThermorossiEntity
from .parsing import active_alarm_bits


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermorossiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.is_params:
        async_add_entities([
            ThermorossiErrorSensor(coordinator, entry, "error"),
            ThermorossiAlarmSensor(coordinator, entry, "alarm"),
        ])
        return
    async_add_entities([
        ThermorossiErrorSensor(coordinator, entry, "error"),
        ThermorossiAlarmSensor(coordinator, entry, "alarm"),
        ThermorossiPelletSensor(coordinator, entry, "pellet"),
        ThermorossiChronoSensor(coordinator, entry, "chrono"),
    ])


class ThermorossiBaseBinarySensor(ThermorossiEntity, BinarySensorEntity):
    pass


class ThermorossiErrorSensor(ThermorossiBaseBinarySensor):
    """Active when the stove is stopped on an alarm (reg[6]==8, or params state 8/9)."""
    _attr_translation_key = "error_stop"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.in_error


class ThermorossiAlarmSensor(ThermorossiBaseBinarySensor):
    """Active when any alarm bit is set (reg[8]+reg[9], or param 3 in alarm states)."""
    _attr_translation_key = "alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.coordinator.alarm_code != 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        code = self.coordinator.alarm_code
        codes = self.coordinator.alarm_codes
        active = [codes.get(bit, f"alarm_bit_{bit}") for bit in active_alarm_bits(code)]
        return {"active_alarms": active, "code": code}


class ThermorossiPelletSensor(ThermorossiBaseBinarySensor):
    """Active when the pellet reserve sensor reports empty (reg[10] != 0)."""
    _attr_translation_key = "pellets_low"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.get(REG_PELLET))


class ThermorossiChronoSensor(ThermorossiBaseBinarySensor):
    """Active when the chronothermostat schedule is enabled (reg[7] bit 0)."""
    _attr_translation_key = "chrono"

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.get(REG_FLAGS) or 0) & 0x1)
