"""Switch platform for Unraid Management Agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from uma_api.formatting import format_bytes

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .const import (
    ATTR_CONTAINER_IMAGE,
    ATTR_CONTAINER_PORTS,
    ATTR_VM_MEMORY,
    ATTR_VM_VCPUS,
    ERROR_CONTROL_FAILED,
)
from .entity import UnraidEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Unraid switch entities."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    entities: list[SwitchEntity] = []

    # Container switches
    containers = data.containers if data else []
    for container in containers or []:
        container_id = getattr(container, "id", None) or getattr(
            container, "container_id", None
        )
        container_name = getattr(container, "name", "unknown")
        if container_id:
            entities.append(
                UnraidContainerSwitch(coordinator, entry, container_id, container_name)
            )

    # VM switches
    vms = data.vms if data else []
    for vm in vms or []:
        vm_id = getattr(vm, "id", None) or getattr(vm, "name", None)
        vm_name = getattr(vm, "name", "unknown")
        if vm_id:
            entities.append(UnraidVMSwitch(coordinator, entry, vm_id, vm_name))

    _LOGGER.debug("Adding %d Unraid switch entities", len(entities))
    async_add_entities(entities)


class UnraidSwitchBase(UnraidEntity, SwitchEntity):
    """Base class for Unraid switches."""


# Container Switches


class UnraidContainerSwitch(UnraidSwitchBase):
    """Container control switch."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        container_id: str,
        container_name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self._container_id = container_id
        self._container_name = container_name
        self._attr_name = f"Container {container_name}"
        self._attr_icon = "mdi:docker"
        self._attr_assumed_state = False
        self._optimistic_state: bool | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_container_switch_{self._container_id}"

    def _find_container(self) -> Any | None:
        """Find the container in coordinator data."""
        data = self.coordinator.data
        if not data or not data.containers:
            return None

        for container in data.containers:
            cid = getattr(container, "id", None) or getattr(
                container, "container_id", None
            )
            if cid == self._container_id:
                return container
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
        return {
            "status": "running" if state == "running" else "stopped",
            ATTR_CONTAINER_IMAGE: getattr(container, "image", None),
            ATTR_CONTAINER_PORTS: getattr(container, "ports", None),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the container."""
        try:
            self._optimistic_state = True
            self.async_write_ha_state()

            await self.coordinator.client.start_container(self._container_id)
            _LOGGER.info("Started container: %s", self._container_name)

            await self.coordinator.async_request_refresh()

            # Wait for state confirmation (10 seconds max)
            for _ in range(20):
                await asyncio.sleep(0.5)
                container = self._find_container()
                if container:
                    state = getattr(container, "state", "").lower()
                    if state == "running":
                        self._optimistic_state = None
                        self.async_write_ha_state()
                        return
                await self.coordinator.async_request_refresh()

            _LOGGER.warning(
                "Container %s start command sent but state not confirmed after 10s",
                self._container_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to start container %s: %s", self._container_name, err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to start container {self._container_name}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the container."""
        try:
            self._optimistic_state = False
            self.async_write_ha_state()

            await self.coordinator.client.stop_container(self._container_id)
            _LOGGER.info("Stopped container: %s", self._container_name)

            await self.coordinator.async_request_refresh()

            # Wait for state confirmation (10 seconds max)
            for _ in range(20):
                await asyncio.sleep(0.5)
                container = self._find_container()
                if container:
                    state = getattr(container, "state", "").lower()
                    if state != "running":
                        self._optimistic_state = None
                        self.async_write_ha_state()
                        return
                await self.coordinator.async_request_refresh()

            _LOGGER.warning(
                "Container %s stop command sent but state not confirmed after 10s",
                self._container_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to stop container %s: %s", self._container_name, err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to stop container {self._container_name}"
            ) from err


# VM Switches


class UnraidVMSwitch(UnraidSwitchBase):
    """VM control switch."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        vm_id: str,
        vm_name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self._vm_id = vm_id
        self._vm_name = vm_name
        self._attr_name = f"VM {vm_name}"
        self._attr_icon = "mdi:desktop-tower"
        self._attr_assumed_state = False
        self._optimistic_state: bool | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_vm_switch_{self._vm_id}"

    def _find_vm(self) -> Any | None:
        """Find the VM in coordinator data."""
        data = self.coordinator.data
        if not data or not data.vms:
            return None

        for vm in data.vms:
            vid = getattr(vm, "id", None) or getattr(vm, "name", None)
            if vid == self._vm_id:
                return vm
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
        try:
            self._optimistic_state = True
            self.async_write_ha_state()

            await self.coordinator.client.start_vm(self._vm_id)
            _LOGGER.info("Started VM: %s", self._vm_name)

            await self.coordinator.async_request_refresh()

            # Wait for state confirmation (30 seconds max - VMs take longer)
            for _ in range(60):
                await asyncio.sleep(0.5)
                vm = self._find_vm()
                if vm:
                    state = getattr(vm, "state", "").lower()
                    if state == "running":
                        self._optimistic_state = None
                        self.async_write_ha_state()
                        _LOGGER.info("VM %s state confirmed as running", self._vm_name)
                        return
                await self.coordinator.async_request_refresh()

            _LOGGER.warning(
                "VM %s start command sent but state not confirmed after 30s",
                self._vm_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to start VM %s: %s", self._vm_name, err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to start VM {self._vm_name}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VM."""
        try:
            self._optimistic_state = False
            self.async_write_ha_state()

            await self.coordinator.client.stop_vm(self._vm_id)
            _LOGGER.info("Stopped VM: %s", self._vm_name)

            await self.coordinator.async_request_refresh()

            # Wait for state confirmation (30 seconds max - VMs take longer)
            for _ in range(60):
                await asyncio.sleep(0.5)
                vm = self._find_vm()
                if vm:
                    state = getattr(vm, "state", "").lower()
                    if state != "running":
                        self._optimistic_state = None
                        self.async_write_ha_state()
                        _LOGGER.info("VM %s state confirmed as stopped", self._vm_name)
                        return
                await self.coordinator.async_request_refresh()

            _LOGGER.warning(
                "VM %s stop command sent but state not confirmed after 30s",
                self._vm_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to stop VM %s: %s", self._vm_name, err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to stop VM {self._vm_name}"
            ) from err
