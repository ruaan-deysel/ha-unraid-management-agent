"""Test the Unraid Management Agent sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.api import RateCalculator
from custom_components.unraid_management_agent.coordinator import UnraidData
from custom_components.unraid_management_agent.sensor import (
    ARRAY_SENSOR_DESCRIPTIONS,
    FLASH_SENSOR_DESCRIPTIONS,
    PLUGIN_SENSOR_DESCRIPTIONS,
    # Description tuples
    SYSTEM_SENSOR_DESCRIPTIONS,
    UPS_SENSOR_DESCRIPTIONS,
    # Dynamic sensor classes
    UnraidDiskHealthSensor,
    UnraidDiskTemperatureSensor,
    UnraidDiskUsageSensor,
    UnraidEnergySensorExtraStoredData,
    UnraidFanSensor,
    UnraidGPUEnergySensor,
    UnraidGPUPowerSensor,
    UnraidGPUTemperatureSensor,
    UnraidGPUUtilizationSensor,
    UnraidNetworkRXSensor,
    UnraidNetworkTXSensor,
    UnraidRateSensorExtraStoredData,
    # Entity description pattern classes
    UnraidSensorEntity,
    UnraidShareUsageSensor,
    UnraidUPSEnergySensor,
    UnraidZFSPoolHealthSensor,
    UnraidZFSPoolUsageSensor,
    # Value functions for testing
    _get_array_attrs,
    _get_array_usage,
    _get_cpu_attrs,
    _get_cpu_power,
    _get_cpu_temperature,
    _get_cpu_usage,
    _get_docker_vdisk_attrs,
    _get_docker_vdisk_usage,
    _get_dram_power,
    _get_flash_free_space,
    _get_flash_usage,
    _get_flash_usage_attrs,
    _get_last_parity_check,
    _get_last_parity_errors,
    _get_latest_version,
    _get_latest_version_attrs,
    _get_log_filesystem_attrs,
    _get_log_filesystem_usage,
    _get_motherboard_temperature,
    _get_next_parity_check,
    _get_next_parity_check_attrs,
    _get_notifications_attrs,
    _get_notifications_count,
    _get_parity_attrs,
    _get_parity_progress,
    _get_plugins_attrs,
    _get_plugins_count,
    _get_plugins_with_updates,
    _get_plugins_with_updates_attrs,
    _get_ram_attrs,
    _get_ram_usage,
    _get_ups_battery,
    _get_ups_battery_attrs,
    _get_ups_load,
    _get_ups_power,
    _get_ups_runtime,
    _get_uptime,
    _get_uptime_attrs,
    _get_zfs_arc_attrs,
    _get_zfs_arc_hit_ratio,
)

# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test sensor platform setup."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify sensor entities are created
    sensor_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if entity_id.startswith("sensor.unraid_")
    ]

    assert len(sensor_entities) > 0


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_multi_gpu_sensors_created(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test per-GPU sensors are created for all detected GPUs."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.unraid_test_gpu_intel_uhd_graphics_630_utilization",
        "sensor.unraid_test_gpu_intel_uhd_graphics_630_temperature",
        "sensor.unraid_test_gpu_intel_uhd_graphics_630_power",
        "sensor.unraid_test_gpu_intel_uhd_graphics_630_energy",
        "sensor.unraid_test_gpu_nvidia_geforce_rtx_3080_utilization",
        "sensor.unraid_test_gpu_nvidia_geforce_rtx_3080_temperature",
        "sensor.unraid_test_gpu_nvidia_geforce_rtx_3080_power",
        "sensor.unraid_test_gpu_nvidia_geforce_rtx_3080_energy",
    ):
        assert hass.states.get(entity_id) is not None


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_cpu_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test CPU usage sensor."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_test_cpu_usage")
    if state:
        assert state.state == "25.5"
        assert state.attributes.get("unit_of_measurement") == PERCENTAGE


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_ram_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test RAM usage sensor."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_test_ram_usage")
    if state:
        assert state.state == "45.2"
        assert state.attributes.get("unit_of_measurement") == PERCENTAGE


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_array_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test array usage sensor."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_test_array_usage")
    if state:
        # 8000000000000 / 16000000000000 * 100 = 50.0%
        assert state.state == "50.0"


# =============================================================================
# Value Function Tests - CPU
# =============================================================================


def test_get_cpu_usage_with_data():
    """Test _get_cpu_usage with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_usage_percent = 75.567

    result = _get_cpu_usage(mock_data)
    assert result == 75.6


def test_get_cpu_usage_none_data():
    """Test _get_cpu_usage with None data."""
    result = _get_cpu_usage(None)
    assert result is None


def test_get_cpu_usage_no_system():
    """Test _get_cpu_usage with no system data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = None

    result = _get_cpu_usage(mock_data)
    assert result is None


def test_get_cpu_usage_no_value():
    """Test _get_cpu_usage with no cpu_usage_percent."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_usage_percent = None

    result = _get_cpu_usage(mock_data)
    assert result is None


def test_get_cpu_attrs_with_data():
    """Test _get_cpu_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_model = "Intel i7-12700K"
    mock_data.system.cpu_cores = 12
    mock_data.system.cpu_threads = 20
    mock_data.system.cpu_mhz = 4900.0

    attrs = _get_cpu_attrs(mock_data)
    assert attrs["cpu_model"] == "Intel i7-12700K"
    assert attrs["cpu_cores"] == 12
    assert attrs["cpu_threads"] == 20
    assert "cpu_frequency" in attrs


def test_get_cpu_attrs_fixes_core_count():
    """Test _get_cpu_attrs returns core count directly from data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_model = "Test CPU"
    mock_data.system.cpu_cores = 1
    mock_data.system.cpu_threads = 8
    mock_data.system.cpu_mhz = None

    attrs = _get_cpu_attrs(mock_data)
    # Source uses cpu_cores directly without correction
    assert attrs["cpu_cores"] == 1


def test_get_cpu_attrs_none_data():
    """Test _get_cpu_attrs with None data."""
    attrs = _get_cpu_attrs(None)
    assert attrs == {}


def test_get_cpu_attrs_no_system():
    """Test _get_cpu_attrs with no system data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = None

    attrs = _get_cpu_attrs(mock_data)
    assert attrs == {}


# =============================================================================
# Value Function Tests - RAM
# =============================================================================


def test_get_ram_usage_with_data():
    """Test _get_ram_usage with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.ram_usage_percent = 65.432

    result = _get_ram_usage(mock_data)
    assert result == 65.4


def test_get_ram_usage_none_data():
    """Test _get_ram_usage with None data."""
    result = _get_ram_usage(None)
    assert result is None


def test_get_ram_usage_no_value():
    """Test _get_ram_usage with no ram_usage_percent."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.ram_usage_percent = None

    result = _get_ram_usage(mock_data)
    assert result is None


def test_get_ram_attrs_with_data():
    """Test _get_ram_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.ram_total_bytes = 32000000000
    mock_data.system.ram_used_bytes = 21000000000
    mock_data.system.ram_free_bytes = 5000000000
    mock_data.system.ram_cached_bytes = 4000000000
    mock_data.system.ram_buffers_bytes = 2000000000
    mock_data.system.server_model = "Test Server"

    attrs = _get_ram_attrs(mock_data)
    assert "ram_total" in attrs
    assert "ram_used" in attrs
    assert "ram_free" in attrs
    assert "ram_cached" in attrs
    assert "ram_buffers" in attrs
    assert "ram_available" in attrs
    assert attrs["server_model"] == "Test Server"


def test_get_ram_attrs_none_data():
    """Test _get_ram_attrs with None data."""
    attrs = _get_ram_attrs(None)
    assert attrs == {}


def test_get_ram_attrs_minimal():
    """Test _get_ram_attrs with minimal data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.ram_total_bytes = 0
    mock_data.system.ram_used_bytes = 0
    mock_data.system.ram_free_bytes = 0
    mock_data.system.ram_cached_bytes = 0
    mock_data.system.ram_buffers_bytes = 0
    mock_data.system.server_model = None

    attrs = _get_ram_attrs(mock_data)
    # Only attributes with truthy values should be present
    assert "ram_total" not in attrs or attrs.get("ram_total") == "Unknown"


# =============================================================================
# Value Function Tests - Temperature
# =============================================================================


def test_get_cpu_temperature_with_data():
    """Test _get_cpu_temperature with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_temp_celsius = 65.5

    result = _get_cpu_temperature(mock_data)
    assert result == 65.5


def test_get_cpu_temperature_none_data():
    """Test _get_cpu_temperature with None data."""
    result = _get_cpu_temperature(None)
    assert result is None


def test_get_cpu_temperature_no_value():
    """Test _get_cpu_temperature with no temperature value."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_temp_celsius = None

    result = _get_cpu_temperature(mock_data)
    assert result is None


def test_get_motherboard_temperature_with_data():
    """Test _get_motherboard_temperature with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.motherboard_temp_celsius = 45.0

    result = _get_motherboard_temperature(mock_data)
    assert result == 45.0


def test_get_motherboard_temperature_none_data():
    """Test _get_motherboard_temperature with None data."""
    result = _get_motherboard_temperature(None)
    assert result is None


# =============================================================================
# Value Function Tests - CPU/DRAM Power
# =============================================================================


def test_get_cpu_power_with_data():
    """Test _get_cpu_power with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_power_watts = 3.43

    result = _get_cpu_power(mock_data)
    assert result == 3.4


def test_get_cpu_power_none_data():
    """Test _get_cpu_power with None data."""
    result = _get_cpu_power(None)
    assert result is None


def test_get_cpu_power_no_value():
    """Test _get_cpu_power with no power value."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.cpu_power_watts = None

    result = _get_cpu_power(mock_data)
    assert result is None


def test_get_dram_power_with_data():
    """Test _get_dram_power with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.dram_power_watts = 0.76

    result = _get_dram_power(mock_data)
    assert result == 0.8


def test_get_dram_power_none_data():
    """Test _get_dram_power with None data."""
    result = _get_dram_power(None)
    assert result is None


def test_get_dram_power_no_value():
    """Test _get_dram_power with no power value."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.dram_power_watts = None

    result = _get_dram_power(mock_data)
    assert result is None


# =============================================================================
# Value Function Tests - Uptime
# =============================================================================


def test_get_uptime_with_data():
    """Test _get_uptime with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.uptime_seconds = 86400  # 1 day

    result = _get_uptime(mock_data)
    assert result is not None
    assert isinstance(result, datetime)


def test_get_uptime_none_data():
    """Test _get_uptime with None data."""
    result = _get_uptime(None)
    assert result is None


def test_get_uptime_attrs_with_data():
    """Test _get_uptime_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.system = MagicMock()
    mock_data.system.hostname = "unraid-server"
    mock_data.system.version = "6.12.0"
    mock_data.system.uptime_seconds = 90061  # 1 day, 1 hour, 1 minute, 1 second
    mock_data.system.uptime_days = 1
    mock_data.system.uptime_hours = 1
    mock_data.system.uptime_minutes = 1

    attrs = _get_uptime_attrs(mock_data)
    assert attrs["hostname"] == "unraid-server"
    assert attrs["version"] == "6.12.0"
    assert attrs["uptime_days"] == 1
    assert attrs["uptime_hours"] == 1
    assert attrs["uptime_minutes"] == 1
    assert attrs["uptime_total_seconds"] == 90061


def test_get_uptime_attrs_none_data():
    """Test _get_uptime_attrs with None data."""
    attrs = _get_uptime_attrs(None)
    assert attrs == {}


# =============================================================================
# Value Function Tests - Array
# =============================================================================


def test_get_array_usage_with_percent():
    """Test _get_array_usage with used_percent."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.array = MagicMock()
    mock_data.array.used_percent = 50.5
    mock_data.array.computed_used_percent = 50.5

    result = _get_array_usage(mock_data)
    assert result == 50.5


def test_get_array_usage_with_bytes():
    """Test _get_array_usage calculating from bytes."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.array = MagicMock()
    mock_data.array.used_percent = None
    mock_data.array.computed_used_percent = 50.0
    mock_data.array.total_bytes = 16000000000000
    mock_data.array.used_bytes = 8000000000000

    result = _get_array_usage(mock_data)
    assert result == 50.0


def test_get_array_usage_zero_total():
    """Test _get_array_usage with zero total bytes."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.array = MagicMock()
    mock_data.array.used_percent = None
    mock_data.array.computed_used_percent = None
    mock_data.array.total_bytes = 0
    mock_data.array.used_bytes = 0

    result = _get_array_usage(mock_data)
    assert result is None


def test_get_array_usage_none_data():
    """Test _get_array_usage with None data."""
    result = _get_array_usage(None)
    assert result is None


def test_get_array_attrs_with_data():
    """Test _get_array_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.array = MagicMock()
    mock_data.array.state = "Started"
    mock_data.array.num_disks = 6
    mock_data.array.num_data_disks = 5
    mock_data.array.num_parity_disks = 1
    mock_data.array.total_bytes = 16000000000000
    mock_data.array.used_bytes = 8000000000000
    mock_data.array.free_bytes = 8000000000000

    attrs = _get_array_attrs(mock_data)
    assert attrs["array_state"] == "Started"
    assert attrs["num_disks"] == 6
    assert attrs["num_data_disks"] == 5
    assert attrs["num_parity_disks"] == 1
    assert "total_capacity" in attrs
    assert "used_space" in attrs
    assert "free_space" in attrs


def test_get_array_attrs_none_data():
    """Test _get_array_attrs with None data."""
    attrs = _get_array_attrs(None)
    assert attrs == {}


# =============================================================================
# Value Function Tests - Parity
# =============================================================================


def test_get_parity_progress_with_data():
    """Test _get_parity_progress with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.array = MagicMock()
    mock_data.array.sync_percent = 45.7

    result = _get_parity_progress(mock_data)
    assert result == 45.7


def test_get_parity_progress_none_data():
    """Test _get_parity_progress with None data."""
    result = _get_parity_progress(None)
    assert result is None


def test_get_parity_attrs_with_data():
    """Test _get_parity_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.array = MagicMock()
    mock_data.array.sync_action = "Checking"
    mock_data.array.sync_errors = 0
    mock_data.array.sync_speed = "100 MB/s"
    mock_data.array.sync_eta = "2 hours"

    attrs = _get_parity_attrs(mock_data)
    assert attrs["sync_action"] == "Checking"
    assert attrs["sync_errors"] == 0
    assert attrs["sync_speed"] == "100 MB/s"
    assert attrs["estimated_completion"] == "2 hours"


def test_get_parity_attrs_none_data():
    """Test _get_parity_attrs with None data."""
    attrs = _get_parity_attrs(None)
    assert attrs == {}


# =============================================================================
# Value Function Tests - UPS
# =============================================================================


def test_get_ups_battery_with_data():
    """Test _get_ups_battery with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.battery_charge_percent = 100.0

    result = _get_ups_battery(mock_data)
    assert result == 100.0


def test_get_ups_battery_none_data():
    """Test _get_ups_battery with None data."""
    result = _get_ups_battery(None)
    assert result is None


def test_get_ups_battery_attrs_with_data():
    """Test _get_ups_battery_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.status = "Online"
    mock_data.ups.model = "APC Smart-UPS 1500"

    attrs = _get_ups_battery_attrs(mock_data)
    assert attrs["ups_status"] == "Online"
    assert attrs["ups_model"] == "APC Smart-UPS 1500"


def test_get_ups_load_with_data():
    """Test _get_ups_load with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.load_percent = 35.0

    result = _get_ups_load(mock_data)
    assert result == 35.0


def test_get_ups_runtime_with_data():
    """Test _get_ups_runtime with valid data (returns minutes)."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.runtime_minutes = 30

    result = _get_ups_runtime(mock_data)
    assert result == 30


def test_get_ups_runtime_battery_runtime_seconds_fallback():
    """Test _get_ups_runtime only uses runtime_minutes."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.runtime_minutes = 60

    result = _get_ups_runtime(mock_data)
    assert result == 60


def test_get_ups_runtime_runtime_seconds_fallback():
    """Test _get_ups_runtime only uses runtime_minutes."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.runtime_minutes = 120

    result = _get_ups_runtime(mock_data)
    assert result == 120


