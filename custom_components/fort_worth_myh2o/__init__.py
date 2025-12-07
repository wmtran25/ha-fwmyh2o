"""
"Fort Worth MyH2O integration for Home Assistant.
"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MyH2ODataUpdateCoordinator

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    # Create coordinator
    coordinator = MyH2ODataUpdateCoordinator(hass, entry)

    # Perform initial data load
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator so platforms can access it
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to sensor (and other) platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
