"""
Sensor platform for Unraid Management Agent.

This module follows the entity description pattern used by Home Assistant core
integrations. All sensors are defined using dataclass descriptions with value_fn
callbacks, enabling a declarative approach to sensor definition.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .api import EnergyIntegrator, RateCalculator, parse_timestamp
from .api.formatting import format_bytes, format_duration
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
from .entity import UnraidBaseEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit needed
PARALLEL_UPDATES = 0
NETWORK_RATE_STALE_SECONDS = 300.0


def _add_attr_if_set(attrs: dict[str, Any], key: str, value: Any) -> None:
    """Add an attribute to the dict only if the value is not None/empty."""
    if value is not None and value != "":
        attrs[key] = value


# =============================================================================
# Entity Description Dataclass
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class UnraidSensorEntityDescription(SensorEntityDescription):
    """Description for Unraid sensor entities with value_fn pattern."""

    value_fn: Callable[[UnraidData], Any] = lambda _: None
    extra_state_attributes_fn: Callable[[UnraidData], dict[str, Any]] | None = None
    available_fn: Callable[[UnraidData], bool] = lambda data: data is not None
    supported_fn: Callable[[UnraidData], bool] = lambda _: True


@dataclass
class UnraidRateSensorExtraStoredData(SensorExtraStoredData):
    """Extra restore-state data for network rate sensors."""

    last_bytes: int | None
    last_timestamp: float | None
    last_uptime_seconds: int | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the network rate restore data."""
        data = super().as_dict()
        data["last_bytes"] = self.last_bytes
        data["last_timestamp"] = self.last_timestamp
        data["last_uptime_seconds"] = self.last_uptime_seconds
        return data

    @classmethod
    def from_dict(
        cls, restored: dict[str, Any]
    ) -> UnraidRateSensorExtraStoredData | None:
        """Create restore data from a persisted dict."""
        extra = SensorExtraStoredData.from_dict(restored)
        if extra is None:
            return None

        try:
            last_bytes = (
                int(restored["last_bytes"])
                if restored.get("last_bytes") is not None
                else None
            )
            last_timestamp = (
                float(restored["last_timestamp"])
                if restored.get("last_timestamp") is not None
                else None
            )
            last_uptime_seconds = (
                int(restored["last_uptime_seconds"])
                if restored.get("last_uptime_seconds") is not None
                else None
            )
        except TypeError, ValueError:
            return None

        return cls(
            extra.native_value,
            extra.native_unit_of_measurement,
            last_bytes,
            last_timestamp,
            last_uptime_seconds,
        )


