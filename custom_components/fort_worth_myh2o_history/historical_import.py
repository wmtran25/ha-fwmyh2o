"""historical_import.py - create backdated hourly delta states by firing state_changed events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Dict

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

UNIT = "gal"


def _ensure_tz(dt: datetime) -> datetime:
    """Ensure datetime is timezone aware (convert naive as local)."""
    if dt.tzinfo is None:
        return dt_util.as_local(dt)
    return dt


def import_hourly_deltas_from_cumulative(hass: HomeAssistant, entity_id: str, readings: List[Dict]):
    """
    Given cumulative readings (list of {timestamp, cumulative}), compute hourly deltas
    and fire state_changed events with the original timestamps but state equal to the delta.

    This will create a time series of hourly consumption values for `entity_id`.
    """

    if not readings:
        _LOGGER.debug("No readings to import for %s", entity_id)
        return

    # sort ascending by timestamp
    readings_sorted = sorted(readings, key=lambda r: r["timestamp"])

    prev_cum = None
    for r in readings_sorted:
        ts = r.get("timestamp")
        cum = r.get("cumulative")
        if ts is None or cum is None:
            _LOGGER.warning("Skipping invalid reading: %s", r)
            continue

        ts = _ensure_tz(ts)
        # compute delta vs previous cumulative (if prev is None, delta = cum)
        if prev_cum is None:
            delta = float(cum)
        else:
            delta = float(cum) - float(prev_cum)
            if delta < 0:
                # guard against negative rollovers; set to 0
                _LOGGER.warning("Negative delta detected at %s (prev=%s curr=%s); setting delta=0", ts.isoformat(), prev_cum, cum)
                delta = 0.0

        prev_cum = cum

        # convert to UTC isoformat
        ts_utc = dt_util.as_utc(ts).isoformat()

        _LOGGER.debug("Importing hourly delta for %s at %s = %s %s", entity_id, ts_utc, delta, UNIT)

        # Fire state_changed event with new_state containing timestamps.
        hass.bus.async_fire(
            "state_changed",
            {
                "entity_id": entity_id,
                "old_state": None,
                "new_state": {
                    "state": str(round(delta, 6)),
                    "attributes": {
                        "unit_of_measurement": UNIT,
                        "device_class": "water",
                        "state_class": "measurement",
                        "source": "fwmyh2o_history"
                    },
                    "last_updated": ts_utc,
                    "last_changed": ts_utc
                }
            }
        )