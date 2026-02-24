---
agent: "agent"
tools: ["search/codebase", "edit", "search", "runCommands"]
description: "Add a new entity platform (sensor, switch, binary_sensor, etc.) to the integration"
---

# Add Entity Platform

Your goal is to add a new entity platform to this Home Assistant integration.

If not provided, ask for:

- Platform type (sensor, binary_sensor, switch, button, number, select, fan, etc.)
- Initial entity or entities to create
- Data source (from coordinator, API, config)
- Purpose and user benefit

## Implementation Steps

### 1. Create Platform File

**File:** `custom_components/unraid_management_agent/[platform].py`

### 2. Platform Template

```python
"""[Platform] platform for Unraid Management Agent."""

from __future__ import annotations

from homeassistant.components.[platform] import [PlatformEntityClass]
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import UnraidDataUpdateCoordinator
from .entity import UnraidBaseEntity
from .const import DOMAIN

type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up [platform] platform."""
    coordinator = entry.runtime_data.coordinator

    entities: list[[PlatformEntityClass]] = []
    # Add entity creation logic here
    async_add_entities(entities)
```

### 3. Entity Implementation

```python
class Unraid[EntityName](UnraidBaseEntity, [PlatformEntityClass]):
    """Representation of [entity description]."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        description: [EntityDescription],
    ) -> None:
        """Initialize the [entity]."""
        super().__init__(coordinator, description)

    @property
    def [platform_property](self) -> [ReturnType]:
        """Return the [property description]."""
        return self.coordinator.data.[data_key]
```

### 4. Register Platform

Add platform to `custom_components/unraid_management_agent/__init__.py` in the `PLATFORMS` list:

```python
PLATFORMS: list[Platform] = [
    # ... existing platforms ...
    Platform.[NEW_PLATFORM],
]
```

### 5. Add Translations

**`translations/en.json`:**

```json
{
  "entity": {
    "[platform]": {
      "[entity_key]": {
        "name": "[Entity Name]"
      }
    }
  }
}
```

### 6. Verify Integration

Run validation and test:

```bash
scripts/lint           # Linting and formatting
./scripts/develop      # Start Home Assistant for testing
```

## Platform-Specific Guidance

### Sensor

- Use `SensorEntity` and `UnraidSensorEntityDescription`
- Set `native_value` via `value_fn` callable
- Add `device_class`, `state_class`, `native_unit_of_measurement`

### Binary Sensor

- Use `BinarySensorEntity` and `UnraidBinarySensorEntityDescription`
- Set `is_on` via `value_fn` callable
- Add `device_class` (connectivity, problem, etc.)

### Switch

- Use `SwitchEntity`
- Implement `async_turn_on()` and `async_turn_off()`
- Call API via coordinator, then `coordinator.async_request_refresh()`

### Button

- Use `ButtonEntity` and `UnraidButtonEntityDescription`
- Implement `async_press()` method
- Call API via coordinator

## Validation Checklist

- [ ] Platform file created
- [ ] Entity class inherits from both `UnraidBaseEntity` and platform class
- [ ] `_attr_has_entity_name = True` set
- [ ] Entity uses `translation_key`
- [ ] Unique ID set correctly
- [ ] Platform registered in `__init__.py` PLATFORMS list
- [ ] Translations added matching translation_key
- [ ] Icons added to `icons.json`
- [ ] Type hints complete
- [ ] `scripts/lint` passes

**Integration Context:**

- **Domain:** `unraid_management_agent`
- **Class prefix:** `Unraid`
- **Base entity:** `UnraidBaseEntity` in `entity.py`
- **Coordinator:** `UnraidDataUpdateCoordinator`

Follow patterns from existing platforms for consistency.

**DO NOT create tests unless explicitly requested.**
