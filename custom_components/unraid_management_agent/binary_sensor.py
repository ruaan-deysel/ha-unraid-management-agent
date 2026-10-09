"""Binary sensor platform for Unraid Management Agent."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .alerts import (
    ALERT_STATE_FIRING,
    alert_rule_key,
    alert_rule_names,
    alert_since,
    find_alert_rule,
    find_alert_status,
)
from .api.models import SystemService
from .cleanup import async_prune_seen_names
from .const import ATTR_PARITY_CHECK_STATUS
from .entity import UnraidBaseEntity, UnraidEntityDescription
from .nut import find_nut_status, nut_device_key, secondary_nut_statuses
from .storage import (
    StorageEntitySpec,
    UnraidStorageBinarySensorEntityDescription,
    UnraidStorageEntity,
    async_setup_storage_entities,
    storage_binary_sensor_specs,
)

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0

# Services in the agent's /services list that /settings/network-services also
# reports. Those already have a "<name> Service" network service binary
# sensor, so they get no second entity here.
_NETWORK_SERVICE_DUPLICATES: Final = frozenset(
    {"smb", "nfs", "ftp", "sshd", "syslog", "ntpd", "avahi", "wireguard"}
)

# System services whose sensor is enabled by default: Docker and the VM
# Manager back containers and VMs. Others (nginx, later additions) start
# disabled like the network service sensors.
_SYSTEM_SERVICES_ENABLED_BY_DEFAULT: Final = frozenset({"docker", "libvirt"})

# Display names for the services that get a system service binary sensor;
# services added to the agent later fall back to their raw name.
_SYSTEM_SERVICE_DISPLAY_NAMES: Final[dict[str, str]] = {
    "docker": "Docker",
    "libvirt": "Libvirt",
    "nginx": "Nginx",
}


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


# =============================================================================
# Container Update Functions (#86)
# =============================================================================


def _has_container_updates(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if any containers have updates available."""
    data = coordinator.data
    if data and data.container_updates:
        updates_available = getattr(data.container_updates, "updates_available", None)
        return (updates_available or 0) > 0
    return False


