"""Test the Unraid Management Agent sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.sensor import (
    UnraidArrayUsageSensor,
    UnraidCPUTemperatureSensor,
    UnraidCPUUsageSensor,
    UnraidDiskHealthSensor,
    UnraidDiskUsageSensor,
    UnraidDockerVDiskUsageSensor,
    UnraidFanSensor,
    UnraidGPUCPUTemperatureSensor,
    UnraidGPUPowerSensor,
    UnraidGPUUtilizationSensor,
    UnraidLogFilesystemUsageSensor,
    UnraidMotherboardTemperatureSensor,
    UnraidNetworkRXSensor,
    UnraidNetworkTXSensor,
    UnraidNotificationsSensor,
    UnraidParityProgressSensor,
    UnraidRAMUsageSensor,
    UnraidShareUsageSensor,
    UnraidUPSBatterySensor,
    UnraidUPSLoadSensor,
    UnraidUPSPowerSensor,
    UnraidUPSRuntimeSensor,
    UnraidUptimeSensor,
    UnraidZFSARCHitRatioSensor,
    UnraidZFSPoolHealthSensor,
    UnraidZFSPoolUsageSensor,
    _is_physical_network_interface,
)


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test sensor platform setup."""
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

    # Verify sensor entities are created
    sensor_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if entity_id.startswith("sensor.unraid_")
    ]

    assert len(sensor_entities) > 0


async def test_cpu_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test CPU usage sensor."""
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

    state = hass.states.get("sensor.unraid_test_cpu_usage")
    if state:
        assert state.state == "25.5"
        assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_ram_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test RAM usage sensor."""
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

    state = hass.states.get("sensor.unraid_test_ram_usage")
    if state:
        assert state.state == "45.2"
        assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_array_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test array usage sensor."""
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

    state = hass.states.get("sensor.unraid_test_array_usage")
    if state:
        # 8000000000000 / 16000000000000 * 100 = 50.0%
        assert state.state == "50.0"


def test_is_physical_network_interface():
    """Test network interface detection."""
    # Physical interfaces
    assert _is_physical_network_interface("eth0") is True
    assert _is_physical_network_interface("eth1") is True
    assert _is_physical_network_interface("wlan0") is True
    assert _is_physical_network_interface("bond0") is True
    assert _is_physical_network_interface("eno1") is True
    assert _is_physical_network_interface("enp2s0") is True

    # Virtual interfaces (should return False)
    assert _is_physical_network_interface("lo") is False
    assert _is_physical_network_interface("docker0") is False
    assert _is_physical_network_interface("br-123abc") is False
    assert _is_physical_network_interface("veth1234") is False
    assert _is_physical_network_interface("virbr0") is False


# Direct sensor class tests for edge cases and coverage


def test_cpu_usage_sensor_no_data() -> None:
    """Test CPU usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_cpu_usage_sensor_with_data() -> None:
    """Test CPU usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 75.567
    mock_coordinator.data.system.cpu_model = "Intel i7-12700K"
    mock_coordinator.data.system.cpu_cores = 12
    mock_coordinator.data.system.cpu_threads = 20
    mock_coordinator.data.system.cpu_mhz = 4900.0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 75.6  # Rounded to 1 decimal
    attrs = sensor.extra_state_attributes
    assert attrs["cpu_model"] == "Intel i7-12700K"
    assert attrs["cpu_cores"] == 12
    assert attrs["cpu_threads"] == 20
    assert "cpu_frequency" in attrs


def test_cpu_usage_sensor_fixes_core_count() -> None:
    """Test CPU usage sensor fixes incorrect core count."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 50.0
    mock_coordinator.data.system.cpu_model = "Test CPU"
    mock_coordinator.data.system.cpu_cores = 1  # Incorrect: 1 core with 8 threads
    mock_coordinator.data.system.cpu_threads = 8
    mock_coordinator.data.system.cpu_mhz = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    # Should be corrected to 4 cores (8 threads / 2)
    assert attrs["cpu_cores"] == 4


def test_ram_usage_sensor_no_data() -> None:
    """Test RAM usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_ram_usage_sensor_with_data() -> None:
    """Test RAM usage sensor with full data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.ram_usage_percent = 65.432
    mock_coordinator.data.system.ram_total_bytes = 32000000000
    mock_coordinator.data.system.ram_used_bytes = 21000000000
    mock_coordinator.data.system.ram_free_bytes = 5000000000
    mock_coordinator.data.system.ram_cached_bytes = 4000000000
    mock_coordinator.data.system.ram_buffers_bytes = 2000000000
    mock_coordinator.data.system.server_model = "Test Server"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 65.4
    attrs = sensor.extra_state_attributes
    assert "ram_total" in attrs
    assert "ram_used" in attrs
    assert "ram_free" in attrs
    assert "ram_cached" in attrs
    assert "ram_buffers" in attrs
    assert "ram_available" in attrs
    assert attrs["server_model"] == "Test Server"


def test_cpu_temperature_sensor_no_data() -> None:
    """Test CPU temperature sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_cpu_temperature_sensor_with_data() -> None:
    """Test CPU temperature sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_temp_celsius = 65.0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 65.0


def test_array_usage_sensor_no_data() -> None:
    """Test array usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_array_usage_sensor_with_data() -> None:
    """Test array usage sensor with full data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.total_bytes = 16000000000000
    mock_coordinator.data.array.used_bytes = 8000000000000
    mock_coordinator.data.array.free_bytes = 8000000000000
    mock_coordinator.data.array.used_percent = 50.0  # API returns used_percent directly
    mock_coordinator.data.array.state = "started"
    mock_coordinator.data.array.parity_status = "valid"
    mock_coordinator.data.array.num_disks = 4
    mock_coordinator.data.array.num_data_disks = 3
    mock_coordinator.data.array.num_parity_disks = 1
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 50.0  # 8TB / 16TB * 100
    attrs = sensor.extra_state_attributes
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs
    assert attrs["array_state"] == "started"
    assert attrs["num_disks"] == 4