def test_get_ups_runtime_runtime_minutes_fallback():
    """Test _get_ups_runtime with runtime_minutes."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.runtime_minutes = 45

    result = _get_ups_runtime(mock_data)
    assert result == 45


def test_get_ups_runtime_no_runtime_fields():
    """Test _get_ups_runtime when no runtime fields are present."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.runtime_minutes = None

    result = _get_ups_runtime(mock_data)
    assert result is None


def test_get_ups_power_with_data():
    """Test _get_ups_power with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.ups = MagicMock()
    mock_data.ups.power_watts = 450.0

    result = _get_ups_power(mock_data)
    assert result == 450.0


# =============================================================================
# Value Function Tests - Flash Drive
# =============================================================================


def test_get_flash_usage_with_data():
    """Test _get_flash_usage with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.flash_info = MagicMock()
    mock_data.flash_info.total_bytes = 1000000000
    mock_data.flash_info.used_bytes = 500000000
    mock_data.flash_info.computed_used_percent = 50.0

    result = _get_flash_usage(mock_data)
    assert result == 50.0


def test_get_flash_usage_none_data():
    """Test _get_flash_usage with None data."""
    result = _get_flash_usage(None)
    assert result is None


def test_get_flash_usage_attrs_with_data():
    """Test _get_flash_usage_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.flash_info = MagicMock()
    mock_data.flash_info.total_bytes = 1000000000
    mock_data.flash_info.used_bytes = 500000000
    mock_data.flash_info.free_bytes = 500000000
    mock_data.flash_info.guid = "TEST-GUID-1234"
    mock_data.flash_info.product = "SanDisk Cruiser"
    mock_data.flash_info.vendor = "SanDisk"

    attrs = _get_flash_usage_attrs(mock_data)
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs
    assert attrs["guid"] == "TEST-GUID-1234"
    assert attrs["product"] == "SanDisk Cruiser"
    assert attrs["vendor"] == "SanDisk"


def test_get_flash_free_space_with_data():
    """Test _get_flash_free_space with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.flash_info = MagicMock()
    mock_data.flash_info.free_bytes = 500000000

    result = _get_flash_free_space(mock_data)
    assert result == 500000000


# =============================================================================
# Value Function Tests - Plugins
# =============================================================================


def test_get_plugins_count_with_data():
    """Test _get_plugins_count with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.plugins = MagicMock()
    mock_data.plugins.plugins = [MagicMock(), MagicMock(), MagicMock()]
    mock_data.plugins.total_plugins = None  # Test fallback to len(plugins)

    result = _get_plugins_count(mock_data)
    assert result == 3


def test_get_plugins_count_none_data():
    """Test _get_plugins_count with None data."""
    result = _get_plugins_count(None)
    assert result is None


def test_get_plugins_attrs_with_data():
    """Test _get_plugins_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_plugin1 = MagicMock()
    mock_plugin1.name = "Plugin A"
    mock_plugin1.update_available = True
    mock_plugin2 = MagicMock()
    mock_plugin2.name = "Plugin B"
    mock_plugin2.update_available = False
    mock_data.plugins = MagicMock()
    mock_data.plugins.plugins = [mock_plugin1, mock_plugin2]
    mock_data.plugins.plugins_with_updates = None  # Test fallback to counting

    attrs = _get_plugins_attrs(mock_data)
    assert attrs["plugin_count"] == 2
    assert "Plugin A" in attrs["plugin_names"]
    assert "Plugin B" in attrs["plugin_names"]
    assert attrs["updates_available"] == 1


def test_get_latest_version_with_data():
    """Test _get_latest_version with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.update_status = MagicMock()
    mock_data.update_status.latest_version = "6.13.0"

    result = _get_latest_version(mock_data)
    assert result == "6.13.0"


def test_get_latest_version_attrs_with_data():
    """Test _get_latest_version_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.update_status = MagicMock()
    mock_data.update_status.current_version = "6.12.0"
    mock_data.update_status.latest_version = "6.13.0"

    attrs = _get_latest_version_attrs(mock_data)
    assert attrs["current_version"] == "6.12.0"
    assert attrs["latest_version"] == "6.13.0"
    assert attrs["update_available"] is True


def test_get_plugins_with_updates_with_data():
    """Test _get_plugins_with_updates with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.update_status = MagicMock()
    mock_data.update_status.plugins_with_updates = ["Plugin A", "Plugin B"]

    result = _get_plugins_with_updates(mock_data)
    assert result == 2


def test_get_plugins_with_updates_attrs_with_data():
    """Test _get_plugins_with_updates_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.update_status = MagicMock()
    mock_data.update_status.plugins_with_updates = ["Plugin A", "Plugin B"]

    attrs = _get_plugins_with_updates_attrs(mock_data)
    assert attrs["plugins_needing_update"] == ["Plugin A", "Plugin B"]


# =============================================================================
# Value Function Tests - Parity Schedule
# =============================================================================


def test_get_next_parity_check_with_datetime():
    """Test _get_next_parity_check with datetime value."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.parity_schedule = MagicMock()
    expected_time = datetime.now().astimezone() + timedelta(days=7)
    mock_data.parity_schedule.next_check_datetime = expected_time

    result = _get_next_parity_check(mock_data)
    assert result == expected_time


def test_get_next_parity_check_with_timestamp():
    """Test _get_next_parity_check with unix timestamp."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.parity_schedule = MagicMock()
    timestamp = datetime.now().timestamp() + 86400
    mock_data.parity_schedule.next_check_datetime = datetime.fromtimestamp(
        timestamp
    ).astimezone()

    result = _get_next_parity_check(mock_data)
    assert result is not None
    assert isinstance(result, datetime)


def test_get_next_parity_check_attrs_with_data():
    """Test _get_next_parity_check_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.parity_schedule = MagicMock()
    mock_data.parity_schedule.enabled = True
    mock_data.parity_schedule.mode = "monthly"
    mock_data.parity_schedule.frequency = 1
    mock_data.parity_schedule.day = 1
    mock_data.parity_schedule.month = None
    mock_data.parity_schedule.hour = 2
    mock_data.parity_schedule.correcting = True

    attrs = _get_next_parity_check_attrs(mock_data)
    assert attrs["enabled"] is True
    assert attrs["mode"] == "monthly"
    assert attrs["frequency"] == 1
    assert attrs["day"] == 1
    assert attrs["hour"] == 2
    assert attrs["correcting"] is True
    assert "month" not in attrs  # None values are excluded


def test_get_last_parity_check_with_data():
    """Test _get_last_parity_check with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_last = MagicMock()
    mock_last.date = "2024-01-08T03:00:00+00:00"
    mock_data.parity_history = MagicMock()
    mock_data.parity_history.records = [mock_last]
    mock_data.parity_history.most_recent = mock_last

    result = _get_last_parity_check(mock_data)
    assert result == datetime(2024, 1, 8, 3, 0, 0, tzinfo=UTC)


def test_get_last_parity_check_empty_history():
    """Test _get_last_parity_check with empty history."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.parity_history = MagicMock()
    mock_data.parity_history.records = []
    mock_data.parity_history.most_recent = None

    result = _get_last_parity_check(mock_data)
    assert result is None


def test_get_last_parity_errors_with_data():
    """Test _get_last_parity_errors with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_last = MagicMock()
    mock_last.errors = 5
    mock_data.parity_history = MagicMock()
    mock_data.parity_history.records = [mock_last]
    mock_data.parity_history.most_recent = mock_last

    result = _get_last_parity_errors(mock_data)
    assert result == 5


def test_get_last_parity_errors_no_errors():
    """Test _get_last_parity_errors with no errors."""
    mock_data = MagicMock(spec=UnraidData)
    mock_last = MagicMock()
    mock_last.errors = 0
    mock_data.parity_history = MagicMock()
    mock_data.parity_history.records = [mock_last]
    mock_data.parity_history.most_recent = mock_last

    result = _get_last_parity_errors(mock_data)
    assert result == 0


# =============================================================================
# Value Function Tests - Notifications
# =============================================================================


def test_get_notifications_count_with_unread_count():
    """Test _get_notifications_count with unread_count."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.notifications = MagicMock()
    mock_data.notifications.unread_count = 5

    result = _get_notifications_count(mock_data)
    assert result == 5


def test_get_notifications_count_with_list():
    """Test _get_notifications_count counting from list."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.notifications = MagicMock()
    mock_data.notifications.unread_count = 3

    result = _get_notifications_count(mock_data)
    assert result == 3


def test_get_notifications_count_from_notification_list() -> None:
    """Test _get_notifications_count with a bare notifications list."""
    data = UnraidData()
    data.notifications = [MagicMock(), MagicMock()]

    assert _get_notifications_count(data) == 2


def test_get_notifications_count_without_overview_uses_list_length() -> None:
    """Test _get_notifications_count falls back to list length without overview."""
    data = UnraidData()
    notifications = MagicMock()
    notifications.overview = None
    notifications.unread_count = 0
    notifications.notifications = [MagicMock(), MagicMock(), MagicMock()]
    data.notifications = notifications

    assert _get_notifications_count(data) == 3


def test_get_notifications_attrs_with_data():
    """Test _get_notifications_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.notifications = MagicMock()
    mock_data.notifications.total_count = 10
    mock_notif = MagicMock()
    mock_notif.subject = "Test Notification"
    mock_notif.importance = "normal"
    mock_data.notifications.notifications = [mock_notif]

    attrs = _get_notifications_attrs(mock_data)
    assert attrs["total_count"] == 10
    assert len(attrs["recent_notifications"]) == 1
    assert attrs["recent_notifications"][0]["subject"] == "Test Notification"


def test_get_notifications_attrs_with_list() -> None:
    """Test _get_notifications_attrs with a bare notifications list."""
    data = UnraidData()
    notification = MagicMock()
    notification.subject = "Disk warning"
    notification.importance = "warning"
    data.notifications = [notification]

    attrs = _get_notifications_attrs(data)

    assert attrs["total_count"] == 1
    assert attrs["recent_notifications"] == [
        {"subject": "Disk warning", "importance": "warning"}
    ]


def test_get_notifications_attrs_uses_overview_totals() -> None:
    """Test _get_notifications_attrs derives total count from overview totals."""
    from custom_components.unraid_management_agent.api.models import (
        NotificationCounts,
        NotificationOverview,
        NotificationsResponse,
    )

    data = UnraidData()
    data.notifications = NotificationsResponse(
        overview=NotificationOverview(
            unread=NotificationCounts(total=2),
            archive=NotificationCounts(total=3),
        ),
        notifications=[],
    )

    attrs = _get_notifications_attrs(data)

    assert attrs["unread_count"] == 2
    assert attrs["total_count"] == 5


# =============================================================================
# Value Function Tests - Docker vDisk and Log Filesystem
# =============================================================================


def test_get_docker_vdisk_usage_with_data():
    """Test _get_docker_vdisk_usage with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_vdisk = MagicMock()
    mock_vdisk.role = "docker_vdisk"
    mock_vdisk.used_bytes = 5000000000
    mock_vdisk.total_bytes = 10000000000
    mock_vdisk.computed_used_percent = 50.0
    mock_data.disks = [mock_vdisk]

    result = _get_docker_vdisk_usage(mock_data)
    assert result == 50.0


def test_get_docker_vdisk_usage_no_vdisk():
    """Test _get_docker_vdisk_usage when no vdisk present."""
    mock_data = MagicMock(spec=UnraidData)
    mock_disk = MagicMock()
    mock_disk.role = "data"
    mock_data.disks = [mock_disk]

    result = _get_docker_vdisk_usage(mock_data)
    assert result is None


def test_get_docker_vdisk_attrs_with_data():
    """Test _get_docker_vdisk_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_vdisk = MagicMock()
    mock_vdisk.role = "docker_vdisk"
    mock_vdisk.total_bytes = 10000000000
    mock_vdisk.used_bytes = 5000000000
    mock_vdisk.free_bytes = 5000000000
    mock_data.disks = [mock_vdisk]

    attrs = _get_docker_vdisk_attrs(mock_data)
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


def test_get_log_filesystem_usage_with_data():
    """Test _get_log_filesystem_usage with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_log = MagicMock()
    mock_log.role = "log"
    mock_log.used_bytes = 100000000
    mock_log.total_bytes = 1000000000
    mock_log.computed_used_percent = 10.0
    mock_data.disks = [mock_log]

    result = _get_log_filesystem_usage(mock_data)
    assert result == 10.0


def test_get_log_filesystem_attrs_with_data():
    """Test _get_log_filesystem_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_log = MagicMock()
    mock_log.role = "log"
    mock_log.total_bytes = 1000000000
    mock_log.used_bytes = 100000000
    mock_log.free_bytes = 900000000
    mock_data.disks = [mock_log]

    attrs = _get_log_filesystem_attrs(mock_data)
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


# =============================================================================
# Value Function Tests - ZFS
# =============================================================================


def test_get_zfs_arc_hit_ratio_with_data():
    """Test _get_zfs_arc_hit_ratio with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.zfs_arc = MagicMock()
    mock_data.zfs_arc.hit_ratio_percent = 92.5

    result = _get_zfs_arc_hit_ratio(mock_data)
    assert result == 92.5


def test_get_zfs_arc_hit_ratio_none_data():
    """Test _get_zfs_arc_hit_ratio with None data."""
    result = _get_zfs_arc_hit_ratio(None)
    assert result is None


def test_get_zfs_arc_attrs_with_data():
    """Test _get_zfs_arc_attrs with valid data."""
    mock_data = MagicMock(spec=UnraidData)
    mock_data.zfs_arc = MagicMock()
    mock_data.zfs_arc.size_bytes = 8000000000
    mock_data.zfs_arc.target_size_bytes = 16000000000
    mock_data.zfs_arc.hits = 1000000
    mock_data.zfs_arc.misses = 50000

    attrs = _get_zfs_arc_attrs(mock_data)
    assert "arc_size" in attrs
    assert "target_size" in attrs
    assert attrs["hits"] == 1000000
    assert attrs["misses"] == 50000


# =============================================================================
# Entity Description Tests
# =============================================================================


def test_entity_description_pattern():
    """Test that entity descriptions are properly defined."""
    # Verify system descriptions
    assert len(SYSTEM_SENSOR_DESCRIPTIONS) > 0
    cpu_desc = next(d for d in SYSTEM_SENSOR_DESCRIPTIONS if d.key == "cpu_usage")
    assert cpu_desc.native_unit_of_measurement == PERCENTAGE
    assert cpu_desc.value_fn is not None
    assert cpu_desc.extra_state_attributes_fn is not None

    # Verify array descriptions
    assert len(ARRAY_SENSOR_DESCRIPTIONS) > 0
    array_desc = next(d for d in ARRAY_SENSOR_DESCRIPTIONS if d.key == "array_usage")
    assert array_desc.native_unit_of_measurement == PERCENTAGE

    # Verify GPU descriptions
    # Verify UPS descriptions
    assert len(UPS_SENSOR_DESCRIPTIONS) > 0

    # Verify Flash descriptions
    assert len(FLASH_SENSOR_DESCRIPTIONS) > 0

    # Verify Plugin descriptions
    assert len(PLUGIN_SENSOR_DESCRIPTIONS) > 0


def test_sensor_entity_with_description():
    """Test UnraidSensorEntity with entity description."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 50.0

    cpu_desc = next(d for d in SYSTEM_SENSOR_DESCRIPTIONS if d.key == "cpu_usage")
    sensor = UnraidSensorEntity(mock_coordinator, cpu_desc)

    assert sensor.native_value == 50.0


def test_sensor_entity_available():
    """Test UnraidSensorEntity availability."""
    mock_coordinator = MagicMock()
    mock_coordinator.available = True
    mock_coordinator.data = MagicMock()

    cpu_desc = next(d for d in SYSTEM_SENSOR_DESCRIPTIONS if d.key == "cpu_usage")
    sensor = UnraidSensorEntity(mock_coordinator, cpu_desc)

    # Available depends on coordinator.available and data
    assert sensor.available is True


def test_sensor_entity_not_available_no_data():
    """Test UnraidSensorEntity unavailable when no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.available = True
    mock_coordinator.data = None

    cpu_desc = next(d for d in SYSTEM_SENSOR_DESCRIPTIONS if d.key == "cpu_usage")
    sensor = UnraidSensorEntity(mock_coordinator, cpu_desc)

    assert sensor.available is False