@dataclass
class UnraidEnergySensorExtraStoredData(SensorExtraStoredData):
    """Extra restore-state data for derived energy sensors."""

    last_power_watts: float | None
    last_timestamp: float | None
    last_uptime_seconds: int | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the energy restore data."""
        data = super().as_dict()
        data["last_power_watts"] = self.last_power_watts
        data["last_timestamp"] = self.last_timestamp
        data["last_uptime_seconds"] = self.last_uptime_seconds
        return data

    @classmethod
    def from_dict(
        cls, restored: dict[str, Any]
    ) -> UnraidEnergySensorExtraStoredData | None:
        """Create restore data from a persisted dict."""
        extra = SensorExtraStoredData.from_dict(restored)
        if extra is None:
            return None

        try:
            last_power_watts = (
                float(restored["last_power_watts"])
                if restored.get("last_power_watts") is not None
                else None
            )
            last_timestamp = (
                float(restored["last_timestamp"])
                if restored.get("last_timestamp") is not None
                else None
            )
            last_uptime_seconds = (
                int(restored["last_uptime_seconds"])
                if restored.get("last_uptime_seconds") is not None
                else None
            )
        except TypeError, ValueError:
            return None

        return cls(
            extra.native_value,
            extra.native_unit_of_measurement,
            last_power_watts,
            last_timestamp,
            last_uptime_seconds,
        )


def _get_system_uptime_seconds(data: UnraidData | None) -> int | None:
    """Get the current system uptime in seconds from coordinator data."""
    if not data or not data.system:
        return None

    uptime_seconds = data.system.uptime_seconds
    if uptime_seconds is None:
        return None

    try:
        return int(uptime_seconds)
    except TypeError, ValueError:
        return None


def _did_system_reboot(
    current_uptime_seconds: int | None,
    previous_uptime_seconds: int | None,
) -> bool:
    """Return true if the current uptime indicates the Unraid host rebooted."""
    return (
        current_uptime_seconds is not None
        and previous_uptime_seconds is not None
        and current_uptime_seconds < previous_uptime_seconds
    )


# =============================================================================
# Value Functions for System Sensors
# =============================================================================


def _get_cpu_usage(data: UnraidData) -> float | None:
    """Get CPU usage from coordinator data."""
    if data and data.system:
        cpu_usage = data.system.cpu_usage_percent
        if cpu_usage is not None:
            return round(float(cpu_usage), 1)
    return None


def _get_cpu_attrs(data: UnraidData) -> dict[str, Any]:
    """Get CPU extra state attributes."""
    if not data or not data.system:
        return {}

    system = data.system
    cpu_cores = system.cpu_cores or 0
    cpu_threads = system.cpu_threads or 0

    attrs: dict[str, Any] = {
        ATTR_CPU_CORES: cpu_cores,
        ATTR_CPU_THREADS: cpu_threads,
    }
    _add_attr_if_set(attrs, ATTR_CPU_MODEL, system.cpu_model)

    cpu_mhz = system.cpu_mhz
    if cpu_mhz:
        attrs["cpu_frequency"] = f"{cpu_mhz:.0f} MHz"

    return attrs


def _get_ram_usage(data: UnraidData) -> float | None:
    """Get RAM usage from coordinator data."""
    if data and data.system:
        ram_usage = data.system.ram_usage_percent
        if ram_usage is not None:
            return round(float(ram_usage), 1)
    return None


def _get_ram_attrs(data: UnraidData) -> dict[str, Any]:
    """Get RAM extra state attributes."""
    if not data or not data.system:
        return {}

    system = data.system
    ram_total = system.ram_total_bytes or 0
    ram_used = system.ram_used_bytes or 0
    ram_free = system.ram_free_bytes or 0
    ram_cached = system.ram_cached_bytes or 0
    ram_buffers = system.ram_buffers_bytes or 0

    attrs: dict[str, Any] = {}
    if ram_total:
        attrs[ATTR_RAM_TOTAL] = format_bytes(ram_total)
    _add_attr_if_set(attrs, ATTR_SERVER_MODEL, system.server_model)

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


def _get_cpu_power(data: UnraidData) -> float | None:
    """Get CPU power consumption from coordinator data."""
    if data and data.system:
        power = data.system.cpu_power_watts
        if power is not None:
            return round(float(power), 1)
    return None


def _get_dram_power(data: UnraidData) -> float | None:
    """Get DRAM power consumption from coordinator data."""
    if data and data.system:
        power = data.system.dram_power_watts
        if power is not None:
            return round(float(power), 1)
    return None


def _get_cpu_temperature(data: UnraidData) -> float | None:
    """Get CPU temperature from coordinator data."""
    if data and data.system:
        cpu_temp = data.system.cpu_temp_celsius
        if cpu_temp is not None:
            return round(float(cpu_temp), 1)
    return None


def _get_motherboard_temperature(data: UnraidData) -> float | None:
    """Get motherboard temperature from coordinator data."""
    if data and data.system:
        mb_temp = data.system.motherboard_temp_celsius
        if mb_temp is not None:
            return round(float(mb_temp), 1)
    return None


def _get_uptime(data: UnraidData) -> datetime | None:
    """Get uptime as boot timestamp from coordinator data."""
    if data and data.system:
        uptime_seconds = data.system.uptime_seconds
        if uptime_seconds is not None:
            return dt_util.now() - timedelta(seconds=uptime_seconds)
    return None


def _get_uptime_attrs(data: UnraidData) -> dict[str, Any]:
    """Get uptime extra state attributes."""
    if not data or not data.system:
        return {}

    system = data.system
    uptime_seconds = system.uptime_seconds

    attrs: dict[str, Any] = {}
    _add_attr_if_set(attrs, "hostname", system.hostname)
    _add_attr_if_set(attrs, "version", system.version)

    if uptime_seconds is not None:
        attrs["uptime_days"] = system.uptime_days
        attrs["uptime_hours"] = system.uptime_hours
        attrs["uptime_minutes"] = system.uptime_minutes
        attrs["uptime_total_seconds"] = uptime_seconds

    return attrs


def _get_chipset_temperature(data: UnraidData) -> float | None:
    """Get chipset temperature from coordinator data."""
    if data and data.system:
        chipset_temp = data.system.chipset_temp_celsius
        if chipset_temp is not None:
            return round(float(chipset_temp), 1)
    return None


def _get_cpu_governor(data: UnraidData) -> str | None:
    """Get CPU frequency governor from coordinator data."""
    if data and data.system and data.system.cpu_power_state:
        return data.system.cpu_power_state.governor
    return None


def _get_cpu_governor_attrs(data: UnraidData) -> dict[str, Any]:
    """Get CPU governor extra state attributes."""
    if not data or not data.system or not data.system.cpu_power_state:
        return {}

    state = data.system.cpu_power_state
    attrs: dict[str, Any] = {}
    if state.available_governors:
        attrs["available_governors"] = ", ".join(state.available_governors)
    _add_attr_if_set(attrs, "scaling_driver", state.driver)
    return attrs


def _get_cpu_current_frequency(data: UnraidData) -> float | None:
    """Get current CPU frequency in MHz from coordinator data."""
    if data and data.system and data.system.cpu_power_state:
        freq = data.system.cpu_power_state.current_freq_mhz
        if freq is not None:
            return round(float(freq), 0)
    return None


def _get_cpu_frequency_attrs(data: UnraidData) -> dict[str, Any]:
    """Get CPU frequency extra state attributes."""
    if not data or not data.system or not data.system.cpu_power_state:
        return {}

    state = data.system.cpu_power_state
    attrs: dict[str, Any] = {}
    if state.min_freq_mhz is not None:
        attrs["min_frequency_mhz"] = round(float(state.min_freq_mhz), 0)
    if state.max_freq_mhz is not None:
        attrs["max_frequency_mhz"] = round(float(state.max_freq_mhz), 0)
    _add_attr_if_set(attrs, "governor", state.governor)
    _add_attr_if_set(attrs, "scaling_driver", state.driver)
    return attrs


# =============================================================================
# Value Functions for Docker Aggregate Sensors
# =============================================================================


def _get_docker_cpu_usage(data: UnraidData) -> float | None:
    """Get total Docker CPU usage from coordinator data."""
    if not data or not data.containers:
        return None
    total = 0.0
    for container in data.containers:
        cpu = getattr(container, "cpu_percent", None)
        if cpu is not None:
            total += float(cpu)
    return round(total, 1)


def _get_docker_cpu_attrs(data: UnraidData) -> dict[str, Any]:
    """Get Docker CPU extra state attributes."""
    if not data or not data.containers:
        return {}
    running = sum(1 for c in data.containers if getattr(c, "status", "") == "running")
    return {
        "total_containers": len(data.containers),
        "running_containers": running,
    }


def _get_docker_memory_usage(data: UnraidData) -> float | None:
    """Get total Docker memory usage in MB from coordinator data."""
    if not data or not data.containers:
        return None
    total = 0.0
    for container in data.containers:
        mem = getattr(container, "memory_usage_bytes", None)
        if mem is not None and mem > 0:
            total += float(mem)
    if total > 0:
        return round(total / (1024 * 1024), 1)
    return None


def _get_docker_memory_attrs(data: UnraidData) -> dict[str, Any]:
    """Get Docker memory extra state attributes."""
    if not data or not data.containers:
        return {}

    running = sum(1 for c in data.containers if getattr(c, "status", "") == "running")
    attrs: dict[str, Any] = {
        "total_containers": len(data.containers),
        "running_containers": running,
    }

    # Find the system's total memory for percentage calculation
    if data.system and data.system.ram_total_bytes:
        total_mem = 0.0
        for container in data.containers:
            mem = getattr(container, "memory_usage_bytes", None)
            if mem is not None and mem > 0:
                total_mem += float(mem)
        if total_mem > 0:
            percent = (total_mem / float(data.system.ram_total_bytes)) * 100
            attrs["memory_percent_of_system"] = round(percent, 1)

    return attrs


# =============================================================================
# Value Functions for Array Sensors
# =============================================================================


def _get_array_usage(data: UnraidData) -> float | None:
    """Get array usage from coordinator data."""
    if data and data.array:
        computed = data.array.computed_used_percent
        if computed is not None:
            return round(float(computed), 1)
    return None


def _get_array_attrs(data: UnraidData) -> dict[str, Any]:
    """Get array extra state attributes."""
    if not data or not data.array:
        return {}

    array = data.array
    total = array.total_bytes or 0
    used = array.used_bytes or 0
    free = array.free_bytes or 0

    attrs = {
        ATTR_ARRAY_STATE: array.state,
        ATTR_NUM_DISKS: array.num_disks,
        ATTR_NUM_DATA_DISKS: array.num_data_disks,
        ATTR_NUM_PARITY_DISKS: array.num_parity_disks,
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
    if data and data.array and data.array.sync_percent is not None:
        return round(data.array.sync_percent, 1)
    return None


def _get_parity_attrs(data: UnraidData) -> dict[str, Any]:
    """Get parity check extra state attributes."""
    if not data or not data.array:
        return {}

    array = data.array
    attrs: dict[str, Any] = {}

    if array.sync_action:
        attrs["sync_action"] = array.sync_action
    if array.sync_errors is not None:
        attrs["sync_errors"] = array.sync_errors
    if array.sync_speed:
        attrs["sync_speed"] = array.sync_speed
    if array.sync_eta:
        attrs["estimated_completion"] = array.sync_eta

    return attrs


# =============================================================================
# Value Functions for UPS Sensors
# =============================================================================


def _get_ups_battery(data: UnraidData) -> float | None:
    """Get UPS battery level from coordinator data."""
    if data and data.ups:
        return data.ups.battery_charge_percent
    return None


def _get_ups_battery_attrs(data: UnraidData) -> dict[str, Any]:
    """Get UPS battery extra state attributes."""
    if not data or not data.ups:
        return {}

    ups = data.ups
    attrs: dict[str, Any] = {}
    _add_attr_if_set(attrs, ATTR_UPS_STATUS, ups.status)
    _add_attr_if_set(attrs, ATTR_UPS_MODEL, ups.model)
    return attrs


def _get_ups_load(data: UnraidData) -> float | None:
    """Get UPS load from coordinator data."""
    if data and data.ups:
        return data.ups.load_percent
    return None


def _get_ups_runtime(data: UnraidData) -> int | None:
    """Get UPS runtime in minutes from coordinator data."""
    if data and data.ups:
        minutes = data.ups.runtime_minutes
        if minutes is not None:
            return int(minutes)
    return None


def _get_ups_power(data: UnraidData) -> float | None:
    """Get UPS power from coordinator data."""
    if data and data.ups:
        return data.ups.power_watts
    return None


# =============================================================================
# Value Functions for Flash Drive Sensors
# =============================================================================


def _get_flash_usage(data: UnraidData) -> float | None:
    """Get flash drive usage from coordinator data."""
    if data and data.flash_info:
        computed = data.flash_info.computed_used_percent
        if computed is not None:
            return round(float(computed), 1)
    return None


def _get_flash_usage_attrs(data: UnraidData) -> dict[str, Any]:
    """Get flash drive usage extra state attributes."""
    if not data or not data.flash_info:
        return {}

    flash = data.flash_info
    attrs: dict[str, Any] = {}

    total = getattr(flash, "total_bytes", None) or 0
    if not total:
        total = flash.size_bytes or 0
    used = flash.used_bytes or 0
    free = flash.free_bytes or 0

    if total:
        attrs["total_size"] = format_bytes(total)
    if used:
        attrs["used_size"] = format_bytes(used)
    if free:
        attrs["free_size"] = format_bytes(free)

    guid = flash.guid
    if guid:
        attrs["guid"] = guid

    product = getattr(flash, "product", None)
    if product:
        attrs["product"] = product

    vendor = flash.vendor
    if vendor:
        attrs["vendor"] = vendor

    return attrs


def _get_flash_free_space(data: UnraidData) -> int | None:
    """Get flash drive free space from coordinator data."""
    if data and data.flash_info:
        free: int | None = data.flash_info.free_bytes
        return free
    return None


# =============================================================================
# Value Functions for Plugin Sensors
# =============================================================================


def _get_plugins_count(data: UnraidData) -> int | None:
    """Get plugins count from coordinator data."""
    if data and data.plugins:
        plugins = data.plugins.plugins
        if plugins is not None:
            return len(plugins)
        # Fallback to total_plugins field if available
        total: int | None = data.plugins.total_plugins
        if total is not None:
            return total
    return None


def _get_plugins_attrs(data: UnraidData) -> dict[str, Any]:
    """Get plugins extra state attributes."""
    if not data or not data.plugins:
        return {}

    plugins_list = data.plugins.plugins or []
    plugin_names = [p.name for p in plugins_list]

    attrs = {
        "plugin_count": len(plugins_list),
        "plugin_names": plugin_names,
    }

    updates_available = data.plugins.plugins_with_updates
    if updates_available is None:
        updates_available = sum(1 for p in plugins_list if p.update_available)
    if updates_available > 0:
        attrs["updates_available"] = updates_available

    return attrs


def _get_latest_version(data: UnraidData) -> str | None:
    """Get latest Unraid version from coordinator data."""
    if not data:
        return None

    if data.update_status:
        if data.update_status.latest_version:
            return data.update_status.latest_version
        if data.update_status.current_version:
            return data.update_status.current_version

    if data.system:
        return data.system.version
    return None


def _get_latest_version_attrs(data: UnraidData) -> dict[str, Any]:
    """Get latest version extra state attributes."""
    if not data:
        return {}

    update = data.update_status
    current = update.current_version if update else None
    if not current and data.system:
        current = data.system.version
    latest = update.latest_version if update else None

    attrs: dict[str, Any] = {}
    if current:
        attrs["current_version"] = current
    if latest:
        attrs["latest_version"] = latest

    if current and latest:
        attrs["update_available"] = current != latest

    return attrs


def _get_plugins_with_updates(data: UnraidData) -> int | None:
    """Get count of plugins with updates from coordinator data."""
    if data and data.update_status:
        updates = getattr(data.update_status, "plugins_with_updates", None)
        if updates is not None:
            return len(updates) if isinstance(updates, list) else updates

    if data and data.plugins:
        updates = data.plugins.plugins_with_updates
        if updates is not None:
            return len(updates) if isinstance(updates, list) else updates
        plugins_list = data.plugins.plugins or []
        if plugins_list:
            return sum(1 for p in plugins_list if p.update_available)
        return 0
    return None


def _get_plugins_with_updates_attrs(data: UnraidData) -> dict[str, Any]:
    """Get plugins with updates extra state attributes."""
    if not data:
        return {}

    update = data.update_status
    plugins = (getattr(update, "plugins_with_updates", None) or []) if update else []
    plugins = plugins or []

    if isinstance(plugins, list) and plugins:
        return {"plugins_needing_update": plugins}

    if data.plugins:
        plugins_list = data.plugins.plugins or []
        needing_update = [p.name for p in plugins_list if p.update_available]
        if needing_update:
            return {"plugins_needing_update": needing_update}
    return {}


# =============================================================================
# Value Functions for Parity Schedule Sensors
# =============================================================================


def _get_next_parity_check(data: UnraidData) -> datetime | None:
    """Get next parity check timestamp from coordinator data."""
    if not data or not data.parity_schedule:
        return None

    schedule = data.parity_schedule

    if not schedule.is_enabled:
        return None

    return schedule.next_check_datetime


def _get_next_parity_check_attrs(data: UnraidData) -> dict[str, Any]:
    """Get next parity check extra state attributes."""
    if not data or not data.parity_schedule:
        return {}

    schedule = data.parity_schedule
    attrs: dict[str, Any] = {}

    if schedule.enabled is not None:
        attrs["enabled"] = schedule.enabled
    if schedule.mode is not None:
        attrs["mode"] = schedule.mode
    if schedule.frequency is not None:
        attrs["frequency"] = schedule.frequency
    if schedule.day is not None:
        attrs["day"] = schedule.day
    if schedule.month is not None:
        attrs["month"] = schedule.month
    if schedule.hour is not None:
        attrs["hour"] = schedule.hour
    if schedule.correcting is not None:
        attrs["correcting"] = schedule.correcting

    return attrs


def _get_most_recent_parity_record(data: UnraidData) -> Any | None:
    """Get the most recent parity check record by date."""
    if not data or not data.parity_history:
        return None
    return data.parity_history.most_recent


def _get_last_parity_check(data: UnraidData) -> datetime | None:
    """Get last parity check timestamp from coordinator data."""
    last = _get_most_recent_parity_record(data)
    if last:
        raw = last.date
        if raw:
            return parse_timestamp(raw)
    return None


def _get_last_parity_check_attrs(data: UnraidData) -> dict[str, Any]:
    """Get last parity check extra state attributes."""
    last = _get_most_recent_parity_record(data)
    if not last:
        return {}

    attrs: dict[str, Any] = {}

    errors = last.errors
    if errors is not None:
        attrs["errors"] = errors

    duration = last.duration_seconds
    if duration:
        attrs["last_duration"] = format_duration(duration)

    result = last.status
    if result:
        attrs["result"] = result

    return attrs


def _get_last_parity_errors(data: UnraidData) -> int | None:
    """Get last parity check error count from coordinator data."""
    last = _get_most_recent_parity_record(data)
    if last:
        return last.errors or 0
    return None


# =============================================================================
# Value Functions for Notification Sensor
# =============================================================================


def _get_notifications_count(data: UnraidData) -> int | None:
    """Get unread notifications count from coordinator data."""
    if not data or data.notifications is None:
        return None

    notifications = data.notifications
    # Handle both list and NotificationsResponse formats
    if isinstance(notifications, list):
        return len(notifications)

    notif_list = notifications.notifications or []
    overview = notifications.overview
    unread_count: int | None = notifications.unread_count

    if overview is None and notif_list:
        return len(notif_list)

    return unread_count


def _get_notifications_attrs(data: UnraidData) -> dict[str, Any]:
    """Get notifications extra state attributes."""
    if not data or data.notifications is None:
        return {}

    notifications = data.notifications
    attrs: dict[str, Any] = {}

    if isinstance(notifications, list):
        if notifications:
            attrs["total_count"] = len(notifications)

        recent: list[dict[str, Any]] = []
        for notif in notifications[:5]:
            subject = notif.subject
            importance = notif.importance
            if subject:
                recent.append(
                    {"subject": subject, "importance": importance}
                    if importance
                    else {"subject": subject}
                )
        if recent:
            attrs["recent_notifications"] = recent
        return attrs

    unread_count = notifications.unread_count
    if unread_count is not None:
        attrs["unread_count"] = unread_count

    total = getattr(notifications, "total_count", None)
    overview = notifications.overview
    if total is None and overview is not None:
        unread_total = getattr(overview.unread, "total", None) or 0
        archive_total = getattr(overview.archive, "total", None) or 0
        if unread_total or archive_total:
            total = unread_total + archive_total

    notif_list = notifications.notifications or []
    if total is None and notif_list:
        total = len(notif_list)

    if total is not None:
        attrs["total_count"] = total

    if notif_list:
        recent = []
        for notif in notif_list[:5]:
            subject = notif.subject
            importance = notif.importance
            if subject:
                recent.append(
                    {"subject": subject, "importance": importance}
                    if importance
                    else {"subject": subject}
                )
        if recent:
            attrs["recent_notifications"] = recent

    return attrs


# =============================================================================
# Value Functions for Docker vDisk and Log Filesystem
# =============================================================================


def _get_docker_vdisk_usage(data: UnraidData) -> float | None:
    """Get Docker vDisk usage from coordinator data."""
    if not data or not data.disks:
        return None

    vdisk = next((d for d in data.disks if (d.role or "") == "docker_vdisk"), None)
    if vdisk:
        computed = vdisk.computed_used_percent
        if computed is not None:
            return round(float(computed), 1)
    return None


def _get_docker_vdisk_attrs(data: UnraidData) -> dict[str, Any]:
    """Get Docker vDisk extra state attributes."""
    if not data or not data.disks:
        return {}

    vdisk = next((d for d in data.disks if (d.role or "") == "docker_vdisk"), None)
    if not vdisk:
        return {}

    total = getattr(vdisk, "total_bytes", None) or 0
    used = vdisk.used_bytes or 0
    free = vdisk.free_bytes or 0
    # Calculate total from used + free if total_bytes is not available
    if total == 0 and (used > 0 or free > 0):
        total = used + free

    attrs = {}
    if total:
        attrs["total_size"] = format_bytes(total)
    if used:
        attrs["used_size"] = format_bytes(used)
    if free:
        attrs["free_size"] = format_bytes(free)

    return attrs


def _get_log_filesystem_usage(data: UnraidData) -> float | None:
    """Get log filesystem usage from coordinator data."""
    if not data or not data.disks:
        return None

    log_fs = next((d for d in data.disks if (d.role or "") == "log"), None)
    if log_fs:
        computed = log_fs.computed_used_percent
        if computed is not None:
            return round(float(computed), 1)
    return None


def _get_log_filesystem_attrs(data: UnraidData) -> dict[str, Any]:
    """Get log filesystem extra state attributes."""
    if not data or not data.disks:
        return {}

    log_fs = next((d for d in data.disks if (d.role or "") == "log"), None)
    if not log_fs:
        return {}

    total = getattr(log_fs, "total_bytes", None) or 0
    used = log_fs.used_bytes or 0
    free = log_fs.free_bytes or 0
    # Calculate total from used + free if total_bytes is not available
    if total == 0 and (used > 0 or free > 0):
        total = used + free

    attrs = {}
    if total:
        attrs["total_size"] = format_bytes(total)
    if used:
        attrs["used_size"] = format_bytes(used)
    if free:
        attrs["free_size"] = format_bytes(free)

    return attrs


# =============================================================================
# Value Functions for ZFS Sensors
# =============================================================================


def _get_zfs_arc_hit_ratio(data: UnraidData) -> float | None:
    """Get ZFS ARC hit ratio from coordinator data."""
    if data and data.zfs_arc:
        return data.zfs_arc.hit_ratio_percent
    return None


def _get_zfs_arc_attrs(data: UnraidData) -> dict[str, Any]:
    """Get ZFS ARC extra state attributes."""
    if not data or not data.zfs_arc:
        return {}

    arc = data.zfs_arc
    attrs: dict[str, Any] = {}

    size = arc.size_bytes
    if size:
        attrs["arc_size"] = format_bytes(size)

    target = arc.target_size_bytes
    if target:
        attrs["target_size"] = format_bytes(target)

    hits = arc.hits
    if hits is not None:
        attrs["hits"] = hits

    misses = arc.misses
    if misses is not None:
        attrs["misses"] = misses

    return attrs


# =============================================================================
# Sensor Entity Descriptions - System Sensors
# =============================================================================

SYSTEM_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
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
        suggested_display_precision=1,
        value_fn=_get_cpu_temperature,
    ),
    UnraidSensorEntityDescription(
        key="motherboard_temperature",
        translation_key="motherboard_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_get_motherboard_temperature,
        supported_fn=lambda data: (
            data is not None
            and data.system is not None
            and data.system.motherboard_temp_celsius is not None
        ),
    ),
    UnraidSensorEntityDescription(
        key="cpu_power",
        translation_key="cpu_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_get_cpu_power,
        supported_fn=lambda data: (
            data is not None
            and data.system is not None
            and data.system.cpu_power_watts is not None
        ),
    ),
    UnraidSensorEntityDescription(
        key="dram_power",
        translation_key="dram_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_get_dram_power,
        supported_fn=lambda data: (
            data is not None
            and data.system is not None
            and data.system.dram_power_watts is not None
        ),
    ),
    UnraidSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_uptime,
        extra_state_attributes_fn=_get_uptime_attrs,
    ),
    UnraidSensorEntityDescription(
        key="chipset_temperature",
        translation_key="chipset_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_get_chipset_temperature,
        supported_fn=lambda data: (
            data is not None
            and data.system is not None
            and data.system.chipset_temp_celsius is not None
        ),
    ),
    UnraidSensorEntityDescription(
        key="cpu_governor",
        translation_key="cpu_governor",
        icon="mdi:gauge",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_cpu_governor,
        extra_state_attributes_fn=_get_cpu_governor_attrs,
        supported_fn=lambda data: (
            data is not None
            and data.system is not None
            and data.system.cpu_power_state is not None
            and data.system.cpu_power_state.governor is not None
        ),
    ),
    UnraidSensorEntityDescription(
        key="cpu_frequency",
        translation_key="cpu_frequency",
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_get_cpu_current_frequency,
        extra_state_attributes_fn=_get_cpu_frequency_attrs,
        supported_fn=lambda data: (
            data is not None
            and data.system is not None
            and data.system.cpu_power_state is not None
            and data.system.cpu_power_state.current_freq_mhz is not None
        ),
    ),
)


# =============================================================================
# Sensor Entity Descriptions - Array Sensors
# =============================================================================

ARRAY_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="array_usage",
        translation_key="array_usage",
        native_unit_of_measurement=PERCENTAGE,
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
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_parity_progress,
        extra_state_attributes_fn=_get_parity_attrs,
    ),
)


# =============================================================================
# Sensor Entity Descriptions - UPS Sensors
# =============================================================================

UPS_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="ups_battery",
        translation_key="ups_battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_ups_battery,
        extra_state_attributes_fn=_get_ups_battery_attrs,
    ),
    UnraidSensorEntityDescription(
        key="ups_load",
        translation_key="ups_load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery",
        value_fn=_get_ups_load,
    ),
    UnraidSensorEntityDescription(
        key="ups_runtime",
        translation_key="ups_runtime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer",
        value_fn=_get_ups_runtime,
    ),
    UnraidSensorEntityDescription(
        key="ups_power",
        translation_key="ups_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_ups_power,
    ),
    UnraidSensorEntityDescription(
        key="ups_energy",
        translation_key="ups_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda _: None,  # Handled by specialized entity class
    ),
)


# =============================================================================
# Sensor Entity Descriptions - Flash Drive Sensors
# =============================================================================

FLASH_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="flash_usage",
        translation_key="flash_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:usb-flash-drive",
        suggested_display_precision=1,
        value_fn=_get_flash_usage,
        extra_state_attributes_fn=_get_flash_usage_attrs,
    ),
    UnraidSensorEntityDescription(
        key="flash_free_space",
        translation_key="flash_free_space",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        icon="mdi:usb-flash-drive-outline",
        value_fn=_get_flash_free_space,
    ),
)


# =============================================================================
# Sensor Entity Descriptions - Plugin/Update Sensors
# =============================================================================

PLUGIN_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="plugins",
        translation_key="plugins",
        icon="mdi:puzzle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_plugins_count,
        extra_state_attributes_fn=_get_plugins_attrs,
    ),
    UnraidSensorEntityDescription(
        key="latest_version",
        translation_key="latest_version",
        icon="mdi:update",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_latest_version,
        extra_state_attributes_fn=_get_latest_version_attrs,
        supported_fn=lambda data: (
            data is not None
            and (data.update_status is not None or data.system is not None)
        ),
    ),
    UnraidSensorEntityDescription(
        key="plugins_with_updates",
        translation_key="plugins_with_updates",
        icon="mdi:puzzle-plus",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_plugins_with_updates,
        extra_state_attributes_fn=_get_plugins_with_updates_attrs,
        supported_fn=lambda data: (
            data is not None
            and (data.update_status is not None or data.plugins is not None)
        ),
    ),
)


# =============================================================================
# Sensor Entity Descriptions - Parity Schedule Sensors
# =============================================================================

PARITY_SCHEDULE_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="next_parity_check",
        translation_key="next_parity_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_next_parity_check,
        extra_state_attributes_fn=_get_next_parity_check_attrs,
        supported_fn=lambda data: data is not None and data.parity_schedule is not None,
    ),
    UnraidSensorEntityDescription(
        key="last_parity_check",
        translation_key="last_parity_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_last_parity_check,
        extra_state_attributes_fn=_get_last_parity_check_attrs,
        supported_fn=lambda data: (
            data is not None
            and data.parity_history is not None
            and data.parity_history.records is not None
            and len(data.parity_history.records or []) > 0
        ),
    ),
)


# =============================================================================
# Sensor Entity Descriptions - Notification Sensor
# =============================================================================

NOTIFICATION_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="notifications",
        translation_key="notifications",
        icon="mdi:bell",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_notifications_count,
        extra_state_attributes_fn=_get_notifications_attrs,
    ),
)


# =============================================================================
# Sensor Entity Descriptions - Virtual Disk Sensors
# =============================================================================

VIRTUAL_DISK_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="docker_vdisk_usage",
        translation_key="docker_vdisk_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:docker",
        suggested_display_precision=1,
        value_fn=_get_docker_vdisk_usage,
        extra_state_attributes_fn=_get_docker_vdisk_attrs,
        supported_fn=lambda data: (
            data is not None
            and data.disks is not None
            and any((d.role or "") == "docker_vdisk" for d in data.disks)
        ),
    ),
    UnraidSensorEntityDescription(
        key="log_filesystem_usage",
        translation_key="log_filesystem_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:file-document",
        suggested_display_precision=1,
        value_fn=_get_log_filesystem_usage,
        extra_state_attributes_fn=_get_log_filesystem_attrs,
        supported_fn=lambda data: (
            data is not None
            and data.disks is not None
            and any((d.role or "") == "log" for d in data.disks)
        ),
    ),
)


# =============================================================================
# Sensor Entity Descriptions - ZFS Sensors
# =============================================================================

ZFS_ARC_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="zfs_arc_hit_ratio",
        translation_key="zfs_arc_hit_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
        suggested_display_precision=1,
        value_fn=_get_zfs_arc_hit_ratio,
        extra_state_attributes_fn=_get_zfs_arc_attrs,
        supported_fn=lambda data: data is not None and data.zfs_arc is not None,
    ),
)


# =============================================================================
# Sensor Entity Class
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


class UnraidSystemStatusSensor(UnraidBaseEntity, SensorEntity):
    """High-level system status sensor for shutdown and reboot visibility."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
    ) -> None:
        """Initialize the system status sensor."""
        super().__init__(coordinator, "system_status")
        self._attr_translation_key = "system_status"

    @property
    def native_value(self) -> str:
        """Return the current status of the Unraid system."""
        return self.coordinator.system_status

    @property
    def icon(self) -> str:
        """Return a status-specific icon."""
        status = self.native_value
        if status == "online":
            return "mdi:server"
        if status in {"starting_array", "reboot_requested", "server_rebooting"}:
            return "mdi:restart"
        if status in {"stopping_array", "shutdown_requested", "shutting_down"}:
            return "mdi:power"
        if status == "server_shutdown":
            return "mdi:server-off"
        if status == "array_stopped":
            return "mdi:harddisk-remove"
        return "mdi:server-network-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for system status diagnostics."""
        attrs: dict[str, Any] = {
            "websocket_connected": self.coordinator.websocket_connected,
        }

        if self.coordinator.pending_system_action is not None:
            attrs["pending_action"] = self.coordinator.pending_system_action

        if self.coordinator.pending_system_action_message is not None:
            attrs["action_message"] = self.coordinator.pending_system_action_message

        requested_at = self.coordinator.pending_system_action_requested_at
        if requested_at is not None:
            attrs["action_requested_at"] = requested_at.isoformat()

        data = self.coordinator.data
        if data and data.array:
            array_state = data.array.state
            if array_state is not None:
                attrs["array_state"] = array_state

        return attrs

    @property
    def available(self) -> bool:
        """Keep the status sensor available during reboots and shutdowns."""
        return True


