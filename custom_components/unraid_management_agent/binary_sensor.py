"""Binary sensor platform for Unraid Management Agent."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .const import ATTR_PARITY_CHECK_STATUS
from .entity import UnraidBaseEntity, UnraidEntityDescription

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class UnraidBinarySensorEntityDescription(
    UnraidEntityDescription,
    BinarySensorEntityDescription,
):
    """Description for Unraid binary sensor entities."""

    is_on_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: False
    extra_state_attributes_fn: (
        Callable[[UnraidDataUpdateCoordinator], dict[str, Any]] | None
    ) = None


def _is_array_started(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if array is started."""
    data = coordinator.data
    if data and data.array:
        state = getattr(data.array, "state", "").lower()
        return state == "started"
    return False


def _is_parity_check_running(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if parity check is running."""
    data = coordinator.data
    if not data or not data.array:
        return False
    parity_status = getattr(data.array, "parity_check_status", None)
    if parity_status:
        status = getattr(parity_status, "status", "").lower()
        return status in ("running", "paused", "checking")
    return False


def _parity_check_attributes(
    coordinator: UnraidDataUpdateCoordinator,
) -> dict[str, Any]:
    """Return parity check attributes."""
    data = coordinator.data
    if not data or not data.array:
        return {}
    parity_status = getattr(data.array, "parity_check_status", None)
    if not parity_status:
        return {}
    status = getattr(parity_status, "status", None)
    return {
        ATTR_PARITY_CHECK_STATUS: status,
        "is_paused": status.lower() == "paused" if status else False,
    }


def _is_parity_invalid(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if parity is invalid (PROBLEM device class: ON=problem)."""
    data = coordinator.data
    if data and data.array:
        parity_valid = getattr(data.array, "parity_valid", True)
        return not parity_valid
    return False


def _is_ups_connected(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if UPS is connected (has valid status)."""
    data = coordinator.data
    if data and data.ups:
        # UPS is considered connected if it has a status
        status = getattr(data.ups, "status", None)
        return status is not None and status != ""
    return False


def _has_ups(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if UPS data is available."""
    data = coordinator.data
    return data is not None and data.ups is not None


def _is_zfs_available(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if ZFS is available."""
    data = coordinator.data
    return data is not None and data.zfs_pools is not None and len(data.zfs_pools) > 0


def _has_zfs(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if ZFS pools exist."""
    data = coordinator.data
    return data is not None and data.zfs_pools is not None and len(data.zfs_pools) > 0


def _zfs_attributes(coordinator: UnraidDataUpdateCoordinator) -> dict[str, Any]:
    """Return ZFS attributes."""
    data = coordinator.data
    if not data or not data.zfs_pools:
        return {"pool_count": 0}
    return {"pool_count": len(data.zfs_pools)}


# =============================================================================
# Update Availability Functions (#19)
# =============================================================================


def _is_update_available(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if Unraid OS update is available."""
    data = coordinator.data
    if data and data.update_status:
        return getattr(data.update_status, "os_update_available", False)
    return False


def _has_update_status(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if update status data is available."""
    data = coordinator.data
    return data is not None and data.update_status is not None


def _update_attributes(coordinator: UnraidDataUpdateCoordinator) -> dict[str, Any]:
    """Return update status attributes."""
    data = coordinator.data
    if not data or not data.update_status:
        return {}
    update = data.update_status
    return {
        "current_version": getattr(update, "current_version", None),
        "plugin_updates_count": getattr(update, "plugin_updates_count", 0),
    }


# =============================================================================
# Flash Drive Health Functions (#20)
# =============================================================================


def _is_flash_healthy(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if flash drive is healthy (not a problem)."""
    data = coordinator.data
    if not data or not data.flash_info:
        return True  # Assume healthy if no data

    flash = data.flash_info
    # Check if SMART is available and healthy
    smart_available = getattr(flash, "smart_available", None)
    if smart_available is False:
        # No SMART support, can't determine health
        return True

    # Check usage - warn if > 90%
    usage = getattr(flash, "usage_percent", 0) or 0
    return usage <= 90


def _has_flash_info(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if flash drive info is available."""
    data = coordinator.data
    return data is not None and data.flash_info is not None


def _flash_attributes(coordinator: UnraidDataUpdateCoordinator) -> dict[str, Any]:
    """Return flash drive attributes."""
    data = coordinator.data
    if not data or not data.flash_info:
        return {}

    flash = data.flash_info
    return {
        "usage_percent": getattr(flash, "usage_percent", None),
        "smart_available": getattr(flash, "smart_available", None),
        "model": getattr(flash, "model", None),
    }


# =============================================================================
# Mover Functions (#17)
# =============================================================================


def _is_mover_running(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if mover is currently running."""
    data = coordinator.data
    if data and data.mover_settings:
        active = getattr(data.mover_settings, "active", False)
        return active is True
    return False


def _has_mover_settings(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if mover settings are available."""
    data = coordinator.data
    return data is not None and data.mover_settings is not None


def _mover_attributes(coordinator: UnraidDataUpdateCoordinator) -> dict[str, Any]:
    """Return mover attributes."""
    data = coordinator.data
    if not data or not data.mover_settings:
        return {}

    mover = data.mover_settings
    return {
        "schedule": getattr(mover, "schedule", None),
        "logging": getattr(mover, "logging", None),
    }


# =============================================================================
# Parity Check Scheduled Functions (#16)
# =============================================================================


def _is_parity_check_scheduled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if parity check is scheduled."""
    data = coordinator.data
    if data and data.parity_schedule:
        mode = getattr(data.parity_schedule, "mode", None)
        return mode is not None and mode != "disabled"
    return False


def _has_parity_schedule(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if parity schedule data is available."""
    data = coordinator.data
    return data is not None and data.parity_schedule is not None


def _parity_schedule_attributes(
    coordinator: UnraidDataUpdateCoordinator,
) -> dict[str, Any]:
    """Return parity schedule attributes."""
    data = coordinator.data
    if not data or not data.parity_schedule:
        return {}

    schedule = data.parity_schedule
    return {
        "mode": getattr(schedule, "mode", None),
        "day": getattr(schedule, "day", None),
        "hour": getattr(schedule, "hour", None),
        "correcting": getattr(schedule, "correcting", False),
    }


BINARY_SENSOR_DESCRIPTIONS: tuple[UnraidBinarySensorEntityDescription, ...] = (
    UnraidBinarySensorEntityDescription(
        key="array_started",
        translation_key="array_started",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_array_started,
    ),
    UnraidBinarySensorEntityDescription(
        key="parity_check_running",
        translation_key="parity_check_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:shield-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_parity_check_running,
        extra_state_attributes_fn=_parity_check_attributes,
    ),
    UnraidBinarySensorEntityDescription(
        key="parity_valid",
        translation_key="parity_valid",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:shield-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_parity_invalid,
    ),
    UnraidBinarySensorEntityDescription(
        key="ups_connected",
        translation_key="ups_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_ups_connected,
        supported_fn=_has_ups,
    ),
    UnraidBinarySensorEntityDescription(
        key="zfs_available",
        translation_key="zfs_available",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:database",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_zfs_available,
        supported_fn=_has_zfs,
        extra_state_attributes_fn=_zfs_attributes,
    ),
    # Update availability (#19)
    UnraidBinarySensorEntityDescription(
        key="update_available",
        translation_key="update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        icon="mdi:update",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_update_available,
        supported_fn=_has_update_status,
        extra_state_attributes_fn=_update_attributes,
    ),
    # Flash drive health (#20)
    UnraidBinarySensorEntityDescription(
        key="flash_healthy",
        translation_key="flash_healthy",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:usb-flash-drive",
        entity_category=EntityCategory.DIAGNOSTIC,
        # is_on returns True when there's a problem (usage > 90%)
        is_on_fn=lambda c: not _is_flash_healthy(c),
        supported_fn=_has_flash_info,
        extra_state_attributes_fn=_flash_attributes,
    ),
    # Mover running (#17)
    UnraidBinarySensorEntityDescription(
        key="mover_running",
        translation_key="mover_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:transfer",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_mover_running,
        supported_fn=_has_mover_settings,
        extra_state_attributes_fn=_mover_attributes,
    ),
    # Parity check scheduled (#16)
    UnraidBinarySensorEntityDescription(
        key="parity_check_scheduled",
        translation_key="parity_check_scheduled",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:calendar-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_parity_check_scheduled,
        supported_fn=_has_parity_schedule,
        extra_state_attributes_fn=_parity_schedule_attributes,
    ),
)


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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid binary sensor entities."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    entities: list[BinarySensorEntity] = []

    # Add binary sensors based on descriptions and their supported_fn
    for description in BINARY_SENSOR_DESCRIPTIONS:
        # Check if the sensor should be created based on collector status
        if description.key == "ups_connected" and not coordinator.is_collector_enabled(
            "ups"
        ):
            # UPS sensor - only if ups collector is enabled
            continue
        if description.key == "zfs_available" and not coordinator.is_collector_enabled(
            "zfs"
        ):
            # ZFS sensor - only if zfs collector is enabled
            continue

        # Check if supported by the supported_fn
        if description.supported_fn(coordinator):
            entities.append(UnraidBinarySensorEntity(coordinator, description))

    # Network interface binary sensors - only if network collector is enabled
    if coordinator.is_collector_enabled("network"):
        for interface in (data.network if data else []) or []:
            interface_name = getattr(interface, "name", "unknown")
            if _is_physical_network_interface(interface_name):
                entities.append(
                    UnraidNetworkInterfaceBinarySensor(coordinator, interface_name)
                )

    _LOGGER.debug("Adding %d Unraid binary sensor entities", len(entities))
    async_add_entities(entities)


class UnraidBinarySensorEntity(UnraidBaseEntity, BinarySensorEntity):
    """Unraid binary sensor entity."""

    entity_description: UnraidBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entity_description: UnraidBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.entity_description.extra_state_attributes_fn is not None:
            return self.entity_description.extra_state_attributes_fn(self.coordinator)
        return {}


class UnraidNetworkInterfaceBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """Network interface up/down binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:ethernet"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        interface_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        self._interface_name = interface_name
        super().__init__(coordinator, f"network_{interface_name}")
        self._attr_translation_key = "network_interface"
        self._attr_translation_placeholders = {"interface": interface_name}

    @property
    def is_on(self) -> bool:
        """Return true if interface is up."""
        data = self.coordinator.data
        if not data or not data.network:
            return False

        for interface in data.network:
            if getattr(interface, "name", "") == self._interface_name:
                state = getattr(interface, "state", "down")
                return state == "up"
        return False
