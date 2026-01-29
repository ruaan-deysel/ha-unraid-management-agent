---
name: Bug Report
about: Report a bug or issue with the Unraid Management Agent integration
title: "[BUG] "
labels: bug
assignees: ""
---

> Important: If this bug is for the Unraid Management Agent backend/plugin/API (not the Home Assistant integration), please open it here instead: https://github.com/ruaan-deysel/unraid-management-agent/issues/new/choose

## Describe the Bug

A clear and concise description of what the bug is.

## Steps to Reproduce

Steps to reproduce the behavior:

1. ...
2. ...
3. See error

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

What actually happened instead.

## Unraid & Integration Setup

- **Home Assistant Version**: (e.g., 2025.12.0)
- **Integration Version**: (e.g., 2025.12.0)
- **Unraid Server Version**: (e.g., 6.12.x)
- **Unraid Management Agent Plugin Version**: (find in Unraid plugins page)
- **Connection Type**: WebSocket / REST API Polling (which one are you using?)
- **Network**: Local network / Remote (VPN/Cloud)

## Unraid Details

- **Array Status**: Stopped / Degraded / Optimal
- **Plugins Installed**: (list any relevant Unraid plugins)
- **Custom Scripts**: (any relevant custom scripts running?)
- **ZFS Pools**: (are you using ZFS?)

## Home Assistant Logs

Set log level to DEBUG for the integration:

```yaml
logger:
  logs:
    custom_components.unraid_management_agent: debug
```

Restart Home Assistant and attach the complete error/warning logs:

```
[Paste logs here - include full tracebacks]
```

## Configuration

Share your integration configuration (remove sensitive data like IP, tokens, etc.):

```yaml
# From Settings > Devices & Services > Unraid Management Agent
[Paste config details here]
```

## Diagnostic Information

- [ ] Unraid Management Agent plugin is installed and running
- [ ] Can access Unraid Management Agent UI directly (http://unraid-ip:port)
- [ ] Integration was previously working (is this a new setup or regression?)
- [ ] Error persists after restarting Home Assistant

## Additional Context

Add screenshots, error messages, or any other relevant information.
