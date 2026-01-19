"""Constants for the Unraid Management Agent integration."""

from typing import Final

# Integration domain
DOMAIN: Final = "unraid_management_agent"

# Configuration keys
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_ENABLE_WEBSOCKET: Final = "enable_websocket"

# Default values
DEFAULT_PORT: Final = 8043
DEFAULT_UPDATE_INTERVAL: Final = 30  # seconds
DEFAULT_ENABLE_WEBSOCKET: Final = True

# Device info
MANUFACTURER: Final = "Lime Technology"

# Attributes used in sensor.py
ATTR_CPU_MODEL: Final = "cpu_model"
ATTR_CPU_CORES: Final = "cpu_cores"
ATTR_CPU_THREADS: Final = "cpu_threads"
ATTR_RAM_TOTAL: Final = "ram_total"
ATTR_SERVER_MODEL: Final = "server_model"
ATTR_ARRAY_STATE: Final = "array_state"
ATTR_NUM_DISKS: Final = "num_disks"
ATTR_NUM_DATA_DISKS: Final = "num_data_disks"
ATTR_NUM_PARITY_DISKS: Final = "num_parity_disks"
ATTR_GPU_NAME: Final = "gpu_name"
ATTR_GPU_DRIVER_VERSION: Final = "gpu_driver_version"
ATTR_NETWORK_MAC: Final = "network_mac"
ATTR_NETWORK_IP: Final = "network_ip"
ATTR_NETWORK_SPEED: Final = "network_speed"
ATTR_UPS_STATUS: Final = "ups_status"
ATTR_UPS_MODEL: Final = "ups_model"

# Attributes used in binary_sensor.py
ATTR_PARITY_CHECK_STATUS: Final = "parity_check_status"

# Attributes used in switch.py
ATTR_CONTAINER_IMAGE: Final = "container_image"
ATTR_CONTAINER_PORTS: Final = "container_ports"
ATTR_VM_VCPUS: Final = "vm_vcpus"
ATTR_VM_MEMORY: Final = "vm_memory"

# Error messages used in config_flow.py
ERROR_CANNOT_CONNECT: Final = "cannot_connect"
ERROR_UNKNOWN: Final = "unknown"
ERROR_TIMEOUT: Final = "timeout"
