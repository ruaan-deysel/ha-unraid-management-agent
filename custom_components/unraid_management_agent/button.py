"""Button platform for Unraid Management Agent."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .const import ERROR_CONTROL_FAILED
from .entity import UnraidEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Unraid button entities."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    entities: list[ButtonEntity] = [
        UnraidArrayStartButton(coordinator, entry),
        UnraidArrayStopButton(coordinator, entry),
        UnraidParityCheckStartButton(coordinator, entry),
        UnraidParityCheckStopButton(coordinator, entry),
    ]

    # Add user script buttons dynamically
    user_scripts = data.user_scripts if data else []
    _LOGGER.debug(
        "Creating button entities for %d user scripts", len(user_scripts or [])
    )
    for script in user_scripts or []:
        entities.append(UnraidUserScriptButton(coordinator, entry, script))

    _LOGGER.debug("Adding %d Unraid button entities", len(entities))
    async_add_entities(entities)


class UnraidButtonBase(UnraidEntity, ButtonEntity):
    """Base class for Unraid buttons."""


# Array Control Buttons


class UnraidArrayStartButton(UnraidButtonBase):
    """Array start button."""

    _attr_name = "Start Array"
    _attr_icon = "mdi:harddisk"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_array_start_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.client.start_array()
            _LOGGER.info("Array start command sent")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start array: %s", err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to start array"
            ) from err


class UnraidArrayStopButton(UnraidButtonBase):
    """Array stop button."""

    _attr_name = "Stop Array"
    _attr_icon = "mdi:harddisk"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_array_stop_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.client.stop_array()
            _LOGGER.info("Array stop command sent")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop array: %s", err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to stop array"
            ) from err


# Parity Check Control Buttons


class UnraidParityCheckStartButton(UnraidButtonBase):
    """Parity check start button."""

    _attr_name = "Start Parity Check"
    _attr_icon = "mdi:shield-check"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_check_start_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.client.start_parity_check()
            _LOGGER.info("Parity check start command sent")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start parity check: %s", err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to start parity check"
            ) from err


class UnraidParityCheckStopButton(UnraidButtonBase):
    """Parity check stop button."""

    _attr_name = "Stop Parity Check"
    _attr_icon = "mdi:shield-check"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_check_stop_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.client.stop_parity_check()
            _LOGGER.info("Parity check stop command sent")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop parity check: %s", err)
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to stop parity check"
            ) from err


# User Script Buttons


class UnraidUserScriptButton(UnraidButtonBase):
    """User script execution button."""

    _attr_icon = "mdi:script-text"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        script: Any,
    ) -> None:
        """Initialize the user script button."""
        super().__init__(coordinator, entry)
        self._script_name = getattr(script, "name", "") or ""
        self._script_description = getattr(script, "description", "") or ""
        self._attr_name = f"User Script {self._script_name}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        safe_name = re.sub(r"[^a-z0-9_]", "_", self._script_name.lower())
        return f"{self._entry.entry_id}_user_script_{safe_name}"

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
        except Exception as err:
            _LOGGER.error(
                "Failed to execute user script '%s': %s", self._script_name, err
            )
            raise HomeAssistantError(
                f"{ERROR_CONTROL_FAILED}: Failed to execute user script '{self._script_name}'"
            ) from err
