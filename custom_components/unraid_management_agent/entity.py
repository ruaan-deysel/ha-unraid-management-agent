"""Base entity classes for Unraid Management Agent."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_CONTAINER_DEVICES,
    CONF_ENABLE_GPU_DEVICES,
    CONF_ENABLE_HWMON_DEVICES,
    CONF_ENABLE_VM_DEVICES,
    CONF_ENABLE_ZFS_POOL_DEVICES,
    CONF_READ_ONLY,
    DEFAULT_ENABLE_CONTAINER_DEVICES,
    DEFAULT_ENABLE_GPU_DEVICES,
    DEFAULT_ENABLE_HWMON_DEVICES,
    DEFAULT_ENABLE_VM_DEVICES,
    DEFAULT_ENABLE_ZFS_POOL_DEVICES,
    DEFAULT_READ_ONLY,
    DOMAIN,
    MANUFACTURER,
)

if TYPE_CHECKING:
    from .coordinator import UnraidDataUpdateCoordinator


# Devices grouping everything about Docker and about VMs, linked to the server
# device. Container and VM devices are child devices of these, so the server
# device lists two devices instead of dozens of containers and VMs.
DOCKER_DEVICE: Final = "docker"
VMS_DEVICE: Final = "vms"
_GROUP_DEVICE_MODELS: Final = {DOCKER_DEVICE: "Docker", VMS_DEVICE: "VM Manager"}
_GROUP_DEVICE_PAGES: Final = {DOCKER_DEVICE: "Docker", VMS_DEVICE: "VMs"}


@dataclass(frozen=True, kw_only=True)
class UnraidEntityDescription(EntityDescription):
    """Base description for all Unraid entities."""

    available_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True
    supported_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True
    # DOCKER_DEVICE or VMS_DEVICE to put the entity on that device
    device_group: str | None = None


class UnraidBaseEntity(CoordinatorEntity["UnraidDataUpdateCoordinator"]):
    """Base entity for Unraid Management Agent."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        """Build device info for this entity."""
        data = self.coordinator.data
        system = data.system if data else None

        hostname = "Unraid"
        version = "Unknown"
        agent_version = None
        host = self.coordinator.config_entry.data.get(CONF_HOST, "")

        if system:
            hostname = system.hostname or "Unraid"
            version = system.version or "Unknown"
            agent_version = getattr(system, "agent_version", None)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=hostname,
            manufacturer=MANUFACTURER,
            model=f"Unraid {version}",
            sw_version=version,
            configuration_url=f"http://{host}",
        )
        if agent_version:
            device_info["hw_version"] = agent_version
        return device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


def vm_devices_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when VMs are shown as separate devices (an option, off by default)."""
    return bool(
        coordinator.config_entry.options.get(
            CONF_ENABLE_VM_DEVICES, DEFAULT_ENABLE_VM_DEVICES
        )
    )


def is_group_device_enabled(
    coordinator: UnraidDataUpdateCoordinator, group: str
) -> bool:
    """Return True if the specified group device is enabled in options."""
    if group == DOCKER_DEVICE:
        return container_devices_enabled(coordinator)
    if group == VMS_DEVICE:
        return vm_devices_enabled(coordinator)
    return False


def group_device_identifier(entry_id: str, group: str) -> str:
    """Return the device registry identifier of the Docker or VMs device."""
    return f"{entry_id}_{group}"


