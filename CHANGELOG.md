# Changelog

All notable changes to the Unraid Management Agent Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2025.12.0] - 2025-12-18

### Fixed

- **Sensor Setup Crash**: Fixed 'NoneType' object is not iterable error when fan data is None
  - Added null-safe guards for system and fans data in sensor setup
  - Fan sensor lookup now tolerates missing or None fan arrays
  - Regression test ensures setup succeeds gracefully when fans data is None

## [2025.11.8] - 2025-11-18

### Added

- **ZFS Storage Pool Monitoring**: Comprehensive ZFS storage pool support with real-time monitoring
  - New `sensor.{hostname}_zfs_pool_{pool_name}_usage` - ZFS pool capacity usage percentage
    - Attributes: pool_name, pool_guid, health, state, size, allocated, free, fragmentation_percent, dedup_ratio, readonly, autoexpand, autotrim
  - New `sensor.{hostname}_zfs_pool_{pool_name}_health` - ZFS pool health status
    - Attributes: state, has_problem (boolean), read_errors, write_errors, checksum_errors, scan_errors, vdevs (array with per-vdev details)
  - New `sensor.{hostname}_zfs_arc_hit_ratio` - ZFS ARC cache hit ratio percentage
    - Attributes: size (GB), target_size (GB), min_size (GB), max_size (GB), mru_hit_ratio_percent, mfu_hit_ratio_percent, hits, misses
  - New `binary_sensor.{hostname}_zfs_available` - Indicates if ZFS is installed and detected on the Unraid server
    - Attributes: pool_count (number of ZFS pools detected)
  - Dynamic entity creation: One set of sensors created per ZFS pool
  - Conditional entity creation: ZFS sensors only created when ZFS pools are detected (prevents phantom entities)
  - Real-time updates via WebSocket for instant pool status changes
  - Comprehensive vdev (virtual device) information including per-vdev health and error counts

### Technical Details

- **ZFS API Integration**: Added support for new Unraid Management Agent ZFS API endpoints
  - `/api/v1/zfs/pools` - List all ZFS pools with detailed metrics
  - `/api/v1/zfs/datasets` - List all ZFS datasets
  - `/api/v1/zfs/snapshots` - List all ZFS snapshots
  - `/api/v1/zfs/arc` - ZFS ARC (Adaptive Replacement Cache) statistics
- **ZFS Metrics Tracked**:
  - Pool capacity: size, allocated, free space in bytes and GB
  - Pool health: health status, state, error counts (read, write, checksum, scan)
  - Pool fragmentation: percentage of fragmented space
  - Pool configuration: dedup ratio, readonly status, autoexpand, autotrim settings
  - ARC cache: hit ratio, size metrics (current, target, min, max), MRU/MFU hit ratios
  - Vdev details: per-vdev name, type, state, and error counts
- **Conditional Creation Logic**: ZFS entities only created when `zfs_pools` data exists, is a non-empty list, and contains valid pool information
- **WebSocket Events**: Added handlers for `zfs_pool_update`, `zfs_dataset_update`, `zfs_snapshot_update`, `zfs_arc_update` events
- **Entity Organization**: All ZFS sensors follow the same naming and attribute patterns as existing disk sensors for consistency

### Changed

- **Sensor Organization**: Streamlined ZFS sensor structure for better usability
  - Moved ZFS pool fragmentation from separate sensor to attribute of pool usage sensor
  - Moved ZFS ARC size from separate sensor to attribute of ARC hit ratio sensor
  - Moved ZFS pool problem status from binary sensor to `has_problem` attribute of pool health sensor
  - Reduced total sensor count while maintaining all functionality through comprehensive attributes

## [2025.11.7] - 2025-11-17

### Fixed

- **UPS Sensor Creation Bug**: Fixed UPS sensors being incorrectly created when no UPS hardware is connected to Unraid server
  - UPS sensors (battery, load, runtime, power, energy) are now only created when a UPS is actually present and connected
  - UPS Connected binary sensor is now only created when UPS hardware is detected
  - Improved detection logic to properly distinguish between "no UPS hardware" vs "UPS disconnected"
  - When the Unraid Management Agent API returns null or error for the UPS endpoint (no UPS present), the integration now correctly skips UPS entity creation
  - Added validation to check that UPS data is not an empty dictionary before creating entities
  - This prevents phantom UPS entities from appearing in Home Assistant for users without UPS hardware

### Changed

- **UPS Detection Logic**: Enhanced UPS presence detection with more robust validation
  - Now checks that UPS data exists, is a non-empty dictionary, and contains valid UPS information
  - Sensor creation requires both non-empty UPS data AND `connected: true` status
  - Binary sensor creation requires non-empty UPS data (will show connection status)
  - Prevents entity creation when API returns empty dict `{}` due to missing UPS hardware

## [2025.11.6] - 2025-11-17

### Added

- **Energy Dashboard Compatibility**: Added UPS Energy and GPU Energy sensors for Home Assistant Energy Dashboard
  - New `sensor.{hostname}_ups_energy` - Tracks cumulative UPS energy consumption in kWh
  - New `sensor.{hostname}_gpu_energy` - Tracks cumulative GPU energy consumption in kWh
  - Both sensors use trapezoidal integration to convert instantaneous power (W) to cumulative energy (kWh)
  - Sensors have `device_class: energy` and `state_class: total_increasing` for Energy Dashboard compatibility
  - Users can now add UPS and GPU to the "Individual Devices" section of the Energy Dashboard
  - Energy sensors automatically integrate power readings over time with high accuracy
  - Includes `integration_method: trapezoidal` and `source_sensor` attributes for transparency
  - Compatible with Home Assistant's long-term statistics and energy tracking features