def test_array_usage_sensor_zero_total() -> None:
    """Test array usage sensor with zero total (avoids division by zero)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.total_bytes = 0
    mock_coordinator.data.array.used_bytes = 0
    mock_coordinator.data.array.free_bytes = 0
    mock_coordinator.data.array.used_percent = None  # No used_percent when array empty
    mock_coordinator.data.array.state = "stopped"
    mock_coordinator.data.array.parity_status = None
    mock_coordinator.data.array.num_disks = 0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None  # Should handle division by zero gracefully


def test_uptime_sensor_no_data() -> None:
    """Test uptime sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_uptime_sensor_with_data() -> None:
    """Test uptime sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 86400  # 1 day
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    # Now returns formatted string instead of raw seconds
    assert sensor.native_value == "1 day"
    attrs = sensor.extra_state_attributes
    assert "uptime_seconds" in attrs
    assert attrs["uptime_seconds"] == 86400
    assert attrs["days"] == 1
    assert attrs["hours"] == 0


# GPU Sensor tests


def test_gpu_utilization_sensor_no_data() -> None:
    """Test GPU utilization sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUUtilizationSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_gpu_utilization_sensor_with_data() -> None:
    """Test GPU utilization sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    gpu = MagicMock()
    gpu.utilization_gpu_percent = 75.5
    gpu.name = "NVIDIA RTX 3080"
    gpu.driver_version = "535.86.05"
    mock_coordinator.data.gpu = [gpu]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUUtilizationSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 75.5
    attrs = sensor.extra_state_attributes
    assert attrs["gpu_name"] == "NVIDIA RTX 3080"
    assert attrs["gpu_driver_version"] == "535.86.05"


def test_gpu_utilization_sensor_empty_list() -> None:
    """Test GPU utilization sensor with empty list."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.gpu = []
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUUtilizationSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_gpu_temperature_sensor_no_data() -> None:
    """Test GPU temperature sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUCPUTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_gpu_temperature_sensor_with_data() -> None:
    """Test GPU temperature sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    gpu = MagicMock()
    gpu.temperature_celsius = 65.0
    mock_coordinator.data.gpu = [gpu]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUCPUTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 65.0


def test_gpu_power_sensor_no_data() -> None:
    """Test GPU power sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUPowerSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_gpu_power_sensor_with_data() -> None:
    """Test GPU power sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    gpu = MagicMock()
    gpu.power_draw_watts = 220.5
    mock_coordinator.data.gpu = [gpu]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUPowerSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 220.5


# UPS Sensor tests


def test_ups_battery_sensor_no_data() -> None:
    """Test UPS battery sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSBatterySensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_ups_battery_sensor_with_data() -> None:
    """Test UPS battery sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.battery_charge_percent = 95
    mock_coordinator.data.ups.status = "ONLINE"
    mock_coordinator.data.ups.model = "APC Back-UPS 1500"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSBatterySensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 95
    attrs = sensor.extra_state_attributes
    assert attrs["ups_status"] == "ONLINE"
    assert attrs["ups_model"] == "APC Back-UPS 1500"


def test_ups_load_sensor_no_data() -> None:
    """Test UPS load sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSLoadSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_ups_load_sensor_with_data() -> None:
    """Test UPS load sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.load_percent = 25
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSLoadSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 25


def test_ups_runtime_sensor_no_data() -> None:
    """Test UPS runtime sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSRuntimeSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_ups_runtime_sensor_with_runtime_left_seconds() -> None:
    """Test UPS runtime sensor with runtime_left_seconds."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.runtime_left_seconds = 3600  # 60 minutes
    mock_coordinator.data.ups.battery_runtime_seconds = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSRuntimeSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 60.0  # Minutes


