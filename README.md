# Unraid Management Agent Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/ruaan-deysel/ha-unraid-management-agent.svg)](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases)
[![codecov](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent)
[![Community Forum](https://img.shields.io/badge/Community-Forum-blue)](https://community.home-assistant.io/t/unraid-integration)
[![License](https://img.shields.io/github/license/ruaan-deysel/ha-unraid-management-agent.svg)](https://github.com/ruaan-deysel/ha-unraid-management-agent/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ruaan-deysel/ha-unraid-management-agent)

This custom integration connects Home Assistant to the Unraid Management Agent running on your Unraid server. It provides monitoring, control, dynamic entity discovery, and real-time updates through the agent's REST API and WebSocket event stream.

## Overview

- UI-based setup with config flow support
- Zeroconf discovery for compatible Unraid Management Agent versions
- Hybrid update model using WebSocket push with REST polling fallback
- Dynamic entities for Docker containers, virtual machines, disks, fans, network interfaces, ZFS pools, remote shares, and unassigned devices
- Control surfaces through switches, buttons, numbers, events, and Home Assistant services

## What The Integration Exposes

- System metrics such as CPU usage, memory usage, temperatures, uptime, swap usage, flash usage, and plugin or OS update status
- Array and parity monitoring including array usage, parity progress, parity schedule, and parity history
- Docker monitoring and control, including per-container CPU, memory, restart count, network throughput, update availability, and start or stop operations
- VM monitoring and control, including state, restart and force-stop controls, and service actions
- ZFS monitoring including pool health, corrupted files, ARC statistics, and configured ARC max
- UPS, GPU, mover, registration, notifications, network services, remote shares, and unassigned device data when available on the target server
- Diagnostics-backed sensors such as degraded subsystem count and Docker port conflict count

## Prerequisites

You must have the Unraid Management Agent plugin installed and running on your Unraid server before adding this integration.

### Unraid Requirements

- Unraid 6.9.0 or newer
- Unraid Management Agent installed and reachable from Home Assistant

### Home Assistant Requirements

- Home Assistant 2025.1 or newer

### Verify The Agent

Confirm the agent is reachable before configuring the integration:

```text
http://<your-unraid-ip>:8043/api/v1/health
```

You should receive a healthy JSON response.

## Install The Unraid Management Agent

### Option A: Community Applications

1. Open the Unraid web interface.
2. Go to Apps.
3. Search for Unraid Management Agent.
4. Install the plugin.
5. Review the plugin settings and confirm the API port, which defaults to 8043.

### Option B: Manual Plugin URL

1. Open the Unraid web interface.
2. Go to Plugins.
3. Select Install Plugin.
4. Paste the following URL:

```text
https://raw.githubusercontent.com/ruaan-deysel/unraid-management-agent/main/unraid-management-agent.plg
```

5. Install the plugin.
6. Review the plugin settings and confirm the API port.

## Install This Integration

### Via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ruaan-deysel&repository=ha-unraid-management-agent&category=integration)

Manual HACS steps:

1. Open HACS in Home Assistant.
2. Go to Integrations.
3. Open the three-dot menu and select Custom repositories.
4. Add `https://github.com/ruaan-deysel/ha-unraid-management-agent`.
5. Set the category to Integration.
6. Install Unraid Management Agent from HACS.
7. Restart Home Assistant.

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases).
2. Extract `custom_components/unraid_management_agent` into your Home Assistant configuration directory.
3. Restart Home Assistant.

## Configuration

### Automatic Discovery

If your Unraid Management Agent version advertises `_unraid-mgmt-agent._tcp.local.`, Home Assistant can discover it automatically through Zeroconf.

### Manual Setup

1. Open Settings > Devices & Services in Home Assistant.
2. Select Add Integration.
3. Search for Unraid Management Agent.
4. Enter the host and port for your Unraid server.
5. Leave WebSocket enabled unless you have a specific reason to disable it.

### Configuration Fields

- Host: IP address or DNS name of the Unraid server
- Port: API port exposed by the Unraid Management Agent, `8043` by default
- Enable WebSocket: enables near real-time updates with REST fallback if the socket disconnects

The REST polling interval is fixed at 30 seconds when polling is required.

### Integration Options

The Configure dialog includes optional behavior toggles:

- Enable fan control entities
- Enable container update checks

## Home Assistant Services

The integration registers 18 services.

### Container Services

- `unraid_management_agent.container_start`
- `unraid_management_agent.container_stop`
- `unraid_management_agent.container_restart`
- `unraid_management_agent.container_pause`
- `unraid_management_agent.container_resume`

Example:

```yaml
service: unraid_management_agent.container_start
data:
  container_id: plex
```

### Virtual Machine Services

- `unraid_management_agent.vm_start`
- `unraid_management_agent.vm_stop`
- `unraid_management_agent.vm_restart`
- `unraid_management_agent.vm_pause`
- `unraid_management_agent.vm_resume`
- `unraid_management_agent.vm_hibernate`
- `unraid_management_agent.vm_force_stop`

Example:

```yaml
service: unraid_management_agent.vm_hibernate
data:
  vm_id: Fedora
```

### Array Services

- `unraid_management_agent.array_start`
- `unraid_management_agent.array_stop`

### Parity Services

- `unraid_management_agent.parity_check_start`
- `unraid_management_agent.parity_check_stop`
- `unraid_management_agent.parity_check_pause`
- `unraid_management_agent.parity_check_resume`

## Entity Types

The exact entity set depends on what the Unraid Management Agent exposes for your server.

- Sensors for system, array, flash, plugins, mover, parity, notifications, registration, ZFS, UPS, GPU, containers, remote shares, and unassigned devices
- Binary sensors for array state, parity state, update availability, mover state, UPS connectivity, network services, remote shares, and unassigned devices
- Switches for containers, virtual machines, disk spin control, and remote shares
- Buttons for array actions, parity actions, system power actions, VM controls, and user scripts
- Number entities for supported fan speed control
- Event entities for notifications

Dynamic entities are cleaned up automatically when the corresponding resource is removed from Unraid.

## Example Automations

Replace `tower` below with your actual server naming in Home Assistant.

### High CPU Notification

```yaml
automation:
  - alias: Unraid High CPU Alert
    trigger:
      - platform: numeric_state
        entity_id: sensor.unraid_tower_cpu_usage
        above: 80
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: Unraid Alert
          message: "CPU usage is {{ states('sensor.unraid_tower_cpu_usage') }}%"
```

### UPS Driven Array Shutdown

```yaml
automation:
  - alias: Unraid UPS Critical Shutdown
    trigger:
      - platform: numeric_state
        entity_id: sensor.unraid_tower_ups_battery
        below: 10
    action:
      - delay:
          seconds: 30
      - service: button.press
        target:
          entity_id: button.unraid_tower_stop_array
```

### Restart A Container After It Stops

```yaml
automation:
  - alias: Restart Plex On Stop
    trigger:
      - platform: state
        entity_id: switch.unraid_tower_container_plex
        to: "off"
        for:
          minutes: 1
    action:
      - service: unraid_management_agent.container_start
        data:
          container_id: plex
```

## Architecture

The integration is structured around a typed API package and a central coordinator.

- `custom_components/unraid_management_agent/api/`: vendored REST, model, formatting, and WebSocket client code
- `custom_components/unraid_management_agent/coordinator.py`: polling and push-update orchestration
- `custom_components/unraid_management_agent/config_flow.py`: UI configuration and options flow
- `custom_components/unraid_management_agent/sensor.py`, `binary_sensor.py`, `switch.py`, `button.py`, `number.py`, `event.py`: entity platforms
- `custom_components/unraid_management_agent/cleanup.py`: stale dynamic entity cleanup

## Troubleshooting

### Cannot Connect

- Confirm the agent is running on the Unraid server.
- Check `http://<ip>:8043/api/v1/health` directly.
- Verify firewall and network routing between Home Assistant and Unraid.

### Discovery Does Not Appear

- Confirm the Unraid Management Agent version supports Zeroconf advertising.
- Ensure Home Assistant and Unraid are on the same local network segment.
- Add the integration manually if discovery is unavailable in your environment.

### Missing Entities

- Some entities are conditional and only appear when the corresponding collector or subsystem exists on the Unraid server.
- Container, VM, GPU, UPS, ZFS, remote share, and fan-related entities depend on runtime availability.
- Reload the integration after changing Unraid-side configuration.

### WebSocket Issues

- The integration falls back to REST polling automatically.
- If live updates stop, check Home Assistant logs for connection and reconnect messages.

### Rate Limiting

- The integration includes client-side retry logic for UMA API rate limiting.
- Temporary debug log entries about retries are expected if the server is busy.

## Development

### Project Layout

```text
custom_components/unraid_management_agent/
  __init__.py
  api/
  binary_sensor.py
  button.py
  cleanup.py
  config_flow.py
  coordinator.py
  diagnostics.py
  entity.py
  event.py
  number.py
  repairs.py
  sensor.py
  services.yaml
  switch.py
```

### Local Commands

```bash
script/lint
pytest tests/ -v --timeout=30
./script/develop
```

### Logging

Enable debug logging in Home Assistant when needed:

```yaml
logger:
  default: info
  logs:
    custom_components.unraid_management_agent: debug
```

## Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make the change.
4. Run linting and tests.
5. Open a pull request.

Pull requests should follow Home Assistant integration conventions, keep type hints current, and update documentation when behavior changes.

## Releases

Releases follow the project's date-based versioning scheme. See the [releases page](https://github.com/ruaan-deysel/ha-unraid-management-agent/releases) for packaged versions and release notes.

## License

This project is licensed under the MIT License. See [LICENSE](https://github.com/ruaan-deysel/ha-unraid-management-agent/blob/main/LICENSE).

## Trademark Notice

Unraid is a registered trademark of Lime Technology, Inc. This project is not affiliated with, endorsed by, or sponsored by Lime Technology, Inc.
action:
