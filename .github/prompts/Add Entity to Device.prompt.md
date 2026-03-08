---
agent: "agent"
tools: ["search/codebase", "edit", "search", "runCommands"]
description: "Add a new entity to an existing device while maintaining proper device grouping"
---

# Add Entity to Device

Your goal is to add a new entity to an existing device in this Home Assistant integration.

If not provided, ask for:

- Entity type (sensor, binary_sensor, switch, button, etc.)
- Entity name and purpose
- Which device it belongs to (Unraid server)
- Data source from coordinator

## Requirements

**Entity Implementation:**

- Add entity description to appropriate platform file
- Inherit from platform base class and `UnraidBaseEntity` (in that MRO order)
- Use `UnraidSensorEntityDescription` (or similar) with `value_fn` and `extra_state_attributes_fn`
- Access data through `coordinator.data` — never call API directly

**Device Grouping:**

- All entities share the same device via `UnraidBaseEntity`
- Device info is built from coordinator data (manufacturer, model, serial, firmware)
- Unique ID format: `{entry_id}_{description.key}`
- Ensure no unique_id collisions with existing entities

**Platform Registration:**

- Add description to the appropriate description list (e.g., `SYSTEM_SENSORS`, `DISK_SENSORS`)
- Ensure entity is yielded by `async_setup_entry`
- Maintain alphabetical order within description groups

**Coordinator Data:**

- Entity must read from `self.coordinator.data`
- Use `value_fn(coordinator)` pattern for state values
- Handle missing data gracefully — return `None` for unavailable states
- Leverage uma-api computed properties where available

**Translations:**

- Add entity name to `strings.json` under `entity.{platform}.{key}.name`
- Update `translations/en.json` to match `strings.json`
- Use placeholders in code — functionality works without translations

**Verification:**

- Run `script/lint` to validate code quality
- Verify entity description follows existing patterns in the platform file
- Check that `value_fn` handles `None` coordinator data

**Related Files:**

- Entity: `custom_components/unraid_management_agent/{platform}.py`
- Base Entity: `custom_components/unraid_management_agent/entity.py`
- Coordinator: `custom_components/unraid_management_agent/coordinator.py`
- Constants: `custom_components/unraid_management_agent/const.py`
- Translations: `custom_components/unraid_management_agent/strings.json`
- Agent docs: Reference [#file:AGENTS.md]

**DO NOT create tests unless explicitly requested.**
