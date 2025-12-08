"""historical_import.py - create backdated cumulative sensor states by firing state_changed events."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import List, Dict

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT

_LOGGER = logging.getLogger(__name__)

# Constants for the cumulative sensor: gallons
UNIT = "gal"

def _ensure_tz(dt: datetime) -> datetime:
    """Ensure datetime is timezone aware (convert naive as local)."""
    if dt.tzinfo is None:
        return dt_util.as_local(dt)
    return dt

def import_cumulative_readings(hass: HomeAssistant, entity_id: str, readings: List[Dict]):
    """
    Insert cumulative readings (one per hour) into HA by firing state_changed events
    with the original timestamp.

    readings: list of dicts:
      - 'timestamp': datetime (should be tz-aware or local naive)
      - 'cumulative': numeric (float/int)
    """

    if not readings:
        _LOGGER.debug("No readings to import for %s", entity_id)
        return

    # Sort readings by timestamp ascending to insert in chronological order
    readings_sorted = sorted(readings, key=lambda r: r["timestamp"])

    for r in readings_sorted:
        ts = r.get("timestamp")
        cum = r.get("cumulative")
        if ts is None or cum is None:
            _LOGGER.warning("Skipping invalid reading: %s", r)
            continue

        ts = _ensure_tz(ts)
        # convert to UTC isoformat for fields
        ts_utc = dt_util.as_utc(ts).isoformat()

        _LOGGER.debug("Importing cumulative reading for %s at %s = %s %s", entity_id, ts_utc, cum, UNIT)

        # Fire state_changed event with new_state containing timestamps.
        # The recorder may accept this as a historical state if it honors the provided timestamps.
        hass.bus.async_fire(
            "state_changed",
            {
                "entity_id": entity_id,
                "old_state": None,
                "new_state": {
                    "state": str(cum),
                    "attributes": {
                        "unit_of_measurement": UNIT,
                        # To help HA treat it properly as cumulative meter reading:
                        "device_class": "water",
                        "state_class": "total_increasing"
                    },
                    "last_updated": ts_utc,
                    "last_changed": ts_utc
                }
            }
        )
