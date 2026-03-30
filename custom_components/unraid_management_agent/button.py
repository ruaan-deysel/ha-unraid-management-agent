"""Button platform for Unraid Management Agent."""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .const import DOMAIN
from .entity import UnraidBaseEntity, UnraidEntityDescription

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class UnraidButtonEntityDescription(
    UnraidEntityDescription,
    ButtonEntityDescription,
):
    """Description for Unraid button entities."""

    press_fn: (
        Callable[[UnraidDataUpdateCoordinator], Coroutine[Any, Any, None]] | None
    ) = None


async def _async_start_array(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Start the array."""
    await coordinator.client.start_array()
    await coordinator.async_request_refresh()


async def _async_stop_array(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Stop the array."""
    await coordinator.client.stop_array()
    await coordinator.async_request_refresh()


async def _async_start_parity_check(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Start parity check."""
    await coordinator.client.start_parity_check()
    await coordinator.async_request_refresh()


async def _async_stop_parity_check(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Stop parity check."""
    await coordinator.client.stop_parity_check()
    await coordinator.async_request_refresh()


async def _async_pause_parity_check(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Pause parity check."""
    await coordinator.client.pause_parity_check()
    await coordinator.async_request_refresh()


async def _async_resume_parity_check(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Resume parity check."""
    await coordinator.client.resume_parity_check()
    await coordinator.async_request_refresh()


async def _async_archive_all_notifications(
    coordinator: UnraidDataUpdateCoordinator,
) -> None:
    """Archive all notifications."""
    await coordinator.client.archive_all_notifications()
    await coordinator.async_request_refresh()


async def _async_shutdown_system(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Shutdown the Unraid system."""
    response = await coordinator.client.shutdown_system()
    coordinator.set_pending_system_action(
        "shutdown",
        getattr(response, "message", None),
    )
    await coordinator.async_request_refresh()


async def _async_reboot_system(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Reboot the Unraid system."""
    response = await coordinator.client.reboot_system()
    coordinator.set_pending_system_action(
        "reboot",
        getattr(response, "message", None),
    )
    await coordinator.async_request_refresh()


BUTTON_DESCRIPTIONS: tuple[UnraidButtonEntityDescription, ...] = (
    UnraidButtonEntityDescription(
        key="array_start",
        translation_key="array_start",
        icon="mdi:harddisk",
        press_fn=_async_start_array,
    ),
    UnraidButtonEntityDescription(
        key="array_stop",
        translation_key="array_stop",
        icon="mdi:harddisk",
        press_fn=_async_stop_array,
    ),
    UnraidButtonEntityDescription(
        key="parity_check_start",
        translation_key="parity_check_start",
        icon="mdi:shield-check",
        press_fn=_async_start_parity_check,
    ),
    UnraidButtonEntityDescription(
        key="parity_check_stop",
        translation_key="parity_check_stop",
        icon="mdi:shield-check",
        press_fn=_async_stop_parity_check,
    ),
    UnraidButtonEntityDescription(
        key="parity_check_pause",
        translation_key="parity_check_pause",
        icon="mdi:pause-circle",
        press_fn=_async_pause_parity_check,
    ),
    UnraidButtonEntityDescription(
        key="parity_check_resume",
        translation_key="parity_check_resume",
        icon="mdi:play-circle",
        press_fn=_async_resume_parity_check,
    ),
    UnraidButtonEntityDescription(
        key="archive_all_notifications",
        translation_key="archive_all_notifications",
        icon="mdi:archive-arrow-down",
        press_fn=_async_archive_all_notifications,
    ),
    UnraidButtonEntityDescription(
        key="system_shutdown",
        translation_key="system_shutdown",
        icon="mdi:power",
        press_fn=_async_shutdown_system,
    ),
    UnraidButtonEntityDescription(
        key="system_reboot",
        translation_key="system_reboot",
        icon="mdi:restart",
        press_fn=_async_reboot_system,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid button entities."""
    coordinator = entry.runtime_data.coordinator

    entities: list[ButtonEntity] = [
        UnraidButtonEntity(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
        if description.supported_fn(coordinator)
    ]

    # Add user script buttons dynamically
    data = coordinator.data
    user_scripts = data.user_scripts if data else []
    _LOGGER.debug(
        "Creating button entities for %d user scripts", len(user_scripts or [])
    )
    for script in user_scripts or []:
        entities.append(UnraidUserScriptButton(coordinator, script))

    # Container restart buttons - only if docker collector is enabled
    if coordinator.is_collector_enabled("docker") and coordinator.is_docker_enabled():
        containers = data.containers if data else []
        seen_container_names: set[str] = set()
        for container in containers or []:
            container_name = getattr(container, "name", None)
            if container_name and container_name not in seen_container_names:
                seen_container_names.add(container_name)
                entities.append(
                    UnraidContainerRestartButton(coordinator, container_name)
                )

    # VM control buttons - only if vm collector is enabled
    if coordinator.is_collector_enabled("vm") and coordinator.is_vm_enabled():
        vms = data.vms if data else []
        seen_vm_identifiers: set[str] = set()
        for vm in vms or []:
            vm_identifier = getattr(vm, "id", None) or getattr(vm, "name", None)
            vm_name = getattr(vm, "name", None)
            if vm_identifier and vm_name and vm_identifier not in seen_vm_identifiers:
                seen_vm_identifiers.add(vm_identifier)
                entities.append(
                    UnraidVMForceStopButton(coordinator, vm_identifier, vm_name)
                )
                entities.append(
                    UnraidVMRestartButton(coordinator, vm_identifier, vm_name)
                )
                entities.append(
                    UnraidVMPauseButton(coordinator, vm_identifier, vm_name)
                )
                entities.append(
                    UnraidVMResumeButton(coordinator, vm_identifier, vm_name)
                )

    _LOGGER.debug("Adding %d Unraid button entities", len(entities))
    async_add_entities(entities)


class UnraidButtonEntity(UnraidBaseEntity, ButtonEntity):
    """Unraid button entity."""

    entity_description: UnraidButtonEntityDescription

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entity_description: UnraidButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.press_fn is None:
            return
        try:
            await self.entity_description.press_fn(self.coordinator)
        except Exception as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="button_error",
                translation_placeholders={
                    "key": self.entity_description.key,
                },
            ) from exc


class UnraidUserScriptButton(UnraidBaseEntity, ButtonEntity):
    """User script execution button."""

    _attr_icon = "mdi:script-text"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        script: Any,
    ) -> None:
        """Initialize the user script button."""
        self._script_name = getattr(script, "name", "") or ""
        self._script_description = getattr(script, "description", "") or ""
        safe_name = re.sub(r"[^a-z0-9_]", "_", self._script_name.lower())
        super().__init__(coordinator, f"user_script_{safe_name}")
        self._attr_translation_key = "user_script"
        self._attr_translation_placeholders = {"script_name": self._script_name}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "script_name": self._script_name,
            "description": self._script_description or "No description",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.client.execute_user_script(self._script_name)
            _LOGGER.info("User script '%s' execution started", self._script_name)
        except Exception as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="user_script_error",
                translation_placeholders={
                    "script_name": self._script_name,
                },
            ) from exc


class UnraidContainerRestartButton(UnraidBaseEntity, ButtonEntity):
    """Container restart button."""

    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        container_name: str,
    ) -> None:
        """Initialize the container restart button."""
        self._container_name = container_name
        safe_name = slugify(container_name)
        super().__init__(coordinator, f"container_{safe_name}_restart")
        self._attr_translation_key = "container_restart"
        self._attr_translation_placeholders = {"container_name": container_name}

    def _find_container(self) -> Any | None:
        """Find the container by name."""
        data = self.coordinator.data
        if not data or not data.containers:
            return None
        for container in data.containers:
            if getattr(container, "name", None) == self._container_name:
                return container
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._find_container() is not None

    async def async_press(self) -> None:
        """Restart the container."""
        container = self._find_container()
        if container is None:
            return
        container_id = getattr(container, "id", None) or self._container_name
        try:
            await self.coordinator.client.restart_container(container_id)
        except Exception as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_restart_error",
                translation_placeholders={
                    "container_name": self._container_name,
                },
            ) from exc


class _UnraidVMButtonBase(UnraidBaseEntity, ButtonEntity):
    """Base class for VM control buttons."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        vm_identifier: str,
        vm_name: str,
        key_suffix: str,
    ) -> None:
        """Initialize the VM button."""
        self._vm_identifier = vm_identifier
        self._vm_name = vm_name
        short_hash = hashlib.md5(
            vm_identifier.encode(), usedforsecurity=False
        ).hexdigest()[:8]
        safe_name = slugify(vm_name)
        super().__init__(coordinator, f"vm_{safe_name}_{short_hash}_{key_suffix}")

    def _find_vm(self) -> Any | None:
        """Find the VM by id or name."""
        data = self.coordinator.data
        if not data or not data.vms:
            return None
        for vm in data.vms:
            if getattr(vm, "id", None) == self._vm_identifier:
                return vm
            if getattr(vm, "name", None) == self._vm_identifier:
                return vm
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._find_vm() is not None


class UnraidVMForceStopButton(_UnraidVMButtonBase):
    """VM force stop button."""

    _attr_icon = "mdi:stop"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        vm_identifier: str,
        vm_name: str,
    ) -> None:
        """Initialize the VM force stop button."""
        super().__init__(coordinator, vm_identifier, vm_name, "force_stop")
        self._attr_translation_key = "vm_force_stop"
        self._attr_translation_placeholders = {"vm_name": vm_name}

    async def async_press(self) -> None:
        """Force stop the VM."""
        try:
            await self.coordinator.client.force_stop_vm(self._vm_identifier)
        except Exception as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_force_stop_error",
                translation_placeholders={"vm_name": self._vm_name},
            ) from exc


class UnraidVMRestartButton(_UnraidVMButtonBase):
    """VM restart button."""

    _attr_icon = "mdi:restart"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        vm_identifier: str,
        vm_name: str,
    ) -> None:
        """Initialize the VM restart button."""
        super().__init__(coordinator, vm_identifier, vm_name, "restart")
        self._attr_translation_key = "vm_restart_button"
        self._attr_translation_placeholders = {"vm_name": vm_name}

    async def async_press(self) -> None:
        """Restart the VM."""
        try:
            await self.coordinator.client.restart_vm(self._vm_identifier)
        except Exception as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_restart_error",
                translation_placeholders={"vm_name": self._vm_name},
            ) from exc


class UnraidVMPauseButton(_UnraidVMButtonBase):
    """VM pause button."""

    _attr_icon = "mdi:pause"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        vm_identifier: str,
        vm_name: str,
    ) -> None:
        """Initialize the VM pause button."""
        super().__init__(coordinator, vm_identifier, vm_name, "pause")
        self._attr_translation_key = "vm_pause"
        self._attr_translation_placeholders = {"vm_name": vm_name}

    async def async_press(self) -> None:
        """Pause the VM."""
        try:
            await self.coordinator.client.pause_vm(self._vm_identifier)
        except Exception as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_pause_error",
                translation_placeholders={"vm_name": self._vm_name},
            ) from exc


class UnraidVMResumeButton(_UnraidVMButtonBase):
    """VM resume button."""

    _attr_icon = "mdi:play"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        vm_identifier: str,
        vm_name: str,
    ) -> None:
        """Initialize the VM resume button."""
        super().__init__(coordinator, vm_identifier, vm_name, "resume")
        self._attr_translation_key = "vm_resume"
        self._attr_translation_placeholders = {"vm_name": vm_name}

    async def async_press(self) -> None:
        """Resume the VM."""
        try:
            await self.coordinator.client.resume_vm(self._vm_identifier)
        except Exception as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_resume_error",
                translation_placeholders={"vm_name": self._vm_name},
            ) from exc
