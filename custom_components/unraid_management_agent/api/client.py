"""Async client for the Unraid Management Agent API using aiohttp."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from .exceptions import (
    UnraidAPIError,
    UnraidConflictError,
    UnraidConnectionError,
    UnraidNotFoundError,
    UnraidValidationError,
)
from .models import (
    ActionResponse,
    AlertHistoryResponse,
    AlertRule,
    AlertsStatusResponse,
    AlertStatus,
    ArrayStatus,
    BaseboardInfo,
    BIOSInfo,
    CollectorInfo,
    CollectorStatus,
    ContainerBulkUpdateResult,
    ContainerInfo,
    ContainerLogs,
    ContainerSizeInfo,
    ContainerUpdateInfo,
    ContainerUpdateResult,
    ContainerUpdatesResult,
    CPUCacheInfo,
    CPUHardwareInfo,
    DiskInfo,
    DiskSettings,
    DockerSettings,
    FlashDriveInfo,
    GPUInfo,
    HardwareFullInfo,
    HealthCheck,
    HealthCheckHistoryResponse,
    HealthChecksStatusResponse,
    HealthCheckStatus,
    HealthStatus,
    LogContent,
    LogList,
    MemoryArrayInfo,
    MemoryDeviceInfo,
    MoverSettings,
    MQTTPublishResponse,
    MQTTStatus,
    MQTTTestResponse,
    NetworkAccessUrls,
    NetworkConfig,
    NetworkInterface,
    NetworkServicesStatus,
    Notification,
    NotificationOverview,
    NotificationsResponse,
    NUTInfo,
    ParityHistory,
    ParitySchedule,
    PluginBulkUpdateResult,
    PluginList,
    PluginUpdateResult,
    PluginUpdatesResult,
    ProcessList,
    RegistrationInfo,
    RemoteSharesResponse,
    ServiceStatus,
    ShareConfig,
    ShareInfo,
    SystemInfo,
    SystemServiceList,
    SystemSettings,
    UnassignedDevicesResponse,
    UnassignedInfo,
    UpdateStatus,
    UPSInfo,
    UserScript,
    UserScriptExecuteResponse,
    VMInfo,
    VMSettings,
    VMSnapshotList,
    ZFSArcStats,
    ZFSDataset,
    ZFSPool,
    ZFSSnapshot,
)

if TYPE_CHECKING:
    import aiohttp


class UnraidClient:
    """
    Async client for interacting with the Unraid Management Agent API.

    This client uses aiohttp for async HTTP requests and is designed for
    use with Home Assistant and other async applications.

    Args:
        host: The Unraid server hostname or IP address
        port: The API port (default: 8043)
        timeout: Request timeout in seconds (default: 10)
        verify_ssl: Whether to verify SSL certificates (default: True)
        use_https: Whether to use HTTPS instead of HTTP (default: False)
        session: Optional aiohttp.ClientSession for session reuse

    Example:
        >>> async with UnraidClient("192.168.1.100") as client:
        ...     system_info = await client.get_system_info()
        ...     print(system_info.hostname)

        >>> # With existing session
        >>> async with aiohttp.ClientSession() as session:
        ...     client = UnraidClient("192.168.1.100", session=session)
        ...     system_info = await client.get_system_info()

    """

    def __init__(
        self,
        host: str,
        port: int = 8043,
        timeout: int = 10,
        verify_ssl: bool = True,
        use_https: bool = False,
        session: aiohttp.ClientSession | None = None,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.use_https = use_https
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{host}:{port}/api/v1"

        self._session: aiohttp.ClientSession | None = session
        self._owns_session = session is None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure a session exists, creating one if necessary."""
        if self._session is None or self._session.closed:
            import ssl

            import aiohttp

            # Create SSL context if needed
            ssl_context: ssl.SSLContext | bool = True
            if not self.verify_ssl:
                ssl_context = False

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            self._owns_session = True

        return self._session

    async def close(self) -> None:
        """
        Close the client session.

        This releases the connection pool resources. Only closes the session
        if it was created by this client (not provided externally).
        """
        if self._session and self._owns_session:
            await self._session.close()

    async def __aenter__(self) -> UnraidClient:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        await self.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Make an async request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response data

        Raises:
            UnraidConnectionError: If unable to connect to the API
            UnraidNotFoundError: If the resource is not found
            UnraidConflictError: If there's a resource conflict
            UnraidValidationError: If request validation fails
            UnraidAPIError: For other API errors

        """
        import aiohttp

        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        session = await self._ensure_session()

        try:
            async with session.request(
                method=method,
                url=url,
                json=data,
                params=params,
            ) as response:
                # Handle successful responses
                if response.status == 200:
                    return await response.json()

                # Handle error responses
                try:
                    error_data = await response.json()
                    error_message = error_data.get("message", "Unknown error")
                    error_code = error_data.get("error_code", "UNKNOWN_ERROR")
                except ValueError, aiohttp.ContentTypeError:
                    error_message = await response.text() or f"HTTP {response.status}"
                    error_code = "UNKNOWN_ERROR"

                # Raise specific exceptions based on status code
                if response.status == 404:
                    raise UnraidNotFoundError(
                        error_message, error_code=error_code, status_code=404
                    )
                if response.status == 409:
                    raise UnraidConflictError(
                        error_message, error_code=error_code, status_code=409
                    )
                if response.status == 400:
                    raise UnraidValidationError(
                        error_message, error_code=error_code, status_code=400
                    )
                raise UnraidAPIError(
                    error_message,
                    error_code=error_code,
                    status_code=response.status,
                )

        except aiohttp.ClientError as e:
            raise UnraidConnectionError(
                f"Unable to connect to Unraid API at {url}: {e!s}"
            ) from e
        except TimeoutError as e:
            raise UnraidConnectionError(f"Request to {url} timed out") from e

    async def _request_text(self, method: str, endpoint: str) -> str:
        """
        Make an async request expecting text response.

        Args:
            method: HTTP method
            endpoint: API endpoint path

        Returns:
            Response text

        Raises:
            UnraidConnectionError: If unable to connect to the API
            UnraidAPIError: For API errors

        """
        import aiohttp

        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        session = await self._ensure_session()

        try:
            async with session.request(method=method, url=url) as response:
                if response.status == 200:
                    text: str = await response.text()
                    return text

                error_message = await response.text() or f"HTTP {response.status}"
                raise UnraidAPIError(
                    error_message,
                    error_code="REQUEST_FAILED",
                    status_code=response.status,
                )
        except aiohttp.ClientError as e:
            raise UnraidConnectionError(
                f"Unable to connect to Unraid API at {url}: {e!s}"
            ) from e
        except TimeoutError as e:
            raise UnraidConnectionError(f"Request to {url} timed out") from e

    # Health & System endpoints

    async def health_check(self) -> HealthStatus:
        """
        Check API health status.

        Returns:
            Health status response

        Example:
            >>> health = await client.health_check()
            >>> print(health.status)

        """
        data = await self._request("GET", "/health")
        return HealthStatus.model_validate(data)

    async def get_metrics(self) -> str:
        """
        Get Prometheus metrics.

        Returns metrics in Prometheus exposition format for Grafana integration.
        Note: The metrics endpoint is at the server root, not under /api/v1.

        Returns:
            Prometheus metrics as plain text

        Example:
            >>> metrics = await client.get_metrics()
            >>> print(metrics)

        """
        import aiohttp

        protocol = "https" if self.use_https else "http"
        url = f"{protocol}://{self.host}:{self.port}/metrics"
        session = await self._ensure_session()

        try:
            async with session.request(method="GET", url=url) as response:
                if response.status == 200:
                    text: str = await response.text()
                    return text

                error_message = await response.text() or f"HTTP {response.status}"
                raise UnraidAPIError(
                    error_message,
                    error_code="REQUEST_FAILED",
                    status_code=response.status,
                )
        except aiohttp.ClientError as e:
            raise UnraidConnectionError(
                f"Unable to connect to Unraid metrics at {url}: {e!s}"
            ) from e
        except TimeoutError as e:
            raise UnraidConnectionError(f"Request to {url} timed out") from e

    async def get_system_info(self) -> SystemInfo:
        """
        Get system information including CPU, memory, and temperatures.

        Returns:
            System information

        Example:
            >>> info = await client.get_system_info()
            >>> print(f"CPU: {info.cpu_usage_percent}%")

        """
        data = await self._request("GET", "/system")
        return SystemInfo.model_validate(data)

    async def reboot_system(self) -> ActionResponse:
        """
        Initiate a system reboot.

        WARNING: This will reboot the Unraid server!

        Returns:
            Success response

        Example:
            >>> result = await client.reboot_system()
            >>> print(result.success)

        """
        data = await self._request("POST", "/system/reboot")
        return ActionResponse.model_validate(data)

    async def shutdown_system(self) -> ActionResponse:
        """
        Initiate a system shutdown.

        WARNING: This will shutdown the Unraid server!

        Returns:
            Success response

        Example:
            >>> result = await client.shutdown_system()
            >>> print(result.success)

        """
        data = await self._request("POST", "/system/shutdown")
        return ActionResponse.model_validate(data)

    async def get_flash_info(self) -> FlashDriveInfo:
        """
        Get USB flash boot drive information.

        Returns:
            Flash drive health and usage information

        Example:
            >>> flash = await client.get_flash_info()
            >>> print(f"Flash usage: {flash.usage_percent}%")

        """
        data = await self._request("GET", "/system/flash")
        return FlashDriveInfo.model_validate(data)

    # Array endpoints

    async def get_array_status(self) -> ArrayStatus:
        """
        Get array status and disk information.

        Returns:
            Array status

        Example:
            >>> status = await client.get_array_status()
            >>> print(status.state)

        """
        data = await self._request("GET", "/array")
        return ArrayStatus.model_validate(data)

    async def start_array(self) -> ActionResponse:
        """
        Start the array.

        Returns:
            Success response

        Raises:
            UnraidConflictError: If the array is already started

        """
        data = await self._request("POST", "/array/start")
        return ActionResponse.model_validate(data)

    async def stop_array(self) -> ActionResponse:
        """
        Stop the array.

        Returns:
            Success response

        Raises:
            UnraidConflictError: If the array is already stopped

        """
        data = await self._request("POST", "/array/stop")
        return ActionResponse.model_validate(data)

    # Note: Parity status is included in ArrayStatus from get_array_status()
    # (fields: parity_check_status, parity_check_progress, parity_valid)

    async def start_parity_check(self, correct: bool = False) -> ActionResponse:
        """
        Start a parity check.

        Args:
            correct: Whether to correct errors (default: False)

        Returns:
            Success response

        """
        params = {"correcting": correct} if correct else None
        data = await self._request("POST", "/array/parity-check/start", params=params)
        return ActionResponse.model_validate(data)

    async def stop_parity_check(self) -> ActionResponse:
        """
        Stop a running parity check.

        Returns:
            Success response

        """
        data = await self._request("POST", "/array/parity-check/stop")
        return ActionResponse.model_validate(data)

    async def pause_parity_check(self) -> ActionResponse:
        """
        Pause a running parity check.

        Returns:
            Success response

        """
        data = await self._request("POST", "/array/parity-check/pause")
        return ActionResponse.model_validate(data)

    async def resume_parity_check(self) -> ActionResponse:
        """
        Resume a paused parity check.

        Returns:
            Success response

        """
        data = await self._request("POST", "/array/parity-check/resume")
        return ActionResponse.model_validate(data)

    async def get_parity_history(self) -> ParityHistory:
        """
        Get parity check history.

        Returns:
            Parity history information

        """
        data = await self._request("GET", "/array/parity-check/history")
        return ParityHistory.model_validate(data)

    async def get_parity_schedule(self) -> ParitySchedule:
        """
        Get parity check schedule configuration.

        Returns:
            Parity schedule settings including mode, timing, and options

        Example:
            >>> schedule = await client.get_parity_schedule()
            >>> print(f"Mode: {schedule.mode}, Correcting: {schedule.correcting}")

        """
        data = await self._request("GET", "/array/parity-check/schedule")
        return ParitySchedule.model_validate(data)

    # Disk endpoints

    async def list_disks(self) -> list[DiskInfo]:
        """
        List all disks.

        Returns:
            List of disk information

        """
        data = await self._request("GET", "/disks")
        return [DiskInfo.model_validate(d) for d in data]

    async def get_disk(self, disk_id: str) -> DiskInfo:
        """
        Get information about a specific disk.

        Args:
            disk_id: Disk identifier

        Returns:
            Disk information

        Raises:
            UnraidNotFoundError: If the disk is not found

        """
        data = await self._request("GET", f"/disks/{disk_id}")
        return DiskInfo.model_validate(data)

    async def spin_up_disk(self, disk_id: str) -> ActionResponse:
        """
        Spin up a disk.

        Args:
            disk_id: Disk identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/disks/{disk_id}/spinup")
        return ActionResponse.model_validate(data)

    async def spin_down_disk(self, disk_id: str) -> ActionResponse:
        """
        Spin down a disk.

        Args:
            disk_id: Disk identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/disks/{disk_id}/spindown")
        return ActionResponse.model_validate(data)

    # Docker endpoints

    async def list_containers(self) -> list[ContainerInfo]:
        """
        List all Docker containers.

        Returns:
            List of container information

        """
        data = await self._request("GET", "/docker")
        return [ContainerInfo.model_validate(c) for c in data]

    async def get_container(self, container_id: str) -> ContainerInfo:
        """
        Get information about a specific container.

        Args:
            container_id: Container identifier

        Returns:
            Container information

        Raises:
            UnraidNotFoundError: If the container is not found

        """
        data = await self._request("GET", f"/docker/{container_id}")
        return ContainerInfo.model_validate(data)

    async def start_container(self, container_id: str) -> ActionResponse:
        """
        Start a container.

        Args:
            container_id: Container identifier

        Returns:
            Success response

        Raises:
            UnraidConflictError: If the container is already running

        """
        data = await self._request("POST", f"/docker/{container_id}/start")
        return ActionResponse.model_validate(data)

    async def stop_container(self, container_id: str) -> ActionResponse:
        """
        Stop a container.

        Args:
            container_id: Container identifier

        Returns:
            Success response

        Raises:
            UnraidConflictError: If the container is already stopped

        """
        data = await self._request("POST", f"/docker/{container_id}/stop")
        return ActionResponse.model_validate(data)

    async def restart_container(self, container_id: str) -> ActionResponse:
        """
        Restart a container.

        Args:
            container_id: Container identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/docker/{container_id}/restart")
        return ActionResponse.model_validate(data)

    async def pause_container(self, container_id: str) -> ActionResponse:
        """
        Pause a container.

        Args:
            container_id: Container identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/docker/{container_id}/pause")
        return ActionResponse.model_validate(data)

    async def unpause_container(self, container_id: str) -> ActionResponse:
        """
        Unpause a container.

        Args:
            container_id: Container identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/docker/{container_id}/unpause")
        return ActionResponse.model_validate(data)

    # VM endpoints

    async def list_vms(self) -> list[VMInfo]:
        """
        List all virtual machines.

        Returns:
            List of VM information

        """
        data = await self._request("GET", "/vm")
        return [VMInfo.model_validate(v) for v in data]

    async def get_vm(self, vm_id: str) -> VMInfo:
        """
        Get information about a specific VM.

        Args:
            vm_id: VM identifier

        Returns:
            VM information

        Raises:
            UnraidNotFoundError: If the VM is not found

        """
        data = await self._request("GET", f"/vm/{vm_id}")
        return VMInfo.model_validate(data)

    async def start_vm(self, vm_id: str) -> ActionResponse:
        """
        Start a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Success response

        Raises:
            UnraidConflictError: If the VM is already running

        """
        data = await self._request("POST", f"/vm/{vm_id}/start")
        return ActionResponse.model_validate(data)

    async def stop_vm(self, vm_id: str) -> ActionResponse:
        """
        Stop a VM gracefully.

        Args:
            vm_id: VM identifier

        Returns:
            Success response

        Raises:
            UnraidConflictError: If the VM is already stopped

        """
        data = await self._request("POST", f"/vm/{vm_id}/stop")
        return ActionResponse.model_validate(data)

    async def restart_vm(self, vm_id: str) -> ActionResponse:
        """
        Restart a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/vm/{vm_id}/restart")
        return ActionResponse.model_validate(data)

    async def pause_vm(self, vm_id: str) -> ActionResponse:
        """
        Pause a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/vm/{vm_id}/pause")
        return ActionResponse.model_validate(data)

    async def resume_vm(self, vm_id: str) -> ActionResponse:
        """
        Resume a paused VM.

        Args:
            vm_id: VM identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/vm/{vm_id}/resume")
        return ActionResponse.model_validate(data)

    async def hibernate_vm(self, vm_id: str) -> ActionResponse:
        """
        Hibernate a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/vm/{vm_id}/hibernate")
        return ActionResponse.model_validate(data)

    async def force_stop_vm(self, vm_id: str) -> ActionResponse:
        """
        Force stop a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/vm/{vm_id}/force-stop")
        return ActionResponse.model_validate(data)

    # Share endpoints

    async def list_shares(self) -> list[ShareInfo]:
        """
        List all user shares.

        Returns:
            List of share information

        """
        data = await self._request("GET", "/shares")
        return [ShareInfo.model_validate(s) for s in data]

    async def get_share(self, share_name: str) -> ShareInfo:
        """
        Get information about a specific share.

        Note: The API doesn't have a direct single-share endpoint.
        This method fetches all shares and filters by name.

        Args:
            share_name: Share name

        Returns:
            Share information

        Raises:
            UnraidNotFoundError: If the share is not found

        """
        shares = await self.list_shares()
        for share in shares:
            if share.name == share_name:
                return share
        raise UnraidNotFoundError(
            status_code=404,
            message=f"Share '{share_name}' not found",
            error_code="SHARE_NOT_FOUND",
        )

    # Network endpoints

    async def list_network_interfaces(self) -> list[NetworkInterface]:
        """
        List all network interfaces.

        Returns:
            List of network interface information

        """
        data = await self._request("GET", "/network")
        return [NetworkInterface.model_validate(n) for n in data]

    async def get_network_interface(self, interface_name: str) -> NetworkInterface:
        """
        Get information about a specific network interface.

        Note: The API doesn't have a direct single-interface endpoint.
        This method fetches all interfaces and filters by name.

        Args:
            interface_name: Network interface name

        Returns:
            Network interface information

        Raises:
            UnraidNotFoundError: If the interface is not found

        """
        interfaces = await self.list_network_interfaces()
        for iface in interfaces:
            if iface.name == interface_name:
                return iface
        raise UnraidNotFoundError(
            status_code=404,
            message=f"Network interface '{interface_name}' not found",
            error_code="INTERFACE_NOT_FOUND",
        )

    async def get_network_access_urls(self) -> NetworkAccessUrls:
        """
        Get network access URLs.

        Returns:
            Network access URLs

        """
        data = await self._request("GET", "/network/access-urls")
        return NetworkAccessUrls.model_validate(data)

    # Hardware endpoints

    async def get_hardware_info(self) -> HardwareFullInfo:
        """
        Get hardware information.

        This is an alias for get_hardware_full_info() for convenience.

        Returns:
            Full hardware information

        """
        return await self.get_hardware_full_info()

    async def get_hardware_full_info(self) -> HardwareFullInfo:
        """
        Get detailed hardware information.

        Returns:
            Full hardware information

        """
        data = await self._request("GET", "/hardware/full")
        return HardwareFullInfo.model_validate(data)

    async def list_gpus(self) -> list[GPUInfo]:
        """
        List all GPUs.

        Returns:
            List of GPU information

        """
        data = await self._request("GET", "/gpu")
        return [GPUInfo.model_validate(g) for g in data]

    async def get_bios_info(self) -> BIOSInfo:
        """
        Get BIOS information.

        Returns:
            BIOS information

        """
        data = await self._request("GET", "/hardware/bios")
        return BIOSInfo.model_validate(data)

    async def get_baseboard_info(self) -> BaseboardInfo:
        """
        Get motherboard/baseboard information.

        Returns:
            Baseboard information

        """
        data = await self._request("GET", "/hardware/baseboard")
        return BaseboardInfo.model_validate(data)

    async def get_cpu_hardware_info(self) -> CPUHardwareInfo:
        """
        Get CPU hardware information.

        Returns:
            CPU hardware information

        """
        data = await self._request("GET", "/hardware/cpu")
        return CPUHardwareInfo.model_validate(data)

    async def get_memory_array_info(self) -> MemoryArrayInfo:
        """
        Get physical memory array information.

        Returns:
            Memory array information

        """
        data = await self._request("GET", "/hardware/memory-array")
        return MemoryArrayInfo.model_validate(data)

    async def get_memory_devices(self) -> list[MemoryDeviceInfo]:
        """
        Get individual DIMM information.

        Returns:
            List of memory device information

        """
        data = await self._request("GET", "/hardware/memory-devices")
        return [MemoryDeviceInfo.model_validate(m) for m in data]

    async def get_cpu_cache_info(self) -> list[CPUCacheInfo]:
        """
        Get CPU cache hierarchy information.

        Returns:
            List of CPU cache information

        """
        data = await self._request("GET", "/hardware/cache")
        return [CPUCacheInfo.model_validate(c) for c in data]

    # UPS endpoint

    async def get_ups_info(self) -> UPSInfo:
        """
        Get UPS information.

        Returns:
            UPS information

        """
        data = await self._request("GET", "/ups")
        return UPSInfo.model_validate(data)

    # Registration endpoint

    async def get_registration_info(self) -> RegistrationInfo:
        """
        Get registration information.

        Returns:
            Registration information

        """
        data = await self._request("GET", "/registration")
        return RegistrationInfo.model_validate(data)

    # Logs endpoints

    async def list_logs(self) -> LogList:
        """
        List available log files.

        Returns:
            List of log files

        """
        data = await self._request("GET", "/logs")
        return LogList.model_validate(data)

    async def get_log(self, filename: str, lines: int = 100) -> LogContent:
        """
        Get log file content.

        Args:
            filename: Log filename
            lines: Number of lines to retrieve (default: 100)

        Returns:
            Log content

        """
        data = await self._request("GET", f"/logs/{filename}", params={"lines": lines})
        return LogContent.model_validate(data)

    # Notification endpoints

    async def list_notifications(self) -> NotificationsResponse:
        """
        List all notifications.

        Returns:
            Notifications response

        """
        data = await self._request("GET", "/notifications")
        return NotificationsResponse.model_validate(data)

    async def list_unread_notifications(self) -> NotificationsResponse:
        """
        List unread notifications.

        Returns:
            Notifications response with unread notifications

        """
        data = await self._request("GET", "/notifications/unread")
        return NotificationsResponse.model_validate(data)

    async def list_archived_notifications(self) -> NotificationsResponse:
        """
        List archived notifications.

        Returns:
            Notifications response with archived notifications

        """
        data = await self._request("GET", "/notifications/archive")
        return NotificationsResponse.model_validate(data)

    async def get_notification_overview(self) -> NotificationOverview:
        """
        Get notification overview.

        Returns:
            Notification overview

        """
        data = await self._request("GET", "/notifications/overview")
        return NotificationOverview.model_validate(data)

    async def get_notification(self, notification_id: str) -> Notification:
        """
        Get a specific notification.

        Args:
            notification_id: Notification identifier

        Returns:
            Notification details

        Raises:
            UnraidNotFoundError: If the notification is not found

        """
        data = await self._request("GET", f"/notifications/{notification_id}")
        return Notification.model_validate(data)

    async def create_notification(
        self,
        subject: str,
        message: str,
        importance: str = "normal",
    ) -> Notification:
        """
        Create a new notification.

        Args:
            subject: Notification subject
            message: Notification message
            importance: Importance level (normal, alert, warning)

        Returns:
            Created notification

        """
        data = await self._request(
            "POST",
            "/notifications",
            data={"subject": subject, "message": message, "importance": importance},
        )
        return Notification.model_validate(data)

    async def delete_notification(
        self, notification_id: str, archived: bool = False
    ) -> ActionResponse:
        """
        Delete a notification.

        Args:
            notification_id: Notification identifier
            archived: Whether the notification is archived

        Returns:
            Success response

        """
        params = {"archived": str(archived).lower()} if archived else None
        data = await self._request(
            "DELETE", f"/notifications/{notification_id}", params=params
        )
        return ActionResponse.model_validate(data)

    async def archive_notification(self, notification_id: str) -> ActionResponse:
        """
        Archive a notification.

        Args:
            notification_id: Notification identifier

        Returns:
            Success response

        """
        data = await self._request("POST", f"/notifications/{notification_id}/archive")
        return ActionResponse.model_validate(data)

    async def unarchive_notification(self, notification_id: str) -> ActionResponse:
        """
        Unarchive a notification.

        Args:
            notification_id: Notification identifier

        Returns:
            Success response

        """
        data = await self._request(
            "POST", f"/notifications/{notification_id}/unarchive"
        )
        return ActionResponse.model_validate(data)

    async def archive_all_notifications(self) -> ActionResponse:
        """
        Archive all unread notifications.

        Returns:
            Success response

        """
        data = await self._request("POST", "/notifications/archive-all")
        return ActionResponse.model_validate(data)

    # Unassigned devices endpoints

    async def get_unassigned_info(self) -> UnassignedInfo:
        """
        Get unassigned devices plugin info.

        Returns:
            Unassigned devices info

        """
        data = await self._request("GET", "/unassigned")
        return UnassignedInfo.model_validate(data)

    async def list_unassigned_devices(self) -> UnassignedDevicesResponse:
        """
        List unassigned devices.

        Returns:
            Unassigned devices response

        """
        data = await self._request("GET", "/unassigned/devices")
        return UnassignedDevicesResponse.model_validate(data)

    async def list_remote_shares(self) -> RemoteSharesResponse:
        """
        List remote shares.

        Returns:
            Remote shares response

        """
        data = await self._request("GET", "/unassigned/remote-shares")
        return RemoteSharesResponse.model_validate(data)

    # Settings endpoints

    async def get_system_settings(self) -> SystemSettings:
        """
        Get system settings.

        Returns:
            System settings

        """
        data = await self._request("GET", "/settings/system")
        return SystemSettings.model_validate(data)

    async def update_system_settings(self, settings: dict[str, Any]) -> ActionResponse:
        """
        Update system settings.

        Args:
            settings: Dictionary of settings to update (server_name, timezone, etc.)

        Returns:
            Success response

        Example:
            >>> result = await client.update_system_settings({"server_name": "MyServer"})
            >>> print(result.success)

        """
        data = await self._request("POST", "/settings/system", data=settings)
        return ActionResponse.model_validate(data)

    async def get_docker_settings(self) -> DockerSettings:
        """
        Get Docker settings.

        Returns:
            Docker settings

        """
        data = await self._request("GET", "/settings/docker")
        return DockerSettings.model_validate(data)

    async def get_vm_settings(self) -> VMSettings:
        """
        Get VM settings.

        Returns:
            VM settings

        """
        data = await self._request("GET", "/settings/vm")
        return VMSettings.model_validate(data)

    async def get_disk_settings(self) -> DiskSettings:
        """
        Get disk temperature threshold settings.

        Returns:
            Disk settings including temperature thresholds and utilization limits

        Example:
            >>> settings = await client.get_disk_settings()
            >>> print(f"HDD Warning: {settings.hdd_temp_warning_celsius}°C")

        """
        data = await self._request("GET", "/settings/disk-thresholds")
        return DiskSettings.model_validate(data)

    async def get_basic_disk_settings(self) -> DiskSettings:
        """
        Get basic disk settings.

        Returns:
            Basic disk settings (spindown, startup, filesystem defaults)

        Example:
            >>> settings = await client.get_basic_disk_settings()
            >>> print(f"Spindown delay: {settings.spindown_delay_minutes} minutes")

        """
        data = await self._request("GET", "/settings/disks")
        return DiskSettings.model_validate(data)

    async def get_mover_settings(self) -> MoverSettings:
        """
        Get mover settings and status.

        Returns:
            Mover settings including schedule and current status

        Example:
            >>> mover = await client.get_mover_settings()
            >>> print(f"Mover active: {mover.active}, Schedule: {mover.schedule}")

        """
        data = await self._request("GET", "/settings/mover")
        return MoverSettings.model_validate(data)

    async def get_service_status(self) -> ServiceStatus:
        """
        Get Docker and VM service enabled status.

        Returns:
            Service status for Docker and VM manager

        Example:
            >>> status = await client.get_service_status()
            >>> print(f"Docker enabled: {status.docker_enabled}")

        """
        data = await self._request("GET", "/settings/services")
        return ServiceStatus.model_validate(data)

    async def get_network_services(self) -> NetworkServicesStatus:
        """
        Get status of all network services.

        Returns:
            Network services status including SMB, NFS, SSH, etc.

        Example:
            >>> services = await client.get_network_services()
            >>> print(f"SMB running: {services.smb.running}")

        """
        data = await self._request("GET", "/settings/network-services")
        return NetworkServicesStatus.model_validate(data)

    async def get_share_config(self, share_name: str) -> ShareConfig:
        """
        Get share configuration.

        Args:
            share_name: Share name

        Returns:
            Share configuration

        """
        data = await self._request("GET", f"/shares/{share_name}/config")
        return ShareConfig.model_validate(data)

    async def update_share_config(
        self, share_name: str, config: dict[str, Any]
    ) -> ActionResponse:
        """
        Update share configuration.

        Args:
            share_name: Share name
            config: Configuration updates

        Returns:
            Success response

        """
        data = await self._request("PUT", f"/shares/{share_name}/config", data=config)
        return ActionResponse.model_validate(data)

    async def get_network_config(self, interface: str) -> NetworkConfig:
        """
        Get network interface configuration.

        Args:
            interface: Interface name (e.g., eth0, bond0)

        Returns:
            Network configuration

        """
        data = await self._request("GET", f"/network/{interface}/config")
        return NetworkConfig.model_validate(data)

    # User scripts endpoints

    async def list_user_scripts(self) -> list[UserScript]:
        """
        List all user scripts.

        Returns:
            List of user scripts

        """
        data = await self._request("GET", "/user-scripts")
        return [UserScript.model_validate(s) for s in data]

    async def execute_user_script(
        self,
        script_name: str,
        background: bool = False,
        wait: bool = True,
    ) -> UserScriptExecuteResponse:
        """
        Execute a user script.

        Args:
            script_name: Name of the script to execute
            background: Run in background (default: False)
            wait: Wait for completion (default: True)

        Returns:
            Execution response

        """
        data = await self._request(
            "POST",
            f"/user-scripts/{script_name}/execute",
            data={"background": background, "wait": wait},
        )
        return UserScriptExecuteResponse.model_validate(data)

    # Plugins endpoints

    async def list_plugins(self) -> PluginList:
        """
        List all installed plugins.

        Returns:
            Plugin list with update information

        Example:
            >>> plugins = await client.list_plugins()
            >>> for p in plugins.plugins:
            ...     print(f"{p.name}: {p.version}")

        """
        data = await self._request("GET", "/plugins")
        return PluginList.model_validate(data)

    # Updates endpoint

    async def get_update_status(self) -> UpdateStatus:
        """
        Get Unraid OS and plugin update availability.

        Returns:
            Update status information

        Example:
            >>> status = await client.get_update_status()
            >>> if status.os_update_available:
            ...     print(f"Update available! Current: {status.current_version}")

        """
        data = await self._request("GET", "/updates")
        return UpdateStatus.model_validate(data)

    # ZFS endpoints

    async def list_zfs_pools(self) -> list[ZFSPool]:
        """
        List ZFS pools.

        Returns:
            List of ZFS pools

        """
        data = await self._request("GET", "/zfs/pools")
        return [ZFSPool.model_validate(p) for p in data]

    async def get_zfs_pool(self, pool_name: str) -> ZFSPool:
        """
        Get a specific ZFS pool.

        Args:
            pool_name: Name of the ZFS pool

        Returns:
            ZFS pool details

        Raises:
            UnraidNotFoundError: If the pool is not found

        """
        data = await self._request("GET", f"/zfs/pools/{pool_name}")
        return ZFSPool.model_validate(data)

    async def list_zfs_datasets(self) -> list[ZFSDataset]:
        """
        List ZFS datasets.

        Returns:
            List of ZFS datasets

        """
        data = await self._request("GET", "/zfs/datasets")
        return [ZFSDataset.model_validate(d) for d in data]

    async def list_zfs_snapshots(self) -> list[ZFSSnapshot]:
        """
        List ZFS snapshots.

        Returns:
            List of ZFS snapshots

        """
        data = await self._request("GET", "/zfs/snapshots")
        return [ZFSSnapshot.model_validate(s) for s in data]

    async def get_zfs_arc_stats(self) -> ZFSArcStats:
        """
        Get ZFS ARC statistics.

        Returns:
            ZFS ARC statistics

        """
        data = await self._request("GET", "/zfs/arc")
        return ZFSArcStats.model_validate(data)

    # NUT endpoint

    async def get_nut_info(self) -> NUTInfo:
        """
        Get NUT (Network UPS Tools) information.

        Returns:
            NUT information

        """
        data = await self._request("GET", "/nut")
        return NUTInfo.model_validate(data)

    # Collector endpoints

    async def get_collectors_status(self) -> CollectorStatus:
        """
        Get status of all collectors.

        Returns:
            Collectors status

        """
        data = await self._request("GET", "/collectors/status")
        return CollectorStatus.model_validate(data)

    async def get_collector(self, name: str) -> CollectorInfo:
        """
        Get status of a specific collector.

        Args:
            name: Collector name

        Returns:
            Collector information

        Raises:
            UnraidNotFoundError: If the collector is not found

        """
        data = await self._request("GET", f"/collectors/{name}")
        return CollectorInfo.model_validate(data)

    async def enable_collector(self, name: str) -> CollectorInfo:
        """
        Enable a collector.

        Args:
            name: Collector name

        Returns:
            Updated collector information

        """
        data = await self._request("POST", f"/collectors/{name}/enable")
        return CollectorInfo.model_validate(data)

    async def disable_collector(self, name: str) -> CollectorInfo:
        """
        Disable a collector.

        Args:
            name: Collector name

        Returns:
            Updated collector information

        """
        data = await self._request("POST", f"/collectors/{name}/disable")
        return CollectorInfo.model_validate(data)

    async def update_collector_interval(
        self, name: str, interval_seconds: int
    ) -> CollectorInfo:
        """
        Update a collector's interval.

        Args:
            name: Collector name
            interval_seconds: New interval in seconds

        Returns:
            Updated collector information

        """
        data = await self._request(
            "PUT",
            f"/collectors/{name}/interval",
            data={"interval_seconds": interval_seconds},
        )
        return CollectorInfo.model_validate(data)

    # Docker extended endpoints (Issue #39)

    async def get_container_logs(
        self,
        container_id: str,
        tail: int | None = None,
        since: str | None = None,
        timestamps: bool = False,
    ) -> ContainerLogs:
        """
        Get logs from a Docker container.

        Args:
            container_id: Container ID or name
            tail: Number of lines from the end
            since: Only logs since this timestamp (RFC3339)
            timestamps: Include timestamps in log output

        Returns:
            Container log output

        """
        params: dict[str, Any] = {}
        if tail is not None:
            params["tail"] = tail
        if since is not None:
            params["since"] = since
        if timestamps:
            params["timestamps"] = True
        data = await self._request(
            "GET", f"/docker/{container_id}/logs", params=params or None
        )
        return ContainerLogs.model_validate(data)

    async def get_container_size(self, container_id: str) -> ContainerSizeInfo:
        """
        Get size information for a Docker container.

        Args:
            container_id: Container ID or name

        Returns:
            Container size breakdown

        """
        data = await self._request("GET", f"/docker/{container_id}/size")
        return ContainerSizeInfo.model_validate(data)

    async def check_container_update(self, container_id: str) -> ContainerUpdateInfo:
        """
        Check if a container has an available update.

        Args:
            container_id: Container ID or name

        Returns:
            Update availability with current/latest digest comparison

        """
        data = await self._request("GET", f"/docker/{container_id}/check-update")
        return ContainerUpdateInfo.model_validate(data)

    async def check_all_container_updates(self) -> ContainerUpdatesResult:
        """
        Check update availability for all Docker containers.

        Returns:
            Update status for every container with summary counts

        """
        data = await self._request("GET", "/docker/updates")
        return ContainerUpdatesResult.model_validate(data)

    async def update_container(self, container_id: str) -> ContainerUpdateResult:
        """
        Update a single container (pull latest image and recreate).

        Args:
            container_id: Container ID or name

        Returns:
            Update result with previous/new digest and status

        """
        data = await self._request("POST", f"/docker/{container_id}/update")
        return ContainerUpdateResult.model_validate(data)

    async def update_all_containers(self) -> ContainerBulkUpdateResult:
        """
        Update all containers that have available updates.

        Returns:
            Bulk update results with succeeded/failed/skipped counts

        """
        data = await self._request("POST", "/docker/update-all")
        return ContainerBulkUpdateResult.model_validate(data)

    # VM snapshot endpoints (Issue #40)

    async def list_vm_snapshots(self, vm_name: str) -> VMSnapshotList:
        """
        List all snapshots for a virtual machine.

        Args:
            vm_name: VM name

        Returns:
            List of snapshots with metadata

        """
        data = await self._request("GET", f"/vm/{vm_name}/snapshots")
        return VMSnapshotList.model_validate(data)

    async def create_vm_snapshot(self, vm_name: str) -> ActionResponse:
        """
        Create a new snapshot of a virtual machine.

        Args:
            vm_name: VM name

        Returns:
            Success response

        """
        data = await self._request("POST", f"/vm/{vm_name}/snapshot")
        return ActionResponse.model_validate(data)

    async def delete_vm_snapshot(
        self, vm_name: str, snapshot_name: str
    ) -> ActionResponse:
        """
        Delete a VM snapshot.

        Args:
            vm_name: VM name
            snapshot_name: Snapshot name to delete

        Returns:
            Success response

        """
        data = await self._request("DELETE", f"/vm/{vm_name}/snapshots/{snapshot_name}")
        return ActionResponse.model_validate(data)

    async def restore_vm_snapshot(
        self, vm_name: str, snapshot_name: str
    ) -> ActionResponse:
        """
        Restore a VM to a specific snapshot.

        Args:
            vm_name: VM name
            snapshot_name: Snapshot name to restore

        Returns:
            Success response

        """
        data = await self._request(
            "POST", f"/vm/{vm_name}/snapshots/{snapshot_name}/restore"
        )
        return ActionResponse.model_validate(data)

    async def clone_vm(self, vm_name: str) -> ActionResponse:
        """
        Clone a virtual machine.

        Args:
            vm_name: VM name to clone

        Returns:
            Success response

        """
        data = await self._request("POST", f"/vm/{vm_name}/clone")
        return ActionResponse.model_validate(data)

    # Process monitoring endpoint (Issue #41)

    async def list_processes(
        self,
        sort_by: str | None = None,
        limit: int | None = None,
    ) -> ProcessList:
        """
        List running processes on the Unraid server.

        Args:
            sort_by: Sort field (e.g., "cpu", "memory")
            limit: Maximum number of processes to return

        Returns:
            List of running processes with resource usage

        """
        params: dict[str, Any] = {}
        if sort_by is not None:
            params["sort_by"] = sort_by
        if limit is not None:
            params["limit"] = limit
        data = await self._request("GET", "/processes", params=params or None)
        return ProcessList.model_validate(data)

    # System service endpoints (Issue #42)

    async def list_services(self) -> SystemServiceList:
        """
        List all managed system services with their status.

        Returns:
            List of services with running state

        """
        data = await self._request("GET", "/services")
        return SystemServiceList.model_validate(data)

    async def control_service(self, name: str, action: str) -> ActionResponse:
        """
        Control a system service.

        Args:
            name: Service name (e.g., "docker", "libvirtd", "sshd")
            action: Action to perform ("start", "stop", "restart")

        Returns:
            Success response

        """
        data = await self._request("POST", f"/services/{name}/{action}")
        return ActionResponse.model_validate(data)

    # Plugin update endpoints (Issue #43)

    async def check_plugin_updates(self) -> PluginUpdatesResult:
        """
        Check for available plugin updates.

        Returns:
            Plugins with update availability info

        """
        data = await self._request("GET", "/plugins/check-updates")
        return PluginUpdatesResult.model_validate(data)

    async def update_plugin(self, plugin_name: str) -> PluginUpdateResult:
        """
        Update a specific plugin to its latest version.

        Args:
            plugin_name: Plugin name

        Returns:
            Update result with status and message

        """
        data = await self._request("POST", f"/plugins/{plugin_name}/update")
        return PluginUpdateResult.model_validate(data)

    async def update_all_plugins(self) -> PluginBulkUpdateResult:
        """
        Update all plugins that have available updates.

        Returns:
            Bulk update results with succeeded/failed counts

        """
        data = await self._request("POST", "/plugins/update-all")
        return PluginBulkUpdateResult.model_validate(data)

    # MQTT endpoints (Issue #44)

    async def get_mqtt_status(self) -> MQTTStatus:
        """
        Get MQTT connection status and configuration.

        Returns:
            MQTT status including connection state and broker info

        """
        data = await self._request("GET", "/mqtt/status")
        return MQTTStatus.model_validate(data)

    async def test_mqtt_connection(self) -> MQTTTestResponse:
        """
        Test MQTT broker connectivity.

        Returns:
            Test result with success status and latency

        """
        data = await self._request("POST", "/mqtt/test")
        return MQTTTestResponse.model_validate(data)

    async def publish_mqtt_message(
        self,
        topic: str,
        payload: str,
        retained: bool = False,
    ) -> MQTTPublishResponse:
        """
        Publish a message to an MQTT topic.

        Args:
            topic: MQTT topic to publish to
            payload: Message payload
            retained: Whether the message should be retained by the broker

        Returns:
            Publish result

        """
        data = await self._request(
            "POST",
            "/mqtt/publish",
            data={"topic": topic, "payload": payload, "retained": retained},
        )
        return MQTTPublishResponse.model_validate(data)

    # Alerting engine endpoints (Issue #45)

    async def list_alert_rules(self) -> list[AlertRule]:
        """
        List all configured alert rules.

        Returns:
            List of alert rules

        """
        data = await self._request("GET", "/alerts/rules")
        return [AlertRule.model_validate(r) for r in data]

    async def create_alert_rule(self, rule: dict[str, Any]) -> AlertRule:
        """
        Create a new alert rule.

        Args:
            rule: Alert rule configuration

        Returns:
            Created alert rule

        """
        data = await self._request("POST", "/alerts/rules", data=rule)
        return AlertRule.model_validate(data)

    async def get_alert_rule(self, rule_id: str) -> AlertRule:
        """
        Get a specific alert rule by ID.

        Args:
            rule_id: Alert rule ID

        Returns:
            Alert rule details

        """
        data = await self._request("GET", f"/alerts/rules/{rule_id}")
        return AlertRule.model_validate(data)

    async def update_alert_rule(self, rule_id: str, rule: dict[str, Any]) -> AlertRule:
        """
        Update an existing alert rule.

        Args:
            rule_id: Alert rule ID
            rule: Updated rule configuration

        Returns:
            Updated alert rule

        """
        data = await self._request("PUT", f"/alerts/rules/{rule_id}", data=rule)
        return AlertRule.model_validate(data)

    async def delete_alert_rule(self, rule_id: str) -> ActionResponse:
        """
        Delete an alert rule.

        Args:
            rule_id: Alert rule ID

        Returns:
            Success response

        """
        data = await self._request("DELETE", f"/alerts/rules/{rule_id}")
        return ActionResponse.model_validate(data)

    async def get_alerts_status(self) -> AlertsStatusResponse:
        """
        Get current status of all alert rules.

        Returns:
            Alert statuses (ok/pending/firing)

        """
        data = await self._request("GET", "/alerts/status")
        return AlertsStatusResponse.model_validate(data)

    async def get_alert_history(self) -> AlertHistoryResponse:
        """
        Get alert event history.

        Returns:
            Alert events (firing and resolved)

        """
        data = await self._request("GET", "/alerts/history")
        return AlertHistoryResponse.model_validate(data)

    async def get_firing_alerts(self) -> list[AlertStatus]:
        """
        Get only currently firing alerts.

        Returns:
            List of currently firing alerts

        """
        data = await self._request("GET", "/alerts/firing")
        if data is None:
            return []
        return [AlertStatus.model_validate(a) for a in data]

    # Health check (watchdog) endpoints (Issue #46)

    async def list_health_checks(self) -> list[HealthCheck]:
        """
        List all configured health check probes.

        Returns:
            List of health checks

        """
        data = await self._request("GET", "/healthchecks")
        return [HealthCheck.model_validate(hc) for hc in data]

    async def create_health_check(self, check: dict[str, Any]) -> HealthCheck:
        """
        Create a new health check probe.

        Args:
            check: Health check config

        Returns:
            Created health check

        """
        data = await self._request("POST", "/healthchecks", data=check)
        return HealthCheck.model_validate(data)

    async def get_health_check(self, check_id: str) -> HealthCheck:
        """
        Get a specific health check by ID.

        Args:
            check_id: Health check ID

        Returns:
            Health check details

        """
        data = await self._request("GET", f"/healthchecks/{check_id}")
        return HealthCheck.model_validate(data)

    async def update_health_check(
        self, check_id: str, check: dict[str, Any]
    ) -> HealthCheck:
        """
        Update an existing health check.

        Args:
            check_id: Health check ID
            check: Updated health check configuration

        Returns:
            Updated health check

        """
        data = await self._request("PUT", f"/healthchecks/{check_id}", data=check)
        return HealthCheck.model_validate(data)

    async def delete_health_check(self, check_id: str) -> ActionResponse:
        """
        Delete a health check.

        Args:
            check_id: Health check ID

        Returns:
            Success response

        """
        data = await self._request("DELETE", f"/healthchecks/{check_id}")
        return ActionResponse.model_validate(data)

    async def get_health_checks_status(self) -> HealthChecksStatusResponse:
        """
        Get current status of all health checks.

        Returns:
            Health check statuses (healthy/unhealthy)

        """
        data = await self._request("GET", "/healthchecks/status")
        return HealthChecksStatusResponse.model_validate(data)

    async def get_health_check_history(self) -> HealthCheckHistoryResponse:
        """
        Get health check event history.

        Returns:
            Health check events

        """
        data = await self._request("GET", "/healthchecks/history")
        return HealthCheckHistoryResponse.model_validate(data)

    async def run_health_check(self, check_id: str) -> HealthCheckStatus:
        """
        Manually trigger a health check and return the result.

        Args:
            check_id: Health check ID to run

        Returns:
            Health check result

        """
        data = await self._request("POST", f"/healthchecks/{check_id}/run")
        return HealthCheckStatus.model_validate(data)
