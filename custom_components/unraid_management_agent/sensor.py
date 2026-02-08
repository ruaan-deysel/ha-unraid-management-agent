"""
Sensor platform for Unraid Management Agent.

This module follows the entity description pattern used by Home Assistant core
integrations. All sensors are defined using dataclass descriptions with value_fn
callbacks, enabling a declarative approach to sensor definition.
"""

from __future__ import annotations

import calendar
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfEnergy,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
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
from .entity import UnraidBaseEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit needed
PARALLEL_UPDATES = 0


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


# =============================================================================
# Value Functions for System Sensors
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

    attrs: dict[str, Any] = {
        ATTR_CPU_CORES: cpu_cores,
        ATTR_CPU_THREADS: cpu_threads,
    }
    _add_attr_if_set(attrs, ATTR_CPU_MODEL, getattr(system, "cpu_model", None))

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

    attrs: dict[str, Any] = {}
    if ram_total:
        attrs[ATTR_RAM_TOTAL] = format_bytes(ram_total)
    _add_attr_if_set(attrs, ATTR_SERVER_MODEL, getattr(system, "server_model", None))

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


def _get_motherboard_temperature(data: UnraidData) -> float | None:
    """Get motherboard temperature from coordinator data."""
    if data and data.system:
        mb_temp = getattr(data.system, "motherboard_temp_celsius", None)
        if mb_temp is not None:
            return round(mb_temp, 1)
    return None


def _get_uptime(data: UnraidData) -> datetime | None:
    """Get uptime as boot timestamp from coordinator data."""
    if data and data.system:
        uptime_seconds = getattr(data.system, "uptime_seconds", None)
        if uptime_seconds is not None:
            return datetime.now().astimezone() - timedelta(seconds=uptime_seconds)
    return None


def _get_uptime_attrs(data: UnraidData) -> dict[str, Any]:
    """Get uptime extra state attributes."""
    if not data or not data.system:
        return {}

    system = data.system
    uptime_seconds = getattr(system, "uptime_seconds", None)

    attrs: dict[str, Any] = {}
    _add_attr_if_set(attrs, "hostname", getattr(system, "hostname", None))
    _add_attr_if_set(attrs, "version", getattr(system, "version", None))

    if uptime_seconds is not None:
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        attrs["uptime_days"] = days
        attrs["uptime_hours"] = hours
        attrs["uptime_minutes"] = minutes
        attrs["uptime_total_seconds"] = uptime_seconds

    return attrs


# =============================================================================
# Value Functions for Array Sensors
# =============================================================================


def _get_array_usage(data: UnraidData) -> float | None:
    """Get array usage from coordinator data."""
    if data and data.array:
        used_percent = getattr(data.array, "used_percent", None)
        if used_percent is not None:
            return round(used_percent, 1)
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
# Value Functions for GPU Sensors
# =============================================================================


def _get_gpu_utilization(data: UnraidData) -> float | None:
    """Get GPU utilization from coordinator data."""
    if data and data.gpu and len(data.gpu) > 0:
        return getattr(data.gpu[0], "utilization_gpu_percent", None)
    return None


def _get_gpu_attrs(data: UnraidData) -> dict[str, Any]:
    """Get GPU extra state attributes."""
    if not data or not data.gpu or len(data.gpu) == 0:
        return {}

    gpu = data.gpu[0]
    attrs: dict[str, Any] = {}
    _add_attr_if_set(attrs, ATTR_GPU_NAME, getattr(gpu, "name", None))
    _add_attr_if_set(
        attrs, ATTR_GPU_DRIVER_VERSION, getattr(gpu, "driver_version", None)
    )
    return attrs


def _get_gpu_temperature(data: UnraidData) -> float | None:
    """Get GPU temperature from coordinator data."""
    if data and data.gpu and len(data.gpu) > 0:
        gpu = data.gpu[0]
        temp = getattr(gpu, "temperature_celsius", None)
        if temp is not None and temp > 0:
            return temp
        return getattr(gpu, "cpu_temperature_celsius", None)
    return None


def _get_gpu_power(data: UnraidData) -> float | None:
    """Get GPU power from coordinator data."""
    if data and data.gpu and len(data.gpu) > 0:
        return getattr(data.gpu[0], "power_draw_watts", None)
    return None


# =============================================================================
# Value Functions for UPS Sensors
# =============================================================================


def _get_ups_battery(data: UnraidData) -> float | None:
    """Get UPS battery level from coordinator data."""
    if data and data.ups:
        return getattr(data.ups, "battery_charge_percent", None)
    return None


def _get_ups_battery_attrs(data: UnraidData) -> dict[str, Any]:
    """Get UPS battery extra state attributes."""
    if not data or not data.ups:
        return {}

    ups = data.ups
    attrs: dict[str, Any] = {}
    _add_attr_if_set(attrs, ATTR_UPS_STATUS, getattr(ups, "status", None))
    _add_attr_if_set(attrs, ATTR_UPS_MODEL, getattr(ups, "model", None))
    return attrs


def _get_ups_load(data: UnraidData) -> float | None:
    """Get UPS load from coordinator data."""
    if data and data.ups:
        return getattr(data.ups, "load_percent", None)
    return None


