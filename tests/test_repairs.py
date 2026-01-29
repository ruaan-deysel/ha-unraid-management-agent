"""Test the Unraid Management Agent repairs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from uma_api.models import ArrayStatus, DiskInfo

from custom_components.unraid_management_agent.coordinator import UnraidData
from custom_components.unraid_management_agent.repairs import (
    ArrayIssueRepairFlow,
    ConnectionIssueRepairFlow,
    DiskHealthRepairFlow,
    ParityCheckRepairFlow,
    _is_ssd,
    async_check_and_create_issues,
    async_create_fix_flow,
)


async def test_create_fix_flow_connection(hass: HomeAssistant) -> None:
    """Test creating connection issue repair flow."""
    flow = await async_create_fix_flow(
        hass, "connection_test", {"error": "test error", "host": "192.168.1.100"}
    )
    assert isinstance(flow, ConnectionIssueRepairFlow)


async def test_create_fix_flow_disk_health(hass: HomeAssistant) -> None:
    """Test creating disk health repair flow."""
    flow = await async_create_fix_flow(
        hass, "disk_health_disk1", {"disk_name": "disk1", "smart_status": "OK"}
    )
    assert isinstance(flow, DiskHealthRepairFlow)


async def test_create_fix_flow_array(hass: HomeAssistant) -> None:
    """Test creating array issue repair flow."""
    flow = await async_create_fix_flow(hass, "array_parity", {"array_state": "Started"})
    assert isinstance(flow, ArrayIssueRepairFlow)


async def test_create_fix_flow_parity(hass: HomeAssistant) -> None:
    """Test creating parity check repair flow."""
    flow = await async_create_fix_flow(hass, "parity_check_stuck", {"sync_percent": 95})
    assert isinstance(flow, ParityCheckRepairFlow)


async def test_create_fix_flow_unknown(hass: HomeAssistant) -> None:
    """Test creating flow for unknown issue type."""
    from homeassistant.components.repairs import RepairsFlow

    flow = await async_create_fix_flow(hass, "unknown_issue", {})
    assert isinstance(flow, RepairsFlow)


async def test_connection_issue_repair_flow_init(hass: HomeAssistant) -> None:
    """Test connection issue repair flow initial step."""
    flow = ConnectionIssueRepairFlow(
        hass,
        "connection_test",
        {"error": "Connection refused", "host": "192.168.1.100", "port": 8043},
    )

    result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert "error" in result["description_placeholders"]
    assert result["description_placeholders"]["error"] == "Connection refused"


async def test_connection_issue_repair_flow_resolve(hass: HomeAssistant) -> None:
    """Test connection issue repair flow resolution."""
    flow = ConnectionIssueRepairFlow(hass, "connection_test", {"error": "test error"})

    with patch(
        "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
    ) as mock_delete:
        result = await flow.async_step_init(user_input={})

    assert result["type"] == "create_entry"
    mock_delete.assert_called_once()


async def test_disk_health_repair_flow_init(hass: HomeAssistant) -> None:
    """Test disk health repair flow initial step."""
    flow = DiskHealthRepairFlow(
        hass,
        "disk_health_disk1",
        {
            "disk_name": "disk1",
            "smart_status": "FAILING",
            "smart_errors": 5,
            "temperature": 55,
        },
    )

    result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["description_placeholders"]["disk_name"] == "disk1"
    assert result["description_placeholders"]["smart_status"] == "FAILING"


async def test_disk_health_repair_flow_resolve(hass: HomeAssistant) -> None:
    """Test disk health repair flow resolution."""
    flow = DiskHealthRepairFlow(hass, "disk_health_disk1", {})

    with patch(
        "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
    ):
        result = await flow.async_step_init(user_input={})

    assert result["type"] == "create_entry"


async def test_array_issue_repair_flow_init(hass: HomeAssistant) -> None:
    """Test array issue repair flow initial step."""
    flow = ArrayIssueRepairFlow(
        hass,
        "array_parity_invalid",
        {"array_state": "Started", "issue_description": "Parity disk is invalid"},
    )

    result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["description_placeholders"]["array_state"] == "Started"


async def test_array_issue_repair_flow_resolve(hass: HomeAssistant) -> None:
    """Test array issue repair flow resolution."""
    flow = ArrayIssueRepairFlow(hass, "array_parity", {})

    with patch(
        "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
    ):
        result = await flow.async_step_init(user_input={})

    assert result["type"] == "create_entry"


async def test_parity_check_repair_flow_init(hass: HomeAssistant) -> None:
    """Test parity check repair flow initial step."""
    flow = ParityCheckRepairFlow(
        hass,
        "parity_check_stuck",
        {"parity_status": "Running", "sync_percent": 96, "errors_found": 0},
    )

    result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["description_placeholders"]["parity_status"] == "Running"
    assert result["description_placeholders"]["sync_percent"] == "96"


async def test_parity_check_repair_flow_resolve(hass: HomeAssistant) -> None:
    """Test parity check repair flow resolution."""
    flow = ParityCheckRepairFlow(hass, "parity_check", {})

    with patch(
        "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
    ):
        result = await flow.async_step_init(user_input={})

    assert result["type"] == "create_entry"


def test_is_ssd_nvme_device() -> None:
    """Test SSD detection for NVMe devices."""
    disk = DiskInfo(device="nvme0n1", role="data", name="disk1", id="Samsung_990")
    assert _is_ssd(disk) is True


def test_is_ssd_cache_role() -> None:
    """Test SSD detection for cache role."""
    disk = DiskInfo(device="sda", role="cache", name="cache", id="SamsungSSD")
    assert _is_ssd(disk) is True


def test_is_ssd_cache_name() -> None:
    """Test SSD detection for cache in name."""
    disk = DiskInfo(device="sda", role="data", name="cache1", id="Unknown")
    assert _is_ssd(disk) is True


def test_is_ssd_in_id() -> None:
    """Test SSD detection from disk ID."""
    disk = DiskInfo(device="sda", role="data", name="disk1", id="Samsung_SSD_860")
    assert _is_ssd(disk) is True


def test_is_not_ssd() -> None:
    """Test HDD detection."""
    disk = DiskInfo(device="sdb", role="data", name="disk2", id="WDC_WD80EFAX")
    assert _is_ssd(disk) is False


async def test_check_and_create_issues_connection_failed(
    hass: HomeAssistant,
) -> None:
    """Test issue creation when connection fails."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = False
    coordinator.last_exception = Exception("Connection timeout")
    coordinator.data = None

    with patch(
        "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
    ) as mock_create:
        await async_check_and_create_issues(hass, coordinator)

    mock_create.assert_called_once()
    # Check that the issue was created with the expected issue_id pattern
    # The first 3 args are positional: hass, domain, issue_id
    call_args = mock_create.call_args
    assert call_args[0][2] == "connection_test_entry"


