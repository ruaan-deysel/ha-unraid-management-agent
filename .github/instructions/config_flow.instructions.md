---
applyTo: "custom_components/unraid_management_agent/config_flow.py"
---

# Config Flow Instructions

**Applies to:** Config flow implementation

**Official Documentation:**

- [Data Entry Flow Index](https://developers.home-assistant.io/docs/data_entry_flow_index) - Fundamental flow concepts and result types
- [Config Flow Handler](https://developers.home-assistant.io/docs/config_entries_config_flow_handler)
- [Options Flow Handler](https://developers.home-assistant.io/docs/config_entries_options_flow_handler)

## Architecture Overview

**Data Entry Flow** (Framework Layer):

- Generic UI flow system for collecting user input
- Provides: `FlowHandler`, result types (`FORM`, `CREATE_ENTRY`, etc.), form schemas
- Has **nothing to do** with runtime data -- confusing naming!

**Config Flow** (Application Layer):

- Uses Data Entry Flow framework for integration setup
- Creates `ConfigEntry` with immutable data (host, port) and mutable options
- Inherits from `config_entries.ConfigFlow`

**Options Flow** (Application Layer):

- Uses Data Entry Flow framework for settings changes
- Modifies `ConfigEntry.options`, never immutable data
- Inherits from `config_entries.OptionsFlow`

## This Integration's Config Flow

- Single file: `config_flow.py` (no package structure)
- No authentication (local API)
- User step collects host/port
- Validates connection before creating entry
- Options flow for configurable settings

## Data Entry Flow Result Types

- `FORM` - Show form: `async_show_form(step_id, data_schema, errors={})`
- `CREATE_ENTRY` - Create entry: `async_create_entry(title, data={}, options={})`
- `ABORT` - Stop flow: `async_abort(reason="...")`

## Form Schemas

**Simple fields:** `vol.Required("field"): str`, `vol.Optional("field", default=value): int`

**Rich UI:** Use selectors for better UX: `TextSelector`, `NumberSelector`

**Pre-filling:**

- Default values: `vol.Optional("field", default="value")`
- Suggested values: `vol.Optional("field", description={"suggested_value": "value"})`
- Merge from existing: `self.add_suggested_values_to_schema(schema, entry.options)`

## Validation and Error Handling

**Return errors dict for validation failures:** `errors={"base": "cannot_connect"}`

**Common error keys:** `cannot_connect`, `already_configured`, `unknown`

**Pattern:** Try validation -> catch exceptions -> set errors -> re-show form

**MUST log unexpected exceptions:** `_LOGGER.exception("Unexpected exception")`

## Unique IDs

**MUST:**

- Set unique ID: `await self.async_set_unique_id(unique_id)`
- Abort if duplicate: `self._abort_if_unique_id_configured()`
- Use stable identifiers (host-based for local devices)

## Reconfigure Flow

**MUST:**

- Use `self._get_reconfigure_entry()` to access current entry
- Update entry: `return self.async_update_reload_and_abort(entry, data_updates=user_input)`
- Pre-fill form: `self.add_suggested_values_to_schema(schema, entry.data)`

**NEVER:**

- Create new entry (always update existing)
- Use for authentication changes (use reauth)

## Options Flow

**MUST:**

- Return via `async_get_options_flow()`
- Implement `async_step_init()`
- Pre-fill with existing options

## Setup Entry Error Handling

**In `async_setup_entry()` in `__init__.py`:**

- Raise `ConfigEntryNotReady` for temporary failures (device offline, network issues)
- No auth errors needed (local API without authentication)
- **NEVER** log `ConfigEntryNotReady` manually (HA logs at debug automatically)

## Version and Migration

**Define versions in ConfigFlow:**

- `VERSION` - Major (breaking changes), `MINOR_VERSION` - Minor (compatible)

**Implement `async_migrate_entry()` in `__init__.py`:**

- Return `False` for downgrades
- Update via `hass.config_entries.async_update_entry(entry, version=X, minor_version=Y)`

## Rules Summary

**ALWAYS:**

- Validate input before creating entry
- Set unique ID and abort if already configured
- Use translation keys for errors
- Pre-fill forms with current values
- Log unexpected exceptions
- Use `async_forward_entry_setups()` for platform setup
- Implement `async_unload_entry()` for clean teardown

**NEVER:**

- Auto-create entries without user confirmation
- Log `ConfigEntryNotReady` manually
- Mutate ConfigEntry objects directly (use `async_update_entry()` instead)
