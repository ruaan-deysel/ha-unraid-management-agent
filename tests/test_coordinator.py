"""Extended tests for Unraid Management Agent coordinator and services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from uma_api.constants import EventType
from uma_api.events import WebSocketEvent

from custom_components.unraid_management_agent import (
    UnraidDataUpdateCoordinator,
    async_setup,
)
from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.coordinator import UnraidData

from .const import (
    MOCK_CONFIG,
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


def _create_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (test)",
        data=MOCK_CONFIG,
        options={},
        unique_id=f"{MOCK_CONFIG[CONF_HOST]}:{MOCK_CONFIG[CONF_PORT]}",
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


class TestAsyncSetup:
    """Tests for async_setup function."""

    @pytest.mark.asyncio
    async def test_async_setup_registers_services(self, hass: HomeAssistant) -> None:
        """Test async_setup registers services."""
        result = await async_setup(hass, {})
        assert result is True
        # Services should be registered
        assert hass.services.has_service(DOMAIN, "container_start")
        assert hass.services.has_service(DOMAIN, "container_stop")


class TestCoordinatorWebSocketEvents:
    """Tests for coordinator WebSocket event handling."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant) -> UnraidDataUpdateCoordinator:
        """Create a coordinator for testing."""
        entry = _create_mock_entry(hass)
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 8043
        return UnraidDataUpdateCoordinator(
            hass,
            entry=entry,
            client=mock_client,
            enable_websocket=True,
        )

    def test_handle_websocket_event_no_data(self, coordinator) -> None:
        """Test handling WebSocket event when coordinator has no data."""
        event = WebSocketEvent(event_type=EventType.SYSTEM_UPDATE, data=MagicMock())
        coordinator.data = None

        # Should return early without error
        coordinator._handle_websocket_event(event)

    def test_handle_websocket_event_system_update(self, coordinator) -> None:
        """Test handling system update WebSocket event."""
        coordinator.data = MagicMock()
        new_system_info = mock_system_info()
        event = WebSocketEvent(event_type=EventType.SYSTEM_UPDATE, data=new_system_info)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.system == new_system_info

    def test_handle_websocket_event_array_status_update(self, coordinator) -> None:
        """Test handling array status update WebSocket event."""
        coordinator.data = MagicMock()
        new_array_status = mock_array_status()
        event = WebSocketEvent(
            event_type=EventType.ARRAY_STATUS_UPDATE, data=new_array_status
        )

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.array == new_array_status

    def test_handle_websocket_event_disk_list_update(self, coordinator) -> None:
        """Test handling disk list update WebSocket event."""
        coordinator.data = MagicMock()
        new_disks = mock_disks()
        event = WebSocketEvent(event_type=EventType.DISK_LIST_UPDATE, data=new_disks)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.disks == new_disks

    def test_handle_websocket_event_disk_single_update(self, coordinator) -> None:
        """Test handling single disk update WebSocket event."""
        coordinator.data = MagicMock()
        single_disk = mock_disks()[0]
        event = WebSocketEvent(event_type=EventType.DISK_LIST_UPDATE, data=single_disk)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.disks == [single_disk]

    def test_handle_websocket_event_ups_status_update(self, coordinator) -> None:
        """Test handling UPS status update WebSocket event."""
        coordinator.data = MagicMock()
        new_ups = mock_ups_info()
        event = WebSocketEvent(event_type=EventType.UPS_STATUS_UPDATE, data=new_ups)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.ups == new_ups

    def test_handle_websocket_event_gpu_update(self, coordinator) -> None:
        """Test handling GPU update WebSocket event."""
        coordinator.data = MagicMock()
        new_gpu = mock_gpu_list()
        event = WebSocketEvent(event_type=EventType.GPU_UPDATE, data=new_gpu)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.gpu == new_gpu

    def test_handle_websocket_event_gpu_single_update(self, coordinator) -> None:
        """Test handling single GPU update WebSocket event."""
        coordinator.data = MagicMock()
        single_gpu = mock_gpu_list()[0]
        event = WebSocketEvent(event_type=EventType.GPU_UPDATE, data=single_gpu)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.gpu == [single_gpu]

    def test_handle_websocket_event_network_list_update(self, coordinator) -> None:
        """Test handling network list update WebSocket event."""
        coordinator.data = MagicMock()
        new_network = mock_network_interfaces()
        event = WebSocketEvent(
            event_type=EventType.NETWORK_LIST_UPDATE, data=new_network
        )

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.network == new_network

    def test_handle_websocket_event_container_list_update(self, coordinator) -> None:
        """Test handling container list update WebSocket event."""
        coordinator.data = MagicMock()
        new_containers = mock_containers()
        event = WebSocketEvent(
            event_type=EventType.CONTAINER_LIST_UPDATE, data=new_containers
        )

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.containers == new_containers

    def test_handle_websocket_event_vm_list_update(self, coordinator) -> None:
        """Test handling VM list update WebSocket event."""
        coordinator.data = MagicMock()
        new_vms = mock_vms()
        event = WebSocketEvent(event_type=EventType.VM_LIST_UPDATE, data=new_vms)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.vms == new_vms

    def test_handle_websocket_event_share_list_update(self, coordinator) -> None:
        """Test handling share list update WebSocket event."""
        coordinator.data = MagicMock()
        new_shares = [MagicMock()]
        event = WebSocketEvent(event_type=EventType.SHARE_LIST_UPDATE, data=new_shares)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.shares == new_shares

    def test_handle_websocket_event_notification_update(self, coordinator) -> None:
        """Test handling notification update WebSocket event."""
        coordinator.data = MagicMock()
        new_notifications = MagicMock()
        event = WebSocketEvent(
            event_type=EventType.NOTIFICATION_UPDATE, data=new_notifications
        )

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.notifications == new_notifications

    def test_handle_websocket_event_zfs_pool_update(self, coordinator) -> None:
        """Test handling ZFS pool update WebSocket event."""
        coordinator.data = MagicMock()
        new_pools = [MagicMock()]
        event = WebSocketEvent(event_type=EventType.ZFS_POOL_UPDATE, data=new_pools)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.zfs_pools == new_pools

    def test_handle_websocket_event_zfs_dataset_update(self, coordinator) -> None:
        """Test handling ZFS dataset update WebSocket event."""
        coordinator.data = MagicMock()
        new_datasets = [MagicMock()]
        event = WebSocketEvent(
            event_type=EventType.ZFS_DATASET_UPDATE, data=new_datasets
        )

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.zfs_datasets == new_datasets

    def test_handle_websocket_event_zfs_snapshot_update(self, coordinator) -> None:
        """Test handling ZFS snapshot update WebSocket event."""
        coordinator.data = MagicMock()
        new_snapshots = [MagicMock()]
        event = WebSocketEvent(
            event_type=EventType.ZFS_SNAPSHOT_UPDATE, data=new_snapshots
        )

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.zfs_snapshots == new_snapshots

    def test_handle_websocket_event_zfs_arc_update(self, coordinator) -> None:
        """Test handling ZFS ARC update WebSocket event."""
        coordinator.data = MagicMock()
        new_arc = MagicMock()
        event = WebSocketEvent(event_type=EventType.ZFS_ARC_UPDATE, data=new_arc)

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_websocket_event(event)

        assert coordinator.data.zfs_arc == new_arc

    def test_handle_raw_message_notifications_response_format(
        self, coordinator
    ) -> None:
        """Test handling raw WebSocket message with NotificationsResponse format."""
        coordinator.data = MagicMock()

        data = {
            "notifications": [{"id": "1", "message": "Test", "type": "unread"}],
            "overview": {"unread": 1, "total": 1},
        }

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_raw_message(data)

        assert coordinator.data.notifications is not None

    def test_handle_raw_message_no_data(self, coordinator) -> None:
        """Test handling raw WebSocket message when coordinator has no data."""
        coordinator.data = None

        data = {
            "notifications": [],
            "overview": {"unread": 0, "total": 0},
        }

        # Should not raise
        coordinator._handle_raw_message(data)

    def test_handle_raw_message_parse_event(self, coordinator) -> None:
        """Test handling raw WebSocket message that needs parsing."""
        coordinator.data = MagicMock()

        # Non-notification message format
        data = {"event_type": "unknown", "data": {}}

        with (
            patch(
                "custom_components.unraid_management_agent.coordinator.parse_event"
            ) as mock_parse,
            patch.object(coordinator, "_handle_websocket_event") as mock_handle,
        ):
            mock_event = MagicMock()
            mock_parse.return_value = mock_event
            coordinator._handle_raw_message(data)

            mock_parse.assert_called_once_with(data)
            mock_handle.assert_called_once_with(mock_event)

    def test_handle_raw_message_parse_error(self, coordinator) -> None:
        """Test handling raw WebSocket message with parse error."""
        coordinator.data = MagicMock()

        data = {"invalid": "message"}

        with patch(
            "custom_components.unraid_management_agent.coordinator.parse_event",
            side_effect=Exception("Parse error"),
        ):
            # Should not raise, error is logged
            coordinator._handle_raw_message(data)


