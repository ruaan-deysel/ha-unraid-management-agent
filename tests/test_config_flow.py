"""Test the Unraid Management Agent config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from uma_api import UnraidConnectionError

from custom_components.unraid_management_agent.const import (
    CONF_ENABLE_WEBSOCKET,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
)

from .const import MOCK_CONFIG, mock_system_info


async def test_form_user_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(return_value=mock_system_info())

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Unraid (unraid-test)"
    assert result2["data"][CONF_HOST] == MOCK_CONFIG[CONF_HOST]
    assert result2["data"][CONF_PORT] == MOCK_CONFIG[CONF_PORT]
    assert (
        result2["result"].unique_id
        == f"{MOCK_CONFIG[CONF_HOST]}:{MOCK_CONFIG[CONF_PORT]}"
    )


async def test_form_user_with_options(hass: HomeAssistant) -> None:
    """Test user config flow with custom options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user_input = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 8043,
        CONF_UPDATE_INTERVAL: 60,
        CONF_ENABLE_WEBSOCKET: False,
    }

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(return_value=mock_system_info())

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == "192.168.1.100"
    assert result2["data"][CONF_PORT] == 8043


async def test_form_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection error in user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(
        side_effect=UnraidConnectionError("Connection failed")
    )

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": ERROR_CANNOT_CONNECT}


async def test_form_user_timeout(hass: HomeAssistant) -> None:
    """Test timeout error in user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(side_effect=TimeoutError("Timeout"))

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    # TimeoutError should map to timeout error
    assert result2["errors"]["base"] == ERROR_TIMEOUT


async def test_form_user_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error in user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(side_effect=Exception("Unknown error"))

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": ERROR_UNKNOWN}


async def test_form_user_already_configured(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test we abort if already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(return_value=mock_system_info())

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test options flow."""
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

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_UPDATE_INTERVAL: 60,
            CONF_ENABLE_WEBSOCKET: False,
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_UPDATE_INTERVAL] == 60
    assert result2["data"][CONF_ENABLE_WEBSOCKET] is False


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test reconfigure flow."""
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

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(return_value=mock_system_info())

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 8043,
                CONF_UPDATE_INTERVAL: 45,
                CONF_ENABLE_WEBSOCKET: True,
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_timeout(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test reconfigure flow with timeout error."""
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

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(side_effect=TimeoutError("Timeout"))

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 8043,
                CONF_UPDATE_INTERVAL: 30,
                CONF_ENABLE_WEBSOCKET: True,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == ERROR_TIMEOUT


async def test_reconfigure_flow_connection_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test reconfigure flow with connection error."""
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

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get_system_info = AsyncMock(
        side_effect=UnraidConnectionError("Connection refused")
    )

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.200",
                CONF_PORT: 8043,
                CONF_UPDATE_INTERVAL: 30,
                CONF_ENABLE_WEBSOCKET: True,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == ERROR_CANNOT_CONNECT


async def test_validate_input_missing_hostname(hass: HomeAssistant) -> None:
    """Test validate_input with missing hostname in response."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # Create system_info with None hostname
    system_info = MagicMock()
    system_info.hostname = None
    mock_client.get_system_info = AsyncMock(return_value=system_info)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.unraid_management_agent.config_flow.AsyncUnraidClient",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

    # Should succeed with "unknown" hostname
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Unraid (unknown)"