async def test_check_and_create_issues_connection_success(
    hass: HomeAssistant,
) -> None:
    """Test issue deletion when connection succeeds."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.data = UnraidData(disks=[], array=None)

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ) as mock_delete,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Should delete connection issue
    assert any("connection_" in str(call) for call in mock_delete.call_args_list)


async def test_check_and_create_issues_disk_smart_errors(
    hass: HomeAssistant,
) -> None:
    """Test issue creation for disk SMART errors."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.data = UnraidData(
        disks=[
            DiskInfo(
                id="disk1",
                name="disk1",
                smart_errors=5,
                smart_status="FAILING",
                temperature_celsius=35,
            )
        ],
        array=None,
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check SMART error issue was created
    assert any("smart_errors" in str(call) for call in mock_create.call_args_list)


async def test_check_and_create_issues_disk_high_temp(
    hass: HomeAssistant,
) -> None:
    """Test issue creation for high disk temperature."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True

    # Mock disk_settings with thresholds
    mock_disk_settings = MagicMock()
    mock_disk_settings.hdd_temp_warning_celsius = 45
    mock_disk_settings.hdd_temp_critical_celsius = 55

    coordinator.data = UnraidData(
        disks=[
            DiskInfo(
                id="disk1",
                name="disk1",
                device="sda",
                role="data",
                smart_errors=0,
                smart_status="OK",
                temperature_celsius=50,  # Above 45 warning threshold for HDD
            )
        ],
        disk_settings=mock_disk_settings,
        array=None,
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check high temp issue was created
    assert any("high_temp" in str(call) for call in mock_create.call_args_list)


async def test_check_and_create_issues_disk_critical_temp(
    hass: HomeAssistant,
) -> None:
    """Test issue creation for critical disk temperature."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True

    # Mock disk_settings with thresholds
    mock_disk_settings = MagicMock()
    mock_disk_settings.hdd_temp_warning_celsius = 45
    mock_disk_settings.hdd_temp_critical_celsius = 55

    coordinator.data = UnraidData(
        disks=[
            DiskInfo(
                id="disk1",
                name="disk1",
                device="sda",
                role="data",
                smart_errors=0,
                temperature_celsius=60,  # Above 55 critical threshold for HDD
            )
        ],
        disk_settings=mock_disk_settings,
        array=None,
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check critical temp issue was created
    assert any("critical_temp" in str(call) for call in mock_create.call_args_list)


async def test_check_and_create_issues_parity_invalid(
    hass: HomeAssistant,
) -> None:
    """Test issue creation for invalid parity."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.data = UnraidData(
        disks=[],
        array=ArrayStatus(parity_valid=False, state="Started"),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check parity invalid issue was created
    assert any("parity_invalid" in str(call) for call in mock_create.call_args_list)


async def test_check_and_create_issues_parity_check_stuck(
    hass: HomeAssistant,
) -> None:
    """Test issue creation for stuck parity check."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.data = UnraidData(
        disks=[],
        array=ArrayStatus(
            parity_valid=True,
            parity_check_status="running",
            parity_check_progress=97,
        ),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check stuck parity check issue was created
    assert any("stuck" in str(call) for call in mock_create.call_args_list)


async def test_check_and_create_issues_no_data(
    hass: HomeAssistant,
) -> None:
    """Test no additional issues created when coordinator has no data."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.data = None

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Should not create any disk or array issues
    assert not any("disk_" in str(call) for call in mock_create.call_args_list)
    assert not any("array_" in str(call) for call in mock_create.call_args_list)


async def test_check_and_create_issues_parity_invalid_no_state(
    hass: HomeAssistant,
) -> None:
    """Test parity invalid issue is created."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.data = UnraidData(
        disks=[],
        array=ArrayStatus(
            parity_valid=False,  # Invalid parity
            parity_check_status=None,
            parity_check_progress=None,
        ),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ),
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check parity invalid issue was created
    assert any("parity_invalid" in str(call) for call in mock_create.call_args_list)


