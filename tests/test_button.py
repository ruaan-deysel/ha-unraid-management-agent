"""Test the Unraid Management Agent button platform."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant


async def test_button_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test button platform setup."""
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

    # Verify button entities are created
    button_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("button")
        if entity_id.startswith("button.unraid_")
    ]

    # Should have array and parity check buttons
    assert len(button_entities) >= 4


async def test_array_start_button(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test array start button."""
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

    state = hass.states.get("button.unraid_test_start_array")
    assert state is not None


async def test_array_stop_button(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test array stop button."""
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

    state = hass.states.get("button.unraid_test_stop_array")
    assert state is not None


async def test_parity_check_buttons(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test parity check buttons."""
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

    state = hass.states.get("button.unraid_test_start_parity_check")
    assert state is not None

    state = hass.states.get("button.unraid_test_stop_parity_check")
    assert state is not None
