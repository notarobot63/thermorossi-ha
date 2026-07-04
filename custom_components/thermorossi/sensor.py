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

from .const import (
    REG_STATUS,
    REG_SET_TEMP,
    REG_AIR_TEMP,
    REG_FIRE_LEVEL,
    REG_FAN_SPEED,
    REG_FLUE_TEMP,
    REG_RTC,
    STATUS_CODES,
    ALARM_CODES,
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
        ThermorossiStatusSensor(coordinator, entry),
        ThermorossiSetTempSensor(coordinator, entry),
        ThermorossiAirTempSensor(coordinator, entry),
        ThermorossiFlueTempSensor(coordinator, entry),
        ThermorossiFireLevelSensor(coordinator, entry),
        ThermorossiFanSpeedSensor(coordinator, entry),
        ThermorossiAlarmMessageSensor(coordinator, entry),
        ThermorossiRtcSensor(coordinator, entry),
    ])


class ThermorossiBaseSensor(ThermorossiEntity, SensorEntity):
    pass


class ThermorossiStatusSensor(ThermorossiBaseSensor):
    _attr_translation_key = "status"

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str | None:
        raw = coordinator_get(self.coordinator, REG_STATUS)
        if raw is None:
            return None
        return STATUS_CODES.get(raw & 0xFF, "unknown")

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
    _attr_translation_key = "set_temperature"
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
    _attr_translation_key = "air_temperature"
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
    _attr_translation_key = "fire_level"
    _attr_icon = "mdi:speedometer"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fire_level"

    @property
    def native_value(self) -> int | None:
        return coordinator_get(self.coordinator, REG_FIRE_LEVEL)


class ThermorossiFanSpeedSensor(ThermorossiBaseSensor):
    _attr_translation_key = "fan_speed"
    _attr_icon = "mdi:fan"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fan_speed"

    @property
    def native_value(self) -> int | None:
        return coordinator_get(self.coordinator, REG_FAN_SPEED)


class ThermorossiAlarmMessageSensor(ThermorossiBaseSensor):
    """Shows the first active alarm message, or 'OK' when no alarm."""
    _attr_translation_key = "alarm_message"
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_alarm_msg"

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        code = self.coordinator.alarm_code
        if code == 0:
            return "ok"
        for bit in range(32):
            if code & (1 << bit):
                return ALARM_CODES.get(bit, "unknown")
        return "ok"


class ThermorossiFlueTempSensor(ThermorossiBaseSensor):
    """Flue gas temperature (reg[21], direct °C value)."""
    _attr_translation_key = "flue_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_flue_temp"

    @property
    def available(self) -> bool:
        raw = coordinator_get(self.coordinator, REG_FLUE_TEMP)
        return raw is not None and raw != 0

    @property
    def native_value(self) -> int | None:
        raw = coordinator_get(self.coordinator, REG_FLUE_TEMP)
        if raw is None or raw == 0:
            return None
        return raw


_RTC_DAYS = ["", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


class ThermorossiRtcSensor(ThermorossiBaseSensor):
    """Internal RTC clock (reg[22]): day bits[13:11], hour bits[10:6], minute bits[5:0]."""
    _attr_translation_key = "rtc_clock"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: ThermorossiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rtc"

    @property
    def native_value(self) -> str | None:
        raw = coordinator_get(self.coordinator, REG_RTC)
        if raw is None:
            return None
        day = (raw >> 11) & 0x7
        hour = (raw >> 6) & 0x1F
        minute = raw & 0x3F
        day_label = _RTC_DAYS[day] if 1 <= day <= 7 else "?"
        return f"{day_label} {hour:02d}:{minute:02d}"


def coordinator_get(coordinator: ThermorossiCoordinator, index: int) -> int | None:
    if coordinator.data is None:
        return None
    return coordinator.data.get(index)
