"""Coordinator for Unraid Management Agent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from uma_api import UnraidClient
from uma_api.constants import EventType
from uma_api.events import WebSocketEvent, parse_event
from uma_api.models import (
    ArrayStatus,
    CollectorStatus,
    ContainerInfo,
    DiskInfo,
    DiskSettings,
    DockerSettings,
    FlashDriveInfo,
    GPUInfo,
    MoverSettings,
    NetworkInterface,
    NotificationsResponse,
    ParityHistory,
    ParitySchedule,
    PluginList,
    ShareInfo,
    SystemInfo,
    UpdateStatus,
    UPSInfo,
    UserScript,
    VMInfo,
    VMSettings,
    ZFSArcStats,
    ZFSDataset,
    ZFSPool,
    ZFSSnapshot,
)
from uma_api.websocket import UnraidWebSocketClient

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class UnraidData:
    """Container for Unraid coordinator data."""

    system: SystemInfo | None = None
    array: ArrayStatus | None = None
    disks: list[DiskInfo] | None = None
    containers: list[ContainerInfo] | None = None
    vms: list[VMInfo] | None = None
    ups: UPSInfo | None = None
    gpu: list[GPUInfo] | None = None
    network: list[NetworkInterface] | None = None
    shares: list[ShareInfo] | None = None
    notifications: NotificationsResponse | None = None
    user_scripts: list[UserScript] | None = None
    zfs_pools: list[ZFSPool] | None = None
    zfs_datasets: list[ZFSDataset] | None = None
    zfs_snapshots: list[ZFSSnapshot] | None = None
    zfs_arc: ZFSArcStats | None = None
    collectors: CollectorStatus | None = None
    # New data for enhanced features
    disk_settings: DiskSettings | None = None
    mover_settings: MoverSettings | None = None
    parity_schedule: ParitySchedule | None = None
    parity_history: ParityHistory | None = None
    flash_info: FlashDriveInfo | None = None
    plugins: PluginList | None = None
    update_status: UpdateStatus | None = None
    docker_settings: DockerSettings | None = None
    vm_settings: VMSettings | None = None


@dataclass
class UnraidRuntimeData:
    """Runtime data for Unraid Management Agent."""

    coordinator: UnraidDataUpdateCoordinator
    client: UnraidClient


type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]


class UnraidDataUpdateCoordinator(DataUpdateCoordinator[UnraidData]):
    """Class to manage fetching Unraid data from the API."""

    config_entry: UnraidConfigEntry
    update_success: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: UnraidConfigEntry,
        client: UnraidClient,
        enable_websocket: bool,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.enable_websocket = enable_websocket
        self._ws_client: UnraidWebSocketClient | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._unavailable_logged = False

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_setup(self) -> None:
        """
        Set up the coordinator.

        This is called once during async_config_entry_first_refresh.
        Use for one-time initialization that requires async operations.

        Note: Connection health is already verified in async_setup_entry,
        so we don't need to check it again here.
        """

    @property
    def websocket_connected(self) -> bool:
        """Return True if websocket is connected."""
        return self._ws_client is not None and self._ws_client.is_connected

    def is_collector_enabled(self, collector_name: str) -> bool:
        """
        Check if a specific collector is enabled.

        Args:
            collector_name: Name of the collector (e.g., 'docker', 'vm', 'ups', 'gpu', 'zfs')

        Returns:
            True if collector is enabled or if collectors status is unavailable (default to enabled)

        """
        if not self.data or not self.data.collectors:
            # If we can't determine collector status, default to enabled
            return True

        collectors = self.data.collectors.collectors or []
        for collector in collectors:
            if getattr(collector, "name", "") == collector_name:
                return getattr(collector, "enabled", True)

        # Collector not found in list, default to enabled
        return True

    def is_docker_enabled(self) -> bool:
        """
        Check if Docker service is enabled in Unraid settings.

        Returns:
            True if Docker is enabled, False if explicitly disabled,
            or True if settings are unavailable (default to enabled)

        """
        if not self.data or not self.data.docker_settings:
            # If we can't determine, default to enabled for backwards compatibility
            return True
        return getattr(self.data.docker_settings, "enabled", True)

    def is_vm_enabled(self) -> bool:
        """
        Check if VM service is enabled in Unraid settings.

        Returns:
            True if VM service is enabled, False if explicitly disabled,
            or True if settings are unavailable (default to enabled)

        """
        if not self.data or not self.data.vm_settings:
            # If we can't determine, default to enabled for backwards compatibility
            return True
        return getattr(self.data.vm_settings, "enabled", True)

    async def _async_update_data(self) -> UnraidData:
        """
        Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.

        Note: Collector enable/disable is configured on the Unraid Management Agent
        plugin side. The integration fetches all available data and the API will
        return empty results for disabled collectors.
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
            notifications: NotificationsResponse | None = None
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
                if "404" not in str(err):
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
                if "404" not in str(err):
                    _LOGGER.debug("Error fetching ZFS ARC stats: %s", err)

            # Fetch collectors status (for filtering entities)
            collectors: CollectorStatus | None = None
            try:
                collectors = await self.client.get_collectors_status()
            except Exception as err:
                _LOGGER.debug("Error fetching collectors status: %s", err)

            # Fetch disk settings (for temperature thresholds)
            disk_settings: DiskSettings | None = None
            try:
                disk_settings = await self.client.get_disk_settings()
            except Exception as err:
                _LOGGER.debug("Error fetching disk settings: %s", err)

            # Fetch mover settings
            mover_settings: MoverSettings | None = None
            try:
                mover_settings = await self.client.get_mover_settings()
            except Exception as err:
                _LOGGER.debug("Error fetching mover settings: %s", err)

            # Fetch parity schedule
            parity_schedule: ParitySchedule | None = None
            try:
                parity_schedule = await self.client.get_parity_schedule()
            except Exception as err:
                _LOGGER.debug("Error fetching parity schedule: %s", err)

            # Fetch parity history
            parity_history: ParityHistory | None = None
            try:
                parity_history = await self.client.get_parity_history()
            except Exception as err:
                _LOGGER.debug("Error fetching parity history: %s", err)

            # Fetch flash drive info
            flash_info: FlashDriveInfo | None = None
            try:
                flash_info = await self.client.get_flash_info()
            except Exception as err:
                _LOGGER.debug("Error fetching flash info: %s", err)

            # Fetch plugins list
            plugins: PluginList | None = None
            try:
                plugins = await self.client.list_plugins()
            except Exception as err:
                _LOGGER.debug("Error fetching plugins: %s", err)

            # Fetch update status
            update_status: UpdateStatus | None = None
            try:
                update_status = await self.client.get_update_status()
            except Exception as err:
                _LOGGER.debug("Error fetching update status: %s", err)

            # Fetch docker settings (for conditional entity creation)
            docker_settings: DockerSettings | None = None
            try:
                docker_settings = await self.client.get_docker_settings()
            except Exception as err:
                _LOGGER.debug("Error fetching docker settings: %s", err)

            # Fetch VM settings (for conditional entity creation)
            vm_settings: VMSettings | None = None
            try:
                vm_settings = await self.client.get_vm_settings()
            except Exception as err:
                _LOGGER.debug("Error fetching VM settings: %s", err)

            # Log recovery if we were previously unavailable
            if self._unavailable_logged:
                _LOGGER.info("Connection to Unraid server restored")
                self._unavailable_logged = False

            # Mark update as successful
            self.update_success = True

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
                collectors=collectors,
                disk_settings=disk_settings,
                mover_settings=mover_settings,
                parity_schedule=parity_schedule,
                parity_history=parity_history,
                flash_info=flash_info,
                plugins=plugins,
                update_status=update_status,
                docker_settings=docker_settings,
                vm_settings=vm_settings,
            )

            # Check for issues and create repair flows
            from . import repairs

            await repairs.async_check_and_create_issues(self.hass, self)

            return data

        except Exception as err:
            # Log unavailable only once
            if not self._unavailable_logged:
                _LOGGER.warning("Error communicating with Unraid API: %s", err)
                self._unavailable_logged = True
            self.update_success = False
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

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
            # WebSocket notification updates come as NotificationsResponse
            self.data.notifications = event.data
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
            # Handle special case where notifications come as NotificationsResponse
            # instead of a list of Notification objects
            if (
                isinstance(data, dict)
                and "notifications" in data
                and "overview" in data
            ):
                # This is a NotificationsResponse format, store the full response
                if self.data:
                    self.data.notifications = NotificationsResponse.model_validate(data)
                    self.async_set_updated_data(self.data)
                return

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

            # Start the WebSocket client as a background task
            # The start() method blocks forever, so we run it in a task
            self._ws_task = self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self._ws_client.start(),
                name="unraid_websocket_task",
            )
            _LOGGER.info("WebSocket client started as background task")

        except Exception as err:
            _LOGGER.error("Failed to start WebSocket client: %s", err)
            self._ws_client = None

    async def async_stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self._ws_client:
            await self._ws_client.stop()
            self._ws_client = None
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
            _LOGGER.info("WebSocket client stopped")
