"""Constants for the Unraid Management Agent integration."""

from datetime import timedelta
from typing import Final

# Integration domain
DOMAIN: Final = "unraid_management_agent"

# Configuration keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_ENABLE_WEBSOCKET: Final = "enable_websocket"

# Default values
DEFAULT_PORT: Final = 8043
DEFAULT_UPDATE_INTERVAL: Final = 30  # seconds
DEFAULT_ENABLE_WEBSOCKET: Final = True

# Update intervals
UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_UPDATE_INTERVAL)

# Sensor types
SENSOR_CPU_USAGE: Final = "cpu_usage"
SENSOR_RAM_USAGE: Final = "ram_usage"
SENSOR_CPU_TEMP: Final = "cpu_temperature"
SENSOR_UPTIME: Final = "uptime"
SENSOR_ARRAY_USAGE: Final = "array_usage"
SENSOR_PARITY_PROGRESS: Final = "parity_progress"
SENSOR_GPU_NAME: Final = "gpu_name"
SENSOR_GPU_UTILIZATION: Final = "gpu_utilization"
SENSOR_GPU_CPU_TEMP: Final = "gpu_cpu_temperature"
SENSOR_GPU_POWER: Final = "gpu_power"
SENSOR_UPS_BATTERY: Final = "ups_battery"
SENSOR_UPS_LOAD: Final = "ups_load"
SENSOR_UPS_RUNTIME: Final = "ups_runtime"

# Binary sensor types
BINARY_SENSOR_ARRAY_STARTED: Final = "array_started"
BINARY_SENSOR_PARITY_CHECK_RUNNING: Final = "parity_check_running"
BINARY_SENSOR_PARITY_VALID: Final = "parity_valid"
BINARY_SENSOR_UPS_CONNECTED: Final = "ups_connected"
BINARY_SENSOR_CONTAINER_RUNNING: Final = "container_running"
BINARY_SENSOR_VM_RUNNING: Final = "vm_running"
BINARY_SENSOR_NETWORK_UP: Final = "network_up"

# Switch types
SWITCH_CONTAINER: Final = "container"
SWITCH_VM: Final = "vm"

# Button types
BUTTON_ARRAY_START: Final = "array_start"
BUTTON_ARRAY_STOP: Final = "array_stop"
BUTTON_PARITY_CHECK_START: Final = "parity_check_start"
BUTTON_PARITY_CHECK_STOP: Final = "parity_check_stop"
BUTTON_CONTAINER_RESTART: Final = "container_restart"

# Device info
MANUFACTURER: Final = "Lime Technology"
MODEL: Final = "Unraid Server"

# Attributes
ATTR_HOSTNAME: Final = "hostname"
ATTR_VERSION: Final = "version"
ATTR_CPU_MODEL: Final = "cpu_model"
ATTR_CPU_CORES: Final = "cpu_cores"
ATTR_CPU_THREADS: Final = "cpu_threads"
ATTR_RAM_TOTAL: Final = "ram_total"
ATTR_SERVER_MODEL: Final = "server_model"
ATTR_BIOS_VERSION: Final = "bios_version"
ATTR_ARRAY_STATE: Final = "array_state"
ATTR_NUM_DISKS: Final = "num_disks"
ATTR_NUM_DATA_DISKS: Final = "num_data_disks"
ATTR_NUM_PARITY_DISKS: Final = "num_parity_disks"
ATTR_CONTAINER_ID: Final = "container_id"
ATTR_CONTAINER_IMAGE: Final = "container_image"
ATTR_CONTAINER_STATUS: Final = "container_status"
ATTR_CONTAINER_PORTS: Final = "container_ports"
ATTR_PARITY_CHECK_STATUS: Final = "parity_check_status"
ATTR_VM_ID: Final = "vm_id"
ATTR_VM_VCPUS: Final = "vm_vcpus"
ATTR_VM_MEMORY: Final = "vm_memory"
ATTR_GPU_NAME: Final = "gpu_name"
ATTR_GPU_DRIVER_VERSION: Final = "gpu_driver_version"
ATTR_NETWORK_MAC: Final = "network_mac"
ATTR_NETWORK_IP: Final = "network_ip"
ATTR_NETWORK_SPEED: Final = "network_speed"
ATTR_UPS_STATUS: Final = "ups_status"
ATTR_UPS_MODEL: Final = "ups_model"

# Error messages
ERROR_CANNOT_CONNECT: Final = "cannot_connect"
ERROR_INVALID_AUTH: Final = "invalid_auth"
ERROR_UNKNOWN: Final = "unknown"
ERROR_TIMEOUT: Final = "timeout"
ERROR_ALREADY_CONFIGURED: Final = "already_configured"
ERROR_CONTROL_FAILED: Final = "control_failed"

# Service names
SERVICE_CONTAINER_START: Final = "container_start"
SERVICE_CONTAINER_STOP: Final = "container_stop"
SERVICE_CONTAINER_RESTART: Final = "container_restart"
SERVICE_VM_START: Final = "vm_start"
SERVICE_VM_STOP: Final = "vm_stop"
SERVICE_VM_RESTART: Final = "vm_restart"
SERVICE_ARRAY_START: Final = "array_start"
SERVICE_ARRAY_STOP: Final = "array_stop"
SERVICE_PARITY_CHECK_START: Final = "parity_check_start"
SERVICE_PARITY_CHECK_STOP: Final = "parity_check_stop"
