"""API client for Unraid Management Agent."""

import logging
from typing import Any

import aiohttp
import async_timeout

from .const import (
    API_ARRAY,
    API_ARRAY_START,
    API_ARRAY_STOP,
    API_DISKS,
    API_DOCKER,
    API_DOCKER_PAUSE,
    API_DOCKER_RESTART,
    API_DOCKER_START,
    API_DOCKER_STOP,
    API_DOCKER_UNPAUSE,
    API_GPU,
    API_HEALTH,
    API_NETWORK,
    API_NOTIFICATIONS,
    API_PARITY_CHECK_PAUSE,
    API_PARITY_CHECK_RESUME,
    API_PARITY_CHECK_START,
    API_PARITY_CHECK_STOP,
    API_SHARES,
    API_SYSTEM,
    API_UPS,
    API_USER_SCRIPT_EXECUTE,
    API_USER_SCRIPTS,
    API_VM,
    API_VM_FORCE_STOP,
    API_VM_HIBERNATE,
    API_VM_PAUSE,
    API_VM_RESTART,
    API_VM_RESUME,
    API_VM_START,
    API_VM_STOP,
    API_ZFS_ARC,
    API_ZFS_DATASETS,
    API_ZFS_POOL,
    API_ZFS_POOLS,
    API_ZFS_SNAPSHOTS,
)

_LOGGER = logging.getLogger(__name__)