# =============================================================================
# Dynamic Sensor Entity Classes (for sensors needing runtime context)
# =============================================================================


class UnraidFanSensor(UnraidBaseEntity, SensorEntity):
    """Fan speed sensor."""

    _attr_native_unit_of_measurement = "RPM"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fan"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        fan_name: str,
        normalized_name: str,
    ) -> None:
        """Initialize the sensor."""
        self._original_fan_name = fan_name
        sanitized = normalized_name.lower().replace(" ", "_")
        super().__init__(coordinator, f"fan_{sanitized}")
        self._fan_name = fan_name
        self._normalized_name = normalized_name
        self._attr_translation_key = "fan"
        self._attr_translation_placeholders = {"name": normalized_name}

    def _get_fan_control_device(self) -> Any:
        """
        Get matching FanDevice from fan_control data.

        System fans use chip driver names (e.g., nct6793_fan1) while fan_control
        uses hwmon IDs (e.g., hwmon4_fan1). Both share the same numeric index
        suffix, so we match on hwmon_index when an exact name match fails.
        """
        data = self.coordinator.data
        if not data or not data.fan_control:
            return None

        devices = (data.fan_control.fans or []) or []

        # Try exact name match first
        for device in devices:
            if device.name == self._normalized_name:
                return device

        # Match by fan index suffix (e.g., nct6793_fan1 → index 1 → hwmon_index 1)
        match = re.search(r"_fan(\d+)$", self._fan_name)
        if match:
            fan_index = int(match.group(1))
            for device in devices:
                if device.hwmon_index == fan_index:
                    return device

        return None

    @property
    def native_value(self) -> int | None:
        """Return the fan speed."""
        # Prefer fan_control data (more detailed) over system.fans
        device = self._get_fan_control_device()
        if device is not None:
            rpm: int | None = device.rpm
            if rpm is not None:
                return rpm

        data = self.coordinator.data
        if not data or not data.system:
            return None

        fans: list[Any] = (data.system.fans or []) or []
        for fan in fans:
            if isinstance(fan, dict):
                if fan.get("name") == self._fan_name:
                    rpm_val: int | None = fan.get("rpm")
                    return rpm_val
            elif not isinstance(fan, (int, float)) and fan.name == self._fan_name:
                result: int | None = fan.rpm
                return result
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes from fan control data."""
        attrs: dict[str, Any] = {}
        if self._original_fan_name != self._normalized_name:
            attrs["original_name"] = self._original_fan_name

        device = self._get_fan_control_device()
        if device is not None:
            pwm_percent = device.pwm_percent
            if pwm_percent is not None:
                attrs["pwm_percent"] = round(pwm_percent, 1)
            mode = device.mode
            if mode is not None:
                attrs["mode"] = mode
            controllable = device.controllable
            if controllable is not None:
                attrs["controllable"] = controllable
            fan_id = device.id
            if fan_id is not None:
                attrs["fan_id"] = fan_id

        # Add failed status from summary
        data = self.coordinator.data
        if data and data.fan_control:
            summary = data.fan_control.summary
            if summary:
                failed = (summary.failed_fans or []) or []
                device = self._get_fan_control_device()
                fan_id = device.id if device else None
                if fan_id and fan_id in failed:
                    attrs["failed"] = True

        return attrs


class UnraidNetworkSensorBase(UnraidBaseEntity, RestoreEntity, SensorEntity):
    """Base class for network rate sensors with restart-safe caching."""

    _attr_native_unit_of_measurement = UnitOfDataRate.KILOBITS_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        interface_name: str,
        direction: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"network_{interface_name}_{direction}")
        self._interface_name = interface_name
        self._direction = direction
        self._attr_translation_key = f"network_{direction}"
        self._attr_translation_placeholders = {"interface": interface_name.upper()}
        self._attr_icon = (
            "mdi:download-network" if direction == "rx" else "mdi:upload-network"
        )

        self._rate_calculator = RateCalculator(
            stale_threshold_seconds=NETWORK_RATE_STALE_SECONDS
        )
        self._last_uptime_seconds: int | None = None

    async def async_added_to_hass(self) -> None:
        """Restore previous calculator context when added to hass."""
        await super().async_added_to_hass()
        await self._async_restore_rate_state()

    async def _async_restore_rate_state(self) -> None:
        """Restore the previously persisted rate calculator context."""
        if (extra_data := await self.async_get_last_extra_data()) is None:
            return

        restored = UnraidRateSensorExtraStoredData.from_dict(extra_data.as_dict())
        if restored is None:
            return

        try:
            restored_rate = float(restored.native_value)
        except TypeError, ValueError:
            restored_rate = 0.0

        self._rate_calculator.restore_state(
            last_bytes=restored.last_bytes,
            last_timestamp=restored.last_timestamp,
            rate_kbps=restored_rate,
        )
        self._last_uptime_seconds = restored.last_uptime_seconds

    @property
    def extra_restore_state_data(self) -> UnraidRateSensorExtraStoredData:
        """Return network sensor state data that should survive restarts."""
        interface = self._get_interface()
        current_bytes = (
            self._get_bytes(interface)
            if interface is not None
            else self._rate_calculator.last_bytes
        )
        return UnraidRateSensorExtraStoredData(
            self.native_value,
            self.native_unit_of_measurement,
            current_bytes,
            self._rate_calculator.last_timestamp,
            getattr(self, "_last_uptime_seconds", None),
        )

    def _get_interface(self) -> Any:
        """Get the network interface data."""
        data = self.coordinator.data
        if not data or not data.network:
            return None
        return next(
            (i for i in data.network if i.name == self._interface_name),
            None,
        )

    def _get_bytes(self, interface: Any) -> int | None:
        """Get bytes from interface - override in subclass."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        interface = self._get_interface()
        if not interface:
            super()._handle_coordinator_update()
            return

        current_bytes = self._get_bytes(interface)
        if current_bytes is not None:
            current_uptime_seconds = _get_system_uptime_seconds(self.coordinator.data)
            if _did_system_reboot(
                current_uptime_seconds,
                getattr(self, "_last_uptime_seconds", None),
            ):
                self._rate_calculator.reset()

            self._rate_calculator.add_sample(
                current_bytes, dt_util.utcnow().timestamp()
            )
            self._last_uptime_seconds = current_uptime_seconds

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        """Return the calculated rate."""
        return self._rate_calculator.rate_kbps

    @property
    def available(self) -> bool:
        """Return if the sensor's interface is present in coordinator data."""
        return super().available and self._get_interface() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        interface = self._get_interface()
        if not interface:
            return {}

        attrs: dict[str, Any] = {}
        _add_attr_if_set(attrs, ATTR_NETWORK_MAC, interface.mac_address)
        _add_attr_if_set(attrs, ATTR_NETWORK_IP, interface.ip_address)
        _add_attr_if_set(attrs, ATTR_NETWORK_SPEED, interface.speed_mbps)
        return attrs