@callback
def async_get_or_create_group_device(
    coordinator: UnraidDataUpdateCoordinator, group: str
) -> dr.DeviceEntry | None:
    """
    Register the Docker or VMs device of the server and return it.

    It is a regular device linked to the server device, created the first time
    an entity or child device needs it, so a server without Docker or VMs gets
    no empty device. It is named after the server ("<hostname> Docker"), which
    keeps it apart from another server's and keeps the friendly names of the
    entities moved to it from the server device. A new one starts in the
    server's area with its labels, which container and VM devices then
    inherit, so area and label targets that reached them through the server
    keep doing so, and is disabled if the server is. Returns None if the
    server device is missing or the group device option is disabled.
    """
    if not is_group_device_enabled(coordinator, group):
        return None
    entry = coordinator.config_entry
    registry = dr.async_get(coordinator.hass)
    # The server device is registered during setup, before the platforms load.
    server = registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    if server is None:
        return None
    data = coordinator.data
    system = data.system if data else None
    hostname = (system.hostname if system else None) or "Unraid"
    host = entry.data.get(CONF_HOST, "")
    identifier = (DOMAIN, group_device_identifier(entry.entry_id, group))
    registered = registry.async_get_device_by_identifier(identifier, entry.entry_id)
    started = dt_util.utcnow()
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={identifier},
        manufacturer=MANUFACTURER,
        model=_GROUP_DEVICE_MODELS[group],
        configuration_url=f"http://{host}/{_GROUP_DEVICE_PAGES[group]}",
        translation_key=group,
        translation_placeholders={"hostname": hostname},
        via_device_id=server.id,
    )
    if registered is not None or device.created_at < started:
        # Registered earlier, or restored from an earlier removal with the
        # settings the user gave it
        return device
    return registry.async_update_device(
        device.id,
        area_id=server.area_id,
        labels=set(server.labels),
        # Container and VM devices of a disabled server are disabled with it,
        # and stay so under a disabled Docker or VMs device
        disabled_by=server.disabled_by,
    )


def build_group_device_info(
    coordinator: UnraidDataUpdateCoordinator, group: str
) -> DeviceInfo:
    """Build device info putting an entity on the Docker or VMs device."""
    entry_id = coordinator.config_entry.entry_id
    if (
        not is_group_device_enabled(coordinator, group)
        or async_get_or_create_group_device(coordinator, group) is None
    ):
        # Keep the entity on the server device if disabled or missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return DeviceInfo(identifiers={(DOMAIN, group_device_identifier(entry_id, group))})


def build_vm_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    vm_identifier: str,
    vm_name: str,
) -> DeviceInfo | ChildDeviceInfo:
    """
    Build device info for a virtual machine.

    VMs are child devices of the server's VMs device, so they are grouped
    there rather than listed as separate devices or under the server. The
    libvirt UUID is used as the identifier so renaming a VM keeps the device.

    The device is named after the VM. Home Assistant puts the parent device's
    name ("<hostname> VMs") in front of it in entity names, which tells VMs
    apart from containers, so the "VM · " prefix VM devices had under the
    server is no longer used. The registry updates the name each time the
    entities are set up, so existing VM devices and renamed VMs follow.
    """
    entry_id = coordinator.config_entry.entry_id
    parent = async_get_or_create_group_device(coordinator, VMS_DEVICE)
    if parent is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_vm_{vm_identifier}")},
        name=vm_name,
        parent_device_id=parent.id,
    )


def find_vm(
    coordinator: UnraidDataUpdateCoordinator,
    vm_identifier: str | None,
    vm_name: str | None,
) -> Any | None:
    """
    Find a VM in coordinator data by stable identifier, falling back to name.

    The identifier is matched across all VMs first, so a VM that was renamed
    is not confused with another VM that has since taken its old name.
    """
    data = coordinator.data
    if not data or not data.vms:
        return None
    if vm_identifier is not None:
        for vm in data.vms:
            current = getattr(vm, "id", None) or getattr(vm, "name", None)
            if current == vm_identifier:
                return vm
    if vm_name is not None:
        for vm in data.vms:
            if getattr(vm, "name", None) == vm_name:
                return vm
    return None


def container_devices_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when containers are shown as separate devices (off by default)."""
    return bool(
        coordinator.config_entry.options.get(
            CONF_ENABLE_CONTAINER_DEVICES, DEFAULT_ENABLE_CONTAINER_DEVICES
        )
    )


def build_container_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    container_name: str,
) -> DeviceInfo | ChildDeviceInfo:
    """
    Build device info for a Docker container.

    Containers are child devices of the server's Docker device: there can be
    dozens, so they are grouped there instead of being listed as separate
    devices or under the server. Keyed by name because container IDs change
    whenever a container is recreated.
    """
    entry_id = coordinator.config_entry.entry_id
    parent = async_get_or_create_group_device(coordinator, DOCKER_DEVICE)
    if parent is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_container_{container_name}")},
        name=container_name,
        parent_device_id=parent.id,
    )


def gpu_devices_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when GPUs are shown as separate devices (an option, off by default)."""
    return bool(
        coordinator.config_entry.options.get(
            CONF_ENABLE_GPU_DEVICES, DEFAULT_ENABLE_GPU_DEVICES
        )
    )


