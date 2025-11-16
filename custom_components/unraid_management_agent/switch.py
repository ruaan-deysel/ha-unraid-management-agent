"""Switch platform for Unraid Management Agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UnraidDataUpdateCoordinator
from .const import (
    ATTR_CONTAINER_IMAGE,
    ATTR_CONTAINER_PORTS,
    ATTR_VM_MEMORY,
    ATTR_VM_VCPUS,
    DOMAIN,
    ERROR_CONTROL_FAILED,
    ICON_CONTAINER,
    ICON_VM,
    KEY_CONTAINERS,
    KEY_SYSTEM,
    KEY_VMS,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Unraid switch entities."""
    coordinator: UnraidDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []

    # Container switches
    for container in coordinator.data.get(KEY_CONTAINERS, []):
        container_id = container.get("id") or container.get("container_id")
        container_name = container.get("name", "unknown")
        if container_id:
            entities.append(
                UnraidContainerSwitch(coordinator, entry, container_id, container_name)
            )

    # VM switches
    for vm in coordinator.data.get(KEY_VMS, []):
        vm_id = vm.get("id") or vm.get("name")
        vm_name = vm.get("name", "unknown")
        if vm_id:
            entities.append(UnraidVMSwitch(coordinator, entry, vm_id, vm_name))

    async_add_entities(entities)


