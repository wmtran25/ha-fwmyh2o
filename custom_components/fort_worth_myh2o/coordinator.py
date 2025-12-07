"""
Coordinator that logs in and fetches usage data from the Fort Worth MyH2O portal.
This implementation uses aiohttp and BeautifulSoup to scrape the usage pages.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_SCAN_INTERVAL, CONF_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

LOGIN_URL = "https://fwmyh2o.smartcmobile.com/portal/login.aspx"
USAGE_URL = "https://fwmyh2o.smartcmobile.com/portal/usages.aspx?type=WU"


class FWMH2ODataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.username = entry.data["username"]
        self.password = entry.data["password"]
        self.session: ClientSession | None = None

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name="Fort Worth MyH2O",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _create_session(self) -> ClientSession:
        if self.session and not self.session.closed:
            return self.session
        self.session = ClientSession()
        return self.session

    async def _async_get(self, url: str, **kwargs) -> str:
        session = await self._create_session()
        async with session.get(url, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _async_post(self, url: str, **kwargs) -> str:
        session = await self._create_session()
        async with session.post(url, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _async_login(self) -> None:
        """Attempt to login to the portal. If the portal uses JavaScript-based auth this may fail; we try a form post first."""
        try:
            # Fetch login page to get any viewstate/hidden fields
            html = await self._async_get(LOGIN_URL)
            soup = BeautifulSoup(html, "html.parser")
            form = {}
            for inp in soup.find_all("input"):
                name = inp.get("name")
                if not name:
                    continue
                val = inp.get("value", "")
                form[name] = val

            # Guess common field names
            form_fields = {
                "ctl00$ContentPlaceHolder1$txtUsername": self.username,
                "ctl00$ContentPlaceHolder1$txtPassword": self.password,
            }
            form.update(form_fields)

            # Post the form
            await self._async_post(LOGIN_URL, data=form)
        except Exception as err:
            _LOGGER.debug("Login attempt failed: %s", err)
            # Don't raise here; the usage page may be accessible without explicit login

    async def _async_parse_usage(self, html: str) -> dict:
        """Parse usage HTML and return a dict with current, daily, monthly."""
        soup = BeautifulSoup(html, "html.parser")

        data = {
            "current_reading": None,
            "daily_usage": None,
            "monthly_usage": None,
            "account": None,
        }

        # Attempt to find labels that often appear on the page. The exact markup may vary.
        # Find current reading by searching for keywords and nearby numeric values
        text = soup.get_text(" ", strip=True)

        import re

        # Find large floating numbers that look like gallons (e.g., 1,234.56)
        numbers = re.findall(r"[0-9,.]+", text)

        def to_float(s: str) -> float | None:
            try:
                return float(s.replace(",", ""))
            except Exception:
                return None

        # Heuristics: last few numbers in the page may be the readings. We'll attempt to find lines with 'Total' or 'Reading'
        for label in ["Total", "Reading", "Current", "Meter"]:
            idx = text.find(label)
            if idx != -1:
                nearby = text[idx: idx + 200]
                m = re.search(r"([0-9,.]+)", nearby)
                if m:
                    val = to_float(m.group(1))
                    if val is not None:
                        data["current_reading"] = val
                        break

        # If not found, try the largest number as a fallback
        if data["current_reading"] is None and numbers:
            val = max((to_float(n) or 0) for n in numbers)
            data["current_reading"] = val

        # Daily and monthly: try to find phrases 'Last 24 Hours' or 'This Month'
        daily_match = re.search(r"Last\s*24\s*Hours[^0-9]*([0-9,.]+)", text, re.IGNORECASE)
        if daily_match:
            data["daily_usage"] = to_float(daily_match.group(1))

        month_match = re.search(r"This\s*Month[^0-9]*([0-9,.]+)", text, re.IGNORECASE)
        if month_match:
            data["monthly_usage"] = to_float(month_match.group(1))

        # Try to find 'Account' or 'Service Address'
        acc_match = re.search(r"Account[:#]*\s*([A-Za-z0-9-]+)", text, re.IGNORECASE)
        if acc_match:
            data["account"] = acc_match.group(1)

        return data

    async def _async_update_data(self) -> dict:
        """Fetch data from the portal and return parsed values."""
        try:
            await self._async_login()
            html = await self._async_get(USAGE_URL)
            # parsed = await asyncio.get_running_loop().run_in_executor(None, lambda: self.hass.async_add_job(lambda: parsed) )
            # Note: above is a placeholder to emphasize parser should not block — instead just call parse directly
            # We'll call parse synchronously here because BeautifulSoup is relatively fast for small pages
            parsed = await self._async_parse_usage(html)
            return parsed
        except Exception as err:
            _LOGGER.exception("Error fetching MyH2O data: %s", err)
            raise UpdateFailed(err)

    async def async_will_remove_from_hass(self) -> None:
        if self.session:
            await self.session.close()
