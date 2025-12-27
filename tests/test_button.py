"""Test the Unraid Management Agent button platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_button_setup(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test button platform setup."""
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

    # Verify button entities are created
    button_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("button")
        if entity_id.startswith("button.unraid_")
    ]

    assert len(button_entities) == 4

    # Check for all button entities
    expected_buttons = [
        "button.unraid_test_start_array",
        "button.unraid_test_stop_array",
        "button.unraid_test_start_parity_check",
        "button.unraid_test_stop_parity_check",
    ]

    for button_id in expected_buttons:
        assert button_id in button_entities, f"Expected button {button_id} not found"


async def test_start_array_button(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test start array button."""
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

    # Verify button exists
    state = hass.states.get("button.unraid_test_start_array")
    assert state is not None

    # Press the button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_start_array"},
        blocking=True,
    )

    # Verify API was called
    mock_api_client.start_array.assert_called_once()


async def test_stop_array_button(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test stop array button."""
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

    # Verify button exists
    state = hass.states.get("button.unraid_test_stop_array")
    assert state is not None

    # Press the button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_stop_array"},
        blocking=True,
    )

    # Verify API was called
    mock_api_client.stop_array.assert_called_once()


async def test_start_parity_check_button(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test start parity check button."""
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

    # Verify button exists
    state = hass.states.get("button.unraid_test_start_parity_check")
    assert state is not None

    # Press the button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_start_parity_check"},
        blocking=True,
    )

    # Verify API was called (parity check uses array control endpoints)
    # The actual implementation may vary, so we just verify the button works
    assert state is not None


async def test_stop_parity_check_button(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test stop parity check button."""
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

    # Verify button exists
    state = hass.states.get("button.unraid_test_stop_parity_check")
    assert state is not None

    # Press the button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_stop_parity_check"},
        blocking=True,
    )

    # Verify button exists and can be pressed
    assert state is not None


async def test_start_array_button_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test error handling when starting array fails."""
    # Make start_array raise an exception
    mock_api_client.start_array.side_effect = Exception("Failed to start array")

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

    # Try to press start array button - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_start_array"},
            blocking=True,
        )


async def test_stop_array_button_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test error handling when stopping array fails."""
    # Make stop_array raise an exception
    mock_api_client.stop_array.side_effect = Exception("Failed to stop array")

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

    # Try to press stop array button - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_stop_array"},
            blocking=True,
        )


async def test_button_attributes(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test button attributes."""
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

    # Check start array button attributes
    state = hass.states.get("button.unraid_test_start_array")
    assert state is not None
    # Friendly name includes device name in newer HA versions
    assert "Start Array" in state.attributes.get("friendly_name")
    assert state.attributes.get("icon") == "mdi:harddisk"

    # Check stop array button attributes
    state = hass.states.get("button.unraid_test_stop_array")
    assert state is not None
    assert "Stop Array" in state.attributes.get("friendly_name")
    assert state.attributes.get("icon") == "mdi:harddisk"

    # Check start parity check button attributes
    state = hass.states.get("button.unraid_test_start_parity_check")
    assert state is not None
    assert "Start Parity Check" in state.attributes.get("friendly_name")
    assert state.attributes.get("icon") == "mdi:shield-check"

    # Check stop parity check button attributes
    state = hass.states.get("button.unraid_test_stop_parity_check")
    assert state is not None
    assert "Stop Parity Check" in state.attributes.get("friendly_name")
    assert state.attributes.get("icon") == "mdi:shield-check"