class UnraidSwitchBase(CoordinatorEntity, SwitchEntity):
    """Base class for Unraid switches."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._entry = entry

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        system_data = self.coordinator.data.get(KEY_SYSTEM, {})
        hostname = system_data.get("hostname", "Unraid")
        version = system_data.get("version", "Unknown")
        host = self._entry.data.get(CONF_HOST, "")

        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": hostname,
            "manufacturer": MANUFACTURER,
            "model": f"Unraid {version}",
            "sw_version": version,
            "configuration_url": f"http://{host}",
        }


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
        self._attr_icon = ICON_CONTAINER
        # Enable optimistic mode to prevent UI state jumping
        self._attr_assumed_state = False
        self._optimistic_state: bool | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_container_switch_{self._container_id}"

    @property
    def is_on(self) -> bool:
        """Return true if container is running."""
        # Use optimistic state if set (during state transitions)
        if self._optimistic_state is not None:
            return self._optimistic_state

        # Otherwise use actual state from coordinator
        for container in self.coordinator.data.get(KEY_CONTAINERS, []):
            cid = container.get("id") or container.get("container_id")
            if cid == self._container_id:
                state = container.get("state", "").lower()
                return state == "running"
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for container in self.coordinator.data.get(KEY_CONTAINERS, []):
            cid = container.get("id") or container.get("container_id")
            if cid == self._container_id:
                state = container.get("state", "").lower()
                return {
                    "status": "running" if state == "running" else "stopped",
                    ATTR_CONTAINER_IMAGE: container.get("image"),
                    ATTR_CONTAINER_PORTS: container.get("ports"),
                }
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the container."""
        try:
            # Set optimistic state immediately to prevent UI jumping
            self._optimistic_state = True
            self.async_write_ha_state()

            await self.coordinator.client.start_container(self._container_id)
            _LOGGER.info("Started container: %s", self._container_name)

            # Request immediate update
            await self.coordinator.async_request_refresh()

            # Wait for state to actually change or timeout after 10 seconds
            # This prevents the switch from bouncing back to "off" before the container starts
            for _ in range(20):  # 20 attempts * 0.5s = 10 seconds max
                await asyncio.sleep(0.5)
                # Check if actual state matches optimistic state
                for container in self.coordinator.data.get(KEY_CONTAINERS, []):
                    cid = container.get("id") or container.get("container_id")
                    if cid == self._container_id:
                        state = container.get("state", "").lower()
                        if state == "running":
                            # State confirmed, clear optimistic state
                            self._optimistic_state = None
                            self.async_write_ha_state()
                            return
                # Trigger another refresh to get latest state
                await self.coordinator.async_request_refresh()

            # Timeout reached, clear optimistic state anyway
            _LOGGER.warning(
                "Container %s start command sent but state not confirmed after 10s",
                self._container_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            # Clear optimistic state on error
            self._optimistic_state = None
            self.async_write_ha_state()

            _LOGGER.error("Failed to start container %s: %s", self._container_name, err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to start container {self._container_name}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the container."""
        try:
            # Set optimistic state immediately to prevent UI jumping
            self._optimistic_state = False
            self.async_write_ha_state()

            await self.coordinator.client.stop_container(self._container_id)
            _LOGGER.info("Stopped container: %s", self._container_name)

            # Request immediate update
            await self.coordinator.async_request_refresh()

            # Wait for state to actually change or timeout after 10 seconds
            # This prevents the switch from bouncing back to "on" before the container stops
            for _ in range(20):  # 20 attempts * 0.5s = 10 seconds max
                await asyncio.sleep(0.5)
                # Check if actual state matches optimistic state
                for container in self.coordinator.data.get(KEY_CONTAINERS, []):
                    cid = container.get("id") or container.get("container_id")
                    if cid == self._container_id:
                        state = container.get("state", "").lower()
                        if state != "running":
                            # State confirmed, clear optimistic state
                            self._optimistic_state = None
                            self.async_write_ha_state()
                            return
                # Trigger another refresh to get latest state
                await self.coordinator.async_request_refresh()

            # Timeout reached, clear optimistic state anyway
            _LOGGER.warning(
                "Container %s stop command sent but state not confirmed after 10s",
                self._container_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            # Clear optimistic state on error
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
        self._attr_icon = ICON_VM
        # Enable optimistic mode to prevent UI state jumping
        self._attr_assumed_state = False
        self._optimistic_state: bool | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_vm_switch_{self._vm_id}"

    @property
    def is_on(self) -> bool:
        """Return true if VM is running."""
        # Use optimistic state if set (during state transitions)
        if self._optimistic_state is not None:
            return self._optimistic_state

        # Otherwise use actual state from coordinator
        for vm in self.coordinator.data.get(KEY_VMS, []):
            vid = vm.get("id") or vm.get("name")
            if vid == self._vm_id:
                state = vm.get("state", "").lower()
                return state == "running"
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        for vm in self.coordinator.data.get(KEY_VMS, []):
            vid = vm.get("id") or vm.get("name")
            if vid == self._vm_id:
                state = vm.get("state", "").lower()

                # Format CPU percentages
                guest_cpu = vm.get("guest_cpu_percent")
                host_cpu = vm.get("host_cpu_percent")
                guest_cpu_str = f"{guest_cpu:.1f}%" if guest_cpu is not None else "0.0%"
                host_cpu_str = f"{host_cpu:.1f}%" if host_cpu is not None else "0.0%"

                # Format memory display
                memory_display = vm.get("memory_display", "Unknown")

                # Format disk I/O
                disk_read = vm.get("disk_read_bytes", 0)
                disk_write = vm.get("disk_write_bytes", 0)
                disk_io_str = f"Rd: {self._format_bytes(disk_read)}/s Wr: {self._format_bytes(disk_write)}/s"

                return {
                    "status": "running" if state == "running" else "stopped",
                    ATTR_VM_VCPUS: vm.get(
                        "cpu_count"
                    ),  # Fixed: use cpu_count instead of vcpus
                    "guest_cpu": guest_cpu_str,
                    "host_cpu": host_cpu_str,
                    ATTR_VM_MEMORY: memory_display,
                    "disk_io": disk_io_str,
                }
        return {}

    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes into human-readable string."""
        if bytes_value == 0:
            return "0B"

        units = ["B", "KiB", "MiB", "GiB", "TiB"]
        unit_index = 0
        value = float(bytes_value)

        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1

        # Format with appropriate precision
        if value < 10:
            return f"{value:.1f}{units[unit_index]}"
        return f"{value:.0f}{units[unit_index]}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the VM."""
        try:
            # Set optimistic state immediately to prevent UI jumping
            self._optimistic_state = True
            self.async_write_ha_state()

            await self.coordinator.client.start_vm(self._vm_id)
            _LOGGER.info("Started VM: %s", self._vm_name)

            # Request immediate update
            await self.coordinator.async_request_refresh()

            # Wait for state to actually change or timeout after 30 seconds
            # VMs take longer to start than containers, so we use a longer timeout
            for _ in range(60):  # 60 attempts * 0.5s = 30 seconds max
                await asyncio.sleep(0.5)
                # Check if actual state matches optimistic state
                for vm in self.coordinator.data.get(KEY_VMS, []):
                    vid = vm.get("id") or vm.get("name")
                    if vid == self._vm_id:
                        state = vm.get("state", "").lower()
                        if state == "running":
                            # State confirmed, clear optimistic state
                            self._optimistic_state = None
                            self.async_write_ha_state()
                            _LOGGER.info(
                                "VM %s state confirmed as running", self._vm_name
                            )
                            return
                # Trigger another refresh to get latest state
                await self.coordinator.async_request_refresh()

            # Timeout reached, clear optimistic state anyway
            _LOGGER.warning(
                "VM %s start command sent but state not confirmed after 30s",
                self._vm_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            # Clear optimistic state on error
            self._optimistic_state = None
            self.async_write_ha_state()

            _LOGGER.error("Failed to start VM %s: %s", self._vm_name, err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to start VM {self._vm_name}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VM."""
        try:
            # Set optimistic state immediately to prevent UI jumping
            self._optimistic_state = False
            self.async_write_ha_state()

            await self.coordinator.client.stop_vm(self._vm_id)
            _LOGGER.info("Stopped VM: %s", self._vm_name)

            # Request immediate update
            await self.coordinator.async_request_refresh()

            # Wait for state to actually change or timeout after 30 seconds
            # VMs take longer to stop than containers, so we use a longer timeout
            for _ in range(60):  # 60 attempts * 0.5s = 30 seconds max
                await asyncio.sleep(0.5)
                # Check if actual state matches optimistic state
                for vm in self.coordinator.data.get(KEY_VMS, []):
                    vid = vm.get("id") or vm.get("name")
                    if vid == self._vm_id:
                        state = vm.get("state", "").lower()
                        if state != "running":
                            # State confirmed, clear optimistic state
                            self._optimistic_state = None
                            self.async_write_ha_state()
                            _LOGGER.info(
                                "VM %s state confirmed as stopped", self._vm_name
                            )
                            return
                # Trigger another refresh to get latest state
                await self.coordinator.async_request_refresh()

            # Timeout reached, clear optimistic state anyway
            _LOGGER.warning(
                "VM %s stop command sent but state not confirmed after 30s",
                self._vm_name,
            )
            self._optimistic_state = None
            self.async_write_ha_state()
        except Exception as err:
            # Clear optimistic state on error
            self._optimistic_state = None
            self.async_write_ha_state()

            _LOGGER.error("Failed to stop VM %s: %s", self._vm_name, err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to stop VM {self._vm_name}"
            ) from err