# =============================================================================
# Dynamic Sensor Class Tests - Fan
# =============================================================================


def test_fan_sensor_no_data() -> None:
    """Test fan sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "cpu", "cpu")

    assert sensor.native_value is None


def test_fan_sensor_with_data() -> None:
    """Test fan sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.fan_control = None
    mock_fan = MagicMock()
    mock_fan.name = "cpu"
    mock_fan.rpm = 1500
    mock_coordinator.data.system.fans = [mock_fan]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "cpu", "cpu")

    assert sensor.native_value == 1500


def test_fan_sensor_with_dict_data() -> None:
    """Test fan sensor with dict data format."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.fan_control = None
    mock_coordinator.data.system.fans = [{"name": "cpu", "rpm": 1200}]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "cpu", "cpu")

    assert sensor.native_value == 1200


def test_fan_sensor_name_not_found() -> None:
    """Test fan sensor when fan name is not in the list."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.fan_control = None
    mock_coordinator.data.system.fans = []
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "cpu", "cpu")

    assert sensor.native_value is None


def test_fan_sensor_with_fan_control_data() -> None:
    """Test fan sensor prefers fan_control data over system.fans."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()

    # fan_control has detailed device info
    mock_device = MagicMock()
    mock_device.name = "cpu"
    mock_device.rpm = 1800
    mock_device.pwm_percent = 75.5
    mock_device.mode = "auto"
    mock_device.controllable = True
    mock_device.id = "hwmon4_fan1"
    mock_coordinator.data.fan_control = MagicMock()
    mock_coordinator.data.fan_control.fans = [mock_device]
    mock_coordinator.data.fan_control.summary = MagicMock()
    mock_coordinator.data.fan_control.summary.failed_fans = []

    # system.fans has older data
    mock_fan = MagicMock()
    mock_fan.name = "cpu"
    mock_fan.rpm = 1500
    mock_coordinator.data.system.fans = [mock_fan]

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "cpu", "cpu")

    # Should prefer fan_control RPM
    assert sensor.native_value == 1800

    # Should include fan control attributes
    attrs = sensor.extra_state_attributes
    assert attrs["pwm_percent"] == 75.5
    assert attrs["mode"] == "auto"
    assert attrs["controllable"] is True
    assert attrs["fan_id"] == "hwmon4_fan1"
    assert "failed" not in attrs


def test_fan_sensor_with_failed_fan() -> None:
    """Test fan sensor reports failed status from summary."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()

    mock_device = MagicMock()
    mock_device.name = "rear"
    mock_device.rpm = 0
    mock_device.pwm_percent = 0.0
    mock_device.mode = "off"
    mock_device.controllable = True
    mock_device.id = "hwmon4_fan3"
    mock_coordinator.data.fan_control = MagicMock()
    mock_coordinator.data.fan_control.fans = [mock_device]
    mock_coordinator.data.fan_control.summary = MagicMock()
    mock_coordinator.data.fan_control.summary.failed_fans = ["hwmon4_fan3"]

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "rear", "rear")

    attrs = sensor.extra_state_attributes
    assert attrs["failed"] is True


def test_fan_sensor_fan_control_no_match() -> None:
    """Test fan sensor falls back to system.fans when fan_control has no match."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()

    # fan_control has a different fan (no name or index match)
    mock_device = MagicMock()
    mock_device.name = "other_fan"
    mock_device.hwmon_index = 99
    mock_coordinator.data.fan_control = MagicMock()
    mock_coordinator.data.fan_control.fans = [mock_device]
    mock_coordinator.data.fan_control.summary = None

    # system.fans has our fan
    mock_fan = MagicMock()
    mock_fan.name = "cpu"
    mock_fan.rpm = 1200
    mock_coordinator.data.system.fans = [mock_fan]

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "cpu", "cpu")

    assert sensor.native_value == 1200


def test_fan_sensor_hwmon_index_matching() -> None:
    """Test fan sensor matches by hwmon_index when system uses chip driver names."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()

    # fan_control uses hwmon-style naming
    mock_device = MagicMock()
    mock_device.name = "Fan 1"
    mock_device.hwmon_index = 1
    mock_device.rpm = 972
    mock_device.pwm_percent = 100.0
    mock_device.mode = "off"
    mock_device.controllable = True
    mock_device.id = "hwmon4_fan1"
    mock_coordinator.data.fan_control = MagicMock()
    mock_coordinator.data.fan_control.fans = [mock_device]
    mock_coordinator.data.fan_control.summary = MagicMock()
    mock_coordinator.data.fan_control.summary.failed_fans = []

    # system.fans uses chip driver naming
    mock_fan = MagicMock()
    mock_fan.name = "nct6793_fan1"
    mock_fan.rpm = 970
    mock_coordinator.data.system.fans = [mock_fan]

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(
        mock_coordinator, mock_entry, "nct6793_fan1", "nct6793_fan1"
    )

    # Should match by hwmon_index and prefer fan_control RPM
    assert sensor.native_value == 972

    # Should include fan control attributes
    attrs = sensor.extra_state_attributes
    assert attrs["pwm_percent"] == 100.0
    assert attrs["mode"] == "off"
    assert attrs["controllable"] is True
    assert attrs["fan_id"] == "hwmon4_fan1"


# =============================================================================
# Dynamic Sensor Class Tests - Network
# =============================================================================


def test_network_rx_sensor_no_data() -> None:
    """Test network RX sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.native_value == 0.0


def test_network_rx_sensor_interface_not_found() -> None:
    """Test network RX sensor when interface not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_interface = MagicMock()
    mock_interface.name = "eth1"  # Different interface
    mock_coordinator.data.network = [mock_interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")
    attrs = sensor.extra_state_attributes

    assert attrs == {}


def test_network_tx_sensor_no_data() -> None:
    """Test network TX sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkTXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.native_value == 0.0


def test_network_rx_sensor_unavailable_when_interface_missing() -> None:
    """Test network RX sensor availability when the interface is missing."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.network = []
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.available is False


def test_network_tx_sensor_available_when_interface_exists() -> None:
    """Test network TX sensor availability when the interface exists."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = MagicMock()
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.bytes_sent = 1000
    mock_coordinator.data.network = [mock_interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkTXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.available is True


def test_network_rx_sensor_extra_attrs() -> None:
    """Test network RX sensor extra attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.mac_address = "00:11:22:33:44:55"
    mock_interface.ip_address = "192.168.1.100"
    mock_interface.speed_mbps = 1000
    mock_coordinator.data.network = [mock_interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")
    attrs = sensor.extra_state_attributes

    # Use const.py attribute names: network_mac, network_ip, network_speed
    assert attrs["network_mac"] == "00:11:22:33:44:55"
    assert attrs["network_ip"] == "192.168.1.100"
    assert attrs["network_speed"] == 1000


def test_network_rx_sensor_handle_update_sets_rate() -> None:
    """Test network RX sensor update calculates rate."""
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.bytes_received = 2000

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.network = [mock_interface]

    sensor = object.__new__(UnraidNetworkRXSensor)
    sensor._interface_name = "eth0"
    sensor._rate_calculator = RateCalculator()
    sensor.coordinator = mock_coordinator
    sensor.async_write_ha_state = MagicMock()

    # Add an initial sample, then update interface bytes and call again
    sensor._rate_calculator.add_sample(1000, 0.0)
    mock_interface.bytes_received = 2000
    sensor._handle_coordinator_update()

    # Rate calculator has received samples
    assert sensor._rate_calculator.rate_kbps >= 0


def test_network_rx_sensor_handle_update_negative_bytes() -> None:
    """Test network RX sensor update handles counter reset."""
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.bytes_received = 1000

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.network = [mock_interface]

    sensor = object.__new__(UnraidNetworkRXSensor)
    sensor._interface_name = "eth0"
    sensor._rate_calculator = RateCalculator()
    sensor.coordinator = mock_coordinator
    sensor.async_write_ha_state = MagicMock()

    # Add initial sample with higher bytes (simulating counter that will reset)
    sensor._rate_calculator.add_sample(2000, 0.0)

    sensor._handle_coordinator_update()

    # Rate calculator handles this internally
    assert sensor._rate_calculator.rate_kbps >= 0


def test_network_rx_sensor_handle_update_initial_bytes() -> None:
    """Test network RX sensor update initializes bytes tracking."""
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.bytes_received = 500

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.network = [mock_interface]

    sensor = object.__new__(UnraidNetworkRXSensor)
    sensor._interface_name = "eth0"
    sensor._rate_calculator = RateCalculator()
    sensor.coordinator = mock_coordinator
    sensor.async_write_ha_state = MagicMock()

    sensor._handle_coordinator_update()

    # After first update, rate should be 0 (only one sample)
    assert sensor._rate_calculator.rate_kbps == 0.0


async def test_network_rx_sensor_restore_rate_state() -> None:
    """Test network RX sensor restores persisted rate calculator context."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")
    sensor.async_get_last_extra_data = AsyncMock(
        return_value=UnraidRateSensorExtraStoredData(
            12.5,
            sensor.native_unit_of_measurement,
            2048,
            100.0,
            500,
        )
    )

    await sensor._async_restore_rate_state()

    assert sensor.native_value == 12.5
    assert sensor._rate_calculator.last_bytes == 2048
    assert sensor._rate_calculator.last_timestamp == 100.0
    assert sensor._last_uptime_seconds == 500


def test_network_rx_sensor_handle_update_uses_restored_context() -> None:
    """Test network RX sensor continues rate calculation after a HA restart."""
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.bytes_received = 1600

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.network = [mock_interface]
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 1060

    sensor = object.__new__(UnraidNetworkRXSensor)
    sensor._interface_name = "eth0"
    sensor._rate_calculator = RateCalculator(stale_threshold_seconds=300.0)
    sensor._last_uptime_seconds = 1000
    sensor.coordinator = mock_coordinator
    sensor.async_write_ha_state = MagicMock()
    sensor._rate_calculator.restore_state(
        last_bytes=1000,
        last_timestamp=100.0,
        rate_kbps=12.0,
    )

    with patch(
        "custom_components.unraid_management_agent.sensor.dt_util.utcnow",
        return_value=MagicMock(timestamp=MagicMock(return_value=160.0)),
    ):
        sensor._handle_coordinator_update()

    assert sensor.native_value == pytest.approx(0.08, rel=0.01)
    assert sensor._last_uptime_seconds == 1060


def test_network_rx_sensor_handle_update_resets_on_reboot() -> None:
    """Test network RX sensor discards restored context after an Unraid reboot."""
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.bytes_received = 1600

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.network = [mock_interface]
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 10

    sensor = object.__new__(UnraidNetworkRXSensor)
    sensor._interface_name = "eth0"
    sensor._rate_calculator = RateCalculator(stale_threshold_seconds=300.0)
    sensor._last_uptime_seconds = 1000
    sensor.coordinator = mock_coordinator
    sensor.async_write_ha_state = MagicMock()
    sensor._rate_calculator.restore_state(
        last_bytes=1000,
        last_timestamp=100.0,
        rate_kbps=12.0,
    )

    with patch(
        "custom_components.unraid_management_agent.sensor.dt_util.utcnow",
        return_value=MagicMock(timestamp=MagicMock(return_value=160.0)),
    ):
        sensor._handle_coordinator_update()

    assert sensor.native_value == 0.0
    assert sensor._rate_calculator.last_bytes == 1600
    assert sensor._last_uptime_seconds == 10


# =============================================================================
# Dynamic Sensor Class Tests - Disk
# =============================================================================


def test_disk_usage_sensor_no_data() -> None:
    """Test disk usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value is None


def test_disk_usage_sensor_with_data() -> None:
    """Test disk usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.used_percent = 65.5
    mock_disk.computed_used_percent = 65.5
    mock_disk.role = "data"
    mock_disk.status = "active"
    mock_disk.total_bytes = 1000000000000
    mock_disk.used_bytes = 655000000000
    mock_disk.free_bytes = 345000000000
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value == 65.5


def test_disk_usage_sensor_disk_not_found() -> None:
    """Test disk usage sensor when disk not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk2"  # Different disk
    mock_disk.name = "Disk 2"
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value is None


def test_disk_health_sensor_no_data() -> None:
    """Test disk health sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value is None


def test_disk_health_sensor_with_data() -> None:
    """Test disk health sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.smart_status = "PASSED"
    mock_disk.device = "/dev/sda"
    mock_disk.model = "WD Red 4TB"
    mock_disk.serial_number = "ABC123"
    mock_disk.temperature_celsius = 35.0
    mock_disk.spin_state = "active"
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value == "PASSED"
    attrs = sensor.extra_state_attributes
    assert attrs["disk_name"] == "Disk 1"
    assert attrs["device"] == "/dev/sda"
    assert attrs["model"] == "WD Red 4TB"
    assert attrs["serial"] == "ABC123"
    assert attrs["temperature"] == "35.0 °C"
    assert attrs["spin_state"] == "active"
    assert "cached_value" not in attrs


def test_disk_health_sensor_standby_returns_cached() -> None:
    """Test disk health sensor returns last known value when disk is in standby."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    # First: disk is active with PASSED health
    mock_disk_active = MagicMock()
    mock_disk_active.id = "disk1"
    mock_disk_active.name = "Disk 1"
    mock_disk_active.smart_status = "PASSED"
    mock_disk_active.spin_state = "active"
    mock_disk_active.device = "/dev/sda"
    mock_disk_active.model = "WD Red 4TB"
    mock_disk_active.serial_number = "ABC123"
    mock_disk_active.temperature_celsius = 35.0
    mock_coordinator.data.disks = [mock_disk_active]

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")
    assert sensor.native_value == "PASSED"

    # Now: disk goes into standby, smart_status becomes None
    mock_disk_standby = MagicMock()
    mock_disk_standby.id = "disk1"
    mock_disk_standby.name = "Disk 1"
    mock_disk_standby.smart_status = None
    mock_disk_standby.status = None
    mock_disk_standby.spin_state = "standby"
    mock_disk_standby.device = "/dev/sda"
    mock_disk_standby.model = "WD Red 4TB"
    mock_disk_standby.serial_number = "ABC123"
    mock_disk_standby.temperature_celsius = None
    mock_coordinator.data.disks = [mock_disk_standby]

    # Should return cached "PASSED" instead of None
    assert sensor.native_value == "PASSED"
    attrs = sensor.extra_state_attributes
    assert attrs["spin_state"] == "standby"
    assert attrs["cached_value"] is True


def test_disk_health_sensor_standby_no_cache() -> None:
    """Test disk health sensor returns None in standby with no cached value."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    # Disk is in standby, no previous health data cached
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.smart_status = None
    mock_disk.status = None
    mock_disk.spin_state = "standby"
    mock_disk.device = "/dev/sda"
    mock_disk.model = None
    mock_disk.serial_number = None
    mock_disk.temperature_celsius = None
    mock_coordinator.data.disks = [mock_disk]

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")
    assert sensor.native_value is None


def test_disk_health_sensor_returns_cached_on_disk_not_found() -> None:
    """Test disk health sensor returns cached value when disk disappears from data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.smart_status = "PASSED"
    mock_disk.spin_state = "active"
    mock_coordinator.data.disks = [mock_disk]

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")
    assert sensor.native_value == "PASSED"

    # Disk disappears from data
    mock_coordinator.data.disks = []
    assert sensor.native_value == "PASSED"


# =============================================================================
# Dynamic Sensor Class Tests - Share
# =============================================================================


def test_share_usage_sensor_no_data() -> None:
    """Test share usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "media")

    assert sensor.native_value is None


def test_share_usage_sensor_with_data() -> None:
    """Test share usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "media"
    mock_share.used_percent = 75.0
    mock_share.computed_used_percent = 75.0
    mock_share.total_bytes = 10000000000000
    mock_share.used_bytes = 7500000000000
    mock_share.free_bytes = 2500000000000
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "media")

    assert sensor.native_value == 75.0


def test_share_usage_sensor_share_not_found() -> None:
    """Test share usage sensor when share not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "other"  # Different share
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "media")

    assert sensor.native_value is None


def test_share_usage_sensor_extra_attrs_with_cache() -> None:
    """Test share usage sensor extra attributes with cache settings."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "appdata"
    mock_share.used_percent = 30.0
    mock_share.total_bytes = 500000000000
    mock_share.used_bytes = 150000000000
    mock_share.free_bytes = 350000000000
    mock_share.use_cache = "prefer"
    mock_share.cache_pool = "cache"
    mock_share.mover_action = "cache_to_array"
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "appdata")
    attrs = sensor.extra_state_attributes

    assert attrs["share_name"] == "appdata"
    assert attrs["use_cache"] == "prefer"
    assert attrs["cache_pool"] == "cache"
    assert attrs["mover_action"] == "cache_to_array"


def test_share_usage_sensor_extra_attrs_no_cache() -> None:
    """Test share usage sensor extra attributes without cache settings."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "backups"
    mock_share.used_percent = 50.0
    mock_share.total_bytes = 1000000000000
    mock_share.used_bytes = 500000000000
    mock_share.free_bytes = 500000000000
    mock_share.use_cache = None
    mock_share.cache_pool = None
    mock_share.mover_action = None
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "backups")
    attrs = sensor.extra_state_attributes

    assert attrs["share_name"] == "backups"
    assert "use_cache" not in attrs
    assert "cache_pool" not in attrs
    assert "mover_action" not in attrs


def test_share_usage_sensor_extra_attrs_partial_cache() -> None:
    """Test share usage sensor extra attrs with partial cache config."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "downloads"
    mock_share.used_percent = 25.0
    mock_share.total_bytes = 2000000000000
    mock_share.used_bytes = 500000000000
    mock_share.free_bytes = 1500000000000
    mock_share.use_cache = "yes"
    mock_share.cache_pool = "cache"
    mock_share.mover_action = None  # No mover action
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "downloads")
    attrs = sensor.extra_state_attributes

    assert attrs["share_name"] == "downloads"
    assert attrs["use_cache"] == "yes"
    assert attrs["cache_pool"] == "cache"
    assert "mover_action" not in attrs


# =============================================================================
# Dynamic Sensor Class Tests - ZFS Pool
# =============================================================================


def test_zfs_pool_usage_sensor_no_data() -> None:
    """Test ZFS pool usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolUsageSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.native_value is None


def test_zfs_pool_usage_sensor_with_data() -> None:
    """Test ZFS pool usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_pool = MagicMock()
    mock_pool.name = "tank"
    mock_pool.used_percent = 45.0
    mock_pool.computed_used_percent = 45.0
    mock_pool.size_bytes = 8000000000000
    mock_pool.used_bytes = 3600000000000
    mock_pool.free_bytes = 4400000000000
    mock_coordinator.data.zfs_pools = [mock_pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolUsageSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.native_value == 45.0


def test_zfs_pool_usage_sensor_pool_not_found() -> None:
    """Test ZFS pool usage sensor when pool not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_pool = MagicMock()
    mock_pool.name = "other"  # Different pool
    mock_coordinator.data.zfs_pools = [mock_pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolUsageSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.native_value is None


def test_zfs_pool_health_sensor_no_data() -> None:
    """Test ZFS pool health sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolHealthSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.native_value is None


def test_zfs_pool_health_sensor_with_data() -> None:
    """Test ZFS pool health sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_pool = MagicMock()
    mock_pool.name = "tank"
    mock_pool.health = "ONLINE"
    mock_pool.errors = 0
    mock_coordinator.data.zfs_pools = [mock_pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolHealthSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.native_value == "ONLINE"
    attrs = sensor.extra_state_attributes
    assert attrs["pool_name"] == "tank"
    assert attrs["errors"] == 0


# =============================================================================
# Additional Helper Function Tests for Coverage (#21)
# =============================================================================


def test_get_last_parity_check_attrs_no_data() -> None:
    """Test _get_last_parity_check_attrs when no parity history."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check_attrs,
    )

    data = UnraidData()
    data.parity_history = None
    assert _get_last_parity_check_attrs(data) == {}


def test_get_last_parity_check_attrs_empty_records() -> None:
    """Test _get_last_parity_check_attrs with empty records."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check_attrs,
    )

    data = UnraidData()
    mock_history = MagicMock()
    mock_history.records = []
    mock_history.most_recent = None
    data.parity_history = mock_history
    assert _get_last_parity_check_attrs(data) == {}


def test_get_last_parity_check_attrs_with_records() -> None:
    """Test _get_last_parity_check_attrs with records."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check_attrs,
    )

    data = UnraidData()
    mock_record = MagicMock()
    mock_record.errors = 5
    mock_record.duration_seconds = 3600
    mock_record.status = "passed"
    mock_history = MagicMock()
    mock_history.records = [mock_record]
    mock_history.most_recent = mock_record
    data.parity_history = mock_history

    attrs = _get_last_parity_check_attrs(data)
    assert attrs["errors"] == 5
    assert "last_duration" in attrs
    assert attrs["result"] == "passed"


def test_get_last_parity_check_attrs_duration_via_duration() -> None:
    """Test _get_last_parity_check_attrs with no duration."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check_attrs,
    )

    data = UnraidData()
    mock_record = MagicMock()
    mock_record.errors = None
    mock_record.duration_seconds = None
    mock_record.status = "complete"
    mock_history = MagicMock()
    mock_history.records = [mock_record]
    mock_history.most_recent = mock_record
    data.parity_history = mock_history

    attrs = _get_last_parity_check_attrs(data)
    assert "last_duration" not in attrs
    assert attrs["result"] == "complete"


def test_get_notifications_attrs_with_recent_no_importance() -> None:
    """Test _get_notifications_attrs with notifications without importance."""
    data = UnraidData()
    mock_notif = MagicMock()
    mock_notif.subject = "Test Subject"
    mock_notif.importance = None
    mock_notifications = MagicMock()
    mock_notifications.total_count = 10
    mock_notifications.notifications = [mock_notif]
    data.notifications = mock_notifications

    attrs = _get_notifications_attrs(data)
    assert attrs["total_count"] == 10
    assert len(attrs["recent_notifications"]) == 1
    assert "importance" not in attrs["recent_notifications"][0]


def test_get_notifications_attrs_with_importance() -> None:
    """Test _get_notifications_attrs with notifications with importance."""
    data = UnraidData()
    mock_notif = MagicMock()
    mock_notif.subject = "Alert"
    mock_notif.importance = "warning"
    mock_notifications = MagicMock()
    mock_notifications.total_count = 5
    mock_notifications.notifications = [mock_notif]
    data.notifications = mock_notifications

    attrs = _get_notifications_attrs(data)
    assert attrs["total_count"] == 5
    assert attrs["recent_notifications"][0]["importance"] == "warning"


def test_get_notifications_attrs_empty_list() -> None:
    """Test _get_notifications_attrs with empty notification list."""
    data = UnraidData()
    mock_notifications = MagicMock()
    mock_notifications.total_count = 0
    mock_notifications.notifications = []
    data.notifications = mock_notifications

    attrs = _get_notifications_attrs(data)
    assert attrs["total_count"] == 0
    assert "recent_notifications" not in attrs


def test_get_docker_vdisk_usage_zero_total() -> None:
    """Test _get_docker_vdisk_usage with zero total and zero free (no data available)."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "docker_vdisk"
    mock_disk.used_bytes = 0
    mock_disk.total_bytes = 0
    mock_disk.free_bytes = 0  # When total, used, and free are all 0, result is None
    mock_disk.computed_used_percent = None
    data.disks = [mock_disk]

    assert _get_docker_vdisk_usage(data) is None


def test_get_docker_vdisk_usage_calculated() -> None:
    """Test _get_docker_vdisk_usage with valid data."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "docker_vdisk"
    mock_disk.used_bytes = 5000000000
    mock_disk.total_bytes = 10000000000
    mock_disk.free_bytes = 5000000000
    mock_disk.computed_used_percent = 50.0
    data.disks = [mock_disk]

    assert _get_docker_vdisk_usage(data) == 50.0


def test_get_docker_vdisk_usage_calculated_from_free() -> None:
    """Test _get_docker_vdisk_usage calculates total from used + free when total_bytes is None."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "docker_vdisk"
    mock_disk.used_bytes = 10000000000  # 10GB used
    mock_disk.total_bytes = None  # total_bytes not available
    mock_disk.free_bytes = 150000000000  # 150GB free
    mock_disk.computed_used_percent = 6.2
    data.disks = [mock_disk]

    # total = 10GB + 150GB = 160GB, usage = 10/160 * 100 = 6.25%
    assert _get_docker_vdisk_usage(data) == 6.2


def test_get_log_filesystem_usage_no_data() -> None:
    """Test _get_log_filesystem_usage with no data."""
    data = UnraidData()
    data.disks = None

    assert _get_log_filesystem_usage(data) is None


def test_get_log_filesystem_usage_no_log_disk() -> None:
    """Test _get_log_filesystem_usage when no log filesystem."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "data"
    data.disks = [mock_disk]

    assert _get_log_filesystem_usage(data) is None


def test_get_log_filesystem_usage_calculated() -> None:
    """Test _get_log_filesystem_usage with valid data."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "log"
    mock_disk.used_bytes = 3000000000
    mock_disk.total_bytes = 10000000000
    mock_disk.free_bytes = 7000000000
    mock_disk.computed_used_percent = 30.0
    data.disks = [mock_disk]

    assert _get_log_filesystem_usage(data) == 30.0


def test_get_log_filesystem_usage_calculated_from_free() -> None:
    """Test _get_log_filesystem_usage calculates total from used + free when total_bytes is None."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "log"
    mock_disk.used_bytes = 8000000  # ~8MB used
    mock_disk.total_bytes = None  # total_bytes not available
    mock_disk.free_bytes = 130000000  # ~130MB free
    mock_disk.computed_used_percent = 5.8
    data.disks = [mock_disk]

    # total = 8MB + 130MB = 138MB, usage = 8/138 * 100 = 5.8%
    assert _get_log_filesystem_usage(data) == 5.8


def test_get_log_filesystem_usage_zero_total() -> None:
    """Test _get_log_filesystem_usage with zero total and zero free (no data available)."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "log"
    mock_disk.used_bytes = 0
    mock_disk.total_bytes = 0
    mock_disk.free_bytes = 0  # When total, used, and free are all 0, result is None
    mock_disk.computed_used_percent = None
    data.disks = [mock_disk]

    assert _get_log_filesystem_usage(data) is None


def test_get_zfs_arc_hit_ratio_no_data() -> None:
    """Test _get_zfs_arc_hit_ratio with no ZFS ARC data."""
    data = UnraidData()
    data.zfs_arc = None

    assert _get_zfs_arc_hit_ratio(data) is None


def test_get_zfs_arc_attrs_no_data() -> None:
    """Test _get_zfs_arc_attrs with no ZFS ARC data."""
    data = UnraidData()
    data.zfs_arc = None

    assert _get_zfs_arc_attrs(data) == {}


def test_get_zfs_arc_attrs_with_full_data() -> None:
    """Test _get_zfs_arc_attrs with full ZFS ARC data."""
    data = UnraidData()
    mock_arc = MagicMock()
    mock_arc.size_bytes = 8000000000
    mock_arc.target_size_bytes = 16000000000
    mock_arc.hits = 1000000
    mock_arc.misses = 50000
    data.zfs_arc = mock_arc

    attrs = _get_zfs_arc_attrs(data)
    assert "arc_size" in attrs
    assert "target_size" in attrs
    assert attrs["hits"] == 1000000
    assert attrs["misses"] == 50000


def test_get_zfs_arc_attrs_partial_data() -> None:
    """Test _get_zfs_arc_attrs with partial data."""
    data = UnraidData()
    mock_arc = MagicMock()
    mock_arc.size_bytes = None
    mock_arc.target_size_bytes = None
    mock_arc.hits = 500
    mock_arc.misses = None
    data.zfs_arc = mock_arc

    attrs = _get_zfs_arc_attrs(data)
    assert "arc_size" not in attrs
    assert "target_size" not in attrs
    assert attrs["hits"] == 500
    assert "misses" not in attrs


# =============================================================================
# Network Sensor Tests (#22)
# =============================================================================


def test_network_rx_sensor_with_interface_data() -> None:
    """Test network RX sensor with interface data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.mac_address = "00:11:22:33:44:55"
    mock_interface.ipv4_address = "192.168.1.100"
    mock_interface.is_up = True
    mock_interface.rx_bytes = 1000000
    mock_coordinator.data.network_interfaces = [mock_interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")

    # Initial value should be 0
    assert sensor.native_value == 0.0


def test_network_tx_sensor_with_interface_data() -> None:
    """Test network TX sensor with interface data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    mock_interface.mac_address = "00:11:22:33:44:55"
    mock_interface.ipv4_address = "192.168.1.100"
    mock_interface.is_up = True
    mock_interface.tx_bytes = 2000000
    mock_coordinator.data.network_interfaces = [mock_interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkTXSensor(mock_coordinator, mock_entry, "eth0")

    # Initial value should be 0
    assert sensor.native_value == 0.0


# =============================================================================
# Share Sensor Extra Attributes Tests (#23)
# =============================================================================


def test_share_usage_sensor_extra_attributes() -> None:
    """Test share usage sensor extra state attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "media"
    mock_share.total_bytes = 10000000000000
    mock_share.used_bytes = 5000000000000
    mock_share.free_bytes = 5000000000000
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "media")

    attrs = sensor.extra_state_attributes
    assert attrs["share_name"] == "media"
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


def test_share_usage_sensor_extra_attributes_no_share() -> None:
    """Test share usage sensor extra attributes when share not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "other"
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "media")

    assert sensor.extra_state_attributes == {}


def test_share_usage_sensor_with_zero_values() -> None:
    """Test share usage sensor when some values are zero."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_share = MagicMock()
    mock_share.name = "media"
    mock_share.used_percent = None  # Must be None to fall through to calculation
    mock_share.computed_used_percent = None
    mock_share.total_bytes = 0
    mock_share.used_bytes = 0
    mock_share.free_bytes = 0
    mock_coordinator.data.shares = [mock_share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "media")

    # native_value should be None when total is 0
    assert sensor.native_value is None


# =============================================================================
# ZFS Pool Sensor Extra Attributes Tests (#24)
# =============================================================================


def test_zfs_pool_usage_sensor_extra_attributes() -> None:
    """Test ZFS pool usage sensor extra state attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_pool = MagicMock()
    mock_pool.name = "tank"
    mock_pool.used_percent = 45.0
    mock_pool.size_bytes = 8000000000000
    mock_pool.used_bytes = 3600000000000
    mock_pool.free_bytes = 4400000000000
    mock_coordinator.data.zfs_pools = [mock_pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolUsageSensor(mock_coordinator, mock_entry, "tank")

    attrs = sensor.extra_state_attributes
    assert attrs["pool_name"] == "tank"
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


def test_zfs_pool_usage_sensor_extra_attributes_no_pool() -> None:
    """Test ZFS pool usage sensor extra attributes when pool not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_pool = MagicMock()
    mock_pool.name = "other"
    mock_coordinator.data.zfs_pools = [mock_pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolUsageSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.extra_state_attributes == {}


def test_zfs_pool_health_sensor_extra_attributes_no_pool() -> None:
    """Test ZFS pool health sensor extra attributes when pool not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_pool = MagicMock()
    mock_pool.name = "other"
    mock_coordinator.data.zfs_pools = [mock_pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolHealthSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.extra_state_attributes == {}


# =============================================================================
# Disk Sensor Tests (#25)
# =============================================================================


def test_disk_usage_sensor_calculated_value() -> None:
    """Test disk usage sensor calculates percentage correctly."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.role = "data"
    mock_disk.status = "DISK_OK"
    mock_disk.used_bytes = 2000000000000
    mock_disk.total_bytes = 4000000000000
    mock_disk.free_bytes = 2000000000000
    mock_disk.used_percent = 50.0
    mock_disk.computed_used_percent = 50.0
    mock_disk.temperature = 35
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value == 50.0


def test_disk_usage_sensor_zero_total() -> None:
    """Test disk usage sensor when total bytes is zero."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.total_bytes = 0
    mock_disk.used_bytes = 0
    mock_disk.used_percent = None
    mock_disk.computed_used_percent = None
    mock_disk.role = "data"
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value is None


def test_disk_usage_sensor_extra_attributes() -> None:
    """Test disk usage sensor extra state attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "WDC Red 4TB"
    mock_disk.role = "data"
    mock_disk.status = "DISK_OK"
    mock_disk.size_bytes = 4000000000000
    mock_disk.used_bytes = 2000000000000
    mock_disk.free_bytes = 2000000000000
    mock_disk.temperature = 35
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "WDC Red 4TB")

    attrs = sensor.extra_state_attributes
    assert attrs["disk_name"] == "WDC Red 4TB"
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


def test_disk_health_sensor_extra_attributes() -> None:
    """Test disk health sensor extra state attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "WDC Red 4TB"
    mock_disk.role = "data"
    mock_disk.smart_status = "Passed"
    mock_disk.serial_number = "ABC123"
    mock_disk.model = "WDC Red"
    mock_disk.device = "sda"
    mock_disk.temperature_celsius = 35
    mock_disk.spin_state = "active"
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskHealthSensor(
        mock_coordinator, mock_entry, "disk1", "WDC Red 4TB"
    )

    assert sensor.native_value == "Passed"
    attrs = sensor.extra_state_attributes
    assert attrs["disk_name"] == "WDC Red 4TB"
    assert attrs["serial"] == "ABC123"
    assert attrs["model"] == "WDC Red"
    assert attrs["temperature"] == "35 °C"
    assert attrs["spin_state"] == "active"


def test_disk_health_sensor_disk_not_found() -> None:
    """Test disk health sensor when disk not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "other"
    mock_disk.name = "Other Disk"
    mock_disk.role = "data"
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


async def test_disk_health_sensor_restores_last_known_health() -> None:
    """Test disk health sensor restores cached SMART health after a HA restart."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.smart_status = None
    mock_disk.status = None
    mock_disk.is_standby = True
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "Disk 1")
    sensor.async_get_last_state = AsyncMock(return_value=MagicMock(state="PASSED"))

    await sensor._async_restore_last_known_health()

    assert sensor.native_value == "PASSED"


# =============================================================================
# Disk Temperature Sensor Tests
# =============================================================================


def test_disk_temperature_sensor_no_data() -> None:
    """Test disk temperature sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskTemperatureSensor(
        mock_coordinator, mock_entry, "disk1", "Disk 1"
    )

    assert sensor.native_value is None
    # Verify sensor is disabled by default
    assert sensor.entity_registry_enabled_default is False


def test_disk_temperature_sensor_with_data() -> None:
    """Test disk temperature sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.temperature_celsius = 35.0
    mock_disk.device = "/dev/sda"
    mock_disk.model = "WD Red 4TB"
    mock_disk.role = "data"
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskTemperatureSensor(
        mock_coordinator, mock_entry, "disk1", "Disk 1"
    )

    assert sensor.native_value == 35.0
    attrs = sensor.extra_state_attributes
    assert attrs["disk_name"] == "Disk 1"
    assert attrs["device"] == "/dev/sda"
    assert attrs["model"] == "WD Red 4TB"
    assert attrs["role"] == "data"


def test_disk_temperature_sensor_zero_temperature() -> None:
    """Test disk temperature sensor with zero temperature returns None."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.temperature_celsius = 0
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskTemperatureSensor(
        mock_coordinator, mock_entry, "disk1", "Disk 1"
    )

    # Zero or negative temperature should return None
    assert sensor.native_value is None


def test_disk_temperature_sensor_disk_not_found() -> None:
    """Test disk temperature sensor when disk not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_disk = MagicMock()
    mock_disk.id = "other"
    mock_disk.name = "Other Disk"
    mock_coordinator.data.disks = [mock_disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskTemperatureSensor(
        mock_coordinator, mock_entry, "disk1", "Disk 1"
    )

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_disk_temperature_sensor_unique_id() -> None:
    """Test disk temperature sensor unique_id."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskTemperatureSensor(
        mock_coordinator, mock_entry, "disk1", "Disk 1"
    )

    assert sensor.unique_id == "test_entry_disk_disk1_temperature"


# =============================================================================
# Fan Sensor Edge Cases (#26)
# =============================================================================


def test_fan_sensor_integer_list() -> None:
    """Test fan sensor with list of integers (not objects)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.fans = [1200, 1500, 900]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "Fan 1", "Fan 1")

    # Fan sensor looks up by name, integers don't have a name attribute
    # so no match is found and None is returned
    assert sensor.native_value is None


def test_fan_sensor_zero_rpm() -> None:
    """Test fan sensor with zero RPM."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_fan = MagicMock()
    mock_fan.name = "Fan 1"
    mock_fan.rpm = 0
    mock_coordinator.data.system.fans = [mock_fan]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "Fan 1", "Fan 1")

    assert sensor.native_value == 0


# =============================================================================
# Additional Edge Case Tests (#27)
# =============================================================================


def test_get_uptime_with_seconds() -> None:
    """Test _get_uptime with uptime_seconds."""
    data = UnraidData()
    mock_system = MagicMock()
    mock_system.uptime_seconds = 93600  # 1 day + 2 hours
    data.system = mock_system

    uptime = _get_uptime(data)
    assert uptime is not None


def test_get_ups_runtime_no_data() -> None:
    """Test _get_ups_runtime with no UPS data."""
    data = UnraidData()
    data.ups = None

    assert _get_ups_runtime(data) is None


def test_get_plugins_count_no_data() -> None:
    """Test _get_plugins_count with no data."""
    data = UnraidData()
    data.plugins = None

    assert _get_plugins_count(data) is None


def test_get_plugins_count_with_plugins_list() -> None:
    """Test _get_plugins_count with plugins list."""
    data = UnraidData()
    mock_plugins = MagicMock()
    mock_plugins.plugins = [MagicMock(), MagicMock()]
    mock_plugins.total_plugins = None
    data.plugins = mock_plugins

    assert _get_plugins_count(data) == 2


def test_get_plugins_count_with_total_plugins() -> None:
    """Test _get_plugins_count with total_plugins field."""
    data = UnraidData()
    mock_plugins = MagicMock()
    mock_plugins.plugins = None
    mock_plugins.total_plugins = 5
    data.plugins = mock_plugins

    assert _get_plugins_count(data) == 5


def test_get_latest_version_no_data() -> None:
    """Test _get_latest_version with no data."""
    data = UnraidData()
    data.update_status = None

    assert _get_latest_version(data) is None


def test_get_latest_version_fallback_to_current() -> None:
    """Test _get_latest_version falls back to current_version."""
    data = UnraidData()
    mock_update = MagicMock()
    mock_update.latest_version = None
    mock_update.current_version = "6.12.5"
    data.update_status = mock_update

    assert _get_latest_version(data) == "6.12.5"


def test_get_latest_version_fallback_to_system() -> None:
    """Test _get_latest_version falls back to system.version."""
    data = UnraidData()
    data.update_status = None
    mock_system = MagicMock()
    mock_system.version = "6.12.0"
    data.system = mock_system

    assert _get_latest_version(data) == "6.12.0"


def test_get_motherboard_temperature_no_data() -> None:
    """Test _get_motherboard_temperature with no data."""
    data = UnraidData()
    data.system = None

    assert _get_motherboard_temperature(data) is None


# =============================================================================
# Additional tests for uncovered branches
# =============================================================================


def test_get_parity_attrs_full() -> None:
    """Test _get_parity_attrs with all attributes."""
    from custom_components.unraid_management_agent.sensor import (
        _get_parity_attrs,
    )

    data = UnraidData()
    mock_array = MagicMock()
    mock_array.sync_action = "resync"
    mock_array.sync_errors = 0
    mock_array.sync_speed = "100 MB/s"
    mock_array.sync_eta = "1h 30m"
    data.array = mock_array

    attrs = _get_parity_attrs(data)
    assert attrs["sync_action"] == "resync"
    assert attrs["sync_errors"] == 0
    assert attrs["sync_speed"] == "100 MB/s"
    assert attrs["estimated_completion"] == "1h 30m"


def test_get_parity_attrs_no_data() -> None:
    """Test _get_parity_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_parity_attrs,
    )

    assert _get_parity_attrs(None) == {}


def test_get_parity_attrs_no_array() -> None:
    """Test _get_parity_attrs with no array data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_parity_attrs,
    )

    data = UnraidData()
    data.array = None
    assert _get_parity_attrs(data) == {}


def test_get_ups_battery_attrs_full() -> None:
    """Test _get_ups_battery_attrs with all attributes."""
    from custom_components.unraid_management_agent.sensor import _get_ups_battery_attrs

    data = UnraidData()
    mock_ups = MagicMock()
    mock_ups.status = "OL"
    mock_ups.model = "APC Smart-UPS 1500"
    data.ups = mock_ups

    attrs = _get_ups_battery_attrs(data)
    assert attrs["ups_status"] == "OL"
    assert attrs["ups_model"] == "APC Smart-UPS 1500"


def test_get_ups_battery_attrs_no_data() -> None:
    """Test _get_ups_battery_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import _get_ups_battery_attrs

    assert _get_ups_battery_attrs(None) == {}


def test_get_ups_load_no_data() -> None:
    """Test _get_ups_load with no data."""
    from custom_components.unraid_management_agent.sensor import _get_ups_load

    assert _get_ups_load(None) is None


def test_get_ups_power_no_data() -> None:
    """Test _get_ups_power with no data."""
    from custom_components.unraid_management_agent.sensor import _get_ups_power

    assert _get_ups_power(None) is None


def test_get_flash_usage_no_data() -> None:
    """Test _get_flash_usage with no data."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    assert _get_flash_usage(None) is None


def test_get_flash_usage_no_flash_info() -> None:
    """Test _get_flash_usage with no flash_info."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    data = UnraidData()
    data.flash_info = None

    assert _get_flash_usage(data) is None


def test_get_flash_usage_calculated() -> None:
    """Test _get_flash_usage calculated from bytes."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.total_bytes = 16000000000  # 16 GB
    mock_flash.used_bytes = 4000000000  # 4 GB (25%)
    mock_flash.computed_used_percent = 25.0
    data.flash_info = mock_flash

    result = _get_flash_usage(data)
    assert result == 25.0


def test_get_flash_usage_zero_total() -> None:
    """Test _get_flash_usage with zero total bytes."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.total_bytes = 0
    mock_flash.used_bytes = 0
    mock_flash.computed_used_percent = None
    data.flash_info = mock_flash

    assert _get_flash_usage(data) is None


def test_get_flash_usage_attrs_full() -> None:
    """Test _get_flash_usage_attrs with all attributes."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage_attrs

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.total_bytes = 16000000000
    mock_flash.used_bytes = 4000000000
    mock_flash.free_bytes = 12000000000
    mock_flash.guid = "1234-5678-ABCD"
    mock_flash.product = "USB Flash Drive"
    mock_flash.vendor = "SanDisk"
    data.flash_info = mock_flash

    attrs = _get_flash_usage_attrs(data)
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs
    assert attrs["guid"] == "1234-5678-ABCD"
    assert attrs["product"] == "USB Flash Drive"
    assert attrs["vendor"] == "SanDisk"


def test_get_flash_usage_attrs_no_data() -> None:
    """Test _get_flash_usage_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage_attrs

    assert _get_flash_usage_attrs(None) == {}


def test_get_flash_usage_with_usage_percent_string() -> None:
    """Test _get_flash_usage with usage_percent as string."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.usage_percent = "45.7"  # String value
    mock_flash.computed_used_percent = 45.7
    data.flash_info = mock_flash

    result = _get_flash_usage(data)
    assert result == 45.7


def test_get_flash_usage_with_usage_percent_number() -> None:
    """Test _get_flash_usage with usage_percent as number."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.usage_percent = 52.3  # Float value
    mock_flash.computed_used_percent = 52.3
    data.flash_info = mock_flash

    result = _get_flash_usage(data)
    assert result == 52.3


def test_get_flash_usage_with_usage_percent_invalid_string() -> None:
    """Test _get_flash_usage with invalid string usage_percent."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.usage_percent = "invalid"
    mock_flash.used_bytes = 500000000
    mock_flash.total_bytes = 1000000000
    mock_flash.computed_used_percent = 50.0
    data.flash_info = mock_flash

    result = _get_flash_usage(data)
    assert result == 50.0


def test_get_flash_usage_with_size_bytes_fallback() -> None:
    """Test _get_flash_usage using size_bytes fallback when total_bytes is 0."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.usage_percent = None
    mock_flash.used_bytes = 500000000
    mock_flash.total_bytes = 0  # Zero total
    mock_flash.size_bytes = 1000000000  # Fallback
    mock_flash.computed_used_percent = 50.0
    data.flash_info = mock_flash

    result = _get_flash_usage(data)
    assert result == 50.0


def test_get_flash_usage_attrs_with_size_bytes_fallback() -> None:
    """Test _get_flash_usage_attrs using size_bytes fallback."""
    from custom_components.unraid_management_agent.sensor import _get_flash_usage_attrs

    data = UnraidData()
    mock_flash = MagicMock()
    mock_flash.total_bytes = 0  # Zero
    mock_flash.size_bytes = 16000000000  # Fallback
    mock_flash.used_bytes = 4000000000
    mock_flash.free_bytes = 12000000000
    mock_flash.guid = None
    mock_flash.product = None
    mock_flash.vendor = None
    data.flash_info = mock_flash

    attrs = _get_flash_usage_attrs(data)
    assert "total_size" in attrs


def test_get_flash_free_space_no_data() -> None:
    """Test _get_flash_free_space with no data."""
    from custom_components.unraid_management_agent.sensor import _get_flash_free_space

    assert _get_flash_free_space(None) is None


def test_get_plugins_attrs_with_updates() -> None:
    """Test _get_plugins_attrs showing updates available."""
    from custom_components.unraid_management_agent.sensor import _get_plugins_attrs

    data = UnraidData()
    mock_plugins = MagicMock()

    mock_plugin1 = MagicMock()
    mock_plugin1.name = "Plugin A"
    mock_plugin1.update_available = True

    mock_plugin2 = MagicMock()
    mock_plugin2.name = "Plugin B"
    mock_plugin2.update_available = False

    mock_plugins.plugins = [mock_plugin1, mock_plugin2]
    mock_plugins.plugins_with_updates = None  # Force counting
    data.plugins = mock_plugins

    attrs = _get_plugins_attrs(data)
    assert attrs["plugin_count"] == 2
    assert "Plugin A" in attrs["plugin_names"]
    assert "Plugin B" in attrs["plugin_names"]
    assert attrs["updates_available"] == 1


def test_get_plugins_attrs_with_updates_field() -> None:
    """Test _get_plugins_attrs with explicit plugins_with_updates field."""
    from custom_components.unraid_management_agent.sensor import _get_plugins_attrs

    data = UnraidData()
    mock_plugins = MagicMock()
    mock_plugins.plugins = []
    mock_plugins.plugins_with_updates = 3
    data.plugins = mock_plugins

    attrs = _get_plugins_attrs(data)
    assert attrs["updates_available"] == 3


def test_get_plugins_attrs_no_data() -> None:
    """Test _get_plugins_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import _get_plugins_attrs

    assert _get_plugins_attrs(None) == {}


