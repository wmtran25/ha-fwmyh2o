"""Fort Worth MyH2O integration for Home Assistant."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import FWMH2ODataUpdateCoordinator

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Fort Worth MyH2O from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create coordinator
    coordinator = FWMH2ODataUpdateCoordinator(hass, entry)

    # Perform initial data load
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator so platforms can access it
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
