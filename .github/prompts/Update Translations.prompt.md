---
agent: "agent"
tools: ["edit", "search", "runCommands"]
description: "Update or add translation strings for entities, config flow, actions, and error messages"
---

# Update Translations

Your goal is to update translation strings for this Home Assistant integration.

If not provided, ask for:

- Which language to update (English is required)
- What to translate (entities, config flow, actions, errors)
- New or changed strings

## Requirements

**Translation Structure:**

- English: `translations/en.json` (always required)
- Follow Home Assistant translation schema
- Keep `strings.json` in sync (root-level copy)

**Common Translation Sections:**

1. **Config Flow:**

   ```json
   "config": {
     "step": {
       "user": {
         "data": {
           "host": "Host",
           "port": "Port"
         },
         "data_description": {
           "host": "Hostname or IP address of your Unraid server"
         }
       }
     },
     "error": {
       "cannot_connect": "Failed to connect"
     },
     "abort": {
       "already_configured": "Device already configured"
     }
   }
   ```

2. **Entity Translations:**

   ```json
   "entity": {
     "sensor": {
       "cpu_usage": {
         "name": "CPU Usage"
       }
     }
   }
   ```

3. **Service Actions:**

   ```json
   "services": {
     "start_array": {
       "name": "Start Array",
       "description": "Start the Unraid disk array"
     }
   }
   ```

4. **Options Flow:**

   ```json
   "options": {
     "step": {
       "init": {
         "data": {
           "use_websocket": "Enable WebSocket"
         }
       }
     }
   }
   ```

5. **Exceptions:**

   ```json
   "exceptions": {
     "action_failed": {
       "message": "Failed to execute action: {error}"
     }
   }
   ```

**Translation Guidelines:**

- Use clear, concise language
- Be consistent with Home Assistant terminology
- Provide helpful descriptions for config options
- Keep error messages user-friendly
- Use sentence case for names, not title case

**Validation:**

- JSON must be valid (no trailing commas, proper quotes)
- Maintain identical structure between `strings.json` and `translations/en.json`
- Run `script/lint` to validate JSON syntax

**Related Files:**

- Strings: `custom_components/unraid_management_agent/strings.json`
- English: `custom_components/unraid_management_agent/translations/en.json`

## Before Finishing

- Validate JSON syntax with `script/lint`
- Restart Home Assistant to load new translations
- Verify translations appear correctly in UI

**DO NOT create tests unless explicitly requested.**