def test_get_plugins_attrs_no_updates() -> None:
    """Test _get_plugins_attrs when no updates are available."""
    from custom_components.unraid_management_agent.sensor import _get_plugins_attrs

    data = UnraidData()
    mock_plugin1 = MagicMock()
    mock_plugin1.name = "Plugin A"
    mock_plugin1.update_available = False
    mock_plugin2 = MagicMock()
    mock_plugin2.name = "Plugin B"
    mock_plugin2.update_available = False

    mock_plugins = MagicMock()
    mock_plugins.plugins = [mock_plugin1, mock_plugin2]
    mock_plugins.plugins_with_updates = None  # Force counting
    data.plugins = mock_plugins

    attrs = _get_plugins_attrs(data)
    assert "updates_available" not in attrs  # Should not be present when 0


def test_get_latest_version_attrs_full() -> None:
    """Test _get_latest_version_attrs with all attributes."""
    from custom_components.unraid_management_agent.sensor import (
        _get_latest_version_attrs,
    )

    data = UnraidData()
    mock_update = MagicMock()
    mock_update.current_version = "6.12.4"
    mock_update.latest_version = "6.13.0"
    data.update_status = mock_update

    attrs = _get_latest_version_attrs(data)
    assert attrs["current_version"] == "6.12.4"
    assert attrs["latest_version"] == "6.13.0"
    assert attrs["update_available"] is True


def test_get_latest_version_attrs_no_data() -> None:
    """Test _get_latest_version_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_latest_version_attrs,
    )

    assert _get_latest_version_attrs(None) == {}


def test_get_latest_version_attrs_system_fallback() -> None:
    """Test _get_latest_version_attrs falls back to system.version for current."""
    from custom_components.unraid_management_agent.sensor import (
        _get_latest_version_attrs,
    )

    data = UnraidData()
    data.update_status = None
    mock_system = MagicMock()
    mock_system.version = "6.12.0"
    data.system = mock_system

    attrs = _get_latest_version_attrs(data)
    assert attrs["current_version"] == "6.12.0"


def test_get_next_parity_check_datetime() -> None:
    """Test _get_next_parity_check with datetime value."""
    from datetime import datetime

    from custom_components.unraid_management_agent.sensor import (
        _get_next_parity_check,
    )

    data = UnraidData()
    mock_schedule = MagicMock()
    expected_time = datetime(2024, 1, 15, 3, 0, 0, tzinfo=UTC)
    mock_schedule.next_check_datetime = expected_time
    data.parity_schedule = mock_schedule

    result = _get_next_parity_check(data)
    assert result == expected_time


def test_get_next_parity_check_timestamp() -> None:
    """Test _get_next_parity_check with timestamp value."""
    from custom_components.unraid_management_agent.sensor import (
        _get_next_parity_check,
    )

    data = UnraidData()
    mock_schedule = MagicMock()
    mock_schedule.next_check_datetime = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
    data.parity_schedule = mock_schedule

    result = _get_next_parity_check(data)
    assert result is not None


def test_get_next_parity_check_no_data() -> None:
    """Test _get_next_parity_check with no data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_next_parity_check,
    )

    assert _get_next_parity_check(None) is None


def test_get_next_parity_check_attrs_full() -> None:
    """Test _get_next_parity_check_attrs with all attributes."""
    from custom_components.unraid_management_agent.sensor import (
        _get_next_parity_check_attrs,
    )

    data = UnraidData()
    mock_schedule = MagicMock()
    mock_schedule.enabled = True
    mock_schedule.mode = "yearly"
    mock_schedule.frequency = 1
    mock_schedule.day = 0
    mock_schedule.month = 6
    mock_schedule.hour = 3
    mock_schedule.correcting = True
    data.parity_schedule = mock_schedule

    attrs = _get_next_parity_check_attrs(data)
    assert attrs["enabled"] is True
    assert attrs["mode"] == "yearly"
    assert attrs["frequency"] == 1
    assert attrs["day"] == 0
    assert attrs["month"] == 6
    assert attrs["hour"] == 3
    assert attrs["correcting"] is True


def test_get_next_parity_check_attrs_no_data() -> None:
    """Test _get_next_parity_check_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_next_parity_check_attrs,
    )

    assert _get_next_parity_check_attrs(None) == {}


def test_get_last_parity_check_datetime() -> None:
    """Test _get_last_parity_check with datetime value."""
    from datetime import datetime

    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check,
    )

    data = UnraidData()
    mock_history = MagicMock()
    expected_time = datetime(2024, 1, 8, 3, 0, 0, tzinfo=UTC)
    mock_record = MagicMock()
    mock_record.date = "2024-01-08T03:00:00+00:00"
    mock_history.records = [mock_record]
    mock_history.most_recent = mock_record
    data.parity_history = mock_history

    result = _get_last_parity_check(data)
    assert result == expected_time


def test_get_last_parity_check_timestamp() -> None:
    """Test _get_last_parity_check with Unix timestamp."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check,
    )

    data = UnraidData()
    mock_history = MagicMock()
    mock_record = MagicMock()
    mock_record.date = "1704686400"  # Unix timestamp as string
    mock_history.records = [mock_record]
    mock_history.most_recent = mock_record
    data.parity_history = mock_history

    result = _get_last_parity_check(data)
    assert result is not None


def test_get_last_parity_check_date_field() -> None:
    """Test _get_last_parity_check using date field fallback."""
    from datetime import datetime

    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check,
    )

    data = UnraidData()
    mock_history = MagicMock()
    expected_time = datetime(2024, 1, 8, 3, 0, 0, tzinfo=UTC)
    mock_record = MagicMock()
    mock_record.date = "2024-01-08T03:00:00+00:00"
    mock_history.records = [mock_record]
    mock_history.most_recent = mock_record
    data.parity_history = mock_history

    result = _get_last_parity_check(data)
    assert result == expected_time


def test_get_last_parity_check_empty_records() -> None:
    """Test _get_last_parity_check with empty records."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check,
    )

    data = UnraidData()
    mock_history = MagicMock()
    mock_history.records = []
    mock_history.most_recent = None
    data.parity_history = mock_history

    assert _get_last_parity_check(data) is None


def test_get_last_parity_check_no_data() -> None:
    """Test _get_last_parity_check with no data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check,
    )

    assert _get_last_parity_check(None) is None


def test_get_last_parity_check_attrs_full() -> None:
    """Test _get_last_parity_check_attrs with all attributes."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check_attrs,
    )

    data = UnraidData()
    mock_history = MagicMock()
    mock_record = MagicMock()
    mock_record.errors = 0
    mock_record.duration_seconds = 3600
    mock_record.status = "completed"
    mock_history.records = [mock_record]
    mock_history.most_recent = mock_record
    data.parity_history = mock_history

    attrs = _get_last_parity_check_attrs(data)
    assert attrs["errors"] == 0
    assert "last_duration" in attrs
    assert attrs["result"] == "completed"


def test_get_last_parity_check_unsorted_records() -> None:
    """
    Test _get_last_parity_check correctly finds most recent from unsorted records.

    The UMA API may return parity records in arbitrary order (not sorted by date).
    This test verifies that the sensor correctly identifies the most recent record.
    """
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check,
        _get_last_parity_check_attrs,
    )

    data = UnraidData()
    mock_history = MagicMock()

    # Create records in non-chronological order (simulating UMA API behavior)
    old_record = MagicMock()
    old_record.date = "2024-11-30T00:30:26Z"  # Oldest
    old_record.errors = 100
    old_record.duration_seconds = 3600
    old_record.status = "errors"

    middle_record = MagicMock()
    middle_record.date = "2025-01-14T09:54:42Z"  # Middle
    middle_record.errors = 0
    middle_record.duration_seconds = 7200
    middle_record.status = "OK"

    newest_record = MagicMock()
    newest_record.date = "2026-01-13T15:16:43Z"  # Newest (but last in list)
    newest_record.errors = 0
    newest_record.duration_seconds = 27
    newest_record.status = "Canceled"

    # Records are in arbitrary order with oldest first
    mock_history.records = [old_record, middle_record, newest_record]
    mock_history.most_recent = newest_record
    data.parity_history = mock_history

    # Should return the newest record's timestamp, not records[0]
    result = _get_last_parity_check(data)
    assert result is not None
    assert result.year == 2026
    assert result.month == 1
    assert result.day == 13

    # Attributes should also come from the newest record
    attrs = _get_last_parity_check_attrs(data)
    assert attrs["errors"] == 0
    assert attrs["result"] == "Canceled"


def test_get_notifications_count_with_data() -> None:
    """Test _get_notifications_count with valid data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_notifications_count,
    )

    data = UnraidData()
    mock_notifications = MagicMock()
    mock_notifications.unread_count = 3
    mock_notifications.notifications = [MagicMock(), MagicMock(), MagicMock()]
    data.notifications = mock_notifications

    assert _get_notifications_count(data) == 3


def test_get_notifications_count_with_unread_field() -> None:
    """Test _get_notifications_count with unread_count field."""
    from custom_components.unraid_management_agent.sensor import (
        _get_notifications_count,
    )

    data = UnraidData()
    mock_notifications = MagicMock()
    mock_notifications.unread_count = 5
    data.notifications = mock_notifications

    assert _get_notifications_count(data) == 5


def test_get_notifications_count_no_data() -> None:
    """Test _get_notifications_count with no data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_notifications_count,
    )

    assert _get_notifications_count(None) is None


def test_get_notifications_attrs_no_data() -> None:
    """Test _get_notifications_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import (
        _get_notifications_attrs,
    )

    assert _get_notifications_attrs(None) == {}


def test_get_zfs_arc_attrs_full() -> None:
    """Test _get_zfs_arc_attrs with all attributes."""
    from custom_components.unraid_management_agent.sensor import _get_zfs_arc_attrs

    data = UnraidData()
    mock_arc = MagicMock()
    mock_arc.size_bytes = 8589934592
    mock_arc.target_size_bytes = 16106127360
    mock_arc.hits = 1000000
    mock_arc.misses = 50000
    data.zfs_arc = mock_arc

    attrs = _get_zfs_arc_attrs(data)
    assert "arc_size" in attrs
    assert "target_size" in attrs
    assert attrs["hits"] == 1000000
    assert attrs["misses"] == 50000


def test_get_plugins_with_updates_updates_is_none() -> None:
    """Test _get_plugins_with_updates when plugins_with_updates is None."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates,
    )

    data = UnraidData()
    mock_update_status = MagicMock()
    mock_update_status.plugins_with_updates = None
    data.update_status = mock_update_status

    result = _get_plugins_with_updates(data)
    assert result is None


def test_get_plugins_with_updates_updates_is_int() -> None:
    """Test _get_plugins_with_updates when plugins_with_updates is an int."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates,
    )

    data = UnraidData()
    mock_update_status = MagicMock()
    mock_update_status.plugins_with_updates = 5
    data.update_status = mock_update_status

    result = _get_plugins_with_updates(data)
    assert result == 5


def test_get_plugins_with_updates_from_plugins_data() -> None:
    """Test _get_plugins_with_updates from data.plugins fallback."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates,
    )

    data = UnraidData()
    data.update_status = None
    mock_plugins = MagicMock()
    mock_plugins.plugins_with_updates = ["plugin1", "plugin2"]
    data.plugins = mock_plugins

    result = _get_plugins_with_updates(data)
    assert result == 2


def test_get_plugins_with_updates_from_plugins_data_as_int() -> None:
    """Test _get_plugins_with_updates from data.plugins when it's an int."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates,
    )

    data = UnraidData()
    data.update_status = None
    mock_plugins = MagicMock()
    mock_plugins.plugins_with_updates = 3
    data.plugins = mock_plugins

    result = _get_plugins_with_updates(data)
    assert result == 3


def test_get_plugins_with_updates_empty_plugins_list() -> None:
    """Test _get_plugins_with_updates when plugins list is empty."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates,
    )

    data = UnraidData()
    data.update_status = None
    mock_plugins = MagicMock()
    mock_plugins.plugins_with_updates = None  # Not set
    mock_plugins.plugins = []  # Empty list
    data.plugins = mock_plugins

    result = _get_plugins_with_updates(data)
    assert result == 0


def test_get_plugins_with_updates_counting_updates() -> None:
    """Test _get_plugins_with_updates counting plugins with updates."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates,
    )

    data = UnraidData()
    data.update_status = None

    mock_plugin1 = MagicMock()
    mock_plugin1.update_available = True
    mock_plugin2 = MagicMock()
    mock_plugin2.update_available = False
    mock_plugin3 = MagicMock()
    mock_plugin3.update_available = True

    mock_plugins = MagicMock()
    mock_plugins.plugins_with_updates = None  # Not set, force counting
    mock_plugins.plugins = [mock_plugin1, mock_plugin2, mock_plugin3]
    data.plugins = mock_plugins

    result = _get_plugins_with_updates(data)
    assert result == 2  # Two plugins have updates


def test_get_plugins_with_updates_attrs_from_plugins_list() -> None:
    """Test _get_plugins_with_updates_attrs from plugins list fallback."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates_attrs,
    )

    data = UnraidData()
    data.update_status = None

    mock_plugin1 = MagicMock()
    mock_plugin1.name = "Plugin A"
    mock_plugin1.update_available = True
    mock_plugin2 = MagicMock()
    mock_plugin2.name = "Plugin B"
    mock_plugin2.update_available = False
    mock_plugin3 = MagicMock()
    mock_plugin3.name = "Plugin C"
    mock_plugin3.update_available = True

    mock_plugins = MagicMock()
    mock_plugins.plugins = [mock_plugin1, mock_plugin2, mock_plugin3]
    data.plugins = mock_plugins

    attrs = _get_plugins_with_updates_attrs(data)
    assert "plugins_needing_update" in attrs
    assert "Plugin A" in attrs["plugins_needing_update"]
    assert "Plugin C" in attrs["plugins_needing_update"]
    assert "Plugin B" not in attrs["plugins_needing_update"]


def test_get_plugins_with_updates_attrs_empty_list() -> None:
    """Test _get_plugins_with_updates_attrs when plugins list is empty."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates_attrs,
    )

    data = UnraidData()
    mock_update_status = MagicMock()
    mock_update_status.plugins_with_updates = []
    data.update_status = mock_update_status

    attrs = _get_plugins_with_updates_attrs(data)
    assert attrs == {}


def test_get_plugins_with_updates_attrs_not_a_list() -> None:
    """Test _get_plugins_with_updates_attrs when plugins is not a list."""
    from custom_components.unraid_management_agent.sensor import (
        _get_plugins_with_updates_attrs,
    )

    data = UnraidData()
    mock_update_status = MagicMock()
    mock_update_status.plugins_with_updates = 5  # int, not list
    data.update_status = mock_update_status

    attrs = _get_plugins_with_updates_attrs(data)
    assert attrs == {}


def test_get_docker_vdisk_attrs_no_vdisk() -> None:
    """Test _get_docker_vdisk_attrs when no docker_vdisk found."""
    from custom_components.unraid_management_agent.sensor import (
        _get_docker_vdisk_attrs,
    )

    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "data"
    data.disks = [mock_disk]

    attrs = _get_docker_vdisk_attrs(data)
    assert attrs == {}


def test_get_log_filesystem_attrs_no_log_fs() -> None:
    """Test _get_log_filesystem_attrs when no log filesystem found."""
    from custom_components.unraid_management_agent.sensor import (
        _get_log_filesystem_attrs,
    )

    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "data"
    data.disks = [mock_disk]

    attrs = _get_log_filesystem_attrs(data)
    assert attrs == {}


def test_get_motherboard_temperature_no_value() -> None:
    """Test _get_motherboard_temperature when motherboard_temp_celsius is None."""
    from custom_components.unraid_management_agent.sensor import (
        _get_motherboard_temperature,
    )

    data = UnraidData()
    mock_system = MagicMock()
    mock_system.motherboard_temp_celsius = None
    data.system = mock_system

    result = _get_motherboard_temperature(data)
    assert result is None


def test_get_uptime_no_value() -> None:
    """Test _get_uptime when uptime_seconds is None."""
    from custom_components.unraid_management_agent.sensor import _get_uptime

    data = UnraidData()
    mock_system = MagicMock()
    mock_system.uptime_seconds = None
    data.system = mock_system

    result = _get_uptime(data)
    assert result is None


