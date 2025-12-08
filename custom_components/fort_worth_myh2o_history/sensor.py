"""Sensor for fwmyh2o_history - publishes latest state from the HA states store."""

from __future__ import annotations

from typing import Any
import logging

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    """Set up the cumulative/usage sensor platform."""
    entity_id = hass.data.get(DOMAIN, {}).get("entity_id", "sensor.fwmyh2o_hourly_usage")
    async_add_entities([FWMyH2OHourlySensor(hass, entity_id)], True)


class FWMyH2OHourlySensor(Entity):
    def __init__(self, hass: HomeAssistant, entity_id: str):
        self.hass = hass
        self._entity_id = entity_id
        self._state = None
        self._attrs = {
            "unit_of_measurement": "gal",
            "device_class": "water",
            "state_class": "measurement",
            "friendly_name": "FW MyH2O Hourly Usage"
        }

    @property
    def name(self) -> str:
        return self._entity_id

    @property
    def state(self) -> Any:
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    async def async_update(self):
        """Pull the most recent state from HA states store."""
        state_obj = self.hass.states.get(self._entity_id)
        if state_obj:
            self._state = state_obj.state