def test_ups_runtime_sensor_with_battery_runtime_seconds() -> None:
    """Test UPS runtime sensor with battery_runtime_seconds fallback."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.runtime_left_seconds = None
    mock_coordinator.data.ups.battery_runtime_seconds = 1800  # 30 minutes
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSRuntimeSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 30.0


def test_ups_power_sensor_no_data() -> None:
    """Test UPS power sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSPowerSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_ups_power_sensor_with_data() -> None:
    """Test UPS power sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.ups = MagicMock()
    mock_coordinator.data.ups.power_watts = 150.5
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUPSPowerSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 150.5


# Network Sensor tests


def test_network_rx_sensor_no_data() -> None:
    """Test network RX sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_network_rx_sensor_with_data() -> None:
    """Test network RX sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    interface = MagicMock()
    interface.name = "eth0"
    interface.bytes_received = 1000000000
    interface.mac_address = "00:11:22:33:44:55"
    interface.ip_address = "192.168.1.100"
    interface.speed_mbps = 1000
    mock_coordinator.data.network = [interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.native_value == 1000000000
    attrs = sensor.extra_state_attributes
    assert attrs["network_mac"] == "00:11:22:33:44:55"
    assert attrs["network_ip"] == "192.168.1.100"
    assert attrs["network_speed"] == 1000


def test_network_rx_sensor_interface_not_found() -> None:
    """Test network RX sensor when interface not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    interface = MagicMock()
    interface.name = "eth1"
    mock_coordinator.data.network = [interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkRXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_network_tx_sensor_no_data() -> None:
    """Test network TX sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkTXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.native_value is None


def test_network_tx_sensor_with_data() -> None:
    """Test network TX sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    interface = MagicMock()
    interface.name = "eth0"
    interface.bytes_sent = 500000000
    mock_coordinator.data.network = [interface]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNetworkTXSensor(mock_coordinator, mock_entry, "eth0")

    assert sensor.native_value == 500000000


# Disk Sensor tests


def test_disk_usage_sensor_no_data() -> None:
    """Test disk usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "disk1")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_disk_usage_sensor_with_data() -> None:
    """Test disk usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    disk = MagicMock()
    disk.id = "disk1"
    disk.name = "disk1"
    disk.size_bytes = 8000000000000
    disk.used_bytes = 4000000000000
    disk.free_bytes = 4000000000000
    disk.device = "sdb"
    disk.filesystem = "xfs"
    mock_coordinator.data.disks = [disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "disk1")

    assert sensor.native_value == 50.0
    attrs = sensor.extra_state_attributes
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs
    assert attrs["device"] == "sdb"
    assert attrs["filesystem"] == "xfs"


def test_disk_usage_sensor_disk_not_found() -> None:
    """Test disk usage sensor when disk not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    disk = MagicMock()
    disk.id = "disk2"
    disk.name = "disk2"
    mock_coordinator.data.disks = [disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskUsageSensor(mock_coordinator, mock_entry, "disk1", "disk1")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_disk_health_sensor_no_data() -> None:
    """Test disk health sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "disk1")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_disk_health_sensor_with_data() -> None:
    """Test disk health sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    disk = MagicMock()
    disk.id = "disk1"
    disk.name = "disk1"
    disk.status = "DISK_OK"
    disk.temperature_celsius = 35
    disk.spin_state = "active"
    disk.serial_number = "WDC_12345"
    disk.device = "sdb"
    mock_coordinator.data.disks = [disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDiskHealthSensor(mock_coordinator, mock_entry, "disk1", "disk1")

    assert sensor.native_value == "DISK_OK"
    attrs = sensor.extra_state_attributes
    assert attrs["temperature"] == 35
    assert attrs["spin_state"] == "active"
    assert attrs["serial"] == "WDC_12345"
    assert attrs["device"] == "sdb"


def test_docker_vdisk_usage_sensor_no_data() -> None:
    """Test Docker vDisk usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDockerVDiskUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_docker_vdisk_usage_sensor_with_data() -> None:
    """Test Docker vDisk usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    disk = MagicMock()
    disk.role = "docker_vdisk"
    disk.size_bytes = 100000000000
    disk.used_bytes = 50000000000
    mock_coordinator.data.disks = [disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidDockerVDiskUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 50.0


def test_log_filesystem_usage_sensor_no_data() -> None:
    """Test log filesystem usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidLogFilesystemUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_log_filesystem_usage_sensor_with_data() -> None:
    """Test log filesystem usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    disk = MagicMock()
    disk.role = "log"
    disk.size_bytes = 10000000000
    disk.used_bytes = 2000000000
    mock_coordinator.data.disks = [disk]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidLogFilesystemUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 20.0


# Share Sensor tests


def test_share_usage_sensor_no_data() -> None:
    """Test share usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "appdata")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_share_usage_sensor_with_data() -> None:
    """Test share usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    share = MagicMock()
    share.name = "appdata"
    share.total_bytes = 1000000000000
    share.used_bytes = 200000000000
    share.free_bytes = 800000000000
    share.path = "/mnt/user/appdata"
    mock_coordinator.data.shares = [share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "appdata")

    assert sensor.native_value == 20.0
    attrs = sensor.extra_state_attributes
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs
    assert attrs["path"] == "/mnt/user/appdata"


def test_share_usage_sensor_share_not_found() -> None:
    """Test share usage sensor when share not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    share = MagicMock()
    share.name = "media"
    mock_coordinator.data.shares = [share]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidShareUsageSensor(mock_coordinator, mock_entry, "appdata")

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


# ZFS Sensor tests


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
    pool = MagicMock()
    pool.name = "tank"
    pool.size_bytes = 10000000000000
    pool.used_bytes = 5000000000000
    mock_coordinator.data.zfs_pools = [pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolUsageSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.native_value == 50.0


def test_zfs_pool_usage_sensor_pool_not_found() -> None:
    """Test ZFS pool usage sensor when pool not found."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    pool = MagicMock()
    pool.name = "other_pool"
    mock_coordinator.data.zfs_pools = [pool]
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
    pool = MagicMock()
    pool.name = "tank"
    pool.health = "ONLINE"
    mock_coordinator.data.zfs_pools = [pool]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSPoolHealthSensor(mock_coordinator, mock_entry, "tank")

    assert sensor.native_value == "ONLINE"


def test_zfs_arc_hit_ratio_sensor_no_data() -> None:
    """Test ZFS ARC hit ratio sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSARCHitRatioSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_zfs_arc_hit_ratio_sensor_with_data() -> None:
    """Test ZFS ARC hit ratio sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.zfs_arc = MagicMock()
    mock_coordinator.data.zfs_arc.hit_ratio_percent = 85.5
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidZFSARCHitRatioSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 85.5


# Notification Sensor tests


def test_notifications_sensor_no_data() -> None:
    """Test notifications sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNotificationsSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 0
    assert sensor.extra_state_attributes == {"unread_count": 0}


def test_notifications_sensor_with_list() -> None:
    """Test notifications sensor with list of notifications."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    # Direct list of notifications
    notif1 = MagicMock()
    notif1.type = "unread"
    notif2 = MagicMock()
    notif2.type = "archived"
    mock_coordinator.data.notifications = [notif1, notif2]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNotificationsSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 2
    attrs = sensor.extra_state_attributes
    assert attrs["unread_count"] == 1


def test_notifications_sensor_with_response_object() -> None:
    """Test notifications sensor with NotificationsResponse object."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    # NotificationsResponse format
    notif1 = MagicMock()
    notif1.type = "unread"
    notif2 = MagicMock()
    notif2.type = "unread"
    notif3 = MagicMock()
    notif3.type = "archived"
    notifications_response = MagicMock()
    notifications_response.notifications = [notif1, notif2, notif3]
    mock_coordinator.data.notifications = notifications_response
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidNotificationsSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 3
    attrs = sensor.extra_state_attributes
    assert attrs["unread_count"] == 2


# Parity Progress Sensor tests


def test_parity_progress_sensor_no_data() -> None:
    """Test parity progress sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidParityProgressSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 0


def test_parity_progress_sensor_with_data() -> None:
    """Test parity progress sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.parity_check_status = MagicMock()
    mock_coordinator.data.array.parity_check_status.progress_percent = 45.5
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidParityProgressSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 45.5


def test_parity_progress_sensor_no_parity_status() -> None:
    """Test parity progress sensor with no parity status."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.parity_check_status = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidParityProgressSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 0


# Fan Sensor tests


def test_fan_sensor_no_data() -> None:
    """Test fan sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 0)

    assert sensor.native_value is None


