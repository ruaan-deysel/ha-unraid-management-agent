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


def _serialize_data(data: Any) -> Any:
    """Serialize Pydantic models and other data types to dict/list."""
    if data is None:
        return None

    # Check if it's a Pydantic model (has model_dump method)
    if hasattr(data, "model_dump"):
        return data.model_dump()

    # Check if it's a dataclass with our UnraidData
    if hasattr(data, "__dataclass_fields__"):
        result = {}
        for field_name in data.__dataclass_fields__:
            field_value = getattr(data, field_name)
            result[field_name] = _serialize_data(field_value)
        return result

    # Handle lists
    if isinstance(data, list):
        return [_serialize_data(item) for item in data]

    # Handle dicts
    if isinstance(data, dict):
        return {key: _serialize_data(value) for key, value in data.items()}

    # Return as-is for primitives
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UnraidConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    # Serialize coordinator data (contains Pydantic models)
    coordinator_data = _serialize_data(coordinator.data)

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator_data": async_redact_data(coordinator_data, TO_REDACT),
    }
