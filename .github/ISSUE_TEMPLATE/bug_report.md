---
name: Bug Report
about: Report a bug or issue with the integration
title: "[BUG] "
labels: bug
assignees: ''

---

## Describe the Bug
A clear and concise description of what the bug is.

## Steps to Reproduce
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

## Expected Behavior
A clear and concise description of what you expected to happen.

## Actual Behavior
What actually happened instead.

## Environment
- **Home Assistant Version**: (e.g., 2025.12.0)
- **Integration Version**: (e.g., 2025.12.0)
- **Unraid Server Version**: (e.g., 6.12.x)
- **Python Version**: (e.g., 3.13)

## Logs
Please attach relevant Home Assistant logs. Set log level to DEBUG for unraid_management_agent:

```yaml
logger:
  logs:
    custom_components.unraid_management_agent: debug
```

Then paste the logs here:
```
[Paste logs here]
```

## Configuration
If applicable, share your integration configuration (remove sensitive data):
```yaml
[Paste configuration here]
```

## Additional Context
Add any other context about the problem here (screenshots, error messages, etc.).