def _get_ups_runtime(data: UnraidData) -> int | None:
    """Get UPS runtime in minutes from coordinator data."""
    if data and data.ups:
        ups = data.ups
        # Try to get runtime in seconds first
        runtime_seconds = getattr(ups, "runtime_left_seconds", None)
        if runtime_seconds is None:
            runtime_seconds = getattr(ups, "battery_runtime_seconds", None)
        if runtime_seconds is None:
            runtime_seconds = getattr(ups, "runtime_seconds", None)
        if runtime_seconds is not None:
            # Convert seconds to minutes
            return int(_coerce_number(runtime_seconds) / 60)
        # Fallback to runtime_minutes if available
        minutes = getattr(ups, "runtime_minutes", None)
        if minutes is not None:
            return int(_coerce_number(minutes))
    return None


def _get_ups_power(data: UnraidData) -> float | None:
    """Get UPS power from coordinator data."""
    if data and data.ups:
        return getattr(data.ups, "power_watts", None)
    return None


# =============================================================================
# Value Functions for Flash Drive Sensors
# =============================================================================


def _coerce_number(value: Any) -> float:
    """Coerce value to float for calculations; return 0.0 when invalid."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _get_flash_usage(data: UnraidData) -> float | None:
    """Get flash drive usage from coordinator data."""
    if data and data.flash_info:
        usage_percent = getattr(data.flash_info, "usage_percent", None)
        if isinstance(usage_percent, (int, float)):
            return round(float(usage_percent), 1)
        if isinstance(usage_percent, str):
            try:
                return round(float(usage_percent), 1)
            except ValueError:
                pass

        used = getattr(data.flash_info, "used_bytes", 0) or 0
        total = getattr(data.flash_info, "total_bytes", 0) or 0
        if not total:
            total = getattr(data.flash_info, "size_bytes", 0) or 0
        total_value = _coerce_number(total)
        used_value = _coerce_number(used)
        if total_value and total_value > 0:
            return round((used_value / total_value) * 100, 1)
    return None


def _get_flash_usage_attrs(data: UnraidData) -> dict[str, Any]:
    """Get flash drive usage extra state attributes."""
    if not data or not data.flash_info:
        return {}

    flash = data.flash_info
    attrs = {}

    total = getattr(flash, "total_bytes", 0) or 0
    if not total:
        total = getattr(flash, "size_bytes", 0) or 0
    used = getattr(flash, "used_bytes", 0) or 0
    free = getattr(flash, "free_bytes", 0) or 0

    if total:
        attrs["total_size"] = format_bytes(total)
    if used:
        attrs["used_size"] = format_bytes(used)
    if free:
        attrs["free_size"] = format_bytes(free)

    guid = getattr(flash, "guid", None)
    if guid:
        attrs["guid"] = guid

    product = getattr(flash, "product", None)
    if product:
        attrs["product"] = product

    vendor = getattr(flash, "vendor", None)
    if vendor:
        attrs["vendor"] = vendor

    return attrs


def _get_flash_free_space(data: UnraidData) -> int | None:
    """Get flash drive free space from coordinator data."""
    if data and data.flash_info:
        return getattr(data.flash_info, "free_bytes", None)
    return None


# =============================================================================
# Value Functions for Plugin Sensors
# =============================================================================


def _get_plugins_count(data: UnraidData) -> int | None:
    """Get plugins count from coordinator data."""
    if data and data.plugins:
        plugins = getattr(data.plugins, "plugins", None)
        if plugins is not None:
            return len(plugins)
        # Fallback to total_plugins field if available
        total = getattr(data.plugins, "total_plugins", None)
        if total is not None:
            return total
    return None


def _get_plugins_attrs(data: UnraidData) -> dict[str, Any]:
    """Get plugins extra state attributes."""
    if not data or not data.plugins:
        return {}

    plugins_list = getattr(data.plugins, "plugins", None) or []
    plugin_names = [getattr(p, "name", "unknown") for p in plugins_list]

    attrs = {
        "plugin_count": len(plugins_list),
        "plugin_names": plugin_names,
    }

    updates_available = getattr(data.plugins, "plugins_with_updates", None)
    if updates_available is None:
        updates_available = sum(
            1 for p in plugins_list if getattr(p, "update_available", False)
        )
    if updates_available > 0:
        attrs["updates_available"] = updates_available

    return attrs


def _get_latest_version(data: UnraidData) -> str | None:
    """Get latest Unraid version from coordinator data."""
    if not data:
        return None

    if data.update_status:
        latest = getattr(data.update_status, "latest_version", None)
        if latest:
            return latest
        current = getattr(data.update_status, "current_version", None)
        if current:
            return current

    if data.system:
        return getattr(data.system, "version", None)
    return None


def _get_latest_version_attrs(data: UnraidData) -> dict[str, Any]:
    """Get latest version extra state attributes."""
    if not data:
        return {}

    update = data.update_status
    current = getattr(update, "current_version", None) if update else None
    if not current and data.system:
        current = getattr(data.system, "version", None)
    latest = getattr(update, "latest_version", None) if update else None

    attrs = {}
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
        updates = getattr(data.plugins, "plugins_with_updates", None)
        if updates is not None:
            return len(updates) if isinstance(updates, list) else updates
        plugins_list = getattr(data.plugins, "plugins", None) or []
        if plugins_list:
            return sum(1 for p in plugins_list if getattr(p, "update_available", False))
        return 0
    return None


def _get_plugins_with_updates_attrs(data: UnraidData) -> dict[str, Any]:
    """Get plugins with updates extra state attributes."""
    if not data:
        return {}

    update = data.update_status
    plugins = getattr(update, "plugins_with_updates", []) if update else []
    plugins = plugins or []

    if isinstance(plugins, list) and plugins:
        return {"plugins_needing_update": plugins}

    if data.plugins:
        plugins_list = getattr(data.plugins, "plugins", None) or []
        needing_update = [
            getattr(p, "name", "unknown")
            for p in plugins_list
            if getattr(p, "update_available", False)
        ]
        if needing_update:
            return {"plugins_needing_update": needing_update}
    return {}


# =============================================================================
# Value Functions for Parity Schedule Sensors
# =============================================================================


def _compute_next_parity_check(schedule: Any) -> datetime | None:
    """Compute next parity check time from schedule fields."""
    if schedule is None:
        return None

    scheduled = getattr(schedule, "scheduled", None)
    if scheduled is False:
        return None

    mode = getattr(schedule, "mode", None)
    frequency = getattr(schedule, "frequency", None)
    frequency_value = str(mode or frequency).lower() if (mode or frequency) else None
    if not frequency_value:
        return None

    hour = getattr(schedule, "hour", None)
    if hour is None:
        return None

    minute = getattr(schedule, "minute", None)
    if minute is None:
        minute = 0

    hour_value = int(_coerce_number(hour))
    minute_value = int(_coerce_number(minute))
    now = datetime.now().astimezone()

    def _next_daily() -> datetime:
        candidate = now.replace(
            hour=hour_value, minute=minute_value, second=0, microsecond=0
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _next_weekly(day_value: int) -> datetime | None:
        if 0 <= day_value <= 6:
            target_weekday = (day_value - 1) % 7
        elif 1 <= day_value <= 7:
            target_weekday = (day_value - 2) % 7
        else:
            return None

        current_weekday = now.weekday()
        days_ahead = (target_weekday - current_weekday) % 7
        candidate = now.replace(
            hour=hour_value, minute=minute_value, second=0, microsecond=0
        ) + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    def _next_monthly(day_value: int) -> datetime | None:
        if day_value <= 0:
            return None

        last_day = calendar.monthrange(now.year, now.month)[1]
        candidate_day = min(day_value, last_day)
        candidate = now.replace(
            day=candidate_day,
            hour=hour_value,
            minute=minute_value,
            second=0,
            microsecond=0,
        )
        if candidate <= now:
            year = now.year + (1 if now.month == 12 else 0)
            month = 1 if now.month == 12 else now.month + 1
            last_day = calendar.monthrange(year, month)[1]
            candidate_day = min(day_value, last_day)
            candidate = now.replace(
                year=year,
                month=month,
                day=candidate_day,
                hour=hour_value,
                minute=minute_value,
                second=0,
                microsecond=0,
            )
        return candidate

    if frequency_value in {"daily", "day"}:
        return _next_daily()
    if frequency_value in {"weekly", "week"}:
        day = getattr(schedule, "day_of_week", None)
        if day is None:
            day = getattr(schedule, "day", None)
        if day is None:
            return None
        return _next_weekly(int(_coerce_number(day)))
    if frequency_value in {"monthly", "month"}:
        day = getattr(schedule, "day_of_month", None)
        if day is None:
            day = getattr(schedule, "day", None)
        if day is None:
            return None
        return _next_monthly(int(_coerce_number(day)))
    if frequency_value in {"yearly", "year"}:
        month = getattr(schedule, "month", None)
        if month is None:
            month = getattr(schedule, "day", None)
        if month is None:
            return None

        month_value = int(_coerce_number(month))
        if 0 <= month_value <= 11:
            month_value += 1
        if month_value <= 0 or month_value > 12:
            return None

        day = getattr(schedule, "day_of_month", None)
        if day is None:
            day = getattr(schedule, "day", None)
        if day is None:
            return None

        day_value = int(_coerce_number(day))
        if day_value <= 0:
            return None

        last_day = calendar.monthrange(now.year, month_value)[1]
        candidate_day = min(day_value, last_day)
        candidate = now.replace(
            month=month_value,
            day=candidate_day,
            hour=hour_value,
            minute=minute_value,
            second=0,
            microsecond=0,
        )
        if candidate <= now:
            last_day = calendar.monthrange(now.year + 1, month_value)[1]
            candidate_day = min(day_value, last_day)
            candidate = now.replace(
                year=now.year + 1,
                month=month_value,
                day=candidate_day,
                hour=hour_value,
                minute=minute_value,
                second=0,
                microsecond=0,
            )
        return candidate

    return None


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse timestamp values into timezone-aware datetimes."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).astimezone()
    if isinstance(value, str):
        try:
            value_str = value
            if value_str.endswith("Z"):
                value_str = f"{value_str[:-1]}+00:00"
            return datetime.fromisoformat(value_str).astimezone()
        except ValueError:
            return None
    return None


def _get_next_parity_check(data: UnraidData) -> datetime | None:
    """Get next parity check timestamp from coordinator data."""
    if data and data.parity_schedule:
        next_check = getattr(data.parity_schedule, "next_check", None)
        if next_check:
            parsed = _parse_timestamp(next_check)
            if parsed:
                return parsed
        return _compute_next_parity_check(data.parity_schedule)
    return None


def _get_next_parity_check_attrs(data: UnraidData) -> dict[str, Any]:
    """Get next parity check extra state attributes."""
    if not data or not data.parity_schedule:
        return {}

    schedule = data.parity_schedule
    attrs = {}

    scheduled = getattr(schedule, "scheduled", None)
    if scheduled is not None:
        attrs["scheduled"] = scheduled

    frequency = getattr(schedule, "frequency", None)
    if frequency:
        attrs["frequency"] = frequency

    day = getattr(schedule, "day", None)
    if day:
        attrs["day"] = day

    hour = getattr(schedule, "hour", None)
    if hour is not None:
        attrs["hour"] = hour

    return attrs


def _get_most_recent_parity_record(data: UnraidData) -> Any | None:
    """
    Get the most recent parity check record by date.

    The UMA API may return records in an arbitrary order (not sorted by date),
    so we need to sort them to find the most recent one.
    """
    records = (
        getattr(data.parity_history, "records", None)
        if data and data.parity_history
        else None
    )
    if not records or len(records) == 0:
        return None

    # Sort records by date descending to get most recent first
    try:
        sorted_records = sorted(
            records,
            key=lambda r: (
                _parse_timestamp(
                    getattr(r, "timestamp", None) or getattr(r, "date", None)
                )
                or datetime.min.replace(tzinfo=UTC)
            ),
            reverse=True,
        )
        return sorted_records[0] if sorted_records else None
    except (TypeError, ValueError):
        # If sorting fails, fall back to first record
        return records[0]


def _get_last_parity_check(data: UnraidData) -> datetime | None:
    """Get last parity check timestamp from coordinator data."""
    last = _get_most_recent_parity_record(data)
    if last:
        timestamp = getattr(last, "timestamp", None) or getattr(last, "date", None)
        if timestamp:
            return _parse_timestamp(timestamp)
    return None


def _get_last_parity_check_attrs(data: UnraidData) -> dict[str, Any]:
    """Get last parity check extra state attributes."""
    last = _get_most_recent_parity_record(data)
    if not last:
        return {}

    attrs = {}

    errors = getattr(last, "errors", None)
    if errors is not None:
        attrs["errors"] = errors

    duration = getattr(last, "duration_seconds", None) or getattr(
        last, "duration", None
    )
    if duration:
        attrs["last_duration"] = format_duration(duration)

    result = getattr(last, "result", None) or getattr(last, "status", None)
    if result:
        attrs["result"] = result

    return attrs


def _get_last_parity_errors(data: UnraidData) -> int | None:
    """Get last parity check error count from coordinator data."""
    last = _get_most_recent_parity_record(data)
    if last:
        return getattr(last, "errors", 0) or 0
    return None


# =============================================================================
# Value Functions for Notification Sensor
# =============================================================================


def _get_notifications_count(data: UnraidData) -> int | None:
    """Get unread notifications count from coordinator data."""
    if data and data.notifications is not None:
        unread = getattr(data.notifications, "unread_count", None)
        if unread is not None:
            return unread
        notif_list = getattr(data.notifications, "notifications", []) or []
        return len(notif_list)
    return None


def _get_notifications_attrs(data: UnraidData) -> dict[str, Any]:
    """Get notifications extra state attributes."""
    if not data or data.notifications is None:
        return {}

    notifications = data.notifications
    attrs = {}

    total = getattr(notifications, "total_count", None)
    if total is not None:
        attrs["total_count"] = total

    notif_list = getattr(notifications, "notifications", []) or []
    if notif_list:
        recent = []
        for notif in notif_list[:5]:
            subject = getattr(notif, "subject", None)
            importance = getattr(notif, "importance", None)
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

    vdisk = next(
        (d for d in data.disks if getattr(d, "role", "") == "docker_vdisk"), None
    )
    if vdisk:
        used = getattr(vdisk, "used_bytes", 0) or 0
        total = getattr(vdisk, "total_bytes", 0) or 0
        free = getattr(vdisk, "free_bytes", 0) or 0
        # Calculate total from used + free if total_bytes is not available
        if total == 0 and (used > 0 or free > 0):
            total = used + free
        if total > 0:
            return round((used / total) * 100, 1)
    return None


def _get_docker_vdisk_attrs(data: UnraidData) -> dict[str, Any]:
    """Get Docker vDisk extra state attributes."""
    if not data or not data.disks:
        return {}

    vdisk = next(
        (d for d in data.disks if getattr(d, "role", "") == "docker_vdisk"), None
    )
    if not vdisk:
        return {}

    total = getattr(vdisk, "total_bytes", 0) or 0
    used = getattr(vdisk, "used_bytes", 0) or 0
    free = getattr(vdisk, "free_bytes", 0) or 0
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

    log_fs = next((d for d in data.disks if getattr(d, "role", "") == "log"), None)
    if log_fs:
        used = getattr(log_fs, "used_bytes", 0) or 0
        total = getattr(log_fs, "total_bytes", 0) or 0
        free = getattr(log_fs, "free_bytes", 0) or 0
        # Calculate total from used + free if total_bytes is not available
        if total == 0 and (used > 0 or free > 0):
            total = used + free
        if total > 0:
            return round((used / total) * 100, 1)
    return None


def _get_log_filesystem_attrs(data: UnraidData) -> dict[str, Any]:
    """Get log filesystem extra state attributes."""
    if not data or not data.disks:
        return {}

    log_fs = next((d for d in data.disks if getattr(d, "role", "") == "log"), None)
    if not log_fs:
        return {}

    total = getattr(log_fs, "total_bytes", 0) or 0
    used = getattr(log_fs, "used_bytes", 0) or 0
    free = getattr(log_fs, "free_bytes", 0) or 0
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
        return getattr(data.zfs_arc, "hit_ratio_percent", None)
    return None


def _get_zfs_arc_attrs(data: UnraidData) -> dict[str, Any]:
    """Get ZFS ARC extra state attributes."""
    if not data or not data.zfs_arc:
        return {}

    arc = data.zfs_arc
    attrs = {}

    size = getattr(arc, "size_bytes", None)
    if size:
        attrs["arc_size"] = format_bytes(size)

    target = getattr(arc, "target_size_bytes", None)
    if target:
        attrs["target_size"] = format_bytes(target)

    hits = getattr(arc, "hits", None)
    if hits is not None:
        attrs["hits"] = hits

    misses = getattr(arc, "misses", None)
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
            and getattr(data.system, "motherboard_temp_celsius", None) is not None
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
# Sensor Entity Descriptions - GPU Sensors
# =============================================================================

GPU_SENSOR_DESCRIPTIONS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="gpu_utilization",
        translation_key="gpu_utilization",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:expansion-card",
        suggested_display_precision=1,
        value_fn=_get_gpu_utilization,
        extra_state_attributes_fn=_get_gpu_attrs,
    ),
    UnraidSensorEntityDescription(
        key="gpu_temperature",
        translation_key="gpu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_get_gpu_temperature,
    ),
    UnraidSensorEntityDescription(
        key="gpu_power",
        translation_key="gpu_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_get_gpu_power,
    ),
    UnraidSensorEntityDescription(
        key="gpu_energy",
        translation_key="gpu_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda _: None,  # Handled by specialized entity class
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
            and getattr(data.parity_history, "records", None) is not None
            and len(data.parity_history.records) > 0
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
            and any(getattr(d, "role", "") == "docker_vdisk" for d in data.disks)
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
            and any(getattr(d, "role", "") == "log" for d in data.disks)
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
    ) -> None:
        """Initialize the sensor."""
        # Use fan name as stable key so entities don't shift when list order changes
        sanitized = fan_name.lower().replace(" ", "_")
        super().__init__(coordinator, f"fan_{sanitized}")
        self._entry = entry
        self._fan_name = fan_name
        self._attr_name = f"Fan {fan_name}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        sanitized = self._fan_name.lower().replace(" ", "_")
        return f"{self._entry.entry_id}_fan_{sanitized}"

    @property
    def native_value(self) -> int | None:
        """Return the fan speed."""
        data = self.coordinator.data
        if not data or not data.system:
            return None

        fans = getattr(data.system, "fans", []) or []
        for fan in fans:
            if isinstance(fan, dict):
                if fan.get("name") == self._fan_name:
                    return fan.get("rpm")
            elif getattr(fan, "name", None) == self._fan_name:
                return getattr(fan, "rpm", None)
        return None


class UnraidNetworkSensorBase(UnraidBaseEntity, SensorEntity):
    """Base class for network rate sensors with caching (PR #12 fix)."""

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
        self._entry = entry
        self._interface_name = interface_name
        self._direction = direction
        self._attr_name = f"Network {interface_name.upper()} {direction.upper()}"
        self._attr_icon = (
            "mdi:download-network" if direction == "rx" else "mdi:upload-network"
        )

        # PR #12 fix: Rate calculation with caching
        self._last_bytes: int | None = None
        self._last_update: datetime | None = None
        self._last_value: float = 0.0

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return (
            f"{self._entry.entry_id}_network_{self._interface_name}_{self._direction}"
        )

    def _get_interface(self) -> Any:
        """Get the network interface data."""
        data = self.coordinator.data
        if not data or not data.network:
            return None
        return next(
            (
                i
                for i in data.network
                if getattr(i, "name", None) == self._interface_name
            ),
            None,
        )

    def _get_bytes(self, interface) -> int | None:
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
        now = datetime.now()

        if current_bytes is not None and self._last_bytes is not None:
            time_diff = (
                (now - self._last_update).total_seconds() if self._last_update else 0
            )

            # PR #12 fix: Only recalculate if time >= 5 seconds and bytes changed
            if time_diff >= 5 and current_bytes != self._last_bytes:
                byte_diff = current_bytes - self._last_bytes
                if byte_diff >= 0:
                    self._last_value = (byte_diff / time_diff) * 8 / 1000
                self._last_bytes = current_bytes
                self._last_update = now
        elif current_bytes is not None:
            self._last_bytes = current_bytes
            self._last_update = now

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        """Return the calculated rate."""
        return self._last_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        interface = self._get_interface()
        if not interface:
            return {}

        attrs: dict[str, Any] = {}
        _add_attr_if_set(
            attrs, ATTR_NETWORK_MAC, getattr(interface, "mac_address", None)
        )
        _add_attr_if_set(attrs, ATTR_NETWORK_IP, getattr(interface, "ip_address", None))
        _add_attr_if_set(
            attrs, ATTR_NETWORK_SPEED, getattr(interface, "speed_mbps", None)
        )
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

    def _get_bytes(self, interface) -> int | None:
        """Get received bytes from interface."""
        return getattr(interface, "bytes_received", None)


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

    def _get_bytes(self, interface) -> int | None:
        """Get transmitted bytes from interface."""
        return getattr(interface, "bytes_sent", None)


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
        self._entry = entry
        self._disk_id = disk_id
        self._disk_name = disk_name

    def _get_disk(self) -> Any:
        """Get the disk data."""
        data = self.coordinator.data
        if not data or not data.disks:
            return None
        return next(
            (
                d
                for d in data.disks
                if getattr(d, "id", None) == self._disk_id
                or getattr(d, "name", None) == self._disk_id
            ),
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
        self._attr_name = f"Disk {disk_name} Usage"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_disk_{self._disk_id}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the disk usage percentage."""
        disk = self._get_disk()
        if not disk:
            return None

        used_percent = getattr(disk, "used_percent", None)
        if used_percent is None:
            used_percent = getattr(disk, "usage_percent", None)
        if isinstance(used_percent, (int, float)):
            return round(float(used_percent), 1)
        if isinstance(used_percent, str):
            try:
                return round(float(used_percent), 1)
            except ValueError:
                pass

        total = getattr(disk, "total_bytes", 0) or 0
        if not total:
            total = getattr(disk, "size_bytes", 0) or 0
        used = getattr(disk, "used_bytes", 0) or 0
        total_value = _coerce_number(total)
        used_value = _coerce_number(used)
        if total_value and total_value > 0:
            return round((used_value / total_value) * 100, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        disk = self._get_disk()
        if not disk:
            return {}

        total = getattr(disk, "total_bytes", 0) or 0
        if not total:
            total = getattr(disk, "size_bytes", 0) or 0
        used = getattr(disk, "used_bytes", 0) or 0
        free = getattr(disk, "free_bytes", 0) or 0

        attrs: dict[str, Any] = {
            "disk_name": self._disk_name,
        }
        _add_attr_if_set(attrs, "role", getattr(disk, "role", None))
        _add_attr_if_set(attrs, "status", getattr(disk, "status", None))

        if total:
            attrs["total_size"] = format_bytes(total)
        if used:
            attrs["used_size"] = format_bytes(used)
        if free:
            attrs["free_size"] = format_bytes(free)

        return attrs


class UnraidDiskHealthSensor(UnraidDiskSensorBase):
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
        self._attr_name = f"Disk {disk_name} Health"
        self._last_known_health: str | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_disk_{self._disk_id}_health"

    def _is_standby(self, disk: Any) -> bool:
        """Return true if the disk is in standby mode."""
        spin_state = getattr(disk, "spin_state", None)
        return spin_state is not None and spin_state.lower() == "standby"

    @property
    def native_value(self) -> str | None:
        """Return the disk health status."""
        disk = self._get_disk()
        if not disk:
            return self._last_known_health

        health = getattr(disk, "smart_status", None) or getattr(disk, "status", None)

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
        _add_attr_if_set(attrs, "device", getattr(disk, "device", None))
        _add_attr_if_set(attrs, "model", getattr(disk, "model", None))
        _add_attr_if_set(attrs, "serial", getattr(disk, "serial_number", None))

        spin_state = getattr(disk, "spin_state", None)
        if spin_state is not None:
            attrs["spin_state"] = spin_state

        health = getattr(disk, "smart_status", None) or getattr(disk, "status", None)
        if health is None and self._is_standby(disk) and self._last_known_health:
            attrs["cached_value"] = True

        temp = getattr(disk, "temperature_celsius", None)
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
        self._attr_name = f"Disk {disk_name} Temperature"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_disk_{self._disk_id}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the disk temperature in Celsius."""
        disk = self._get_disk()
        if not disk:
            return None
        temp = getattr(disk, "temperature_celsius", None)
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
        _add_attr_if_set(attrs, "device", getattr(disk, "device", None))
        _add_attr_if_set(attrs, "model", getattr(disk, "model", None))
        _add_attr_if_set(attrs, "role", getattr(disk, "role", None))

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
        self._entry = entry
        self._share_name = share_name
        self._attr_name = f"Share {share_name} Usage"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_share_{self._share_name}_usage"

    def _get_share(self) -> Any:
        """Get the share data."""
        data = self.coordinator.data
        if not data or not data.shares:
            return None
        return next(
            (s for s in data.shares if getattr(s, "name", None) == self._share_name),
            None,
        )

    @property
    def native_value(self) -> float | None:
        """Return the share usage percentage."""
        share = self._get_share()
        if not share:
            return None

        used_percent = getattr(share, "used_percent", None)
        if used_percent is not None:
            return round(used_percent, 1)

        total = getattr(share, "total_bytes", 0) or 0
        used = getattr(share, "used_bytes", 0) or 0
        if total > 0:
            return round((used / total) * 100, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        share = self._get_share()
        if not share:
            return {}

        total = getattr(share, "total_bytes", 0) or 0
        used = getattr(share, "used_bytes", 0) or 0
        free = getattr(share, "free_bytes", 0) or 0

        attrs = {
            "share_name": self._share_name,
        }

        if total:
            attrs["total_size"] = format_bytes(total)
        if used:
            attrs["used_size"] = format_bytes(used)
        if free:
            attrs["free_size"] = format_bytes(free)

        # Cache configuration attributes (from uma-api#33)
        use_cache = getattr(share, "use_cache", None)
        if use_cache:
            attrs["use_cache"] = use_cache

        cache_pool = getattr(share, "cache_pool", None)
        if cache_pool:
            attrs["cache_pool"] = cache_pool

        mover_action = getattr(share, "mover_action", None)
        if mover_action:
            attrs["mover_action"] = mover_action

        split_level = getattr(share, "split_level", None)
        if split_level is not None:
            attrs["split_level"] = split_level

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
        self._entry = entry
        self._pool_name = pool_name

    def _get_pool(self) -> Any:
        """Get the ZFS pool data."""
        data = self.coordinator.data
        if not data or not data.zfs_pools:
            return None
        return next(
            (p for p in data.zfs_pools if getattr(p, "name", None) == self._pool_name),
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
        self._attr_name = f"ZFS Pool {pool_name} Usage"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_zfs_{self._pool_name}_usage"

    @property
    def native_value(self) -> float | None:
        """Return the pool usage percentage."""
        pool = self._get_pool()
        if not pool:
            return None

        used_percent = getattr(pool, "used_percent", None)
        if used_percent is not None:
            return round(used_percent, 1)

        total = getattr(pool, "size_bytes", 0) or 0
        used = getattr(pool, "used_bytes", 0) or 0
        if total > 0:
            return round((used / total) * 100, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        pool = self._get_pool()
        if not pool:
            return {}

        total = getattr(pool, "size_bytes", 0) or 0
        used = getattr(pool, "used_bytes", 0) or 0
        free = getattr(pool, "free_bytes", 0) or 0

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
        self._attr_name = f"ZFS Pool {pool_name} Health"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_zfs_{self._pool_name}_health"

    @property
    def native_value(self) -> str | None:
        """Return the pool health status."""
        pool = self._get_pool()
        if not pool:
            return None
        return getattr(pool, "health", None) or getattr(pool, "state", None)

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
        self._entry = entry
        self._attr_translation_key = "ups_energy"
        self._total_energy: float = 0.0
        self._last_update: datetime | None = None
        self._last_power: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    self._total_energy = float(last_state.state)
                except (ValueError, TypeError):
                    self._total_energy = 0.0

            # Restore last update time from attributes if available
            if last_state.attributes.get("last_reset"):
                try:
                    self._last_update = datetime.fromisoformat(
                        str(last_state.attributes["last_reset"])
                    )
                except (ValueError, TypeError):
                    self._last_update = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_energy()
        self.async_write_ha_state()

    def _update_energy(self) -> None:
        """Calculate and update energy based on current power reading."""
        if not self.coordinator.data or not self.coordinator.data.ups:
            return

        ups = self.coordinator.data.ups
        current_power = getattr(ups, "power_watts", None)

        if current_power is None or current_power < 0:
            return

        now = datetime.now(UTC)

        if self._last_update is not None and self._last_power is not None:
            # Calculate time delta in hours
            time_delta = (now - self._last_update).total_seconds() / 3600

            # Sanity check: only calculate if time delta is reasonable (< 1 hour)
            # This prevents huge jumps after restarts or long unavailability
            if 0 < time_delta < 1:
                # Use trapezoidal integration (average of last and current power)
                avg_power = (self._last_power + current_power) / 2
                # Energy (kWh) = Power (W) * Time (h) / 1000
                energy_increment = (avg_power * time_delta) / 1000
                self._total_energy += energy_increment

        self._last_update = now
        self._last_power = current_power

    @property
    def native_value(self) -> float:
        """Return the total energy consumed in kWh."""
        return round(self._total_energy, 3)

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

        if self._last_update:
            attrs["last_reset"] = self._last_update.isoformat()

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
    ) -> None:
        """Initialize the GPU energy sensor."""
        super().__init__(coordinator, "gpu_energy")
        self._entry = entry
        self._attr_translation_key = "gpu_energy"
        self._total_energy: float = 0.0
        self._last_update: datetime | None = None
        self._last_power: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    self._total_energy = float(last_state.state)
                except (ValueError, TypeError):
                    self._total_energy = 0.0

            # Restore last update time from attributes if available
            if last_state.attributes.get("last_reset"):
                try:
                    self._last_update = datetime.fromisoformat(
                        str(last_state.attributes["last_reset"])
                    )
                except (ValueError, TypeError):
                    self._last_update = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_energy()
        self.async_write_ha_state()

    def _update_energy(self) -> None:
        """Calculate and update energy based on current power reading."""
        if not self.coordinator.data or not self.coordinator.data.gpu:
            return

        gpu_list = self.coordinator.data.gpu
        if not gpu_list or len(gpu_list) == 0:
            return

        current_power = getattr(gpu_list[0], "power_draw_watts", None)

        if current_power is None or current_power < 0:
            return

        now = datetime.now(UTC)

        if self._last_update is not None and self._last_power is not None:
            # Calculate time delta in hours
            time_delta = (now - self._last_update).total_seconds() / 3600

            # Sanity check: only calculate if time delta is reasonable (< 1 hour)
            # This prevents huge jumps after restarts or long unavailability
            if 0 < time_delta < 1:
                # Use trapezoidal integration (average of last and current power)
                avg_power = (self._last_power + current_power) / 2
                # Energy (kWh) = Power (W) * Time (h) / 1000
                energy_increment = (avg_power * time_delta) / 1000
                self._total_energy += energy_increment

        self._last_update = now
        self._last_power = current_power

    @property
    def native_value(self) -> float:
        """Return the total energy consumed in kWh."""
        return round(self._total_energy, 3)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if not self.coordinator.data:
            return False
        gpu = self.coordinator.data.gpu
        return gpu is not None and len(gpu) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}

        if self._last_update:
            attrs["last_reset"] = self._last_update.isoformat()

        if self._last_power is not None:
            attrs["current_power_watts"] = self._last_power

        return attrs


# =============================================================================
# Helper Functions
# =============================================================================


def _is_physical_network_interface(interface_name: str) -> bool:
    """Check if the network interface is a physical interface or main bridge."""
    physical_patterns = [
        r"^eth\d+$",
        r"^wlan\d+$",
        r"^bond\d+$",
        r"^eno\d+$",
        r"^enp\d+s\d+$",
        r"^br0$",  # Main network bridge on Unraid
    ]
    for pattern in physical_patterns:
        if re.match(pattern, interface_name):
            return True
    return False


def _is_physical_disk(disk) -> bool:
    """Check if disk is a physical, installed disk."""
    role = getattr(disk, "role", "")
    status = getattr(disk, "status", "")
    device = getattr(disk, "device", "")

    if role in ("docker_vdisk", "log"):
        return False
    if status == "DISK_NP_DSBL":
        return False
    return bool(device)


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

    # Array sensors
    for description in ARRAY_SENSOR_DESCRIPTIONS:
        entities.append(UnraidSensorEntity(coordinator, description))

    # Fan sensors (dynamic, one per fan, keyed by name for stability)
    if data and data.system:
        fans = getattr(data.system, "fans", []) or []
        seen_names: set[str] = set()
        for idx, fan in enumerate(fans):
            if isinstance(fan, dict):
                fan_name = fan.get("name") or f"fan_{idx}"
            else:
                fan_name = getattr(fan, "name", None) or f"fan_{idx}"
            # Ensure uniqueness in case of duplicate names
            if fan_name in seen_names:
                fan_name = f"{fan_name}_{idx}"
            seen_names.add(fan_name)
            entities.append(UnraidFanSensor(coordinator, entry, fan_name))

    # GPU sensors - only if gpu collector is enabled
    if coordinator.is_collector_enabled("gpu") and data and data.gpu:
        for description in GPU_SENSOR_DESCRIPTIONS:
            # Skip gpu_energy - it uses a specialized entity class
            if description.key == "gpu_energy":
                continue
            entities.append(UnraidSensorEntity(coordinator, description))

        # Add GPU Energy sensor (uses specialized class for state restoration)
        entities.append(UnraidGPUEnergySensor(coordinator, entry))

    # UPS sensors - only if ups collector is enabled
    if (
        coordinator.is_collector_enabled("ups")
        and data
        and data.ups
        and getattr(data.ups, "status", None) is not None
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
        physical_disks = [d for d in (disks or []) if _is_physical_disk(d)]

        for disk in physical_disks:
            disk_id = getattr(disk, "id", None) or getattr(disk, "name", "unknown")
            disk_name = getattr(disk, "name", disk_id)
            disk_role = getattr(disk, "role", "")

            entities.append(
                UnraidDiskHealthSensor(coordinator, entry, disk_id, disk_name)
            )

            # Temperature sensor (disabled by default)
            entities.append(
                UnraidDiskTemperatureSensor(coordinator, entry, disk_id, disk_name)
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

    _LOGGER.debug("Adding %d Unraid sensor entities", len(entities))
    async_add_entities(entities)
