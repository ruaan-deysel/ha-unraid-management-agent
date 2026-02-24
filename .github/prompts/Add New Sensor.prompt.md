---
agent: "agent"
tools: ["search/codebase", "edit", "search", "runCommands"]
description: "Add a new sensor entity with proper structure, coordinator integration, and translations"
---

# Add New Sensor

Your goal is to add a new sensor entity to this Home Assistant integration.

If not provided, ask for:

- Sensor name and purpose
- Data type (temperature, humidity, battery, etc.)
- Unit of measurement (if applicable)
- Device class (if applicable)
- State class (measurement, total, total_increasing)
- Which UMA API data field provides the value

## Requirements

**Entity Implementation:**

- Add a new `UnraidSensorEntityDescription` to the appropriate sensor list in `sensor.py`
- Use `value_fn` callable to extract data from coordinator
- Use `extra_state_attributes_fn` for additional attributes (if needed)
- Add proper type hints

**Data Flow:**

- Sensor must read data from `self.coordinator.data` via the `value_fn`
- Never fetch data directly in entity -- use coordinator pattern
- Handle missing data gracefully (return `None` from `value_fn`)

**Entity Description Pattern:**

```python
UnraidSensorEntityDescription(
    key="new_sensor_key",
    translation_key="new_sensor_key",
    device_class=SensorDeviceClass.TEMPERATURE,  # if applicable
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # if applicable
    entity_category=None,  # or EntityCategory.DIAGNOSTIC
    value_fn=lambda data: data.system_info.some_value if data.system_info else None,
    extra_state_attributes_fn=lambda data: {"detail": data.system_info.detail} if data.system_info else {},
),
```

**State Class Guidance:**

- `MEASUREMENT`: Value can increase or decrease (temperature, humidity, CPU usage)
- `TOTAL_INCREASING`: Monotonically increasing counter (energy consumed, data transferred)
- `TOTAL`: Like TOTAL_INCREASING but resets are allowed

**Collector Filtering:**

This integration uses collector-based entity filtering. Ensure the new sensor checks if its collector is enabled:

```python
if not coordinator.is_collector_enabled("collector_name"):
    return  # Skip entity creation
```

**Translations:**

- Add sensor name to `translations/en.json` under `entity.sensor.[sensor_key].name`
- Translation key must match `translation_key` in EntityDescription
- With `has_entity_name=True`, entity name comes from translations

**Icons:**

- Add icon to `icons.json` under `entity.sensor.[sensor_key].default`
- Use Material Design Icons (MDI)

**Code Quality:**

- Follow existing sensor patterns in `sensor.py`
- Use constants from `const.py` for keys
- Add proper docstrings (Google-style)
- Run `scripts/lint` to validate before completion

**Related Files:**

- Sensors: `custom_components/unraid_management_agent/sensor.py`
- Translations: `custom_components/unraid_management_agent/translations/en.json`
- Icons: `custom_components/unraid_management_agent/icons.json`
- Constants: `custom_components/unraid_management_agent/const.py`

**DO NOT create tests unless explicitly requested.**
