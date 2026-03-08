---
agent: "agent"
tools: ["search/codebase", "edit", "search", "runCommands"]
description: "Add a new configuration option to initial setup or options flow with validation"
---

# Add Config Option

Your goal is to add a new configuration option to the config flow (setup or options flow).

If not provided, ask for:

- Option name and purpose
- Data type (string, int, float, bool, selector)
- Where to add (initial setup or options flow)
- Default value (if applicable)
- Validation requirements

## Requirements

**Schema Definition:**

- Add to appropriate schema in `config_flow.py`
- Use voluptuous validators from `homeassistant.helpers.config_validation as cv`
- Use selectors for better UI (BooleanSelector, NumberSelector, etc.)
- Set appropriate default values with `vol.Optional()`

**Config Flow Logic:**

- Update flow step in `config_flow.py`
- Handle new field in `async_step_user()` or options flow
- Validate input if needed
- Store value in `config_entry.data` or `config_entry.options`

**Using the Option:**

- Access via `entry.data[CONF_OPTION_KEY]` or `entry.options.get(CONF_OPTION_KEY)`
- Pass to coordinator if needed for data fetching
- Update entity behavior based on option value

**Translations:**

- Add label to `translations/en.json` under `config.step.[step_name].data`
- Add helper text under `data_description`
- Add error messages under `config.error.[error_key]`

**Constants:**

- Add constant to `const.py`: `CONF_[OPTION_NAME]`
- Document purpose with inline comment

**Migration (if changing existing config):**

- Increment `VERSION` in config flow handler
- Implement `async_migrate_entry()` if needed
- Handle both old and new format for backwards compatibility

**Code Quality:**

- Follow existing config flow patterns in `config_flow.py`
- Use proper selector types for best UX
- Run `script/lint` to validate before completion

**Related Files:**

- Config Flow: `custom_components/unraid_management_agent/config_flow.py`
- Constants: `custom_components/unraid_management_agent/const.py`
- Translations: `custom_components/unraid_management_agent/translations/en.json`

**DO NOT create tests unless explicitly requested.**