class UnraidNetworkRXSensor(UnraidNetworkSensorBase):
    """Network RX (receive) rate sensor."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        interface_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface_name, "rx")

    def _get_bytes(self, interface: Any) -> int | None:
        """Get received bytes from interface."""
        result: int | None = interface.bytes_received
        return result


class UnraidNetworkTXSensor(UnraidNetworkSensorBase):
    """Network TX (transmit) rate sensor."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        interface_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, interface_name, "tx")

    def _get_bytes(self, interface: Any) -> int | None:
        """Get transmitted bytes from interface."""
        result: int | None = interface.bytes_sent
        return result


class UnraidDiskSensorBase(UnraidBaseEntity, SensorEntity):
    """Base class for disk sensors."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        disk_id: str,
        disk_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"disk_{disk_id}_{sensor_type}")
        self._disk_id = disk_id
        self._disk_name = disk_name

    def _get_disk(self) -> Any:
        """Get the disk data."""
        data = self.coordinator.data
        if not data or not data.disks:
            return None
        return next(
            (d for d in data.disks if self._disk_id in (d.id, d.name)),
            None,
        )


class UnraidDiskUsageSensor(UnraidDiskSensorBase):
    """Disk usage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:harddisk"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, disk_id, disk_name, "usage")
        self._attr_translation_key = "disk_usage"
        self._attr_translation_placeholders = {"disk_name": disk_name}

    @property
    def native_value(self) -> float | None:
        """Return the disk usage percentage."""
        disk = self._get_disk()
        if not disk:
            return None

        computed = disk.computed_used_percent
        if computed is not None:
            return round(float(computed), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        disk = self._get_disk()
        if not disk:
            return {}

        total = disk.size_bytes or 0
        used = disk.used_bytes or 0
        free = disk.free_bytes or 0

        attrs: dict[str, Any] = {
            "disk_name": self._disk_name,
        }
        _add_attr_if_set(attrs, "role", disk.role)
        _add_attr_if_set(attrs, "status", disk.status)

        if total:
            attrs["total_size"] = format_bytes(total)
        if used:
            attrs["used_size"] = format_bytes(used)
        if free:
            attrs["free_size"] = format_bytes(free)

        return attrs


class UnraidDiskHealthSensor(UnraidDiskSensorBase, RestoreEntity):
    """Disk health/SMART status sensor."""

    _attr_icon = "mdi:harddisk"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, disk_id, disk_name, "health")
        self._attr_translation_key = "disk_health"
        self._attr_translation_placeholders = {"disk_name": disk_name}
        self._last_known_health: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the cached SMART health value when added to hass."""
        await super().async_added_to_hass()
        await self._async_restore_last_known_health()

    async def _async_restore_last_known_health(self) -> None:
        """Restore the last known SMART health value."""
        if (last_state := await self.async_get_last_state()) is None:
            return

        if last_state.state not in (None, "unknown", "unavailable"):
            self._last_known_health = last_state.state

    def _is_standby(self, disk: Any) -> bool:
        """Return true if the disk is in standby mode."""
        result: bool = disk.is_standby
        return result

    @property
    def native_value(self) -> str | None:
        """Return the disk health status."""
        disk = self._get_disk()
        if not disk:
            return self._last_known_health

        health: str | None = disk.smart_status or disk.status

        if health is not None:
            # Update cached value when we have fresh data
            self._last_known_health = health
            return health

        # No health data available - return cached value if disk is in standby
        if self._is_standby(disk) and self._last_known_health is not None:
            return self._last_known_health

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        disk = self._get_disk()
        if not disk:
            return {}

        attrs: dict[str, Any] = {
            "disk_name": self._disk_name,
        }
        _add_attr_if_set(attrs, "device", disk.device)
        _add_attr_if_set(attrs, "model", disk.model)
        _add_attr_if_set(attrs, "serial", disk.serial_number)

        spin_state = disk.spin_state
        if spin_state is not None:
            attrs["spin_state"] = spin_state

        health = disk.smart_status or disk.status
        if health is None and self._is_standby(disk) and self._last_known_health:
            attrs["cached_value"] = True

        temp = disk.temperature_celsius
        if temp is not None and temp > 0:
            attrs["temperature"] = f"{temp} °C"

        return attrs


class UnraidDiskTemperatureSensor(UnraidDiskSensorBase):
    """
    Disk temperature sensor.

    This sensor is disabled by default. Users can enable individual disk
    temperature sensors as needed from the entity settings.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, disk_id, disk_name, "temperature")
        self._attr_translation_key = "disk_temperature"
        self._attr_translation_placeholders = {"disk_name": disk_name}

    @property
    def native_value(self) -> float | None:
        """Return the disk temperature in Celsius."""
        disk = self._get_disk()
        if not disk:
            return None
        temp = disk.temperature_celsius
        if temp is not None and temp > 0:
            return float(temp)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        disk = self._get_disk()
        if not disk:
            return {}

        attrs: dict[str, Any] = {
            "disk_name": self._disk_name,
        }
        _add_attr_if_set(attrs, "device", disk.device)
        _add_attr_if_set(attrs, "model", disk.model)
        _add_attr_if_set(attrs, "role", disk.role)

        return attrs


