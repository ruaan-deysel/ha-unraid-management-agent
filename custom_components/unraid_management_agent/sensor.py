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
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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
from .coordinator import UnraidData
from .entity import UnraidBaseEntity, UnraidSensorEntityDescription

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit needed
PARALLEL_UPDATES = 0


# =============================================================================
# Value functions for entity descriptions (La Marzocco pattern)
# =============================================================================


def _get_cpu_usage(data: UnraidData) -> float | None:
    """Get CPU usage from coordinator data."""
    if data and data.system:
        cpu_usage = getattr(data.system, "cpu_usage_percent", None)
        if cpu_usage is not None:
            return round(cpu_usage, 1)
    return None


def _get_cpu_attrs(data: UnraidData) -> dict[str, Any]:
    """Get CPU extra state attributes."""
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


def _get_ram_usage(data: UnraidData) -> float | None:
    """Get RAM usage from coordinator data."""
    if data and data.system:
        ram_usage = getattr(data.system, "ram_usage_percent", None)
        if ram_usage is not None:
            return round(ram_usage, 1)
    return None


def _get_ram_attrs(data: UnraidData) -> dict[str, Any]:
    """Get RAM extra state attributes."""
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


def _get_cpu_temperature(data: UnraidData) -> float | None:
    """Get CPU temperature from coordinator data."""
    if data and data.system:
        cpu_temp = getattr(data.system, "cpu_temp_celsius", None)
        if cpu_temp is not None:
            return round(cpu_temp, 1)
    return None


def _get_uptime(data: UnraidData) -> str | None:
    """Get uptime from coordinator data."""
    if data and data.system:
        uptime_seconds = getattr(data.system, "uptime_seconds", None)
        if uptime_seconds is not None:
            return format_duration(uptime_seconds)
    return None


def _get_uptime_attrs(data: UnraidData) -> dict[str, Any]:
    """Get uptime extra state attributes."""
    if not data or not data.system:
        return {}

    system = data.system
    uptime_seconds = getattr(system, "uptime_seconds", None)

    attrs = {
        "hostname": getattr(system, "hostname", None),
        "version": getattr(system, "version", None),
    }

    if uptime_seconds is not None:
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        attrs["uptime_days"] = days
        attrs["uptime_hours"] = hours
        attrs["uptime_minutes"] = minutes
        attrs["uptime_total_seconds"] = uptime_seconds

    return attrs


def _get_array_usage(data: UnraidData) -> float | None:
    """Get array usage from coordinator data."""
    if data and data.array:
        # First try to use used_percent directly from API
        used_percent = getattr(data.array, "used_percent", None)
        if used_percent is not None:
            return round(used_percent, 1)
        # Fallback: calculate from bytes
        total = getattr(data.array, "total_bytes", 0) or 0
        used = getattr(data.array, "used_bytes", 0) or 0
        if total > 0:
            return round((used / total) * 100, 1)
    return None


def _get_array_attrs(data: UnraidData) -> dict[str, Any]:
    """Get array extra state attributes."""
    if not data or not data.array:
        return {}

    array = data.array
    total = getattr(array, "total_bytes", 0) or 0
    used = getattr(array, "used_bytes", 0) or 0
    free = getattr(array, "free_bytes", 0) or 0

    attrs = {
        ATTR_ARRAY_STATE: getattr(array, "state", "Unknown"),
        ATTR_NUM_DISKS: getattr(array, "num_disks", 0),
        ATTR_NUM_DATA_DISKS: getattr(array, "num_data_disks", 0),
        ATTR_NUM_PARITY_DISKS: getattr(array, "num_parity_disks", 0),
    }

    if total:
        attrs["total_capacity"] = format_bytes(total)
    if used:
        attrs["used_space"] = format_bytes(used)
    if free:
        attrs["free_space"] = format_bytes(free)

    return attrs


def _get_parity_progress(data: UnraidData) -> float | None:
    """Get parity check progress from coordinator data."""
    if data and data.array:
        sync_percent = getattr(data.array, "sync_percent", None)
        if sync_percent is not None:
            return round(sync_percent, 1)
    return 0.0


