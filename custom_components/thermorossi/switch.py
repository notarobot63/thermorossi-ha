"""Switch entity for the Thermorossi integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ACTIVE_STATES
from .coordinator import ThermorossiConfigEntry
from .entity import ThermorossiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermorossiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([ThermorossiSwitch(entry.runtime_data, entry, "switch")])


class ThermorossiSwitch(ThermorossiEntity, SwitchEntity):
    _attr_translation_key = "stove"

    @property
    def is_on(self) -> bool:
        # The STOP error state is reported as "on": the stove has not been
        # acknowledged yet, and switching off (the same as pressing the power
        # button on Micronova boards) is what clears it.
        return self.coordinator.status_code in ACTIVE_STATES or self.in_error

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.in_error:
            raise HomeAssistantError(
                "The stove is in error stop: turn it off to acknowledge the alarm first"
            )
        if not await self.coordinator.async_turn_on():
            raise HomeAssistantError("Failed to turn on the stove")

    async def async_turn_off(self, **kwargs: Any) -> None:
        if not await self.coordinator.async_turn_off():
            raise HomeAssistantError("Failed to turn off the stove")
