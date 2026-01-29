"""Fixtures for Unraid Management Agent tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.coordinator import UnraidData

from .const import (
    MOCK_CONFIG,
    MOCK_OPTIONS,
    mock_array_status,
    mock_collectors_status,
    mock_containers,
    mock_disks,
    mock_gpu_list,
    mock_network_interfaces,
    mock_system_info,
    mock_ups_info,
    mock_vms,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    mock_setup_entry = AsyncMock(return_value=True)
    with patch(
        "custom_components.unraid_management_agent.async_setup_entry",
        new=mock_setup_entry,
    ):
        yield mock_setup_entry


@pytest.fixture
def mock_async_unraid_client() -> Generator[MagicMock]:
    """Mock UnraidClient from uma-api (async by default in v1.2.1+)."""
    with patch(
        "custom_components.unraid_management_agent.UnraidClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value

        # Context manager support
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        # Mock all API methods - these return Pydantic models
        client.health_check = AsyncMock(return_value=True)
        client.get_system_info = AsyncMock(return_value=mock_system_info())
        client.get_array_status = AsyncMock(return_value=mock_array_status())
        client.list_disks = AsyncMock(return_value=mock_disks())
        client.list_containers = AsyncMock(return_value=mock_containers())
        client.list_vms = AsyncMock(return_value=mock_vms())
        client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        client.list_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        client.list_shares = AsyncMock(return_value=[])
        client.list_notifications = AsyncMock(return_value=[])
        client.list_user_scripts = AsyncMock(return_value=[])
        client.list_zfs_pools = AsyncMock(return_value=[])
        client.list_zfs_datasets = AsyncMock(return_value=[])
        client.list_zfs_snapshots = AsyncMock(return_value=[])
        client.get_zfs_arc_stats = AsyncMock(return_value=None)
        client.get_collectors_status = AsyncMock(return_value=mock_collectors_status())

        # New API methods for uma-api v1.3.0
        client.get_disk_settings = AsyncMock(return_value=None)
        client.get_mover_settings = AsyncMock(return_value=None)
        client.get_parity_schedule = AsyncMock(return_value=None)
        client.get_parity_history = AsyncMock(return_value=None)
        client.get_flash_info = AsyncMock(return_value=None)
        client.list_plugins = AsyncMock(return_value=None)
        client.get_update_status = AsyncMock(return_value=None)
        client.get_docker_settings = AsyncMock(return_value=None)
        client.get_vm_settings = AsyncMock(return_value=None)

        # Mock control methods
        client.start_array = AsyncMock(return_value=True)
        client.stop_array = AsyncMock(return_value=True)
        client.start_parity_check = AsyncMock(return_value=True)
        client.stop_parity_check = AsyncMock(return_value=True)
        client.pause_parity_check = AsyncMock(return_value=True)
        client.resume_parity_check = AsyncMock(return_value=True)
        client.start_container = AsyncMock(return_value=True)
        client.stop_container = AsyncMock(return_value=True)
        client.restart_container = AsyncMock(return_value=True)
        client.pause_container = AsyncMock(return_value=True)
        client.unpause_container = AsyncMock(return_value=True)
        client.start_vm = AsyncMock(return_value=True)
        client.stop_vm = AsyncMock(return_value=True)
        client.restart_vm = AsyncMock(return_value=True)
        client.pause_vm = AsyncMock(return_value=True)
        client.resume_vm = AsyncMock(return_value=True)
        client.hibernate_vm = AsyncMock(return_value=True)
        client.force_stop_vm = AsyncMock(return_value=True)
        client.execute_user_script = AsyncMock(return_value=True)
        client.shutdown_system = AsyncMock(return_value=True)
        client.reboot_system = AsyncMock(return_value=True)

        # Mock cleanup
        client.close = AsyncMock()

        # Store host/port for WebSocket client
        client.host = MOCK_CONFIG[CONF_HOST]
        client.port = MOCK_CONFIG[CONF_PORT]

        yield client


@pytest.fixture
def mock_websocket_client() -> Generator[MagicMock]:
    """Mock UnraidWebSocketClient from uma-api."""
    with patch(
        "custom_components.unraid_management_agent.UnraidWebSocketClient",
        autospec=True,
    ) as mock_ws_class:
        ws_client = mock_ws_class.return_value
        ws_client.start = AsyncMock()
        ws_client.stop = AsyncMock()
        ws_client.is_connected = False
        yield ws_client


@pytest.fixture
def mock_unraid_client_class(
    mock_async_unraid_client: MagicMock,
) -> Generator[MagicMock]:
    """Patch UnraidClient to return the mocked client instance."""
    mock_class = MagicMock(return_value=mock_async_unraid_client)
    with patch(
        "custom_components.unraid_management_agent.UnraidClient",
        new=mock_class,
    ):
        yield mock_class


@pytest.fixture
def mock_unraid_websocket_client_class(
    mock_websocket_client: MagicMock,
) -> Generator[MagicMock]:
    """Patch UnraidWebSocketClient to return the mocked client instance."""
    mock_class = MagicMock(return_value=mock_websocket_client)
    with patch(
        "custom_components.unraid_management_agent.UnraidWebSocketClient",
        new=mock_class,
    ):
        yield mock_class


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a mock config entry."""
    entry = (
        hass.config_entries.async_entries(DOMAIN)[0]
        if hass.config_entries.async_entries(DOMAIN)
        else None
    )

    if not entry:
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Unraid (unraid-test)",
            data=MOCK_CONFIG,
            options=MOCK_OPTIONS,
            unique_id=f"{MOCK_CONFIG[CONF_HOST]}:{MOCK_CONFIG[CONF_PORT]}",
            entry_id="test_entry_id",
        )
        entry.add_to_hass(hass)

    return entry


@pytest.fixture
def mock_unraid_data() -> UnraidData:
    """Create mock UnraidData with Pydantic models."""
    return UnraidData(
        system=mock_system_info(),
        array=mock_array_status(),
        disks=mock_disks(),
        containers=mock_containers(),
        vms=mock_vms(),
        ups=mock_ups_info(),
        gpu=mock_gpu_list(),
        network=mock_network_interfaces(),
        shares=[],
        notifications=[],
        user_scripts=[],
        zfs_pools=[],
        zfs_datasets=[],
        zfs_snapshots=[],
        zfs_arc=None,
        collectors=mock_collectors_status(),
    )


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant, mock_async_unraid_client, mock_unraid_data
) -> Generator[MagicMock]:
    """Mock UnraidDataUpdateCoordinator."""
    with patch(
        "custom_components.unraid_management_agent.UnraidDataUpdateCoordinator",
        autospec=True,
    ) as mock_coordinator_class:
        coordinator = mock_coordinator_class.return_value
        coordinator.hass = hass
        coordinator.client = mock_async_unraid_client
        coordinator.data = mock_unraid_data
        coordinator.last_update_success = True
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.async_start_websocket = AsyncMock()
        coordinator.async_stop_websocket = AsyncMock()

        # Add is_collector_enabled method - defaults to True for all collectors in tests
        def _is_collector_enabled(collector_name: str) -> bool:
            """Check if a collector is enabled (default all enabled in tests)."""
            if not coordinator.data or not coordinator.data.collectors:
                return True
            collectors = coordinator.data.collectors.collectors or []
            for c in collectors:
                if getattr(c, "name", "") == collector_name:
                    return getattr(c, "enabled", True)
            return True

        coordinator.is_collector_enabled = _is_collector_enabled

        yield coordinator


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return
