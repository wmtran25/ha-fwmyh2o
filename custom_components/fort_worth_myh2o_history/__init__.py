"""fwmyh2o_history __init__ - schedule and run daily import of cumulative hourly readings."""

from __future__ import annotations

import logging
from datetime import datetime, time as dtime, timedelta
import asyncio

import homeassistant.util.dt as dt_util
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    ATTR_IMPORT_TIME,
    ATTR_ENTITY_ID,
    DEFAULT_IMPORT_TIME,
)

from .historical_import import import_cumulative_readings
from .fetcher import fetch_cumulative_readings_for_date  # you will implement this

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the fwmyh2o_history integration from configuration.yaml."""

    conf = config.get(DOMAIN, {}) if config else {}
    import_time_str = conf.get(ATTR_IMPORT_TIME, DEFAULT_IMPORT_TIME)
    entity_id = conf.get(ATTR_ENTITY_ID, "sensor.fwmyh2o_cumulative")
    debug = conf.get("debug", False)

    if debug:
        _LOGGER.setLevel(logging.DEBUG)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entity_id"] = entity_id
    hass.data[DOMAIN]["import_time"] = import_time_str

    async def schedule_imports(_=None):
        """Schedule the next import at the configured time (daily)."""
        # calculate next occurrence of import_time (in local tz)
        now = dt_util.now()
        hh, mm = map(int, import_time_str.split(":"))
        target_today = dt_util.as_local(datetime.combine(now.date(), dtime(hh, mm)))
        if target_today <= now:
            # schedule for tomorrow
            target_today = dt_util.as_local(datetime.combine(now.date() + timedelta(days=1), dtime(hh, mm)))

        delay = (target_today - now).total_seconds()

        _LOGGER.info("fwmyh2o_history: scheduling next import at %s (in %s seconds)", target_today.isoformat(), int(delay))

        async def _delayed():
            await asyncio.sleep(delay)
            try:
                await do_import_for_yesterday(hass)
            except Exception as e:
                _LOGGER.exception("fwmyh2o_history: import failed: %s", e)
            # schedule next import
            hass.async_create_task(schedule_imports())

        hass.async_create_task(_delayed())

    async def do_import_for_yesterday(hass_obj: HomeAssistant):
        """Fetch yesterday's cumulative hourly readings and import them."""
        # yesterday date in local time
        tz = dt_util.get_time_zone(hass_obj.config.time_zone)
        yesterday = dt_util.now().astimezone(tz).date() - timedelta(days=1)
        _LOGGER.info("fwmyh2o_history: starting import for date %s", yesterday.isoformat())

        # fetch cumulative readings for the date (implement in fetcher.py)
        readings = await fetch_cumulative_readings_for_date(hass_obj, yesterday)

        if not readings:
            _LOGGER.warning("fwmyh2o_history: no readings returned for %s", yesterday.isoformat())
            return

        # readings should be list of dicts: { "timestamp": datetime (tz-aware), "cumulative": float }
        # convert timestamps to UTC & import
        entity = hass_obj.data[DOMAIN]["entity_id"]
        # call helper to import
        import_cumulative_readings(hass_obj, entity, readings)
        _LOGGER.info("fwmyh2o_history: import for %s completed, %d readings inserted", yesterday.isoformat(), len(readings))

    # on HA start, schedule imports
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, schedule_imports)

    # also schedule immediately (on setup) so we import yesterday right away
    hass.async_create_task(do_import_for_yesterday(hass))

    return True
