---
applyTo: "custom_components/unraid_management_agent/repairs.py"
---

# Repairs Instructions

**Applies to:** Repairs implementation

**Official Documentation:**

- [Repairs Framework](https://developers.home-assistant.io/docs/core/platform/repairs)
- [Issue Registry](https://developers.home-assistant.io/docs/core/platform/repairs#issue-registry)

## Overview

Repair Flows guide users through fixing issues (deprecated settings, missing configuration, etc.).

**Key differences from Config Flow:**

- **Location**: `repairs.py` in integration root (NOT in config flow)
- **Base class**: `homeassistant.components.repairs.RepairsFlow` (NOT `ConfigFlow`)
- **Trigger**: System creates issue -> user clicks "Fix" -> Repair Flow runs
- **Purpose**: Fix existing problems, not create new config entries

## Architecture

**Lifecycle:**

1. Integration detects issue -> `async_create_issue()`
2. User clicks "Fix" -> `async_create_fix_flow()` called with issue_id
3. Repair flow guides user through steps
4. Fix applied -> `async_delete_issue()`

## Creating Issues

```python
from homeassistant.helpers import issue_registry as ir

ir.async_create_issue(
    hass,
    DOMAIN,
    "issue_id",
    is_fixable=True,
    severity=ir.IssueSeverity.WARNING,
    translation_key="issue_id",
    translation_placeholders={"key": "value"},
)
```

## Repair Flow Implementation

**Required function in repairs.py:**

```python
async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow for issue_id."""
    return UnraidRepairFlow()
```

**Flow class:**

```python
class UnraidRepairFlow(RepairsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            ir.async_delete_issue(self.hass, DOMAIN, "issue_id")
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="init")
```

## Translations

**Required keys:**

```json
{
  "issues": {
    "issue_id": {
      "title": "Issue title",
      "description": "Description with {placeholder}",
      "fix_flow": {
        "step": {
          "init": {
            "title": "Repair step title",
            "description": "Instructions"
          }
        }
      }
    }
  }
}
```

## Rules

**MUST:**

- Place `repairs.py` in integration root
- Implement `async_create_fix_flow()` returning `RepairsFlow` subclass
- Delete issue after successful repair: `ir.async_delete_issue()`
- Set `is_fixable=True` only if repair flow exists
- Provide translations for all text

**NEVER:**

- Leave issues after repair completes (always delete)
- Use repair flows for normal config changes (use reconfigure instead)
- Create issues without translations