def test_fan_sensor_with_data() -> None:
    """Test fan sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    fan = MagicMock()
    fan.rpm = 1200
    mock_coordinator.data.system.fans = [fan]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 0)

    assert sensor.native_value == 1200


def test_fan_sensor_with_dict_data() -> None:
    """Test fan sensor with dict fan data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    # Dict format
    mock_coordinator.data.system.fans = [{"name": "CPU Fan", "rpm": 1500}]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 0)

    assert sensor.native_value == 1500


def test_fan_sensor_index_out_of_range() -> None:
    """Test fan sensor when index is out of range."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.fans = []
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 5)

    assert sensor.native_value is None


# Motherboard Temperature Sensor tests


def test_motherboard_temp_sensor_no_data() -> None:
    """Test motherboard temperature sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidMotherboardTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_motherboard_temp_sensor_with_data() -> None:
    """Test motherboard temperature sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.motherboard_temp_celsius = 42.0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidMotherboardTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 42.0


# =============================================================================
# Tests for helper functions and edge cases
# =============================================================================


def test_cpu_usage_sensor_extra_attributes() -> None:
    """Test CPU usage sensor extra attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 25.5
    mock_coordinator.data.system.cpu_model = "Intel Core i7-9700K"
    mock_coordinator.data.system.cpu_cores = 8
    mock_coordinator.data.system.cpu_threads = 16
    mock_coordinator.data.system.cpu_mhz = 3600
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    assert attrs["cpu_model"] == "Intel Core i7-9700K"
    assert attrs["cpu_cores"] == 8
    assert attrs["cpu_threads"] == 16
    assert "cpu_frequency" in attrs


def test_cpu_usage_sensor_incorrect_core_count() -> None:
    """Test CPU usage sensor corrects incorrect core count."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 25.5
    mock_coordinator.data.system.cpu_model = "Intel Core i7"
    # This should trigger the fix: cores=1 but threads > 2
    mock_coordinator.data.system.cpu_cores = 1
    mock_coordinator.data.system.cpu_threads = 16
    mock_coordinator.data.system.cpu_mhz = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    # Core count should be fixed to threads/2
    assert attrs["cpu_cores"] == 8


def test_ram_usage_sensor_extra_attributes() -> None:
    """Test RAM usage sensor extra attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.ram_usage_percent = 45.0
    mock_coordinator.data.system.ram_total_bytes = 32000000000  # ~32 GB
    mock_coordinator.data.system.ram_used_bytes = 14400000000  # ~14.4 GB
    mock_coordinator.data.system.ram_free_bytes = 10000000000  # ~10 GB
    mock_coordinator.data.system.ram_cached_bytes = 7500000000  # ~7.5 GB
    mock_coordinator.data.system.ram_buffers_bytes = 100000000  # ~100 MB
    mock_coordinator.data.system.server_model = "Custom Build"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    assert "ram_total" in attrs
    assert "server_model" in attrs
    assert "ram_used" in attrs
    assert "ram_free" in attrs
    assert "ram_cached" in attrs
    assert "ram_available" in attrs


def test_uptime_sensor_extra_attributes() -> None:
    """Test uptime sensor extra attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 86400  # 1 day
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    # These are the actual attribute names used in the sensor
    assert attrs["uptime_seconds"] == 86400
    assert attrs["days"] == 1
    assert attrs["hours"] == 0
    assert attrs["minutes"] == 0


def test_is_physical_network_interface_more_cases():
    """Test network interface detection with more cases."""
    # Additional physical interfaces (must match patterns in sensor.py)
    assert _is_physical_network_interface("bond1") is True
    assert _is_physical_network_interface("enp3s0") is True
    assert _is_physical_network_interface("eno2") is True

    # Virtual interfaces
    assert _is_physical_network_interface("br0") is False
    assert _is_physical_network_interface("docker0") is False
    assert _is_physical_network_interface("veth123") is False


# ==================== More helper function tests ====================


def test_get_cpu_usage_none_data():
    """Test _get_cpu_usage with None data."""
    from custom_components.unraid_management_agent.sensor import _get_cpu_usage

    result = _get_cpu_usage(None)
    assert result is None


def test_get_cpu_usage_no_system():
    """Test _get_cpu_usage with no system data."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_cpu_usage

    data = UnraidData()
    data.system = None
    result = _get_cpu_usage(data)
    assert result is None


