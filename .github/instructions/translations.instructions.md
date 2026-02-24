---
applyTo: "**/translations/*.json, **/strings.json"
---

# Translation Files Instructions

**Applies to:** `custom_components/unraid_management_agent/translations/*.json` and `strings.json`

## File Location

**Custom integrations** use the `translations/` folder with language-specific files:

- `strings.json` - Source strings (English, used to generate `translations/en.json`)
- `translations/en.json` - English (auto-generated from `strings.json`)
- `translations/de.json`, etc. - Additional languages

**Language codes:** BCP47 format (e.g., `en`, `de`, `fr-CA`)

## Critical Instructions

### Translation Placeholders

**Runtime values:** Use `{variable}` syntax -- replaced with actual values at runtime

- Never translate placeholder names (e.g., `{host}` stays `{host}`)
- Placeholder names must match code exactly

**CRITICAL: Quotes inside string values:**

- `"Service {service} is unavailable"` (no quotes around placeholder)
- `"Service \"{service}\" is unavailable"` (escaped double quotes)
- Single quotes around placeholders cause hassfest errors

**Key references:** Use `[%key:...]` syntax to reuse translations

```json
{
  "config": {
    "error": {
      "cannot_connect": "Cannot connect to Unraid server",
      "connection_error": "[%key:component::unraid_management_agent::config::error::cannot_connect%]"
    }
  }
}
```

**Reference Home Assistant common strings:**

```json
"state": {
  "off": "[%key:common::state::off%]",
  "on": "[%key:common::state::on%]"
}
```

### Entity Translations

**Requirements in code:**

- Set `has_entity_name=True` on entity
- Set `translation_key` property to match JSON key
- For placeholders: Set `translation_placeholders` dict

**Example:**

```json
"entity": {
  "sensor": {
    "cpu_usage": {
      "name": "CPU Usage"
    },
    "array_status": {
      "name": "Array Status",
      "state": {
        "started": "Started",
        "stopped": "Stopped"
      }
    }
  }
}
```

### Markdown Support

These fields support Markdown formatting:

- Config/Options: `description`, `abort`, `progress`, `create_entry`
- Issues: `title`, `description`

### Proper Nouns

**Never translate:**

- Home Assistant
- Unraid
- HACS
- Brand names (Docker, KVM, etc.)

## Structure

```json
{
  "config": {
    "step": { "user": { "title": "...", "data": { "host": "..." } } },
    "error": { "cannot_connect": "..." },
    "abort": { "already_configured": "..." }
  },
  "options": { ... },
  "entity": {
    "sensor": { "<translation_key>": { "name": "..." } },
    "binary_sensor": { ... },
    "switch": { ... },
    "button": { ... }
  },
  "exceptions": {
    "<exception_key>": { "message": "..." }
  },
  "services": {
    "<action_name>": { "name": "...", "description": "..." }
  },
  "issues": {
    "<issue_id>": { "title": "...", "description": "..." }
  }
}
```

## Common Mistakes

- Translating placeholder names (`{host}` -> `{hôte}`)
- Translating proper nouns (Unraid, Home Assistant)
- Missing `translation_key` in entity code
- Using entity translations without `has_entity_name=True`
- Inconsistent key structure across language files
- Invalid JSON syntax (trailing commas, comments)
- Wrong key reference syntax (must be exact: `[%key:...]`)

## Best Practices

1. Use key references `[%key:...]` to avoid duplicate translations
2. Keep consistent terminology within and across languages
3. Provide helpful descriptions for non-obvious fields in `data_description`
4. All language files must have identical structure -- only values differ

## References

- [Custom Integration Localization](https://developers.home-assistant.io/docs/internationalization/custom_integration)
- [Backend Localization](https://developers.home-assistant.io/docs/internationalization/core)