### Technical Details

- Energy sensors use the trapezoidal rule for numerical integration: `energy = (power1 + power2) / 2 * time_delta`
- Integration happens on every coordinator update, providing accurate energy tracking
- Sensors maintain internal state for cumulative energy calculation across Home Assistant restarts
- Zero point automatically set by Home Assistant recorder for statistics compilation

## [2025.11.5] - 2025-11-17

### Fixed

- **Share Sensor Attributes**: Fixed incorrect attribute values in file share sensors
  - Changed from using `size_bytes` field to `total_bytes` field to match the actual API response
  - Share sensors now correctly display `size`, `used`, and `free` attributes in GB
  - Previously, share sensors would show "Unknown" for all size attributes due to field name mismatch

### Added

- **UPS Power Sensor Enhancements**: Enhanced UPS Power sensor with rich, user-friendly attributes for better Energy Dashboard integration
  - Added `energy_dashboard_ready` indicator for easy identification
  - Added `rated_power` attribute showing UPS nominal power (e.g., "800W")
  - Added `load_status` with user-friendly descriptions ("Very Light", "Light", "Moderate", "High", "Very High - Check connected devices")
  - Added `battery_status` with user-friendly descriptions ("Excellent", "Good", "Fair", "Low", "Critical")
  - Added `estimated_runtime` with human-readable formatting (e.g., "1h 40m" or "100m")
  - Added `current_load` attribute showing load percentage (e.g., "13%")
  - Added `battery_charge` attribute showing battery percentage (e.g., "100%")
  - Retained raw `runtime_seconds` value for automation purposes
  - Improved Energy Dashboard compatibility with comprehensive power monitoring attributes

### Changed

- **Entity Categories**: Moved Docker vDisk Usage, Log Filesystem Usage, and Parity Check Progress sensors from Diagnostic category to main Sensors category
  - These sensors are now more prominently displayed in the Home Assistant UI
  - Users can more easily monitor these important system metrics without navigating to diagnostic entities

## [2025.11.4] - 2025-11-17

### Added

- **Management Agent Version Support**: Added support for the new `agent_version` field from Unraid Management Agent API v2025.11.22+
  - Device info now includes Management Agent version in the `hw_version` field
  - Uptime sensor attributes now include `management_agent_version` for diagnostics
  - Enables version-specific compatibility checks and better troubleshooting
  - Automatically displays both Unraid OS version and Management Agent version in device information

### Fixed

- **Motherboard Temperature Sensor**: Fixed conditional creation logic to properly handle `0°C` readings
  - Changed from `if system_data.get("motherboard_temp_celsius"):` to `if system_data.get("motherboard_temp_celsius") is not None:`
  - Previously, the sensor would not be created when the motherboard temperature was exactly `0°C` (a valid reading)
  - Now correctly distinguishes between field not existing (`None`) and field existing with value `0`

### Changed

- Device information now displays Management Agent version alongside Unraid OS version for complete version tracking
- Enhanced diagnostics with Management Agent version information in Uptime sensor attributes

### Technical Details

- The `agent_version` field was added to the Unraid Management Agent API in v2025.11.22 (GitHub issue #26)
- The integration automatically detects and uses the `agent_version` field when available
- Backward compatible with older Management Agent versions that don't provide `agent_version`
- The motherboard temperature sensor fix ensures proper sensor creation regardless of temperature value

### Requirements

- **Recommended**: Unraid Management Agent v2025.11.22 or later for full feature support
- **Minimum**: Unraid Management Agent v2025.11.0 (earlier versions will work but won't display Management Agent version)

## [2025.11.3] - 2025-11-17

### Fixed

- **CRITICAL**: Fixed multiple WebSocket event detection bugs causing delayed real-time updates
  - **VM Event Detection**: Changed from checking for `vcpus` field to `cpu_count` field
    - VM state changes were delayed by up to 30 seconds instead of updating in real-time
    - VM events were being incorrectly classified as "unknown" and ignored
  - **GPU Event Detection**: Fixed to handle GPU data as arrays instead of single objects
    - GPU events were being incorrectly classified as "unknown" and ignored
    - GPU metrics now update in real-time via WebSocket instead of relying on 30-second polling
  - **Disk Event Detection**: Changed from checking for non-existent `mount_point` field to `status` and `filesystem` fields
    - Disk events were being incorrectly classified as "unknown" and ignored
    - Disk state changes now update in real-time via WebSocket
  - **Share Event Detection**: Changed from checking for `size_bytes` field to `total_bytes` field
    - Share events were being incorrectly classified as "unknown" and ignored
    - Share usage now updates in real-time via WebSocket

### Impact

- Users on v2025.11.2 experiencing delayed state updates for VMs, GPUs, disks, and shares should upgrade immediately
- All affected entities now receive real-time updates via WebSocket instead of waiting for the 30-second polling interval
- This significantly improves responsiveness for automations and dashboards monitoring these entities

### Technical Details

- The bugs were introduced when the Unraid Management Agent API field names changed
- The switch.py and sensor.py files were updated in v2025.11.2 to use the new field names, but the WebSocket event detection logic was not updated
- GPU events come as arrays from the API, but the detection logic was expecting single objects
- All four event types are now correctly identified and processed in real-time

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