async def test_check_and_create_issues_parity_valid(
    hass: HomeAssistant,
) -> None:
    """Test parity valid removes existing issue."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.data = UnraidData(
        disks=[],
        array=ArrayStatus(
            parity_valid=True,  # Valid parity
            parity_check_status=None,
            parity_check_progress=None,
        ),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ),
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ) as mock_delete,
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check parity invalid issue was deleted
    assert any("parity_invalid" in str(call) for call in mock_delete.call_args_list)


async def test_check_and_create_issues_temp_warning(
    hass: HomeAssistant,
) -> None:
    """Test temperature warning issue is created when disk is above warning threshold."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.last_exception = None

    # Disk with high temperature (warning level: 45+)
    disk = DiskInfo(
        device="sda",
        role="data",
        name="disk1",
        id="WDC_WD80EFAX",
        temperature_celsius=50,  # Above 45 warning threshold, below 55 critical
    )

    # Mock disk_settings with thresholds
    mock_disk_settings = MagicMock()
    mock_disk_settings.hdd_temp_warning_celsius = 45
    mock_disk_settings.hdd_temp_critical_celsius = 55

    coordinator.data = UnraidData(
        disks=[disk],
        disk_settings=mock_disk_settings,
        array=ArrayStatus(parity_valid=True),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ) as mock_delete,
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check temperature warning issue was created
    create_calls = [str(call) for call in mock_create.call_args_list]
    assert any("high_temp" in str(call) for call in create_calls)


async def test_check_and_create_issues_temp_critical(
    hass: HomeAssistant,
) -> None:
    """Test temperature critical issue is created when disk is above critical threshold."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.last_exception = None

    # Disk with critical temperature (55+ for HDD)
    disk = DiskInfo(
        device="sda",
        role="data",
        name="disk1",
        id="WDC_WD80EFAX",
        temperature_celsius=60,  # Above 55 critical threshold
    )

    # Mock disk_settings with thresholds
    mock_disk_settings = MagicMock()
    mock_disk_settings.hdd_temp_warning_celsius = 45
    mock_disk_settings.hdd_temp_critical_celsius = 55

    coordinator.data = UnraidData(
        disks=[disk],
        disk_settings=mock_disk_settings,
        array=ArrayStatus(parity_valid=True),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ) as mock_delete,
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check temperature critical issue was created
    create_calls = [str(call) for call in mock_create.call_args_list]
    assert any("critical_temp" in str(call) for call in create_calls)


async def test_check_and_create_issues_temp_normal_clears(
    hass: HomeAssistant,
) -> None:
    """Test normal temperature clears existing issues."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.last_exception = None

    # Disk with normal temperature (below 45 warning threshold for HDD)
    disk = DiskInfo(
        device="sda",
        role="data",
        name="disk1",
        id="WDC_WD80EFAX",
        temperature_celsius=35,  # Normal temperature
    )

    # Mock disk_settings with thresholds
    mock_disk_settings = MagicMock()
    mock_disk_settings.hdd_temp_warning_celsius = 45
    mock_disk_settings.hdd_temp_critical_celsius = 55

    coordinator.data = UnraidData(
        disks=[disk],
        disk_settings=mock_disk_settings,
        array=ArrayStatus(parity_valid=True),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ) as mock_delete,
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check temperature issues were deleted (for normal temps, both are deleted)
    delete_calls = [str(call) for call in mock_delete.call_args_list]
    # Should delete both warning and critical temp issues
    assert any("high_temp" in str(call) for call in delete_calls)
    assert any("critical_temp" in str(call) for call in delete_calls)