def _gpu_hardware_key(gpu: Any) -> str | None:
    """
    Return the key of a GPU's own hardware ID, or None when it reports none.

    The UUID (NVIDIA only) belongs to the card itself, so it survives moving
    the card to another slot. The PCI bus address is reported for every vendor
    and only changes when the card moves.
    """
    for prefix, attr in (("uuid", "uuid"), ("pci", "pci_id")):
        value = getattr(gpu, attr, None)
        if not isinstance(value, str):
            continue
        # nvidia-smi reports an unknown field as "[N/A]"
        if (value := value.strip().lower()) and value not in ("n/a", "[n/a]"):
            return f"{prefix}_{value}"
    return None


def gpu_device_keys(gpus: list[Any] | None) -> dict[int, str]:
    """
    Return the device key of each reported GPU, by GPU index.

    GPU entities are keyed by index, but an index belongs to whichever GPU the
    agent lists at that position: one appearing in front of it (e.g. a GPU
    given back to the host by a VM) shifts the others. The device is keyed by
    the GPU's hardware ID instead, so its name, area and labels stay with the
    physical card. GPUs reporting no hardware ID, or one shared with another
    GPU, fall back to their index.
    """
    candidates: list[tuple[int, str | None]] = [
        (gpu.index if gpu.index is not None else position, _gpu_hardware_key(gpu))
        for position, gpu in enumerate(gpus or [])
    ]
    counts = Counter(key for _, key in candidates if key)
    return {
        index: key if key and counts[key] == 1 else f"index_{index}"
        for index, key in candidates
    }


def gpu_device_key(coordinator: UnraidDataUpdateCoordinator, gpu_index: int) -> str:
    """Return the device key of the GPU currently at an index."""
    data = coordinator.data
    return gpu_device_keys(data.gpu if data else None).get(
        gpu_index, f"index_{gpu_index}"
    )


def gpu_device_identifier(entry_id: str, key: str) -> str:
    """Return the device registry identifier of a GPU."""
    return f"{entry_id}_gpu_{key}"


def build_gpu_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    gpu_index: int,
    gpu_name: str,
) -> DeviceInfo | ChildDeviceInfo:
    """
    Build device info for a GPU.

    With the "GPUs as separate devices" option on, GPUs are child devices of
    the Unraid server, like storage controllers. Child devices can't carry a
    manufacturer, model or firmware version, so the device name is translated
    ("GPU · <name>") to tell GPUs apart from other child devices; the driver
    version stays a sensor attribute.
    """
    entry_id = coordinator.config_entry.entry_id
    # The server device is registered during setup, before the platforms load.
    server = dr.async_get(coordinator.hass).async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )
    if server is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    key = gpu_device_key(coordinator, gpu_index)
    return ChildDeviceInfo(
        identifiers={(DOMAIN, gpu_device_identifier(entry_id, key))},
        parent_device_id=server.id,
        translation_key="gpu",
        translation_placeholders={"name": gpu_name},
    )


def read_only_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when the entry is in read-only mode (nothing may change the server)."""
    return bool(coordinator.config_entry.options.get(CONF_READ_ONLY, DEFAULT_READ_ONLY))


def hwmon_devices_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when USB sensor controllers get their own devices (off by default)."""
    return bool(
        coordinator.config_entry.options.get(
            CONF_ENABLE_HWMON_DEVICES, DEFAULT_ENABLE_HWMON_DEVICES
        )
    )


