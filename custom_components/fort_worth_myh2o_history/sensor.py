"""Sensor exposing the latest cumulative reading fetched by fwmyh2o_history."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    """Set up the temporary cumulative sensor platform."""
    entity_id = hass.data.get(DOMAIN, {}).get("entity_id", "sensor.fwmyh2o_cumulative")
    async_add_entities([FWMyH2OCumulativeSensor(hass, entity_id)], True)

class FWMyH2OCumulativeSensor(Entity):
    def __init__(self, hass: HomeAssistant, entity_id: str):
        self.hass = hass
        self._entity_id = entity_id
        self._state = None
        self._attrs = {
            "device_class": "water",
            "state_class": "total_increasing",
            "unit_of_measurement": "gal"
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
        """Called by HA to update the sensor state: get latest state from HA states store."""
        state_obj = self.hass.states.get(self._entity_id)
        if state_obj:
            self._state = state_obj.state
