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
    old = _get_entry_device(dev_reg, (DOMAIN, entry.data[CONF_HOST]), entry.entry_id)
    if old is None:
        return
    if _get_entry_device(dev_reg, (DOMAIN, entry.entry_id), entry.entry_id) is None:
        dev_reg.async_update_device(old.id, new_identifiers={(DOMAIN, entry.entry_id)})


def _get_entry_device(
    dev_reg: dr.DeviceRegistry, identifier: tuple[str, str], entry_id: str
) -> dr.DeviceEntry | None:
    """Return the device with this identifier, owned by this config entry only."""
    # async_get_device is deprecated (breaks in HA 2027.8) but its replacement
    # does not exist in older supported releases.
    # shortcut: fallback for old HA, drop it when hacs.json requires a release with
    # async_get_device_by_identifier.
    if hasattr(dev_reg, "async_get_device_by_identifier"):
        return dev_reg.async_get_device_by_identifier(identifier, entry_id)
    device = dev_reg.async_get_device(identifiers={identifier})
    if device is None or device.config_entries != {entry_id}:
        return None
    return device


async def async_setup_entry(hass: HomeAssistant, entry: ThermorossiConfigEntry) -> bool:
    """Set up Thermorossi from a config entry."""
    _migrate_device_identifier(hass, entry)

    coordinator = ThermorossiCoordinator(hass, entry)
    # Attached before the first refresh so diagnostics (raw replies, firmware)
    # stay available when setup fails on an unsupported firmware.
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThermorossiConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