def test_get_cpu_usage_no_value():
    """Test _get_cpu_usage when cpu_usage_percent is None."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_cpu_usage

    data = UnraidData()
    data.system = MagicMock()
    data.system.cpu_usage_percent = None
    result = _get_cpu_usage(data)
    assert result is None


def test_get_cpu_attrs_none_data():
    """Test _get_cpu_attrs with None data."""
    from custom_components.unraid_management_agent.sensor import _get_cpu_attrs

    result = _get_cpu_attrs(None)
    assert result == {}


def test_get_cpu_attrs_no_system():
    """Test _get_cpu_attrs with no system data."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_cpu_attrs

    data = UnraidData()
    data.system = None
    result = _get_cpu_attrs(data)
    assert result == {}


def test_get_ram_usage_none_data():
    """Test _get_ram_usage with None data."""
    from custom_components.unraid_management_agent.sensor import _get_ram_usage

    result = _get_ram_usage(None)
    assert result is None


def test_get_ram_usage_no_value():
    """Test _get_ram_usage when ram_usage_percent is None."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_ram_usage

    data = UnraidData()
    data.system = MagicMock()
    data.system.ram_usage_percent = None
    result = _get_ram_usage(data)
    assert result is None


def test_get_ram_attrs_none_data():
    """Test _get_ram_attrs with None data."""
    from custom_components.unraid_management_agent.sensor import _get_ram_attrs

    result = _get_ram_attrs(None)
    assert result == {}


def test_get_ram_attrs_minimal():
    """Test _get_ram_attrs with minimal data."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_ram_attrs

    data = UnraidData()
    data.system = MagicMock()
    data.system.ram_total_bytes = 0
    data.system.ram_used_bytes = 0
    data.system.ram_free_bytes = 0
    data.system.ram_cached_bytes = 0
    data.system.ram_buffers_bytes = 0
    data.system.server_model = None

    result = _get_ram_attrs(data)
    # Should not have ram_available since free/cached/buffers are 0
    assert "ram_available" not in result


def test_get_cpu_temperature_none_data():
    """Test _get_cpu_temperature with None data."""
    from custom_components.unraid_management_agent.sensor import _get_cpu_temperature

    result = _get_cpu_temperature(None)
    assert result is None


def test_get_cpu_temperature_no_value():
    """Test _get_cpu_temperature when cpu_temp_celsius is None."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_cpu_temperature

    data = UnraidData()
    data.system = MagicMock()
    data.system.cpu_temp_celsius = None
    result = _get_cpu_temperature(data)
    assert result is None


def test_get_uptime_none_data():
    """Test _get_uptime with None data."""
    from custom_components.unraid_management_agent.sensor import _get_uptime

    result = _get_uptime(None)
    assert result is None


def test_get_uptime_attrs_none_data():
    """Test _get_uptime_attrs with None data."""
    from custom_components.unraid_management_agent.sensor import _get_uptime_attrs

    result = _get_uptime_attrs(None)
    assert result == {}


def test_get_parity_progress_none_data():
    """Test _get_parity_progress with None data returns 0.0."""
    from custom_components.unraid_management_agent.sensor import _get_parity_progress

    result = _get_parity_progress(None)
    # Returns 0.0 when no data
    assert result == 0.0


def test_get_parity_progress_no_array():
    """Test _get_parity_progress with no array data returns 0.0."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_parity_progress

    data = UnraidData()
    data.array = None
    result = _get_parity_progress(data)
    assert result == 0.0


def test_get_array_usage_none_data():
    """Test _get_array_usage with None data."""
    from custom_components.unraid_management_agent.sensor import _get_array_usage

    result = _get_array_usage(None)
    assert result is None


def test_get_array_attrs_none_data():
    """Test _get_array_attrs with None data."""
    from custom_components.unraid_management_agent.sensor import _get_array_attrs

    result = _get_array_attrs(None)
    assert result == {}


def test_get_parity_attrs_none_data():
    """Test _get_parity_attrs with None data."""
    from custom_components.unraid_management_agent.sensor import _get_parity_attrs

    result = _get_parity_attrs(None)
    assert result == {}


def test_get_cpu_attrs_no_mhz():
    """Test _get_cpu_attrs without cpu_mhz."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_cpu_attrs

    data = UnraidData()
    data.system = MagicMock()
    data.system.cpu_model = "Intel Core i7"
    data.system.cpu_cores = 4
    data.system.cpu_threads = 8
    data.system.cpu_mhz = None

    result = _get_cpu_attrs(data)
    assert "cpu_model" in result
    assert result["cpu_cores"] == 4
    assert "cpu_frequency" not in result


def test_get_array_attrs_no_data():
    """Test _get_array_attrs with no data."""
    from custom_components.unraid_management_agent.sensor import _get_array_attrs

    result = _get_array_attrs(None)
    assert result == {}


def test_get_array_usage_fallback_calculation():
    """Test _get_array_usage with fallback calculation."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_array_usage

    data = UnraidData()
    data.array = MagicMock()
    data.array.used_percent = None  # No direct percent
    data.array.total_bytes = 1000000000000  # 1 TB
    data.array.used_bytes = 500000000000  # 500 GB

    result = _get_array_usage(data)
    assert result == 50.0


def test_get_array_usage_zero_total():
    """Test _get_array_usage when total is zero."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_array_usage

    data = UnraidData()
    data.array = MagicMock()
    data.array.used_percent = None
    data.array.total_bytes = 0
    data.array.used_bytes = 0

    result = _get_array_usage(data)
    assert result is None


def test_get_parity_progress_with_value():
    """Test _get_parity_progress with a value."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_parity_progress

    data = UnraidData()
    data.array = MagicMock()
    data.array.sync_percent = 45.678

    result = _get_parity_progress(data)
    assert result == 45.7


