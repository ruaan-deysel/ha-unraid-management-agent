---
agent: "agent"
tools: ["search/codebase", "edit", "search"]
description: "Add a new service action to the integration with proper schema and registration"
---

# Add Service Action

Your goal is to add a new **service action** to this Home Assistant integration that users can call from automations, scripts, or the UI.

**Terminology:**

- **Developer/Code:** "service action" (function names, comments)
- **User-facing:** "action" only (in UI, translations under `services` key)
- **Legacy:** `services.yaml`, `hass.services.async_register()`, `ServiceCall` class

If not provided, ask for:

- Service action name and purpose
- Parameters required (with types and validation)
- What the action does (API call, state change, etc.)
- Response data (if any)

## Implementation Steps

### 1. Define in `services.yaml`

**File:** `custom_components/unraid_management_agent/services.yaml`

**CRITICAL:** Action names and descriptions must be in translation files under the `services` key, NOT in `services.yaml`.

```yaml
[action_name]:
  fields:
    [parameter_name]:
      required: true
      example: "[example value]"
      selector:
        text:
```

### 2. Create Service Action Handler

Add to `custom_components/unraid_management_agent/__init__.py` in `async_setup`:

```python
async def async_handle_[action_name](call: ServiceCall) -> None:
    """Handle the [action_name] service action."""
    # Get coordinator from first config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data.coordinator

    try:
        await coordinator.client.[api_method](call.data["param"])
        await coordinator.async_request_refresh()
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="[action_name]_failed",
        ) from err

hass.services.async_register(
    DOMAIN,
    "[action_name]",
    async_handle_[action_name],
    schema=vol.Schema({
        vol.Required("param"): cv.string,
    }),
)
```

### 3. Register in `async_setup` (CRITICAL)

**Service actions must register in `async_setup`, NOT in `async_setup_entry`!**

Service actions are integration-wide, not per config entry. This follows the existing pattern in `__init__.py`.

### 4. Add Translations

**`translations/en.json`:**

```json
{
  "services": {
    "[action_name]": {
      "name": "[Action Name]",
      "description": "[Description of what the action does]",
      "fields": {
        "[parameter_name]": {
          "name": "Parameter Name",
          "description": "Description of the parameter"
        }
      }
    }
  }
}
```

### 5. Add Icons

**`icons.json`:**

```json
{
  "services": {
    "[action_name]": {
      "service": "mdi:icon-name"
    }
  }
}
```

## Error Handling

```python
from homeassistant.exceptions import HomeAssistantError

async def async_handle_action(call: ServiceCall) -> None:
    """Handle service action with error handling."""
    try:
        await coordinator.client.do_something(call.data)
    except UnraidConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_failed",
        ) from err
```

## Validation Checklist

- [ ] Service action defined in `services.yaml` (schema only, no text)
- [ ] All user-facing text in `translations/en.json` under `services` key
- [ ] Handler implemented with proper error handling
- [ ] Registered in `async_setup` (NOT `async_setup_entry`)
- [ ] Icons added to `icons.json`
- [ ] Type hints complete
- [ ] `script/lint` passes

**DO NOT create tests unless explicitly requested.**
