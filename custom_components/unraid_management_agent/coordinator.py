"""Coordinator for Unraid Management Agent."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import UnraidClient
from .api.constants import EventType
from .api.events import WebSocketEvent, parse_event
from .api.models import (
    ArrayStatus,
    CollectorStatus,
    ContainerInfo,
    DiskInfo,
    DiskSettings,
    DockerSettings,
    FanControlStatus,
    FlashDriveInfo,
    GPUInfo,
    MoverSettings,
    NetworkInterface,
    NetworkServicesStatus,
    NotificationOverview,
    NotificationsResponse,
    ParityHistory,
    ParitySchedule,
    PluginList,
    RegistrationInfo,
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
from .api.websocket import UnraidWebSocketClient
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
    fan_control: FanControlStatus | None = None
    disk_settings: DiskSettings | None = None
    mover_settings: MoverSettings | None = None
    parity_schedule: ParitySchedule | None = None
    parity_history: ParityHistory | None = None
    flash_info: FlashDriveInfo | None = None
    plugins: PluginList | None = None
    update_status: UpdateStatus | None = None
    docker_settings: DockerSettings | None = None
    vm_settings: VMSettings | None = None
    registration: RegistrationInfo | None = None
    network_services: NetworkServicesStatus | None = None


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
        self._pending_system_action: str | None = None
        self._pending_system_action_message: str | None = None
        self._pending_system_action_requested_at: datetime | None = None
        self._pending_system_action_disconnected = False

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

    @property
    def pending_system_action(self) -> str | None:
        """Return the pending reboot or shutdown action, if any."""
        return self._pending_system_action

    @property
    def pending_system_action_message(self) -> str | None:
        """Return the last action response message for the pending system action."""
        return self._pending_system_action_message

    @property
    def pending_system_action_requested_at(self) -> datetime | None:
        """Return when the current pending system action was requested."""
        return self._pending_system_action_requested_at

    def set_pending_system_action(
        self,
        action: str,
        message: str | None = None,
    ) -> None:
        """Track a reboot or shutdown action requested through the integration."""
        self._pending_system_action = action
        self._pending_system_action_message = message
        self._pending_system_action_requested_at = dt_util.utcnow()
        self._pending_system_action_disconnected = False
        self.async_update_listeners()

    def _clear_pending_system_action(self) -> None:
        """Clear any pending reboot or shutdown action state."""
        self._pending_system_action = None
        self._pending_system_action_message = None
        self._pending_system_action_requested_at = None
        self._pending_system_action_disconnected = False

    @property
    def system_status(self) -> str:
        """Return a high-level status string for the Unraid system."""
        data = self.data
        array_state = (
            getattr(data.array, "state", None) if data and data.array else None
        )
        normalized_array_state = (
            str(array_state).lower() if array_state is not None else None
        )

        if self._pending_system_action == "shutdown":
            if not self.last_update_success or data is None:
                return "server_shutdown"
            if normalized_array_state == "stopping":
                return "stopping_array"
            if normalized_array_state == "stopped":
                return "shutting_down"
            return "shutdown_requested"

        if self._pending_system_action == "reboot":
            if not self.last_update_success or data is None:
                return "server_rebooting"
            if normalized_array_state == "stopping":
                return "stopping_array"
            if normalized_array_state == "stopped":
                return "server_rebooting"
            return "reboot_requested"

        if not self.last_update_success:
            return "offline"

        if normalized_array_state == "starting":
            return "starting_array"
        if normalized_array_state == "stopping":
            return "stopping_array"
        if normalized_array_state == "stopped":
            return "array_stopped"
        return "online"

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

        collector = self.data.collectors.get_collector_by_name(collector_name)
        if collector is not None:
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

    async def _fetch[T](
        self,
        label: str,
        coro_fn: Callable[[], Coroutine[Any, Any, T]],
        *,
        suppress_404: bool = False,
    ) -> T | None:
        """Fetch data from a single API endpoint, returning *None* on failure."""
        try:
            return await coro_fn()
        except Exception as err:
            if not (suppress_404 and "404" in str(err)):
                _LOGGER.debug("Error fetching %s: %s", label, err)
            return None

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
            # Fetch all data concurrently - each method returns typed Pydantic models
            # Fetch all data concurrently - each method returns typed Pydantic models
            results: list[Any] = await asyncio.gather(
                self._fetch("system info", self.client.get_system_info),
                self._fetch("array status", self.client.get_array_status),
                self._fetch("disks", self.client.list_disks),
                self._fetch("containers", self.client.list_containers),
                self._fetch("VMs", self.client.list_vms),
                self._fetch("UPS status", self.client.get_ups_info),
                self._fetch("GPU metrics", self.client.list_gpus, suppress_404=True),
                self._fetch("network interfaces", self.client.list_network_interfaces),
                self._fetch("shares", self.client.list_shares),
                self._fetch("notifications", self.client.list_notifications),
                self._fetch(
                    "notification overview", self.client.get_notification_overview
                ),
                self._fetch("user scripts", self.client.list_user_scripts),
                self._fetch("ZFS pools", self.client.list_zfs_pools),
                self._fetch("ZFS datasets", self.client.list_zfs_datasets),
                self._fetch("ZFS snapshots", self.client.list_zfs_snapshots),
                self._fetch(
                    "ZFS ARC stats", self.client.get_zfs_arc_stats, suppress_404=True
                ),
                self._fetch("collectors status", self.client.get_collectors_status),
                self._fetch(
                    "fan control status", self.client.get_fan_status, suppress_404=True
                ),
                self._fetch("disk settings", self.client.get_disk_settings),
                self._fetch("mover settings", self.client.get_mover_settings),
                self._fetch("parity schedule", self.client.get_parity_schedule),
                self._fetch("parity history", self.client.get_parity_history),
                self._fetch("flash info", self.client.get_flash_info),
                self._fetch("plugins", self.client.list_plugins),
                self._fetch("update status", self.client.get_update_status),
                self._fetch("docker settings", self.client.get_docker_settings),
                self._fetch("VM settings", self.client.get_vm_settings),
                self._fetch("registration info", self.client.get_registration_info),
                self._fetch("network services", self.client.get_network_services),
            )

            # Unpack results with proper types (gather loses individual type info)
            system: SystemInfo | None = results[0]
            array: ArrayStatus | None = results[1]
            disks: list[DiskInfo] = results[2] or []
            containers: list[ContainerInfo] = results[3] or []
            vms: list[VMInfo] = results[4] or []
            ups: UPSInfo | None = results[5]
            gpu: list[GPUInfo] = results[6] or []
            network: list[NetworkInterface] = results[7] or []
            shares: list[ShareInfo] = results[8] or []
            notifications: NotificationsResponse | None = results[9]
            notification_overview: NotificationOverview | None = results[10]
            user_scripts: list[UserScript] = results[11] or []
            zfs_pools: list[ZFSPool] = results[12] or []
            zfs_datasets: list[ZFSDataset] = results[13] or []
            zfs_snapshots: list[ZFSSnapshot] = results[14] or []
            zfs_arc: ZFSArcStats | None = results[15]
            collectors: CollectorStatus | None = results[16]
            fan_control: FanControlStatus | None = results[17]
            disk_settings: DiskSettings | None = results[18]
            mover_settings: MoverSettings | None = results[19]
            parity_schedule: ParitySchedule | None = results[20]
            parity_history: ParityHistory | None = results[21]
            flash_info: FlashDriveInfo | None = results[22]
            plugins: PluginList | None = results[23]
            update_status: UpdateStatus | None = results[24]
            docker_settings: DockerSettings | None = results[25]
            vm_settings: VMSettings | None = results[26]
            registration: RegistrationInfo | None = results[27]
            network_services: NetworkServicesStatus | None = results[28]

            # Merge notification overview into notifications response
            if isinstance(notifications, list):
                notifications = NotificationsResponse(notifications=notifications)
            if notification_overview is not None:
                if notifications is None:
                    notifications = NotificationsResponse(
                        overview=notification_overview,
                        notifications=None,
                        timestamp=None,
                    )
                else:
                    notifications = notifications.model_copy(
                        update={"overview": notification_overview}
                    )

            # Log recovery if we were previously unavailable
            if self._unavailable_logged:
                _LOGGER.info("Connection to Unraid server restored")
                self._unavailable_logged = False

            if self._pending_system_action and self._pending_system_action_disconnected:
                _LOGGER.info(
                    "Clearing pending system %s action after server became reachable again",
                    self._pending_system_action,
                )
                self._clear_pending_system_action()

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
                fan_control=fan_control,
                disk_settings=disk_settings,
                mover_settings=mover_settings,
                parity_schedule=parity_schedule,
                parity_history=parity_history,
                flash_info=flash_info,
                plugins=plugins,
                update_status=update_status,
                docker_settings=docker_settings,
                vm_settings=vm_settings,
                registration=registration,
                network_services=network_services,
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
            if self._pending_system_action:
                self._pending_system_action_disconnected = True
            self.update_success = False
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

    def _handle_websocket_event(self, event: WebSocketEvent) -> None:
        """Handle WebSocket event and update coordinator data."""
        if not self.data:
            return

        # Update coordinator data based on event type using the vendored EventType enum
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
            current_notifications = self.data.notifications
            if isinstance(current_notifications, NotificationsResponse):
                self.data.notifications = current_notifications.model_copy(
                    update={"notifications": event.data}
                )
            else:
                self.data.notifications = NotificationsResponse(
                    notifications=event.data,
                    overview=None,
                    timestamp=None,
                )
        elif event.event_type == EventType.NOTIFICATIONS_RESPONSE:
            # Full notifications response with overview and counts
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
        elif event.event_type == EventType.NUT_STATUS_UPDATE:
            # NUT (Network UPS Tools) status is stored as UPS data
            self.data.ups = event.data
        elif event.event_type == EventType.HARDWARE_UPDATE:
            # Hardware updates contain system info (fans, temps, power)
            self.data.system = event.data
        elif event.event_type == EventType.COLLECTOR_STATE_CHANGE:
            # Collector state changes update the collectors status
            self.data.collectors = event.data
        elif event.event_type == EventType.FAN_CONTROL_UPDATE:
            self.data.fan_control = event.data

        # Notify listeners of data update without resetting the polling timer.
        # Using async_set_updated_data would cancel and reschedule the poll
        # interval, which prevents periodic full REST polls from firing if
        # WebSocket events arrive frequently (e.g., during reconnect cycles).
        self.async_update_listeners()

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
            # Create the vendored WebSocket client with auto-reconnect
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
                # Task cancellation is expected during shutdown
                pass
            self._ws_task = None
            _LOGGER.info("WebSocket client stopped")
