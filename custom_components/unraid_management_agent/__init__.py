"""The Unraid Management Agent integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from uma_api import AsyncUnraidClient, UnraidConnectionError
from uma_api.constants import EventType
from uma_api.events import WebSocketEvent, parse_event
from uma_api.models import (
    ArrayStatus,
    ContainerInfo,
    DiskInfo,
    GPUInfo,
    NetworkInterface,
    Notification,
    ShareInfo,
    SystemInfo,
    UPSInfo,
    UserScript,
    VMInfo,
    ZFSArcStats,
    ZFSDataset,
    ZFSPool,
    ZFSSnapshot,
)
from uma_api.websocket import UnraidWebSocketClient

from . import repairs
from .const import (
    CONF_ENABLE_WEBSOCKET,
    CONF_UPDATE_INTERVAL,
    DEFAULT_ENABLE_WEBSOCKET,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .entity import UnraidData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]

type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]


@dataclass
class UnraidRuntimeData:
    """Runtime data for Unraid Management Agent."""

    coordinator: UnraidDataUpdateCoordinator
    client: AsyncUnraidClient


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Unraid Management Agent integration."""
    # Register services once at integration level (not per entry)
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Set up Unraid Management Agent from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    enable_websocket = entry.options.get(
        CONF_ENABLE_WEBSOCKET, DEFAULT_ENABLE_WEBSOCKET
    )

    # Create AsyncUnraidClient from uma-api
    client = AsyncUnraidClient(host=host, port=port)

    # Test connection
    try:
        await client.health_check()
    except UnraidConnectionError as err:
        _LOGGER.error("Failed to connect to Unraid server: %s", err)
        raise ConfigEntryNotReady from err
    except Exception as err:
        _LOGGER.error("Unexpected error connecting to Unraid server: %s", err)
        raise ConfigEntryNotReady from err

    # Create coordinator
    coordinator = UnraidDataUpdateCoordinator(
        hass,
        client=client,
        update_interval=update_interval,
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

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

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
            msg = "No Unraid Management Agent entries configured"
            raise HomeAssistantError(msg)
        # Use the first entry's coordinator (services are domain-wide)
        entry: UnraidConfigEntry = entries[0]
        return entry.runtime_data.coordinator

    async def handle_container_start(call: ServiceCall) -> None:
        """Handle container start service."""
        coordinator = _get_coordinator(call)
        container_id = call.data["container_id"]
        try:
            await coordinator.client.start_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start container %s: %s", container_id, err)
            raise HomeAssistantError(f"Failed to start container: {err}") from err

    async def handle_container_stop(call: ServiceCall) -> None:
        """Handle container stop service."""
        coordinator = _get_coordinator(call)
        container_id = call.data["container_id"]
        try:
            await coordinator.client.stop_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop container %s: %s", container_id, err)
            raise HomeAssistantError(f"Failed to stop container: {err}") from err

    async def handle_container_restart(call: ServiceCall) -> None:
        """Handle container restart service."""
        coordinator = _get_coordinator(call)
        container_id = call.data["container_id"]
        try:
            await coordinator.client.restart_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to restart container %s: %s", container_id, err)
            raise HomeAssistantError(f"Failed to restart container: {err}") from err

    async def handle_container_pause(call: ServiceCall) -> None:
        """Handle container pause service."""
        coordinator = _get_coordinator(call)
        container_id = call.data["container_id"]
        try:
            await coordinator.client.pause_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to pause container %s: %s", container_id, err)
            raise HomeAssistantError(f"Failed to pause container: {err}") from err

    async def handle_container_resume(call: ServiceCall) -> None:
        """Handle container resume service."""
        coordinator = _get_coordinator(call)
        container_id = call.data["container_id"]
        try:
            await coordinator.client.unpause_container(container_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to resume container %s: %s", container_id, err)
            raise HomeAssistantError(f"Failed to resume container: {err}") from err

    async def handle_vm_start(call: ServiceCall) -> None:
        """Handle VM start service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data["vm_id"]
        try:
            await coordinator.client.start_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start VM %s: %s", vm_id, err)
            raise HomeAssistantError(f"Failed to start VM: {err}") from err

    async def handle_vm_stop(call: ServiceCall) -> None:
        """Handle VM stop service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data["vm_id"]
        try:
            await coordinator.client.stop_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop VM %s: %s", vm_id, err)
            raise HomeAssistantError(f"Failed to stop VM: {err}") from err

    async def handle_vm_restart(call: ServiceCall) -> None:
        """Handle VM restart service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data["vm_id"]
        try:
            await coordinator.client.restart_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to restart VM %s: %s", vm_id, err)
            raise HomeAssistantError(f"Failed to restart VM: {err}") from err

    async def handle_vm_pause(call: ServiceCall) -> None:
        """Handle VM pause service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data["vm_id"]
        try:
            await coordinator.client.pause_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to pause VM %s: %s", vm_id, err)
            raise HomeAssistantError(f"Failed to pause VM: {err}") from err

    async def handle_vm_resume(call: ServiceCall) -> None:
        """Handle VM resume service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data["vm_id"]
        try:
            await coordinator.client.resume_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to resume VM %s: %s", vm_id, err)
            raise HomeAssistantError(f"Failed to resume VM: {err}") from err

    async def handle_vm_hibernate(call: ServiceCall) -> None:
        """Handle VM hibernate service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data["vm_id"]
        try:
            await coordinator.client.hibernate_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to hibernate VM %s: %s", vm_id, err)
            raise HomeAssistantError(f"Failed to hibernate VM: {err}") from err

    async def handle_vm_force_stop(call: ServiceCall) -> None:
        """Handle VM force stop service."""
        coordinator = _get_coordinator(call)
        vm_id = call.data["vm_id"]
        try:
            await coordinator.client.force_stop_vm(vm_id)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to force stop VM %s: %s", vm_id, err)
            raise HomeAssistantError(f"Failed to force stop VM: {err}") from err

    async def handle_array_start(call: ServiceCall) -> None:
        """Handle array start service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.start_array()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start array: %s", err)
            raise HomeAssistantError(f"Failed to start array: {err}") from err

    async def handle_array_stop(call: ServiceCall) -> None:
        """Handle array stop service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.stop_array()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop array: %s", err)
            raise HomeAssistantError(f"Failed to stop array: {err}") from err

    async def handle_parity_check_start(call: ServiceCall) -> None:
        """Handle parity check start service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.start_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start parity check: %s", err)
            raise HomeAssistantError(f"Failed to start parity check: {err}") from err

    async def handle_parity_check_stop(call: ServiceCall) -> None:
        """Handle parity check stop service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.stop_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop parity check: %s", err)
            raise HomeAssistantError(f"Failed to stop parity check: {err}") from err

    async def handle_parity_check_pause(call: ServiceCall) -> None:
        """Handle parity check pause service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.pause_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to pause parity check: %s", err)
            raise HomeAssistantError(f"Failed to pause parity check: {err}") from err

    async def handle_parity_check_resume(call: ServiceCall) -> None:
        """Handle parity check resume service."""
        coordinator = _get_coordinator(call)
        try:
            await coordinator.client.resume_parity_check()
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to resume parity check: %s", err)
            raise HomeAssistantError(f"Failed to resume parity check: {err}") from err

    # Register all services
    hass.services.async_register(DOMAIN, "container_start", handle_container_start)
    hass.services.async_register(DOMAIN, "container_stop", handle_container_stop)
    hass.services.async_register(DOMAIN, "container_restart", handle_container_restart)
    hass.services.async_register(DOMAIN, "container_pause", handle_container_pause)
    hass.services.async_register(DOMAIN, "container_resume", handle_container_resume)

    hass.services.async_register(DOMAIN, "vm_start", handle_vm_start)
    hass.services.async_register(DOMAIN, "vm_stop", handle_vm_stop)
    hass.services.async_register(DOMAIN, "vm_restart", handle_vm_restart)
    hass.services.async_register(DOMAIN, "vm_pause", handle_vm_pause)
    hass.services.async_register(DOMAIN, "vm_resume", handle_vm_resume)
    hass.services.async_register(DOMAIN, "vm_hibernate", handle_vm_hibernate)
    hass.services.async_register(DOMAIN, "vm_force_stop", handle_vm_force_stop)

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


class UnraidDataUpdateCoordinator(DataUpdateCoordinator[UnraidData]):
    """Class to manage fetching Unraid data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncUnraidClient,
        update_interval: int,
        enable_websocket: bool,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.enable_websocket = enable_websocket
        self._ws_client: UnraidWebSocketClient | None = None
        self._unavailable_logged = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> UnraidData:
        """
        Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Fetch all data - each method returns typed Pydantic models
            system: SystemInfo | None = None
            array: ArrayStatus | None = None
            disks: list[DiskInfo] = []
            containers: list[ContainerInfo] = []
            vms: list[VMInfo] = []
            ups: UPSInfo | None = None
            gpu: list[GPUInfo] = []
            network: list[NetworkInterface] = []
            shares: list[ShareInfo] = []
            notifications: list[Notification] = []
            user_scripts: list[UserScript] = []
            zfs_pools: list[ZFSPool] = []
            zfs_datasets: list[ZFSDataset] = []
            zfs_snapshots: list[ZFSSnapshot] = []
            zfs_arc: ZFSArcStats | None = None

            # Fetch system info
            try:
                system = await self.client.get_system_info()
            except Exception as err:
                _LOGGER.debug("Error fetching system info: %s", err)

            # Fetch array status
            try:
                array = await self.client.get_array_status()
            except Exception as err:
                _LOGGER.debug("Error fetching array status: %s", err)

            # Fetch disks
            try:
                disks = await self.client.list_disks()
            except Exception as err:
                _LOGGER.debug("Error fetching disks: %s", err)

            # Fetch containers
            try:
                containers = await self.client.list_containers()
            except Exception as err:
                _LOGGER.debug("Error fetching containers: %s", err)

            # Fetch VMs
            try:
                vms = await self.client.list_vms()
            except Exception as err:
                _LOGGER.debug("Error fetching VMs: %s", err)

            # Fetch UPS status
            try:
                ups = await self.client.get_ups_info()
            except Exception as err:
                _LOGGER.debug("Error fetching UPS status: %s", err)

            # Fetch GPU metrics
            try:
                gpu = await self.client.list_gpus()
            except Exception as err:
                _LOGGER.debug("Error fetching GPU metrics: %s", err)

            # Fetch network interfaces
            try:
                network = await self.client.list_network_interfaces()
            except Exception as err:
                _LOGGER.debug("Error fetching network interfaces: %s", err)

            # Fetch shares
            try:
                shares = await self.client.list_shares()
            except Exception as err:
                _LOGGER.debug("Error fetching shares: %s", err)

            # Fetch notifications
            try:
                notifications = await self.client.list_notifications()
            except Exception as err:
                _LOGGER.debug("Error fetching notifications: %s", err)

            # Fetch user scripts
            try:
                user_scripts = await self.client.list_user_scripts()
            except Exception as err:
                _LOGGER.debug("Error fetching user scripts: %s", err)

            # Fetch ZFS pools
            try:
                zfs_pools = await self.client.list_zfs_pools()
            except Exception as err:
                _LOGGER.debug("Error fetching ZFS pools: %s", err)

            # Fetch ZFS datasets
            try:
                zfs_datasets = await self.client.list_zfs_datasets()
            except Exception as err:
                _LOGGER.debug("Error fetching ZFS datasets: %s", err)

            # Fetch ZFS snapshots
            try:
                zfs_snapshots = await self.client.list_zfs_snapshots()
            except Exception as err:
                _LOGGER.debug("Error fetching ZFS snapshots: %s", err)

            # Fetch ZFS ARC stats
            try:
                zfs_arc = await self.client.get_zfs_arc_stats()
            except Exception as err:
                _LOGGER.debug("Error fetching ZFS ARC stats: %s", err)

            # Log recovery if we were previously unavailable
            if self._unavailable_logged:
                _LOGGER.info("Connection to Unraid server restored")
                self._unavailable_logged = False

            # Build data container with Pydantic models
            data = UnraidData(
                system=system,
                array=array,
                disks=disks,
                containers=containers,
                vms=vms,
                ups=ups,
                gpu=gpu,
                network=network,
                shares=shares,
                notifications=notifications,
                user_scripts=user_scripts,
                zfs_pools=zfs_pools,
                zfs_datasets=zfs_datasets,
                zfs_snapshots=zfs_snapshots,
                zfs_arc=zfs_arc,
            )

            # Check for issues and create repair flows
            await repairs.async_check_and_create_issues(self.hass, self)

            return data

        except Exception as err:
            # Log unavailable only once
            if not self._unavailable_logged:
                _LOGGER.warning("Error communicating with Unraid API: %s", err)
                self._unavailable_logged = True
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _handle_websocket_event(self, event: WebSocketEvent) -> None:
        """Handle WebSocket event and update coordinator data."""
        if not self.data:
            return

        # Update coordinator data based on event type using uma-api EventType enum
        if event.event_type == EventType.SYSTEM_UPDATE:
            self.data.system = event.data
        elif event.event_type == EventType.ARRAY_STATUS_UPDATE:
            self.data.array = event.data
        elif event.event_type == EventType.DISK_LIST_UPDATE:
            self.data.disks = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.UPS_STATUS_UPDATE:
            self.data.ups = event.data
        elif event.event_type == EventType.GPU_UPDATE:
            self.data.gpu = event.data if isinstance(event.data, list) else [event.data]
        elif event.event_type == EventType.NETWORK_LIST_UPDATE:
            self.data.network = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.CONTAINER_LIST_UPDATE:
            self.data.containers = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.VM_LIST_UPDATE:
            self.data.vms = event.data if isinstance(event.data, list) else [event.data]
        elif event.event_type == EventType.SHARE_LIST_UPDATE:
            self.data.shares = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.NOTIFICATION_UPDATE:
            self.data.notifications = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.ZFS_POOL_UPDATE:
            self.data.zfs_pools = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.ZFS_DATASET_UPDATE:
            self.data.zfs_datasets = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.ZFS_SNAPSHOT_UPDATE:
            self.data.zfs_snapshots = (
                event.data if isinstance(event.data, list) else [event.data]
            )
        elif event.event_type == EventType.ZFS_ARC_UPDATE:
            self.data.zfs_arc = event.data

        # Notify listeners of data update
        self.async_set_updated_data(self.data)

    def _handle_raw_message(self, data: dict) -> None:
        """Handle raw WebSocket message and parse to typed event."""
        try:
            event = parse_event(data)
            self._handle_websocket_event(event)
        except Exception as err:
            _LOGGER.debug("Error parsing WebSocket event: %s", err)

    async def async_start_websocket(self) -> None:
        """Start WebSocket connection for real-time updates."""
        if not self.enable_websocket:
            _LOGGER.debug("WebSocket disabled in configuration")
            return

        if self._ws_client and self._ws_client.is_connected:
            _LOGGER.debug("WebSocket already running")
            return

        try:
            # Create WebSocket client from uma-api with auto-reconnect
            self._ws_client = UnraidWebSocketClient(
                host=self.client.host,
                port=self.client.port,
                on_message=self._handle_raw_message,
                on_connect=lambda: _LOGGER.info("WebSocket connected"),
                on_disconnect=lambda: _LOGGER.warning("WebSocket disconnected"),
                auto_reconnect=True,
                reconnect_delays=[1, 2, 5, 10, 30],
                max_retries=10,
            )

            # Start the WebSocket client
            await self._ws_client.start()
            _LOGGER.info("WebSocket client started")

        except Exception as err:
            _LOGGER.error("Failed to start WebSocket client: %s", err)
            self._ws_client = None

    async def async_stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self._ws_client:
            await self._ws_client.stop()
            self._ws_client = None
            _LOGGER.info("WebSocket client stopped")
