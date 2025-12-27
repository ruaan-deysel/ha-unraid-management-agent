"""Constants for Unraid Management Agent tests."""

from homeassistant.const import CONF_HOST, CONF_PORT

# Mock configuration
MOCK_CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 8043,
}

MOCK_OPTIONS = {
    "update_interval": 30,
    "enable_websocket": True,
}

# Mock API responses
MOCK_SYSTEM_DATA = {
    "hostname": "unraid-test",
    "cpu_usage_percent": 25.5,
    "ram_usage_percent": 45.2,
    "cpu_temp_celsius": 55.0,
    "motherboard_temp_celsius": 42.0,
    "cpu_model": "Intel Core i7-9700K",
    "ram_total_bytes": 34359738368,  # 32 GB
    "uptime_seconds": 86400,  # 1 day
    "fans": [
        {"name": "CPU Fan", "rpm": 1200},
        {"name": "System Fan", "rpm": 800},
    ],
}

MOCK_ARRAY_DATA = {
    "state": "STARTED",
    "size_bytes": 16000000000000,
    "used_bytes": 8000000000000,
    "free_bytes": 8000000000000,
    "used_percent": 50.0,  # Added for sensor
    "num_disks": 4,
    "num_data_disks": 3,
    "num_parity_disks": 1,
    "parity_check_status": "idle",
    "parity_valid": True,
    "sync_percent": 0,
}

MOCK_DISKS_DATA = [
    {
        "id": "WDC_WD80EFAX_12345",
        "device": "sdb",
        "name": "disk1",
        "role": "data",
        "size_bytes": 8000000000000,
        "used_bytes": 4000000000000,
        "free_bytes": 4000000000000,
        "usage_percent": 50.0,
        "temperature_celsius": 35,
        "spin_state": "active",
        "status": "DISK_OK",
        "filesystem": "xfs",
        "mount_point": "/mnt/disk1",
        "smart_status": "PASSED",
        "smart_errors": 0,
    },
    {
        "id": "Samsung_SSD_980_67890",
        "device": "nvme0n1",
        "name": "cache",
        "role": "cache",
        "size_bytes": 256054571008,
        "used_bytes": 36332154880,
        "free_bytes": 219722416128,
        "usage_percent": 14.2,
        "temperature_celsius": 42,
        "spin_state": "active",
        "status": "DISK_OK",
        "filesystem": "btrfs",
        "mount_point": "/mnt/cache",
        "smart_status": "PASSED",
        "smart_errors": 0,
    },
]

MOCK_UPS_DATA = {
    "status": "ONLINE",
    "battery_charge_percent": 100,
    "runtime_left_seconds": 3600,
    "power_watts": 150.5,
    "load_percent": 25,
    "model": "APC Back-UPS 1500",
}

MOCK_CONTAINERS_DATA = [
    {
        "id": "plex",
        "name": "plex",
        "state": "running",
        "status": "Up 2 days",
        "image": "plexinc/pms-docker:latest",
    },
    {
        "id": "sonarr",
        "name": "sonarr",
        "state": "stopped",
        "status": "Exited (0) 1 hour ago",
        "image": "linuxserver/sonarr:latest",
    },
]

MOCK_VMS_DATA = [
    {
        "id": "windows-10",
        "name": "Windows 10",
        "state": "running",
        "cpu_count": 4,
        "memory_mb": 8192,
    },
    {
        "id": "ubuntu-server",
        "name": "Ubuntu Server",
        "state": "stopped",
        "cpu_count": 2,
        "memory_mb": 4096,
    },
]

MOCK_GPU_DATA = [
    {
        "name": "NVIDIA GeForce RTX 3080",
        "utilization_percent": 45,
        "temperature_celsius": 65,
        "power_watts": 220,
        "memory_used_mb": 4096,
        "memory_total_mb": 10240,
    },
]

MOCK_NETWORK_DATA = [
    {
        "interface": "eth0",
        "state": "up",
        "speed_mbps": 1000,
        "rx_bytes": 1234567890,
        "tx_bytes": 987654321,
        "rx_packets": 1000000,
        "tx_packets": 800000,
    },
    {
        "interface": "eth1",
        "state": "down",
        "speed_mbps": 0,
        "rx_bytes": 0,
        "tx_bytes": 0,
        "rx_packets": 0,
        "tx_packets": 0,
    },
]

# Mock health check response
MOCK_HEALTH_CHECK = {
    "status": "healthy",
    "version": "1.0.0",
}