def test_get_cpu_attrs_with_core_fix():
    """Test _get_cpu_attrs with core count fix."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_cpu_attrs

    data = UnraidData()
    data.system = MagicMock()
    data.system.cpu_model = "Intel Core i7"
    # cores=1 with threads>2 triggers the fix
    data.system.cpu_cores = 1
    data.system.cpu_threads = 8
    data.system.cpu_mhz = 3600

    result = _get_cpu_attrs(data)
    # Cores should be fixed to threads/2
    assert result["cpu_cores"] == 4


def test_get_uptime_attrs_with_data():
    """Test _get_uptime_attrs with data."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_uptime_attrs

    data = UnraidData()
    data.system = MagicMock()
    data.system.uptime_seconds = 90061  # 1 day, 1 hour, 1 minute, 1 second
    data.system.hostname = "TestServer"
    data.system.version = "6.12.4"

    result = _get_uptime_attrs(data)
    assert result["uptime_total_seconds"] == 90061
    assert result["uptime_days"] == 1
    assert result["uptime_hours"] == 1
    assert result["uptime_minutes"] == 1
    assert result["hostname"] == "TestServer"
    assert result["version"] == "6.12.4"


def test_get_uptime_no_system():
    """Test _get_uptime with no system."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_uptime

    data = UnraidData()
    data.system = None

    result = _get_uptime(data)
    assert result is None


def test_get_uptime_no_value():
    """Test _get_uptime when uptime_seconds is None."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_uptime

    data = UnraidData()
    data.system = MagicMock()
    data.system.uptime_seconds = None

    result = _get_uptime(data)
    assert result is None


def test_get_parity_attrs_with_data():
    """Test _get_parity_attrs with data."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_parity_attrs

    data = UnraidData()
    data.array = MagicMock()
    data.array.sync_action = "check"
    data.array.sync_errors = 0
    data.array.sync_speed = "100 MB/s"
    data.array.sync_estimated_finish = "2 hours"
    data.array.sync_correcting = False

    result = _get_parity_attrs(data)
    assert result["sync_action"] == "check"
    assert result["sync_errors"] == 0
    assert result["sync_speed"] == "100 MB/s"


def test_get_array_attrs_with_data():
    """Test _get_array_attrs with data."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_array_attrs

    data = UnraidData()
    data.array = MagicMock()
    data.array.state = "started"
    data.array.num_disks = 10
    data.array.num_data_disks = 8
    data.array.num_parity_disks = 2
    data.array.total_bytes = 10000000000000  # 10 TB
    data.array.used_bytes = 5000000000000  # 5 TB
    data.array.free_bytes = 5000000000000  # 5 TB

    result = _get_array_attrs(data)
    assert result["array_state"] == "started"
    assert result["num_disks"] == 10
    assert "total_capacity" in result
    assert "used_space" in result
    assert "free_space" in result


def test_is_physical_disk_various_patterns() -> None:
    """Test _is_physical_disk with various patterns."""
    from custom_components.unraid_management_agent.sensor import _is_physical_disk

    # Physical disk - valid role, status, and device
    class PhysicalDisk:
        role = "data"
        status = "DISK_OK"
        device = "sda"

    assert _is_physical_disk(PhysicalDisk()) is True

    # Virtual disk - docker_vdisk role
    class VirtualDisk:
        role = "docker_vdisk"
        status = "DISK_OK"
        device = "sdb"

    assert _is_physical_disk(VirtualDisk()) is False

    # Disabled slot
    class DisabledDisk:
        role = "data"
        status = "DISK_NP_DSBL"
        device = ""

    assert _is_physical_disk(DisabledDisk()) is False

    # No device assigned
    class NoDeviceDisk:
        role = "parity"
        status = "DISK_OK"
        device = ""

    assert _is_physical_disk(NoDeviceDisk()) is False


def test_get_ram_attrs_with_available():
    """Test _get_ram_attrs calculates ram_available correctly."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_ram_attrs

    data = UnraidData()
    data.system = MagicMock()
    data.system.ram_total_bytes = 32000000000  # ~32 GB
    data.system.ram_used_bytes = 10000000000  # ~10 GB
    data.system.ram_free_bytes = 5000000000  # ~5 GB
    data.system.ram_cached_bytes = 12000000000  # ~12 GB
    data.system.ram_buffers_bytes = 5000000000  # ~5 GB
    data.system.server_model = None

    result = _get_ram_attrs(data)
    assert "ram_available" in result
    assert "ram_used" in result
    assert "ram_free" in result
    assert "ram_cached" in result


def test_format_bytes():
    """Test format_bytes helper function."""
    from custom_components.unraid_management_agent.sensor import format_bytes

    # format_bytes always uses .1f format
    assert format_bytes(0) == "0.0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"
    assert format_bytes(1099511627776) == "1.0 TB"


def test_get_uptime_no_uptime_seconds():
    """Test _get_uptime when uptime_seconds is missing."""
    from custom_components.unraid_management_agent.coordinator import UnraidData
    from custom_components.unraid_management_agent.sensor import _get_uptime

    data = UnraidData()
    data.system = MagicMock(spec=[])  # Empty spec means no attributes

    result = _get_uptime(data)
    assert result is None


def test_array_usage_sensor_native_value():
    """Test UnraidArrayUsageSensor native_value."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.used_percent = 45.678
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 45.7


def test_parity_progress_sensor_native_value():
    """Test UnraidParityProgressSensor native_value."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_parity_status = MagicMock()
    mock_parity_status.progress_percent = 50.5
    mock_coordinator.data.array.parity_check_status = mock_parity_status
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidParityProgressSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 50.5


def test_parity_progress_sensor_native_value_no_parity_status():
    """Test UnraidParityProgressSensor native_value with no parity status."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.parity_check_status = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidParityProgressSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 0