class TestCoordinatorWebSocketManagement:
    """Tests for coordinator WebSocket start/stop."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant) -> UnraidDataUpdateCoordinator:
        """Create a coordinator for testing."""
        entry = _create_mock_entry(hass)
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 8043
        return UnraidDataUpdateCoordinator(
            hass,
            entry=entry,
            client=mock_client,
            enable_websocket=True,
        )

    @pytest.mark.asyncio
    async def test_async_start_websocket_disabled(self, hass: HomeAssistant) -> None:
        """Test starting WebSocket when disabled in configuration."""
        entry = _create_mock_entry(hass)
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 8043
        coordinator = UnraidDataUpdateCoordinator(
            hass,
            entry=entry,
            client=mock_client,
            enable_websocket=False,
        )

        await coordinator.async_start_websocket()

        assert coordinator._ws_client is None

    @pytest.mark.asyncio
    async def test_async_start_websocket_already_running(self, coordinator) -> None:
        """Test starting WebSocket when already connected."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        coordinator._ws_client = mock_ws

        await coordinator.async_start_websocket()

        # Should not create a new client
        assert coordinator._ws_client is mock_ws

    @pytest.mark.asyncio
    async def test_async_start_websocket_success(self, coordinator) -> None:
        """Test successful WebSocket start."""
        mock_ws = MagicMock()
        mock_ws.start = AsyncMock()

        with patch(
            "custom_components.unraid_management_agent.coordinator.UnraidWebSocketClient",
            return_value=mock_ws,
        ):
            await coordinator.async_start_websocket()

        assert coordinator._ws_client is mock_ws
        assert coordinator._ws_task is not None

    @pytest.mark.asyncio
    async def test_async_start_websocket_failure(self, coordinator) -> None:
        """Test WebSocket start failure."""
        with patch(
            "custom_components.unraid_management_agent.coordinator.UnraidWebSocketClient",
            side_effect=Exception("WebSocket error"),
        ):
            await coordinator.async_start_websocket()

        assert coordinator._ws_client is None

    @pytest.mark.asyncio
    async def test_async_stop_websocket(self, coordinator) -> None:
        """Test stopping WebSocket."""
        import asyncio

        mock_ws = MagicMock()
        mock_ws.stop = AsyncMock()
        coordinator._ws_client = mock_ws

        # Create an actual asyncio task that can be cancelled
        async def dummy_task() -> None:
            await asyncio.sleep(100)

        task = asyncio.create_task(dummy_task())
        coordinator._ws_task = task

        await coordinator.async_stop_websocket()

        mock_ws.stop.assert_called_once()
        assert coordinator._ws_client is None
        assert coordinator._ws_task is None

    @pytest.mark.asyncio
    async def test_async_stop_websocket_no_client(self, coordinator) -> None:
        """Test stopping WebSocket when no client exists."""
        coordinator._ws_client = None
        coordinator._ws_task = None

        # Should not raise
        await coordinator.async_stop_websocket()