async def test_check_and_create_issues_no_temp_clears(
    hass: HomeAssistant,
) -> None:
    """Test missing temperature clears existing issues."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100", "port": 8043}
    coordinator.last_update_success = True
    coordinator.last_exception = None

    # Disk without temperature reading
    disk = DiskInfo(
        device="sda",
        role="data",
        name="disk1",
        id="WDC_WD80EFAX",
        temperature_celsius=None,
    )

    coordinator.data = UnraidData(
        disks=[disk],
        disk_settings=None,
        array=ArrayStatus(parity_valid=True),
    )

    with (
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_create_issue"
        ) as mock_create,
        patch(
            "custom_components.unraid_management_agent.repairs.ir.async_delete_issue"
        ) as mock_delete,
    ):
        await async_check_and_create_issues(hass, coordinator)

    # Check temperature issues were deleted (for missing temp, both are deleted)
    delete_calls = [str(call) for call in mock_delete.call_args_list]
    # Should delete both warning and critical temp issues when no temp reading
    assert any("high_temp" in str(call) for call in delete_calls)
    assert any("critical_temp" in str(call) for call in delete_calls)


def test_get_disk_temp_thresholds_per_disk_override() -> None:
    """Test _get_disk_temp_thresholds with per-disk override values."""
    from custom_components.unraid_management_agent.repairs import (
        _get_disk_temp_thresholds,
    )

    disk = DiskInfo(
        device="sda",
        role="data",
        name="disk1",
        id="WDC_WD80EFAX",
        temp_warning=55,
        temp_critical=65,
    )

    result = _get_disk_temp_thresholds(disk, None)
    assert result == (55, 65)


def test_get_disk_temp_thresholds_global_hdd_settings() -> None:
    """Test _get_disk_temp_thresholds with global HDD settings."""
    from custom_components.unraid_management_agent.repairs import (
        _get_disk_temp_thresholds,
    )

    disk = DiskInfo(
        device="sda",
        role="data",
        name="disk1",
        id="WDC_WD80EFAX",
    )

    mock_settings = MagicMock()
    mock_settings.hdd_temp_warning_celsius = 48
    mock_settings.hdd_temp_critical_celsius = 58

    result = _get_disk_temp_thresholds(disk, mock_settings)
    assert result == (48, 58)


def test_get_disk_temp_thresholds_global_ssd_settings() -> None:
    """Test _get_disk_temp_thresholds with global SSD settings."""
    from custom_components.unraid_management_agent.repairs import (
        _get_disk_temp_thresholds,
    )

    disk = DiskInfo(
        device="nvme0n1",
        role="cache",
        name="cache",
        id="Samsung_SSD_980",
    )

    mock_settings = MagicMock()
    mock_settings.ssd_temp_warning_celsius = 60
    mock_settings.ssd_temp_critical_celsius = 70

    result = _get_disk_temp_thresholds(disk, mock_settings)
    assert result == (60, 70)


def test_get_disk_temp_thresholds_no_thresholds_hdd() -> None:
    """Test _get_disk_temp_thresholds returns None when no thresholds available for HDD."""
    from custom_components.unraid_management_agent.repairs import (
        _get_disk_temp_thresholds,
    )

    disk = DiskInfo(
        device="sda",
        role="data",
        name="disk1",
        id="WDC_WD80EFAX",
    )

    result = _get_disk_temp_thresholds(disk, None)
    # No thresholds available - should return None
    assert result is None


def test_get_disk_temp_thresholds_no_thresholds_ssd() -> None:
    """Test _get_disk_temp_thresholds returns None when no thresholds available for SSD."""
    from custom_components.unraid_management_agent.repairs import (
        _get_disk_temp_thresholds,
    )

    disk = DiskInfo(
        device="nvme0n1",
        role="cache",
        name="cache",
        id="Samsung_SSD_980",
    )

    result = _get_disk_temp_thresholds(disk, None)
    # No thresholds available - should return None
    assert result is None
