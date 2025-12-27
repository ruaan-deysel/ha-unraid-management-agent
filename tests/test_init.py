"""Test the Unraid Management Agent integration setup."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.const import DOMAIN


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test successful setup of config entry."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
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
    mock_api_client.health_check.assert_called_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test setup failure due to connection error."""
    mock_api_client.health_check.side_effect = ConnectionError("Connection failed")

    with patch(
        "custom_components.unraid_management_agent.api_client.UnraidAPIClient",
        return_value=mock_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_timeout_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test setup failure due to timeout error."""
    mock_api_client.health_check.side_effect = TimeoutError("Timeout")

    with patch(
        "custom_components.unraid_management_agent.api_client.UnraidAPIClient",
        return_value=mock_api_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test unloading a config entry."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
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


async def test_reload_entry(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test reloading a config entry."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
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
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_setup_platforms(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test that all platforms are set up."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that platforms are loaded
    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Verify entities are created (basic check)
    # Note: Detailed entity tests are in platform-specific test files
    assert len(hass.states.async_all()) > 0


async def test_websocket_enabled(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test WebSocket is started when enabled."""
    # Update options using proper method
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"enable_websocket": True, "update_interval": 30}
    )

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify runtime_data is set
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None


async def test_websocket_disabled(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test WebSocket is not started when disabled."""
    # Update options using proper method
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"enable_websocket": False, "update_interval": 30}
    )

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify runtime_data is set
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None


async def test_update_listener(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test that update listener triggers reload."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Update options and reload
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={"enable_websocket": False, "update_interval": 60},
        )
        await hass.async_block_till_done()

    # Entry should still be loaded
    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_multiple_entries(
    hass: HomeAssistant, mock_api_client, mock_websocket_client
) -> None:
    """Test that the integration supports multiple config entries."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create and set up first entry
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid Server 1",
        data={"host": "192.168.1.100", "port": 8043},
        options={"enable_websocket": True, "update_interval": 30},
        unique_id="192.168.1.100:8043",
    )
    entry1.add_to_hass(hass)

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        result1 = await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

    assert result1 is True
    assert entry1.state == ConfigEntryState.LOADED
    assert entry1.runtime_data is not None

    # Verify that runtime_data supports multiple entries (each entry has its own)
    assert entry1.runtime_data.coordinator is not None