class TestServiceHandlers:
    """Tests for service handlers."""

    @pytest.mark.asyncio
    async def test_container_start_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_start service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "container_start",
                {"container_id": "test_container"},
                blocking=True,
            )

            mock_async_unraid_client.start_container.assert_called_once_with(
                "test_container"
            )

    @pytest.mark.asyncio
    async def test_container_start_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_start service with error."""
        mock_async_unraid_client.start_container.side_effect = Exception("Start failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="container_start_failed"):
            await hass.services.async_call(
                DOMAIN,
                "container_start",
                {"container_id": "test_container"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_container_stop_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_stop service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "container_stop",
                {"container_id": "test_container"},
                blocking=True,
            )

            mock_async_unraid_client.stop_container.assert_called_once_with(
                "test_container"
            )

    @pytest.mark.asyncio
    async def test_container_stop_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_stop service with error."""
        mock_async_unraid_client.stop_container.side_effect = Exception("Stop failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="container_stop_failed"):
            await hass.services.async_call(
                DOMAIN,
                "container_stop",
                {"container_id": "test_container"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_container_restart_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_restart service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "container_restart",
                {"container_id": "test_container"},
                blocking=True,
            )

            mock_async_unraid_client.restart_container.assert_called_once_with(
                "test_container"
            )

    @pytest.mark.asyncio
    async def test_container_restart_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_restart service with error."""
        mock_async_unraid_client.restart_container.side_effect = Exception(
            "Restart failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="container_restart_failed"):
            await hass.services.async_call(
                DOMAIN,
                "container_restart",
                {"container_id": "test_container"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_container_pause_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_pause service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "container_pause",
                {"container_id": "test_container"},
                blocking=True,
            )

            mock_async_unraid_client.pause_container.assert_called_once_with(
                "test_container"
            )

    @pytest.mark.asyncio
    async def test_container_pause_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_pause service with error."""
        mock_async_unraid_client.pause_container.side_effect = Exception("Pause failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="container_pause_failed"):
            await hass.services.async_call(
                DOMAIN,
                "container_pause",
                {"container_id": "test_container"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_container_resume_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_resume service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "container_resume",
                {"container_id": "test_container"},
                blocking=True,
            )

            mock_async_unraid_client.unpause_container.assert_called_once_with(
                "test_container"
            )

    @pytest.mark.asyncio
    async def test_container_resume_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test container_resume service with error."""
        mock_async_unraid_client.unpause_container.side_effect = Exception(
            "Resume failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="container_resume_failed"):
            await hass.services.async_call(
                DOMAIN,
                "container_resume",
                {"container_id": "test_container"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_vm_start_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_start service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "vm_start",
                {"vm_id": "test_vm"},
                blocking=True,
            )

            mock_async_unraid_client.start_vm.assert_called_once_with("test_vm")

    @pytest.mark.asyncio
    async def test_vm_start_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_start service with error."""
        mock_async_unraid_client.start_vm.side_effect = Exception("Start failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="vm_start_failed"):
            await hass.services.async_call(
                DOMAIN,
                "vm_start",
                {"vm_id": "test_vm"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_vm_stop_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_stop service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "vm_stop",
                {"vm_id": "test_vm"},
                blocking=True,
            )

            mock_async_unraid_client.stop_vm.assert_called_once_with("test_vm")

    @pytest.mark.asyncio
    async def test_vm_stop_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_stop service with error."""
        mock_async_unraid_client.stop_vm.side_effect = Exception("Stop failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="vm_stop_failed"):
            await hass.services.async_call(
                DOMAIN,
                "vm_stop",
                {"vm_id": "test_vm"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_vm_restart_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_restart service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "vm_restart",
                {"vm_id": "test_vm"},
                blocking=True,
            )

            mock_async_unraid_client.restart_vm.assert_called_once_with("test_vm")

    @pytest.mark.asyncio
    async def test_vm_restart_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_restart service with error."""
        mock_async_unraid_client.restart_vm.side_effect = Exception("Restart failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="vm_restart_failed"):
            await hass.services.async_call(
                DOMAIN,
                "vm_restart",
                {"vm_id": "test_vm"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_vm_pause_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_pause service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "vm_pause",
                {"vm_id": "test_vm"},
                blocking=True,
            )

            mock_async_unraid_client.pause_vm.assert_called_once_with("test_vm")

    @pytest.mark.asyncio
    async def test_vm_pause_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_pause service with error."""
        mock_async_unraid_client.pause_vm.side_effect = Exception("Pause failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="vm_pause_failed"):
            await hass.services.async_call(
                DOMAIN,
                "vm_pause",
                {"vm_id": "test_vm"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_vm_resume_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_resume service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "vm_resume",
                {"vm_id": "test_vm"},
                blocking=True,
            )

            mock_async_unraid_client.resume_vm.assert_called_once_with("test_vm")

    @pytest.mark.asyncio
    async def test_vm_resume_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_resume service with error."""
        mock_async_unraid_client.resume_vm.side_effect = Exception("Resume failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="vm_resume_failed"):
            await hass.services.async_call(
                DOMAIN,
                "vm_resume",
                {"vm_id": "test_vm"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_vm_hibernate_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_hibernate service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "vm_hibernate",
                {"vm_id": "test_vm"},
                blocking=True,
            )

            mock_async_unraid_client.hibernate_vm.assert_called_once_with("test_vm")

    @pytest.mark.asyncio
    async def test_vm_hibernate_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_hibernate service with error."""
        mock_async_unraid_client.hibernate_vm.side_effect = Exception(
            "Hibernate failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="vm_hibernate_failed"):
            await hass.services.async_call(
                DOMAIN,
                "vm_hibernate",
                {"vm_id": "test_vm"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_vm_force_stop_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_force_stop service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "vm_force_stop",
                {"vm_id": "test_vm"},
                blocking=True,
            )

            mock_async_unraid_client.force_stop_vm.assert_called_once_with("test_vm")

    @pytest.mark.asyncio
    async def test_vm_force_stop_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test vm_force_stop service with error."""
        mock_async_unraid_client.force_stop_vm.side_effect = Exception(
            "Force stop failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="vm_force_stop_failed"):
            await hass.services.async_call(
                DOMAIN,
                "vm_force_stop",
                {"vm_id": "test_vm"},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_parity_check_pause_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test parity_check_pause service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "parity_check_pause",
                {},
                blocking=True,
            )

            mock_async_unraid_client.pause_parity_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_parity_check_pause_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test parity_check_pause service with error."""
        mock_async_unraid_client.pause_parity_check.side_effect = Exception(
            "Pause failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="parity_check_pause_failed"):
            await hass.services.async_call(
                DOMAIN,
                "parity_check_pause",
                {},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_parity_check_resume_service(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test parity_check_resume service."""
        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            await hass.services.async_call(
                DOMAIN,
                "parity_check_resume",
                {},
                blocking=True,
            )

            mock_async_unraid_client.resume_parity_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_parity_check_resume_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test parity_check_resume service with error."""
        mock_async_unraid_client.resume_parity_check.side_effect = Exception(
            "Resume failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="parity_check_resume_failed"):
            await hass.services.async_call(
                DOMAIN,
                "parity_check_resume",
                {},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_array_start_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test array_start service with error."""
        mock_async_unraid_client.start_array.side_effect = Exception("Start failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="array_start_failed"):
            await hass.services.async_call(
                DOMAIN,
                "array_start",
                {},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_array_stop_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test array_stop service with error."""
        mock_async_unraid_client.stop_array.side_effect = Exception("Stop failed")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="array_stop_failed"):
            await hass.services.async_call(
                DOMAIN,
                "array_stop",
                {},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_parity_check_start_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test parity_check_start service with error."""
        mock_async_unraid_client.start_parity_check.side_effect = Exception(
            "Start failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="parity_check_start_failed"):
            await hass.services.async_call(
                DOMAIN,
                "parity_check_start",
                {},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_parity_check_stop_service_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test parity_check_stop service with error."""
        mock_async_unraid_client.stop_parity_check.side_effect = Exception(
            "Stop failed"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="parity_check_stop_failed"):
            await hass.services.async_call(
                DOMAIN,
                "parity_check_stop",
                {},
                blocking=True,
            )


class TestCoordinatorIsCollectorEnabled:
    """Tests for coordinator is_collector_enabled method."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant) -> UnraidDataUpdateCoordinator:
        """Create a coordinator for testing."""
        entry = _create_mock_entry(hass)
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 8043
        return UnraidDataUpdateCoordinator(
            hass,
            entry=entry,
            client=mock_client,
            enable_websocket=True,
        )

    def test_is_collector_enabled_no_data(self, coordinator) -> None:
        """Test is_collector_enabled when coordinator has no data."""
        coordinator.data = None
        # Should default to True when no data
        assert coordinator.is_collector_enabled("docker") is True

    def test_is_collector_enabled_no_collectors(self, coordinator) -> None:
        """Test is_collector_enabled when collectors is None."""
        coordinator.data = UnraidData()
        coordinator.data.collectors = None
        # Should default to True when no collectors data
        assert coordinator.is_collector_enabled("docker") is True

    def test_is_collector_enabled_empty_collectors(self, coordinator) -> None:
        """Test is_collector_enabled when collectors list is empty."""
        coordinator.data = UnraidData()
        mock_collectors = MagicMock()
        mock_collectors.collectors = []
        coordinator.data.collectors = mock_collectors
        # Collector not in list should default to True
        assert coordinator.is_collector_enabled("docker") is True

    def test_is_collector_enabled_collector_found_enabled(self, coordinator) -> None:
        """Test is_collector_enabled when collector is found and enabled."""
        coordinator.data = UnraidData()
        mock_collector = MagicMock()
        mock_collector.name = "docker"
        mock_collector.enabled = True
        mock_collectors = MagicMock()
        mock_collectors.collectors = [mock_collector]
        coordinator.data.collectors = mock_collectors

        assert coordinator.is_collector_enabled("docker") is True

    def test_is_collector_enabled_collector_found_disabled(self, coordinator) -> None:
        """Test is_collector_enabled when collector is found and disabled."""
        coordinator.data = UnraidData()
        mock_collector = MagicMock()
        mock_collector.name = "zfs"
        mock_collector.enabled = False
        mock_collectors = MagicMock()
        mock_collectors.collectors = [mock_collector]
        coordinator.data.collectors = mock_collectors

        assert coordinator.is_collector_enabled("zfs") is False

    def test_is_collector_enabled_collector_not_found(self, coordinator) -> None:
        """Test is_collector_enabled when collector is not in the list."""
        coordinator.data = UnraidData()
        mock_collector = MagicMock()
        mock_collector.name = "docker"
        mock_collector.enabled = True
        mock_collectors = MagicMock()
        mock_collectors.collectors = [mock_collector]
        coordinator.data.collectors = mock_collectors

        # Unknown collector should default to True
        assert coordinator.is_collector_enabled("unknown_collector") is True

    def test_is_collector_enabled_with_full_collectors(self, coordinator) -> None:
        """Test is_collector_enabled with full collectors status."""
        coordinator.data = UnraidData()
        coordinator.data.collectors = mock_collectors_status(all_enabled=False)

        # Enabled collectors
        assert coordinator.is_collector_enabled("docker") is True
        assert coordinator.is_collector_enabled("vm") is True
        assert coordinator.is_collector_enabled("system") is True

        # Disabled collectors
        assert coordinator.is_collector_enabled("nut") is False
        assert coordinator.is_collector_enabled("zfs") is False
        assert coordinator.is_collector_enabled("unassigned") is False


class TestCoordinatorDataUpdate:
    """Tests for coordinator _async_update_data edge cases."""

    @pytest.mark.asyncio
    async def test_async_update_data_optional_endpoints_fail_gracefully(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles optional endpoints failing with 404 gracefully."""
        # Make optional API endpoints fail with 404
        mock_async_unraid_client.list_gpus.side_effect = Exception("404 Not Found")
        mock_async_unraid_client.get_zfs_arc_stats.side_effect = Exception(
            "404 Not Found"
        )
        mock_async_unraid_client.list_zfs_datasets.side_effect = Exception(
            "404 Not Found"
        )
        mock_async_unraid_client.list_zfs_snapshots.side_effect = Exception(
            "404 Not Found"
        )
        mock_async_unraid_client.list_user_scripts.side_effect = Exception(
            "404 Not Found"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Setup should succeed since these are optional endpoints
            assert result is True

            # Verify core sensors exist
            sensor_entities = [
                entity_id
                for entity_id in hass.states.async_entity_ids("sensor")
                if entity_id.startswith("sensor.unraid_")
            ]
            assert len(sensor_entities) > 0

    @pytest.mark.asyncio
    async def test_async_update_data_partial_data(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles partial data (some endpoints fail)."""
        # Make some API calls fail (e.g., optional features)
        mock_async_unraid_client.list_zfs_pools.side_effect = Exception(
            "ZFS not available"
        )
        mock_async_unraid_client.list_zfs_datasets.side_effect = Exception(
            "ZFS not available"
        )
        mock_async_unraid_client.list_zfs_snapshots.side_effect = Exception(
            "ZFS not available"
        )
        mock_async_unraid_client.get_zfs_arc_stats.side_effect = Exception(
            "404 Not Found"
        )
        mock_async_unraid_client.list_gpus.side_effect = Exception("404 Not Found")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Setup should succeed even with partial data
            assert result is True

            # Verify core sensors exist
            sensor_entities = [
                entity_id
                for entity_id in hass.states.async_entity_ids("sensor")
                if entity_id.startswith("sensor.unraid_")
            ]
            assert len(sensor_entities) > 0


class TestCoordinatorAPIExceptionHandling:
    """Tests for coordinator API exception handling (lines 170-269)."""

    @pytest.mark.asyncio
    async def test_api_system_info_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles system info API exception."""
        mock_async_unraid_client.get_system_info.side_effect = Exception(
            "System info error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Should still succeed - system info is optional
            assert result is True

    @pytest.mark.asyncio
    async def test_api_array_status_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles array status API exception."""
        mock_async_unraid_client.get_array_status.side_effect = Exception(
            "Array status error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_disks_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles disks API exception."""
        mock_async_unraid_client.list_disks.side_effect = Exception("Disks error")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_containers_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles containers API exception."""
        mock_async_unraid_client.list_containers.side_effect = Exception(
            "Containers error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_vms_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles VMs API exception."""
        mock_async_unraid_client.list_vms.side_effect = Exception("VMs error")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_ups_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles UPS API exception."""
        mock_async_unraid_client.get_ups_info.side_effect = Exception("UPS error")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_network_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles network interfaces API exception."""
        mock_async_unraid_client.list_network_interfaces.side_effect = Exception(
            "Network error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_shares_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles shares API exception."""
        mock_async_unraid_client.list_shares.side_effect = Exception("Shares error")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_notifications_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles notifications API exception."""
        mock_async_unraid_client.list_notifications.side_effect = Exception(
            "Notifications error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_user_scripts_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles user scripts API exception."""
        mock_async_unraid_client.list_user_scripts.side_effect = Exception(
            "User scripts error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_zfs_pools_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles ZFS pools API exception."""
        mock_async_unraid_client.list_zfs_pools.side_effect = Exception(
            "ZFS pools error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_zfs_datasets_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles ZFS datasets API exception."""
        mock_async_unraid_client.list_zfs_datasets.side_effect = Exception(
            "ZFS datasets error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_zfs_snapshots_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles ZFS snapshots API exception."""
        mock_async_unraid_client.list_zfs_snapshots.side_effect = Exception(
            "ZFS snapshots error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_gpu_exception_non_404(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles GPU API exception (non-404)."""
        mock_async_unraid_client.list_gpus.side_effect = Exception("GPU timeout")

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_zfs_arc_exception_non_404(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles ZFS ARC API exception (non-404)."""
        mock_async_unraid_client.get_zfs_arc_stats.side_effect = Exception(
            "ARC timeout"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True

    @pytest.mark.asyncio
    async def test_api_collectors_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client,
        mock_websocket_client,
    ) -> None:
        """Test coordinator handles collectors API exception."""
        mock_async_unraid_client.get_collectors_status.side_effect = Exception(
            "Collectors error"
        )

        with (
            patch(
                "custom_components.unraid_management_agent.UnraidClient",
                return_value=mock_async_unraid_client,
            ),
            patch(
                "custom_components.unraid_management_agent.UnraidWebSocketClient",
                return_value=mock_websocket_client,
            ),
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert result is True


# ==================== Entity Tests ====================


class TestUnraidEntity:
    """Tests for UnraidEntity class."""

    def test_unraid_entity_init(self) -> None:
        """Test UnraidEntity initialization."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.entity import (
            UnraidEntity,
            UnraidEntityDescription,
        )

        # Create entity using object.__new__ to bypass init
        entity = object.__new__(UnraidEntity)

        # Create description
        description = UnraidEntityDescription(
            key="test_key",
            translation_key="test_translation",
        )

        # Create mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.entry_id = "test_entry"
        mock_coordinator.data = MagicMock()
        mock_coordinator.data.system = MagicMock()
        mock_coordinator.data.system.hostname = "TestServer"
        mock_coordinator.data.system.version = "6.12.4"
        mock_coordinator.data.system.agent_version = "1.0.0"

        # Set required attributes
        entity.entity_description = description
        entity.coordinator = mock_coordinator
        entity._attr_unique_id = "test_unique_id"

        assert entity.entity_description.key == "test_key"

    def test_unraid_entity_available_when_coordinator_unavailable(self) -> None:
        """Test UnraidEntity.available returns False when coordinator is unavailable."""
        from unittest.mock import PropertyMock

        from custom_components.unraid_management_agent.entity import (
            UnraidEntity,
            UnraidEntityDescription,
        )

        # Create entity using object.__new__ to bypass init
        entity = object.__new__(UnraidEntity)

        # Create description with available_fn
        description = UnraidEntityDescription(
            key="test_key",
            translation_key="test_translation",
            available_fn=lambda _coord: True,
        )

        entity.entity_description = description

        # Mock the parent class's available property to return False
        with patch.object(
            type(entity).__bases__[0], "available", new_callable=PropertyMock
        ) as mock_available:
            mock_available.return_value = False

            # Should return False because parent is unavailable
            result = entity.available
            assert result is False

    def test_unraid_entity_available_when_available_fn_returns_false(self) -> None:
        """Test UnraidEntity.available returns False when available_fn returns False."""
        from unittest.mock import MagicMock, PropertyMock

        from custom_components.unraid_management_agent.entity import (
            UnraidEntity,
            UnraidEntityDescription,
        )

        # Create entity using object.__new__ to bypass init
        entity = object.__new__(UnraidEntity)

        # Mock coordinator
        mock_coordinator = MagicMock()
        entity.coordinator = mock_coordinator

        # Create description with available_fn that returns False
        description = UnraidEntityDescription(
            key="test_key",
            translation_key="test_translation",
            available_fn=lambda _coord: False,  # Always unavailable
        )

        entity.entity_description = description

        # Mock the parent class's available property to return True
        with patch.object(
            type(entity).__bases__[0], "available", new_callable=PropertyMock
        ) as mock_available:
            mock_available.return_value = True

            # Should return False because available_fn returns False
            result = entity.available
            assert result is False

    def test_unraid_entity_available_when_all_true(self) -> None:
        """Test UnraidEntity.available returns True when all conditions met."""
        from unittest.mock import MagicMock, PropertyMock

        from custom_components.unraid_management_agent.entity import (
            UnraidEntity,
            UnraidEntityDescription,
        )

        # Create entity using object.__new__ to bypass init
        entity = object.__new__(UnraidEntity)

        # Mock coordinator
        mock_coordinator = MagicMock()
        entity.coordinator = mock_coordinator

        # Create description with available_fn that returns True
        description = UnraidEntityDescription(
            key="test_key",
            translation_key="test_translation",
            available_fn=lambda _coord: True,
        )

        entity.entity_description = description

        # Mock the parent class's available property to return True
        with patch.object(
            type(entity).__bases__[0], "available", new_callable=PropertyMock
        ) as mock_available:
            mock_available.return_value = True

            # Should return True
            result = entity.available
            assert result is True


class TestCoordinatorServiceSettings:
    """Tests for service enabled checks in coordinator."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant) -> UnraidDataUpdateCoordinator:
        """Create a coordinator for testing."""
        entry = _create_mock_entry(hass)
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 8043
        return UnraidDataUpdateCoordinator(
            hass,
            entry=entry,
            client=mock_client,
            enable_websocket=False,
        )

    def test_is_docker_enabled_no_data(self, coordinator) -> None:
        """Test is_docker_enabled returns True when no data."""
        coordinator.data = None
        assert coordinator.is_docker_enabled() is True

    def test_is_docker_enabled_no_settings(self, coordinator) -> None:
        """Test is_docker_enabled returns True when no docker_settings."""
        coordinator.data = MagicMock()
        coordinator.data.docker_settings = None
        assert coordinator.is_docker_enabled() is True

    def test_is_docker_enabled_true(self, coordinator) -> None:
        """Test is_docker_enabled returns True when enabled."""
        coordinator.data = MagicMock()
        mock_settings = MagicMock()
        mock_settings.enabled = True
        coordinator.data.docker_settings = mock_settings
        assert coordinator.is_docker_enabled() is True

    def test_is_docker_enabled_false(self, coordinator) -> None:
        """Test is_docker_enabled returns False when disabled."""
        coordinator.data = MagicMock()
        mock_settings = MagicMock()
        mock_settings.enabled = False
        coordinator.data.docker_settings = mock_settings
        assert coordinator.is_docker_enabled() is False

    def test_is_vm_enabled_no_data(self, coordinator) -> None:
        """Test is_vm_enabled returns True when no data."""
        coordinator.data = None
        assert coordinator.is_vm_enabled() is True

    def test_is_vm_enabled_no_settings(self, coordinator) -> None:
        """Test is_vm_enabled returns True when no vm_settings."""
        coordinator.data = MagicMock()
        coordinator.data.vm_settings = None
        assert coordinator.is_vm_enabled() is True

    def test_is_vm_enabled_true(self, coordinator) -> None:
        """Test is_vm_enabled returns True when enabled."""
        coordinator.data = MagicMock()
        mock_settings = MagicMock()
        mock_settings.enabled = True
        coordinator.data.vm_settings = mock_settings
        assert coordinator.is_vm_enabled() is True

    def test_is_vm_enabled_false(self, coordinator) -> None:
        """Test is_vm_enabled returns False when disabled."""
        coordinator.data = MagicMock()
        mock_settings = MagicMock()
        mock_settings.enabled = False
        coordinator.data.vm_settings = mock_settings
        assert coordinator.is_vm_enabled() is False


class TestCoordinatorRawMessageHandling:
    """Tests for raw WebSocket message handling in coordinator."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant) -> UnraidDataUpdateCoordinator:
        """Create a coordinator for testing."""
        entry = _create_mock_entry(hass)
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 8043
        return UnraidDataUpdateCoordinator(
            hass,
            entry=entry,
            client=mock_client,
            enable_websocket=True,
        )

    def test_handle_raw_message_notifications_response(self, coordinator) -> None:
        """Test handling raw message with NotificationsResponse format."""
        coordinator.data = MagicMock()

        # NotificationsResponse format has both notifications and overview keys
        raw_data = {
            "notifications": [{"id": 1, "message": "Test notification"}],
            "overview": {"unread": 1, "archive": 0},
        }

        with patch.object(coordinator, "async_set_updated_data"):
            coordinator._handle_raw_message(raw_data)

        assert coordinator.data.notifications is not None

    def test_handle_raw_message_parse_error(self, coordinator) -> None:
        """Test handling raw message with parse error."""
        coordinator.data = MagicMock()

        # Data that will fail to parse
        raw_data = {"invalid": "data"}

        with patch(
            "custom_components.unraid_management_agent.coordinator.parse_event",
            side_effect=Exception("Parse error"),
        ):
            # Should not raise, just log debug
            coordinator._handle_raw_message(raw_data)

    def test_handle_raw_message_normal_event(self, coordinator) -> None:
        """Test handling raw message with normal event."""
        coordinator.data = MagicMock()

        raw_data = {"type": "system_update", "data": {"hostname": "tower"}}

        mock_event = MagicMock()
        mock_event.event_type = EventType.SYSTEM_UPDATE
        mock_event.data = MagicMock()

        with (
            patch(
                "custom_components.unraid_management_agent.coordinator.parse_event",
                return_value=mock_event,
            ),
            patch.object(coordinator, "_handle_websocket_event") as mock_handle,
            patch.object(coordinator, "async_set_updated_data"),
        ):
            coordinator._handle_raw_message(raw_data)
            mock_handle.assert_called_once_with(mock_event)


class TestCoordinatorAPIErrorHandling:
    """Tests for coordinator API error handling branches."""

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant) -> UnraidDataUpdateCoordinator:
        """Create a coordinator for testing."""
        entry = _create_mock_entry(hass)
        mock_client = MagicMock()
        mock_client.host = "192.168.1.100"
        mock_client.port = 8043
        return UnraidDataUpdateCoordinator(
            hass,
            entry=entry,
            client=mock_client,
            enable_websocket=False,
        )

    @pytest.fixture
    def mock_repairs(self):
        """Mock the repairs module to prevent import issues."""
        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ) as mock_check:
            yield mock_check

    @pytest.mark.asyncio
    async def test_api_error_logs_warning_once(self, coordinator, mock_repairs) -> None:
        """Test API error logs warning only once when repairs module fails."""
        from homeassistant.helpers.update_coordinator import UpdateFailed
        from uma_api.models import SystemInfo

        # Setup valid API responses
        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        # Make repairs module throw an error
        mock_repairs.side_effect = Exception("Repairs error")

        # First error should raise UpdateFailed
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        assert coordinator._unavailable_logged is True
        assert coordinator.update_success is False

    @pytest.mark.asyncio
    async def test_disk_settings_error_continues(
        self, coordinator, mock_repairs
    ) -> None:
        """Test disk_settings error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        # This one fails
        coordinator.client.get_disk_settings = AsyncMock(
            side_effect=Exception("Disk settings error")
        )
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite disk_settings error
        assert data is not None
        assert data.disk_settings is None

    @pytest.mark.asyncio
    async def test_mover_settings_error_continues(
        self, coordinator, mock_repairs
    ) -> None:
        """Test mover_settings error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.get_mover_settings = AsyncMock(
            side_effect=Exception("Mover settings error")
        )
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite mover_settings error
        assert data is not None
        assert data.mover_settings is None

    @pytest.mark.asyncio
    async def test_parity_schedule_error_continues(
        self, coordinator, mock_repairs
    ) -> None:
        """Test parity_schedule error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.get_parity_schedule = AsyncMock(
            side_effect=Exception("Parity schedule error")
        )
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite parity_schedule error
        assert data is not None
        assert data.parity_schedule is None

    @pytest.mark.asyncio
    async def test_parity_history_error_continues(
        self, coordinator, mock_repairs
    ) -> None:
        """Test parity_history error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.get_parity_history = AsyncMock(
            side_effect=Exception("Parity history error")
        )
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite parity_history error
        assert data is not None
        assert data.parity_history is None

    @pytest.mark.asyncio
    async def test_flash_info_error_continues(self, coordinator, mock_repairs) -> None:
        """Test flash_info error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.get_flash_info = AsyncMock(
            side_effect=Exception("Flash info error")
        )
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite flash_info error
        assert data is not None
        assert data.flash_info is None

    @pytest.mark.asyncio
    async def test_plugins_error_continues(self, coordinator, mock_repairs) -> None:
        """Test plugins error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.list_plugins = AsyncMock(
            side_effect=Exception("Plugins error")
        )
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite plugins error
        assert data is not None
        assert data.plugins is None

    @pytest.mark.asyncio
    async def test_update_status_error_continues(
        self, coordinator, mock_repairs
    ) -> None:
        """Test update_status error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.get_update_status = AsyncMock(
            side_effect=Exception("Update status error")
        )
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite update_status error
        assert data is not None
        assert data.update_status is None

    @pytest.mark.asyncio
    async def test_docker_settings_error_continues(
        self, coordinator, mock_repairs
    ) -> None:
        """Test docker_settings error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.get_docker_settings = AsyncMock(
            side_effect=Exception("Docker settings error")
        )
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite docker_settings error
        assert data is not None
        assert data.docker_settings is None

    @pytest.mark.asyncio
    async def test_vm_settings_error_continues(self, coordinator, mock_repairs) -> None:
        """Test vm_settings error is logged but update continues."""
        from uma_api.models import SystemInfo

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        # This one fails
        coordinator.client.get_vm_settings = AsyncMock(
            side_effect=Exception("VM settings error")
        )

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Update should succeed despite vm_settings error
        assert data is not None
        assert data.vm_settings is None

    @pytest.mark.asyncio
    async def test_connection_restored_logs_info(
        self, coordinator, mock_repairs
    ) -> None:
        """Test connection restore logs info when previously unavailable."""
        from uma_api.models import SystemInfo

        # Set unavailable flag to True first
        coordinator._unavailable_logged = True

        coordinator.client.get_system_info = AsyncMock(
            return_value=SystemInfo(hostname="tower", uptime_seconds=1000)
        )
        coordinator.client.get_array_status = AsyncMock(
            return_value=mock_array_status()
        )
        coordinator.client.get_network_interfaces = AsyncMock(
            return_value=mock_network_interfaces()
        )
        coordinator.client.list_disks = AsyncMock(return_value=mock_disks())
        coordinator.client.list_containers = AsyncMock(return_value=mock_containers())
        coordinator.client.list_vms = AsyncMock(return_value=mock_vms())
        coordinator.client.list_shares = AsyncMock(return_value=[])
        coordinator.client.list_gpus = AsyncMock(return_value=mock_gpu_list())
        coordinator.client.get_ups_info = AsyncMock(return_value=mock_ups_info())
        coordinator.client.get_notifications = AsyncMock(return_value=None)
        coordinator.client.list_zfs_pools = AsyncMock(return_value=[])
        coordinator.client.list_zfs_datasets = AsyncMock(return_value=[])
        coordinator.client.list_zfs_snapshots = AsyncMock(return_value=[])
        coordinator.client.get_zfs_arc_stats = AsyncMock(return_value=None)
        coordinator.client.get_collectors_status = AsyncMock(
            return_value=mock_collectors_status()
        )
        coordinator.client.get_disk_settings = AsyncMock(return_value=None)
        coordinator.client.get_mover_settings = AsyncMock(return_value=None)
        coordinator.client.get_parity_schedule = AsyncMock(return_value=None)
        coordinator.client.get_parity_history = AsyncMock(return_value=None)
        coordinator.client.get_flash_info = AsyncMock(return_value=None)
        coordinator.client.list_plugins = AsyncMock(return_value=None)
        coordinator.client.get_update_status = AsyncMock(return_value=None)
        coordinator.client.get_docker_settings = AsyncMock(return_value=None)
        coordinator.client.get_vm_settings = AsyncMock(return_value=None)

        with patch(
            "custom_components.unraid_management_agent.repairs.async_check_and_create_issues",
            new_callable=AsyncMock,
        ):
            data = await coordinator._async_update_data()

        # Unavailable flag should be reset
        assert coordinator._unavailable_logged is False
        assert coordinator.update_success is True
        assert data is not None
