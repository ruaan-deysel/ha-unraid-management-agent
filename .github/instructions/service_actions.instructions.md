---
applyTo: "custom_components/unraid_management_agent/__init__.py"
---

# Service Actions Instructions

**Applies to:** Service action registration in `__init__.py`

**Reference:** [Home Assistant Service Actions Documentation](https://developers.home-assistant.io/docs/dev_101_services/)

## This Integration's Pattern

Service actions are registered in `async_setup()` in `__init__.py` (not in a separate package).

**Service naming:** `unraid_management_agent.<action_name>`

## Registration

**Register in `async_setup()` (component level):**

```python
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    async def handle_action(call: ServiceCall) -> None:
        """Handle the action."""
        ...

    hass.services.async_register(
        DOMAIN, "action_name", handle_action, schema=ACTION_SCHEMA
    )
    return True
```

**NEVER register in `async_setup_entry()`** (per config entry).

## Service Schema

Use voluptuous with `homeassistant.helpers.config_validation`:

```python
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

SERVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): cv.string,
    vol.Optional("force", default=False): cv.boolean,
})
```

## Exception Handling

**Use appropriate exceptions:**

- `ServiceValidationError` - User provided invalid data (no stack trace in logs)
- `HomeAssistantError` - Device/communication errors (full stack trace in logs)

Both exceptions support translation keys for localization.

## Response Data

Services can return JSON-serializable data for use in automations:

**Critical requirements:**

- Response MUST be a `dict`
- **datetime objects MUST use `.isoformat()`**
- Raise exceptions for errors, never return error codes

**SupportsResponse modes:**

- `SupportsResponse.OPTIONAL` - Returns data only if `call.return_response` is True
- `SupportsResponse.ONLY` - Always returns data, performs no action

## Service Icons

Define in `icons.json`:

```json
{
  "services": {
    "action_name": { "service": "mdi:icon-name" }
  }
}
```

## Rules

**MUST:**

- Register in `async_setup()`, not `async_setup_entry()`
- Use `DOMAIN` for service domain, never platform domain
- Include translations for all service actions in `strings.json`
- Define icons in `icons.json`

**NEVER:**

- Register services per config entry
- Return error codes in response data (raise exceptions instead)
