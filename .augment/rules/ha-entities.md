---
type: "always_apply"
---

# Home Assistant Unraid Management Agent Integration - Entity Standards

**Last Updated**: 2025-01-15
**Integration**: `unraid_management_agent`
**Purpose**: This file defines entity standards, naming conventions, and implementation patterns for the Unraid Management Agent Home Assistant integration.

## Table of Contents

1. [Integration Overview](#integration-overview)
2. [File Organization](#file-organization)
3. [Entity Implementation Patterns](#entity-implementation-patterns)
4. [Naming Convention Rules](#naming-convention-rules)
5. [Entity Inventory and Groupings](#entity-inventory-and-groupings)
6. [Complete Attribute Reference](#complete-attribute-reference)
7. [Device Info Standards](#device-info-standards)
8. [Data Coordinator Patterns](#data-coordinator-patterns)
9. [Code Examples](#code-examples)

---

## 1. Integration Overview

**Domain**: `unraid_management_agent` | **Manufacturer**: `Lime Technology` | **Model**: `Unraid Server`

**Platforms**: SENSOR (system metrics, storage, GPU, UPS, network), BINARY_SENSOR (status indicators), SWITCH (containers, VMs), BUTTON (array/parity controls)

**Architecture**: Coordinator pattern with `hass.data[DOMAIN][entry.entry_id]`, entity format v2 with `has_entity_name = True`, dynamic entities (fans, disks, network, containers, VMs), conditional entities (GPU, UPS, motherboard temp)

---

## 2. File Organization

**Structure**: Flat layout with `sensor.py`, `binary_sensor.py`, `switch.py`, `button.py`, `const.py`, `api_client.py`, `websocket_client.py`

**Classes**: `Unraid{Feature}Sensor`, `Unraid{Feature}BinarySensor`, `Unraid{Feature}Switch`, `Unraid{Feature}Button`
**Base Classes**: `UnraidSensorBase`, `UnraidBinarySensorBase`, `UnraidSwitchBase`, `UnraidButtonBase`

---

## 3. Entity Implementation Patterns

### Base Classes

All entities extend base classes with `_attr_has_entity_name = True`, `unique_id`, and `device_info` properties.

### Setup Pattern

```python
coordinator: UnraidDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
entities = [AlwaysCreatedSensor(coordinator, entry), ...]
# Conditional: if coordinator.data.get(KEY_GPU): entities.append(GPUSensor(...))
# Dynamic: for disk in coordinator.data.get(KEY_DISKS, []): entities.append(DiskSensor(...))
async_add_entities(entities)
```

---

## 4. Naming Convention Rules

### 4.1 Entity ID Format

**Pattern**: `{platform}.{hostname}_{feature}_{subfeature}`

**Examples**:

- `sensor.tower_cpu_usage`
- `sensor.tower_ram_usage`
- `sensor.tower_cpu_temperature`
- `sensor.tower_array_usage`
- `sensor.tower_disk_disk1_usage`
- `sensor.tower_network_eth0_inbound`
- `binary_sensor.tower_array_started`
- `binary_sensor.tower_parity_check_running`
- `switch.tower_container_plex`
- `switch.tower_vm_windows_10`
- `button.tower_array_start`

**Rules**:

- Hostname is always lowercase
- Underscores separate components
- No duplicate hostname/domain in ID
- Dynamic entities include identifying suffix (disk name, interface name, container name, etc.)

### 4.2 Unique ID Format

**Pattern**: `f"{entry.entry_id}_{feature}_{subfeature}"`

**Examples**:

- `abc123_cpu_usage`
- `abc123_ram_usage`
- `abc123_array_usage`
- `abc123_disk_disk1_usage`
- `abc123_network_eth0_rx`
- `abc123_container_plex` (for switch)
- `abc123_array_start_button`

**Implementation**:

```python
@property
def unique_id(self) -> str:
    """Return unique ID."""
    return f"{self._entry.entry_id}_cpu_usage"

# For dynamic entities (fans, disks, network interfaces):
@property
def unique_id(self) -> str:
    """Return unique ID."""
    safe_name = self._interface_name.replace(" ", "_").replace("/", "_").lower()
    return f"{self._entry.entry_id}_network_{safe_name}_rx"
```

### 4.3 Device Info Pattern

All entities in this integration use a single device representing the Unraid server:

```python
@property
def device_info(self) -> dict[str, Any]:
    """Return device information."""
    system_data = self.coordinator.data.get(KEY_SYSTEM, {})
    hostname = system_data.get("hostname", "Unraid")

    return {
        "identifiers": {(DOMAIN, self._entry.entry_id)},
        "name": f"Unraid ({hostname})",
        "manufacturer": MANUFACTURER,  # "Lime Technology"
        "model": MODEL,  # "Unraid Server"
        "sw_version": system_data.get("version", "Unknown"),
    }
```

**Device Identifier**: `(DOMAIN, entry.entry_id)` - Single tuple for all entities

**Device Name**: `f"Unraid ({hostname})"` where hostname comes from system data (e.g., "Unraid (Tower)")

### 4.4 Entity Name Patterns

With `_attr_has_entity_name = True`, entity names are set via `_attr_name`:

- **System Sensors**: `"CPU Usage"`, `"RAM Usage"`, `"CPU Temperature"`, `"Uptime"`
- **Array Sensors**: `"Array Usage"`, `"Parity Check Progress"`
- **Dynamic Sensors**: `f"Fan {fan_name}"`, `f"Disk {disk_name} Usage"`, `f"Network {interface} Inbound"`
- **GPU Sensors**: `"GPU Name"`, `"GPU Utilization"`, `"GPU CPU Temperature"`, `"GPU Power"`
- **UPS Sensors**: `"UPS Battery"`, `"UPS Load"`, `"UPS Runtime"`, `"UPS Power"`
- **Binary Sensors**: `"Array Started"`, `"Parity Check Running"`, `"Parity Valid"`, `"UPS Connected"`
- **Switches**: `f"Container {container_name}"`, `f"VM {vm_name}"`
- **Buttons**: `"Start Array"`, `"Stop Array"`, `"Start Parity Check"`, `"Stop Parity Check"`

**Final Entity ID**: Home Assistant combines device name + entity name (e.g., `sensor.tower_cpu_usage`)

---

## 5. Entity Inventory and Groupings

### 5.1 System Sensors Group

| Entity Class                         | Entity Name             | Device Class   | Unit  | State Class   | Icon                | Notes                            |
| ------------------------------------ | ----------------------- | -------------- | ----- | ------------- | ------------------- | -------------------------------- |
| `UnraidCPUUsageSensor`               | CPU Usage               | `power_factor` | `%`   | `measurement` | `mdi:cpu-64-bit`    | Always created                   |
| `UnraidRAMUsageSensor`               | RAM Usage               | `power_factor` | `%`   | `measurement` | `mdi:memory`        | Always created                   |
| `UnraidCPUTemperatureSensor`         | CPU Temperature         | `temperature`  | `°C`  | `measurement` | `mdi:thermometer`   | Always created                   |
| `UnraidMotherboardTemperatureSensor` | Motherboard Temperature | `temperature`  | `°C`  | `measurement` | `mdi:thermometer`   | Conditional: only if available   |
| `UnraidFanSensor`                    | Fan {name}              | None           | `RPM` | `measurement` | `mdi:fan`           | Dynamic: one per fan             |
| `UnraidUptimeSensor`                 | Uptime                  | None           | None  | None          | `mdi:clock-outline` | Always created, formatted string |

**Unique ID Pattern**: `{entry_id}_cpu_usage`, `{entry_id}_ram_usage`, `{entry_id}_cpu_temperature`, `{entry_id}_motherboard_temperature`, `{entry_id}_fan_{safe_name}`, `{entry_id}_uptime`

### 5.2 Array and Storage Sensors Group

| Entity Class                 | Entity Name           | Device Class   | Unit | State Class   | Icon               | Notes                                      |
| ---------------------------- | --------------------- | -------------- | ---- | ------------- | ------------------ | ------------------------------------------ |
| `UnraidArrayUsageSensor`     | Array Usage           | `power_factor` | `%`  | `measurement` | `mdi:harddisk`     | Always created                             |
| `UnraidParityProgressSensor` | Parity Check Progress | `power_factor` | `%`  | `measurement` | `mdi:shield-check` | Always created, entity_category=diagnostic |
| `UnraidDiskUsageSensor`      | Disk {name} Usage     | None           | `%`  | `measurement` | `mdi:harddisk`     | Dynamic: one per disk                      |

**Unique ID Pattern**: `{entry_id}_array_usage`, `{entry_id}_parity_progress`, `{entry_id}_disk_{safe_id}_usage`

**Special Behavior**: Disk sensors cache last known value when disk is in standby to avoid spinning up the disk

### 5.3 GPU Sensors Group (Conditional)

| Entity Class                    | Entity Name         | Device Class   | Unit  | State Class        | Icon                 | Notes                                                          |
| ------------------------------- | ------------------- | -------------- | ----- | ------------------ | -------------------- | -------------------------------------------------------------- |
| `UnraidGPUNameSensor`           | GPU Name            | None           | None  | None               | `mdi:expansion-card` | Conditional: only if GPU detected                              |
| `UnraidGPUUtilizationSensor`    | GPU Utilization     | `power_factor` | `%`   | `measurement`      | `mdi:expansion-card` | Conditional: only if GPU detected                              |
| `UnraidGPUCPUTemperatureSensor` | GPU CPU Temperature | `temperature`  | `°C`  | `measurement`      | `mdi:thermometer`    | Conditional: only if GPU detected                              |
| `UnraidGPUPowerSensor`          | GPU Power           | `power`        | `W`   | `measurement`      | `mdi:lightning-bolt` | Conditional: only if GPU detected                              |
| `UnraidGPUEnergySensor`         | GPU Energy          | `energy`       | `kWh` | `total_increasing` | `mdi:power`          | Conditional: only if GPU detected, Energy Dashboard compatible |

**Unique ID Pattern**: `{entry_id}_gpu_name`, `{entry_id}_gpu_utilization`, `{entry_id}_gpu_cpu_temperature`, `{entry_id}_gpu_power`, `{entry_id}_gpu_energy`

**Conditional Creation**: All GPU sensors are created only when `coordinator.data.get(KEY_GPU, [])` is not empty

**Energy Dashboard**: GPU Energy sensor is compatible with Home Assistant Energy Dashboard and uses trapezoidal integration to convert GPU Power (W) to cumulative energy consumption (kWh)

### 5.4 UPS Sensors Group (Conditional)

| Entity Class             | Entity Name | Device Class   | Unit  | State Class        | Icon                 | Notes                                                          |
| ------------------------ | ----------- | -------------- | ----- | ------------------ | -------------------- | -------------------------------------------------------------- |
| `UnraidUPSBatterySensor` | UPS Battery | `battery`      | `%`   | `measurement`      | `mdi:battery`        | Conditional: only if UPS detected                              |
| `UnraidUPSLoadSensor`    | UPS Load    | `power_factor` | `%`   | `measurement`      | `mdi:battery`        | Conditional: only if UPS detected                              |
| `UnraidUPSRuntimeSensor` | UPS Runtime | `duration`     | `s`   | `measurement`      | `mdi:battery`        | Conditional: only if UPS detected                              |
| `UnraidUPSPowerSensor`   | UPS Power   | `power`        | `W`   | `measurement`      | `mdi:lightning-bolt` | Conditional: only if UPS detected                              |
| `UnraidUPSEnergySensor`  | UPS Energy  | `energy`       | `kWh` | `total_increasing` | `mdi:power`          | Conditional: only if UPS detected, Energy Dashboard compatible |

**Unique ID Pattern**: `{entry_id}_ups_battery`, `{entry_id}_ups_load`, `{entry_id}_ups_runtime`, `{entry_id}_ups_power`, `{entry_id}_ups_energy`

**Conditional Creation**: All UPS sensors are created only when `coordinator.data.get(KEY_UPS, {}).get("connected")` is True. This differs from the UPS Connected binary sensor, which is created whenever UPS data exists (using `coordinator.data.get(KEY_UPS)`), allowing it to show connection status even when the UPS is disconnected.

**Energy Dashboard**: UPS Energy sensor is compatible with Home Assistant Energy Dashboard and uses trapezoidal integration to convert UPS Power (W) to cumulative energy consumption (kWh)

### 5.5 Network Sensors Group (Dynamic)

| Entity Class            | Entity Name                  | Device Class | Unit    | State Class   | Icon                   | Notes                               |
| ----------------------- | ---------------------------- | ------------ | ------- | ------------- | ---------------------- | ----------------------------------- |
| `UnraidNetworkRXSensor` | Network {interface} Inbound  | `data_rate`  | `bit/s` | `measurement` | `mdi:download-network` | Dynamic: one per physical interface |
| `UnraidNetworkTXSensor` | Network {interface} Outbound | `data_rate`  | `bit/s` | `measurement` | `mdi:upload-network`   | Dynamic: one per physical interface |

**Unique ID Pattern**: `{entry_id}_network_{interface_name}_rx`, `{entry_id}_network_{interface_name}_tx`

**Dynamic Creation**: One RX and one TX sensor created for each physical network interface. Physical interfaces are detected using a custom regex function `_is_physical_network_interface()` that matches patterns like `eth0`, `wlan0`, `bond0`, `eno1`, `enp2s0`.

**Unit Note**: Uses `UnitOfDataRate.BITS_PER_SECOND`, not MB/s

### 5.6 Binary Sensors Group

| Entity Class                           | Entity Name          | Device Class   | Entity Category | Notes                              |
| -------------------------------------- | -------------------- | -------------- | --------------- | ---------------------------------- |
| `UnraidArrayStartedBinarySensor`       | Array Started        | `running`      | `diagnostic`    | Always created                     |
| `UnraidParityCheckRunningBinarySensor` | Parity Check Running | `running`      | `diagnostic`    | Always created                     |
| `UnraidParityValidBinarySensor`        | Parity Valid         | `problem`      | `diagnostic`    | Always created                     |
| `UnraidUPSConnectedBinarySensor`       | UPS Connected        | `connectivity` | `diagnostic`    | Conditional: only if UPS detected  |
| `UnraidContainerBinarySensor`          | {container_name}     | `running`      | None            | Dynamic: one per container         |
| `UnraidVMBinarySensor`                 | {vm_name}            | `running`      | None            | Dynamic: one per VM                |
| `UnraidNetworkBinarySensor`            | {interface_name}     | `connectivity` | `diagnostic`    | Dynamic: one per network interface |

**Unique ID Pattern**: `{entry_id}_array_started`, `{entry_id}_parity_check_running`, `{entry_id}_parity_valid`, `{entry_id}_ups_connected`, `{entry_id}_container_{container_name}`, `{entry_id}_vm_{vm_name}`, `{entry_id}_network_{interface_name}`

### 5.7 Switches Group (Dynamic)

| Entity Class            | Entity Name                | Icon                | Notes                      |
| ----------------------- | -------------------------- | ------------------- | -------------------------- |
| `UnraidContainerSwitch` | Container {container_name} | `mdi:docker`        | Dynamic: one per container |
| `UnraidVMSwitch`        | VM {vm_name}               | `mdi:desktop-tower` | Dynamic: one per VM        |

**Unique ID Pattern**: `{entry_id}_container_switch_{container_id}`, `{entry_id}_vm_switch_{vm_id}`

**Dynamic Creation**: Switches are created for each container in `coordinator.data.get(KEY_CONTAINERS, [])` and each VM in `coordinator.data.get(KEY_VMS, [])`

### 5.8 Buttons Group

| Entity Class                   | Entity Name        | Icon               | Entity Category | Notes          |
| ------------------------------ | ------------------ | ------------------ | --------------- | -------------- |
| `UnraidArrayStartButton`       | Start Array        | `mdi:array`        | None            | Always created |
| `UnraidArrayStopButton`        | Stop Array         | `mdi:array`        | None            | Always created |
| `UnraidParityCheckStartButton` | Start Parity Check | `mdi:shield-check` | None            | Always created |
| `UnraidParityCheckStopButton`  | Stop Parity Check  | `mdi:shield-off`   | None            | Always created |

**Unique ID Pattern**: `{entry_id}_array_start_button`, `{entry_id}_array_stop_button`, `{entry_id}_parity_check_start_button`, `{entry_id}_parity_check_stop_button`

**Note**: No reboot/shutdown buttons are implemented in this integration

---

## 6. Complete Attribute Reference

This section documents EVERY attribute for EVERY entity type based on the actual implementation.

### 6.1 CPU Usage Sensor Attributes

**Entity**: `sensor.{hostname}_cpu_usage` | **State**: CPU % (0-100) | **Class**: `UnraidCPUUsageSensor`

| Attribute     | Data Type | Description           | Example Value                                |
| ------------- | --------- | --------------------- | -------------------------------------------- |
| `cpu_model`   | `str`     | CPU model name        | `"Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz"` |
| `cpu_cores`   | `int`     | Number of CPU cores   | `6`                                          |
| `cpu_threads` | `int`     | Number of CPU threads | `12`                                         |

### 6.2 RAM Usage Sensor Attributes

**Entity**: `sensor.{hostname}_ram_usage` | **State**: RAM % (0-100) | **Class**: `UnraidRAMUsageSensor`

| Attribute      | Data Type | Description     | Example Value           |
| -------------- | --------- | --------------- | ----------------------- |
| `ram_total`    | `str`     | Total RAM in GB | `"32.00 GB"`            |
| `server_model` | `str`     | Server model    | `"Supermicro X11SSH-F"` |

### 6.3 CPU Temperature Sensor Attributes

**Entity**: `sensor.{hostname}_cpu_temperature`
**State Value**: CPU temperature in °C
**Class**: `UnraidCPUTemperatureSensor`

**No extra attributes** - This sensor only provides the temperature value.

### 6.4 Motherboard Temperature Sensor Attributes

**Entity**: `sensor.{hostname}_motherboard_temperature`
**State Value**: Motherboard temperature in °C
**Class**: `UnraidMotherboardTemperatureSensor`

**No extra attributes** - This sensor only provides the temperature value.

**Conditional Creation**: Only created when `coordinator.data.get(KEY_SYSTEM, {}).get("motherboard_temp_celsius")` is not None.

### 6.5 Fan Sensor Attributes

**Entity**: `sensor.{hostname}_fan_{name}`
**State Value**: Fan speed in RPM
**Class**: `UnraidFanSensor`

**No extra attributes** - This sensor only provides the RPM value.

**Dynamic Creation**: One sensor created for each fan in `coordinator.data.get(KEY_SYSTEM, {}).get("fans", [])`.

### 6.6 Uptime Sensor Attributes

**Entity**: `sensor.{hostname}_uptime` | **State**: Human-readable uptime | **Class**: `UnraidUptimeSensor`

| Attribute        | Data Type | Description           | Example Value |
| ---------------- | --------- | --------------------- | ------------- |
| `hostname`       | `str`     | Server hostname       | `"Tower"`     |
| `uptime_seconds` | `int`     | Raw uptime in seconds | `1234567`     |

### 6.7 Array Usage Sensor Attributes

**Entity**: `sensor.{hostname}_array_usage` | **State**: Array % (0-100) | **Class**: `UnraidArrayUsageSensor`

| Attribute          | Data Type | Description            | Example Value             |
| ------------------ | --------- | ---------------------- | ------------------------- |
| `array_state`      | `str`     | Array state            | `"Started"` / `"Stopped"` |
| `num_disks`        | `int`     | Total number of disks  | `6`                       |
| `num_data_disks`   | `int`     | Number of data disks   | `4`                       |
| `num_parity_disks` | `int`     | Number of parity disks | `2`                       |

### 6.8 Parity Check Progress Sensor Attributes

**Entity**: `sensor.{hostname}_parity_progress`
**State Value**: Parity check progress percentage (0-100)
**Class**: `UnraidParityProgressSensor`

**No extra attributes** - This sensor only provides the progress percentage.

**Entity Category**: `diagnostic`

### 6.9 Disk Usage Sensor Attributes

**Entity**: `sensor.{hostname}_disk_{name}_usage`
**State Value**: Disk usage percentage (0-100)
**Class**: `UnraidDiskUsageSensor`

| Attribute             | Data Type      | Description                         | Example Value                       |
| --------------------- | -------------- | ----------------------------------- | ----------------------------------- |
| `device`              | `str`          | Device path                         | `"/dev/sda1"`                       |
| `status`              | `str`          | Disk status                         | `"DISK_OK"`                         |
| `filesystem`          | `str`          | Filesystem type                     | `"xfs"`                             |
| `mount_point`         | `str`          | Mount point path                    | `"/mnt/disk1"`                      |
| `spin_state`          | `str`          | Disk spin state                     | `"active"` / `"standby"` / `"idle"` |
| `size`                | `str`          | Total disk size                     | `"4000.00 GB"`                      |
| `used`                | `str`          | Used disk space                     | `"2500.00 GB"`                      |
| `free`                | `str`          | Free disk space                     | `"1500.00 GB"`                      |
| `smart_status`        | `str`          | SMART health status                 | `"PASSED"`                          |
| `smart_errors`        | `int`          | Number of SMART errors              | `0`                                 |
| `temperature_celsius` | `int` or `str` | Disk temperature or standby message | `35` or `"Disk in standby"`         |

**Dynamic Creation**: One sensor created for each disk in `coordinator.data.get(KEY_DISKS, [])`.

**Special Behavior**: When disk is in standby (`spin_state == "standby"`), the sensor returns the last known value to avoid spinning up the disk. Temperature shows "Disk in standby" when disk is spun down.

### 6.10 GPU Name Sensor Attributes

**Entity**: `sensor.{hostname}_gpu_name` | **State**: GPU name | **Class**: `UnraidGPUNameSensor`

| Attribute            | Data Type | Description        | Example Value  |
| -------------------- | --------- | ------------------ | -------------- |
| `gpu_driver_version` | `str`     | GPU driver version | `"535.129.03"` |

**Conditional Creation**: Only created when GPU detected.

### 6.11 GPU Utilization Sensor Attributes

**Entity**: `sensor.{hostname}_gpu_utilization`
**State Value**: GPU utilization percentage (0-100)
**Class**: `UnraidGPUUtilizationSensor`

**No extra attributes** - This sensor only provides the utilization percentage.

**Conditional Creation**: Only created when GPU is detected.

### 6.12 GPU CPU Temperature Sensor Attributes

**Entity**: `sensor.{hostname}_gpu_cpu_temperature`
**State Value**: GPU CPU temperature in °C (for integrated GPUs)
**Class**: `UnraidGPUCPUTemperatureSensor`

**No extra attributes** - This sensor only provides the temperature value.

**Conditional Creation**: Only created when GPU is detected.

### 6.13 GPU Power Sensor Attributes

**Entity**: `sensor.{hostname}_gpu_power`
**State Value**: GPU power consumption in Watts
**Class**: `UnraidGPUPowerSensor`

**No extra attributes** - This sensor only provides the power value.

**Conditional Creation**: Only created when GPU is detected.

### 6.14 UPS Battery Sensor Attributes

**Entity**: `sensor.{hostname}_ups_battery`
**State Value**: UPS battery charge percentage (0-100)
**Class**: `UnraidUPSBatterySensor`

**No extra attributes** - This sensor only provides the battery percentage.

**Conditional Creation**: Only created when `coordinator.data.get(KEY_UPS)` is not None.

### 6.15 UPS Load Sensor Attributes

**Entity**: `sensor.{hostname}_ups_load`
**State Value**: UPS load percentage (0-100)
**Class**: `UnraidUPSLoadSensor`

**No extra attributes** - This sensor only provides the load percentage.

**Conditional Creation**: Only created when UPS is detected.

### 6.16 UPS Runtime Sensor Attributes

**Entity**: `sensor.{hostname}_ups_runtime`
**State Value**: UPS runtime left in seconds
**Class**: `UnraidUPSRuntimeSensor`

**No extra attributes** - This sensor only provides the runtime value.

**Conditional Creation**: Only created when UPS is detected.

### 6.17 UPS Power Sensor Attributes

**Entity**: `sensor.{hostname}_ups_power`
**State Value**: UPS power consumption in Watts
**Class**: `UnraidUPSPowerSensor`

| Attribute        | Data Type | Description                | Example Value               |
| ---------------- | --------- | -------------------------- | --------------------------- |
| `ups_status`     | `str`     | UPS status                 | `"ONLINE"` / `"ONBATT"`     |
| `ups_model`      | `str`     | UPS model                  | `"CyberPower CP1500PFCLCD"` |
| `load_percent`   | `float`   | Load percentage (optional) | `45.0`                      |
| `input_voltage`  | `float`   | Input voltage (optional)   | `120.0`                     |
| `output_voltage` | `float`   | Output voltage (optional)  | `120.0`                     |

**Note**: `load_percent`, `input_voltage`, and `output_voltage` are only included if available in the UPS data.

**Conditional Creation**: Only when UPS detected. **Energy Dashboard**: Compatible.

### 6.18 Network RX/TX Sensor Attributes

**Entity**: `sensor.{hostname}_network_{interface}_inbound` / `outbound`
**State Value**: Network traffic in bits per second
**Class**: `UnraidNetworkRXSensor` / `UnraidNetworkTXSensor`

| Attribute       | Data Type | Description      | Example Value         |
| --------------- | --------- | ---------------- | --------------------- |
| `network_mac`   | `str`     | MAC address      | `"00:11:22:33:44:55"` |
| `network_ip`    | `str`     | IP address       | `"192.168.1.100"`     |
| `network_speed` | `str`     | Link speed       | `"1000 Mbps"`         |
| `status`        | `str`     | Interface status | `"up"` / `"down"`     |
| `interface`     | `str`     | Interface name   | `"eth0"`              |

**Dynamic Creation**: One RX and one TX sensor per physical interface.

### 6.19 Binary Sensor Attributes

#### Array Started Binary Sensor

**Entity**: `binary_sensor.{hostname}_array_started`
**State**: `on` (started) / `off` (stopped)
**Class**: `UnraidArrayStartedBinarySensor`

**No extra attributes** - This sensor only provides the on/off state.

**Device Class**: `running`
**Entity Category**: `diagnostic`

#### Parity Check Running Binary Sensor

**Entity**: `binary_sensor.{hostname}_parity_check_running`
**State**: `on` (running) / `off` (not running)
**Class**: `UnraidParityCheckRunningBinarySensor`

**No extra attributes** - This sensor only provides the on/off state.

**Device Class**: `running`
**Entity Category**: `diagnostic`

#### Parity Valid Binary Sensor

**Entity**: `binary_sensor.{hostname}_parity_valid`
**State**: `on` (problem/invalid) / `off` (valid)
**Class**: `UnraidParityValidBinarySensor`

**No extra attributes** - This sensor only provides the on/off state.

**Device Class**: `problem`
**Entity Category**: `diagnostic`

**Note**: This sensor is inverted - `on` means there's a problem (parity is invalid).

#### UPS Connected Binary Sensor

**Entity**: `binary_sensor.{hostname}_ups_connected`
**State**: `on` (connected) / `off` (disconnected)
**Class**: `UnraidUPSConnectedBinarySensor`

**No extra attributes** - This sensor only provides the on/off state.

**Device Class**: `connectivity`
**Entity Category**: `diagnostic`

**Conditional Creation**: Only created when UPS data is available (`coordinator.data.get(KEY_UPS)` is not None). This differs from UPS sensors (battery, load, runtime, power), which are only created when the UPS is actually connected (`coordinator.data.get(KEY_UPS, {}).get("connected")` is True). The binary sensor exists whenever UPS data is available so it can show the connection status even when the UPS is disconnected.

#### Container Binary Sensor

**Entity**: `binary_sensor.{hostname}_container_{container_name}`
**State**: `on` (running) / `off` (stopped)
**Class**: `UnraidContainerBinarySensor`

**No extra attributes** - This sensor only provides the on/off state.

**Device Class**: `running`

**Dynamic Creation**: One sensor created for each container.

#### VM Binary Sensor

**Entity**: `binary_sensor.{hostname}_vm_{vm_name}`
**State**: `on` (running) / `off` (stopped)
**Class**: `UnraidVMBinarySensor`

**No extra attributes** - This sensor only provides the on/off state.

**Device Class**: `running`

**Dynamic Creation**: One sensor created for each VM.

#### Network Binary Sensor

**Entity**: `binary_sensor.{hostname}_network_{interface_name}`
**State**: `on` (up) / `off` (down)
**Class**: `UnraidNetworkBinarySensor`

**No extra attributes** - This sensor only provides the on/off state.

**Device Class**: `connectivity`
**Entity Category**: `diagnostic`

**Dynamic Creation**: One sensor created for each network interface.

### 6.20 Switch Attributes

#### Container Switch

**Entity**: `switch.{hostname}_container_{container_name}`
**State**: `on` (running) / `off` (stopped)
**Class**: `UnraidContainerSwitch`

**No extra attributes** - This switch only provides the on/off state.

**Dynamic Creation**: One switch created for each container.

#### VM Switch

**Entity**: `switch.{hostname}_vm_{vm_name}`
**State**: `on` (running) / `off` (stopped)
**Class**: `UnraidVMSwitch`

**No extra attributes** - This switch only provides the on/off state.

**Dynamic Creation**: One switch created for each VM.

### 6.21 Button Attributes

All button entities in this integration have **no extra attributes** - they only provide the press action.

**Entity Classes**:

- `UnraidArrayStartButton` - `button.{hostname}_array_start`
- `UnraidArrayStopButton` - `button.{hostname}_array_stop`
- `UnraidParityCheckStartButton` - `button.{hostname}_parity_check_start`
- `UnraidParityCheckStopButton` - `button.{hostname}_parity_check_stop`

**Entity Category**: `config`

**Note**: No reboot/shutdown buttons are implemented in this integration.

---

## 7. Device Info Standards

All entities use a **single device** representing the Unraid server.

**Device Identifier**: `(DOMAIN, entry.entry_id)` - Single tuple for all entities
**Device Name**: `f"Unraid ({hostname})"` where hostname comes from system data (e.g., "Unraid (Tower)")
**Manufacturer**: `"Lime Technology"`
**Model**: `"Unraid Server"`

```python
@property
def device_info(self) -> dict[str, Any]:
    """Return device information."""
    system_data = self.coordinator.data.get(KEY_SYSTEM, {})
    hostname = system_data.get("hostname", "Unraid")

    return {
        "identifiers": {(DOMAIN, self._entry.entry_id)},
        "name": f"Unraid ({hostname})",
        "manufacturer": MANUFACTURER,
        "model": MODEL,
        "sw_version": system_data.get("version", "Unknown"),
    }
```

---

## 8. Data Coordinator Patterns

**Data Structure**: `coordinator.data` contains keys: `KEY_SYSTEM`, `KEY_ARRAY`, `KEY_DISKS`, `KEY_GPU`, `KEY_UPS`, `KEY_NETWORK`, `KEY_CONTAINERS`, `KEY_VMS`

**Access Pattern**: `coordinator: UnraidDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]`

**Safe Access**: Always use `self.coordinator.data.get(KEY_SYSTEM, {}).get("cpu_usage_percent", 0)`

**Refresh**: `await self.coordinator.async_request_refresh()`

---

## 9. Code Examples

### Creating a New Sensor

```python
class UnraidNewMetricSensor(UnraidSensorBase):
    _attr_name = "New Metric"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:icon-name"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_new_metric"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(KEY_SYSTEM, {}).get("new_metric_value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        system_data = self.coordinator.data.get(KEY_SYSTEM, {})
        return {"attribute_1": system_data.get("attr1")}
```

### Creating a Dynamic Sensor

```python
class UnraidDiskSensor(UnraidSensorBase):
    def __init__(self, coordinator, entry, disk_id, disk_name):
        super().__init__(coordinator, entry)
        self._disk_id = disk_id
        self._attr_name = f"Disk {disk_name} Usage"

    @property
    def unique_id(self) -> str:
        safe_id = self._disk_id.replace(" ", "_").lower()
        return f"{self._entry.entry_id}_disk_{safe_id}_usage"

    @property
    def native_value(self) -> float | None:
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            if disk.get("id") == self._disk_id:
                return disk.get("used_percent")
        return None

# In async_setup_entry:
for disk in coordinator.data.get(KEY_DISKS, []):
    entities.append(UnraidDiskSensor(coordinator, entry, disk["id"], disk["name"]))
```

---

## Summary

This rule file documents the complete architecture, patterns, and standards for Unraid Home Assistant integrations. When creating new entities:

1. **Follow the naming conventions** for entity IDs, unique IDs, and device IDs
2. **Use the appropriate base class** (UnraidSensorBase, UnraidBinarySensorBase, etc.)
3. **Register sensors** using the factory/registry pattern
4. **Document all attributes** with data types and examples
5. **Implement proper availability checks** using coordinator and custom logic
6. **Use safe data access patterns** with .get() and defaults
7. **Follow the device info structure** for proper device grouping
8. **Respect update priorities** for optimal performance
9. **Handle standby disks** by caching last known values

Every new entity should be indistinguishable from existing ones by following these patterns exactly, regardless of the underlying communication protocol (SSH, GraphQL, REST API, etc.).
