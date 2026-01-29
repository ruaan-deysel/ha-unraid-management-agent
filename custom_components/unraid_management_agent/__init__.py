"""The Unraid Management Agent integration."""

from __future__ import annotations

import logging
from typing import Final

import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from uma_api import UnraidClient, UnraidConnectionError
from uma_api.websocket import UnraidWebSocketClient

from .const import (
    CONF_ENABLE_WEBSOCKET,
    DEFAULT_ENABLE_WEBSOCKET,
    DOMAIN,
)
from .coordinator import (
    UnraidConfigEntry,
    UnraidDataUpdateCoordinator,
    UnraidRuntimeData,
)

# Service field constants
ATTR_CONTAINER_ID: Final = "container_id"
ATTR_VM_ID: Final = "vm_id"

# Service schemas
SERVICE_CONTAINER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONTAINER_ID): cv.string,
    }
)

SERVICE_VM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VM_ID): cv.string,
    }
)

# Re-export for backwards compatibility and for tests to patch
__all__ = [
    "ATTR_CONTAINER_ID",
    "ATTR_VM_ID",
    "UnraidClient",
    "UnraidConfigEntry",
    "UnraidDataUpdateCoordinator",
    "UnraidRuntimeData",
    "UnraidWebSocketClient",
]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Unraid Management Agent integration."""
    # Register services once at integration level (not per entry)
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Set up Unraid Management Agent from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    enable_websocket = entry.options.get(
        CONF_ENABLE_WEBSOCKET, DEFAULT_ENABLE_WEBSOCKET
    )

    # Create UnraidClient using Home Assistant's shared client session (inject-websession)
    session = async_get_clientsession(hass)
    client = UnraidClient(host=host, port=port, session=session)

    # Test connection
    try:
        await client.health_check()
    except UnraidConnectionError as err:
        _LOGGER.error("Failed to connect to Unraid server: %s", err)
        raise ConfigEntryNotReady from err
    except Exception as err:
        _LOGGER.error("Unexpected error connecting to Unraid server: %s", err)
        raise ConfigEntryNotReady from err

    # Create coordinator (now passing entry as per HA best practice)
    coordinator = UnraidDataUpdateCoordinator(
        hass,
        entry=entry,
        client=client,
        enable_websocket=enable_websocket,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data using the new pattern
    entry.runtime_data = UnraidRuntimeData(coordinator=coordinator, client=client)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start WebSocket for real-time updates
    if enable_websocket:
        await coordinator.async_start_websocket()

    # Note: We use OptionsFlowWithReload, so no need for manual update listener
    # The reload is handled automatically by Home Assistant

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Stop WebSocket if running
        await entry.runtime_data.coordinator.async_stop_websocket()
        # Close the client session
        await entry.runtime_data.client.close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Unraid Management Agent."""
    # Check if services are already registered
    if hass.services.has_service(DOMAIN, "container_start"):
        return

    def _get_coordinator(call: ServiceCall) -> UnraidDataUpdateCoordinator:
        """Get coordinator from any config entry."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_config_entries",
            )
        # Use the first entry's coordinator (services are domain-wide)
        entry: UnraidConfigEntry = entries[0]
        return entry.runtime_data.coordinator

    async def handle_container_start(call: ServiceCall) -> None:
        """Handle container start service."""
        coordinator = _get_coordinator(call)
        container_id = call.data[ATTR_CONTAINER_ID]
        try:
            await coordinator.client.start_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start container %s: %s", container_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_start_failed",
                translation_placeholders={"container_id": container_id},
            ) from err

    async def handle_container_stop(call: ServiceCall) -> None:
        """Handle container stop service."""
        coordinator = _get_coordinator(call)
        container_id = call.data[ATTR_CONTAINER_ID]
        try:
            await coordinator.client.stop_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop container %s: %s", container_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_stop_failed",
                translation_placeholders={"container_id": container_id},
            ) from err

    async def handle_container_restart(call: ServiceCall) -> None:
        """Handle container restart service."""
        coordinator = _get_coordinator(call)
        container_id = call.data[ATTR_CONTAINER_ID]
        try:
            await coordinator.client.restart_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to restart container %s: %s", container_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_restart_failed",
                translation_placeholders={"container_id": container_id},
            ) from err

    async def handle_container_pause(call: ServiceCall) -> None:
        """Handle container pause service."""
        coordinator = _get_coordinator(call)
        container_id = call.data[ATTR_CONTAINER_ID]
        try:
            await coordinator.client.pause_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to pause container %s: %s", container_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_pause_failed",
                translation_placeholders={"container_id": container_id},
            ) from err

    async def handle_container_resume(call: ServiceCall) -> None:
        """Handle container resume service."""
        coordinator = _get_coordinator(call)
        container_id = call.data[ATTR_CONTAINER_ID]
        try:
            await coordinator.client.unpause_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to resume container %s: %s", container_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="container_resume_failed",
                translation_placeholders={"container_id": container_id},
            ) from err

    async def handle_vm_start(call: ServiceCall) -> None:
        """Handle VM start service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data[ATTR_VM_ID]
        try:
            await coordinator.client.start_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start VM %s: %s", vm_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_start_failed",
                translation_placeholders={"vm_id": vm_id},
            ) from err

    async def handle_vm_stop(call: ServiceCall) -> None:
        """Handle VM stop service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data[ATTR_VM_ID]
        try:
            await coordinator.client.stop_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop VM %s: %s", vm_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_stop_failed",
                translation_placeholders={"vm_id": vm_id},
            ) from err

    async def handle_vm_restart(call: ServiceCall) -> None:
        """Handle VM restart service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data[ATTR_VM_ID]
        try:
            await coordinator.client.restart_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to restart VM %s: %s", vm_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_restart_failed",
                translation_placeholders={"vm_id": vm_id},
            ) from err

    async def handle_vm_pause(call: ServiceCall) -> None:
        """Handle VM pause service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data[ATTR_VM_ID]
        try:
            await coordinator.client.pause_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to pause VM %s: %s", vm_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_pause_failed",
                translation_placeholders={"vm_id": vm_id},
            ) from err

    async def handle_vm_resume(call: ServiceCall) -> None:
        """Handle VM resume service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data[ATTR_VM_ID]
        try:
            await coordinator.client.resume_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to resume VM %s: %s", vm_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_resume_failed",
                translation_placeholders={"vm_id": vm_id},
            ) from err

    async def handle_vm_hibernate(call: ServiceCall) -> None:
        """Handle VM hibernate service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data[ATTR_VM_ID]
        try:
            await coordinator.client.hibernate_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to hibernate VM %s: %s", vm_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_hibernate_failed",
                translation_placeholders={"vm_id": vm_id},
            ) from err

    async def handle_vm_force_stop(call: ServiceCall) -> None:
        """Handle VM force stop service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data[ATTR_VM_ID]
        try:
            await coordinator.client.force_stop_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to force stop VM %s: %s", vm_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vm_force_stop_failed",
                translation_placeholders={"vm_id": vm_id},
            ) from err

    async def handle_array_start(call: ServiceCall) -> None:
        """Handle array start service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.start_array()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start array: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="array_start_failed",
            ) from err

    async def handle_array_stop(call: ServiceCall) -> None:
        """Handle array stop service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.stop_array()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop array: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="array_stop_failed",
            ) from err

    async def handle_parity_check_start(call: ServiceCall) -> None:
        """Handle parity check start service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.start_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start parity check: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parity_check_start_failed",
            ) from err

    async def handle_parity_check_stop(call: ServiceCall) -> None:
        """Handle parity check stop service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.stop_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop parity check: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parity_check_stop_failed",
            ) from err

    async def handle_parity_check_pause(call: ServiceCall) -> None:
        """Handle parity check pause service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.pause_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to pause parity check: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parity_check_pause_failed",
            ) from err

    async def handle_parity_check_resume(call: ServiceCall) -> None:
        """Handle parity check resume service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.resume_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to resume parity check: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="parity_check_resume_failed",
            ) from err

    # Register all services with proper schemas
    hass.services.async_register(
        DOMAIN,
        "container_start",
        handle_container_start,
        schema=SERVICE_CONTAINER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, "container_stop", handle_container_stop, schema=SERVICE_CONTAINER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "container_restart",
        handle_container_restart,
        schema=SERVICE_CONTAINER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "container_pause",
        handle_container_pause,
        schema=SERVICE_CONTAINER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "container_resume",
        handle_container_resume,
        schema=SERVICE_CONTAINER_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN, "vm_start", handle_vm_start, schema=SERVICE_VM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "vm_stop", handle_vm_stop, schema=SERVICE_VM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "vm_restart", handle_vm_restart, schema=SERVICE_VM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "vm_pause", handle_vm_pause, schema=SERVICE_VM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "vm_resume", handle_vm_resume, schema=SERVICE_VM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "vm_hibernate", handle_vm_hibernate, schema=SERVICE_VM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "vm_force_stop", handle_vm_force_stop, schema=SERVICE_VM_SCHEMA
    )

    hass.services.async_register(DOMAIN, "array_start", handle_array_start)
    hass.services.async_register(DOMAIN, "array_stop", handle_array_stop)

    hass.services.async_register(
        DOMAIN, "parity_check_start", handle_parity_check_start
    )
    hass.services.async_register(DOMAIN, "parity_check_stop", handle_parity_check_stop)
    hass.services.async_register(
        DOMAIN, "parity_check_pause", handle_parity_check_pause
    )
    hass.services.async_register(
        DOMAIN, "parity_check_resume", handle_parity_check_resume
    )

    _LOGGER.info("Registered %d services for Unraid Management Agent", 18)