def test_get_uptime_no_system() -> None:
    """Test _get_uptime with no system data."""
    from custom_components.unraid_management_agent.sensor import _get_uptime

    data = UnraidData()
    data.system = None

    result = _get_uptime(data)
    assert result is None


# =============================================================================
# UnraidSensorEntity Property Tests for Coverage
# =============================================================================


def test_unraid_sensor_entity_native_value_no_data() -> None:
    """Test UnraidSensorEntity native_value returns None when coordinator has no data."""
    from custom_components.unraid_management_agent.sensor import (
        SYSTEM_SENSOR_DESCRIPTIONS,
        UnraidSensorEntity,
    )

    # Create a minimal sensor entity
    entity = object.__new__(UnraidSensorEntity)
    entity.coordinator = MagicMock()
    entity.coordinator.data = None  # No data
    entity.entity_description = SYSTEM_SENSOR_DESCRIPTIONS[0]

    assert entity.native_value is None


def test_unraid_sensor_entity_available_no_data() -> None:
    """Test UnraidSensorEntity available returns False when coordinator has no data."""
    from custom_components.unraid_management_agent.sensor import (
        SYSTEM_SENSOR_DESCRIPTIONS,
        UnraidSensorEntity,
    )

    # Create a minimal sensor entity
    entity = object.__new__(UnraidSensorEntity)
    entity.coordinator = MagicMock()
    entity.coordinator.data = None  # No data
    entity.coordinator.last_update_success = True
    entity.entity_description = SYSTEM_SENSOR_DESCRIPTIONS[0]
    entity._attr_available = True

    # Mock super().available to return True
    with patch.object(
        UnraidSensorEntity,
        "available",
        new_callable=lambda: property(lambda self: self.coordinator.data is not None),
    ):
        # Direct call to test the actual implementation
        pass

    # Simpler approach - just test the property directly
    assert entity.available is False


def test_unraid_sensor_entity_extra_state_attributes_no_fn() -> None:
    """Test UnraidSensorEntity extra_state_attributes when no function defined."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidSensorEntity,
        UnraidSensorEntityDescription,
    )

    # Create a description without extra_state_attributes_fn
    description = UnraidSensorEntityDescription(
        key="test_sensor",
        value_fn=lambda _: None,
        available_fn=lambda _: True,
        extra_state_attributes_fn=None,  # No attributes function
    )

    entity = object.__new__(UnraidSensorEntity)
    entity.coordinator = MagicMock()
    entity.coordinator.data = MagicMock()
    entity.entity_description = description

    assert entity.extra_state_attributes is None


def test_unraid_sensor_entity_extra_state_attributes_no_data() -> None:
    """Test UnraidSensorEntity extra_state_attributes when coordinator has no data."""
    from custom_components.unraid_management_agent.sensor import (
        SYSTEM_SENSOR_DESCRIPTIONS,
        UnraidSensorEntity,
    )

    # Get a description that has an extra_state_attributes_fn
    description = None
    for desc in SYSTEM_SENSOR_DESCRIPTIONS:
        if desc.extra_state_attributes_fn:
            description = desc
            break

    # If none found, skip this test
    if description is None:
        return

    entity = object.__new__(UnraidSensorEntity)
    entity.coordinator = MagicMock()
    entity.coordinator.data = None  # No data
    entity.entity_description = description

    assert entity.extra_state_attributes is None


def test_get_last_parity_errors_no_records() -> None:
    """Test _get_last_parity_errors returns None when records list is empty."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_errors,
    )

    data = UnraidData()
    mock_history = MagicMock()
    mock_history.records = []  # Empty records
    mock_history.most_recent = None
    data.parity_history = mock_history

    result = _get_last_parity_errors(data)
    assert result is None


def test_get_last_parity_check_attrs_no_history() -> None:
    """Test _get_last_parity_check_attrs when no parity history."""
    from custom_components.unraid_management_agent.sensor import (
        _get_last_parity_check_attrs,
    )

    data = UnraidData()
    data.parity_history = None

    attrs = _get_last_parity_check_attrs(data)
    assert attrs == {}


# =============================================================================
# ZFS Pool Sensor Tests for Coverage
# =============================================================================


def test_zfs_pool_usage_sensor_fallback_calculation() -> None:
    """Test ZFS pool usage sensor uses fallback calculation when used_percent is None."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidZFSPoolUsageSensor,
    )

    sensor = object.__new__(UnraidZFSPoolUsageSensor)
    sensor._pool_name = "tank"
    sensor.coordinator = MagicMock()

    # Create pool with no used_percent but has size_bytes and used_bytes
    mock_pool = MagicMock()
    mock_pool.name = "tank"
    mock_pool.used_percent = None  # No direct percent
    mock_pool.computed_used_percent = 50.0
    mock_pool.size_bytes = 1000000000  # 1GB
    mock_pool.used_bytes = 500000000  # 500MB

    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.zfs_pools = [mock_pool]

    # Call native_value which should use fallback calculation
    result = sensor.native_value
    assert result == 50.0  # 500MB / 1GB = 50%


def test_zfs_pool_usage_sensor_no_pool_found() -> None:
    """Test ZFS pool usage sensor returns None when pool not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidZFSPoolUsageSensor,
    )

    sensor = object.__new__(UnraidZFSPoolUsageSensor)
    sensor._pool_name = "nonexistent"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.zfs_pools = []  # No pools

    result = sensor.native_value
    assert result is None


def test_zfs_pool_health_sensor_no_pool() -> None:
    """Test ZFS pool health sensor returns None when pool not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidZFSPoolHealthSensor,
    )

    sensor = object.__new__(UnraidZFSPoolHealthSensor)
    sensor._pool_name = "nonexistent"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.zfs_pools = []

    result = sensor.native_value
    assert result is None


def test_zfs_pool_usage_sensor_zero_size() -> None:
    """Test ZFS pool usage sensor returns None when total size is zero."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidZFSPoolUsageSensor,
    )

    sensor = object.__new__(UnraidZFSPoolUsageSensor)
    sensor._pool_name = "tank"
    sensor.coordinator = MagicMock()

    mock_pool = MagicMock()
    mock_pool.name = "tank"
    mock_pool.used_percent = None
    mock_pool.computed_used_percent = None
    mock_pool.size_bytes = 0  # Zero size
    mock_pool.used_bytes = 0

    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.zfs_pools = [mock_pool]

    result = sensor.native_value
    assert result is None


def test_zfs_pool_usage_sensor_extra_attrs_no_pool() -> None:
    """Test ZFS pool usage sensor extra attrs returns empty when pool not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidZFSPoolUsageSensor,
    )

    sensor = object.__new__(UnraidZFSPoolUsageSensor)
    sensor._pool_name = "nonexistent"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.zfs_pools = []

    attrs = sensor.extra_state_attributes
    assert attrs == {}


def test_zfs_pool_health_sensor_extra_attrs_no_pool() -> None:
    """Test ZFS pool health sensor extra attrs returns empty when pool not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidZFSPoolHealthSensor,
    )

    sensor = object.__new__(UnraidZFSPoolHealthSensor)
    sensor._pool_name = "nonexistent"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.zfs_pools = []

    attrs = sensor.extra_state_attributes
    assert attrs == {}


# =============================================================================
# Disk Usage Sensor Tests for Coverage
# =============================================================================


def test_disk_usage_sensor_fallback_calculation() -> None:
    """Test disk usage sensor uses fallback calculation when used_percent is None."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidDiskUsageSensor,
    )

    sensor = object.__new__(UnraidDiskUsageSensor)
    sensor._disk_id = "disk1"
    sensor._disk_name = "Disk 1"
    sensor.coordinator = MagicMock()

    mock_disk = MagicMock()
    mock_disk.id = "disk1"
    mock_disk.name = "Disk 1"
    mock_disk.used_percent = None  # No direct percent
    mock_disk.computed_used_percent = 25.0
    mock_disk.total_bytes = 1000000000  # 1GB
    mock_disk.used_bytes = 250000000  # 250MB

    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.disks = [mock_disk]

    result = sensor.native_value
    assert result == 25.0  # 250MB / 1GB = 25%


def test_disk_usage_sensor_no_disk_found() -> None:
    """Test disk usage sensor returns None when disk not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidDiskUsageSensor,
    )

    sensor = object.__new__(UnraidDiskUsageSensor)
    sensor._disk_id = "nonexistent"
    sensor._disk_name = "Unknown"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.disks = []

    result = sensor.native_value
    assert result is None


def test_disk_usage_sensor_extra_attrs_no_disk() -> None:
    """Test disk usage sensor extra attrs returns empty when disk not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidDiskUsageSensor,
    )

    sensor = object.__new__(UnraidDiskUsageSensor)
    sensor._disk_id = "nonexistent"
    sensor._disk_name = "Unknown"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.disks = []

    attrs = sensor.extra_state_attributes
    assert attrs == {}


def test_disk_health_sensor_no_disk() -> None:
    """Test disk health sensor returns None when disk not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidDiskHealthSensor,
    )

    sensor = object.__new__(UnraidDiskHealthSensor)
    sensor._disk_id = "nonexistent"
    sensor._disk_name = "Unknown"
    sensor._last_known_health = None
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.disks = []

    result = sensor.native_value
    assert result is None


def test_disk_health_sensor_extra_attrs_no_disk() -> None:
    """Test disk health sensor extra attrs returns empty when disk not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidDiskHealthSensor,
    )

    sensor = object.__new__(UnraidDiskHealthSensor)
    sensor._disk_id = "nonexistent"
    sensor._disk_name = "Unknown"
    sensor._last_known_health = None
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.disks = []

    attrs = sensor.extra_state_attributes
    assert attrs == {}


def test_share_usage_sensor_no_share() -> None:
    """Test share usage sensor returns None when share not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidShareUsageSensor,
    )

    sensor = object.__new__(UnraidShareUsageSensor)
    sensor._share_name = "nonexistent"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.shares = []

    result = sensor.native_value
    assert result is None


def test_share_usage_sensor_extra_attrs_no_share() -> None:
    """Test share usage sensor extra attrs returns empty when share not found."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidShareUsageSensor,
    )

    sensor = object.__new__(UnraidShareUsageSensor)
    sensor._share_name = "nonexistent"
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.shares = []

    attrs = sensor.extra_state_attributes
    assert attrs == {}


class SimpleShare:
    """Simple share class for testing."""

    def __init__(
        self,
        name: str,
        used_percent: float | None = None,
        total_bytes: int = 0,
        used_bytes: int = 0,
    ) -> None:
        """Initialize simple share."""
        self.name = name
        self.used_percent = used_percent
        self.total_bytes = total_bytes
        self.used_bytes = used_bytes


def test_share_usage_sensor_zero_total() -> None:
    """Test share usage sensor returns None when total is zero."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidShareUsageSensor,
    )

    sensor = object.__new__(UnraidShareUsageSensor)
    sensor._share_name = "media"
    sensor.coordinator = MagicMock()

    # Use simple class to ensure used_percent is actually None
    simple_share = SimpleShare(
        name="media", used_percent=None, total_bytes=0, used_bytes=0
    )

    data = SimpleData()
    data.shares = [simple_share]
    sensor.coordinator.data = data

    result = sensor.native_value
    assert result is None


def test_fan_sensor_no_fans() -> None:
    """Test fan sensor returns None when no fans data."""
    from custom_components.unraid_management_agent.sensor import UnraidFanSensor

    sensor = object.__new__(UnraidFanSensor)
    sensor._fan_name = "Fan 1"
    sensor._fan_index = 0
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.system = MagicMock()
    sensor.coordinator.data.system.fans = []

    result = sensor.native_value
    assert result is None


def test_network_rx_sensor_no_interface() -> None:
    """Test network RX sensor returns None when interface not found."""
    from custom_components.unraid_management_agent.sensor import UnraidNetworkRXSensor

    sensor = object.__new__(UnraidNetworkRXSensor)
    sensor._interface_name = "eth99"
    sensor._rate_calculator = RateCalculator()
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.network = []

    result = sensor.native_value
    assert result == 0.0


def test_network_tx_sensor_no_interface() -> None:
    """Test network TX sensor returns None when interface not found."""
    from custom_components.unraid_management_agent.sensor import UnraidNetworkTXSensor

    sensor = object.__new__(UnraidNetworkTXSensor)
    sensor._interface_name = "eth99"
    sensor._rate_calculator = RateCalculator()
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = MagicMock()
    sensor.coordinator.data.network = []

    result = sensor.native_value
    assert result == 0.0


# =============================================================================
# Additional Tests for _get methods (using simple objects instead of MagicMock)
# =============================================================================


class SimpleData:
    """Simple data class for testing."""

    def __init__(self) -> None:
        """Initialize simple data."""
        self.shares = None
        self.disks = None
        self.network = None
        self.zfs_pools = None
        self.system = None
        self.fan_control = None


def test_share_usage_sensor_get_share_no_shares() -> None:
    """Test share sensor _get_share returns None when shares is None."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidShareUsageSensor,
    )

    sensor = object.__new__(UnraidShareUsageSensor)
    sensor._share_name = "media"
    sensor.coordinator = MagicMock()

    # Use simple data with shares=None
    data = SimpleData()
    data.shares = None
    sensor.coordinator.data = data

    result = sensor._get_share()
    assert result is None


def test_disk_usage_sensor_get_disk_no_disks() -> None:
    """Test disk sensor _get_disk returns None when disks is None."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidDiskUsageSensor,
    )

    sensor = object.__new__(UnraidDiskUsageSensor)
    sensor._disk_id = "disk1"
    sensor._disk_name = "Disk 1"
    sensor.coordinator = MagicMock()

    data = SimpleData()
    data.disks = None
    sensor.coordinator.data = data

    result = sensor._get_disk()
    assert result is None


def test_zfs_pool_sensor_get_pool_no_pools() -> None:
    """Test ZFS pool sensor _get_pool returns None when zfs_pools is None."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidZFSPoolUsageSensor,
    )

    sensor = object.__new__(UnraidZFSPoolUsageSensor)
    sensor._pool_name = "tank"
    sensor.coordinator = MagicMock()

    data = SimpleData()
    data.zfs_pools = None
    sensor.coordinator.data = data

    result = sensor._get_pool()
    assert result is None


def test_fan_sensor_no_system() -> None:
    """Test fan sensor returns None when system is None."""
    from custom_components.unraid_management_agent.sensor import UnraidFanSensor

    sensor = object.__new__(UnraidFanSensor)
    sensor._fan_name = "Fan 1"
    sensor._normalized_name = "Fan 1"
    sensor._original_fan_name = "Fan 1"
    sensor.coordinator = MagicMock()

    data = SimpleData()
    data.system = None
    data.fan_control = None
    sensor.coordinator.data = data

    result = sensor.native_value
    assert result is None


def test_network_sensor_get_interface_no_network() -> None:
    """Test network sensor _get_interface returns None when network is None."""
    from custom_components.unraid_management_agent.sensor import UnraidNetworkRXSensor

    sensor = object.__new__(UnraidNetworkRXSensor)
    sensor._interface_name = "eth0"
    sensor._rate_calculator = RateCalculator()
    sensor.coordinator = MagicMock()

    data = SimpleData()
    data.network = None
    sensor.coordinator.data = data

    result = sensor._get_interface()
    assert result is None


# =============================================================================
# UPS Energy Sensor Tests
# =============================================================================


def test_ups_energy_sensor_initialization() -> None:
    """Test UPS energy sensor initialization."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    assert sensor._total_energy == 0.0
    assert sensor._last_power is None
    assert sensor._attr_translation_key == "ups_energy"


def test_ups_energy_sensor_native_value() -> None:
    """Test UPS energy sensor native_value property."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor._total_energy = 1.2345

    assert sensor.native_value == 1.234  # Rounded to 3 decimal places


def test_ups_energy_sensor_update_energy_no_data() -> None:
    """Test UPS energy sensor _update_energy with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor._update_energy()

    assert sensor._total_energy == 0.0