class UnraidDiskSmartErrorsSensor(UnraidDiskSensorBase):
    """
    Disk SMART errors sensor.

    Reports the number of SMART errors detected on the disk.
    Disabled by default. Uses TOTAL state class since errors only increase.
    """

    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:alert-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, disk_id, disk_name, "smart_errors")
        self._attr_translation_key = "disk_smart_errors"
        self._attr_translation_placeholders = {"disk_name": disk_name}

    @property
    def native_value(self) -> int | None:
        """Return the number of SMART errors."""
        disk = self._get_disk()
        if not disk:
            return None
        result: int | None = disk.smart_errors
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        disk = self._get_disk()
        if not disk:
            return {}

        attrs: dict[str, Any] = {
            "disk_name": self._disk_name,
        }
        _add_attr_if_set(attrs, "device", disk.device)
        _add_attr_if_set(attrs, "smart_status", disk.smart_status)
        _add_attr_if_set(attrs, "power_on_hours", disk.power_on_hours)

        return attrs


class UnraidDiskReadBytesSensor(UnraidDiskSensorBase):
    """
    Disk read bytes sensor.

    Reports total bytes read from the disk. Uses TOTAL_INCREASING state class
    for monotonically increasing counters. Disabled by default.
    """

    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_unit_of_measurement = UnitOfInformation.GIBIBYTES
    _attr_icon = "mdi:harddisk-plus"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, disk_id, disk_name, "read_bytes")
        self._attr_translation_key = "disk_read_bytes"
        self._attr_translation_placeholders = {"disk_name": disk_name}

    @property
    def native_value(self) -> int | None:
        """Return total bytes read from the disk."""
        disk = self._get_disk()
        if not disk:
            return None
        result: int | None = disk.read_bytes
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        disk = self._get_disk()
        if not disk:
            return {}

        attrs: dict[str, Any] = {
            "disk_name": self._disk_name,
        }
        _add_attr_if_set(attrs, "device", disk.device)
        _add_attr_if_set(attrs, "read_ops", disk.read_ops)

        return attrs


