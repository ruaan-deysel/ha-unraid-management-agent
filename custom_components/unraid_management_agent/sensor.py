"""Sensor platform for Unraid Management Agent."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from uma_api.formatting import format_bytes, format_duration

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .const import (
    ATTR_ARRAY_STATE,
    ATTR_CPU_CORES,
    ATTR_CPU_MODEL,
    ATTR_CPU_THREADS,
    ATTR_GPU_DRIVER_VERSION,
    ATTR_GPU_NAME,
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
)
from .entity import UnraidEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


def _is_physical_network_interface(interface_name: str) -> bool:
    """Check if the network interface is a physical interface."""
    physical_patterns = [
        r"^eth\d+$",
        r"^wlan\d+$",
        r"^bond\d+$",
        r"^eno\d+$",
        r"^enp\d+s\d+$",
    ]
    for pattern in physical_patterns:
        if re.match(pattern, interface_name):
            return True
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Unraid sensor entities."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    _LOGGER.debug("Setting up Unraid sensors")

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
    if (
        data
        and data.system
        and getattr(data.system, "motherboard_temp_celsius", None) is not None
    ):
        entities.append(UnraidMotherboardTemperatureSensor(coordinator, entry))

    # Fan sensors (dynamic, one per fan)
    if data and data.system:
        fans = getattr(data.system, "fans", []) or []
        for fan in fans:
            fan_name = getattr(fan, "name", "unknown")
            entities.append(UnraidFanSensor(coordinator, entry, fan_name))

    # Array sensors
    entities.extend(
        [
            UnraidArrayUsageSensor(coordinator, entry),
            UnraidParityProgressSensor(coordinator, entry),
        ]
    )

    # Disk sensors (dynamic, one per disk)
    disks = data.disks if data else []
    for disk in disks or []:
        disk_id = getattr(disk, "id", None) or getattr(disk, "name", "unknown")
        disk_name = getattr(disk, "name", disk_id)
        disk_role = getattr(disk, "role", "")
        disk_device = getattr(disk, "device", None)

        # Create health sensor for physical disks only
        if disk_role not in ("docker_vdisk", "log"):
            if disk_name in ("parity", "parity2") and not disk_device:
                _LOGGER.debug(
                    "Skipping %s health sensor - no device assigned", disk_name
                )
                continue
            entities.append(
                UnraidDiskHealthSensor(coordinator, entry, disk_id, disk_name)
            )

        # Skip parity disks for usage sensors
        if disk_name not in ("parity", "parity2"):
            entities.append(
                UnraidDiskUsageSensor(coordinator, entry, disk_id, disk_name)
            )

    # Docker vDisk usage sensor (if available)
    docker_vdisk = next(
        (d for d in (disks or []) if getattr(d, "role", "") == "docker_vdisk"), None
    )
    if docker_vdisk:
        entities.append(UnraidDockerVDiskUsageSensor(coordinator, entry))

    # Log filesystem usage sensor (if available)
    log_filesystem = next(
        (d for d in (disks or []) if getattr(d, "role", "") == "log"), None
    )
    if log_filesystem:
        entities.append(UnraidLogFilesystemUsageSensor(coordinator, entry))

    # GPU sensors (if GPU available)
    if data and data.gpu:
        entities.extend(
            [
                UnraidGPUUtilizationSensor(coordinator, entry),
                UnraidGPUCPUTemperatureSensor(coordinator, entry),
                UnraidGPUPowerSensor(coordinator, entry),
                UnraidGPUEnergySensor(coordinator, entry),
            ]
        )

    # UPS sensors (if UPS connected)
    if data and data.ups and getattr(data.ups, "connected", False):
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
    for interface in (data.network if data else []) or []:
        interface_name = getattr(interface, "name", "unknown")
        interface_state = getattr(interface, "state", "down")
        if _is_physical_network_interface(interface_name) and interface_state == "up":
            entities.extend(
                [
                    UnraidNetworkRXSensor(coordinator, entry, interface_name),
                    UnraidNetworkTXSensor(coordinator, entry, interface_name),
                ]
            )

    # Share sensors (dynamic, one per share)
    for share in (data.shares if data else []) or []:
        share_name = getattr(share, "name", "unknown")
        entities.append(UnraidShareUsageSensor(coordinator, entry, share_name))

    # ZFS pool sensors (if ZFS pools available)
    zfs_pools = data.zfs_pools if data else []
    if zfs_pools:
        for pool in zfs_pools:
            pool_name = getattr(pool, "name", "unknown")
            entities.extend(
                [
                    UnraidZFSPoolUsageSensor(coordinator, entry, pool_name),
                    UnraidZFSPoolHealthSensor(coordinator, entry, pool_name),
                ]
            )

    # ZFS ARC sensors (only if ZFS pools exist)
    if zfs_pools and data and data.zfs_arc:
        entities.append(UnraidZFSARCHitRatioSensor(coordinator, entry))

    # Notification sensor (if notifications available)
    if data and data.notifications is not None:
        entities.append(UnraidNotificationsSensor(coordinator, entry))

    _LOGGER.debug("Adding %d Unraid sensor entities", len(entities))
    async_add_entities(entities)


class UnraidSensorBase(UnraidEntity, SensorEntity):
    """Base class for Unraid sensors."""


# System Sensors


class UnraidCPUUsageSensor(UnraidSensorBase):
    """CPU usage sensor."""

    _attr_name = "CPU Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cpu-64-bit"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_cpu_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.system:
            cpu_usage = getattr(data.system, "cpu_usage_percent", None)
            if cpu_usage is not None:
                return round(cpu_usage, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.system:
            return {}

        system = data.system
        cpu_cores = getattr(system, "cpu_cores", 0) or 0
        cpu_threads = getattr(system, "cpu_threads", 0) or 0

        # Fix incorrect core count
        if cpu_cores == 1 and cpu_threads > 2:
            cpu_cores = cpu_threads // 2

        attrs = {
            ATTR_CPU_MODEL: getattr(system, "cpu_model", None),
            ATTR_CPU_CORES: cpu_cores,
            ATTR_CPU_THREADS: cpu_threads,
        }

        cpu_mhz = getattr(system, "cpu_mhz", None)
        if cpu_mhz:
            attrs["cpu_frequency"] = f"{cpu_mhz:.0f} MHz"

        return attrs


class UnraidRAMUsageSensor(UnraidSensorBase):
    """RAM usage sensor."""

    _attr_name = "RAM Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:memory"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ram_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.system:
            ram_usage = getattr(data.system, "ram_usage_percent", None)
            if ram_usage is not None:
                return round(ram_usage, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.system:
            return {}

        system = data.system
        ram_total = getattr(system, "ram_total_bytes", 0) or 0
        ram_used = getattr(system, "ram_used_bytes", 0) or 0
        ram_free = getattr(system, "ram_free_bytes", 0) or 0
        ram_cached = getattr(system, "ram_cached_bytes", 0) or 0
        ram_buffers = getattr(system, "ram_buffers_bytes", 0) or 0

        attrs = {
            ATTR_RAM_TOTAL: format_bytes(ram_total) if ram_total else "Unknown",
            ATTR_SERVER_MODEL: getattr(system, "server_model", None),
        }

        if ram_used:
            attrs["ram_used"] = format_bytes(ram_used)
        if ram_free:
            attrs["ram_free"] = format_bytes(ram_free)
        if ram_cached:
            attrs["ram_cached"] = format_bytes(ram_cached)
        if ram_buffers:
            attrs["ram_buffers"] = format_bytes(ram_buffers)

        if ram_free and ram_cached and ram_buffers:
            ram_available = ram_free + ram_cached + ram_buffers
            attrs["ram_available"] = format_bytes(ram_available)

        return attrs


class UnraidCPUTemperatureSensor(UnraidSensorBase):
    """CPU temperature sensor."""

    _attr_name = "CPU Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_cpu_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.system:
            return getattr(data.system, "cpu_temp_celsius", None)
        return None


class UnraidMotherboardTemperatureSensor(UnraidSensorBase):
    """Motherboard temperature sensor."""

    _attr_name = "Motherboard Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_motherboard_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.system:
            return getattr(data.system, "motherboard_temp_celsius", None)
        return None


class UnraidFanSensor(UnraidSensorBase):
    """Fan sensor."""

    _attr_native_unit_of_measurement = "RPM"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fan"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        fan_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._fan_name = fan_name
        self._attr_name = f"Fan {fan_name}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_fan_{self._fan_name}"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.system:
            return None

        fans = getattr(data.system, "fans", []) or []
        for fan in fans:
            if getattr(fan, "name", "") == self._fan_name:
                return getattr(fan, "rpm", None)
        return None


class UnraidUptimeSensor(UnraidSensorBase):
    """Uptime sensor."""

    _attr_name = "Uptime"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:clock-outline"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_uptime"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.system:
            return getattr(data.system, "uptime_seconds", None)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.system:
            return {}

        uptime_seconds = getattr(data.system, "uptime_seconds", None)
        attrs = {}
        if uptime_seconds:
            attrs["uptime_formatted"] = format_duration(uptime_seconds)
        return attrs


# Array Sensors


class UnraidArrayUsageSensor(UnraidSensorBase):
    """Array usage sensor."""

    _attr_name = "Array Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:harddisk"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_array_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.array:
            return None

        total = getattr(data.array, "total_bytes", 0) or 0
        used = getattr(data.array, "used_bytes", 0) or 0
        if total > 0:
            return round((used / total) * 100, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.array:
            return {}

        array = data.array
        return {
            ATTR_ARRAY_STATE: getattr(array, "state", None),
            ATTR_NUM_DISKS: getattr(array, "num_disks", 0),
            ATTR_NUM_DATA_DISKS: getattr(array, "num_data_disks", 0),
            ATTR_NUM_PARITY_DISKS: getattr(array, "num_parity_disks", 0),
            "total_size": format_bytes(getattr(array, "total_bytes", 0) or 0),
            "used_size": format_bytes(getattr(array, "used_bytes", 0) or 0),
            "free_size": format_bytes(getattr(array, "free_bytes", 0) or 0),
        }


class UnraidParityProgressSensor(UnraidSensorBase):
    """Parity check progress sensor."""

    _attr_name = "Parity Check Progress"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:shield-check"
    _attr_suggested_display_precision = 1
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_progress"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.array:
            parity_status = getattr(data.array, "parity_check_status", None)
            if parity_status:
                return getattr(parity_status, "progress_percent", 0)
        return 0


# GPU Sensors


class UnraidGPUUtilizationSensor(UnraidSensorBase):
    """GPU utilization sensor."""

    _attr_name = "GPU Utilization"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:expansion-card"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_utilization"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.gpu and len(data.gpu) > 0:
            return getattr(data.gpu[0], "utilization_gpu_percent", None)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.gpu or len(data.gpu) == 0:
            return {}

        gpu = data.gpu[0]
        return {
            ATTR_GPU_NAME: getattr(gpu, "name", None),
            ATTR_GPU_DRIVER_VERSION: getattr(gpu, "driver_version", None),
        }


class UnraidGPUCPUTemperatureSensor(UnraidSensorBase):
    """GPU temperature sensor."""

    _attr_name = "GPU Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.gpu and len(data.gpu) > 0:
            return getattr(data.gpu[0], "temperature_celsius", None)
        return None


class UnraidGPUPowerSensor(UnraidSensorBase):
    """GPU power sensor."""

    _attr_name = "GPU Power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:power"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_power"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.gpu and len(data.gpu) > 0:
            return getattr(data.gpu[0], "power_watts", None)
        return None


class UnraidGPUEnergySensor(UnraidSensorBase):
    """GPU energy sensor."""

    _attr_name = "GPU Energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:expansion-card"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_gpu_energy"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.gpu and len(data.gpu) > 0:
            return getattr(data.gpu[0], "energy_kwh", None)
        return None


# UPS Sensors


class UnraidUPSBatterySensor(UnraidSensorBase):
    """UPS battery sensor."""

    _attr_name = "UPS Battery"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_battery"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.ups:
            return getattr(data.ups, "battery_charge_percent", None)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.ups:
            return {}

        ups = data.ups
        return {
            ATTR_UPS_STATUS: getattr(ups, "status", None),
            ATTR_UPS_MODEL: getattr(ups, "model", None),
        }


class UnraidUPSLoadSensor(UnraidSensorBase):
    """UPS load sensor."""

    _attr_name = "UPS Load"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_load"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.ups:
            return getattr(data.ups, "load_percent", None)
        return None


class UnraidUPSRuntimeSensor(UnraidSensorBase):
    """UPS runtime sensor."""

    _attr_name = "UPS Runtime"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_runtime"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.ups:
            return getattr(data.ups, "runtime_minutes", None)
        return None


class UnraidUPSPowerSensor(UnraidSensorBase):
    """UPS power sensor."""

    _attr_name = "UPS Power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:power"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_power"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.ups:
            return getattr(data.ups, "power_watts", None)
        return None


class UnraidUPSEnergySensor(UnraidSensorBase):
    """UPS energy sensor."""

    _attr_name = "UPS Energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_energy"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.ups:
            return getattr(data.ups, "energy_kwh", None)
        return None


# Network Sensors


class UnraidNetworkRXSensor(UnraidSensorBase):
    """Network receive sensor."""

    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:ethernet"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        interface_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._attr_name = f"{interface_name} RX"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_network_{self._interface_name}_rx"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.network:
            return None

        for interface in data.network:
            if getattr(interface, "name", "") == self._interface_name:
                return getattr(interface, "rx_bytes_per_sec", None)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.network:
            return {}

        for interface in data.network:
            if getattr(interface, "name", "") == self._interface_name:
                return {
                    ATTR_NETWORK_MAC: getattr(interface, "mac_address", None),
                    ATTR_NETWORK_IP: getattr(interface, "ip_address", None),
                    ATTR_NETWORK_SPEED: getattr(interface, "speed_mbps", None),
                }
        return {}


class UnraidNetworkTXSensor(UnraidSensorBase):
    """Network transmit sensor."""

    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:ethernet"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        interface_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._attr_name = f"{interface_name} TX"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_network_{self._interface_name}_tx"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.network:
            return None

        for interface in data.network:
            if getattr(interface, "name", "") == self._interface_name:
                return getattr(interface, "tx_bytes_per_sec", None)
        return None


# Disk Sensors


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

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_disk_{self._disk_id}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.disks:
            return None

        for disk in data.disks:
            if (
                getattr(disk, "id", None) == self._disk_id
                or getattr(disk, "name", None) == self._disk_id
            ):
                total = getattr(disk, "size_bytes", 0) or 0
                used = getattr(disk, "used_bytes", 0) or 0
                if total > 0:
                    return round((used / total) * 100, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.disks:
            return {}

        for disk in data.disks:
            if (
                getattr(disk, "id", None) == self._disk_id
                or getattr(disk, "name", None) == self._disk_id
            ):
                return {
                    "total_size": format_bytes(getattr(disk, "size_bytes", 0) or 0),
                    "used_size": format_bytes(getattr(disk, "used_bytes", 0) or 0),
                    "free_size": format_bytes(getattr(disk, "free_bytes", 0) or 0),
                    "device": getattr(disk, "device", None),
                    "filesystem": getattr(disk, "filesystem", None),
                }
        return {}


class UnraidDiskHealthSensor(UnraidSensorBase):
    """Disk health sensor."""

    _attr_icon = "mdi:harddisk"
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
        return f"{self._entry.entry_id}_disk_{self._disk_id}_health"

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.disks:
            return None

        for disk in data.disks:
            if (
                getattr(disk, "id", None) == self._disk_id
                or getattr(disk, "name", None) == self._disk_id
            ):
                return getattr(disk, "status", "Unknown")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.disks:
            return {}

        for disk in data.disks:
            if (
                getattr(disk, "id", None) == self._disk_id
                or getattr(disk, "name", None) == self._disk_id
            ):
                return {
                    "temperature": getattr(disk, "temp_celsius", None),
                    "spin_state": getattr(disk, "spin_state", None),
                    "serial": getattr(disk, "serial", None),
                    "device": getattr(disk, "device", None),
                }
        return {}


class UnraidDockerVDiskUsageSensor(UnraidSensorBase):
    """Docker vDisk usage sensor."""

    _attr_name = "Docker vDisk Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:docker"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_docker_vdisk_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.disks:
            return None

        for disk in data.disks:
            if getattr(disk, "role", "") == "docker_vdisk":
                total = getattr(disk, "size_bytes", 0) or 0
                used = getattr(disk, "used_bytes", 0) or 0
                if total > 0:
                    return round((used / total) * 100, 1)
        return None


class UnraidLogFilesystemUsageSensor(UnraidSensorBase):
    """Log filesystem usage sensor."""

    _attr_name = "Log Filesystem Usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:harddisk"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_log_filesystem_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.disks:
            return None

        for disk in data.disks:
            if getattr(disk, "role", "") == "log":
                total = getattr(disk, "size_bytes", 0) or 0
                used = getattr(disk, "used_bytes", 0) or 0
                if total > 0:
                    return round((used / total) * 100, 1)
        return None


# Share Sensors


class UnraidShareUsageSensor(UnraidSensorBase):
    """Share usage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:folder-network"
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
        return f"{self._entry.entry_id}_share_{self._share_name}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.shares:
            return None

        for share in data.shares:
            if getattr(share, "name", "") == self._share_name:
                total = getattr(share, "total_bytes", 0) or 0
                used = getattr(share, "used_bytes", 0) or 0
                if total > 0:
                    return round((used / total) * 100, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.shares:
            return {}

        for share in data.shares:
            if getattr(share, "name", "") == self._share_name:
                return {
                    "total_size": format_bytes(getattr(share, "total_bytes", 0) or 0),
                    "used_size": format_bytes(getattr(share, "used_bytes", 0) or 0),
                    "free_size": format_bytes(getattr(share, "free_bytes", 0) or 0),
                    "path": getattr(share, "path", None),
                }
        return {}


# ZFS Sensors


class UnraidZFSPoolUsageSensor(UnraidSensorBase):
    """ZFS pool usage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:database-outline"
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
        return f"{self._entry.entry_id}_zfs_pool_{self._pool_name}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.zfs_pools:
            return None

        for pool in data.zfs_pools:
            if getattr(pool, "name", "") == self._pool_name:
                total = getattr(pool, "size_bytes", 0) or 0
                used = getattr(pool, "used_bytes", 0) or 0
                if total > 0:
                    return round((used / total) * 100, 1)
        return None


class UnraidZFSPoolHealthSensor(UnraidSensorBase):
    """ZFS pool health sensor."""

    _attr_icon = "mdi:database-outline"
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
        return f"{self._entry.entry_id}_zfs_pool_{self._pool_name}_health"

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.zfs_pools:
            return None

        for pool in data.zfs_pools:
            if getattr(pool, "name", "") == self._pool_name:
                return getattr(pool, "health", "Unknown")
        return None


class UnraidZFSARCHitRatioSensor(UnraidSensorBase):
    """ZFS ARC hit ratio sensor."""

    _attr_name = "ZFS ARC Hit Ratio"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:memory-arrow-down"
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_zfs_arc_hit_ratio"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        data = self.coordinator.data
        if data and data.zfs_arc:
            return getattr(data.zfs_arc, "hit_ratio_percent", None)
        return None


# Notification Sensor


class UnraidNotificationsSensor(UnraidSensorBase):
    """Notifications sensor."""

    _attr_name = "Notifications"
    _attr_icon = "mdi:bell-alert"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_notifications"

    @property
    def native_value(self) -> int:
        """Return the state."""
        data = self.coordinator.data
        if data and data.notifications:
            return len(data.notifications)
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.notifications:
            return {"unread_count": 0}

        unread = sum(1 for n in data.notifications if not getattr(n, "read", True))
        return {"unread_count": unread}
