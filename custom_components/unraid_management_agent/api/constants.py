"""
Constants and enums for the Uma API client.

This module provides type-safe enums for event types and entity states,
eliminating the need for consumers to define their own string constants.

Example:
    >>> from custom_components.unraid_management_agent.api.constants import EventType, ContainerState, ArrayState
    >>>
    >>> # Use in event handling
    >>> if event_type == EventType.SYSTEM_UPDATE:
    ...     handle_system_update()
    >>>
    >>> # Use in state comparisons
    >>> if container.state == ContainerState.RUNNING:
    ...     print("Container is running")
    >>>
    >>> if array.state == ArrayState.STARTED:
    ...     print("Array is started")

"""

from enum import StrEnum


class EventType(StrEnum):
    """
    WebSocket event types.

    These are the event types that can be received from the WebSocket
    connection. Use these instead of raw strings to avoid typos.

    Example:
        >>> if event_type == EventType.SYSTEM_UPDATE:
        ...     handle_system_update(data)

    """

    SYSTEM_UPDATE = "system_update"
    ARRAY_STATUS_UPDATE = "array_status_update"
    DISK_LIST_UPDATE = "disk_list_update"
    CONTAINER_LIST_UPDATE = "container_list_update"
    VM_LIST_UPDATE = "vm_list_update"
    NETWORK_LIST_UPDATE = "network_list_update"
    SHARE_LIST_UPDATE = "share_list_update"
    UPS_STATUS_UPDATE = "ups_status_update"
    GPU_UPDATE = "gpu_update"
    NOTIFICATION_UPDATE = "notification_update"
    ZFS_POOL_UPDATE = "zfs_pool_update"
    ZFS_DATASET_UPDATE = "zfs_dataset_update"
    ZFS_SNAPSHOT_UPDATE = "zfs_snapshot_update"
    ZFS_ARC_UPDATE = "zfs_arc_update"
    NUT_STATUS_UPDATE = "nut_status_update"
    HARDWARE_UPDATE = "hardware_update"
    COLLECTOR_STATE_CHANGE = "collector_state_change"
    NOTIFICATIONS_RESPONSE = "notifications_response"


class ArrayState(StrEnum):
    """
    Unraid array states.

    Example:
        >>> if array.state == ArrayState.STARTED:
        ...     print("Array is online")

    """

    STARTED = "Started"
    STOPPED = "Stopped"
    STARTING = "Starting"
    STOPPING = "Stopping"
    MAINTENANCE = "Maintenance"


class ContainerState(StrEnum):
    """
    Docker container states.

    Example:
        >>> if container.state == ContainerState.RUNNING:
        ...     print("Container is running")

    """

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    CREATED = "created"
    EXITED = "exited"


class VMState(StrEnum):
    """
    Virtual machine states.

    Example:
        >>> if vm.state == VMState.RUNNING:
        ...     print("VM is running")

    """

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    PMSUSPENDED = "pmsuspended"
    SHUTOFF = "shutoff"


class DiskStatus(StrEnum):
    """
    Disk status values.

    Example:
        >>> if disk.status == DiskStatus.NORMAL:
        ...     print("Disk is healthy")

    """

    NORMAL = "Normal"
    DISABLED = "Disabled"
    STANDBY = "Standby"
    ABSENT = "Absent"


class DiskSpinState(StrEnum):
    """
    Disk spin states.

    Example:
        >>> if disk.spin_state == DiskSpinState.ACTIVE:
        ...     print("Disk is spinning")

    """

    ACTIVE = "active"
    STANDBY = "standby"
    UNKNOWN = "unknown"


class TemperatureStatus(StrEnum):
    """
    Temperature status levels for disk health evaluation.

    Example:
        >>> if disk.temperature_status() == TemperatureStatus.CRITICAL:
        ...     send_alert()

    """

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
