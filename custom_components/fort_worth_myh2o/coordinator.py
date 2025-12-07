"""Coordinator that logs in and fetches usage data from the Fort Worth MyH2O portal."""
from __future__ import annotations

import logging
from datetime import timedelta
import re

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, CONF_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

LOGIN_URL = "https://fwmyh2o.smartcmobile.com/portal/login.aspx"
USAGE_URL = "https://fwmyh2o.smartcmobile.com/portal/usages.aspx?type=WU"


class FWMH2ODataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching Fort Worth MyH2O usage data."""

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
        """Attempt to login to the portal."""
        try:
            html = await self._async_get(LOGIN_URL)
            soup = BeautifulSoup(html, "html.parser")
            form = {inp.get("name"): inp.get("value", "") for inp in soup.find_all("input") if inp.get("name")}

            form.update({
                "ctl00$ContentPlaceHolder1$txtUsername": self.username,
                "ctl00$ContentPlaceHolder1$txtPassword": self.password,
            })

            await self._async_post(LOGIN_URL, data=form)
        except Exception as err:
            _LOGGER.debug("Login attempt failed: %s", err)
            # Continue; sometimes the usage page is accessible without login

    async def _async_parse_usage(self, html: str) -> dict:
        """Parse usage HTML and return dict with current, daily, monthly usage."""
        soup = BeautifulSoup(html, "html.parser")
        data = {"current_reading": None, "daily_usage": None, "monthly_usage": None, "account": None}

        text = soup.get_text(" ", strip=True)

        numbers = re.findall(r"[0-9,.]+", text)

        def to_float(s: str) -> float | None:
            try:
                return float(s.replace(",", ""))
            except Exception:
                return None

        # Find current reading
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

        if data["current_reading"] is None and numbers:
            val = max((to_float(n) or 0) for n in numbers)
            data["current_reading"] = val

        daily_match = re.search(r"Last\s*24\s*Hours[^0-9]*([0-9,.]+)", text, re.IGNORECASE)
        if daily_match:
            data["daily_usage"] = to_float(daily_match.group(1))

        month_match = re.search(r"This\s*Month[^0-9]*([0-9,.]+)", text, re.IGNORECASE)
        if month_match:
            data["monthly_usage"] = to_float(month_match.group(1))

        acc_match = re.search(r"Account[:#]*\s*([A-Za-z0-9-]+)", text, re.IGNORECASE)
        if acc_match:
            data["account"] = acc_match.group(1)

        return data

    async def _async_update_data(self) -> dict:
        """Fetch and parse usage data."""
        try:
            await self._async_login()
            html = await self._async_get(USAGE_URL)
            parsed = await self._async_parse_usage(html)
            return parsed
        except Exception as err:
            _LOGGER.exception("Error fetching MyH2O data: %s", err)
            raise UpdateFailed(err)

    async def async_will_remove_from_hass(self) -> None:
        if self.session:
            await self.session.close()
