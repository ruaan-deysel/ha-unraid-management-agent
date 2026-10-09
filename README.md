# Unraid Management Agent Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/ruaan-deysel/ha-unraid-management-agent.svg)](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases)
[![codecov](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent)
[![Community Forum](https://img.shields.io/badge/Community-Forum-blue)](https://community.home-assistant.io/t/unraid-integration)
[![License](https://img.shields.io/github/license/ruaan-deysel/ha-unraid-management-agent.svg)](https://github.com/ruaan-deysel/ha-unraid-management-agent/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ruaan-deysel/ha-unraid-management-agent)

This custom integration connects Home Assistant to the [Unraid Management Agent](https://github.com/ruaan-deysel/unraid-management-agent) (UMA) running on your Unraid server. It delivers comprehensive monitoring, interactive controls, dynamic entity discovery, real-time WebSocket telemetry, and a bundled suite of custom Lovelace dashboard cards.

---

## Highlights & Features

- **Bundled Lovelace Dashboard Cards**: 15 custom Lovelace cards bundled directly with the integration—no manual JavaScript download or separate HACS frontend repository required.
- **Unified UI Setup & Zeroconf**: Effortless discovery via Zeroconf (`_unraid-mgmt-agent._tcp.local.`) or guided manual config flow.
- **Hybrid Real-Time Updates**: Local push via WebSocket event stream with automatic reconnect and 30-second REST polling fallback.
- **Dynamic Entity Discovery**: Automatically creates, tracks, and cleans up entities for Docker containers, virtual machines, disks, fans, network interfaces, ZFS pools, remote shares, unassigned devices, and SAS storage topology.
- **Modular Device Organization**: Optional settings to split Docker containers and virtual machines into their own dedicated child devices with clean, short entity names.
- **Update Management Platform**: Monitor Unraid OS versions, track plugin updates (with one-click install), and detect Docker container image updates via image digest tracking.
- **Agent Alert Rules Engine**: Monitor custom and built-in UMA alert rules as problem binary sensors, track firing counts, and trigger automations from alert events.
- **Enterprise SAS Storage Topology**: Discovers RAID/HBA controllers, SAS disk shelves/backplanes, power supplies, I/O modules, cabling maps, and path redundancy.
- **Flexible Control Surfaces**: Switches for containers, VMs, and disk spin; buttons for array operations, parity checks, power commands, and user scripts; numbers for PWM fan control.
- **Safe Read-Only Mode**: Dedicated toggle to restrict the integration to sensors and telemetry only, disabling all control switches, buttons, numbers, and service calls.

---

## Lovelace Dashboard Cards Suite

The integration automatically registers a complete suite of custom Lovelace cards in Home Assistant's resource registry upon integration setup. Each card features visual UI configuration, auto-detection of your Unraid server, and responsive layouts for desktop and mobile dashboards.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          custom:unraid-dashboard-card                       │
│  [ Server ] [ Storage ] [ Docker ] [ VMs ] [ UPS ] [ Network ] [ ZFS ] ...  │
├─────────────────────────────────────────────────────────────────────────────┤
│  All-in-one unified dashboard card with tabbed navigation across subsystems │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Available Custom Cards

| Card Tag                                | Description                      | Key Features                                                                                              |
| :-------------------------------------- | :------------------------------- | :-------------------------------------------------------------------------------------------------------- |
| `custom:unraid-dashboard-card`          | **Unified Multi-Tab Dashboard**  | Full-featured dashboard embedding all modules with intuitive sub-navigation tabs.                         |
| `custom:unraid-server-card`             | **Server Telemetry & Health**    | CPU, RAM, uptime, system load, motherboard info, array status, and navigation rings.                      |
| `custom:unraid-storage-card`            | **Array & Storage Manager**      | Array state, parity status & operations, cache pools, drive temperatures, and health.                     |
| `custom:unraid-docker-card`             | **Docker Containers**            | Container list or grid, autostart badges, running switches, CPU/memory telemetry, and update status.      |
| `custom:unraid-vm-card`                 | **Virtual Machines**             | VM list, power state, start/stop/pause controls, vCPUs, memory allocation, and transfer rates.            |
| `custom:unraid-ups-card`                | **UPS Power Monitoring**         | Battery percentage, load %, estimated runtime duration, input/output voltage, and power draw.             |
| `custom:unraid-gpu-card`                | **GPU Telemetry**                | Multi-GPU support (NVIDIA, Intel, AMD), utilization rings, VRAM usage, clocks, driver version, and temps. |
| `custom:unraid-network-card`            | **Network Interfaces**           | Interface status, IPv4/IPv6 addresses, link speeds, MTU, and real-time RX/TX throughput.                  |
| `custom:unraid-shares-card`             | **User Shares**                  | User share capacity usage, free space, and parity protection status badges.                               |
| `custom:unraid-remote-shares-card`      | **Remote Shares**                | Mounted remote SMB/NFS shares, mount/unmount switches, and usage metrics.                                 |
| `custom:unraid-unassigned-devices-card` | **Unassigned Devices**           | External USB/SATA drives, file systems, mount switches, and partition details.                            |
| `custom:unraid-zfs-card`                | **ZFS Pools & Datasets**         | Pool status, ARC hit ratio gauges, scrub status, error counts, and dataset capacity.                      |
| `custom:unraid-fans-card`               | **Fan & Thermal Control**        | PWM fan speeds (RPM), duty cycle percentages, and fan control number sliders.                             |
| `custom:unraid-notifications-card`      | **System Notifications**         | System notifications breakdown across alerts, warnings, and informational notices.                        |
| `custom:unraid-maintenance-card`        | **Maintenance & Parity History** | Boot flash drive health, parity check schedule, history, duration, and sync errors.                       |

### Dashboard Configuration Examples

#### 1. All-in-One Dashboard (Recommended)

Simply add the unified dashboard card to any Lovelace view. It automatically discovers your Unraid server:

```yaml
type: custom:unraid-dashboard-card
```

To bind to a specific server or customize the header:

```yaml
type: custom:unraid-dashboard-card
server: tower # Name or device ID of your Unraid server (optional)
title: Main Unraid Server
```

#### 2. Individual Cards

You can mix and match individual cards across your custom dashboards:

```yaml
# Server telemetry overview
type: custom:unraid-server-card
show_system_info: true
show_motherboard: true

# Docker container monitoring in grid view
type: custom:unraid-docker-card
view_mode: grid # "grid" or "list"

# Storage array and disk health
type: custom:unraid-storage-card

# Power & UPS status
type: custom:unraid-ups-card

# Multi-GPU metrics
type: custom:unraid-gpu-card
```

---

## What The Integration Exposes

The exact entities exposed depend on the hardware, plugins, and collectors active on your Unraid server:

### System & Telemetry

- **CPU & Memory**: Overall CPU utilization, memory used/free/percentage, swap memory, and system load averages (1m, 5m, 15m).
- **Temperatures**: CPU temperature, motherboard temperature, plus individual per-channel hwmon sensors (`temp*_input`) for VRMs, chipsets, coolant probes, and custom sensors.
- **Uptime & Boot**: System uptime duration and boot timestamp.
- **Diagnostics**: Degraded subsystem counts and Docker port conflict sensors.

### Array & Parity

- **Array State**: Array status (Started, Stopped), total capacity, used space, free space, and usage percentage.
- **Parity Operations**: Parity check progress percentage, parity check state (Running, Paused, Idle), schedule, history timestamp, duration, and parity sync error count.
- **Flash Boot Drive**: Flash drive utilization, free space, and device status.

### SAS Storage Topology

When the agent's `storage_topology` collector is active (`storcli` or `sg3_utils` SES):

- **Controllers**: Controller temperature, firmware version, PCIe link generation/width, port link rates, and overall controller problem binary sensor.
- **Enclosures / Shelves**: Enclosure status, highest temperature, lowest fan speed, drive media/other error totals, and slot error counters.
- **Problem Binary Sensors**: Dedicated problem sensors for each power supply, I/O module, fan bank, cabling anomaly, path redundancy loss, drive health, and I/O firmware mismatches.

### Docker Containers

- **Status & Control**: Running binary sensor, power switch (`switch`), autostart switch, and restart button (`button`).
- **Telemetry**: Container CPU utilization, memory allocated, memory percentage, restart count, and network RX/TX transfer rates.
- **Image Updates**: Update entity (`update`) tracking upstream image digest updates; one-click image pull and container recreation from Home Assistant.
- **Device Grouping**: Optional toggle to group each container into a child device in Home Assistant.

### Virtual Machines

- **Status & Control**: Running binary sensor, power switch (`switch`), restart button, pause/resume button, force-stop button, and hibernate action.
- **Telemetry**: vCPU count, memory allocation, and network RX/TX transfer rates.
- **Device Grouping**: Optional toggle to group each VM into a child device in Home Assistant.

### ZFS Pools & Datasets

- **Pool Health**: Pool status sensor, pool problem binary sensor, and fragmentation percentage.
- **Scrubbing & Errors**: Scrub status (Scrubbing, Paused, Finished), last scrub timestamp, scrub error count, repaired bytes, and aggregate read/write/checksum error totals.
- **Corrupted Files**: Permanent corrupted file count and attribute list of corrupted file paths.
- **ARC Cache**: ARC size, target size, max size, hit ratio percentage, data size, and metadata size.

### Updates (Update Platform)

- **Unraid OS**: Displays installed version and latest available version (read-only; upgrades remain safely handled via Unraid UI).
- **Plugins**: Displays installed and available versions with one-click update installation.
- **Containers**: Digest-based image update detection with one-click pull and restart.

### Alerts & Notifications

- **Alert Rules**: Each UMA alert rule is exposed as a problem binary sensor (on while firing; unavailable if disabled) with severity, duration, and rule expressions in attributes.
- **Alert Events**: `event` entity emitting `firing` and `resolved` events for easy automation triggering.
- **Firing Count**: Sensor reporting the current count of active firing alert rules.
- **Notification Center**: Notification counts categorized by alerts, warnings, and informational notices.

### GPUs, UPS, Fans, & Services

- **GPUs**: Utilization percentage, VRAM Used (MiB), VRAM Total (GiB), VRAM Usage (%), temperatures, and clock frequencies.
- **UPS**: Battery percentage, load percentage, estimated runtime duration, and power draw. With NUT, every additional NUT device (a second UPS, an ATS, ...) gets its own `UPS <device> ...` entities for the readings it reports, plus a connected sensor (needs an agent with multi-device NUT support).
- **Fans**: Fan RPM sensors and PWM speed number entities (`number`) when fan control is enabled.
- **Network Interfaces**: Status, IPv4/IPv6 addresses, link speeds, MTU, and real-time throughput.
- **Network & System Services**: Binary sensors for network services (SMB, NFS, SSH, FTP, Syslog) and system services (Docker, Libvirt, Nginx).
- **Remote Shares & Unassigned Devices**: Mount state binary sensors, mount toggles (`switch`), and capacity usage.

---

## Prerequisites

- **Unraid OS**: Version 6.9.0 or newer.
- **Home Assistant**: Version 2026.9 or newer.
- **Unraid Management Agent**: Installed and running on your Unraid server.

### Verify The Agent

Confirm the agent is running and accessible before setting up the integration:

```text
http://<your-unraid-ip>:8043/api/v1/health
```

A healthy agent responds with JSON status `{"status":"ok",...}`.

---

## Installation

### Method 1: Via HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ruaan-deysel&repository=ha-unraid-management-agent&category=integration)

1. Open **HACS** in Home Assistant.
2. Navigate to **Integrations**.
3. Click the three-dot menu in the upper-right corner and select **Custom repositories**.
4. Enter `https://github.com/ruaan-deysel/ha-unraid-management-agent` and select category **Integration**.
5. Click **Add**, find **Unraid Management Agent**, and click **Download**.
6. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release archive from the [GitHub Releases](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases) page.
2. Extract the `custom_components/unraid_management_agent` folder into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

### Automatic Discovery

If your Unraid Management Agent advertises via Zeroconf (`_unraid-mgmt-agent._tcp.local.`), Home Assistant discovers it automatically. Click **Configure** on the discovered device to complete setup.

### Manual Setup

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for **Unraid Management Agent**.
3. Fill in the connection settings:
   - **Host**: IP address or hostname of your Unraid server.
   - **Port**: API port (default: `8043`).
   - **API Token** _(optional)_: Required if `API_TOKEN` is configured on your agent (agent v2026.08.02+). Sent as a bearer token. Supports automatic re-authentication if rotated.
   - **Enable WebSocket**: Checked by default for instant local push updates.
4. Click **Submit**.

### Integration Options

Click **Configure** on an active integration entry to adjust operational options at any time:

| Option                                         | Default | Description                                                                                         |
| :--------------------------------------------- | :-----: | :-------------------------------------------------------------------------------------------------- |
| **Enable WebSocket**                           | `true`  | Real-time push updates via WebSocket with automatic 30s polling fallback.                           |
| **Enable fan control entities**                | `false` | Exposes PWM number control entities (`number`) for configurable fan controllers.                    |
| **Show Docker containers as separate devices** | `false` | Creates a child device for each container in Home Assistant with short entity names.                |
| **Show virtual machines as separate devices**  | `false` | Creates a child device for each VM in Home Assistant keyed by libvirt UUID.                         |
| **Enable container update checks**             | `false` | Tracks container image digest updates and adds an `update` entity per container.                    |
| **Read-only (sensors only)**                   | `false` | Restricts the integration to monitoring only, disabling all switches, buttons, and control actions. |

---

## Home Assistant Services

The integration exposes 18 service actions for dashboard buttons and automations:

### Docker Container Actions

- `unraid_management_agent.container_start`: Start a Docker container.
- `unraid_management_agent.container_stop`: Gracefully stop a container.
- `unraid_management_agent.container_restart`: Restart a container.
- `unraid_management_agent.container_pause`: Pause container execution.
- `unraid_management_agent.container_resume`: Resume a paused container.

```yaml
action: unraid_management_agent.container_restart
data:
  container_id: plex
```

### Virtual Machine Actions

- `unraid_management_agent.vm_start`: Power on a VM.
- `unraid_management_agent.vm_stop`: Gracefully shut down a VM.
- `unraid_management_agent.vm_restart`: Restart a VM.
- `unraid_management_agent.vm_pause`: Pause a running VM.
- `unraid_management_agent.vm_resume`: Resume a paused VM.
- `unraid_management_agent.vm_hibernate`: Suspend / hibernate a VM.
- `unraid_management_agent.vm_force_stop`: Forcefully stop / power off a VM.

```yaml
action: unraid_management_agent.vm_start
data:
  vm_id: Ubuntu-Server
```

### Array & Parity Actions

- `unraid_management_agent.array_start`: Start the storage array.
- `unraid_management_agent.array_stop`: Stop the storage array.
- `unraid_management_agent.parity_check_start`: Begin a parity check.
- `unraid_management_agent.parity_check_stop`: Stop an ongoing parity check.
- `unraid_management_agent.parity_check_pause`: Pause parity check operations.
- `unraid_management_agent.parity_check_resume`: Resume paused parity operations.

---

## Example Automations

### High CPU Alert

```yaml
automation:
  - alias: "Unraid: High CPU Usage Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.unraid_tower_cpu_usage
        above: 85
        for:
          minutes: 5
    action:
      - action: notify.mobile_app
        data:
          title: "Unraid Alert: High CPU"
          message: "CPU utilization has remained at {{ states('sensor.unraid_tower_cpu_usage') }}% for 5 minutes."
```

### Critical UPS Battery Shutdown

```yaml
automation:
  - alias: "Unraid: UPS Critical Battery Shutdown"
    trigger:
      - platform: numeric_state
        entity_id: sensor.unraid_tower_ups_battery
        below: 15
    action:
      - action: button.press
        target:
          entity_id: button.unraid_tower_stop_array
      - delay:
          seconds: 30
      - action: button.press
        target:
          entity_id: button.unraid_tower_shutdown
```

### React to Agent Alert Rule Events

```yaml
automation:
  - alias: "Unraid: Agent Alert Triggered"
    trigger:
      - platform: state
        entity_id: event.unraid_tower_alert
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.event_type == 'firing' }}"
    action:
      - action: notify.mobile_app
        data:
          title: "Unraid Alert: {{ trigger.to_state.attributes.severity | upper }}"
          message: "{{ trigger.to_state.attributes.rule_name }}"
```

### Auto-Restart Container on Unplanned Stop

```yaml
automation:
  - alias: "Unraid: Restart Vaultwarden on Failure"
    trigger:
      - platform: state
        entity_id: switch.unraid_tower_container_vaultwarden
        to: "off"
        for:
          minutes: 2
    action:
      - action: unraid_management_agent.container_start
        data:
          container_id: vaultwarden
```

---

## Architecture & Project Structure

The integration is built upon modern Home Assistant architectural patterns (Platinum Quality Scale target) with typed Pydantic models and asynchronous I/O:

```text
custom_components/unraid_management_agent/
├── __init__.py           # Setup lifecycle, services registration, frontend registration
├── api/                  # Vendored async API client, Pydantic models, and WebSocket hub
├── binary_sensor.py      # Binary sensor platform (array, services, alerts, ZFS, topology)
├── button.py             # Button platform (array, parity, reboot, VM, container restart)
├── cleanup.py            # Dynamic entity cleanup coordinator
├── config_flow.py        # Config flow, Zeroconf discovery, reauth, and options flow
├── const.py              # Domain constants, configuration keys, default intervals
├── coordinator.py        # Central data coordinator (WebSocket push + REST polling)
├── diagnostics.py        # Redacted diagnostics export
├── entity.py             # Base entity classes and device info builders
├── event.py              # Event platform (notifications and alert rule events)
├── frontend.py           # Lovelace custom cards resource registration & static asset serving
├── frontend/             # Compiled custom cards bundle (unraid-cards.js)
├── number.py             # Number platform (PWM fan duty cycle control)
├── repairs.py            # Guided repair flows
├── sensor.py             # Sensor platform (system, array, disks, GPUs, UPS, ZFS, rates)
├── services.yaml         # Action schemas and translation descriptions
├── switch.py             # Switch platform (containers, VMs, disk spin, remote shares)
├── update.py             # Update platform (Unraid OS, plugins, Docker containers)
└── translations/         # Multi-language translations
```

---

## Troubleshooting

### Connection Failures

- Verify the agent is running on your Unraid server by visiting `http://<unraid-ip>:8043/api/v1/health` in a browser.
- Check firewall settings on Unraid and any intermediate routers.
- If `API_TOKEN` is enabled on the agent, verify the token in the re-authentication or reconfigure dialog.

### Missing Entities

- Certain entities only populate when the corresponding subsystem or collector is active on the server (e.g. ZFS pools, UPS, GPU, fan controllers, SAS topology).
- Storage topology devices require `storcli` or `sg3_utils` (SES) on Unraid and usually appear within 1–2 minutes of starting the agent.
- If you recently added new containers, disks, or pools, reload the integration entry under **Settings** > **Devices & Services**.

### Dashboard Cards Not Appearing

- The cards are bundled directly with the integration and registered automatically.
- If custom cards show as unknown in Lovelace after an upgrade, perform a hard refresh in your browser (Ctrl+F5 or Shift+Reload) to clear the browser cache.

---

## Development & Testing

```bash
# Linting and formatting
script/lint

# Run test suite with pytest
pytest tests/ -v --timeout=30

# Launch local Home Assistant development environment
./script/develop
```

---

## Contributing

Contributions are welcome! Please ensure:

1. Code adheres to Home Assistant Platinum Quality Scale rules (no deprecated APIs, full type annotations, async I/O).
2. All pre-commit hooks and tests pass (`script/lint` and `pytest`).
3. `CHANGELOG.md` is updated under `## [Unreleased]`.
4. Pull requests follow the provided PR template.

---

## License

This project is licensed under the MIT License. See [LICENSE](https://github.com/ruaan-deysel/ha-unraid-management-agent/blob/main/LICENSE) for details.

## Trademark Notice

Unraid is a registered trademark of Lime Technology, Inc. This project is an independent community integration and is not affiliated with, endorsed by, or sponsored by Lime Technology, Inc.