def _has_container_updates_data(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return true if container updates data is available."""
    data = coordinator.data
    return (
        data is not None
        and data.container_updates is not None
        and coordinator.is_container_updates_enabled()
    )


def _container_updates_attributes(
    coordinator: UnraidDataUpdateCoordinator,
) -> dict[str, Any]:
    """Return container updates attributes."""
    data = coordinator.data
    if not data or not data.container_updates:
        return {}
    updates = data.container_updates
    return {
        "updates_available": getattr(updates, "updates_available", 0),
        "total_containers": getattr(updates, "total_count", None),
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
    # Container updates available (#86)
    UnraidBinarySensorEntityDescription(
        key="container_updates_available",
        translation_key="container_updates_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        icon="mdi:update",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_has_container_updates,
        supported_fn=_has_container_updates_data,
        extra_state_attributes_fn=_container_updates_attributes,
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

    # ZFS pool problem binary sensors - only if zfs collector is enabled
    if coordinator.is_collector_enabled("zfs"):
        entities.extend(
            UnraidZFSPoolProblemBinarySensor(coordinator, pool.name)
            for pool in (data.zfs_pools if data else None) or []
            if pool.name
        )

    # Unassigned device mounted binary sensors - created dynamically as devices appear
    seen_unassigned: set[str] = set()

    def _add_unassigned_device_sensors() -> None:
        new_entities: list[BinarySensorEntity] = []
        current_data = coordinator.data
        if not current_data or not current_data.unassigned_devices:
            return
        # Allow re-creation of entities removed from the registry (see #83)
        async_prune_seen_names(
            hass,
            "binary_sensor",
            seen_unassigned,
            lambda name: f"{entry.entry_id}_unassigned_device_{slugify(name)}_mounted",
        )
        for device in current_data.unassigned_devices:
            device_name = getattr(device, "name", None) or getattr(
                device, "device", None
            )
            if device_name and device_name not in seen_unassigned:
                seen_unassigned.add(device_name)
                new_entities.append(
                    UnraidUnassignedDeviceBinarySensor(coordinator, device_name)
                )
        if new_entities:
            async_add_entities(new_entities)

    _add_unassigned_device_sensors()

    # Remote share mounted binary sensors - created dynamically as shares appear (#83)
    seen_remote_shares: set[str] = set()

    def _add_remote_share_sensors() -> None:
        new_entities: list[BinarySensorEntity] = []
        current_data = coordinator.data
        if not current_data or not current_data.remote_shares:
            return
        # Allow re-creation of entities removed from the registry (see #83)
        async_prune_seen_names(
            hass,
            "binary_sensor",
            seen_remote_shares,
            lambda name: f"{entry.entry_id}_remote_share_{slugify(name)}_mounted",
        )
        for remote_share in current_data.remote_shares:
            share_name = getattr(remote_share, "name", None)
            if share_name and share_name not in seen_remote_shares:
                seen_remote_shares.add(share_name)
                new_entities.append(
                    UnraidRemoteShareBinarySensor(coordinator, share_name)
                )
        if new_entities:
            async_add_entities(new_entities)

    _add_remote_share_sensors()

    # Alert rule binary sensors - one per agent alert rule, created as rules appear
    seen_alert_rules: set[str] = set()

    def _add_alert_rule_sensors() -> None:
        # Allow re-creation of entities removed from the registry (see #83)
        async_prune_seen_names(
            hass,
            "binary_sensor",
            seen_alert_rules,
            lambda rule_id: f"{entry.entry_id}_{alert_rule_key(rule_id)}",
        )
        new_entities: list[BinarySensorEntity] = []
        for rule_id, rule_name in alert_rule_names(coordinator.data).items():
            if rule_id not in seen_alert_rules:
                seen_alert_rules.add(rule_id)
                new_entities.append(
                    UnraidAlertRuleBinarySensor(coordinator, rule_id, rule_name)
                )
        if new_entities:
            async_add_entities(new_entities)

    _add_alert_rule_sensors()

    # Register listeners so entities are added when new unassigned/remote-share
    # data or new alert rules arrive
    entry.async_on_unload(
        coordinator.async_add_listener(callback(_add_unassigned_device_sensors))
    )
    entry.async_on_unload(
        coordinator.async_add_listener(callback(_add_remote_share_sensors))
    )
    entry.async_on_unload(
        coordinator.async_add_listener(callback(_add_alert_rule_sensors))
    )

    # System service binary sensors (/services) - created as services appear
    seen_system_services: set[str] = set()

    def _add_system_service_sensors() -> None:
        current_data = coordinator.data
        if not current_data or not current_data.system_services:
            return
        # Allow re-creation of entities removed from the registry (see #83)
        async_prune_seen_names(
            hass,
            "binary_sensor",
            seen_system_services,
            lambda name: f"{entry.entry_id}_system_service_{slugify(name)}",
        )
        new_entities: list[BinarySensorEntity] = []
        for service in current_data.system_services:
            name = service.name
            if (
                name
                and name not in _NETWORK_SERVICE_DUPLICATES
                and name not in seen_system_services
            ):
                seen_system_services.add(name)
                new_entities.append(UnraidSystemServiceBinarySensor(coordinator, name))
        if new_entities:
            async_add_entities(new_entities)

    _add_system_service_sensors()
    entry.async_on_unload(
        coordinator.async_add_listener(callback(_add_system_service_sensors))
    )

    # NUT device connected sensors - one per NUT device other than the primary
    # UPS (which has ups_connected), created as devices appear
    seen_nut_devices: set[str] = set()

    def _add_nut_device_sensors() -> None:
        if not coordinator.is_collector_enabled("nut"):
            return
        # Allow re-creation of entities removed from the registry (see #83)
        async_prune_seen_names(
            hass,
            "binary_sensor",
            seen_nut_devices,
            lambda name: f"{entry.entry_id}_{nut_device_key(name)}_connected",
        )
        new_entities: list[BinarySensorEntity] = []
        for name, _status in secondary_nut_statuses(coordinator.data):
            if name not in seen_nut_devices:
                seen_nut_devices.add(name)
                new_entities.append(UnraidNUTConnectedBinarySensor(coordinator, name))
        if new_entities:
            async_add_entities(new_entities)

    _add_nut_device_sensors()
    entry.async_on_unload(
        coordinator.async_add_listener(callback(_add_nut_device_sensors))
    )

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

    # Storage controllers and enclosures (each a child device of the server)
    async_setup_storage_entities(
        entry,
        "binary_sensor",
        storage_binary_sensor_specs,
        UnraidStorageBinarySensor,
        async_add_entities,
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


class UnraidNUTConnectedBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """Whether a NUT device other than the primary UPS answers, like UPS Connected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "nut_ups_connected"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, f"{nut_device_key(device_name)}_connected")
        self._device_name = device_name
        self._attr_translation_placeholders = {"device": device_name}

    @property
    def is_on(self) -> bool:
        """Return True while the device answers with a status."""
        status = find_nut_status(self.coordinator.data, self._device_name)
        return status is not None and bool(status.status)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device type, status and model when known."""
        status = find_nut_status(self.coordinator.data, self._device_name)
        if status is None:
            return {}
        return {
            key: value
            for key, value in (
                ("device_type", status.type),
                ("ups_status", status.status),
                ("ups_model", status.model),
            )
            if value
        }


class UnraidSystemServiceBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """Running state of a system service from the agent's /services list."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "system_service"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        service_name: str,
    ) -> None:
        """Initialize the system service binary sensor."""
        self._service_name = service_name
        super().__init__(coordinator, f"system_service_{slugify(service_name)}")
        self._attr_entity_registry_enabled_default = (
            service_name in _SYSTEM_SERVICES_ENABLED_BY_DEFAULT
        )
        self._attr_translation_placeholders = {
            "service_name": _SYSTEM_SERVICE_DISPLAY_NAMES.get(
                service_name, service_name
            )
        }

    def _get_service(self) -> SystemService | None:
        """Return this service from the latest coordinator data, if present."""
        data = self.coordinator.data
        for service in (data.system_services if data else None) or []:
            if service.name == self._service_name:
                return service
        return None

    @property
    def available(self) -> bool:
        """Return False when the service is missing from the current data."""
        return super().available and self._get_service() is not None

    @property
    def is_on(self) -> bool:
        """Return True if the service is running."""
        service = self._get_service()
        return service is not None and service.running is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return whether the service is enabled in Unraid's settings, if known."""
        data = self.coordinator.data
        settings: Any = None
        if data and self._service_name == "docker":
            settings = data.docker_settings
        elif data and self._service_name == "libvirt":
            settings = data.vm_settings
        enabled = getattr(settings, "enabled", None)
        return {} if enabled is None else {"enabled": enabled}


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


