"""Test the Unraid Management Agent button platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
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


async def test_array_start_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test pressing array start button."""
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

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_start_array"},
            blocking=True,
        )

    mock_async_unraid_client.start_array.assert_called_once()


async def test_array_stop_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test pressing array stop button."""
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

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_stop_array"},
            blocking=True,
        )

    mock_async_unraid_client.stop_array.assert_called_once()


async def test_parity_check_start_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test pressing parity check start button."""
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

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_start_parity_check"},
            blocking=True,
        )

    mock_async_unraid_client.start_parity_check.assert_called_once()


async def test_parity_check_stop_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test pressing parity check stop button."""
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

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_stop_parity_check"},
            blocking=True,
        )

    mock_async_unraid_client.stop_parity_check.assert_called_once()


async def test_user_script_button(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test user script buttons are created (but disabled by default)."""
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

    # User script buttons are created but disabled by default
    # They won't appear in hass.states until enabled
    # Verify other buttons were created properly
    button_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("button")
        if entity_id.startswith("button.unraid_")
    ]
    # Should have at least the array and parity check buttons
    assert len(button_entities) >= 4


async def test_button_entity_icon(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test button entity icons."""
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

    # Check array button icon
    state = hass.states.get("button.unraid_test_start_array")
    if state:
        assert state.attributes.get("icon") == "mdi:harddisk"

    # Check parity check button icon
    state = hass.states.get("button.unraid_test_start_parity_check")
    if state:
        assert state.attributes.get("icon") == "mdi:shield-check"


async def test_user_script_button_entity_registry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test user script buttons are in entity registry."""
    from unittest.mock import MagicMock

    from homeassistant.helpers import entity_registry as er

    # Create mock user scripts
    mock_script1 = MagicMock()
    mock_script1.name = "backup_script"
    mock_script1.description = "Daily backup script"
    mock_script2 = MagicMock()
    mock_script2.name = "cleanup_script"
    mock_script2.description = "Cleanup temporary files"

    # Set up mock to return user scripts
    mock_async_unraid_client.list_user_scripts.return_value = [
        mock_script1,
        mock_script2,
    ]

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

    # Check entity registry for user script buttons (they're disabled by default)
    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, mock_config_entry.entry_id)

    # Find user script entities
    user_script_entities = [e for e in entities if "user_script" in e.unique_id]

    # We have 2 user scripts in mock data
    assert len(user_script_entities) == 2


async def test_array_start_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test array start button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_array.side_effect = Exception("Array start failed")

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

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.unraid_test_start_array"},
                blocking=True,
            )


async def test_array_stop_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test array stop button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_array.side_effect = Exception("Array stop failed")

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

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.unraid_test_stop_array"},
                blocking=True,
            )


async def test_parity_check_start_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test parity check start button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_parity_check.side_effect = Exception(
        "Parity check start failed"
    )

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

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.unraid_test_start_parity_check"},
                blocking=True,
            )


async def test_parity_check_stop_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test parity check stop button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_parity_check.side_effect = Exception(
        "Parity check stop failed"
    )

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

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.unraid_test_stop_parity_check"},
                blocking=True,
            )