def test_unraid_sensor_entity_native_value_with_none_data():
    """Test UnraidSensorEntity native_value returns None when coordinator data is None."""
    from custom_components.unraid_management_agent.sensor import UnraidSensorEntity

    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    mock_description = MagicMock()
    mock_description.key = "test_sensor"
    mock_description.value_fn = MagicMock(return_value=42)
    mock_description.available_fn = MagicMock(return_value=True)

    sensor = UnraidSensorEntity(mock_coordinator, mock_description)

    value = sensor.native_value
    assert value is None


def test_unraid_sensor_entity_extra_state_attributes_no_fn():
    """Test UnraidSensorEntity extra_state_attributes returns None when no fn defined."""
    from custom_components.unraid_management_agent.sensor import UnraidSensorEntity

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    mock_description = MagicMock()
    mock_description.key = "test_sensor"
    mock_description.value_fn = MagicMock(return_value=42)
    mock_description.extra_state_attributes_fn = None
    mock_description.available_fn = MagicMock(return_value=True)

    sensor = UnraidSensorEntity(mock_coordinator, mock_description)

    attrs = sensor.extra_state_attributes
    assert attrs is None


def test_unraid_sensor_entity_available_when_coordinator_unavailable():
    """Test UnraidSensorEntity available returns False when coordinator unavailable."""
    from custom_components.unraid_management_agent.sensor import UnraidSensorEntity

    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = False
    mock_coordinator.data = MagicMock()
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    mock_description = MagicMock()
    mock_description.key = "test_sensor"
    mock_description.value_fn = MagicMock(return_value=42)
    mock_description.available_fn = MagicMock(return_value=True)

    sensor = UnraidSensorEntity(mock_coordinator, mock_description)

    available = sensor.available
    assert available is False


def test_unraid_sensor_entity_available_when_data_is_none():
    """Test UnraidSensorEntity available returns False when data is None."""
    from custom_components.unraid_management_agent.sensor import UnraidSensorEntity

    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = None
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    mock_description = MagicMock()
    mock_description.key = "test_sensor"
    mock_description.value_fn = MagicMock(return_value=42)
    mock_description.available_fn = MagicMock(return_value=True)

    sensor = UnraidSensorEntity(mock_coordinator, mock_description)

    available = sensor.available
    assert available is False


def test_is_physical_network_interface_extended():
    """Test _is_physical_network_interface function with extended cases."""
    from custom_components.unraid_management_agent.sensor import (
        _is_physical_network_interface,
    )

    # Physical interfaces
    assert _is_physical_network_interface("eth0") is True
    assert _is_physical_network_interface("eth1") is True
    assert _is_physical_network_interface("wlan0") is True
    assert _is_physical_network_interface("bond0") is True
    assert _is_physical_network_interface("eno1") is True
    assert _is_physical_network_interface("enp2s0") is True

    # Non-physical interfaces
    assert _is_physical_network_interface("docker0") is False
    assert _is_physical_network_interface("lo") is False
    assert _is_physical_network_interface("veth123") is False
    assert _is_physical_network_interface("br0") is False


def test_fan_sensor_native_value():
    """Test UnraidFanSensor native_value."""
    from custom_components.unraid_management_agent.sensor import UnraidFanSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    fan_obj = MagicMock()
    fan_obj.rpm = 1200  # Correct attribute name
    mock_coordinator.data.system.fans = [fan_obj]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 0)

    value = sensor.native_value
    assert value == 1200


def test_fan_sensor_native_value_with_dict():
    """Test UnraidFanSensor native_value when fan is a dict."""
    from custom_components.unraid_management_agent.sensor import UnraidFanSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    # Fan as dict instead of object
    mock_coordinator.data.system.fans = [{"name": "CPU Fan", "rpm": 1500}]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 0)

    value = sensor.native_value
    assert value == 1500


def test_fan_sensor_native_value_no_fans():
    """Test UnraidFanSensor native_value when no fans data."""
    from custom_components.unraid_management_agent.sensor import UnraidFanSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.fans = []
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 0)

    value = sensor.native_value
    assert value is None


def test_cpu_usage_sensor_native_value():
    """Test UnraidCPUUsageSensor native_value."""
    from custom_components.unraid_management_agent.sensor import UnraidCPUUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 45.5
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 45.5


def test_ram_usage_sensor_native_value():
    """Test UnraidRAMUsageSensor native_value."""
    from custom_components.unraid_management_agent.sensor import UnraidRAMUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.ram_usage_percent = 60.0  # Correct attribute name
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 60.0


def test_cpu_temperature_sensor_native_value():
    """Test UnraidCPUTemperatureSensor native_value."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidCPUTemperatureSensor,
    )

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_temp_celsius = 55.0  # Correct attribute name
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUTemperatureSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 55.0


def test_uptime_sensor_native_value():
    """Test UnraidUptimeSensor native_value."""
    from custom_components.unraid_management_agent.sensor import UnraidUptimeSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 86400
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    # Should return formatted time
    assert value is not None


def test_array_usage_sensor_native_value_direct():
    """Test UnraidArrayUsageSensor native_value with direct used_percent."""
    from custom_components.unraid_management_agent.sensor import UnraidArrayUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.used_percent = 75.5
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 75.5


def test_cpu_usage_sensor_unique_id():
    """Test UnraidCPUUsageSensor unique_id."""
    from custom_components.unraid_management_agent.sensor import UnraidCPUUsageSensor

    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    assert sensor.unique_id == "test_entry_cpu_usage"


def test_ram_usage_sensor_unique_id():
    """Test UnraidRAMUsageSensor unique_id."""
    from custom_components.unraid_management_agent.sensor import UnraidRAMUsageSensor

    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    assert sensor.unique_id == "test_entry_ram_usage"


def test_cpu_temperature_sensor_unique_id():
    """Test UnraidCPUTemperatureSensor unique_id."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidCPUTemperatureSensor,
    )

    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.unique_id == "test_entry_cpu_temperature"


