"""Diagnostics support for Unraid Management Agent."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import UnraidConfigEntry

TO_REDACT = {
    CONF_HOST,
    CONF_PORT,
    "ip",
    "ip_address",
    "mac",
    "mac_address",
    "serial",
    "serial_number",
    "hostname",
    "host",
    "gateway",
    "dns",
    "email",
    "password",
    "api_key",
    "token",
    "secret",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UnraidConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator_data": async_redact_data(coordinator.data, TO_REDACT),
    }
