"""Switch platform for Unraid Management Agent."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .api.formatting import format_bytes
from .const import (
    ATTR_CONTAINER_IMAGE,
    ATTR_CONTAINER_PORTS,
    ATTR_VM_MEMORY,
    ATTR_VM_VCPUS,
    DOMAIN,
)
from .entity import UnraidBaseEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


def _make_unique_key(name: str) -> str:
    """
    Create a unique key from a name that preserves uniqueness.

    Uses slugify for readability plus a short hash suffix to ensure
    names that differ only by spaces/special chars remain unique.
    E.g., "Windows Server 2016" and "WindowsServer2016" will have
    different keys.
    """
    slug = slugify(name)
    # Add short hash of original name to ensure uniqueness
    name_hash = hashlib.md5(name.encode(), usedforsecurity=False).hexdigest()[:6]
    return f"{slug}_{name_hash}"


def _make_vm_unique_key(vm_identifier: str, vm_name: str) -> str:
    """Create a stable VM key that prefers the backend VM identifier."""
    if vm_identifier and vm_identifier != vm_name:
        return slugify(vm_identifier)
    return _make_unique_key(vm_name)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid switch entities."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    entities: list[SwitchEntity] = []

    # Container switches - only if docker collector is enabled AND docker service is enabled
    if coordinator.is_collector_enabled("docker") and coordinator.is_docker_enabled():
        containers = data.containers if data else []
        seen_container_names: set[str] = set()
        for container in containers or []:
            container_name = getattr(container, "name", None)
            if container_name and container_name not in seen_container_names:
                seen_container_names.add(container_name)
                entities.append(UnraidContainerSwitch(coordinator, container_name))

    # VM switches - only if vm collector is enabled AND vm service is enabled
    if coordinator.is_collector_enabled("vm") and coordinator.is_vm_enabled():
        vms = data.vms if data else []
        seen_vm_identifiers: set[str] = set()
        for vm in vms or []:
            vm_identifier = getattr(vm, "id", None) or getattr(vm, "name", None)
            vm_name = getattr(vm, "name", None)
            if vm_identifier and vm_name and vm_identifier not in seen_vm_identifiers:
                seen_vm_identifiers.add(vm_identifier)
                entities.append(UnraidVMSwitch(coordinator, vm_identifier, vm_name))

    # Disk spin switches - only if disk collector is enabled
    if coordinator.is_collector_enabled("disk"):
        disks = data.disks if data else []
        for disk in disks or []:
            if getattr(disk, "is_physical", False):
                disk_id = str(getattr(disk, "id", None) or getattr(disk, "name", ""))
                disk_name = str(getattr(disk, "name", ""))
                if disk_id and disk_name:
                    entities.append(
                        UnraidDiskSpinSwitch(coordinator, disk_id, disk_name)
                    )

    _LOGGER.debug("Adding %d Unraid switch entities", len(entities))
    async_add_entities(entities)


class UnraidContainerSwitch(UnraidBaseEntity, SwitchEntity):
    """Container control switch."""

    _attr_icon = "mdi:docker"
    _attr_assumed_state = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        container_name: str,
    ) -> None:
        """
        Initialize the switch.

        Uses container name as the stable identifier to prevent entity
        duplication when containers are updated (which changes their ID).
        """
        self._container_name = container_name
        # Use unique key from container name for stable unique_id
        safe_name = _make_unique_key(container_name)
        super().__init__(coordinator, f"container_{safe_name}")
        self._attr_translation_key = "container"
        self._attr_translation_placeholders = {"name": container_name}
        self._optimistic_state: bool | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear optimistic state when API state matches expected state
        if self._optimistic_state is not None:
            container = self._find_container()
            if container:
                actual_running = getattr(container, "state", "").lower() == "running"
                if actual_running == self._optimistic_state:
                    self._optimistic_state = None
        super()._handle_coordinator_update()

    def _find_container(self) -> Any | None:
        """Find the container in coordinator data by name."""
        data = self.coordinator.data
        if not data or not data.containers:
            return None

        for container in data.containers:
            if getattr(container, "name", None) == self._container_name:
                return container
        return None

    @property
    def _container_id(self) -> str | None:
        """Get the current container ID for API calls."""
        container = self._find_container()
        if container:
            return getattr(container, "id", None) or getattr(
                container, "container_id", None
            )
        return None

    @property
    def is_on(self) -> bool:
        """Return true if container is running."""
        if self._optimistic_state is not None:
            return self._optimistic_state

        container = self._find_container()
        if container:
            state = getattr(container, "state", "").lower()
            return state == "running"
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        container = self._find_container()
        if not container:
            return {}

        state = getattr(container, "state", "").lower()

        # Convert PortMapping objects to JSON-serializable format
        ports = getattr(container, "ports", None)
        serializable_ports = None
        if ports:
            serializable_ports = [
                {
                    "public_port": getattr(p, "public_port", None),
                    "private_port": getattr(p, "private_port", None),
                    "type": getattr(p, "type", None),
                }
                for p in ports
            ]

        return {
            "status": "running" if state == "running" else "stopped",
            ATTR_CONTAINER_IMAGE: getattr(container, "image", None),
            ATTR_CONTAINER_PORTS: serializable_ports,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the container."""
        container_id = self._container_id
        if container_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_start_error",
                translation_placeholders={"name": self._container_name},
            )
        try:
            self._optimistic_state = True
            self.async_write_ha_state()

            await self.coordinator.client.start_container(container_id)
            _LOGGER.info("Started container: %s", self._container_name)

            # Request a refresh to update state
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_start_error",
                translation_placeholders={"name": self._container_name},
            ) from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the container."""
        container_id = self._container_id
        if container_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_stop_error",
                translation_placeholders={"name": self._container_name},
            )
        try:
            self._optimistic_state = False
            self.async_write_ha_state()

            await self.coordinator.client.stop_container(container_id)
            _LOGGER.info("Stopped container: %s", self._container_name)

            # Request a refresh to update state
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_stop_error",
                translation_placeholders={"name": self._container_name},
            ) from exc


class UnraidVMSwitch(UnraidBaseEntity, SwitchEntity):
    """VM control switch."""

    _attr_icon = "mdi:desktop-tower"
    _attr_assumed_state = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        vm_identifier: str,
        vm_name: str | None = None,
    ) -> None:
        """
        Initialize the switch.

        Uses the backend VM identifier when available so VM renames and
        punctuation changes do not create duplicate entities.
        """
        if vm_name is None:
            vm_name = vm_identifier
        self._vm_identifier = vm_identifier
        self._vm_name = vm_name
        safe_name = _make_vm_unique_key(vm_identifier, vm_name)
        super().__init__(coordinator, f"vm_{safe_name}")
        self._attr_translation_key = "vm"
        self._attr_translation_placeholders = {"name": vm_name}
        self._optimistic_state: bool | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear optimistic state when API state matches expected state
        if self._optimistic_state is not None:
            vm = self._find_vm()
            if vm:
                actual_running = getattr(vm, "state", "").lower() == "running"
                if actual_running == self._optimistic_state:
                    self._optimistic_state = None
        super()._handle_coordinator_update()

    def _find_vm(self) -> Any | None:
        """Find the VM in coordinator data by stable identifier."""
        data = self.coordinator.data
        if not data or not data.vms:
            return None

        vm_identifier = getattr(self, "_vm_identifier", None)
        vm_name = getattr(self, "_vm_name", None)

        for vm in data.vms:
            current_identifier = getattr(vm, "id", None) or getattr(vm, "name", None)
            if vm_identifier is not None and current_identifier == vm_identifier:
                return vm
            if vm_name is not None and getattr(vm, "name", None) == vm_name:
                return vm
        return None

    @property
    def _vm_id(self) -> str | None:
        """
        Get the VM identifier for API calls.

        Note: The UMA API uses VM name (not ID) for start/stop operations.
        """
        vm = self._find_vm()
        if vm:
            # UMA API expects VM name for start/stop, not the internal ID
            return getattr(vm, "name", None)
        return None

    @property
    def is_on(self) -> bool:
        """Return true if VM is running."""
        if self._optimistic_state is not None:
            return self._optimistic_state

        vm = self._find_vm()
        if vm:
            state = getattr(vm, "state", "").lower()
            return state == "running"
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        vm = self._find_vm()
        if not vm:
            return {}

        state = getattr(vm, "state", "").lower()

        # Format CPU percentages
        guest_cpu = getattr(vm, "guest_cpu_percent", None)
        host_cpu = getattr(vm, "host_cpu_percent", None)
        guest_cpu_str = f"{guest_cpu:.1f}%" if guest_cpu is not None else "0.0%"
        host_cpu_str = f"{host_cpu:.1f}%" if host_cpu is not None else "0.0%"

        # Format memory display
        memory_display = getattr(vm, "memory_display", None) or "Unknown"

        # Format disk I/O
        disk_read = getattr(vm, "disk_read_bytes", 0) or 0
        disk_write = getattr(vm, "disk_write_bytes", 0) or 0
        disk_io_str = (
            f"Rd: {format_bytes(disk_read)}/s Wr: {format_bytes(disk_write)}/s"
        )

        return {
            "status": "running" if state == "running" else "stopped",
            ATTR_VM_VCPUS: getattr(vm, "cpu_count", None),
            "guest_cpu": guest_cpu_str,
            "host_cpu": host_cpu_str,
            ATTR_VM_MEMORY: memory_display,
            "disk_io": disk_io_str,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the VM."""
        vm_id = self._vm_id
        if vm_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_start_error",
                translation_placeholders={"name": self._vm_name},
            )
        try:
            self._optimistic_state = True
            self.async_write_ha_state()

            await self.coordinator.client.start_vm(vm_id)
            _LOGGER.info("Started VM: %s", self._vm_name)

            # Request a refresh to update state
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_start_error",
                translation_placeholders={"name": self._vm_name},
            ) from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VM."""
        vm_id = self._vm_id
        if vm_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_stop_error",
                translation_placeholders={"name": self._vm_name},
            )
        try:
            self._optimistic_state = False
            self.async_write_ha_state()

            await self.coordinator.client.stop_vm(vm_id)
            _LOGGER.info("Stopped VM: %s", self._vm_name)

            # Request a refresh to update state
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_stop_error",
                translation_placeholders={"name": self._vm_name},
            ) from exc


class UnraidDiskSpinSwitch(UnraidBaseEntity, SwitchEntity):
    """Disk spin control switch."""

    _attr_icon = "mdi:harddisk"
    _attr_assumed_state = False
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        disk_id: str,
        disk_name: str,
    ) -> None:
        """Initialize the disk spin switch."""
        self._disk_id = disk_id
        self._disk_name = disk_name
        safe_name = slugify(disk_name)
        super().__init__(coordinator, f"disk_{safe_name}_spin")
        self._attr_translation_key = "disk_spin"
        self._attr_translation_placeholders = {"disk_name": disk_name}
        self._optimistic_state: bool | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._optimistic_state is not None:
            disk = self._find_disk()
            if disk:
                actual_active = getattr(disk, "spin_state", "").lower() == "active"
                if actual_active == self._optimistic_state:
                    self._optimistic_state = None
        super()._handle_coordinator_update()

    def _find_disk(self) -> Any | None:
        """Find the disk in coordinator data."""
        data = self.coordinator.data
        if not data or not data.disks:
            return None
        for disk in data.disks:
            d_id = str(getattr(disk, "id", None) or getattr(disk, "name", ""))
            if d_id == self._disk_id:
                return disk
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._find_disk() is not None

    @property
    def is_on(self) -> bool:
        """Return true if disk is spun up (active)."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        disk = self._find_disk()
        if disk:
            return getattr(disk, "spin_state", "").lower() == "active"
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Spin up the disk."""
        try:
            self._optimistic_state = True
            self.async_write_ha_state()
            await self.coordinator.client.spin_up_disk(self._disk_id)
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="disk_spin_up_error",
                translation_placeholders={"disk_name": self._disk_name},
            ) from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Spin down the disk."""
        try:
            self._optimistic_state = False
            self.async_write_ha_state()
            await self.coordinator.client.spin_down_disk(self._disk_id)
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="disk_spin_down_error",
                translation_placeholders={"disk_name": self._disk_name},
            ) from exc
