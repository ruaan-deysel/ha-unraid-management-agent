"""Test the Unraid Management Agent integration setup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent import (
    _async_migrate_legacy_entity_unique_ids,
    _make_vm_key,
)
from custom_components.unraid_management_agent.api import UnraidConnectionError
from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.coordinator import UnraidData


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test successful setup of config entry."""
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

    assert mock_config_entry.state == ConfigEntryState.LOADED
    # Verify runtime_data is set
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None
    assert mock_config_entry.runtime_data.client is not None

    # Verify health check was called
    mock_async_unraid_client.health_check.assert_called_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_async_unraid_client
) -> None:
    """Test setup failure due to connection error."""
    mock_async_unraid_client.health_check.side_effect = UnraidConnectionError(
        "Connection failed"
    )

    with patch(
        "custom_components.unraid_management_agent.UnraidClient",
        return_value=mock_async_unraid_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_unexpected_error(
    hass: HomeAssistant, mock_config_entry, mock_async_unraid_client
) -> None:
    """Test setup failure due to unexpected error."""
    mock_async_unraid_client.health_check.side_effect = Exception("Unexpected error")

    with patch(
        "custom_components.unraid_management_agent.UnraidClient",
        return_value=mock_async_unraid_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test unloading a config entry."""
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

    assert mock_config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    # Verify client was closed
    mock_async_unraid_client.close.assert_called_once()


async def test_reload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test reloading a config entry."""
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

    assert mock_config_entry.state == ConfigEntryState.LOADED

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
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_services_registered(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test services are registered after setup."""
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

    # Verify services are registered
    assert hass.services.has_service(DOMAIN, "container_start")
    assert hass.services.has_service(DOMAIN, "container_stop")
    assert hass.services.has_service(DOMAIN, "container_restart")
    assert hass.services.has_service(DOMAIN, "vm_start")
    assert hass.services.has_service(DOMAIN, "vm_stop")
    assert hass.services.has_service(DOMAIN, "array_start")
    assert hass.services.has_service(DOMAIN, "array_stop")
    assert hass.services.has_service(DOMAIN, "parity_check_start")
    assert hass.services.has_service(DOMAIN, "parity_check_stop")


def test_make_vm_key_uses_identifier_when_name_changes() -> None:
    """Test VM key prefers the backend identifier when it differs from the display name."""
    assert (
        _make_vm_key("Windows Server 2016", "Home Assistant") == "windows_server_2016"
    )


async def test_migrate_legacy_unique_ids_skips_when_no_data(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test legacy unique ID migration exits early when coordinator data is unavailable."""
    coordinator = MagicMock()
    coordinator.data = None

    await _async_migrate_legacy_entity_unique_ids(hass, mock_config_entry, coordinator)


async def test_migrate_legacy_vm_unique_id_skips_when_target_exists(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test legacy VM migration does not rewrite entities when the target unique ID already exists."""
    coordinator = MagicMock()
    vm = MagicMock()
    vm.id = "Windows Server 2016"
    vm.name = "Home Assistant"
    coordinator.data = UnraidData(vms=[vm])

    source_entry = MagicMock(
        domain="switch",
        unique_id=f"{mock_config_entry.entry_id}_vm_switch_Windows Server 2016",
        entity_id="switch.cube_vm_home_assistant_old",
    )
    target_entry = MagicMock(
        domain="switch",
        unique_id=f"{mock_config_entry.entry_id}_vm_windows_server_2016",
        entity_id="switch.cube_vm_home_assistant",
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.unraid_management_agent.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.unraid_management_agent.er.async_entries_for_config_entry",
            return_value=[source_entry, target_entry],
        ),
    ):
        await _async_migrate_legacy_entity_unique_ids(
            hass, mock_config_entry, coordinator
        )

    registry.async_update_entity.assert_not_called()


async def test_migrate_legacy_vm_unique_id_handles_registry_update_error(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test legacy VM migration tolerates registry update errors."""
    coordinator = MagicMock()
    vm = MagicMock()
    vm.id = "Windows Server 2016"
    vm.name = "Home Assistant"
    coordinator.data = UnraidData(vms=[vm])

    source_entry = MagicMock(
        domain="switch",
        unique_id=f"{mock_config_entry.entry_id}_vm_switch_Windows Server 2016",
        entity_id="switch.cube_vm_home_assistant_old",
    )
    registry = MagicMock()
    registry.async_update_entity.side_effect = ValueError("duplicate entity")

    with (
        patch(
            "custom_components.unraid_management_agent.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.unraid_management_agent.er.async_entries_for_config_entry",
            return_value=[source_entry],
        ),
    ):
        await _async_migrate_legacy_entity_unique_ids(
            hass, mock_config_entry, coordinator
        )

    registry.async_update_entity.assert_called_once_with(
        "switch.cube_vm_home_assistant_old",
        new_unique_id=f"{mock_config_entry.entry_id}_vm_windows_server_2016",
    )