def _get_parity_attrs(data: UnraidData) -> dict[str, Any]:
    """Get parity check extra state attributes."""
    if not data or not data.array:
        return {}

    array = data.array
    attrs = {}

    sync_action = getattr(array, "sync_action", None)
    if sync_action:
        attrs["sync_action"] = sync_action

    sync_errors = getattr(array, "sync_errors", None)
    if sync_errors is not None:
        attrs["sync_errors"] = sync_errors

    sync_speed = getattr(array, "sync_speed", None)
    if sync_speed:
        attrs["sync_speed"] = sync_speed

    sync_eta = getattr(array, "sync_eta", None)
    if sync_eta:
        attrs["estimated_completion"] = sync_eta

    return attrs


# =============================================================================
# Sensor Entity Descriptions with value_fn pattern
# =============================================================================

SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cpu-64-bit",
        suggested_display_precision=1,
        value_fn=_get_cpu_usage,
        extra_state_attributes_fn=_get_cpu_attrs,
    ),
    UnraidSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
        suggested_display_precision=1,
        value_fn=_get_ram_usage,
        extra_state_attributes_fn=_get_ram_attrs,
    ),
    UnraidSensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        suggested_display_precision=1,
        value_fn=_get_cpu_temperature,
    ),
    UnraidSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        icon="mdi:clock-outline",
        value_fn=_get_uptime,
        extra_state_attributes_fn=_get_uptime_attrs,
    ),
    UnraidSensorEntityDescription(
        key="array_usage",
        translation_key="array_usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:harddisk",
        suggested_display_precision=1,
        value_fn=_get_array_usage,
        extra_state_attributes_fn=_get_array_attrs,
    ),
    UnraidSensorEntityDescription(
        key="parity_progress",
        translation_key="parity_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sync",
        suggested_display_precision=1,
        value_fn=_get_parity_progress,
        extra_state_attributes_fn=_get_parity_attrs,
    ),
)


# =============================================================================
# Sensor Entity class using descriptions
# =============================================================================


class UnraidSensorEntity(UnraidBaseEntity, SensorEntity):
    """Unraid sensor entity using entity description with value_fn pattern."""

    entity_description: UnraidSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        description: UnraidSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if (
            self.entity_description.extra_state_attributes_fn
            and self.coordinator.data is not None
        ):
            return self.entity_description.extra_state_attributes_fn(
                self.coordinator.data
            )
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        if self.coordinator.data is None:
            return False
        return self.entity_description.available_fn(self.coordinator.data)


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