class UnraidDiskWriteBytesSensor(UnraidDiskSensorBase):
    """
    Disk write bytes sensor.

    Reports total bytes written to the disk. Uses TOTAL_INCREASING state class
    for monotonically increasing counters. Disabled by default.
    """

    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_unit_of_measurement = UnitOfInformation.GIBIBYTES
    _attr_icon = "mdi:harddisk-plus"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, disk_id, disk_name, "write_bytes")
        self._attr_translation_key = "disk_write_bytes"
        self._attr_translation_placeholders = {"disk_name": disk_name}

    @property
    def native_value(self) -> int | None:
        """Return total bytes written to the disk."""
        disk = self._get_disk()
        if not disk:
            return None
        result: int | None = disk.write_bytes
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        disk = self._get_disk()
        if not disk:
            return {}

        attrs: dict[str, Any] = {
            "disk_name": self._disk_name,
        }
        _add_attr_if_set(attrs, "device", disk.device)
        _add_attr_if_set(attrs, "write_ops", disk.write_ops)

        return attrs


class UnraidShareUsageSensor(UnraidBaseEntity, SensorEntity):
    """Share usage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:folder-network"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        share_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"share_{share_name}_usage")
        self._share_name = share_name
        self._attr_translation_key = "share_usage"
        self._attr_translation_placeholders = {"share_name": share_name}

    def _get_share(self) -> Any:
        """Get the share data."""
        data = self.coordinator.data
        if not data or not data.shares:
            return None
        return next(
            (s for s in data.shares if s.name == self._share_name),
            None,
        )

    @property
    def native_value(self) -> float | None:
        """Return the share usage percentage."""
        share = self._get_share()
        if not share:
            return None

        computed = getattr(share, "computed_used_percent", None)
        if computed is not None:
            return round(float(computed), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        share = self._get_share()
        if not share:
            return {}

        total = share.total_bytes or 0
        used = share.used_bytes or 0
        free = share.free_bytes or 0

        attrs = {
            "share_name": self._share_name,
        }

        if total:
            attrs["total_size"] = format_bytes(total)
        if used:
            attrs["used_size"] = format_bytes(used)
        if free:
            attrs["free_size"] = format_bytes(free)

        # Cache configuration attributes from the vendored API models
        use_cache = share.use_cache
        if use_cache:
            attrs["use_cache"] = use_cache

        cache_pool = share.cache_pool
        if cache_pool:
            attrs["cache_pool"] = cache_pool

        mover_action = share.mover_action
        if mover_action:
            attrs["mover_action"] = mover_action

        return attrs


class UnraidZFSPoolSensorBase(UnraidBaseEntity, SensorEntity):
    """Base class for ZFS pool sensors."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        pool_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"zfs_{pool_name}_{sensor_type}")
        self._pool_name = pool_name

    def _get_pool(self) -> Any:
        """Get the ZFS pool data."""
        data = self.coordinator.data
        if not data or not data.zfs_pools:
            return None
        return next(
            (p for p in data.zfs_pools if p.name == self._pool_name),
            None,
        )


class UnraidZFSPoolUsageSensor(UnraidZFSPoolSensorBase):
    """ZFS pool usage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:database"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        pool_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, pool_name, "usage")
        self._attr_translation_key = "zfs_pool_usage"
        self._attr_translation_placeholders = {"pool_name": pool_name}

    @property
    def native_value(self) -> float | None:
        """Return the pool usage percentage."""
        pool = self._get_pool()
        if not pool:
            return None

        computed = pool.computed_used_percent
        if computed is not None:
            return round(float(computed), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        pool = self._get_pool()
        if not pool:
            return {}

        total = pool.size_bytes or 0
        used = pool.used_bytes or 0
        free = pool.free_bytes or 0

        attrs = {"pool_name": self._pool_name}

        if total:
            attrs["total_size"] = format_bytes(total)
        if used:
            attrs["used_size"] = format_bytes(used)
        if free:
            attrs["free_size"] = format_bytes(free)

        return attrs


class UnraidZFSPoolHealthSensor(UnraidZFSPoolSensorBase):
    """ZFS pool health sensor."""

    _attr_icon = "mdi:database-check"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        pool_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, pool_name, "health")
        self._attr_translation_key = "zfs_pool_health"
        self._attr_translation_placeholders = {"pool_name": pool_name}

    @property
    def native_value(self) -> str | None:
        """Return the pool health status."""
        pool = self._get_pool()
        if not pool:
            return None
        result: str | None = pool.health or pool.state
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        pool = self._get_pool()
        if not pool:
            return {}

        attrs = {"pool_name": self._pool_name}

        errors = getattr(pool, "errors", None)
        if errors is not None:
            attrs["errors"] = errors

        return attrs


# =============================================================================
# GPU Metric Sensors
# =============================================================================


class UnraidGPUSensorBase(UnraidBaseEntity, SensorEntity):
    """Base class for per-GPU sensors."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        gpu_index: int,
        gpu_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"gpu_{gpu_index}_{sensor_type}")
        self._gpu_index = gpu_index
        self._gpu_name = gpu_name

    def _find_gpu(self) -> Any | None:
        """Find a GPU by its stable index."""
        data = self.coordinator.data
        if not data or not data.gpu:
            return None
        return next((gpu for gpu in data.gpu if gpu.index == self._gpu_index), None)


class UnraidGPUUtilizationSensor(UnraidGPUSensorBase):
    """Per-GPU utilization sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:expansion-card"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        gpu_index: int,
        gpu_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, gpu_index, gpu_name, "utilization")
        self._attr_translation_key = "gpu_utilization"
        self._attr_translation_placeholders = {"gpu_name": gpu_name}

    @property
    def native_value(self) -> float | None:
        """Return GPU utilization percentage."""
        gpu = self._find_gpu()
        if not gpu:
            return None
        result: float | None = gpu.utilization_gpu_percent
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        gpu = self._find_gpu()
        if not gpu:
            return {}

        attrs: dict[str, Any] = {}
        _add_attr_if_set(attrs, ATTR_GPU_NAME, gpu.name)
        _add_attr_if_set(attrs, ATTR_GPU_DRIVER_VERSION, gpu.driver_version)
        return attrs


class UnraidGPUTemperatureSensor(UnraidGPUSensorBase):
    """Per-GPU temperature sensor."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        gpu_index: int,
        gpu_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, gpu_index, gpu_name, "temperature")
        self._attr_translation_key = "gpu_temperature"
        self._attr_translation_placeholders = {"gpu_name": gpu_name}

    @property
    def native_value(self) -> float | None:
        """Return GPU temperature in Celsius."""
        gpu = self._find_gpu()
        if not gpu:
            return None
        result: float | None = gpu.gpu_temperature
        return result


