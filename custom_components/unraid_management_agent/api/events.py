"""
WebSocket event models and parsing utilities.

This module provides Pydantic models for WebSocket events and automatic
event type detection based on data structure.

Example:
    >>> from custom_components.unraid_management_agent.api.events import parse_event, SystemUpdateEvent
    >>>
    >>> # Parse raw WebSocket data
    >>> event = parse_event(raw_data)
    >>>
    >>> # Use with match statement
    >>> match event:
    ...     case SystemUpdateEvent(data=system_info):
    ...         print(f"System update: {system_info.hostname}")
    ...     case ContainerListUpdateEvent(data=containers):
    ...         for c in containers:
    ...             print(f"Container: {c.name}")

"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .constants import EventType
from .models import (
    ArrayStatus,
    CollectorDetails,
    ContainerInfo,
    DiskInfo,
    GPUInfo,
    HardwareFullInfo,
    NetworkInterface,
    Notification,
    NotificationsResponse,
    NUTInfo,
    ShareInfo,
    SystemInfo,
    UPSInfo,
    VMInfo,
    ZFSArcStats,
    ZFSDataset,
    ZFSPool,
    ZFSSnapshot,
)


class WebSocketEvent(BaseModel):
    """
    Base class for WebSocket events.

    All event types inherit from this class and provide:
    - event_type: The type of event (from EventType enum)
    - data: The parsed event data as a Pydantic model or list of models
    """

    event_type: EventType | None = None
    data: Any = None

    model_config = {"frozen": True}


class SystemUpdateEvent(WebSocketEvent):
    """System information update event."""

    event_type: EventType = EventType.SYSTEM_UPDATE
    data: SystemInfo


class ArrayStatusUpdateEvent(WebSocketEvent):
    """Array status update event."""

    event_type: EventType = EventType.ARRAY_STATUS_UPDATE
    data: ArrayStatus


class DiskListUpdateEvent(WebSocketEvent):
    """Disk list update event."""

    event_type: EventType = EventType.DISK_LIST_UPDATE
    data: list[DiskInfo]


class ContainerListUpdateEvent(WebSocketEvent):
    """Container list update event."""

    event_type: EventType = EventType.CONTAINER_LIST_UPDATE
    data: list[ContainerInfo]


class VMListUpdateEvent(WebSocketEvent):
    """VM list update event."""

    event_type: EventType = EventType.VM_LIST_UPDATE
    data: list[VMInfo]


class NetworkListUpdateEvent(WebSocketEvent):
    """Network interface list update event."""

    event_type: EventType = EventType.NETWORK_LIST_UPDATE
    data: list[NetworkInterface]


class ShareListUpdateEvent(WebSocketEvent):
    """Share list update event."""

    event_type: EventType = EventType.SHARE_LIST_UPDATE
    data: list[ShareInfo]


class UPSStatusUpdateEvent(WebSocketEvent):
    """UPS status update event."""

    event_type: EventType = EventType.UPS_STATUS_UPDATE
    data: UPSInfo


class GPUUpdateEvent(WebSocketEvent):
    """GPU update event."""

    event_type: EventType = EventType.GPU_UPDATE
    data: list[GPUInfo]


class NotificationUpdateEvent(WebSocketEvent):
    """Notification update event."""

    event_type: EventType = EventType.NOTIFICATION_UPDATE
    data: list[Notification]


class ZFSPoolUpdateEvent(WebSocketEvent):
    """ZFS pool update event."""

    event_type: EventType = EventType.ZFS_POOL_UPDATE
    data: list[ZFSPool]


class ZFSDatasetUpdateEvent(WebSocketEvent):
    """ZFS dataset update event."""

    event_type: EventType = EventType.ZFS_DATASET_UPDATE
    data: list[ZFSDataset]


class ZFSSnapshotUpdateEvent(WebSocketEvent):
    """ZFS snapshot update event."""

    event_type: EventType = EventType.ZFS_SNAPSHOT_UPDATE
    data: list[ZFSSnapshot]


class ZFSArcUpdateEvent(WebSocketEvent):
    """ZFS ARC statistics update event."""

    event_type: EventType = EventType.ZFS_ARC_UPDATE
    data: ZFSArcStats


class NUTStatusUpdateEvent(WebSocketEvent):
    """NUT (Network UPS Tools) status update event."""

    event_type: EventType = EventType.NUT_STATUS_UPDATE
    data: NUTInfo


class HardwareUpdateEvent(WebSocketEvent):
    """Hardware DMI data update event."""

    event_type: EventType = EventType.HARDWARE_UPDATE
    data: HardwareFullInfo


class CollectorStateChangeEvent(WebSocketEvent):
    """Collector state change event (enabled/disabled/interval changed)."""

    event_type: EventType = EventType.COLLECTOR_STATE_CHANGE
    data: CollectorDetails


class NotificationsResponseEvent(WebSocketEvent):
    """Full notifications response event (overview + notification list)."""

    event_type: EventType = EventType.NOTIFICATIONS_RESPONSE
    data: NotificationsResponse


class UnknownEvent(WebSocketEvent):
    """Unknown event type - data structure not recognized."""

    event_type: None = None
    data: Any = None


def identify_event_type(data: Any) -> EventType | None:
    """
    Identify the event type from data structure.

    Since the WebSocket server doesn't send a 'type' field, events must
    be identified by inspecting the data structure.

    Args:
        data: Raw event data (dict or list)

    Returns:
        The identified EventType or None if unknown

    Example:
        >>> data = {"hostname": "unraid", "cpu_usage_percent": 25.5}
        >>> identify_event_type(data)
        <EventType.SYSTEM_UPDATE: 'system_update'>

    """
    if isinstance(data, list):
        if not data:
            return None

        first_item = data[0]
        if not isinstance(first_item, dict):
            return None

        # Check list item structure for identification
        # Disk list: has 'device' and 'filesystem'
        if "device" in first_item and "filesystem" in first_item:
            return EventType.DISK_LIST_UPDATE

        # Container list: has 'image'
        if "image" in first_item:
            return EventType.CONTAINER_LIST_UPDATE

        # VM list: has 'cpu_count' and 'memory_bytes'
        if "cpu_count" in first_item and "memory_bytes" in first_item:
            return EventType.VM_LIST_UPDATE

        # Network list: has 'mac_address' and 'ip_address'
        if "mac_address" in first_item and "ip_address" in first_item:
            return EventType.NETWORK_LIST_UPDATE

        # Share list: has 'path' and name (but not mac_address)
        if (
            "path" in first_item
            and "name" in first_item
            and "mac_address" not in first_item
        ):
            return EventType.SHARE_LIST_UPDATE

        # GPU list: has 'vendor' and 'utilization_percent'
        if "vendor" in first_item and "utilization_percent" in first_item:
            return EventType.GPU_UPDATE

        # Notification list: has 'importance' and 'subject'
        if "importance" in first_item and "subject" in first_item:
            return EventType.NOTIFICATION_UPDATE

        # ZFS pool: has 'health' and 'name' (but not 'mountpoint' or 'dataset')
        if "health" in first_item and "name" in first_item:
            return EventType.ZFS_POOL_UPDATE

        # ZFS dataset: has 'mountpoint' and 'pool'
        if "mountpoint" in first_item and "pool" in first_item:
            return EventType.ZFS_DATASET_UPDATE

        # ZFS snapshot: has 'dataset' and 'creation'
        if "dataset" in first_item and "creation" in first_item:
            return EventType.ZFS_SNAPSHOT_UPDATE

        return None

    if isinstance(data, dict):
        # System update: has 'hostname' and cpu-related fields
        if "hostname" in data and "cpu_usage_percent" in data:
            return EventType.SYSTEM_UPDATE

        # Array status: has 'state' and 'total_disks'
        if "state" in data and "total_disks" in data:
            return EventType.ARRAY_STATUS_UPDATE

        # UPS status: has 'battery_charge_percent' and 'load_percent'
        if "battery_charge_percent" in data and "load_percent" in data:
            return EventType.UPS_STATUS_UPDATE

        # ZFS ARC: has 'hit_ratio_percent' and 'size_bytes'
        if "hit_ratio_percent" in data and "size_bytes" in data:
            return EventType.ZFS_ARC_UPDATE

        # NUT: has 'installed' and 'running' and 'config_mode'
        if "installed" in data and "running" in data and "config_mode" in data:
            return EventType.NUT_STATUS_UPDATE

        # Hardware: has 'bios' and 'baseboard' keys
        if "bios" in data and "baseboard" in data:
            return EventType.HARDWARE_UPDATE

        # Collector state change: has 'name' and 'enabled' and 'interval_seconds'
        if "name" in data and "enabled" in data and "interval_seconds" in data:
            return EventType.COLLECTOR_STATE_CHANGE

        # Notifications response: has 'overview' key (and optionally 'notifications')
        if "overview" in data and ("notifications" in data or "timestamp" in data):
            return EventType.NOTIFICATIONS_RESPONSE

        return None

    return None


def parse_event(data: Any) -> WebSocketEvent:
    """
    Parse raw WebSocket data into a typed event.

    This function identifies the event type and returns the appropriate
    event class with parsed Pydantic models.

    Args:
        data: Raw event data from WebSocket (dict or list)

    Returns:
        A WebSocketEvent subclass instance with parsed data

    Example:
        >>> data = {"hostname": "unraid", "cpu_usage_percent": 25.5}
        >>> event = parse_event(data)
        >>> isinstance(event, SystemUpdateEvent)
        True
        >>> event.data.hostname
        'unraid'

    """
    event_type = identify_event_type(data)

    if event_type is None:
        return UnknownEvent(data=data)

    match event_type:
        case EventType.SYSTEM_UPDATE:
            return SystemUpdateEvent(data=SystemInfo.model_validate(data))

        case EventType.ARRAY_STATUS_UPDATE:
            return ArrayStatusUpdateEvent(data=ArrayStatus.model_validate(data))

        case EventType.DISK_LIST_UPDATE:
            disks = [DiskInfo.model_validate(d) for d in data]
            return DiskListUpdateEvent(data=disks)

        case EventType.CONTAINER_LIST_UPDATE:
            containers = [ContainerInfo.model_validate(c) for c in data]
            return ContainerListUpdateEvent(data=containers)

        case EventType.VM_LIST_UPDATE:
            vms = [VMInfo.model_validate(v) for v in data]
            return VMListUpdateEvent(data=vms)

        case EventType.NETWORK_LIST_UPDATE:
            interfaces = [NetworkInterface.model_validate(n) for n in data]
            return NetworkListUpdateEvent(data=interfaces)

        case EventType.SHARE_LIST_UPDATE:
            shares = [ShareInfo.model_validate(s) for s in data]
            return ShareListUpdateEvent(data=shares)

        case EventType.UPS_STATUS_UPDATE:
            return UPSStatusUpdateEvent(data=UPSInfo.model_validate(data))

        case EventType.GPU_UPDATE:
            gpus = [GPUInfo.model_validate(g) for g in data]
            return GPUUpdateEvent(data=gpus)

        case EventType.NOTIFICATION_UPDATE:
            notifications = [Notification.model_validate(n) for n in data]
            return NotificationUpdateEvent(data=notifications)

        case EventType.ZFS_POOL_UPDATE:
            pools = [ZFSPool.model_validate(p) for p in data]
            return ZFSPoolUpdateEvent(data=pools)

        case EventType.ZFS_DATASET_UPDATE:
            datasets = [ZFSDataset.model_validate(d) for d in data]
            return ZFSDatasetUpdateEvent(data=datasets)

        case EventType.ZFS_SNAPSHOT_UPDATE:
            snapshots = [ZFSSnapshot.model_validate(s) for s in data]
            return ZFSSnapshotUpdateEvent(data=snapshots)

        case EventType.ZFS_ARC_UPDATE:
            return ZFSArcUpdateEvent(data=ZFSArcStats.model_validate(data))

        case EventType.NUT_STATUS_UPDATE:
            return NUTStatusUpdateEvent(data=NUTInfo.model_validate(data))

        case EventType.HARDWARE_UPDATE:
            return HardwareUpdateEvent(data=HardwareFullInfo.model_validate(data))

        case EventType.COLLECTOR_STATE_CHANGE:
            return CollectorStateChangeEvent(data=CollectorDetails.model_validate(data))

        case EventType.NOTIFICATIONS_RESPONSE:
            return NotificationsResponseEvent(
                data=NotificationsResponse.model_validate(data)
            )

        case _:
            return UnknownEvent(data=data)  # type: ignore[unreachable]
