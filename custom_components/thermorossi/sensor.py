"""Sensors for the Thermorossi integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    REG_SET_TEMP,
    REG_AIR_TEMP,
    REG_FIRE_LEVEL,
    REG_FAN_SPEED,
    REG_FLUE_TEMP,
    REG_RTC,
    STATUS_CODES,
    STATUS_OPTIONS,
    ALARM_CODES,
    ALARM_OPTIONS,
    TEMP_MUL,
    TEMP_OFFSET,
)
from .coordinator import ThermorossiConfigEntry
from .entity import ThermorossiEntity
from .parsing import active_alarm_bits, decode_rtc


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermorossiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([
        ThermorossiStatusSensor(coordinator, entry, "status"),
        ThermorossiSetTempSensor(coordinator, entry, "set_temp"),
        ThermorossiAirTempSensor(coordinator, entry, "air_temp"),
        ThermorossiFlueTempSensor(coordinator, entry, "flue_temp"),
        ThermorossiFireLevelSensor(coordinator, entry, "fire_level"),
        ThermorossiFanSpeedSensor(coordinator, entry, "fan_speed"),
        ThermorossiAlarmMessageSensor(coordinator, entry, "alarm_msg"),
        ThermorossiRtcSensor(coordinator, entry, "rtc"),
    ])


class ThermorossiBaseSensor(ThermorossiEntity, SensorEntity):
    pass


class ThermorossiStatusSensor(ThermorossiBaseSensor):
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS

    @property
    def native_value(self) -> str | None:
        code = self.coordinator.status_code
        if code is None:
            return None
        return STATUS_CODES.get(code, "unknown")


class ThermorossiSetTempSensor(ThermorossiBaseSensor):
    """Read-only duplicate of the setpoint number entity (disabled by default)."""
    _attr_translation_key = "set_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.get(REG_SET_TEMP)
        if raw is None:
            return None
        return round(raw * TEMP_MUL + TEMP_OFFSET, 1)


class ThermorossiAirTempSensor(ThermorossiBaseSensor):
    _attr_translation_key = "air_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def available(self) -> bool:
        # raw 0 means no room control module is installed
        return super().available and bool(self.coordinator.get(REG_AIR_TEMP))

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.get(REG_AIR_TEMP)
        if not raw:
            return None
        return round(raw * TEMP_MUL + TEMP_OFFSET, 1)


class ThermorossiFireLevelSensor(ThermorossiBaseSensor):
    """Read-only duplicate of the power level number entity (disabled by default)."""
    _attr_translation_key = "fire_level"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> int | None:
        return self.coordinator.get(REG_FIRE_LEVEL)


class ThermorossiFanSpeedSensor(ThermorossiBaseSensor):
    """Read-only duplicate of the fan speed number entity (disabled by default)."""
    _attr_translation_key = "fan_speed"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> int | None:
        return self.coordinator.get(REG_FAN_SPEED)


class ThermorossiAlarmMessageSensor(ThermorossiBaseSensor):
    """Shows the first active alarm message, or 'ok' when no alarm."""
    _attr_translation_key = "alarm_message"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ALARM_OPTIONS

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        bits = active_alarm_bits(self.coordinator.alarm_code)
        if not bits:
            return "ok"
        return ALARM_CODES.get(bits[0], "unknown")


class ThermorossiFlueTempSensor(ThermorossiBaseSensor):
    """Flue gas temperature (reg[21], direct °C value)."""
    _attr_translation_key = "flue_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.get(REG_FLUE_TEMP))

    @property
    def native_value(self) -> int | None:
        return self.coordinator.get(REG_FLUE_TEMP) or None


class ThermorossiRtcSensor(ThermorossiBaseSensor):
    """Internal RTC clock (reg[22]): state is HH:MM, weekday (1=Monday) as attribute."""
    _attr_translation_key = "rtc_clock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        raw = self.coordinator.get(REG_RTC)
        if raw is None:
            return None
        _, hour, minute = decode_rtc(raw)
        hour_label = f"{hour:02d}" if hour < 24 else "??"
        minute_label = f"{minute:02d}" if minute < 60 else "??"
        return f"{hour_label}:{minute_label}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        raw = self.coordinator.get(REG_RTC)
        if raw is None:
            return None
        day = decode_rtc(raw)[0]
        return {"weekday": day if 1 <= day <= 7 else None}
