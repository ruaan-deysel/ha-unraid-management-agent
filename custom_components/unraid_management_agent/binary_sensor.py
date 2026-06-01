"""Binary sensor platform for Unraid Management Agent."""

from __future__ import annotations

import logging
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
from homeassistant.util import slugify

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
    return getattr(data.array, "is_parity_check_running", False)


def _parity_check_attributes(
    coordinator: UnraidDataUpdateCoordinator,
) -> dict[str, Any]:
    """Return parity check attributes."""
    data = coordinator.data
    if not data or not data.array:
        return {}
    parity_status = getattr(data.array, "parity_check_status", None)
    status = (
        parity_status
        if isinstance(parity_status, str)
        else getattr(parity_status, "status", None)
    )
    if status is None:
        sync_action = getattr(data.array, "sync_action", None)
        status = sync_action if isinstance(sync_action, str) else None
    if status is None:
        return {}
    return {
        ATTR_PARITY_CHECK_STATUS: status,
        "is_paused": status.lower() == "paused",
    }


def _has_parity_disks(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if the array has parity disks configured."""
    data = coordinator.data
    if not data or not data.array:
        return False
    num_parity = getattr(data.array, "num_parity_disks", None)
    return num_parity is not None and num_parity > 0


def _is_parity_invalid(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if parity is invalid (PROBLEM device class: ON=problem)."""
    data = coordinator.data
    if data and data.array:
        parity_valid = getattr(data.array, "parity_valid", None)
        # Only report invalid when explicitly False (not None/missing)
        return parity_valid is False
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
    return getattr(data.flash_info, "is_healthy", True)


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
        return getattr(data.parity_schedule, "is_enabled", False)
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
        "correcting": getattr(schedule, "correcting", None),
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
        supported_fn=_has_parity_disks,
    ),
    UnraidBinarySensorEntityDescription(
        key="parity_valid",
        translation_key="parity_valid",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:shield-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_parity_invalid,
        supported_fn=_has_parity_disks,
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
            if getattr(interface, "is_physical", False):
                entities.append(
                    UnraidNetworkInterfaceBinarySensor(coordinator, interface_name)
                )

    # Unassigned device mounted binary sensors
    if data and data.unassigned_devices:
        seen_unassigned: set[str] = set()
        for device in data.unassigned_devices:
            device_name = getattr(device, "name", None) or getattr(
                device, "device", None
            )
            if device_name and device_name not in seen_unassigned:
                seen_unassigned.add(device_name)
                entities.append(
                    UnraidUnassignedDeviceBinarySensor(coordinator, device_name)
                )

    # Remote share mounted binary sensors
    if data and data.remote_shares:
        seen_remote_shares: set[str] = set()
        for remote_share in data.remote_shares:
            share_name = getattr(remote_share, "name", None)
            if share_name and share_name not in seen_remote_shares:
                seen_remote_shares.add(share_name)
                entities.append(UnraidRemoteShareBinarySensor(coordinator, share_name))

    # Network service binary sensors
    if data and data.network_services:
        # Iterate over known service fields on NetworkServicesStatus
        service_fields = (
            "smb",
            "nfs",
            "afp",
            "ftp",
            "ssh",
            "telnet",
            "avahi",
            "netbios",
            "wsd",
            "wireguard",
            "upnp",
            "ntp",
            "syslog",
        )
        for service_key in service_fields:
            service_info = getattr(data.network_services, service_key, None)
            if service_info is not None:
                service_name = getattr(service_info, "name", None) or service_key
                entities.append(
                    UnraidNetworkServiceBinarySensor(
                        coordinator, service_key, service_name
                    )
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


class UnraidNetworkServiceBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """Network service running binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:server-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        service_key: str,
        service_name: str,
    ) -> None:
        """Initialize the network service binary sensor."""
        self._service_key = service_key
        self._service_name = service_name
        safe_key = slugify(service_key)
        super().__init__(coordinator, f"network_service_{safe_key}")
        self._attr_translation_key = "network_service"
        self._attr_translation_placeholders = {"service_name": service_name}

    def _get_service_info(self) -> Any | None:
        """Get the service info from coordinator data."""
        data = self.coordinator.data
        if not data or not data.network_services:
            return None
        return getattr(data.network_services, self._service_key, None)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._get_service_info() is not None

    @property
    def is_on(self) -> bool:
        """Return true if the service is running."""
        service_info = self._get_service_info()
        if service_info is None:
            return False
        return getattr(service_info, "running", False) is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        service_info = self._get_service_info()
        if service_info is None:
            return {}
        return {
            "enabled": getattr(service_info, "enabled", None),
            "port": getattr(service_info, "port", None),
        }


class UnraidUnassignedDeviceBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """Mounted status binary sensor for an unassigned device."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:harddisk"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize the unassigned device binary sensor."""
        self._device_name = device_name
        super().__init__(
            coordinator, f"unassigned_device_{slugify(device_name)}_mounted"
        )
        self._attr_translation_key = "unassigned_device_mounted"
        self._attr_translation_placeholders = {"device_name": device_name}

    def _get_device(self) -> Any | None:
        """Return the device data from coordinator."""
        data = self.coordinator.data
        if not data or not data.unassigned_devices:
            return None
        for dev in data.unassigned_devices:
            name = getattr(dev, "name", None) or getattr(dev, "device", None)
            if name == self._device_name:
                return dev
        return None

    @property
    def available(self) -> bool:
        """Return True if the device is present in coordinator data."""
        return super().available and self._get_device() is not None

    @property
    def is_on(self) -> bool:
        """Return True if the device is mounted."""
        device = self._get_device()
        if device is None:
            return False
        return getattr(device, "mounted", False) is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        device = self._get_device()
        if device is None:
            return {}
        attrs: dict[str, Any] = {}
        if getattr(device, "device", None):
            attrs["device_path"] = device.device
        if getattr(device, "filesystem", None):
            attrs["filesystem"] = device.filesystem
        if getattr(device, "size_bytes", None) is not None:
            from .api.formatting import format_bytes

            attrs["size"] = format_bytes(device.size_bytes)
        return attrs


class UnraidRemoteShareBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """Mounted status binary sensor for a remote share."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:folder-network"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        share_name: str,
    ) -> None:
        """Initialize the remote share binary sensor."""
        self._share_name = share_name
        super().__init__(coordinator, f"remote_share_{slugify(share_name)}_mounted")
        self._attr_translation_key = "remote_share_mounted"
        self._attr_translation_placeholders = {"share_name": share_name}

    def _get_share(self) -> Any | None:
        """Return the remote share data from coordinator."""
        data = self.coordinator.data
        if not data or not data.remote_shares:
            return None
        for share in data.remote_shares:
            if getattr(share, "name", None) == self._share_name:
                return share
        return None

    @property
    def available(self) -> bool:
        """Return True if the share is present in coordinator data."""
        return super().available and self._get_share() is not None

    @property
    def is_on(self) -> bool:
        """Return True if the remote share is mounted."""
        share = self._get_share()
        if share is None:
            return False
        return getattr(share, "mounted", False) is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        share = self._get_share()
        if share is None:
            return {}
        attrs: dict[str, Any] = {}
        if getattr(share, "protocol", None):
            attrs["protocol"] = share.protocol
        if getattr(share, "server", None):
            attrs["server"] = share.server
        if getattr(share, "mount_point", None):
            attrs["mount_point"] = share.mount_point
        return attrs