def test_ups_energy_sensor_update_energy_no_ups() -> None:
    """Test UPS energy sensor _update_energy with no UPS data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor._update_energy()

    assert sensor._total_energy == 0.0


def test_ups_energy_sensor_update_energy_first_reading() -> None:
    """Test UPS energy sensor _update_energy with first reading."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.power_watts = 100.0
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor._update_energy()

    # First reading should only set last_power, no energy increment
    assert sensor._total_energy == 0.0
    assert sensor._last_power == 100.0


def test_ups_energy_sensor_update_energy_subsequent_reading() -> None:
    """Test UPS energy sensor _update_energy with subsequent reading."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.power_watts = 100.0
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    # Simulate two readings 30 minutes apart using wall-clock timestamps
    with patch("custom_components.unraid_management_agent.sensor.dt_util") as mock_dt:
        mock_dt.utcnow.return_value.timestamp.return_value = 0.0
        sensor._update_energy()  # First reading at t=0
        mock_dt.utcnow.return_value.timestamp.return_value = 1800.0  # 30 minutes later
        sensor._update_energy()  # Second reading at t=1800

    # Energy integrator: 100W * 1800s = 50 Wh; native_value = total_energy + 50/1000
    assert sensor.native_value == pytest.approx(0.05, rel=0.01)


def test_ups_energy_sensor_update_energy_negative_power() -> None:
    """Test UPS energy sensor _update_energy with negative power (should be ignored)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.power_watts = -50.0
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor._last_power = 100.0
    sensor._total_energy = 1.0

    sensor._update_energy()

    # Energy should not change when power is negative
    assert sensor._total_energy == 1.0


def test_ups_energy_sensor_update_energy_long_gap() -> None:
    """Test UPS energy sensor _update_energy with long time gap (>1 hour)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.power_watts = 100.0
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    # Simulate two readings with a long gap (2 hours apart)
    with patch("custom_components.unraid_management_agent.sensor.dt_util") as mock_dt:
        mock_dt.utcnow.return_value.timestamp.return_value = 0.0
        sensor._update_energy()  # First reading at t=0
        mock_dt.utcnow.return_value.timestamp.return_value = 7200.0  # 2 hours later
        sensor._update_energy()  # Second reading at t=7200

    # Energy should not increment for gaps > 1 hour (stale threshold)
    assert sensor._energy_integrator.total_wh == 0.0


def test_ups_energy_sensor_available_true() -> None:
    """Test UPS energy sensor available property when available."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    assert sensor.available is True


def test_ups_energy_sensor_available_false_no_update_success() -> None:
    """Test UPS energy sensor available property when update failed."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = False
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    assert sensor.available is False


def test_ups_energy_sensor_available_false_no_data() -> None:
    """Test UPS energy sensor available property when no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    assert sensor.available is False


def test_ups_energy_sensor_available_false_no_ups() -> None:
    """Test UPS energy sensor available property when no UPS."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    assert sensor.available is False


def test_ups_energy_sensor_extra_state_attributes() -> None:
    """Test UPS energy sensor extra_state_attributes property."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor._last_power = 250.0

    attrs = sensor.extra_state_attributes

    assert attrs["current_power_watts"] == 250.0


def test_ups_energy_sensor_extra_state_attributes_empty() -> None:
    """Test UPS energy sensor extra_state_attributes when no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes

    assert "last_reset" not in attrs
    assert "current_power_watts" not in attrs


async def test_ups_energy_sensor_restore_energy_state() -> None:
    """Test UPS energy sensor restores its total and integration baseline."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor.async_get_last_state = AsyncMock(return_value=MagicMock(state="1.25"))
    sensor.async_get_last_extra_data = AsyncMock(
        return_value=UnraidEnergySensorExtraStoredData(
            1.25,
            sensor.native_unit_of_measurement,
            100.0,
            1000.0,
            500,
        )
    )

    await sensor._async_restore_energy_state()

    assert sensor.native_value == 1.25
    assert sensor._last_power == 100.0
    assert sensor._energy_integrator.last_power_watts == 100.0
    assert sensor._energy_integrator.last_timestamp == 1000.0
    assert sensor._last_uptime_seconds == 500


def test_ups_energy_sensor_update_energy_resets_on_reboot() -> None:
    """Test UPS energy sensor resets the integration baseline after reboot."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 5
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.power_watts = 100.0
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSEnergySensor(mock_coordinator, mock_entry)
    sensor._total_energy = 1.5
    sensor._last_power = 120.0
    sensor._last_uptime_seconds = 1000
    sensor._energy_integrator.restore_state(
        last_power_watts=120.0,
        last_timestamp=100.0,
    )

    with patch(
        "custom_components.unraid_management_agent.sensor.dt_util.utcnow",
        return_value=MagicMock(timestamp=MagicMock(return_value=160.0)),
    ):
        sensor._update_energy()

    assert sensor.native_value == 1.5
    assert sensor._energy_integrator.total_wh == 0.0
    assert sensor._last_power == 100.0
    assert sensor._last_uptime_seconds == 5


# =============================================================================
# Additional Coverage Tests
# =============================================================================


def test_get_latest_version_none_data() -> None:
    """Test _get_latest_version with None data."""
    assert _get_latest_version(None) is None


def test_get_plugins_with_updates_attrs_none_data() -> None:
    """Test _get_plugins_with_updates_attrs with None data."""
    assert _get_plugins_with_updates_attrs(None) == {}


def test_get_docker_vdisk_usage_total_bytes_zero() -> None:
    """Test _get_docker_vdisk_usage when total_bytes is 0 but used+free available."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "docker_vdisk"
    mock_disk.total_bytes = 0
    mock_disk.used_bytes = 4000000000
    mock_disk.free_bytes = 6000000000
    mock_disk.computed_used_percent = 40.0
    data.disks = [mock_disk]

    result = _get_docker_vdisk_usage(data)
    assert result is not None
    assert result == 40.0


def test_get_docker_vdisk_usage_no_vdisk_disk() -> None:
    """Test _get_docker_vdisk_usage returns None when no docker_vdisk disk."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "data"
    data.disks = [mock_disk]

    assert _get_docker_vdisk_usage(data) is None


def test_get_docker_vdisk_attrs_total_bytes_zero() -> None:
    """Test _get_docker_vdisk_attrs when total_bytes is 0 but used+free available."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "docker_vdisk"
    mock_disk.total_bytes = 0
    mock_disk.used_bytes = 4000000000
    mock_disk.free_bytes = 6000000000
    data.disks = [mock_disk]

    attrs = _get_docker_vdisk_attrs(data)
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


def test_get_log_filesystem_usage_total_bytes_zero() -> None:
    """Test _get_log_filesystem_usage when total_bytes is 0 but used+free available."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "log"
    mock_disk.total_bytes = 0
    mock_disk.used_bytes = 500000000
    mock_disk.free_bytes = 1500000000
    mock_disk.computed_used_percent = 25.0
    data.disks = [mock_disk]

    result = _get_log_filesystem_usage(data)
    assert result is not None
    assert result == 25.0


def test_get_log_filesystem_attrs_total_bytes_zero() -> None:
    """Test _get_log_filesystem_attrs when total_bytes is 0 but used+free available."""
    data = UnraidData()
    mock_disk = MagicMock()
    mock_disk.role = "log"
    mock_disk.total_bytes = 0
    mock_disk.used_bytes = 500000000
    mock_disk.free_bytes = 1500000000
    data.disks = [mock_disk]

    attrs = _get_log_filesystem_attrs(data)
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


def test_get_notifications_attrs_importance_conditional() -> None:
    """Test _get_notifications_attrs includes importance only when non-None."""
    data = UnraidData()
    mock_notif1 = MagicMock()
    mock_notif1.subject = "Alert"
    mock_notif1.importance = "alert"
    mock_notif2 = MagicMock()
    mock_notif2.subject = "Info"
    mock_notif2.importance = None
    mock_notifications = MagicMock()
    mock_notifications.total_count = 2
    mock_notifications.notifications = [mock_notif1, mock_notif2]
    data.notifications = mock_notifications

    attrs = _get_notifications_attrs(data)
    assert "recent_notifications" in attrs
    recent = attrs["recent_notifications"]
    assert len(recent) == 2
    assert recent[0] == {"subject": "Alert", "importance": "alert"}
    assert recent[1] == {"subject": "Info"}


# =============================================================================
# GPU Energy Sensor Tests
# =============================================================================


def test_gpu_energy_sensor_initialization() -> None:
    """Test GPU energy sensor initialization."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    assert sensor._total_energy == 0.0
    assert sensor._last_power is None
    assert sensor._attr_translation_placeholders == {"gpu_name": "GPU 0"}
    assert sensor._attr_translation_key == "gpu_energy"


def test_gpu_energy_sensor_native_value() -> None:
    """Test GPU energy sensor native_value property."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor._total_energy = 1.2345

    assert sensor.native_value == 1.234  # Rounded to 3 decimal places


def test_gpu_energy_sensor_update_energy_no_data() -> None:
    """Test GPU energy sensor _update_energy with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor._update_energy()

    assert sensor._total_energy == 0.0


def test_gpu_energy_sensor_update_energy_no_gpu() -> None:
    """Test GPU energy sensor _update_energy with no GPU data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.gpu = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor._update_energy()

    assert sensor._total_energy == 0.0


def test_gpu_energy_sensor_update_energy_empty_gpu_list() -> None:
    """Test GPU energy sensor _update_energy with empty GPU list."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.gpu = []
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor._update_energy()

    assert sensor._total_energy == 0.0


def test_gpu_energy_sensor_update_energy_first_reading() -> None:
    """Test GPU energy sensor _update_energy with first reading."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.index = 0
    mock_gpu.power_draw_watts = 220.5
    mock_coordinator.data.gpu = [mock_gpu]
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor._update_energy()

    # First reading should only set last_power, no energy increment
    assert sensor._total_energy == 0.0
    assert sensor._last_power == 220.5


def test_gpu_energy_sensor_update_energy_subsequent_reading() -> None:
    """Test GPU energy sensor _update_energy with subsequent reading."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.index = 0
    mock_gpu.power_draw_watts = 200.0
    mock_coordinator.data.gpu = [mock_gpu]
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    # Simulate two readings 30 minutes apart using wall-clock timestamps
    with patch("custom_components.unraid_management_agent.sensor.dt_util") as mock_dt:
        mock_dt.utcnow.return_value.timestamp.return_value = 0.0
        sensor._update_energy()  # First reading at t=0
        mock_dt.utcnow.return_value.timestamp.return_value = 1800.0  # 30 minutes later
        sensor._update_energy()  # Second reading at t=1800

    # Energy integrator: 200W * 1800s = 100 Wh; native_value = total_energy + 100/1000
    assert sensor.native_value == pytest.approx(0.1, rel=0.01)


def test_gpu_energy_sensor_update_energy_negative_power() -> None:
    """Test GPU energy sensor _update_energy with negative power (should be ignored)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.index = 0
    mock_gpu.power_draw_watts = -50.0
    mock_coordinator.data.gpu = [mock_gpu]
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor._last_power = 200.0
    sensor._total_energy = 1.0

    sensor._update_energy()

    # Energy should not change when power is negative
    assert sensor._total_energy == 1.0


def test_gpu_energy_sensor_update_energy_long_gap() -> None:
    """Test GPU energy sensor _update_energy with long time gap (>1 hour)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.index = 0
    mock_gpu.power_draw_watts = 200.0
    mock_coordinator.data.gpu = [mock_gpu]
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    # Simulate two readings with a long gap (2 hours apart)
    with patch("custom_components.unraid_management_agent.sensor.dt_util") as mock_dt:
        mock_dt.utcnow.return_value.timestamp.return_value = 0.0
        sensor._update_energy()  # First reading at t=0
        mock_dt.utcnow.return_value.timestamp.return_value = 7200.0  # 2 hours later
        sensor._update_energy()  # Second reading at t=7200

    # Energy should not increment for gaps > 1 hour (stale threshold)
    assert sensor._energy_integrator.total_wh == 0.0


def test_gpu_energy_sensor_available_true() -> None:
    """Test GPU energy sensor available property when available."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = MagicMock()
    gpu = MagicMock()
    gpu.index = 0
    mock_coordinator.data.gpu = [gpu]
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    assert sensor.available is True


def test_gpu_energy_sensor_available_false_no_update_success() -> None:
    """Test GPU energy sensor available property when update failed."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = False
    mock_coordinator.data = MagicMock()
    gpu = MagicMock()
    gpu.index = 0
    mock_coordinator.data.gpu = [gpu]
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    assert sensor.available is False


def test_gpu_energy_sensor_available_false_no_data() -> None:
    """Test GPU energy sensor available property when no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    assert sensor.available is False


def test_gpu_energy_sensor_available_false_no_gpu() -> None:
    """Test GPU energy sensor available property when no GPU."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.gpu = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    assert sensor.available is False


def test_gpu_energy_sensor_available_false_empty_gpu_list() -> None:
    """Test GPU energy sensor available property when GPU list is empty."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.gpu = []
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    assert sensor.available is False


def test_gpu_energy_sensor_extra_state_attributes() -> None:
    """Test GPU energy sensor extra_state_attributes property."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor._last_power = 220.5

    attrs = sensor.extra_state_attributes

    assert attrs["current_power_watts"] == 220.5


def test_gpu_energy_sensor_extra_state_attributes_empty() -> None:
    """Test GPU energy sensor extra_state_attributes when no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")

    attrs = sensor.extra_state_attributes

    assert "last_reset" not in attrs
    assert "current_power_watts" not in attrs


async def test_gpu_energy_sensor_restore_energy_state() -> None:
    """Test GPU energy sensor restores its total and integration baseline."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUEnergySensor(mock_coordinator, mock_entry, 0, "GPU 0")
    sensor.async_get_last_state = AsyncMock(return_value=MagicMock(state="2.5"))
    sensor.async_get_last_extra_data = AsyncMock(
        return_value=UnraidEnergySensorExtraStoredData(
            2.5,
            sensor.native_unit_of_measurement,
            220.0,
            2000.0,
            800,
        )
    )

    await sensor._async_restore_energy_state()

    assert sensor.native_value == 2.5
    assert sensor._last_power == 220.0
    assert sensor._energy_integrator.last_power_watts == 220.0
    assert sensor._energy_integrator.last_timestamp == 2000.0
    assert sensor._last_uptime_seconds == 800


def test_gpu_sensor_classes_find_and_read_values() -> None:
    """Test per-GPU sensor classes resolve values by GPU index."""
    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    gpu0 = MagicMock()
    gpu0.index = 0
    gpu0.name = "Intel UHD Graphics 630"
    gpu0.driver_version = "i915"
    gpu0.utilization_gpu_percent = 15
    gpu0.gpu_temperature = 50
    gpu0.power_draw_watts = 21.2

    gpu1 = MagicMock()
    gpu1.index = 1
    gpu1.name = "NVIDIA GeForce RTX 3080"
    gpu1.driver_version = "535.86.05"
    gpu1.utilization_gpu_percent = 45
    gpu1.gpu_temperature = 65
    gpu1.power_draw_watts = 220.5

    mock_coordinator.data = MagicMock()
    mock_coordinator.data.gpu = [gpu0, gpu1]

    utilization = UnraidGPUUtilizationSensor(mock_coordinator, mock_entry, 1, gpu1.name)
    temperature = UnraidGPUTemperatureSensor(mock_coordinator, mock_entry, 1, gpu1.name)
    power = UnraidGPUPowerSensor(mock_coordinator, mock_entry, 1, gpu1.name)

    assert utilization.native_value == 45
    assert temperature.native_value == 65
    assert power.native_value == 220.5


def test_gpu_sensor_classes_missing_index_return_none() -> None:
    """Test per-GPU sensor classes return None when index cannot be found."""
    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.gpu = []

    utilization = UnraidGPUUtilizationSensor(mock_coordinator, mock_entry, 42, "GPU 42")
    temperature = UnraidGPUTemperatureSensor(mock_coordinator, mock_entry, 42, "GPU 42")
    power = UnraidGPUPowerSensor(mock_coordinator, mock_entry, 42, "GPU 42")

    assert utilization.native_value is None
    assert temperature.native_value is None
    assert power.native_value is None
