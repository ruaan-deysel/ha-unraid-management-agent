"""Test the Unraid Management Agent integration setup."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from uma_api import UnraidConnectionError

from custom_components.unraid_management_agent.const import DOMAIN


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test successful setup of config entry."""
    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
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
        "custom_components.unraid_management_agent.AsyncUnraidClient",
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
        "custom_components.unraid_management_agent.AsyncUnraidClient",
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
            "custom_components.unraid_management_agent.AsyncUnraidClient",
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
            "custom_components.unraid_management_agent.AsyncUnraidClient",
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
            "custom_components.unraid_management_agent.AsyncUnraidClient",
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
            "custom_components.unraid_management_agent.AsyncUnraidClient",
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
