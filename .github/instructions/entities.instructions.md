---
applyTo: "custom_components/unraid_management_agent/sensor.py, custom_components/unraid_management_agent/binary_sensor.py, custom_components/unraid_management_agent/switch.py, custom_components/unraid_management_agent/button.py, custom_components/unraid_management_agent/entity.py"
---

# Entity Platform Instructions

**Applies to:** All entity platform implementations and entity base classes

## Base Entity Inheritance

**MUST inherit from:** `(PlatformEntity, UnraidBaseEntity)` -- order matters for MRO

**Base class provides:** Coordinator integration, device info, unique ID (`{entry_id}_{description.key}`), entity naming

**You implement:** Platform-specific properties/methods (`native_value`, `is_on`, `async_press`, etc.)

**Constructor:** Call `super().__init__(coordinator, entity_description)` -- base handles setup

## Entity Descriptions

This integration uses custom entity descriptions with callable fields:

**Sensor pattern:**

```python
UnraidSensorEntityDescription(
    key="cpu_usage",
    translation_key="cpu_usage",
    device_class=SensorDeviceClass.POWER_FACTOR,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    value_fn=lambda data: data.system_info.cpu_usage if data.system_info else None,
    extra_state_attributes_fn=lambda data: {...} if data.system_info else {},
)
```

**Entity Categories:**

- `None` -- Primary functionality (prominent display)
- `EntityCategory.DIAGNOSTIC` -- Diagnostic info (uptime, signal, errors)
- `EntityCategory.CONFIG` -- Configuration settings

## Coordinator Data Access

**MUST use coordinator only:** Access via `value_fn` callable on description

**NEVER call API directly:** No `self.coordinator.client` in entities

**Handle missing data:** Return `None` from `value_fn` when data unavailable

## Collector Filtering

This integration filters entities based on enabled collectors:

```python
if not coordinator.is_collector_enabled("gpu"):
    return  # Skip GPU entities
```

## Platform-Required Methods

**Must implement per platform:**

- Sensors: `native_value` (via `value_fn`)
- Binary Sensors: `is_on` (via `value_fn`)
- Switches: `is_on`, `async_turn_on()`, `async_turn_off()`
- Buttons: `async_press()`

## Dynamic Entity Creation

Switches and buttons are created dynamically based on available containers, VMs, etc.

**Pattern:** Iterate over coordinator data to create entities for each resource.

## Common Pitfalls

**Don't:**

- Call API directly from entities
- Hardcode unique IDs
- Log in property getters (called frequently)
- Override base class methods unnecessarily

**Do:**

- Use coordinator data exclusively via `value_fn`
- Generate unique IDs from `entry_id + description.key`
- Log only in async methods or `__init__`
- Use stable identifiers for dynamic entities (name-based, not index-based)
