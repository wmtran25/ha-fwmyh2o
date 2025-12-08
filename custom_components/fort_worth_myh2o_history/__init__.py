"""fwmyh2o_history __init__ - schedule and run daily import of hourly usage (option A)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time as dtime, timedelta

import homeassistant.util.dt as dt_util
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    ATTR_IMPORT_TIME,
    ATTR_ENTITY_ID,
    ATTR_USERNAME,
    ATTR_PASSWORD,
    DEFAULT_IMPORT_TIME,
)

from .historical_import import import_hourly_deltas_from_cumulative
from .fetcher import fetch_cumulative_readings_for_date_sync  # synchronous helper executed in executor

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the fwmyh2o_history integration from configuration.yaml."""

    conf = config.get(DOMAIN, {}) if config else {}

    import_time_str = conf.get(ATTR_IMPORT_TIME, DEFAULT_IMPORT_TIME)
    entity_id = conf.get(ATTR_ENTITY_ID, DEFAULT_ENTITY_ID)
    username = conf.get(ATTR_USERNAME)
    password = conf.get(ATTR_PASSWORD)
    debug = conf.get("debug", False)

    if debug:
        _LOGGER.setLevel(logging.DEBUG)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entity_id"] = entity_id
    hass.data[DOMAIN]["import_time"] = import_time_str
    hass.data[DOMAIN]["username"] = username
    hass.data[DOMAIN]["password"] = password

    async def schedule_imports(_=None):
        """Schedule the next import at the configured time (daily)."""
        now = dt_util.now()
        hh, mm = map(int, import_time_str.split(":"))
        target_today = dt_util.as_local(datetime.combine(now.date(), dtime(hh, mm)))
        if target_today <= now:
            target_today = dt_util.as_local(datetime.combine(now.date() + timedelta(days=1), dtime(hh, mm)))

        delay = (target_today - now).total_seconds()

        _LOGGER.info("fwmyh2o_history: scheduling next import at %s (in %s seconds)", target_today.isoformat(), int(delay))

        async def _delayed():
            await asyncio.sleep(delay)
            try:
                await do_import_for_yesterday(hass)
            except Exception:
                _LOGGER.exception("fwmyh2o_history: import failed")
            hass.async_create_task(schedule_imports())

        hass.async_create_task(_delayed())

    async def do_import_for_yesterday(hass_obj: HomeAssistant):
        """Fetch yesterday's cumulative hourly readings and import them (as hourly deltas)."""
        # yesterday date in local time
        tz = dt_util.get_time_zone(hass_obj.config.time_zone)
        yesterday = dt_util.now().astimezone(tz).date() - timedelta(days=1)
        _LOGGER.info("fwmyh2o_history: starting import for date %s", yesterday.isoformat())

        # fetch cumulative readings using requests in executor to avoid blocking
        try:
            readings = await hass_obj.async_add_executor_job(
                fetch_cumulative_readings_for_date_sync, hass_obj, yesterday
            )
        except Exception as e:
            _LOGGER.exception("fwmyh2o_history: fetcher raised exception: %s", e)
            readings = []

        if not readings:
            _LOGGER.warning("fwmyh2o_history: no readings returned for %s", yesterday.isoformat())
            return

        # readings: list of { "timestamp": datetime tz-aware, "cumulative": float }
        entity = hass_obj.data[DOMAIN]["entity_id"]
        # import into HA as hourly delta states (fires historical state_changed events)
        import_hourly_deltas_from_cumulative(hass_obj, entity, readings)
        _LOGGER.info("fwmyh2o_history: import for %s completed, %d readings processed", yesterday.isoformat(), len(readings))

    # on HA start, schedule imports
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, schedule_imports)

    # also schedule an immediate import (attempt to import yesterday on setup)
    hass.async_create_task(do_import_for_yesterday(hass))

    return True