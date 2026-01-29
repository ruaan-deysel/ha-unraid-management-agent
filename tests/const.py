"""Constants and mock factories for Unraid Management Agent tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import CONF_HOST, CONF_PORT

# Mock configuration
MOCK_CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 8043,
}

MOCK_OPTIONS = {
    "enable_websocket": True,
}


def mock_system_info() -> MagicMock:
    """Create a mock SystemInfo Pydantic model."""
    system = MagicMock()
    system.hostname = "unraid-test"
    system.version = "6.12.6"
    system.agent_version = "1.2.0"
    system.cpu_usage_percent = 25.5
    system.ram_usage_percent = 45.2
    system.cpu_temp_celsius = 55.0
    system.motherboard_temp_celsius = 42.0
    system.cpu_model = "Intel Core i7-9700K"
    system.cpu_cores = 8
    system.cpu_threads = 8
    system.cpu_mhz = 3600.0
    system.ram_total_bytes = 34359738368  # 32 GB
    system.ram_used_bytes = 15534686208
    system.ram_free_bytes = 10737418240
    system.ram_cached_bytes = 8087633920
    system.ram_buffers_bytes = 0
    system.uptime_seconds = 86400  # 1 day
    system.server_model = "Custom Build"
    system.fans = [
        MagicMock(name="CPU Fan", rpm=1200),
        MagicMock(name="System Fan", rpm=800),
    ]
    # Set fan name as an attribute since MagicMock(name=...) sets the mock's name
    system.fans[0].name = "CPU Fan"
    system.fans[1].name = "System Fan"
    return system


def mock_array_status() -> MagicMock:
    """Create a mock ArrayStatus Pydantic model."""
    array = MagicMock()
    array.state = "Started"
    array.total_bytes = 16000000000000
    array.used_bytes = 8000000000000
    array.free_bytes = 8000000000000
    array.used_percent = 50.0  # Add used_percent for direct access
    array.num_disks = 4
    array.num_data_disks = 3
    array.num_parity_disks = 1
    array.parity_valid = True
    array.parity_check_status = MagicMock()
    array.parity_check_status.status = "idle"
    array.parity_check_status.progress_percent = 0
    return array


def mock_disks() -> list[MagicMock]:
    """Create mock DiskInfo Pydantic models."""
    disk1 = MagicMock()
    disk1.id = "WDC_WD80EFAX_12345"
    disk1.name = "disk1"
    disk1.device = "sdb"
    disk1.role = "data"
    disk1.size_bytes = 8000000000000
    disk1.total_bytes = 8000000000000  # Alias for size_bytes used by some sensors
    disk1.used_bytes = 4000000000000
    disk1.free_bytes = 4000000000000
    disk1.temperature_celsius = 35
    disk1.spin_state = "active"
    disk1.status = "DISK_OK"
    disk1.smart_status = "PASSED"
    disk1.model = "WD Red 8TB"
    disk1.serial = "WD-WX12A34567"
    disk1.filesystem = "xfs"
    disk1.serial_number = "WDC_WD80EFAX_12345"
    disk1.used_percent = 50.0

    disk2 = MagicMock()
    disk2.id = "Samsung_SSD_980_67890"
    disk2.name = "cache"
    disk2.device = "nvme0n1"
    disk2.role = "cache"
    disk2.size_bytes = 256054571008
    disk2.total_bytes = 256054571008  # Alias for size_bytes used by some sensors
    disk2.used_bytes = 36332154880
    disk2.free_bytes = 219722416128
    disk2.temperature_celsius = 42
    disk2.spin_state = "active"
    disk2.status = "DISK_OK"
    disk2.smart_status = "PASSED"
    disk2.model = "Samsung 980 Pro"
    disk2.serial = "S5PXNG0R123456"
    disk2.filesystem = "btrfs"
    disk2.serial_number = "Samsung_SSD_980_67890"
    disk2.used_percent = 14.2

    return [disk1, disk2]


def mock_ups_info() -> MagicMock:
    """Create a mock UPSInfo Pydantic model."""
    ups = MagicMock()
    ups.connected = True
    ups.status = "ONLINE"
    ups.model = "APC Back-UPS 1500"
    ups.battery_charge_percent = 100
    ups.runtime_minutes = 60
    # Add runtime_left_seconds for uma-api compatibility
    ups.runtime_left_seconds = 3600  # 60 minutes in seconds
    ups.battery_runtime_seconds = 3600  # fallback field
    ups.power_watts = 150.5
    ups.load_percent = 25
    ups.energy_kwh = 10.5
    return ups


def mock_containers() -> list[MagicMock]:
    """Create mock ContainerInfo Pydantic models."""
    plex = MagicMock()
    plex.id = "plex_container_id"
    plex.container_id = "plex_container_id"
    plex.name = "plex"
    plex.state = "running"
    plex.image = "plexinc/pms-docker:latest"
    plex.ports = ["32400:32400/tcp"]

    sonarr = MagicMock()
    sonarr.id = "sonarr_container_id"
    sonarr.container_id = "sonarr_container_id"
    sonarr.name = "sonarr"
    sonarr.state = "stopped"
    sonarr.image = "linuxserver/sonarr:latest"
    sonarr.ports = ["8989:8989/tcp"]

    return [plex, sonarr]


def mock_vms() -> list[MagicMock]:
    """Create mock VMInfo Pydantic models."""
    windows = MagicMock()
    windows.id = "windows-10"
    windows.name = "Windows 10"
    windows.state = "running"
    windows.cpu_count = 4
    windows.memory_display = "8 GB"
    windows.guest_cpu_percent = 15.5
    windows.host_cpu_percent = 3.2
    windows.disk_read_bytes = 1024000
    windows.disk_write_bytes = 512000

    ubuntu = MagicMock()
    ubuntu.id = "ubuntu-server"
    ubuntu.name = "Ubuntu Server"
    ubuntu.state = "stopped"
    ubuntu.cpu_count = 2
    ubuntu.memory_display = "4 GB"
    ubuntu.guest_cpu_percent = None
    ubuntu.host_cpu_percent = None
    ubuntu.disk_read_bytes = 0
    ubuntu.disk_write_bytes = 0

    return [windows, ubuntu]


def mock_gpu_list() -> list[MagicMock]:
    """Create mock GPUInfo Pydantic models."""
    gpu = MagicMock()
    gpu.name = "NVIDIA GeForce RTX 3080"
    gpu.driver_version = "535.86.05"
    gpu.utilization_gpu_percent = 45
    gpu.temperature_celsius = 65
    gpu.cpu_temperature_celsius = 50  # Fallback for iGPUs
    gpu.power_draw_watts = 220.5
    return [gpu]


def mock_network_interfaces() -> list[MagicMock]:
    """Create mock NetworkInterface Pydantic models."""
    eth0 = MagicMock()
    eth0.name = "eth0"
    eth0.state = "up"
    eth0.speed_mbps = 1000
    eth0.mac_address = "00:11:22:33:44:55"
    eth0.ip_address = "192.168.1.100"
    eth0.rx_bytes_per_sec = 125000
    eth0.tx_bytes_per_sec = 62500
    # Add bytes_received/bytes_sent for total byte counters
    eth0.bytes_received = 1000000000
    eth0.bytes_sent = 500000000

    eth1 = MagicMock()
    eth1.name = "eth1"
    eth1.state = "down"
    eth1.speed_mbps = 0
    eth1.mac_address = "00:11:22:33:44:56"
    eth1.ip_address = None
    eth1.rx_bytes_per_sec = 0
    eth1.tx_bytes_per_sec = 0
    eth1.bytes_received = 0
    eth1.bytes_sent = 0

    return [eth0, eth1]


def mock_collectors_status(*, all_enabled: bool = True) -> MagicMock:
    """
    Create a mock CollectorStatus Pydantic model.

    Args:
        all_enabled: If True, all collectors are enabled. If False, nut/zfs/unassigned disabled.

    """
    collectors_status = MagicMock()

    # Define collector info items
    collector_names = [
        "system",
        "array",
        "disk",
        "docker",
        "vm",
        "ups",
        "nut",
        "gpu",
        "shares",
        "network",
        "hardware",
        "zfs",
        "notification",
        "registration",
        "unassigned",
    ]

    collectors = []
    disabled = {"nut", "zfs", "unassigned"} if not all_enabled else set()

    for name in collector_names:
        c = MagicMock()
        c.name = name
        c.enabled = name not in disabled
        c.interval_seconds = 60 if c.enabled else 0
        c.status = "running" if c.enabled else "disabled"
        c.required = name == "system"
        c.error_count = 0
        collectors.append(c)

    collectors_status.collectors = collectors
    collectors_status.total = len(collectors)
    collectors_status.enabled_count = sum(1 for c in collectors if c.enabled)
    collectors_status.disabled_count = sum(1 for c in collectors if not c.enabled)

    return collectors_status


# Legacy dict format for backward compatibility with older tests
MOCK_HEALTH_CHECK = {
    "status": "healthy",
    "version": "1.0.0",
}

MOCK_SYSTEM_DATA = {
    "hostname": "unraid-test",
    "version": "6.12.6",
    "cpu_usage_percent": 25.5,
    "ram_usage_percent": 45.2,
    "cpu_temp_celsius": 55.0,
    "motherboard_temp_celsius": 42.0,
    "cpu_model": "Intel Core i7-9700K",
    "ram_total_bytes": 34359738368,
    "uptime_seconds": 86400,
}

MOCK_ARRAY_DATA = {
    "state": "STARTED",
    "size_bytes": 16000000000000,
    "used_bytes": 8000000000000,
    "free_bytes": 8000000000000,
    "used_percent": 50.0,
    "num_disks": 4,
    "num_data_disks": 3,
    "num_parity_disks": 1,
    "parity_check_status": "idle",
    "parity_valid": True,
    "sync_percent": 0,
}
