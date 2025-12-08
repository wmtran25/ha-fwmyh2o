# fetcher.py — Fort Worth MyH2O hourly cumulative history fetcher

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import json
import homeassistant.util.dt as dt_util
import requests

_LOGGER = logging.getLogger(__name__)

API_URL = "https://fwmyh2o.smartcmobile.com/Portal/Usages.aspx/LoadWaterUsage"

HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}


async def fetch_cumulative_readings_for_date(hass, date) -> List[Dict]:
    """
    POST to Fort Worth MyH2O API to fetch hourly cumulative usage for a given date.

    Returns a list of dicts like:
      { "timestamp": datetime, "cumulative": float }
    """

    # MyH2O expects mm/dd/yyyy format
    req_date_str = date.strftime("%m/%d/%Y")

    payload = {
        "Type": "C",
        "Mode": "H",
        "strDate": req_date_str,
        "hourlyType": "H",
        "seasonId": 0,
        "weatherOverlay": 0,
        "usageyear": "",
        "MeterNumber": "",
        "DateFromDaily": "",
        "DateToDaily": "",
        "isNoDashboard": True
    }

    _LOGGER.debug("Posting usage request for date=%s", req_date_str)

    try:
        resp = requests.post(API_URL, headers=HEADERS, data=json.dumps(payload), timeout=20)
        resp.raise_for_status()

    except Exception as e:
        _LOGGER.error("API request failed: %s", e)
        return []

    try:
        # Response JSON field "d" contains another JSON string
        raw_json = resp.json().get("d")
        parsed = json.loads(raw_json)
        hourly_list = parsed.get("objUsageGenerationResultSetTwo", [])

    except Exception as e:
        _LOGGER.error("Error parsing response JSON: %s", e)
        return []

    results = []
    tz = dt_util.get_time_zone(hass.config.time_zone)

    for entry in hourly_list:
        usage_date = entry.get("UsageDate")
        hourly_str = entry.get("Hourly")
        val = entry.get("UsageValue", 0.0)

        if not usage_date or not hourly_str:
            continue

        try:
            # UsageDate always mm/dd/yyyy
            base_date = datetime.strptime(usage_date, "%m/%d/%Y")

            # Parse hour like "12:00 AM"
            hour_dt = datetime.strptime(hourly_str, "%I:%M %p")

            dt_full = datetime.combine(base_date, hour_dt.time())
            dt_full = tz.localize(dt_full)

            results.append({
                "timestamp": dt_full,
                "cumulative": float(val)
            })

        except Exception as e:
            _LOGGER.warning("Could not parse timestamp from entry: %s", e)

    _LOGGER.info("Fetched %d hourly readings for %s", len(results), req_date_str)

    return results