class UnraidGPUPowerSensor(UnraidGPUSensorBase):
    """Per-GPU power draw sensor."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        gpu_index: int,
        gpu_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, gpu_index, gpu_name, "power")
        self._attr_translation_key = "gpu_power"
        self._attr_translation_placeholders = {"gpu_name": gpu_name}

    @property
    def native_value(self) -> float | None:
        """Return GPU power draw in watts."""
        gpu = self._find_gpu()
        if not gpu:
            return None
        result: float | None = gpu.power_draw_watts
        return result


# =============================================================================
# UPS Energy Sensor (Calculated from Power)
# =============================================================================


class UnraidUPSEnergySensor(UnraidBaseEntity, RestoreEntity, SensorEntity):
    """
    UPS Energy sensor that calculates cumulative energy from power readings.

    This sensor integrates power readings over time to calculate total energy
    consumption in kWh. It persists its state across restarts using RestoreEntity.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_has_entity_name = True
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
    ) -> None:
        """Initialize the UPS energy sensor."""
        super().__init__(coordinator, "ups_energy")
        self._attr_translation_key = "ups_energy"
        self._energy_integrator = EnergyIntegrator()
        self._total_energy: float = 0.0
        self._last_power: float | None = None
        self._last_uptime_seconds: int | None = None

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()
        await self._async_restore_energy_state()

    async def _async_restore_energy_state(self) -> None:
        """Restore the accumulated energy total and integration baseline."""
        if (
            last_state := await self.async_get_last_state()
        ) is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._total_energy = float(last_state.state)
            except TypeError, ValueError:
                self._total_energy = 0.0

        if (extra_data := await self.async_get_last_extra_data()) is None:
            return

        restored = UnraidEnergySensorExtraStoredData.from_dict(extra_data.as_dict())
        if restored is None:
            return

        if self._total_energy == 0.0:
            try:
                self._total_energy = float(restored.native_value)
            except TypeError, ValueError:
                pass

        self._last_power = restored.last_power_watts
        self._last_uptime_seconds = restored.last_uptime_seconds
        self._energy_integrator.restore_state(
            last_power_watts=restored.last_power_watts,
            last_timestamp=restored.last_timestamp,
        )

    @property
    def extra_restore_state_data(self) -> UnraidEnergySensorExtraStoredData:
        """Return energy sensor state data that should survive restarts."""
        return UnraidEnergySensorExtraStoredData(
            self.native_value,
            self.native_unit_of_measurement,
            self._last_power,
            self._energy_integrator.last_timestamp,
            self._last_uptime_seconds,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_energy()
        self.async_write_ha_state()

    def _update_energy(self) -> None:
        """Calculate and update energy based on current power reading."""
        if not self.coordinator.data or not self.coordinator.data.ups:
            return

        current_power = self.coordinator.data.ups.power_watts

        if current_power is None or current_power < 0:
            return

        current_uptime_seconds = _get_system_uptime_seconds(self.coordinator.data)
        if _did_system_reboot(
            current_uptime_seconds,
            self._last_uptime_seconds,
        ):
            self._energy_integrator.reset()

        self._energy_integrator.add_sample(current_power, dt_util.utcnow().timestamp())
        self._last_power = current_power
        self._last_uptime_seconds = current_uptime_seconds

    @property
    def native_value(self) -> float:
        """Return the total energy consumed in kWh."""
        return round(self._total_energy + self._energy_integrator.total_wh / 1000, 3)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if not self.coordinator.data:
            return False
        return self.coordinator.data.ups is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}

        if self._last_power is not None:
            attrs["current_power_watts"] = self._last_power

        return attrs


# =============================================================================
# GPU Energy Sensor (Calculated from Power)
# =============================================================================


class UnraidGPUEnergySensor(UnraidBaseEntity, RestoreEntity, SensorEntity):
    """
    GPU Energy sensor that calculates cumulative energy from power readings.

    This sensor integrates power readings over time to calculate total energy
    consumption in kWh. It persists its state across restarts using RestoreEntity.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_has_entity_name = True
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        gpu_index: int,
        gpu_name: str,
    ) -> None:
        """Initialize the GPU energy sensor."""
        super().__init__(coordinator, f"gpu_{gpu_index}_energy")
        self._gpu_index = gpu_index
        self._gpu_name = gpu_name
        self._attr_translation_key = "gpu_energy"
        self._attr_translation_placeholders = {"gpu_name": gpu_name}
        self._energy_integrator = EnergyIntegrator()
        self._total_energy: float = 0.0
        self._last_power: float | None = None
        self._last_uptime_seconds: int | None = None

    def _find_gpu(self) -> Any | None:
        """Find a GPU by its stable index."""
        data = self.coordinator.data
        if not data or not data.gpu:
            return None
        return next((gpu for gpu in data.gpu if gpu.index == self._gpu_index), None)

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()
        await self._async_restore_energy_state()

    async def _async_restore_energy_state(self) -> None:
        """Restore the accumulated energy total and integration baseline."""
        if (
            last_state := await self.async_get_last_state()
        ) is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._total_energy = float(last_state.state)
            except TypeError, ValueError:
                self._total_energy = 0.0

        if (extra_data := await self.async_get_last_extra_data()) is None:
            return

        restored = UnraidEnergySensorExtraStoredData.from_dict(extra_data.as_dict())
        if restored is None:
            return

        if self._total_energy == 0.0:
            try:
                self._total_energy = float(restored.native_value)
            except TypeError, ValueError:
                pass

        self._last_power = restored.last_power_watts
        self._last_uptime_seconds = restored.last_uptime_seconds
        self._energy_integrator.restore_state(
            last_power_watts=restored.last_power_watts,
            last_timestamp=restored.last_timestamp,
        )

    @property
    def extra_restore_state_data(self) -> UnraidEnergySensorExtraStoredData:
        """Return energy sensor state data that should survive restarts."""
        return UnraidEnergySensorExtraStoredData(
            self.native_value,
            self.native_unit_of_measurement,
            self._last_power,
            self._energy_integrator.last_timestamp,
            self._last_uptime_seconds,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_energy()
        self.async_write_ha_state()

    def _update_energy(self) -> None:
        """Calculate and update energy based on current power reading."""
        if not self.coordinator.data:
            return

        gpu = self._find_gpu()
        if gpu is None:
            return

        current_power = gpu.power_draw_watts

        if current_power is None or current_power < 0:
            return

        current_uptime_seconds = _get_system_uptime_seconds(self.coordinator.data)
        if _did_system_reboot(
            current_uptime_seconds,
            self._last_uptime_seconds,
        ):
            self._energy_integrator.reset()

        self._energy_integrator.add_sample(current_power, dt_util.utcnow().timestamp())
        self._last_power = current_power
        self._last_uptime_seconds = current_uptime_seconds

    @property
    def native_value(self) -> float:
        """Return the total energy consumed in kWh."""
        return round(self._total_energy + self._energy_integrator.total_wh / 1000, 3)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if not self.coordinator.data:
            return False
        return self._find_gpu() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}

        if self._last_power is not None:
            attrs["current_power_watts"] = self._last_power

        gpu = self._find_gpu()
        if gpu is not None:
            _add_attr_if_set(attrs, ATTR_GPU_NAME, gpu.name)
            _add_attr_if_set(attrs, ATTR_GPU_DRIVER_VERSION, gpu.driver_version)

        return attrs


# =============================================================================
# Container Metric Sensors
# =============================================================================


class UnraidContainerSensorBase(UnraidBaseEntity, SensorEntity):
    """Base class for per-container metric sensors."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        container_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        safe_name = re.sub(r"[^a-z0-9_]", "_", container_name.lower())
        super().__init__(coordinator, f"container_{safe_name}_{sensor_type}")
        self._container_name = container_name

    def _find_container(self) -> Any | None:
        """Find the container in coordinator data by name."""
        data = self.coordinator.data
        if not data or not data.containers:
            return None
        return next(
            (
                c
                for c in data.containers
                if getattr(c, "name", None) == self._container_name
            ),
            None,
        )


class UnraidContainerCPUSensor(UnraidContainerSensorBase):
    """Container CPU usage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chip"
    _attr_suggested_display_precision = 1
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        container_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, container_name, "cpu")
        self._attr_translation_key = "container_cpu"
        self._attr_translation_placeholders = {"container_name": container_name}

    @property
    def native_value(self) -> float | None:
        """Return the container CPU usage percentage."""
        container = self._find_container()
        if not container:
            return None
        cpu = getattr(container, "cpu_percent", None)
        return round(float(cpu), 1) if cpu is not None else None


class UnraidContainerMemorySensor(UnraidContainerSensorBase):
    """Container memory usage sensor."""

    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_icon = "mdi:memory"
    _attr_suggested_display_precision = 1
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        container_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, container_name, "memory")
        self._attr_translation_key = "container_memory"
        self._attr_translation_placeholders = {"container_name": container_name}

    @property
    def native_value(self) -> float | None:
        """Return the container memory usage in MB."""
        container = self._find_container()
        if not container:
            return None
        mem_bytes = getattr(container, "memory_usage_bytes", None)
        if mem_bytes is not None and mem_bytes > 0:
            return round(float(mem_bytes) / (1024 * 1024), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        container = self._find_container()
        if not container:
            return {}
        attrs: dict[str, Any] = {}
        mem_display = getattr(container, "memory_display", None)
        if mem_display:
            attrs["memory_display"] = mem_display
        limit = getattr(container, "memory_limit_bytes", None)
        if limit:
            attrs["memory_limit"] = format_bytes(limit)
        return attrs


class UnraidContainerMemoryPercentSensor(UnraidContainerSensorBase):
    """Container memory usage percentage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:memory"
    _attr_suggested_display_precision = 1
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        container_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, container_name, "memory_percent")
        self._attr_translation_key = "container_memory_percent"
        self._attr_translation_placeholders = {"container_name": container_name}

    @property
    def native_value(self) -> float | None:
        """Return the container memory usage percentage."""
        container = self._find_container()
        if not container:
            return None
        # Check for memory_percent field from API (exists in ContainerInfo extra fields)
        mem_bytes = getattr(container, "memory_usage_bytes", None)
        limit_bytes = getattr(container, "memory_limit_bytes", None)
        if mem_bytes is not None and limit_bytes and limit_bytes > 0:
            return round(float(mem_bytes) / float(limit_bytes) * 100, 1)
        return None


# =============================================================================
# Docker Aggregate Sensors
# =============================================================================

DOCKER_AGGREGATE_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="docker_cpu_usage",
        translation_key="docker_cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:docker",
        suggested_display_precision=1,
        value_fn=_get_docker_cpu_usage,
        extra_state_attributes_fn=_get_docker_cpu_attrs,
    ),
    UnraidSensorEntityDescription(
        key="docker_memory_usage",
        translation_key="docker_memory_usage",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:docker",
        suggested_display_precision=1,
        value_fn=_get_docker_memory_usage,
        extra_state_attributes_fn=_get_docker_memory_attrs,
    ),
)


# =============================================================================
# Registration Sensors
# =============================================================================

REGISTRATION_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="registration_type",
        translation_key="registration_type",
        icon="mdi:license",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            getattr(data.registration, "type", None) if data.registration else None
        ),
        supported_fn=lambda data: data is not None and data.registration is not None,
    ),
    UnraidSensorEntityDescription(
        key="registration_state",
        translation_key="registration_state",
        icon="mdi:shield-key",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            getattr(data.registration, "state", None) if data.registration else None
        ),
        supported_fn=lambda data: data is not None and data.registration is not None,
    ),
)