def _is_physical_disk(disk) -> bool:
    """
    Check if disk is a physical, installed disk (not virtual or disabled).

    Filters out:
    - Virtual disks (docker_vdisk, log)
    - Disabled/empty slots (status=DISK_NP_DSBL, no device)
    - Disks without a device assigned
    """
    role = getattr(disk, "role", "")
    status = getattr(disk, "status", "")
    device = getattr(disk, "device", "")

    # Exclude virtual disk types
    if role in ("docker_vdisk", "log"):
        return False

    # Exclude disabled/not present slots
    if status == "DISK_NP_DSBL":
        return False

    # Exclude disks without a device (empty slots)
    return bool(device)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid sensor entities."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    _LOGGER.debug("Setting up Unraid sensors")

    entities: list[SensorEntity] = []

    # Core system sensors using entity descriptions with value_fn pattern
    # System collector is always enabled (required=true)
    entities.extend(
        UnraidSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
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
        for idx, fan in enumerate(fans):
            # Fans can be dict or object depending on API version
            if isinstance(fan, dict):
                fan_name = fan.get("name", "unknown")
            else:
                fan_name = getattr(fan, "name", "unknown")
            entities.append(UnraidFanSensor(coordinator, entry, fan_name, idx))

    # Note: Array sensors (usage, parity) are now created via SENSOR_DESCRIPTIONS

    # Disk sensors - only if disk collector is enabled
    if coordinator.is_collector_enabled("disk"):
        disks = data.disks if data else []
        # Filter to only physical, installed disks
        physical_disks = [d for d in (disks or []) if _is_physical_disk(d)]

        for disk in physical_disks:
            disk_id = getattr(disk, "id", None) or getattr(disk, "name", "unknown")
            disk_name = getattr(disk, "name", disk_id)
            disk_role = getattr(disk, "role", "")

            # Create health sensor for physical disks
            entities.append(
                UnraidDiskHealthSensor(coordinator, entry, disk_id, disk_name)
            )

            # Skip parity disks for usage sensors (parity doesn't have usage data)
            if disk_role not in ("parity", "parity2"):
                entities.append(
                    UnraidDiskUsageSensor(coordinator, entry, disk_id, disk_name)
                )

        # Docker vDisk usage sensor (if available) - virtual disk, always included if exists
        docker_vdisk = next(
            (d for d in (disks or []) if getattr(d, "role", "") == "docker_vdisk"), None
        )
        if docker_vdisk:
            entities.append(UnraidDockerVDiskUsageSensor(coordinator, entry))

        # Log filesystem usage sensor (if available) - virtual disk, always included if exists
        log_filesystem = next(
            (d for d in (disks or []) if getattr(d, "role", "") == "log"), None
        )
        if log_filesystem:
            entities.append(UnraidLogFilesystemUsageSensor(coordinator, entry))

    # GPU sensors - only if gpu collector is enabled
    if coordinator.is_collector_enabled("gpu") and data and data.gpu:
        entities.extend(
            [
                UnraidGPUUtilizationSensor(coordinator, entry),
                UnraidGPUCPUTemperatureSensor(coordinator, entry),
                UnraidGPUPowerSensor(coordinator, entry),
            ]
        )

    # UPS sensors - only if ups collector is enabled
    if (
        coordinator.is_collector_enabled("ups")
        and data
        and data.ups
        and getattr(data.ups, "status", None) is not None
    ):
        entities.extend(
            [
                UnraidUPSBatterySensor(coordinator, entry),
                UnraidUPSLoadSensor(coordinator, entry),
                UnraidUPSRuntimeSensor(coordinator, entry),
                UnraidUPSPowerSensor(coordinator, entry),
            ]
        )

    # Network sensors - only if network collector is enabled
    if coordinator.is_collector_enabled("network"):
        for interface in (data.network if data else []) or []:
            interface_name = getattr(interface, "name", "unknown")
            interface_state = getattr(interface, "state", "down")
            if (
                _is_physical_network_interface(interface_name)
                and interface_state == "up"
            ):
                entities.extend(
                    [
                        UnraidNetworkRXSensor(coordinator, entry, interface_name),
                        UnraidNetworkTXSensor(coordinator, entry, interface_name),
                    ]
                )

    # Share sensors - only if shares collector is enabled
    if coordinator.is_collector_enabled("shares"):
        for share in (data.shares if data else []) or []:
            share_name = getattr(share, "name", "unknown")
            entities.append(UnraidShareUsageSensor(coordinator, entry, share_name))

    # ZFS pool sensors - only if zfs collector is enabled
    if coordinator.is_collector_enabled("zfs"):
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
            if data and data.zfs_arc:
                entities.append(UnraidZFSARCHitRatioSensor(coordinator, entry))

    # Notification sensor - only if notification collector is enabled
    if (
        coordinator.is_collector_enabled("notification")
        and data
        and data.notifications is not None
    ):
        entities.append(UnraidNotificationsSensor(coordinator, entry))

    _LOGGER.debug("Adding %d Unraid sensor entities", len(entities))
    async_add_entities(entities)


class UnraidSensorBase(UnraidBaseEntity, SensorEntity):
    """Base class for Unraid sensors."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        # Use provided key or derive from class name
        sensor_key = key if key else self.__class__.__name__.lower()
        super().__init__(coordinator, sensor_key)
        # Keep _entry reference for backwards compatibility with unique_id properties
        self._entry = entry


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
        index: int = 0,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._fan_name = fan_name
        self._fan_index = index
        self._attr_name = f"Fan {fan_name}" if fan_name != "unknown" else f"Fan {index}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        # Use index to ensure uniqueness for fans with same name
        return f"{self._entry.entry_id}_fan_{self._fan_index}"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        data = self.coordinator.data
        if not data or not data.system:
            return None

        fans = getattr(data.system, "fans", []) or []
        if self._fan_index < len(fans):
            fan = fans[self._fan_index]
            # Fans can be dict or object depending on API version
            if isinstance(fan, dict):
                return fan.get("rpm")
            return getattr(fan, "rpm", None)
        return None


class UnraidUptimeSensor(UnraidSensorBase):
    """
    Uptime sensor.

    Displays uptime as a formatted human-readable string.
    """

    _attr_name = "Uptime"
    _attr_icon = "mdi:clock-outline"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_uptime"

    @property
    def native_value(self) -> str | None:
        """Return the state as formatted uptime."""
        data = self.coordinator.data
        if data and data.system:
            uptime_seconds = getattr(data.system, "uptime_seconds", None)
            if uptime_seconds is not None:
                return format_duration(uptime_seconds)
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
            attrs["uptime_seconds"] = uptime_seconds
            # Calculate days, hours, minutes, seconds breakdown
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60
            attrs["days"] = days
            attrs["hours"] = hours
            attrs["minutes"] = minutes
            attrs["seconds"] = seconds
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

        # API returns used_percent directly
        used_percent = getattr(data.array, "used_percent", None)
        if used_percent is not None:
            return round(used_percent, 1)

        # Fallback: calculate from total_bytes and used_bytes
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
            gpu = data.gpu[0]
            # Try GPU temperature first, fall back to CPU temperature for iGPUs
            temp = getattr(gpu, "temperature_celsius", None)
            if temp is not None and temp > 0:
                return temp
            # For iGPUs, use cpu_temperature_celsius
            return getattr(gpu, "cpu_temperature_celsius", None)
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
            return getattr(data.gpu[0], "power_draw_watts", None)
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
            # Try runtime_left_seconds (in model_extra) first, then battery_runtime_seconds
            runtime_seconds = getattr(data.ups, "runtime_left_seconds", None)
            if runtime_seconds is None:
                runtime_seconds = getattr(data.ups, "battery_runtime_seconds", None)
            if runtime_seconds is not None:
                return round(runtime_seconds / 60, 1)
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


# Network Sensors


class UnraidNetworkRXSensor(UnraidSensorBase):
    """Network receive sensor."""

    _attr_native_unit_of_measurement = "B"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
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
                # API returns bytes_received (not rx_bytes)
                return getattr(interface, "bytes_received", None)
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

    _attr_native_unit_of_measurement = "B"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
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
                # API returns bytes_sent (not tx_bytes)
                return getattr(interface, "bytes_sent", None)
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
                    "temperature": getattr(disk, "temperature_celsius", None),
                    "spin_state": getattr(disk, "spin_state", None),
                    "serial": getattr(disk, "serial_number", None),
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

    def _get_notifications_list(self) -> list:
        """Extract notifications list from data."""
        data = self.coordinator.data
        if not data or not data.notifications:
            return []

        notifications = data.notifications
        # Handle NotificationsResponse (has .notifications attribute)
        if hasattr(notifications, "notifications"):
            return notifications.notifications or []
        # Handle direct list
        if isinstance(notifications, list):
            return notifications
        return []

    @property
    def native_value(self) -> int:
        """Return the state."""
        return len(self._get_notifications_list())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        notifications = self._get_notifications_list()
        if not notifications:
            return {"unread_count": 0}

        # Count unread: type='unread' means not read yet
        unread = sum(1 for n in notifications if getattr(n, "type", "") == "unread")
        return {"unread_count": unread}