def zfs_pool_devices_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when ZFS pools are shown as separate devices (off by default)."""
    return bool(
        coordinator.config_entry.options.get(
            CONF_ENABLE_ZFS_POOL_DEVICES, DEFAULT_ENABLE_ZFS_POOL_DEVICES
        )
    )


def hwmon_controller_identifier(entry_id: str, driver: str, device_id: str) -> str:
    """Return the device registry identifier of a USB sensor controller."""
    key = re.sub(r"[^a-z0-9]+", "_", f"{driver}_{device_id}".lower()).strip("_")
    return f"{entry_id}_hwmon_{key}"


def build_hwmon_controller_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    driver: str,
    device_id: str,
    name: str,
) -> DeviceInfo | ChildDeviceInfo:
    """
    Build device info for a USB HID sensor controller (e.g. an Aquacomputer Octo).

    Controllers are child devices of the Unraid server, keyed by driver and
    the device_id the agent reports (USB serial or port), which stays the
    same when the controller reconnects.
    """
    entry_id = coordinator.config_entry.entry_id
    server = dr.async_get(coordinator.hass).async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )
    if server is None:
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return ChildDeviceInfo(
        identifiers={
            (DOMAIN, hwmon_controller_identifier(entry_id, driver, device_id))
        },
        name=name,
        parent_device_id=server.id,
    )


def zfs_pool_device_identifier(entry_id: str, pool_name: str) -> str:
    """Return the device registry identifier of a ZFS pool device."""
    return f"{entry_id}_zfs_pool_{pool_name}"


def build_zfs_pool_device_info(
    coordinator: UnraidDataUpdateCoordinator, pool_name: str
) -> DeviceInfo | ChildDeviceInfo:
    """
    Build device info for a ZFS pool.

    Pools are child devices of the Unraid server, keyed by pool name (the
    name is how zpool and Unraid identify a pool). The device name is
    translated ("ZFS pool · <name>"), like VM devices.
    """
    entry_id = coordinator.config_entry.entry_id
    # The server device is registered during setup, before the platforms load.
    server = dr.async_get(coordinator.hass).async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )
    if server is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return ChildDeviceInfo(
        identifiers={(DOMAIN, zfs_pool_device_identifier(entry_id, pool_name))},
        parent_device_id=server.id,
        translation_key="zfs_pool",
        translation_placeholders={"name": pool_name},
    )


class UnraidZFSPoolEntity(UnraidBaseEntity):
    """Base for per-pool ZFS entities: on the pool's device or the server device."""

    def _use_pool_device_or_name(self, pool_name: str, sensor_type: str) -> None:
        """
        Put the entity on the pool's device, or name it after the pool.

        With the "ZFS pools as separate devices" option on, the entity sits on
        the pool's device with a short name (the device name holds the pool
        name). Otherwise it stays on the server device, named after the pool.
        Unique IDs are the same either way, so toggling the option moves the
        existing entities and keeps their entity IDs.
        """
        if zfs_pool_devices_enabled(self.coordinator):
            self._attr_device_info = build_zfs_pool_device_info(
                self.coordinator, pool_name
            )
            self._attr_translation_key = f"zfs_pool_device_{sensor_type}"
            self._attr_translation_placeholders = {}
        else:
            self._attr_translation_key = f"zfs_pool_{sensor_type}"
            self._attr_translation_placeholders = {"pool_name": pool_name}


class UnraidEntity(UnraidBaseEntity):
    """Entity with description support for Unraid Management Agent."""

    entity_description: UnraidEntityDescription

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entity_description: UnraidEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if super().available:
            return self.entity_description.available_fn(self.coordinator)
        return False


# Export these for external use
__all__ = [
    "DOCKER_DEVICE",
    "VMS_DEVICE",
    "UnraidBaseEntity",
    "UnraidEntity",
    "UnraidEntityDescription",
    "UnraidZFSPoolEntity",
    "async_get_or_create_group_device",
    "build_container_device_info",
    "build_gpu_device_info",
    "build_group_device_info",
    "build_hwmon_controller_device_info",
    "build_vm_device_info",
    "build_zfs_pool_device_info",
    "container_devices_enabled",
    "find_vm",
    "gpu_device_identifier",
    "gpu_device_key",
    "gpu_device_keys",
    "gpu_devices_enabled",
    "group_device_identifier",
    "hwmon_controller_identifier",
    "hwmon_devices_enabled",
    "is_group_device_enabled",
    "read_only_enabled",
    "vm_devices_enabled",
    "zfs_pool_device_identifier",
    "zfs_pool_devices_enabled",
]
