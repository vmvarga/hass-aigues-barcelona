"""Integration for Aigues de Barcelona."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_TOKEN
from homeassistant.const import CONF_USERNAME
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import AiguesApiClient
from .api import RecaptchaRequired
from .const import DOMAIN
from .service import async_setup as setup_service

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def _try_startup_refresh(hass: HomeAssistant, entry: ConfigEntry, api: AiguesApiClient) -> bool:
    """Attempt to obtain a fresh token at startup.  Returns True on success."""
    try:
        new_token = await hass.async_add_executor_job(api.login)
    except RecaptchaRequired:
        _LOGGER.warning("Captcha required – cannot refresh token at startup")
        return False
    except Exception as exc:
        _LOGGER.warning("Startup token refresh failed: %s", exc)
        return False

    if not new_token:
        return False

    _LOGGER.info("Token refreshed successfully at startup")
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_TOKEN: new_token}
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    api = AiguesApiClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    api.set_token(entry.data.get(CONF_TOKEN))

    if api.is_token_expired() or api.is_token_expiring_soon():
        refreshed = await _try_startup_refresh(hass, entry, api)
        if not refreshed and api.is_token_expired():
            entry.async_start_reauth(hass)
            return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await setup_service(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if entry.entry_id in hass.data[DOMAIN].keys():
            hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return unload_ok