class UnraidStorageBinarySensor(UnraidStorageEntity, BinarySensorEntity):
    """A problem indicator of a storage controller or enclosure."""

    entity_description: UnraidStorageBinarySensorEntityDescription

    def __init__(
        self, coordinator: UnraidDataUpdateCoordinator, spec: StorageEntitySpec
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, spec)
        self.entity_description = spec.description

    @property
    def is_on(self) -> bool | None:
        """Return True when there is a problem."""
        ctx = self._storage_context()
        return self.entity_description.is_on_fn(ctx) if ctx else None


class UnraidAlertRuleBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """
    Problem binary sensor for one agent alert rule, on while the rule fires.

    The agent only evaluates enabled rules, so a disabled rule's sensor is
    unavailable rather than reporting a misleading "OK".
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "alert_rule"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        rule_id: str,
        rule_name: str,
    ) -> None:
        """Initialize the alert rule binary sensor."""
        self._rule_id = rule_id
        super().__init__(coordinator, alert_rule_key(rule_id))
        self._attr_translation_placeholders = {"rule_name": rule_name}

    @property
    def available(self) -> bool:
        """Return True while the agent reports a status for the rule."""
        return (
            super().available
            and find_alert_status(self.coordinator.data, self._rule_id) is not None
        )

    @property
    def is_on(self) -> bool:
        """Return True if the alert rule is firing."""
        status = find_alert_status(self.coordinator.data, self._rule_id)
        return status is not None and status.state == ALERT_STATE_FIRING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return the rule's state, severity and definition.

        Notification channels are left out: they can hold webhook URLs with
        credentials.
        """
        attrs: dict[str, Any] = {"rule_id": self._rule_id}
        status = find_alert_status(self.coordinator.data, self._rule_id)
        rule = find_alert_rule(self.coordinator.data, self._rule_id)
        severity = (status.severity if status else None) or (
            rule.severity if rule else None
        )
        if severity:
            attrs["severity"] = severity
        if status is not None:
            if status.state:
                attrs["alert_state"] = status.state
            since = alert_since(status)
            if since is not None:
                attrs["since"] = since.isoformat()
            if status.message:
                attrs["message"] = status.message
        if rule is not None:
            if rule.expression:
                attrs["expression"] = rule.expression
            if rule.duration_seconds:
                attrs["duration_seconds"] = rule.duration_seconds
            if rule.cooldown_minutes:
                attrs["cooldown_minutes"] = rule.cooldown_minutes
        return attrs


class UnraidZFSPoolProblemBinarySensor(UnraidBaseEntity, BinarySensorEntity):
    """On when a ZFS pool is not ONLINE or has read/write/checksum/scrub errors."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        pool_name: str,
    ) -> None:
        """Initialize the ZFS pool problem binary sensor."""
        self._pool_name = pool_name
        super().__init__(coordinator, f"zfs_{pool_name}_problem")
        self._attr_translation_key = "zfs_pool_problem"
        self._attr_translation_placeholders = {"pool_name": pool_name}

    def _get_pool(self) -> Any | None:
        """Return this pool from coordinator data."""
        data = self.coordinator.data
        if not data or not data.zfs_pools:
            return None
        return next((p for p in data.zfs_pools if p.name == self._pool_name), None)

    @staticmethod
    def _error_counts(pool: Any) -> dict[str, int | None]:
        """Return the pool's error totals and last scrub error count."""
        return {
            "read_errors": pool.error_total("read_errors"),
            "write_errors": pool.error_total("write_errors"),
            "checksum_errors": pool.error_total("checksum_errors"),
            "scrub_errors": pool.scan_errors,
        }

    @property
    def is_on(self) -> bool | None:
        """Return True if the pool is unhealthy or has reported errors."""
        pool = self._get_pool()
        if pool is None:
            return None
        health = pool.health or pool.state
        if health and health.upper() != "ONLINE":
            return True
        return any(count for count in self._error_counts(pool).values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return pool health and error counts."""
        pool = self._get_pool()
        if pool is None:
            return {}
        attrs: dict[str, Any] = {"health": pool.health or pool.state}
        attrs.update(self._error_counts(pool))
        return attrs