# =============================================================================
# Notification Breakdown Sensors
# =============================================================================

NOTIFICATION_BREAKDOWN_SENSOR_DESCRIPTIONS: tuple[
    UnraidSensorEntityDescription, ...
] = (
    UnraidSensorEntityDescription(
        key="notifications_unread_info",
        translation_key="notifications_unread_info",
        icon="mdi:information",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            getattr(data.notifications.overview.unread, "info", 0)
            if data.notifications
            and data.notifications.overview
            and data.notifications.overview.unread
            else 0
        ),
        supported_fn=lambda data: (
            data is not None
            and data.notifications is not None
            and data.notifications.overview is not None
        ),
    ),
    UnraidSensorEntityDescription(
        key="notifications_unread_warning",
        translation_key="notifications_unread_warning",
        icon="mdi:alert",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            getattr(data.notifications.overview.unread, "warning", 0)
            if data.notifications
            and data.notifications.overview
            and data.notifications.overview.unread
            else 0
        ),
        supported_fn=lambda data: (
            data is not None
            and data.notifications is not None
            and data.notifications.overview is not None
        ),
    ),
    UnraidSensorEntityDescription(
        key="notifications_unread_alert",
        translation_key="notifications_unread_alert",
        icon="mdi:alert-circle",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            getattr(data.notifications.overview.unread, "alert", 0)
            if data.notifications
            and data.notifications.overview
            and data.notifications.overview.unread
            else 0
        ),
        supported_fn=lambda data: (
            data is not None
            and data.notifications is not None
            and data.notifications.overview is not None
        ),
    ),
)


# =============================================================================
# Setup Entry
# =============================================================================


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

    # System sensors (always enabled - system collector is required)
    for description in SYSTEM_SENSOR_DESCRIPTIONS:
        if description.supported_fn(data):
            entities.append(UnraidSensorEntity(coordinator, description))

    entities.append(UnraidSystemStatusSensor(coordinator))

    # Array sensors
    for description in ARRAY_SENSOR_DESCRIPTIONS:
        entities.append(UnraidSensorEntity(coordinator, description))

    # Fan sensors (dynamic, one per fan, keyed by normalized name for stability)
    if data and data.system:
        fans: list[Any] = (data.system.fans or []) or []
        seen_names: set[str] = set()
        for idx, fan in enumerate(fans):
            if isinstance(fan, dict):
                fan_name = fan.get("name") or f"fan_{idx}"
                normalized = fan_name
            elif isinstance(fan, (int, float)):
                fan_name = f"fan_{idx}"
                normalized = fan_name
            else:
                fan_name = fan.name or f"fan_{idx}"
                normalized = fan.normalized_name or fan_name
            # Ensure uniqueness in case of duplicate normalized names
            if normalized in seen_names:
                normalized_key = f"{normalized}_{idx}"
                _LOGGER.debug(
                    "Duplicate fan name '%s' (normalized from '%s'), using '%s'",
                    normalized,
                    fan_name,
                    normalized_key,
                )
                fan_name = f"{fan_name}_{idx}"
                normalized = normalized_key
            else:
                normalized_key = normalized
            seen_names.add(normalized_key)
            entities.append(UnraidFanSensor(coordinator, entry, fan_name, normalized))

    # GPU sensors - only if gpu collector is enabled
    if coordinator.is_collector_enabled("gpu") and data and data.gpu:
        for loop_idx, gpu in enumerate(data.gpu):
            # Prefer the API-provided index; fall back to the loop position so
            # unique IDs are never "gpu_None_*" (which would cause collisions).
            gpu_index = gpu.index if gpu.index is not None else loop_idx
            gpu_name = gpu.name or f"GPU {gpu_index}"
            entities.extend(
                [
                    UnraidGPUUtilizationSensor(coordinator, entry, gpu_index, gpu_name),
                    UnraidGPUTemperatureSensor(coordinator, entry, gpu_index, gpu_name),
                    UnraidGPUPowerSensor(coordinator, entry, gpu_index, gpu_name),
                    UnraidGPUEnergySensor(coordinator, entry, gpu_index, gpu_name),
                ]
            )

    # UPS sensors - only if ups collector is enabled
    if (
        coordinator.is_collector_enabled("ups")
        and data
        and data.ups
        and data.ups.status is not None
    ):
        for description in UPS_SENSOR_DESCRIPTIONS:
            # Skip ups_energy - it uses a specialized entity class
            if description.key == "ups_energy":
                continue
            entities.append(UnraidSensorEntity(coordinator, description))

        # Add UPS Energy sensor (uses specialized class for state restoration)
        entities.append(UnraidUPSEnergySensor(coordinator, entry))

    # Disk sensors - only if disk collector is enabled
    if coordinator.is_collector_enabled("disk"):
        disks = data.disks if data else []
        physical_disks = [d for d in (disks or []) if d.is_physical]

        for disk in physical_disks:
            disk_id: str = str(disk.id or disk.name)
            disk_name: str = str(disk.name)
            disk_role: str = str(disk.role or "")

            entities.append(
                UnraidDiskHealthSensor(coordinator, entry, disk_id, disk_name)
            )

            # Temperature sensor (disabled by default)
            entities.append(
                UnraidDiskTemperatureSensor(coordinator, entry, disk_id, disk_name)
            )

            # SMART errors sensor (disabled by default)
            entities.append(
                UnraidDiskSmartErrorsSensor(coordinator, entry, disk_id, disk_name)
            )

            # Disk I/O sensors (disabled by default)
            entities.append(
                UnraidDiskReadBytesSensor(coordinator, entry, disk_id, disk_name)
            )
            entities.append(
                UnraidDiskWriteBytesSensor(coordinator, entry, disk_id, disk_name)
            )

            if disk_role not in ("parity", "parity2"):
                entities.append(
                    UnraidDiskUsageSensor(coordinator, entry, disk_id, disk_name)
                )

        # Virtual disk sensors (docker vdisk, log filesystem)
        for description in VIRTUAL_DISK_SENSOR_DESCRIPTIONS:
            if description.supported_fn(data):
                entities.append(UnraidSensorEntity(coordinator, description))

    # Network sensors - only if network collector is enabled
    if coordinator.is_collector_enabled("network"):
        for interface in (data.network if data else []) or []:
            if interface.name and interface.is_physical and interface.state == "up":
                entities.extend(
                    [
                        UnraidNetworkRXSensor(coordinator, entry, interface.name),
                        UnraidNetworkTXSensor(coordinator, entry, interface.name),
                    ]
                )

    # Share sensors - only if shares collector is enabled
    if coordinator.is_collector_enabled("shares"):
        for share in (data.shares if data else []) or []:
            if share.name:
                entities.append(UnraidShareUsageSensor(coordinator, entry, share.name))

    # ZFS pool sensors - only if zfs collector is enabled
    if coordinator.is_collector_enabled("zfs"):
        zfs_pools = data.zfs_pools if data else []
        if zfs_pools:
            for pool in zfs_pools:
                if pool.name:
                    entities.extend(
                        [
                            UnraidZFSPoolUsageSensor(coordinator, entry, pool.name),
                            UnraidZFSPoolHealthSensor(coordinator, entry, pool.name),
                        ]
                    )

            # ZFS ARC sensors
            for description in ZFS_ARC_SENSOR_DESCRIPTIONS:
                if description.supported_fn(data):
                    entities.append(UnraidSensorEntity(coordinator, description))

    # Flash drive sensors
    if data and data.flash_info:
        for description in FLASH_SENSOR_DESCRIPTIONS:
            entities.append(UnraidSensorEntity(coordinator, description))

    # Plugin sensors
    if data and data.plugins:
        for description in PLUGIN_SENSOR_DESCRIPTIONS:
            if description.supported_fn(data):
                entities.append(UnraidSensorEntity(coordinator, description))

    # Parity schedule sensors
    for description in PARITY_SCHEDULE_SENSOR_DESCRIPTIONS:
        if description.supported_fn(data):
            entities.append(UnraidSensorEntity(coordinator, description))

    # Notification sensor - only if notification collector is enabled
    if (
        coordinator.is_collector_enabled("notification")
        and data
        and data.notifications is not None
    ):
        for description in NOTIFICATION_SENSOR_DESCRIPTIONS:
            entities.append(UnraidSensorEntity(coordinator, description))

        # Notification breakdown sensors (unread by severity)
        for description in NOTIFICATION_BREAKDOWN_SENSOR_DESCRIPTIONS:
            if description.supported_fn(data):
                entities.append(UnraidSensorEntity(coordinator, description))

    # Container metric sensors - only if docker collector is enabled
    if coordinator.is_collector_enabled("docker") and coordinator.is_docker_enabled():
        # Docker aggregate sensors
        for description in DOCKER_AGGREGATE_SENSOR_DESCRIPTIONS:
            entities.append(UnraidSensorEntity(coordinator, description))

        # Per-container sensors
        containers = data.containers if data else []
        seen_container_names: set[str] = set()
        for container in containers or []:
            container_name = getattr(container, "name", None)
            if container_name and container_name not in seen_container_names:
                seen_container_names.add(container_name)
                entities.append(UnraidContainerCPUSensor(coordinator, container_name))
                entities.append(
                    UnraidContainerMemorySensor(coordinator, container_name)
                )
                entities.append(
                    UnraidContainerMemoryPercentSensor(coordinator, container_name)
                )

    # Registration sensors
    if data and data.registration:
        for description in REGISTRATION_SENSOR_DESCRIPTIONS:
            if description.supported_fn(data):
                entities.append(UnraidSensorEntity(coordinator, description))

    _LOGGER.debug("Adding %d Unraid sensor entities", len(entities))
    async_add_entities(entities)
