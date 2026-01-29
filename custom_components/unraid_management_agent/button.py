"""Button platform for Unraid Management Agent."""

from __future__ import annotations

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


async def _async_shutdown_system(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Shutdown the Unraid system."""
    await coordinator.client.shutdown_system()


async def _async_reboot_system(coordinator: UnraidDataUpdateCoordinator) -> None:
    """Reboot the Unraid system."""
    await coordinator.client.reboot_system()


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
