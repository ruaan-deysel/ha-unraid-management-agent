# Unraid® Management Agent - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/ruaan-deysel/ha-unraid-management-agent.svg)](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases)
[![codecov](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent)
[![CI](https://github.com/ruaan-deysel/ha-unraid-management-agent/workflows/CI/badge.svg)](https://github.com/ruaan-deysel/ha-unraid-management-agent/actions/workflows/ci.yml)
[![Community Forum](https://img.shields.io/badge/Community-Forum-blue)](https://community.home-assistant.io/t/unraid-integration)
[![License](https://img.shields.io/github/license/ruaan-deysel/ha-unraid-management-agent.svg)](https://github.com/ruaan-deysel/ha-unraid-management-agent/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ruaan-deysel/ha-unraid-management-agent)

Complete Home Assistant custom integration for monitoring and controlling Unraid servers via the Unraid Management Agent.

## Features

### 🔍 Comprehensive Monitoring

- **System Metrics**: CPU usage, RAM usage, CPU temperature, uptime
- **Array Status**: Array state, disk usage, parity check progress
- **ZFS Storage**: Pool capacity, health, fragmentation, ARC cache statistics
- **GPU Metrics**: GPU utilization, temperature, power consumption (Intel/NVIDIA/AMD)
- **Network**: Interface status, bandwidth monitoring (RX/TX)
- **UPS**: Battery level, load, runtime estimation
- **Containers**: Docker container status and metrics
- **Virtual Machines**: VM status and resource allocation

### 🎮 Full Control

- **Docker Containers**: Start, stop, restart containers via switches
- **Virtual Machines**: Start, stop, restart VMs via switches
- **Array Management**: Start/stop array with buttons
- **Parity Checks**: Start/stop parity checks with buttons
- **System Power Actions**: Reboot and shutdown buttons with explicit system-status tracking

### ⚡ Real-Time Updates

- **WebSocket Support**: Instant state updates (<1s latency)
- **Automatic Fallback**: Falls back to REST API polling if WebSocket fails
- **Exponential Backoff**: Smart reconnection strategy
- **No Data Loss**: Seamless transition between WebSocket and polling

### 🧠 Smart Entity Management

- **Collector-Based Filtering**: Only creates entities for enabled collectors on your Unraid server
- **Physical Disk Detection**: Automatically filters out virtual disks (docker_vdisk, log) and empty disk slots
- **Dynamic Discovery**: Automatically discovers containers, VMs, disks, network interfaces, and more
- **Minimal Clutter**: Disabled collectors result in no orphan entities

### 🏠 Home Assistant Native

- **UI Configuration**: No YAML required for setup
- **Device Grouping**: All entities grouped under single device
- **Proper Device Classes**: Temperature, power, battery, duration, etc.
- **State Classes**: Support for statistics and long-term data
- **MDI Icons**: Beautiful Material Design Icons for all entities
- **Extra Attributes**: Contextual information for each entity

## Prerequisites

Before installing this Home Assistant integration, you **must** have the Unraid Management Agent plugin installed and running on your Unraid server.

### 1. Install Unraid Management Agent Plugin

The Unraid Management Agent is a plugin that runs on your Unraid server and provides the API that this Home Assistant integration connects to.

#### Option A: Install via Community Applications (Recommended)

1. Open your Unraid web interface
2. Go to **Apps** tab
3. Search for **"Unraid Management Agent"**
4. Click **Install**
5. Configure the plugin settings (default port: 8043)
6. Start the plugin

#### Option B: Manual Installation via Plugin URL

1. Open your Unraid web interface
2. Go to **Plugins** tab
3. Click **Install Plugin**
4. Paste this URL:
   ```
   https://raw.githubusercontent.com/ruaan-deysel/unraid-management-agent/main/unraid-management-agent.plg
   ```
5. Click **Install**
6. Configure the plugin settings (default port: 8043)
7. Start the plugin

#### Verify Plugin Installation

After installation, verify the plugin is running by accessing:

```
http://<your-unraid-ip>:8043/api/v1/health
```

You should see a JSON response indicating the service is healthy.

### 2. System Requirements

- **Unraid Server**: Unraid 6.9.0 or newer
- **Home Assistant**: 2025.1 or newer
- **Network**: Home Assistant must be able to reach your Unraid server on port 8043 (or your configured port)

### 3. Network Configuration

Ensure your firewall allows:

- **Port 8043** (or your configured port) for REST API communication
- **WebSocket connections** on the same port for real-time updates

---

## Installation

### Via HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ruaan-deysel&repository=ha-unraid-management-agent&category=integration)

**Manual HACS Installation:**

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the **⋮** menu → **Custom repositories**
4. Add this repository: `https://github.com/ruaan-deysel/ha-unraid-management-agent`
5. Category: **Integration**
6. Click **Add**
7. Search for **Unraid Management Agent**
8. Click **Download**
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [Releases](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases) page
2. Extract the `unraid_management_agent` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

### Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Unraid Management Agent"
4. Enter your Unraid server details:
   - Host: `192.168.1.100` (your Unraid IP)
   - Port: `8043` (default)
   - Enable WebSocket: `true` (recommended)

### Configuration Parameters

- **Host**: IP address or DNS name of your Unraid server
- **Port**: Port exposed by the Unraid Management Agent plugin, `8043` by default
- **Enable WebSocket**: Recommended. Keeps entity state near real-time and lets the integration fall back to polling automatically if the socket drops
- **Polling interval**: Fixed at 30 seconds when REST polling is needed. This is not a user-configurable option

### Removal

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Open **Unraid Management Agent**
3. Choose **Delete** to remove the config entry and all entities created by the integration
4. If installed through HACS, remove the repository from HACS and restart Home Assistant
5. If installed manually, delete `custom_components/unraid_management_agent` from your Home Assistant config directory and restart Home Assistant
6. If you no longer need the backend service, uninstall or disable the Unraid Management Agent plugin from your Unraid server

## Supported Environment

- **Supported Unraid versions**: Unraid 6.9.0 and newer, including current 7.x releases
- **Supported Home Assistant setup**: UI-based config entry setup only. YAML configuration is not supported
- **Supported subsystems**: Array, disks, Docker, virtual machines, network interfaces, UPS, GPU metrics, shares, flash drive health, parity scheduling, mover status, plugins, and ZFS where exposed by the Unraid Management Agent
- **Conditional entities**: Container, VM, UPS, GPU, network, and ZFS entities only appear when those services or collectors are available on the target server

## Known Limitations

- The integration depends on the separate Unraid Management Agent plugin running on the Unraid server
- Discovery is not implemented. You must add the integration manually with the server host and port
- If WebSocket is unavailable, the integration falls back to REST polling, so some state changes can be delayed by up to 30 seconds
- Some entities are intentionally conditional and will not be created unless the matching Unraid feature is enabled or the collector is available
- Older installations can still have historical entity registry entries from previous naming schemes; the integration migrates the known legacy unique IDs during startup, but it does not delete user-managed historical registry rows

## Use Cases

- Monitor core Unraid health in Home Assistant dashboards, including CPU, RAM, temperatures, array status, and flash health
- Automate maintenance workflows such as parity checks, array start and stop, and graceful shutdown during UPS events
- Control Docker containers and virtual machines from dashboards, scripts, and automations
- Feed supported power and energy entities into Home Assistant’s long-term statistics and Energy Dashboard

## Entity Overview

### Sensors (30+ base entities)

**System Sensors (6+ entities)**

- CPU Usage (%)
- RAM Usage (%)
- CPU Temperature (°C)
- System Status
- Motherboard Temperature (°C) - conditional, only if available
- Fan {name} (RPM) - dynamic, one per detected fan
- Uptime (human-readable format)

**Array Sensors (2 entities)**

- Array Usage (%)
- Parity Check Progress (%)

**Disk Sensors (dynamic)**

- Disk {name} Usage (%) - dynamic, one per disk (excludes parity disks)
- Disk {name} Health - dynamic, one per physical disk with SMART data
- Docker vDisk Usage (%) - conditional, only if Docker vDisk exists
- Log Filesystem Usage (%) - conditional, only if log filesystem exists

**GPU Sensors (3 entities, conditional)**

- GPU Utilization (%)
- GPU CPU Temperature (°C)
- GPU Power (W)

**UPS Sensors (4 entities, conditional)**

- UPS Battery (%)
- UPS Load (%)
- UPS Runtime (seconds)
- UPS Power (W) - compatible with Home Assistant Energy Dashboard

**Network Sensors (dynamic)**

- Network {interface} Inbound (bits/s) - one per physical interface
- Network {interface} Outbound (bits/s) - one per physical interface

### Binary Sensors (7+ entities)

**Array Binary Sensors (3)**

- Array Started (on/off)
- Parity Check Running (on/off)
- Parity Valid (problem indicator)

**UPS Binary Sensor (1, conditional)**

- UPS Connected (on/off)

**Container Binary Sensors (dynamic)**

- Container {name} (running/stopped)

**VM Binary Sensors (dynamic)**

- VM {name} (running/stopped)

**Network Binary Sensors (dynamic)**

- Network {interface} (up/down)

### Switches (dynamic)

- Container {name} - Start/stop Docker containers
- VM {name} - Start/stop virtual machines

### Buttons (6 + dynamic user scripts)

- Start Array
- Stop Array
- Start Parity Check
- Stop Parity Check
- Shutdown System
- Reboot System
- User script buttons are exposed when available and are disabled by default to avoid noise

## Services

The integration provides 18 services for advanced automation and control beyond what switches and buttons offer.

### Container Services (5)

- `unraid_management_agent.container_start` - Start a Docker container
- `unraid_management_agent.container_stop` - Stop a Docker container
- `unraid_management_agent.container_restart` - Restart a Docker container
- `unraid_management_agent.container_pause` - Pause a running Docker container
- `unraid_management_agent.container_resume` - Resume a paused Docker container (unpause)

**Example**:

```yaml
service: unraid_management_agent.container_start
data:
  container_id: "plex"
```

### Virtual Machine Services (7)

- `unraid_management_agent.vm_start` - Start a virtual machine
- `unraid_management_agent.vm_stop` - Stop a virtual machine (graceful shutdown)
- `unraid_management_agent.vm_restart` - Restart a virtual machine
- `unraid_management_agent.vm_pause` - Pause a running virtual machine (suspend to RAM)
- `unraid_management_agent.vm_resume` - Resume a paused virtual machine
- `unraid_management_agent.vm_hibernate` - Hibernate a virtual machine (suspend to disk)
- `unraid_management_agent.vm_force_stop` - Force stop a virtual machine (equivalent to power off)

**Example**:

```yaml
service: unraid_management_agent.vm_hibernate
data:
  vm_id: "Windows 10"
```

### Array Control Services (2)

- `unraid_management_agent.array_start` - Start the Unraid array
- `unraid_management_agent.array_stop` - Stop the Unraid array

**Example**:

```yaml
service: unraid_management_agent.array_start
```

### Parity Check Services (4)

- `unraid_management_agent.parity_check_start` - Start a parity check
- `unraid_management_agent.parity_check_stop` - Stop the running parity check
- `unraid_management_agent.parity_check_pause` - Pause the running parity check
- `unraid_management_agent.parity_check_resume` - Resume a paused parity check

**Example**:

```yaml
service: unraid_management_agent.parity_check_pause
```

## Example Automations

> **Note**: Replace `tower` in the entity IDs below with your actual Unraid server hostname (e.g., if your Unraid server is named "nas", use `sensor.unraid_nas_cpu_usage`).

### High CPU Alert

```yaml
automation:
  - alias: "Unraid High CPU Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.unraid_tower_cpu_usage
        above: 80
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Unraid Alert"
          message: "CPU usage is {{ states('sensor.unraid_tower_cpu_usage') }}%"
```

### UPS Graceful Shutdown

```yaml
automation:
  - alias: "Unraid UPS Critical Shutdown"
    trigger:
      - platform: numeric_state
        entity_id: sensor.unraid_tower_ups_battery
        below: 10
    action:
      - service: switch.turn_off
        target:
          entity_id: all
        data:
          domain: switch
      - delay:
          seconds: 30
      - service: button.press
        target:
          entity_id: button.unraid_tower_stop_array
```

### Disk Health Alert

```yaml
automation:
  - alias: "Unraid Disk Health Alert"
    trigger:
      - platform: state
        entity_id: sensor.unraid_tower_disk_disk1_health
        to: "Failed"
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 Unraid Disk Alert"
          message: "Disk 1 health status is {{ states('sensor.unraid_tower_disk_disk1_health') }}"
```

### Container Auto-Restart on Failure

```yaml
automation:
  - alias: "Restart Plex on Stop"
    trigger:
      - platform: state
        entity_id: switch.unraid_tower_container_plex
        to: "off"
        for:
          minutes: 1
    action:
      - service: unraid_management_agent.container_start
        data:
          container_id: "plex"
```

## Architecture

### Components

- **API Client** (`api/client.py`) - REST API communication with aiohttp
- **WebSocket Client** (`api/websocket.py`) - Real-time event streaming
- **Data Coordinator** (`coordinator.py`) - Data management and updates
- **Config Flow** (`config_flow.py`) - UI-based configuration
- **Platforms**:
  - `sensor.py` - System, array, GPU, UPS, network sensors
  - `binary_sensor.py` - Status indicators
  - `switch.py` - Container and VM control
  - `button.py` - Array, parity, system power, and user-script control

### Data Flow

```bash
Unraid Server (REST API + WebSocket)
           ↓
    API Client / WebSocket Client
           ↓
    Data Update Coordinator
           ↓
    Entity Platforms (Sensor, Binary Sensor, Switch, Button)
           ↓
    Home Assistant UI
```

### Update Strategy

1. **Initial Load**: REST API fetches all data on startup
2. **Real-Time Updates**: WebSocket receives events and updates coordinator
3. **Fallback Polling**: REST API polls every 30 seconds if WebSocket fails or is disabled
4. **Control Actions**: REST API sends commands, coordinator refreshes immediately

## Troubleshooting

### Common Issues

**Cannot Connect**

- Verify Unraid Management Agent is running: `curl http://<ip>:8043/api/v1/health`
- Check firewall rules allow port 8043
- Ensure Home Assistant can reach Unraid server

**WebSocket Not Working**

- Check logs for WebSocket errors
- Verify no proxy blocking WebSocket
- Integration will fall back to REST polling automatically

**Entities Not Updating**

- Verify WebSocket connection in logs
- Test REST API manually
- Remember that REST fallback polling is fixed at 30 seconds

**Missing Entities**

- Verify resources exist on Unraid (containers, VMs, GPU, UPS)
- Reload integration
- Check logs for entity creation errors

## Development

### Project Structure

```bash
ha-unraid-management-agent/
├── custom_components/
│   └── unraid_management_agent/
│       ├── __init__.py           # Integration setup
│       ├── api_client.py         # REST API client
│       ├── binary_sensor.py      # Binary sensor platform
│       ├── button.py             # Button platform
│       ├── config_flow.py        # Configuration flow
│       ├── const.py              # Constants
│       ├── manifest.json         # Integration metadata
│       ├── sensor.py             # Sensor platform
│       ├── strings.json          # Translations
│       ├── switch.py             # Switch platform
│       └── websocket_client.py   # WebSocket client
└── README.md                     # This file
```

### Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov --cov-report=term-missing --cov-report=html

# Run specific test file
pytest tests/test_coordinator.py -v

# Run tests in parallel
pytest -n auto
```

**CI/CD Pipeline:**

- Automated tests run on every push and pull request
- Tests run on Python 3.14
- Coverage reports automatically uploaded to Codecov
- Test results tracked in GitHub Actions

**Coverage Requirements:**

- Minimum coverage: 60%
- Coverage reports available at [Codecov](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent)

1. Install in development mode
2. Enable debug logging:

   ```yaml
   logger:
     default: info
     logs:
       custom_components.unraid_management_agent: debug
   ```

3. Check logs for errors
4. Test all entity types
5. Test control operations
6. Test WebSocket reconnection

## Releases

This integration follows semantic versioning with the format `vYYYY.MM.x` (e.g., `v2025.11.1`).

### Latest Release

Check the [Releases](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases) page for the latest version and changelog.

### Release Process

Releases are automated via GitHub Actions:

1. Update `manifest.json` version
2. Update `CHANGELOG.md` with release notes
3. Create and push a version tag (e.g., `v2025.11.1`)
4. GitHub Actions automatically builds and publishes the release

For detailed release process documentation, see [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run linting and tests:
   ```bash
   script/lint
   pytest
   ```
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

**Development Guidelines:**

- Follow Home Assistant core integration best practices
- Maintain 60%+ code coverage
- Use type hints throughout
- Add tests for new features
- Update documentation as needed

**CI Checks:**
All pull requests must pass:

- ✅ Ruff linting (format and check)
- ✅ Pytest test suite (Python 3.14)
- ✅ Coverage threshold (60% minimum)
- ✅ Manifest and configuration validation

5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/ruaan-deysel/ha-unraid-management-agent/blob/main/LICENSE) file for details.

## Trademark Notice

Unraid® is a registered trademark of Lime Technology, Inc. This application is not affiliated with, endorsed, or sponsored by Lime Technology, Inc.
