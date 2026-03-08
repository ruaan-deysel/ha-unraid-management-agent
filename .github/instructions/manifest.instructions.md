---
applyTo: "**/manifest.json"
---

# Manifest Instructions

**Applies to:** `custom_components/unraid_management_agent/manifest.json`

## Current Manifest

```json
{
  "domain": "unraid_management_agent",
  "name": "Unraid Management Agent",
  "codeowners": ["@ruaan-deysel"],
  "config_flow": true,
  "documentation": "https://github.com/ruaan-deysel/ha-unraid-management-agent",
  "integration_type": "device",
  "iot_class": "local_push",
  "issue_tracker": "https://github.com/ruaan-deysel/ha-unraid-management-agent/issues",
  "requirements": [],
  "version": "2026.2.2"
}
```

## Field Reference

**Core fields:**

- `domain` - `unraid_management_agent` (matches directory name, never change)
- `name` - `Unraid Management Agent` (display name in HA)
- `version` - CalVer format `YYYY.M.P` (required for HACS)
- `documentation` - Link to GitHub repository
- `issue_tracker` - Link to GitHub issues (required for HACS)
- `codeowners` - GitHub usernames for notifications

**Integration behavior:**

- `config_flow` - `true` (UI-based configuration)
- `integration_type` - `device` (represents physical devices)
- `iot_class` - `local_push` (local device with WebSocket push updates)
- `requirements` - Only direct external Python package dependencies required at runtime

## IoT Class

This integration uses `local_push`:

- **local** - Communicates with Unraid server on local network
- **push** - WebSocket provides real-time updates (with 30s polling fallback)

## Requirements Format

```json
"requirements": []
```

Use `requirements` only for true external packages. Vendored modules under the integration package must not be listed here.

## Version

This project uses CalVer: `YYYY.M.P` (e.g., `2026.2.2`)

- `YYYY` - Year
- `M` - Month (no leading zero)
- `P` - Patch number

## Common Mistakes

- Missing `version` (required for HACS)
- Missing `issue_tracker` (required for HACS)
- Wrong `domain` (must match directory name)
- Invalid `iot_class` value
- Trailing commas in JSON
