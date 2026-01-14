"""Test the Unraid Management Agent diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.diagnostics import (
    _serialize_data,
    async_get_config_entry_diagnostics,
)
from custom_components.unraid_management_agent.entity import UnraidData

from .const import (
    mock_array_status,
    mock_containers,
    mock_disks,
    mock_gpu_list,
    mock_network_interfaces,
    mock_system_info,
    mock_ups_info,
    mock_vms,
)


async def test_async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test diagnostics returns expected data structure."""
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

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Check structure
    assert "entry" in diagnostics
    assert "coordinator_data" in diagnostics
    assert diagnostics["entry"]["domain"] == "unraid_management_agent"
    assert diagnostics["entry"]["entry_id"] == mock_config_entry.entry_id

    # Check that sensitive data is redacted
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["port"] == "**REDACTED**"


def test_serialize_data_none() -> None:
    """Test serialization of None."""
    result = _serialize_data(None)
    assert result is None


def test_serialize_data_primitive() -> None:
    """Test serialization of primitive types."""
    assert _serialize_data(42) == 42
    assert _serialize_data("test") == "test"
    assert _serialize_data(3.14) == 3.14
    bool_value = True
    assert _serialize_data(bool_value) is True


def test_serialize_data_list() -> None:
    """Test serialization of lists."""
    result = _serialize_data([1, 2, 3])
    assert result == [1, 2, 3]


def test_serialize_data_dict() -> None:
    """Test serialization of dicts."""
    result = _serialize_data({"key": "value", "number": 42})
    assert result == {"key": "value", "number": 42}


def test_serialize_data_pydantic_model() -> None:
    """Test serialization of Pydantic-like models."""
    mock_model = MagicMock()
    mock_model.model_dump = MagicMock(return_value={"field": "value"})

    result = _serialize_data(mock_model)
    assert result == {"field": "value"}
    mock_model.model_dump.assert_called_once()


def test_serialize_data_dataclass() -> None:
    """Test serialization of UnraidData dataclass."""
    data = UnraidData(
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
    )

    result = _serialize_data(data)

    assert isinstance(result, dict)
    assert "system" in result
    assert "array" in result
    assert "disks" in result
    assert "containers" in result
    assert "vms" in result
    assert "ups" in result
    assert "gpu" in result
    assert "network" in result
    assert "shares" in result
    assert "notifications" in result
    assert "user_scripts" in result
    assert "zfs_pools" in result
    assert "zfs_datasets" in result
    assert "zfs_snapshots" in result
    assert "zfs_arc" in result


def test_serialize_data_nested() -> None:
    """Test serialization of nested structures."""
    nested = {"list": [1, 2, {"nested": "value"}], "dict": {"inner": [3, 4]}}
    result = _serialize_data(nested)

    assert result == {"list": [1, 2, {"nested": "value"}], "dict": {"inner": [3, 4]}}
