---
applyTo: "**/services.yaml"
---

# Service Actions Definition Instructions

**Applies to:** `services.yaml` (service action definitions)

**Note:** The filename `services.yaml` is legacy. Use "service actions" in code/documentation and "actions" for users.

## Structure

```yaml
action_name:
  name: Human-Readable Name
  description: Clear description of what the action does.
  fields:
    parameter_name:
      name: Parameter Name
      description: What this parameter does.
      required: true
      example: "example_value"
      selector:
        text:
  target:
    entity:
      - domain: sensor
```

## Key Requirements

**Service action definition:**

- `name` - User-visible name (required)
- `description` - Clear explanation with Markdown support (required)
- `fields` - Parameter definitions (optional)
- `target` - Entity/device/area selector (optional)

**Field definition:**

- `name` - Field display name (required)
- `description` - Field explanation (required)
- `required` - Boolean, default false
- `example` - Example value (recommended)
- `selector` - UI selector type (recommended)

## Common Selectors

- `text:` - String input
- `number:` - Numeric input with optional min/max/step
- `boolean:` - Toggle switch
- `select:` - Dropdown with options
- `entity:` - Entity picker with optional domain filter
- `device:` - Device picker

## Target Selector

Use `target:` to allow users to select entities, devices, or areas:

```yaml
start_container:
  name: Start Container
  description: Starts a Docker container.
  target:
    entity:
      - domain: switch
```

**Important:** If `target:` is defined, do NOT define `entity_id` as a field.

## Best Practices

- Always provide meaningful descriptions
- Include realistic examples for complex fields
- Use appropriate selectors for better UI
- Mark fields as required only when necessary
- Keep action names verb-based (e.g., `start_container`, `stop_vm`)
