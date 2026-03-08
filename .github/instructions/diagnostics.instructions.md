---
applyTo: "custom_components/unraid_management_agent/diagnostics.py"
---

# Diagnostics Instructions

**Applies to:** Diagnostics implementation

## Critical: Always Redact Sensitive Data

**Use `async_redact_data()` for all user data:**

```python
from homeassistant.helpers.redact import async_redact_data

TO_REDACT = {
    "host",
    "port",
    "api_key",
    "token",
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": async_redact_data(entry.options, TO_REDACT),
        "coordinator_data": coordinator.data,
    }
```

## Never Expose

The following must ALWAYS be redacted:

- Host addresses / IP addresses
- Port numbers (if considered sensitive)
- API keys / tokens
- Location data (latitude/longitude)
- Personal information

## When in Doubt

If you're unsure whether data is sensitive, **redact it**. Better to redact too much than expose credentials.
