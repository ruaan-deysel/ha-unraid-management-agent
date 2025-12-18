"""Sensor platform for Unraid Management Agent."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UnraidDataUpdateCoordinator
from .const import (
    ATTR_ARRAY_STATE,
    ATTR_CPU_CORES,
    ATTR_CPU_MODEL,
    ATTR_CPU_THREADS,
    ATTR_GPU_DRIVER_VERSION,
    ATTR_GPU_NAME,
    ATTR_HOSTNAME,
    ATTR_NETWORK_IP,
    ATTR_NETWORK_MAC,
    ATTR_NETWORK_SPEED,
    ATTR_NUM_DATA_DISKS,
    ATTR_NUM_DISKS,
    ATTR_NUM_PARITY_DISKS,
    ATTR_RAM_TOTAL,
    ATTR_SERVER_MODEL,
    ATTR_UPS_MODEL,
    ATTR_UPS_STATUS,
    DOMAIN,
    ICON_ARRAY,
    ICON_CONTAINER,
    ICON_CPU,
    ICON_GPU,
    ICON_MEMORY,
    ICON_NETWORK,
    ICON_NOTIFICATION,
    ICON_PARITY,
    ICON_POWER,
    ICON_SHARE,
    ICON_TEMPERATURE,
    ICON_UPS,
    ICON_UPTIME,
    ICON_ZFS_ARC,
    ICON_ZFS_POOL,
    KEY_ARRAY,
    KEY_DISKS,
    KEY_GPU,
    KEY_NETWORK,
    KEY_NOTIFICATIONS,
    KEY_SHARES,
    KEY_SYSTEM,
    KEY_UPS,
    KEY_ZFS_ARC,
    KEY_ZFS_POOLS,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


def _is_physical_network_interface(interface_name: str) -> bool:
    """
    Check if the network interface is a physical interface.

    Only include physical interfaces like eth0, eth1, wlan0, bond0, etc.
    Exclude virtual interfaces (veth*, br-*, docker*, virbr*) and loopback (lo).
    """
    # Patterns for physical interfaces
    physical_patterns = [
        r"^eth\d+$",  # Ethernet: eth0, eth1, etc.
        r"^wlan\d+$",  # Wireless: wlan0, wlan1, etc.
        r"^bond\d+$",  # Bonded interfaces: bond0, bond1, etc.
        r"^eno\d+$",  # Onboard Ethernet: eno1, eno2, etc.
        r"^enp\d+s\d+$",  # PCI Ethernet: enp2s0, etc.
    ]

    # Check if interface matches any physical pattern
    for pattern in physical_patterns:
        if re.match(pattern, interface_name):
            return True

    return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Unraid sensor entities."""
    coordinator: UnraidDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug(
        "Setting up Unraid sensors, coordinator data keys: %s", coordinator.data.keys()
    )

    entities: list[SensorEntity] = []

    # System sensors
    entities.extend(
        [
            UnraidCPUUsageSensor(coordinator, entry),
            UnraidRAMUsageSensor(coordinator, entry),
            UnraidCPUTemperatureSensor(coordinator, entry),
            UnraidUptimeSensor(coordinator, entry),
        ]
    )

    # Motherboard temperature sensor (if available)
    system_data = coordinator.data.get(KEY_SYSTEM) or {}
    if system_data.get("motherboard_temp_celsius") is not None:
        entities.append(UnraidMotherboardTemperatureSensor(coordinator, entry))

    # Fan sensors (dynamic, one per fan)
    fans = system_data.get("fans") or []
    for fan in fans:
        fan_name = fan.get("name", "unknown")
        entities.append(UnraidFanSensor(coordinator, entry, fan_name))

    # Array sensors
    entities.extend(
        [
            UnraidArrayUsageSensor(coordinator, entry),
            UnraidParityProgressSensor(coordinator, entry),
        ]
    )

    # Disk sensors (dynamic, one per disk)
    disks = coordinator.data.get(KEY_DISKS, [])
    for disk in disks:
        disk_id = disk.get("id", disk.get("name", "unknown"))
        disk_name = disk.get("name", disk_id)
        disk_role = disk.get("role", "")

        # Create health sensor for physical disks only (skip virtual filesystems)
        # Virtual filesystems like docker_vdisk and log don't have SMART data
        if disk_role not in ("docker_vdisk", "log"):
            entities.append(
                UnraidDiskHealthSensor(coordinator, entry, disk_id, disk_name)
            )

        # Skip parity disks for usage sensors - they don't have usage data
        # Check the disk name, not the ID (ID is the device ID, name is "parity", "disk1", etc.)
        if disk_name not in ("parity", "parity2"):
            # Create usage sensor for each non-parity disk
            entities.append(
                UnraidDiskUsageSensor(coordinator, entry, disk_id, disk_name)
            )

    # Docker vDisk usage sensor (if available)
    docker_vdisk = next((d for d in disks if d.get("role") == "docker_vdisk"), None)
    _LOGGER.debug("Docker vDisk found: %s", docker_vdisk is not None)
    if docker_vdisk:
        _LOGGER.debug("Creating Docker vDisk usage sensor")
        entities.append(UnraidDockerVDiskUsageSensor(coordinator, entry))

    # Log filesystem usage sensor (if available)
    log_filesystem = next((d for d in disks if d.get("role") == "log"), None)
    _LOGGER.debug("Log filesystem found: %s", log_filesystem is not None)
    if log_filesystem:
        _LOGGER.debug("Creating Log filesystem usage sensor")
        entities.append(UnraidLogFilesystemUsageSensor(coordinator, entry))

    # GPU sensors (if GPU available)
    if coordinator.data.get(KEY_GPU):
        entities.extend(
            [
                UnraidGPUUtilizationSensor(coordinator, entry),
                UnraidGPUCPUTemperatureSensor(coordinator, entry),
                UnraidGPUPowerSensor(coordinator, entry),
                UnraidGPUEnergySensor(coordinator, entry),
            ]
        )

    # UPS sensors (if UPS connected)
    # Only create if UPS data exists, is not empty, and UPS is connected
    # When no UPS hardware is present, the API returns null/error and coordinator sets KEY_UPS to {}
    ups_data = coordinator.data.get(KEY_UPS, {})
    if (
        ups_data
        and isinstance(ups_data, dict)
        and len(ups_data) > 0
        and ups_data.get("connected")
    ):
        entities.extend(
            [
                UnraidUPSBatterySensor(coordinator, entry),
                UnraidUPSLoadSensor(coordinator, entry),
                UnraidUPSRuntimeSensor(coordinator, entry),
                UnraidUPSPowerSensor(coordinator, entry),
                UnraidUPSEnergySensor(coordinator, entry),
            ]
        )

    # Network sensors (only physical interfaces that are connected)
    for interface in coordinator.data.get(KEY_NETWORK, []):
        interface_name = interface.get("name", "unknown")
        interface_state = interface.get("state", "down")
        # Only create sensors for physical network interfaces that are up/connected
        if _is_physical_network_interface(interface_name) and interface_state == "up":
            entities.extend(
                [
                    UnraidNetworkRXSensor(coordinator, entry, interface_name),
                    UnraidNetworkTXSensor(coordinator, entry, interface_name),
                ]
            )

    # Share sensors (dynamic, one per share)
    for share in coordinator.data.get(KEY_SHARES, []):
        share_name = share.get("name", "unknown")
        entities.append(UnraidShareUsageSensor(coordinator, entry, share_name))

    # ZFS pool sensors (if ZFS pools available)
    # Only create if ZFS pools data exists and is not empty
    zfs_pools = coordinator.data.get(KEY_ZFS_POOLS, [])
    if zfs_pools and isinstance(zfs_pools, list) and len(zfs_pools) > 0:
        for pool in zfs_pools:
            pool_name = pool.get("name", "unknown")
            entities.extend(
                [
                    UnraidZFSPoolUsageSensor(coordinator, entry, pool_name),
                    UnraidZFSPoolHealthSensor(coordinator, entry, pool_name),
                ]
            )

    # ZFS ARC sensors (if ZFS ARC data available)
    # Only create if ZFS ARC data exists and is not empty
    zfs_arc = coordinator.data.get(KEY_ZFS_ARC, {})
    if zfs_arc and isinstance(zfs_arc, dict) and len(zfs_arc) > 0:
        entities.append(UnraidZFSARCHitRatioSensor(coordinator, entry))

    # Notification sensor (if notifications available)
    if coordinator.data.get(KEY_NOTIFICATIONS) is not None:
        entities.append(UnraidNotificationsSensor(coordinator, entry))

    _LOGGER.debug("Adding %d Unraid sensor entities", len(entities))
    async_add_entities(entities)


class UnraidSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Unraid sensors."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._entry = entry

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        system_data = self.coordinator.data.get(KEY_SYSTEM, {})
        hostname = system_data.get("hostname", "Unraid")
        version = system_data.get("version", "Unknown")
        agent_version = system_data.get("agent_version")
        host = self._entry.data.get(CONF_HOST, "")

        device_info_dict = {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": hostname,
            "manufacturer": MANUFACTURER,
            "model": f"Unraid {version}",
            "sw_version": version,
            "configuration_url": f"http://{host}",
        }

        # Add Management Agent version if available
        if agent_version:
            device_info_dict["hw_version"] = agent_version

        return device_info_dict


# System Sensors


class UnraidCPUUsageSensor(UnraidSensorBase):
    """CPU usage sensor."""

    _attr_name = "CPU Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_CPU
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_cpu_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        cpu_usage = self.coordinator.data.get(KEY_SYSTEM, {}).get("cpu_usage_percent")
        if cpu_usage is not None:
            return round(cpu_usage, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        system_data = self.coordinator.data.get(KEY_SYSTEM, {})

        # Note: cpu_cores from API is incorrect (shows 1 instead of actual core count)
        # cpu_threads is correct, so we can infer cores if needed
        cpu_cores = system_data.get("cpu_cores", 0)
        cpu_threads = system_data.get("cpu_threads", 0)

        # If cores seems wrong (1 core with 12 threads is impossible),
        # assume hyperthreading and divide threads by 2
        if cpu_cores == 1 and cpu_threads > 2:
            cpu_cores = cpu_threads // 2

        attrs = {
            ATTR_CPU_MODEL: system_data.get("cpu_model"),
            ATTR_CPU_CORES: cpu_cores,
            ATTR_CPU_THREADS: cpu_threads,
        }

        # Add CPU frequency if available
        cpu_mhz = system_data.get("cpu_mhz")
        if cpu_mhz:
            attrs["cpu_frequency"] = f"{cpu_mhz:.0f} MHz"

        return attrs


class UnraidRAMUsageSensor(UnraidSensorBase):
    """RAM usage sensor."""

    _attr_name = "RAM Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_MEMORY
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ram_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        ram_usage = self.coordinator.data.get(KEY_SYSTEM, {}).get("ram_usage_percent")
        if ram_usage is not None:
            return round(ram_usage, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        system_data = self.coordinator.data.get(KEY_SYSTEM, {})
        ram_total = system_data.get("ram_total_bytes", 0)
        ram_used = system_data.get("ram_used_bytes", 0)
        ram_free = system_data.get("ram_free_bytes", 0)
        ram_cached = system_data.get("ram_cached_bytes", 0)
        ram_buffers = system_data.get("ram_buffers_bytes", 0)

        attrs = {
            ATTR_RAM_TOTAL: (
                f"{ram_total / (1024**3):.2f} GB" if ram_total else "Unknown"
            ),
            ATTR_SERVER_MODEL: system_data.get("server_model"),
        }

        # Add detailed memory breakdown if available
        if ram_used:
            attrs["ram_used"] = f"{ram_used / (1024**3):.2f} GB"
        if ram_free:
            attrs["ram_free"] = f"{ram_free / (1024**3):.2f} GB"
        if ram_cached:
            attrs["ram_cached"] = f"{ram_cached / (1024**3):.2f} GB"
        if ram_buffers:
            attrs["ram_buffers"] = f"{ram_buffers / (1024**3):.2f} GB"

        # Calculate available memory (free + cached + buffers)
        if ram_free and ram_cached and ram_buffers:
            ram_available = ram_free + ram_cached + ram_buffers
            attrs["ram_available"] = f"{ram_available / (1024**3):.2f} GB"

        return attrs


class UnraidCPUTemperatureSensor(UnraidSensorBase):
    """CPU temperature sensor."""

    _attr_name = "CPU Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_TEMPERATURE
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_cpu_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get(KEY_SYSTEM, {}).get("cpu_temp_celsius")


class UnraidMotherboardTemperatureSensor(UnraidSensorBase):
    """Motherboard temperature sensor."""

    _attr_name = "Motherboard Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_TEMPERATURE
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_motherboard_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get(KEY_SYSTEM, {}).get("motherboard_temp_celsius")


class UnraidFanSensor(UnraidSensorBase):
    """Fan speed sensor."""

    _attr_native_unit_of_measurement = "RPM"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fan"
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        fan_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._fan_name = fan_name
        # Clean up fan name: remove hwmon prefixes and make user-friendly
        friendly_name = self._clean_fan_name(fan_name)
        self._attr_name = f"Fan {friendly_name}"

    @staticmethod
    def _clean_fan_name(fan_name: str) -> str:
        """Clean up fan name to be user-friendly."""
        import re

        # Remove hwmon prefixes (e.g., "hwmon4_fan1" -> "1")
        cleaned = re.sub(r"^hwmon\d+_fan", "", fan_name)
        # If we got a number, return it as is
        if cleaned.isdigit():
            return cleaned
        # Otherwise return the original name
        return fan_name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        # Sanitize fan name for unique ID
        safe_name = self._fan_name.replace(" ", "_").replace("/", "_").lower()
        return f"{self._entry.entry_id}_fan_{safe_name}"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        system_data = self.coordinator.data.get(KEY_SYSTEM) or {}
        fans = system_data.get("fans") or []
        for fan in fans:
            if fan.get("name") == self._fan_name:
                return fan.get("rpm")
        return None


class UnraidUptimeSensor(UnraidSensorBase):
    """Uptime sensor."""

    _attr_name = "Uptime"
    _attr_icon = ICON_UPTIME

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_uptime"

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """
        Format uptime seconds into human-readable string.

        Returns format like: "42 days, 21 hours, 31 minutes, 49 seconds"
        Matches the Unraid web UI display format.
        """
        if seconds is None:
            return "Unknown"

        # Calculate time components
        years, remainder = divmod(seconds, 31536000)  # 365 days
        months, remainder = divmod(remainder, 2592000)  # 30 days
        days, remainder = divmod(remainder, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds_remaining = divmod(remainder, 60)

        # Build the formatted string
        parts = []
        if years > 0:
            parts.append(f"{years} year{'s' if years != 1 else ''}")
        if months > 0:
            parts.append(f"{months} month{'s' if months != 1 else ''}")
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds_remaining > 0 or not parts:  # Always show seconds if nothing else
            parts.append(
                f"{seconds_remaining} second{'s' if seconds_remaining != 1 else ''}"
            )

        return ", ".join(parts)

    @property
    def native_value(self) -> str | None:
        """Return the state as human-readable uptime."""
        uptime_seconds = self.coordinator.data.get(KEY_SYSTEM, {}).get("uptime_seconds")
        if uptime_seconds is not None:
            return self._format_uptime(uptime_seconds)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        system_data = self.coordinator.data.get(KEY_SYSTEM, {})
        uptime_seconds = system_data.get("uptime_seconds")

        attributes = {
            ATTR_HOSTNAME: system_data.get("hostname"),
        }

        # Include raw seconds value for use in automations/templates
        if uptime_seconds is not None:
            attributes["uptime_seconds"] = uptime_seconds

        # Include Management Agent version for diagnostics
        agent_version = system_data.get("agent_version")
        if agent_version:
            attributes["management_agent_version"] = agent_version

        return attributes


# Array Sensors


class UnraidArrayUsageSensor(UnraidSensorBase):
    """Array usage sensor."""

    _attr_name = "Array Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_ARRAY
    _attr_suggested_display_precision = 1  # Already set - Fix #2 complete

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_array_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get(KEY_ARRAY, {}).get("used_percent")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        array_data = self.coordinator.data.get(KEY_ARRAY, {})
        return {
            ATTR_ARRAY_STATE: array_data.get("state"),
            ATTR_NUM_DISKS: array_data.get("num_disks"),
            ATTR_NUM_DATA_DISKS: array_data.get("num_data_disks"),
            ATTR_NUM_PARITY_DISKS: array_data.get("num_parity_disks"),
        }


class UnraidParityProgressSensor(UnraidSensorBase):
    """Parity check progress sensor."""

    _attr_name = "Parity Check Progress"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_PARITY
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_progress"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get(KEY_ARRAY, {}).get("parity_check_progress")


# GPU Sensors


class UnraidGPUUtilizationSensor(UnraidSensorBase):
    """GPU utilization sensor."""

    _attr_name = "GPU Utilization"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_GPU
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_utilization"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        if gpu_list and len(gpu_list) > 0:
            return gpu_list[0].get("utilization_gpu_percent")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        if gpu_list and len(gpu_list) > 0:
            return {
                ATTR_GPU_NAME: gpu_list[0].get("name"),
                ATTR_GPU_DRIVER_VERSION: gpu_list[0].get("driver_version"),
            }
        return {}


class UnraidGPUCPUTemperatureSensor(UnraidSensorBase):
    """GPU CPU temperature sensor (for iGPUs)."""

    _attr_name = "GPU CPU Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_TEMPERATURE
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_cpu_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        if gpu_list and len(gpu_list) > 0:
            return gpu_list[0].get("cpu_temperature_celsius")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        if gpu_list and len(gpu_list) > 0:
            return {
                ATTR_GPU_NAME: gpu_list[0].get("name"),
                ATTR_GPU_DRIVER_VERSION: gpu_list[0].get("driver_version"),
            }
        return {}


class UnraidGPUPowerSensor(UnraidSensorBase):
    """GPU power consumption sensor."""

    _attr_name = "GPU Power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_POWER
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_power"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        if gpu_list and len(gpu_list) > 0:
            return gpu_list[0].get("power_draw_watts")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        if gpu_list and len(gpu_list) > 0:
            return {
                ATTR_GPU_NAME: gpu_list[0].get("name"),
                ATTR_GPU_DRIVER_VERSION: gpu_list[0].get("driver_version"),
            }
        return {}


class UnraidGPUEnergySensor(UnraidSensorBase):
    """GPU energy consumption sensor for Energy Dashboard (integrates power over time)."""

    _attr_name = "GPU Energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = ICON_POWER
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._total_energy = 0.0  # Total energy in kWh
        self._last_power = None  # Last power reading in W
        self._last_update = None  # Last update timestamp

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_energy"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        if not gpu_list or len(gpu_list) == 0:
            return self._total_energy if self._total_energy > 0 else None

        power_watts = gpu_list[0].get("power_draw_watts")
        if power_watts is None:
            return self._total_energy if self._total_energy > 0 else None

        now = datetime.now()

        # If we have previous data, calculate energy consumed since last update
        if self._last_power is not None and self._last_update is not None:
            time_diff_hours = (now - self._last_update).total_seconds() / 3600
            if time_diff_hours > 0:
                # Use trapezoidal rule for integration (average of two power readings)
                avg_power = (self._last_power + power_watts) / 2
                energy_kwh = (avg_power * time_diff_hours) / 1000  # Convert W*h to kWh
                self._total_energy += energy_kwh

        # Update tracking variables
        self._last_power = power_watts
        self._last_update = now

        return round(self._total_energy, 3) if self._total_energy > 0 else 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        gpu_list = self.coordinator.data.get(KEY_GPU, [])
        attributes = {
            "integration_method": "trapezoidal",
            "source_sensor": "GPU Power",
        }

        if gpu_list and len(gpu_list) > 0:
            gpu_name = gpu_list[0].get("name")
            if gpu_name:
                attributes[ATTR_GPU_NAME] = gpu_name

            driver_version = gpu_list[0].get("driver_version")
            if driver_version:
                attributes[ATTR_GPU_DRIVER_VERSION] = driver_version

        return attributes


# UPS Sensors


class UnraidUPSBatterySensor(UnraidSensorBase):
    """UPS battery sensor."""

    _attr_name = "UPS Battery"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_UPS
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_battery"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get(KEY_UPS, {}).get("battery_charge_percent")


class UnraidUPSLoadSensor(UnraidSensorBase):
    """UPS load sensor."""

    _attr_name = "UPS Load"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_UPS
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_load"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get(KEY_UPS, {}).get("load_percent")


class UnraidUPSRuntimeSensor(UnraidSensorBase):
    """UPS runtime sensor."""

    _attr_name = "UPS Runtime"
    _attr_native_unit_of_measurement = None
    _attr_device_class = None
    _attr_state_class = None
    _attr_icon = ICON_UPS

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_runtime"

    @property
    def native_value(self) -> str | None:
        """Return the state in human-readable format."""
        runtime_seconds = self.coordinator.data.get(KEY_UPS, {}).get(
            "runtime_left_seconds"
        )
        if runtime_seconds is None:
            return None

        # Convert to hours and minutes for better readability
        if runtime_seconds >= 3600:
            hours = runtime_seconds / 3600
            return f"{hours:.1f} hours"
        minutes = runtime_seconds / 60
        return f"{minutes:.0f} minutes"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        runtime_seconds = self.coordinator.data.get(KEY_UPS, {}).get(
            "runtime_left_seconds"
        )
        if runtime_seconds is not None:
            return {"runtime_seconds": runtime_seconds}
        return {}


class UnraidUPSPowerSensor(UnraidSensorBase):
    """UPS power consumption sensor for Energy Dashboard."""

    _attr_name = "UPS Power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_POWER
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_power"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        ups_data = self.coordinator.data.get(KEY_UPS, {})
        power_watts = ups_data.get("power_watts")

        # Return power_watts if available
        if power_watts is not None:
            return round(power_watts, 1)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes with user-friendly formatting."""
        ups_data = self.coordinator.data.get(KEY_UPS, {})

        attributes = {
            ATTR_UPS_STATUS: ups_data.get("status"),
            ATTR_UPS_MODEL: ups_data.get("model"),
            "energy_dashboard_ready": True,
        }

        # Add nominal power (rated power)
        nominal_power = ups_data.get("nominal_power_watts")
        if nominal_power is not None:
            attributes["rated_power"] = f"{nominal_power}W"

        # Add load percentage with status description
        load_percent = ups_data.get("load_percent")
        if load_percent is not None:
            attributes["load_percent"] = load_percent
            attributes["current_load"] = f"{load_percent}%"

            # Add load status description
            if load_percent >= 90:
                attributes["load_status"] = "Very High - Check connected devices"
            elif load_percent >= 70:
                attributes["load_status"] = "High"
            elif load_percent >= 50:
                attributes["load_status"] = "Moderate"
            elif load_percent >= 25:
                attributes["load_status"] = "Light"
            else:
                attributes["load_status"] = "Very Light"

        # Add battery information with status description
        battery_charge = ups_data.get("battery_charge_percent")
        if battery_charge is not None:
            attributes["battery_charge"] = f"{battery_charge}%"

            # Add battery status description
            if battery_charge >= 90:
                attributes["battery_status"] = "Excellent"
            elif battery_charge >= 70:
                attributes["battery_status"] = "Good"
            elif battery_charge >= 50:
                attributes["battery_status"] = "Fair"
            elif battery_charge >= 25:
                attributes["battery_status"] = "Low"
            else:
                attributes["battery_status"] = "Critical"

        # Add runtime information with formatting
        runtime_seconds = ups_data.get("runtime_left_seconds")
        if runtime_seconds is not None:
            runtime_minutes = runtime_seconds / 60
            if runtime_minutes >= 60:
                hours = int(runtime_minutes // 60)
                minutes = int(runtime_minutes % 60)
                attributes["estimated_runtime"] = f"{hours}h {minutes}m"
            else:
                attributes["estimated_runtime"] = f"{int(runtime_minutes)}m"
            attributes["runtime_seconds"] = runtime_seconds

        # Add input/output voltage if available
        input_voltage = ups_data.get("input_voltage")
        if input_voltage is not None:
            attributes["input_voltage"] = input_voltage

        output_voltage = ups_data.get("output_voltage")
        if output_voltage is not None:
            attributes["output_voltage"] = output_voltage

        return attributes


class UnraidUPSEnergySensor(UnraidSensorBase):
    """UPS energy consumption sensor for Energy Dashboard (integrates power over time)."""

    _attr_name = "UPS Energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = ICON_POWER
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._total_energy = 0.0  # Total energy in kWh
        self._last_power = None  # Last power reading in W
        self._last_update = None  # Last update timestamp

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_energy"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        ups_data = self.coordinator.data.get(KEY_UPS, {})
        power_watts = ups_data.get("power_watts")

        if power_watts is None:
            return self._total_energy if self._total_energy > 0 else None

        now = datetime.now()

        # If we have previous data, calculate energy consumed since last update
        if self._last_power is not None and self._last_update is not None:
            time_diff_hours = (now - self._last_update).total_seconds() / 3600
            if time_diff_hours > 0:
                # Use trapezoidal rule for integration (average of two power readings)
                avg_power = (self._last_power + power_watts) / 2
                energy_kwh = (avg_power * time_diff_hours) / 1000  # Convert W*h to kWh
                self._total_energy += energy_kwh

        # Update tracking variables
        self._last_power = power_watts
        self._last_update = now

        return round(self._total_energy, 3) if self._total_energy > 0 else 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        ups_data = self.coordinator.data.get(KEY_UPS, {})
        attributes = {
            "integration_method": "trapezoidal",
            "source_sensor": "UPS Power",
        }

        # Add UPS status for context
        ups_status = ups_data.get("status")
        if ups_status:
            attributes["ups_status"] = ups_status

        ups_model = ups_data.get("model")
        if ups_model:
            attributes["ups_model"] = ups_model

        return attributes


# Network Sensors


class UnraidNetworkRXSensor(UnraidSensorBase):
    """Network inbound traffic sensor."""

    _attr_native_unit_of_measurement = UnitOfDataRate.KILOBITS_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        interface_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._attr_name = f"Network {interface_name} Inbound"
        self._attr_icon = ICON_NETWORK
        self._last_bytes = None
        self._last_update = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_network_{self._interface_name}_rx"

    @property
    def native_value(self) -> float | None:
        """Return the state in kilobits per second."""
        from datetime import datetime

        for interface in self.coordinator.data.get(KEY_NETWORK, []):
            if interface.get("name") == self._interface_name:
                bytes_received = interface.get("bytes_received")
                if bytes_received is None:
                    return None

                # Get current time
                now = datetime.now()

                # If we have previous data, calculate rate
                if self._last_bytes is not None and self._last_update is not None:
                    time_diff = (now - self._last_update).total_seconds()
                    if time_diff > 0:
                        bytes_diff = bytes_received - self._last_bytes
                        # Calculate bytes per second, then convert to kilobits per second
                        bytes_per_second = bytes_diff / time_diff
                        bits_per_second = bytes_per_second * 8
                        kilobits_per_second = bits_per_second / 1000

                        # Update tracking variables
                        self._last_bytes = bytes_received
                        self._last_update = now

                        # Return rate (can be negative if counter reset, return 0 in that case)
                        return max(0.0, kilobits_per_second)

                # First run or after reset - store values and return 0
                self._last_bytes = bytes_received
                self._last_update = now
                return 0.0

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for interface in self.coordinator.data.get(KEY_NETWORK, []):
            if interface.get("name") == self._interface_name:
                # Format network speed
                speed_mbps = interface.get("speed_mbps")
                if speed_mbps is not None and speed_mbps > 0:
                    if speed_mbps >= 1000:
                        network_speed = f"{speed_mbps / 1000:.0f} Gbps"
                    else:
                        network_speed = f"{speed_mbps} Mbps"
                else:
                    network_speed = "Unknown"

                # Get IP address or show "N/A" if empty
                ip_address = interface.get("ip_address") or "N/A"

                # Get status (API uses "state" field)
                status = interface.get("state", "unknown")

                return {
                    ATTR_NETWORK_MAC: interface.get("mac_address"),
                    ATTR_NETWORK_IP: ip_address,
                    ATTR_NETWORK_SPEED: network_speed,
                    "status": status,
                    "interface": self._interface_name,
                }
        return {}


class UnraidNetworkTXSensor(UnraidSensorBase):
    """Network outbound traffic sensor."""

    _attr_native_unit_of_measurement = UnitOfDataRate.KILOBITS_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        interface_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._attr_name = f"Network {interface_name} Outbound"
        self._attr_icon = ICON_NETWORK
        self._last_bytes = None
        self._last_update = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_network_{self._interface_name}_tx"

    @property
    def native_value(self) -> float | None:
        """Return the state in kilobits per second."""
        from datetime import datetime

        for interface in self.coordinator.data.get(KEY_NETWORK, []):
            if interface.get("name") == self._interface_name:
                bytes_sent = interface.get("bytes_sent")
                if bytes_sent is None:
                    return None

                # Get current time
                now = datetime.now()

                # If we have previous data, calculate rate
                if self._last_bytes is not None and self._last_update is not None:
                    time_diff = (now - self._last_update).total_seconds()
                    if time_diff > 0:
                        bytes_diff = bytes_sent - self._last_bytes
                        # Calculate bytes per second, then convert to kilobits per second
                        bytes_per_second = bytes_diff / time_diff
                        bits_per_second = bytes_per_second * 8
                        kilobits_per_second = bits_per_second / 1000

                        # Update tracking variables
                        self._last_bytes = bytes_sent
                        self._last_update = now

                        # Return rate (can be negative if counter reset, return 0 in that case)
                        return max(0.0, kilobits_per_second)

                # First run or after reset - store values and return 0
                self._last_bytes = bytes_sent
                self._last_update = now
                return 0.0

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for interface in self.coordinator.data.get(KEY_NETWORK, []):
            if interface.get("name") == self._interface_name:
                # Format network speed
                speed_mbps = interface.get("speed_mbps")
                if speed_mbps is not None and speed_mbps > 0:
                    if speed_mbps >= 1000:
                        network_speed = f"{speed_mbps / 1000:.0f} Gbps"
                    else:
                        network_speed = f"{speed_mbps} Mbps"
                else:
                    network_speed = "Unknown"

                # Get IP address or show "N/A" if empty
                ip_address = interface.get("ip_address") or "N/A"

                # Get status (API uses "state" field)
                status = interface.get("state", "unknown")

                return {
                    ATTR_NETWORK_MAC: interface.get("mac_address"),
                    ATTR_NETWORK_IP: ip_address,
                    ATTR_NETWORK_SPEED: network_speed,
                    "status": status,
                    "interface": self._interface_name,
                }
        return {}


class UnraidDiskUsageSensor(UnraidSensorBase):
    """Disk usage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:harddisk"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._disk_id = disk_id
        self._disk_name = disk_name
        self._attr_name = f"Disk {disk_name} Usage"
        self._last_known_value = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        # Sanitize disk ID for unique ID
        safe_id = self._disk_id.replace(" ", "_").replace("/", "_").lower()
        return f"{self._entry.entry_id}_disk_{safe_id}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            disk_id = disk.get("id", disk.get("name"))
            if disk_id == self._disk_id:
                spin_state = disk.get("spin_state", "active")
                usage_percent = disk.get("usage_percent")

                # Calculate usage_percent if not provided by API
                if usage_percent is None:
                    size_bytes = disk.get("size_bytes", 0)
                    used_bytes = disk.get("used_bytes", 0)
                    if size_bytes > 0 and used_bytes > 0:
                        usage_percent = (used_bytes / size_bytes) * 100

                # Update last known value if we have a valid percentage
                # (API provides usage_percent even for standby disks)
                if usage_percent is not None:
                    self._last_known_value = round(usage_percent, 1)

                # Return the last known value (works for both active and standby)
                return self._last_known_value

        return self._last_known_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            disk_id = disk.get("id", disk.get("name"))
            if disk_id == self._disk_id:
                size_bytes = disk.get("size_bytes", 0)
                used_bytes = disk.get("used_bytes", 0)
                free_bytes = disk.get("free_bytes", 0)
                spin_state = disk.get("spin_state", "active")
                temperature = disk.get("temperature_celsius")

                # Validate disk size calculation (Fix #5)
                # Note: Some API data may have inconsistent size/used/free values
                # This is an API issue, not a sensor issue
                if size_bytes and free_bytes and size_bytes < free_bytes:
                    # If size < free, use free as the actual size (API data issue)
                    actual_size = free_bytes
                else:
                    actual_size = size_bytes

                attrs = {
                    "device": disk.get("device"),
                    "status": disk.get("status"),
                    "filesystem": disk.get("filesystem"),
                    "mount_point": disk.get("mount_point"),
                    "spin_state": spin_state,
                    "size": (
                        f"{actual_size / (1024**3):.2f} GB"
                        if actual_size is not None and actual_size > 0
                        else "Unknown"
                    ),
                    "used": (
                        f"{used_bytes / (1024**3):.2f} GB"
                        if used_bytes is not None and used_bytes > 0
                        else "Unknown"
                    ),
                    "free": (
                        f"{free_bytes / (1024**3):.2f} GB"
                        if free_bytes is not None and free_bytes > 0
                        else "Unknown"
                    ),
                    "smart_status": disk.get("smart_status"),
                    "smart_errors": disk.get("smart_errors", 0),
                }

                # Add temperature if available (will be 0 or None when spun down)
                if temperature is not None and temperature > 0:
                    attrs["temperature_celsius"] = temperature
                elif spin_state in ("standby", "idle"):
                    attrs["temperature_celsius"] = "Disk in standby"

                return attrs
        return {}


class UnraidDiskHealthSensor(UnraidSensorBase):
    """Disk health diagnostic sensor."""

    _attr_native_unit_of_measurement = None
    _attr_state_class = None
    _attr_icon = "mdi:heart-pulse"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._disk_id = disk_id
        self._disk_name = disk_name
        self._attr_name = f"Disk {disk_name} Health"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        # Sanitize disk ID for unique ID
        safe_id = self._disk_id.replace(" ", "_").replace("/", "_").lower()
        return f"{self._entry.entry_id}_disk_{safe_id}_health"

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            disk_id = disk.get("id", disk.get("name"))
            if disk_id == self._disk_id:
                smart_status = disk.get("smart_status", "").upper()
                # Map API values to user-friendly display
                if smart_status == "PASSED":
                    return "Healthy"
                if smart_status == "FAILED":
                    return "Failed"
                if smart_status == "UNKNOWN":
                    # For NVMe drives, UNKNOWN status with no errors means healthy
                    # Check if disk is active and has no SMART errors
                    disk_status = disk.get("status", "")
                    smart_errors = disk.get("smart_errors", 0)
                    if disk_status == "DISK_OK" and smart_errors == 0:
                        return "Healthy"
                    return "Unknown"
                if smart_status:
                    return smart_status.capitalize()
                return "Unknown"
        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            disk_id = disk.get("id", disk.get("name"))
            if disk_id == self._disk_id:
                smart_status = disk.get("smart_status", "").upper()
                smart_errors = disk.get("smart_errors", 0)
                disk_status = disk.get("status", "")

                # Provide user-friendly SMART status in attributes
                # Match the logic used in native_value for consistency
                if smart_status == "PASSED":
                    friendly_status = "PASSED"
                elif smart_status == "FAILED":
                    friendly_status = "FAILED"
                elif smart_status == "UNKNOWN":
                    # For disks with UNKNOWN status, check if they're healthy
                    if disk_status == "DISK_OK" and smart_errors == 0:
                        friendly_status = "PASSED (inferred)"
                    else:
                        friendly_status = "UNKNOWN"
                elif smart_status:
                    friendly_status = smart_status
                else:
                    friendly_status = "UNKNOWN"

                return {
                    "smart_status": friendly_status,
                    "smart_errors": smart_errors,
                    "device": disk.get("device"),
                }
        return {}


class UnraidDockerVDiskUsageSensor(UnraidSensorBase):
    """Docker vDisk usage sensor."""

    _attr_name = "Docker vDisk Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_CONTAINER
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_docker_vdisk_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            if disk.get("role") == "docker_vdisk":
                usage_percent = disk.get("usage_percent")
                if usage_percent is not None:
                    return round(usage_percent, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            if disk.get("role") == "docker_vdisk":
                size_bytes = disk.get("size_bytes", 0)
                used_bytes = disk.get("used_bytes", 0)
                free_bytes = disk.get("free_bytes", 0)

                return {
                    "mount_point": disk.get("mount_point"),
                    "size": (
                        f"{size_bytes / (1024**3):.2f} GB"
                        if size_bytes is not None and size_bytes > 0
                        else "Unknown"
                    ),
                    "used": (
                        f"{used_bytes / (1024**3):.2f} GB"
                        if used_bytes is not None and used_bytes > 0
                        else "Unknown"
                    ),
                    "free": (
                        f"{free_bytes / (1024**3):.2f} GB"
                        if free_bytes is not None and free_bytes > 0
                        else "Unknown"
                    ),
                }
        return {}


class UnraidLogFilesystemUsageSensor(UnraidSensorBase):
    """Log filesystem usage sensor."""

    _attr_name = "Log Filesystem Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:file-document-outline"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_log_filesystem_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            if disk.get("role") == "log":
                usage_percent = disk.get("usage_percent")
                if usage_percent is not None:
                    return round(usage_percent, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for disk in self.coordinator.data.get(KEY_DISKS, []):
            if disk.get("role") == "log":
                size_bytes = disk.get("size_bytes", 0)
                used_bytes = disk.get("used_bytes", 0)
                free_bytes = disk.get("free_bytes", 0)

                # Log filesystem is typically small (MB range), so format accordingly
                # If size is less than 1 GB, show in MB
                if size_bytes and size_bytes < 1024**3:
                    size_str = f"{size_bytes / (1024**2):.2f} MB"
                    used_str = f"{used_bytes / (1024**2):.2f} MB"
                    free_str = f"{free_bytes / (1024**2):.2f} MB"
                else:
                    size_str = f"{size_bytes / (1024**3):.2f} GB"
                    used_str = f"{used_bytes / (1024**3):.2f} GB"
                    free_str = f"{free_bytes / (1024**3):.2f} GB"

                return {
                    "mount_point": disk.get("mount_point"),
                    "size": size_str if size_bytes > 0 else "Unknown",
                    "used": used_str if used_bytes > 0 else "Unknown",
                    "free": free_str if free_bytes > 0 else "Unknown",
                }
        return {}


class UnraidShareUsageSensor(UnraidSensorBase):
    """Sensor for share usage."""

    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_SHARE
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        share_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._share_name = share_name
        self._attr_name = f"Share {share_name} Usage"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        # Sanitize share name for use in unique ID
        safe_name = self._share_name.replace(" ", "_").replace("/", "_").lower()
        return f"{self._entry.entry_id}_share_{safe_name}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        for share in self.coordinator.data.get(KEY_SHARES, []):
            if share.get("name") == self._share_name:
                usage_percent = share.get("usage_percent")
                if usage_percent is not None:
                    return round(usage_percent, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for share in self.coordinator.data.get(KEY_SHARES, []):
            if share.get("name") == self._share_name:
                total_bytes = share.get("total_bytes", 0)
                used_bytes = share.get("used_bytes", 0)
                free_bytes = share.get("free_bytes", 0)

                return {
                    "size": f"{total_bytes / (1024**3):.2f} GB"
                    if total_bytes > 0
                    else "Unknown",
                    "used": f"{used_bytes / (1024**3):.2f} GB"
                    if used_bytes > 0
                    else "Unknown",
                    "free": f"{free_bytes / (1024**3):.2f} GB"
                    if free_bytes > 0
                    else "Unknown",
                }
        return {}


class UnraidNotificationsSensor(UnraidSensorBase):
    """Sensor for active notifications count."""

    _attr_name = "Active Notifications"
    _attr_icon = ICON_NOTIFICATION
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "notifications"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_active_notifications"

    @property
    def native_value(self) -> int:
        """Return the state."""
        notifications = self.coordinator.data.get(KEY_NOTIFICATIONS, [])
        return len(notifications) if isinstance(notifications, list) else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        notifications = self.coordinator.data.get(KEY_NOTIFICATIONS, [])
        if not isinstance(notifications, list):
            return {"notifications": []}

        # Return list of notifications with relevant details
        notification_list = []
        for notification in notifications:
            notification_list.append(
                {
                    "message": notification.get("message", ""),
                    "severity": notification.get("severity", "info"),
                    "timestamp": notification.get("timestamp", ""),
                    "source": notification.get("source", ""),
                }
            )

        return {"notifications": notification_list}


# ZFS Pool Sensors


class UnraidZFSPoolUsageSensor(UnraidSensorBase):
    """Sensor for ZFS pool usage percentage."""

    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_ZFS_POOL
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        pool_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._pool_name = pool_name
        self._attr_name = f"ZFS Pool {pool_name} Usage"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        safe_name = self._pool_name.replace(" ", "_").lower()
        return f"{self._entry.entry_id}_zfs_pool_{safe_name}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        pools = self.coordinator.data.get(KEY_ZFS_POOLS, [])
        for pool in pools:
            if pool.get("name") == self._pool_name:
                return pool.get("capacity_percent")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        pools = self.coordinator.data.get(KEY_ZFS_POOLS, [])
        for pool in pools:
            if pool.get("name") == self._pool_name:
                size_bytes = pool.get("size_bytes", 0)
                allocated_bytes = pool.get("allocated_bytes", 0)
                free_bytes = pool.get("free_bytes", 0)

                return {
                    "pool_name": pool.get("name"),
                    "pool_guid": pool.get("guid"),
                    "health": pool.get("health"),
                    "state": pool.get("state"),
                    "size": f"{size_bytes / (1024**3):.2f} GB",
                    "allocated": f"{allocated_bytes / (1024**3):.2f} GB",
                    "free": f"{free_bytes / (1024**3):.2f} GB",
                    "fragmentation_percent": pool.get("fragmentation_percent"),
                    "dedup_ratio": pool.get("dedup_ratio"),
                    "readonly": pool.get("readonly"),
                    "autoexpand": pool.get("autoexpand"),
                    "autotrim": pool.get("autotrim"),
                }
        return {}


class UnraidZFSPoolHealthSensor(UnraidSensorBase):
    """Sensor for ZFS pool health status."""

    _attr_icon = ICON_ZFS_POOL
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        pool_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._pool_name = pool_name
        self._attr_name = f"ZFS Pool {pool_name} Health"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        safe_name = self._pool_name.replace(" ", "_").lower()
        return f"{self._entry.entry_id}_zfs_pool_{safe_name}_health"

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        pools = self.coordinator.data.get(KEY_ZFS_POOLS, [])
        for pool in pools:
            if pool.get("name") == self._pool_name:
                return pool.get("health")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        pools = self.coordinator.data.get(KEY_ZFS_POOLS, [])
        for pool in pools:
            if pool.get("name") == self._pool_name:
                vdevs = pool.get("vdevs", [])
                vdev_info = []
                for vdev in vdevs:
                    vdev_info.append(
                        {
                            "name": vdev.get("name"),
                            "type": vdev.get("type"),
                            "state": vdev.get("state"),
                            "read_errors": vdev.get("read_errors", 0),
                            "write_errors": vdev.get("write_errors", 0),
                            "checksum_errors": vdev.get("checksum_errors", 0),
                        }
                    )

                # Calculate if pool has problems
                health = pool.get("health", "UNKNOWN")
                state = pool.get("state", "UNKNOWN")
                read_errors = pool.get("read_errors", 0)
                write_errors = pool.get("write_errors", 0)
                checksum_errors = pool.get("checksum_errors", 0)
                has_errors = read_errors > 0 or write_errors > 0 or checksum_errors > 0
                has_problem = health != "ONLINE" or state != "ONLINE" or has_errors

                return {
                    "state": pool.get("state"),
                    "has_problem": has_problem,
                    "read_errors": read_errors,
                    "write_errors": write_errors,
                    "checksum_errors": checksum_errors,
                    "scan_errors": pool.get("scan_errors", 0),
                    "vdevs": vdev_info,
                }
        return {}


# ZFS ARC Sensors


class UnraidZFSARCHitRatioSensor(UnraidSensorBase):
    """Sensor for ZFS ARC cache hit ratio."""

    _attr_name = "ZFS ARC Hit Ratio"
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = ICON_ZFS_ARC
    _attr_suggested_display_precision = 2

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_zfs_arc_hit_ratio"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        arc_data = self.coordinator.data.get(KEY_ZFS_ARC, {})
        return arc_data.get("hit_ratio_percent")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        arc_data = self.coordinator.data.get(KEY_ZFS_ARC, {})
        size_bytes = arc_data.get("size_bytes", 0)
        target_size = arc_data.get("target_size_bytes", 0)
        min_size = arc_data.get("min_size_bytes", 0)
        max_size = arc_data.get("max_size_bytes", 0)

        return {
            "size": f"{size_bytes / (1024**3):.2f} GB",
            "target_size": f"{target_size / (1024**3):.2f} GB",
            "min_size": f"{min_size / (1024**3):.2f} GB",
            "max_size": f"{max_size / (1024**3):.2f} GB",
            "mru_hit_ratio_percent": arc_data.get("mru_hit_ratio_percent"),
            "mfu_hit_ratio_percent": arc_data.get("mfu_hit_ratio_percent"),
            "hits": arc_data.get("hits"),
            "misses": arc_data.get("misses"),
        }
