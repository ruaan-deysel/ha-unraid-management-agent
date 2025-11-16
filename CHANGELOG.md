# Changelog

All notable changes to the Unraid Management Agent Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2025.11.2] - 2025-11-16

### Fixed

- Fixed VM switch attributes showing "Unknown" values for vCPUs
- Fixed missing import for `ATTR_VM_MEMORY` constant causing integration errors
- Fixed vCPUs attribute to use correct API field name (`cpu_count` instead of `vcpus`)

### Added

- Added comprehensive VM switch attributes:
  - Guest CPU percentage
  - Host CPU percentage
  - Memory display (formatted string)
  - Disk I/O (read/write rates with human-readable formatting)
- Added `_format_bytes()` helper method for human-readable byte formatting

### Changed

- **Major README.md improvements based on comprehensive audit**:
  - Fixed sensor count from "13+ entities" to "30+ base entities" to accurately reflect actual implementation
  - Corrected GPU Sensors count from 4 to 3 (removed non-existent "GPU Name" sensor)
  - Added missing Disk Sensors section documenting disk usage, disk health, Docker vDisk, and log filesystem sensors
  - Added missing System Sensors: Motherboard Temperature (conditional) and Fan Speed (dynamic)
  - Added missing UPS Power sensor (Energy Dashboard compatible)
  - Fixed Network Sensors units from "bytes" to "bits/s" for accuracy
  - Added comprehensive Services section documenting all 18 available services (container, VM, array, parity check)
  - Updated example automations with correct entity ID format including hostname
  - Added new example automations for disk health monitoring and container auto-restart
- Enhanced README.md with comprehensive Prerequisites section
- Added HACS installation badge for one-click installation
- Improved documentation with detailed Unraid Management Agent plugin installation instructions

## [2025.11.1] - 2025-11-07

### Fixed

- Fixed container/VM switch state synchronization issue where switches would jump back to previous state after toggling
- Implemented optimistic state handling for switches to provide immediate UI feedback

### Added

- Automated GitHub release workflow for streamlined version releases
- Comprehensive release process documentation in `docs/RELEASE_PROCESS.md`
- CHANGELOG.md for tracking version history
- Release section in README.md with version information

### Changed

- Updated README.md with releases section and contributing guidelines

## [2025.10.3] - 2024-10-XX

### Added

- Initial release of the Unraid Management Agent Home Assistant integration
- System monitoring sensors (CPU, RAM, temperature, uptime)
- Array and storage sensors (array usage, parity check progress, disk usage)
- GPU monitoring sensors (conditional, when GPU detected)
- UPS monitoring sensors (conditional, when UPS detected)
- Network monitoring sensors (dynamic, per interface)
- Binary sensors for status indicators (array started, parity check running, etc.)
- Container switches for Docker container control
- VM switches for virtual machine control
- Buttons for array and parity check control
- WebSocket support for real-time updates
- REST API fallback when WebSocket unavailable
- SMART health status monitoring for disks
- Disk standby state detection (prevents spinning up disks)
- Energy dashboard compatibility for UPS power sensor

### Features

- **Entity Format v2**: Uses `has_entity_name = True` pattern
- **Data Coordinator Pattern**: Centralized data management
- **Dynamic Entities**: Automatically creates entities for fans, disks, network interfaces, containers, and VMs
- **Conditional Entities**: GPU and UPS sensors only created when hardware detected
- **Single Device**: All entities grouped under one Unraid server device
- **Real-time Updates**: WebSocket client with automatic reconnection
- **Comprehensive Attributes**: Rich contextual information for all entities
- **HACS Compatible**: Installable via Home Assistant Community Store

### Requirements

- Home Assistant 2024.1.0 or newer
- Unraid Management Agent v2025.11.0 or newer running on Unraid server
- Python 3.11 or newer
- aiohttp 3.9.0 or newer

---

## Release Notes Format

For future releases, use this format:

```markdown
## [VERSION] - YYYY-MM-DD

### Added

- New features

### Changed

- Changes to existing functionality

### Deprecated

- Soon-to-be removed features

### Removed

- Removed features

### Fixed

- Bug fixes

### Security

- Security fixes
```

---

[Unreleased]: https://github.com/ruaan-deysel/ha-unraid-management-agent/compare/v2025.11.1...HEAD
[2025.11.1]: https://github.com/ruaan-deysel/ha-unraid-management-agent/compare/v2025.10.3...v2025.11.1
[2025.10.3]: https://github.com/ruaan-deysel/ha-unraid-management-agent/releases/tag/v2025.10.3