def test_uptime_sensor_unique_id():
    """Test UnraidUptimeSensor unique_id."""
    from custom_components.unraid_management_agent.sensor import UnraidUptimeSensor

    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    assert sensor.unique_id == "test_entry_uptime"


def test_array_usage_sensor_unique_id():
    """Test UnraidArrayUsageSensor unique_id."""
    from custom_components.unraid_management_agent.sensor import UnraidArrayUsageSensor

    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    assert sensor.unique_id == "test_entry_array_usage"


def test_fan_sensor_unique_id():
    """Test UnraidFanSensor unique_id."""
    from custom_components.unraid_management_agent.sensor import UnraidFanSensor

    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidFanSensor(mock_coordinator, mock_entry, "CPU Fan", 0)

    assert sensor.unique_id == "test_entry_fan_0"


def test_parity_progress_sensor_unique_id():
    """Test UnraidParityProgressSensor unique_id."""
    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidParityProgressSensor(mock_coordinator, mock_entry)

    assert sensor.unique_id == "test_entry_parity_progress"


def test_array_usage_sensor_native_value_from_bytes():
    """Test UnraidArrayUsageSensor native_value calculated from bytes."""
    from custom_components.unraid_management_agent.sensor import UnraidArrayUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    # No used_percent, calculate from bytes
    mock_coordinator.data.array.used_percent = None
    mock_coordinator.data.array.total_bytes = 1000
    mock_coordinator.data.array.used_bytes = 500
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 50.0  # 500/1000 * 100


def test_array_usage_sensor_native_value_zero_total():
    """Test UnraidArrayUsageSensor native_value returns None when total is zero."""
    from custom_components.unraid_management_agent.sensor import UnraidArrayUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.used_percent = None
    mock_coordinator.data.array.total_bytes = 0
    mock_coordinator.data.array.used_bytes = 0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value is None


def test_array_usage_sensor_extra_state_attributes():
    """Test UnraidArrayUsageSensor extra_state_attributes."""
    from custom_components.unraid_management_agent.sensor import UnraidArrayUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.state = "Started"
    mock_coordinator.data.array.num_disks = 5
    mock_coordinator.data.array.num_data_disks = 4
    mock_coordinator.data.array.num_parity_disks = 1
    mock_coordinator.data.array.total_bytes = 10000000000
    mock_coordinator.data.array.used_bytes = 5000000000
    mock_coordinator.data.array.free_bytes = 5000000000
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs


def test_motherboard_temperature_sensor_native_value():
    """Test UnraidMotherboardTemperatureSensor native_value."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidMotherboardTemperatureSensor,
    )

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.motherboard_temp_celsius = 42.0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidMotherboardTemperatureSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 42.0


def test_motherboard_temperature_sensor_unique_id():
    """Test UnraidMotherboardTemperatureSensor unique_id."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidMotherboardTemperatureSensor,
    )

    mock_coordinator = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidMotherboardTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.unique_id == "test_entry_motherboard_temperature"


def test_uptime_sensor_extra_state_attributes():
    """Test UnraidUptimeSensor extra_state_attributes."""
    from custom_components.unraid_management_agent.sensor import UnraidUptimeSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 86400
    mock_coordinator.data.system.boot_time = 1700000000
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    assert attrs is not None


def test_ram_usage_sensor_extra_state_attributes():
    """Test UnraidRAMUsageSensor extra_state_attributes with no data."""
    from custom_components.unraid_management_agent.sensor import UnraidRAMUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    assert attrs == {}


def test_cpu_usage_sensor_extra_state_attributes():
    """Test UnraidCPUUsageSensor extra_state_attributes."""
    from custom_components.unraid_management_agent.sensor import UnraidCPUUsageSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_model = "Intel Core i9"
    mock_coordinator.data.system.cpu_cores = 8
    mock_coordinator.data.system.cpu_threads = 16
    mock_coordinator.data.system.cpu_mhz = 3600.0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    assert attrs is not None


def test_gpu_temperature_sensor_igpu_fallback():
    """Test UnraidGPUCPUTemperatureSensor falls back to cpu_temperature for iGPU."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidGPUCPUTemperatureSensor,
    )

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.temperature_celsius = 0  # Zero means no discrete GPU temp
    mock_gpu.cpu_temperature_celsius = 65.0  # iGPU fallback
    mock_coordinator.data.gpu = [mock_gpu]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUCPUTemperatureSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 65.0


def test_gpu_temperature_sensor_discrete():
    """Test UnraidGPUCPUTemperatureSensor with discrete GPU temp."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidGPUCPUTemperatureSensor,
    )

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.temperature_celsius = 70.0  # Discrete GPU temp
    mock_coordinator.data.gpu = [mock_gpu]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUCPUTemperatureSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 70.0


def test_gpu_utilization_sensor_native_value():
    """Test UnraidGPUUtilizationSensor native_value."""
    from custom_components.unraid_management_agent.sensor import (
        UnraidGPUUtilizationSensor,
    )

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.utilization_gpu_percent = 45.0  # Correct attribute name
    mock_coordinator.data.gpu = [mock_gpu]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUUtilizationSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 45.0


def test_gpu_power_sensor_native_value():
    """Test UnraidGPUPowerSensor native_value."""
    from custom_components.unraid_management_agent.sensor import UnraidGPUPowerSensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.power_draw_watts = 150.0  # Correct attribute name
    mock_coordinator.data.gpu = [mock_gpu]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidGPUPowerSensor(mock_coordinator, mock_entry)

    value = sensor.native_value
    assert value == 150.0
