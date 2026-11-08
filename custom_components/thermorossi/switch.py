"""Switch entity for the Thermorossi integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ACTIVE_STATES, PARAMS_FINAL_CLEANING_STATE, PARAMS_OFF_STATE
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
        if self.coordinator.is_params:
            # As on the official page: anything but OFF can be switched off
            # (alarm states included, that is how they are acknowledged).
            return self.coordinator.status_code != PARAMS_OFF_STATE
        return self.coordinator.status_code in ACTIVE_STATES or self.in_error

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.in_error:
            raise HomeAssistantError(
                "The stove is in error stop: turn it off to acknowledge the alarm first"
            )
        if self.coordinator.is_params:
            await self._params_toggle(turn_on=True)
        elif not await self.coordinator.async_turn_on():
            raise HomeAssistantError("Failed to turn on the stove")

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.coordinator.is_params:
            await self._params_toggle(turn_on=False)
        elif not await self.coordinator.async_turn_off():
            raise HomeAssistantError("Failed to turn off the stove")

    async def _params_toggle(self, turn_on: bool) -> None:
        """Send the on/off toggle only when it moves the stove the requested way."""
        async with self.coordinator.toggle_lock:
            # A toggle sent a moment ago may not show in the state yet: sending
            # another one would undo it.
            pending = self.coordinator.toggle_pending_turn_on
            if pending is not None:
                if pending == turn_on:
                    return
                raise HomeAssistantError(
                    f"The stove is still processing the previous "
                    f"{'on' if pending else 'off'} command: try again in a few seconds"
                )
            status = self.coordinator.status_code
            if status is None:
                raise HomeAssistantError("The stove state is unknown")
            if turn_on and status == PARAMS_FINAL_CLEANING_STATE:
                raise HomeAssistantError(
                    "The stove is finishing its final cleaning: wait until it is off"
                )
            # Off is reached through the final cleaning: already on the way there.
            already_there = (
                status != PARAMS_OFF_STATE
                if turn_on
                else status in (PARAMS_OFF_STATE, PARAMS_FINAL_CLEANING_STATE)
            )
            if already_there:
                return
            if not await self.coordinator.async_toggle_power(turn_on):
                raise HomeAssistantError(
                    f"Failed to turn {'on' if turn_on else 'off'} the stove"
                )
