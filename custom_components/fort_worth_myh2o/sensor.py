"""Sensors for the Fort Worth MyH2O integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up sensors for Fort Worth MyH2O."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unique_base = f"{entry.entry_id}_{entry.data.get(CONF_USERNAME)}"

    entities = [
        CurrentReadingSensor(coordinator, unique_base),
        DailyUsageSensor(coordinator, unique_base),
        MonthlyUsageSensor(coordinator, unique_base),
    ]

    async_add_entities(entities, True)


class BaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor using DataUpdateCoordinator."""

    def __init__(self, coordinator, unique_base: str, name: str, key: str):
        super().__init__(coordinator)
        self._name = name
        self._unique_id = f"{unique_base}_{key}"
        self._key = key

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name="Fort Worth MyH2O",
            manufacturer="City of Fort Worth",
        )


class CurrentReadingSensor(BaseSensor):
    @property
    def state(self):
        return self.coordinator.data.get("current_reading")

    @property
    def unit_of_measurement(self):
        return "gal"

    @property
    def device_class(self):
        return "water"

    @property
    def state_class(self):
        return "total_increasing"


class DailyUsageSensor(BaseSensor):
    @property
    def state(self):
        return self.coordinator.data.get("daily_usage")

    @property
    def unit_of_measurement(self):
        return "gal"

    @property
    def state_class(self):
        return "measurement"


class MonthlyUsageSensor(BaseSensor):
    @property
    def state(self):
        return self.coordinator.data.get("monthly_usage")

    @property
    def unit_of_measurement(self):
        return "gal"

    @property
    def state_class(self):
        return "measurement"
