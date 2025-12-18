---
name: Feature Request
about: Suggest an enhancement for the Unraid Management Agent integration
title: "[FEATURE] "
labels: enhancement
assignees: ''

---

## What Unraid Component?
Select what you want to monitor/control:
- [ ] System metrics (CPU, RAM, temp)
- [ ] Array & disk management
- [ ] Docker containers
- [ ] Virtual machines
- [ ] ZFS pools/datasets
- [ ] GPU monitoring
- [ ] Network interfaces
- [ ] UPS / Power monitoring
- [ ] Notifications
- [ ] User scripts
- [ ] Other: ___

## Feature Description
A clear and concise description of the feature you want to add.

## Use Case
Why would this be helpful? What problem does it solve?

## Proposed Implementation
How would you like this feature to work? What entities/sensors would be created?

```yaml
# Example:
# New sensor: sensor.unraid_[hostname]_feature_name
# New switch: switch.unraid_[hostname]_feature_toggle
```

## Data Requirements
What data from Unraid would be needed? Is this available from the Unraid Management Agent API?

## Alternatives Considered
Any alternative approaches or existing workarounds?

## Related Issues
Link any related issues here (e.g., Related to #456).
