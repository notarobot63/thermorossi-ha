"""Thermorossi WiNET integration for Home Assistant."""
from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import ThermorossiConfigEntry, ThermorossiCoordinator

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR, Platform.NUMBER]


def _migrate_device_identifier(hass: HomeAssistant, entry: ThermorossiConfigEntry) -> None:
    """Re-key the device from the host (pre-1.2) to the entry id.

    Keying on the host would create a new device whenever the stove's IP is
    reconfigured.
    """
    dev_reg = dr.async_get(hass)
    old = dev_reg.async_get_device(identifiers={(DOMAIN, entry.data[CONF_HOST])})
    if old is None or old.config_entries != {entry.entry_id}:
        return
    if dev_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)}) is None:
        dev_reg.async_update_device(old.id, new_identifiers={(DOMAIN, entry.entry_id)})


async def async_setup_entry(hass: HomeAssistant, entry: ThermorossiConfigEntry) -> bool:
    """Set up Thermorossi from a config entry."""
    _migrate_device_identifier(hass, entry)

    coordinator = ThermorossiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThermorossiConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