class UnraidAPIClient:
    """API client for Unraid Management Agent."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self.host = host
        self.port = port
        self.session = session
        self.base_url = f"http://{host}:{port}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        timeout: int = 10,
        **kwargs: Any,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make a request to the API."""
        url = f"{self.base_url}{endpoint}"

        try:
            async with async_timeout.timeout(timeout):
                async with self.session.request(method, url, **kwargs) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")
                    text = await response.text()

                    _LOGGER.debug(
                        "API response from %s: status=%s, content_type=%s, body_length=%d",
                        url,
                        response.status,
                        content_type,
                        len(text),
                    )

                    if not text or text.strip() == "":
                        _LOGGER.error("Empty response from %s", url)
                        raise ValueError(f"Empty response from {url}")

                    try:
                        data = await response.json()
                        if data is None:
                            _LOGGER.error("API returned null/None from %s", url)
                            raise ValueError(f"API returned null from {url}")
                        return data
                    except ValueError as json_err:
                        _LOGGER.error(
                            "Invalid JSON from %s: %s. Response text: %s",
                            url,
                            json_err,
                            text[:500],
                        )
                        raise
        except TimeoutError as err:
            _LOGGER.error("Timeout connecting to %s", url)
            raise TimeoutError(f"Timeout connecting to {url}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Error connecting to %s: %s", url, err)
            raise ConnectionError(f"Error connecting to {url}: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error connecting to %s: %s", url, err)
            raise

    async def _get(
        self, endpoint: str, **kwargs: Any
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make a GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", endpoint, **kwargs)

    # Health check
    async def health_check(self) -> dict[str, Any]:
        """Check if the API is healthy."""
        return await self._get(API_HEALTH)

    # System information
    async def get_system_info(self) -> dict[str, Any]:
        """Get system information."""
        return await self._get(API_SYSTEM)

    # Array status
    async def get_array_status(self) -> dict[str, Any]:
        """Get array status."""
        return await self._get(API_ARRAY)

    async def start_array(self) -> dict[str, Any]:
        """Start the array."""
        return await self._post(API_ARRAY_START)

    async def stop_array(self) -> dict[str, Any]:
        """Stop the array."""
        return await self._post(API_ARRAY_STOP)

    async def start_parity_check(self) -> dict[str, Any]:
        """Start a parity check."""
        return await self._post(API_PARITY_CHECK_START)

    async def stop_parity_check(self) -> dict[str, Any]:
        """Stop the parity check."""
        return await self._post(API_PARITY_CHECK_STOP)

    async def pause_parity_check(self) -> dict[str, Any]:
        """Pause the parity check."""
        return await self._post(API_PARITY_CHECK_PAUSE)

    async def resume_parity_check(self) -> dict[str, Any]:
        """Resume the parity check."""
        return await self._post(API_PARITY_CHECK_RESUME)

    # Disks
    async def get_disks(self) -> list[dict[str, Any]]:
        """Get list of disks."""
        return await self._get(API_DISKS)

    # Shares
    async def get_shares(self) -> list[dict[str, Any]]:
        """Get list of shares."""
        return await self._get(API_SHARES)

    # Notifications
    async def get_notifications(self) -> list[dict[str, Any]]:
        """Get list of notifications."""
        return await self._get(API_NOTIFICATIONS)

    # Docker containers
    async def get_containers(self) -> list[dict[str, Any]]:
        """Get list of Docker containers."""
        return await self._get(API_DOCKER)

    async def start_container(self, container_id: str) -> dict[str, Any]:
        """Start a Docker container."""
        endpoint = API_DOCKER_START.format(id=container_id)
        return await self._post(endpoint)

    async def stop_container(self, container_id: str) -> dict[str, Any]:
        """Stop a Docker container."""
        endpoint = API_DOCKER_STOP.format(id=container_id)
        return await self._post(endpoint)

    async def restart_container(self, container_id: str) -> dict[str, Any]:
        """Restart a Docker container."""
        endpoint = API_DOCKER_RESTART.format(id=container_id)
        return await self._post(endpoint)

    async def pause_container(self, container_id: str) -> dict[str, Any]:
        """Pause a Docker container."""
        endpoint = API_DOCKER_PAUSE.format(id=container_id)
        return await self._post(endpoint)

    async def unpause_container(self, container_id: str) -> dict[str, Any]:
        """Unpause (resume) a Docker container."""
        endpoint = API_DOCKER_UNPAUSE.format(id=container_id)
        return await self._post(endpoint)

    # Virtual machines
    async def get_vms(self) -> list[dict[str, Any]]:
        """Get list of virtual machines."""
        return await self._get(API_VM)

    async def start_vm(self, vm_id: str) -> dict[str, Any]:
        """Start a virtual machine."""
        endpoint = API_VM_START.format(id=vm_id)
        return await self._post(endpoint)

    async def stop_vm(self, vm_id: str) -> dict[str, Any]:
        """Stop a virtual machine."""
        endpoint = API_VM_STOP.format(id=vm_id)
        return await self._post(endpoint)

    async def restart_vm(self, vm_id: str) -> dict[str, Any]:
        """Restart a virtual machine."""
        endpoint = API_VM_RESTART.format(id=vm_id)
        return await self._post(endpoint)

    async def pause_vm(self, vm_id: str) -> dict[str, Any]:
        """Pause a virtual machine (suspend to RAM)."""
        endpoint = API_VM_PAUSE.format(id=vm_id)
        return await self._post(endpoint)

    async def resume_vm(self, vm_id: str) -> dict[str, Any]:
        """Resume a paused virtual machine."""
        endpoint = API_VM_RESUME.format(id=vm_id)
        return await self._post(endpoint)

    async def hibernate_vm(self, vm_id: str) -> dict[str, Any]:
        """Hibernate a virtual machine (suspend to disk)."""
        endpoint = API_VM_HIBERNATE.format(id=vm_id)
        return await self._post(endpoint)

    async def force_stop_vm(self, vm_id: str) -> dict[str, Any]:
        """Force stop a virtual machine (power off)."""
        endpoint = API_VM_FORCE_STOP.format(id=vm_id)
        return await self._post(endpoint)

    # UPS status
    async def get_ups_status(self) -> dict[str, Any]:
        """Get UPS status."""
        return await self._get(API_UPS)

    # GPU metrics
    async def get_gpu_metrics(self) -> list[dict[str, Any]]:
        """Get GPU metrics."""
        return await self._get(API_GPU)

    # Network interfaces
    async def get_network_interfaces(self) -> list[dict[str, Any]]:
        """Get network interfaces."""
        return await self._get(API_NETWORK)

    # User scripts
    async def get_user_scripts(self) -> list[dict[str, Any]]:
        """Get list of user scripts."""
        return await self._get(API_USER_SCRIPTS)

    async def execute_user_script(self, script_name: str) -> None:
        """Execute a user script."""
        endpoint = API_USER_SCRIPT_EXECUTE.format(name=script_name)
        await self._post(endpoint)

    # ZFS storage pools
    async def get_zfs_pools(self) -> list[dict[str, Any]]:
        """Get all ZFS pools."""
        return await self._get(API_ZFS_POOLS)

    async def get_zfs_pool(self, pool_name: str) -> dict[str, Any]:
        """Get specific ZFS pool details."""
        endpoint = API_ZFS_POOL.format(name=pool_name)
        return await self._get(endpoint)

    async def get_zfs_datasets(self) -> list[dict[str, Any]]:
        """Get all ZFS datasets."""
        return await self._get(API_ZFS_DATASETS)

    async def get_zfs_snapshots(self) -> list[dict[str, Any]]:
        """Get all ZFS snapshots."""
        return await self._get(API_ZFS_SNAPSHOTS)

    async def get_zfs_arc(self) -> dict[str, Any]:
        """Get ZFS ARC statistics."""
        return await self._get(API_ZFS_ARC)


class UnraidAPIError(Exception):
    """Base exception for Unraid API errors."""


class UnraidConnectionError(UnraidAPIError):
    """Exception for connection errors."""


class UnraidTimeoutError(UnraidAPIError):
    """Exception for timeout errors."""
