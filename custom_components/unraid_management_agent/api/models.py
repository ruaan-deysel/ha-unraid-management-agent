"""Pydantic models for the Uma API client."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, model_validator


def _coerce_float(v: Any) -> Any:
    """Coerce string or numeric values to float, returning None for unparsable values."""
    if v is None:
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        v = v.strip()
        if v == "" or v == "-":
            return None
        try:
            return float(v)
        except ValueError:
            return None
    return v


def _coerce_int(v: Any) -> Any:
    """Coerce string or numeric values to int, returning None for unparsable values."""
    if v is None:
        return None
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        v = v.strip()
        if v == "" or v == "-":
            return None
        try:
            return int(float(v))
        except ValueError:
            return None
    return v


CoercedFloat = Annotated[float | None, BeforeValidator(_coerce_float)]
CoercedInt = Annotated[int | None, BeforeValidator(_coerce_int)]


class FanInfo(BaseModel):
    """Fan information from sensors."""

    name: str | None = Field(None, description="Fan name", examples=["CPU Fan"])
    rpm: int | None = Field(None, description="Fan speed in RPM", examples=[1200])

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def normalized_name(self) -> str | None:
        """
        Return a human-friendly fan name, stripping hwmon/chip prefixes.

        Converts names like 'hwmon2/fan1' or 'hwmon4_fan5' to 'fan1'/'fan5',
        and 'it8688/fan3' to 'fan3'.

        Returns:
            Cleaned fan name without sensor chip prefixes, or None if name is None.

        Example:
            >>> fan = FanInfo(name="hwmon2/fan1", rpm=1200)
            >>> fan.normalized_name
            'fan1'
            >>> fan2 = FanInfo(name="hwmon4_fan5", rpm=800)
            >>> fan2.normalized_name
            'fan5'

        """
        if self.name is None:
            return None
        # Strip hwmon/chip prefixes like 'hwmon2/', 'it8688/', 'hwmon4_'
        # Handle slash-separated: 'hwmon2/fan1' -> 'fan1'
        parts = self.name.split("/")
        if len(parts) > 1:
            return parts[-1]
        # Handle underscore-separated: 'hwmon4_fan5' -> 'fan5'
        match = re.match(r"^(?:hwmon\d+|it\d+)_(.+)$", self.name, re.IGNORECASE)
        if match:
            return match.group(1)
        return self.name


class SystemInfo(BaseModel):
    """System information response from the Unraid server."""

    # Basic info
    hostname: str | None = Field(None, description="Server hostname")
    version: str | None = Field(None, description="Unraid version")
    agent_version: str | None = Field(None, description="Agent version")
    uptime_seconds: CoercedInt = Field(None, description="System uptime in seconds")

    # CPU Information
    cpu_usage_percent: CoercedFloat = Field(None, description="CPU usage percentage")
    cpu_model: str | None = Field(None, description="CPU model name")
    cpu_cores: CoercedInt = Field(None, description="Number of CPU cores")
    cpu_threads: CoercedInt = Field(None, description="Number of CPU threads")
    cpu_mhz: CoercedFloat = Field(None, description="CPU frequency in MHz")
    cpu_per_core_usage: dict[str, float] | None = Field(
        None, description="Per-core CPU usage"
    )
    cpu_temp_celsius: CoercedFloat = Field(
        None, description="CPU temperature in Celsius"
    )

    # Memory Information
    ram_usage_percent: CoercedFloat = Field(None, description="RAM usage percentage")
    ram_total_bytes: CoercedInt = Field(None, description="Total RAM in bytes")
    ram_used_bytes: CoercedInt = Field(None, description="Used RAM in bytes")
    ram_free_bytes: CoercedInt = Field(None, description="Free RAM in bytes")
    ram_buffers_bytes: CoercedInt = Field(None, description="RAM buffers in bytes")
    ram_cached_bytes: CoercedInt = Field(None, description="Cached RAM in bytes")

    # System Information
    server_model: str | None = Field(None, description="Server model")
    motherboard_model: str | None = Field(None, description="Motherboard model")
    bios_version: str | None = Field(None, description="BIOS version")
    bios_date: str | None = Field(None, description="BIOS date")

    # Additional System Information
    openssl_version: str | None = Field(None, description="OpenSSL version")
    kernel_version: str | None = Field(None, description="Kernel version")

    # Virtualization Features
    hvm_enabled: bool | None = Field(
        None, description="Hardware virtualization (HVM) enabled"
    )
    iommu_enabled: bool | None = Field(None, description="IOMMU enabled")

    # Power Information
    cpu_power_watts: CoercedFloat = Field(
        None, description="CPU power consumption in watts"
    )
    dram_power_watts: CoercedFloat = Field(
        None, description="DRAM power consumption in watts"
    )

    # Additional Metrics
    fans: list[FanInfo] | None = Field(None, description="Fan information")
    motherboard_temp_celsius: CoercedFloat = Field(
        None, description="Motherboard temperature in Celsius"
    )
    parity_check_speed: str | None = Field(None, description="Parity check speed")

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _correct_cpu_cores(cls, data: Any) -> Any:
        """
        Correct cpu_cores when per_core_usage has more entries than cpu_cores.

        Some systems report physical cores in cpu_cores but provide usage data
        for logical cores (including hyperthreading) in cpu_per_core_usage.
        """
        if isinstance(data, dict):
            per_core = data.get("cpu_per_core_usage")
            cores = data.get("cpu_cores")
            if per_core and isinstance(per_core, dict) and cores is not None:
                try:
                    core_count = int(cores) if not isinstance(cores, int) else cores
                    if len(per_core) > core_count:
                        data = dict(data)
                        data["cpu_cores"] = len(per_core)
                except ValueError, TypeError:
                    pass
        return data

    @property
    def uptime_days(self) -> int | None:
        """
        Return uptime in whole days.

        Returns:
            Number of complete days of uptime, or None if uptime_seconds is None.

        Example:
            >>> info = SystemInfo(uptime_seconds=90061)
            >>> info.uptime_days
            1

        """
        if self.uptime_seconds is None:
            return None
        return self.uptime_seconds // 86400

    @property
    def uptime_hours(self) -> int | None:
        """
        Return the hours component of uptime (0-23).

        Returns:
            Hours component after removing full days, or None if uptime_seconds is None.

        Example:
            >>> info = SystemInfo(uptime_seconds=90061)
            >>> info.uptime_hours
            1

        """
        if self.uptime_seconds is None:
            return None
        return (self.uptime_seconds % 86400) // 3600

    @property
    def uptime_minutes(self) -> int | None:
        """
        Return the minutes component of uptime (0-59).

        Returns:
            Minutes component after removing full hours, or None if uptime_seconds is None.

        Example:
            >>> info = SystemInfo(uptime_seconds=90061)
            >>> info.uptime_minutes
            1

        """
        if self.uptime_seconds is None:
            return None
        return (self.uptime_seconds % 3600) // 60


ArrayState = Literal["STARTED", "STOPPED", "STARTING", "STOPPING", "Started", "Stopped"]


class ArrayStatus(BaseModel):
    """Array status response."""

    state: ArrayState | str | None = Field(None, description="Array state")

    # Disk counts (API uses num_disks, num_data_disks, num_parity_disks)
    num_disks: CoercedInt = Field(None, description="Total number of disks")
    num_data_disks: CoercedInt = Field(None, description="Number of data disks")
    num_parity_disks: CoercedInt = Field(None, description="Number of parity disks")

    # Capacity (API uses total_bytes, not size_bytes)
    total_bytes: CoercedInt = Field(None, description="Total array size in bytes")
    used_bytes: CoercedInt = Field(None, description="Used space in bytes")
    free_bytes: CoercedInt = Field(None, description="Free space in bytes")

    # Usage (API uses used_percent, not usage_percent)
    used_percent: CoercedFloat = Field(None, description="Array usage percentage")

    # Parity information
    parity_valid: bool | None = Field(None, description="Whether parity is valid")
    parity_check_status: str | None = Field(
        None, description="Parity check status (e.g., 'idle', 'running')"
    )
    parity_check_progress: CoercedFloat = Field(
        None, description="Parity check progress percentage"
    )

    # Sync/parity operation fields (Issue #59)
    sync_action: str | None = Field(
        None,
        description="Current sync action type (e.g., 'Parity-Check', 'Parity-Sync', 'Rebuild')",
    )
    sync_errors: CoercedInt = Field(
        None, description="Number of errors found during sync"
    )
    sync_speed: str | None = Field(
        None, description="Current sync speed (e.g., '150.0 MB/s')"
    )
    sync_eta: str | None = Field(
        None, description="Estimated time remaining for sync operation"
    )

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def computed_used_percent(self) -> float | None:
        """
        Calculate used percentage from total_bytes and used_bytes.

        Falls back to the API-provided used_percent if available,
        otherwise computes from raw byte values.

        Returns:
            Usage percentage (0-100), or None if insufficient data.

        Example:
            >>> status = ArrayStatus(total_bytes=1000, used_bytes=250)
            >>> status.computed_used_percent
            25.0

        """
        if self.used_percent is not None:
            return self.used_percent
        if self.total_bytes and self.used_bytes is not None and self.total_bytes > 0:
            return round((self.used_bytes / self.total_bytes) * 100, 1)
        return None

    @property
    def is_parity_check_running(self) -> bool:
        """
        Check if a parity check is currently running.

        Returns:
            True if parity check status indicates running or checking.

        Example:
            >>> status = ArrayStatus(parity_check_status="running")
            >>> status.is_parity_check_running
            True

        """
        if self.parity_check_status is None:
            return False
        return self.parity_check_status.lower() in (
            "running",
            "checking",
            "in progress",
        )

    @property
    def is_parity_check_stuck(self) -> bool:
        """
        Check if a parity check appears stuck (progress >= 95% but not complete).

        A parity check near completion (95-99%) that hasn't finished may indicate
        a stuck operation. For full stuck detection with time-based tracking,
        external monitoring would be needed.

        Returns:
            True if parity check is running and progress is between 95% and 100%.

        Example:
            >>> status = ArrayStatus(parity_check_status="running", parity_check_progress=97.0)
            >>> status.is_parity_check_stuck
            True
            >>> status2 = ArrayStatus(parity_check_status="running", parity_check_progress=50.0)
            >>> status2.is_parity_check_stuck
            False

        """
        if not self.is_parity_check_running:
            return False
        if self.parity_check_progress is not None:
            return 95.0 <= self.parity_check_progress < 100.0
        return False

    @property
    def sync_percent(self) -> float | None:
        """
        Get sync progress percentage (alias for parity_check_progress).

        Provides compatibility for consumers that expect a sync_percent field.

        Returns:
            Sync progress percentage, or None if not available.

        Example:
            >>> status = ArrayStatus(parity_check_progress=45.5)
            >>> status.sync_percent
            45.5

        """
        return self.parity_check_progress


DiskRole = Literal["parity", "parity2", "data", "cache", "pool", "docker_vdisk", "log"]
SpinState = Literal["active", "standby", "idle", "unknown"]


class SMARTAttribute(BaseModel):
    """SMART attribute information."""

    id: int | None = Field(None, description="Attribute ID")
    name: str | None = Field(None, description="Attribute name")
    value: int | None = Field(None, description="Current value")
    worst: int | None = Field(None, description="Worst recorded value")
    threshold: int | None = Field(None, description="Threshold value")
    raw_value: str | None = Field(None, description="Raw value")
    when_failed: str | None = Field(None, description="When the attribute failed")

    model_config = {"frozen": True, "extra": "allow"}


class DiskInfo(BaseModel):
    """Disk information response."""

    # Disk identification
    id: str | None = Field(None, description="Disk identifier")
    device: str | None = Field(None, description="Device path")
    name: str | None = Field(None, description="Disk name")
    serial_number: str | None = Field(None, description="Disk serial number")
    model: str | None = Field(None, description="Disk model")
    role: str | None = Field(None, description="Disk role (parity, data, cache, pool)")

    # Capacity
    size_bytes: CoercedInt = Field(None, description="Disk size in bytes")
    used_bytes: CoercedInt = Field(None, description="Used space in bytes")
    free_bytes: CoercedInt = Field(None, description="Free space in bytes")
    usage_percent: CoercedFloat = Field(None, description="Usage percentage")

    # Mount information
    mount_point: str | None = Field(None, description="Mount point")
    filesystem: str | None = Field(None, description="Filesystem type")

    # State and temperature
    temperature_celsius: CoercedFloat = Field(
        None, description="Disk temperature in Celsius"
    )
    temp_warning: CoercedInt = Field(
        None,
        description="Per-disk warning temperature threshold (null = use global default)",
    )
    temp_critical: CoercedInt = Field(
        None,
        description="Per-disk critical temperature threshold (null = use global default)",
    )
    spin_state: str | None = Field(
        None, description="Disk spin state (active, standby, unknown)"
    )
    spindown_delay: CoercedInt = Field(None, description="Spindown delay in minutes")
    status: str | None = Field(None, description="Disk status")

    # SMART information
    smart_status: str | None = Field(None, description="SMART status (PASSED, FAILED)")
    smart_errors: CoercedInt = Field(None, description="Number of SMART errors")
    smart_attributes: dict[str, SMARTAttribute] | None = Field(
        None, description="Enhanced SMART attributes"
    )

    # Power information
    power_on_hours: CoercedInt = Field(None, description="Power on hours")
    power_cycle_count: CoercedInt = Field(None, description="Power cycle count")

    # I/O Statistics
    read_bytes: CoercedInt = Field(None, description="Total bytes read")
    write_bytes: CoercedInt = Field(None, description="Total bytes written")
    read_ops: CoercedInt = Field(None, description="Total read operations")
    write_ops: CoercedInt = Field(None, description="Total write operations")
    io_utilization_percent: CoercedFloat = Field(
        None, description="I/O utilization percentage"
    )

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def computed_used_percent(self) -> float | None:
        """
        Calculate used percentage from size_bytes and used_bytes.

        Falls back to the API-provided usage_percent if available,
        otherwise computes from raw byte values.

        Returns:
            Usage percentage (0-100), or None if insufficient data.

        Example:
            >>> disk = DiskInfo(size_bytes=1000, used_bytes=250)
            >>> disk.computed_used_percent
            25.0

        """
        if self.usage_percent is not None:
            return self.usage_percent
        if self.size_bytes and self.used_bytes is not None and self.size_bytes > 0:
            return round((self.used_bytes / self.size_bytes) * 100, 1)
        return None

    @property
    def is_physical(self) -> bool:
        """
        Check if this is a physical disk (not a virtual disk).

        Returns:
            True if the disk role is not docker_vdisk or log.

        Example:
            >>> disk = DiskInfo(role="data")
            >>> disk.is_physical
            True

        """
        if self.role is None:
            return True
        return self.role.lower() not in ("docker_vdisk", "log")

    @property
    def is_ssd(self) -> bool:
        """
        Check if this disk is an SSD or NVMe drive.

        Uses multiple heuristics:
        - Device path contains 'nvme'
        - Model name contains 'ssd' or 'nvme'
        - SMART attribute 'rotation_rate' is '0' (Solid State Device)

        Returns:
            True if the disk appears to be an SSD or NVMe.

        Example:
            >>> disk = DiskInfo(device="/dev/nvme0n1")
            >>> disk.is_ssd
            True

        """
        # Check device path
        if self.device and "nvme" in self.device.lower():
            return True
        # Check model name
        if self.model and any(kw in self.model.lower() for kw in ("ssd", "nvme")):
            return True
        # Check SMART rotation rate attribute
        if self.smart_attributes:
            rotation = self.smart_attributes.get("rotation_rate")
            if rotation and rotation.raw_value == "0":
                return True
        return False

    @property
    def is_standby(self) -> bool:
        """
        Check if the disk is in standby (spun down).

        Returns:
            True if spin_state is 'standby'.

        Example:
            >>> disk = DiskInfo(spin_state="standby")
            >>> disk.is_standby
            True

        """
        if self.spin_state is None:
            return False
        return self.spin_state.lower() == "standby"

    @property
    def has_smart_errors(self) -> bool:
        """
        Check if the disk has any SMART errors.

        Returns:
            True if smart_errors > 0 or smart_status is 'FAILED'.

        Example:
            >>> disk = DiskInfo(smart_errors=2)
            >>> disk.has_smart_errors
            True

        """
        if self.smart_status and self.smart_status.upper() == "FAILED":
            return True
        return self.smart_errors is not None and self.smart_errors > 0

    def get_temp_thresholds(
        self, settings: DiskSettings | None = None
    ) -> tuple[int | None, int | None]:
        """
        Get the effective temperature thresholds for this disk.

        Uses per-disk overrides if set, falls back to global settings
        (SSD or HDD thresholds based on is_ssd), then returns None.

        Args:
            settings: Global disk settings for fallback thresholds.

        Returns:
            Tuple of (warning_threshold, critical_threshold) in Celsius.

        Example:
            >>> disk = DiskInfo(temp_warning=45, temp_critical=55)
            >>> disk.get_temp_thresholds()
            (45, 55)

        """
        warning = self.temp_warning
        critical = self.temp_critical

        if settings is not None:
            if warning is None:
                warning = (
                    settings.ssd_temp_warning_celsius
                    if self.is_ssd
                    else settings.hdd_temp_warning_celsius
                )
            if critical is None:
                critical = (
                    settings.ssd_temp_critical_celsius
                    if self.is_ssd
                    else settings.hdd_temp_critical_celsius
                )

        return (warning, critical)

    def temperature_status(self, settings: DiskSettings | None = None) -> str:
        """
        Get the temperature status based on thresholds.

        Args:
            settings: Global disk settings for fallback thresholds.

        Returns:
            'critical', 'warning', or 'normal' based on current temperature.
            Returns 'normal' if temperature or thresholds are unavailable.

        Example:
            >>> disk = DiskInfo(temperature_celsius=55.0, temp_critical=50)
            >>> disk.temperature_status()
            'critical'

        """
        if self.temperature_celsius is None:
            return "normal"

        warning, critical = self.get_temp_thresholds(settings)

        if critical is not None and self.temperature_celsius >= critical:
            return "critical"
        if warning is not None and self.temperature_celsius >= warning:
            return "warning"
        return "normal"


ContainerState = Literal["running", "stopped", "paused", "created", "exited", "dead"]


class PortMapping(BaseModel):
    """Docker container port mapping."""

    public_port: int | None = Field(None, description="Public (host) port")
    private_port: int | None = Field(None, description="Private (container) port")
    type: str | None = Field(None, description="Protocol type (tcp, udp)")

    model_config = {"frozen": True, "extra": "allow"}


class VolumeMapping(BaseModel):
    """Docker container volume mapping."""

    host_path: str | None = Field(None, description="Host path")
    container_path: str | None = Field(None, description="Container path")
    mode: str | None = Field(None, description="Mount mode (rw, ro)")

    model_config = {"frozen": True, "extra": "allow"}


class ContainerInfo(BaseModel):
    """Docker container information response."""

    # Identification
    id: str | None = Field(None, description="Container ID")
    name: str | None = Field(None, description="Container name")
    image: str | None = Field(None, description="Container image")
    version: str | None = Field(None, description="Container version")

    # State
    state: str | None = Field(None, description="Container state")
    status: str | None = Field(None, description="Container status string")
    uptime: str | None = Field(None, description="Container uptime")

    # Resource usage
    cpu_percent: CoercedFloat = Field(None, description="CPU usage percentage")
    memory_usage_bytes: CoercedInt = Field(None, description="Memory usage in bytes")
    memory_limit_bytes: CoercedInt = Field(None, description="Memory limit in bytes")
    memory_display: str | None = Field(
        None, description="Memory usage display (e.g., '1 GiB')"
    )

    # Network
    network_mode: str | None = Field(
        None, description="Network mode (bridge, host, etc.)"
    )
    ip_address: str | None = Field(None, description="Container IP address")
    network_rx_bytes: CoercedInt = Field(None, description="Network bytes received")
    network_tx_bytes: CoercedInt = Field(None, description="Network bytes transmitted")

    # Port and volume mappings
    ports: list[PortMapping] | None = Field(None, description="Port mappings")
    port_mappings: list[str] | None = Field(
        None, description="Port mappings as strings"
    )
    volume_mappings: list[VolumeMapping] | None = Field(
        None, description="Volume mappings"
    )

    # Configuration
    restart_policy: str | None = Field(None, description="Restart policy")

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


VMState = Literal["running", "stopped", "paused", "shut off", "crashed", "suspended"]


class VMInfo(BaseModel):
    """Virtual machine information response."""

    # Identification
    id: str | None = Field(None, description="VM ID")
    name: str | None = Field(None, description="VM name")
    state: str | None = Field(None, description="VM state")

    # CPU
    cpu_count: CoercedInt = Field(None, description="Number of CPUs")
    guest_cpu_percent: CoercedFloat = Field(
        None, description="Guest CPU usage percentage"
    )
    host_cpu_percent: CoercedFloat = Field(
        None, description="Host CPU usage percentage"
    )

    # Memory (API uses memory_allocated_bytes and memory_used_bytes)
    memory_allocated_bytes: CoercedInt = Field(
        None, description="Memory allocated in bytes"
    )
    memory_used_bytes: CoercedInt = Field(None, description="Memory used in bytes")
    memory_display: str | None = Field(None, description="Memory usage display")

    # Disk
    disk_path: str | None = Field(None, description="VM disk path")
    disk_size_bytes: CoercedInt = Field(None, description="VM disk size in bytes")
    disk_read_bytes: CoercedInt = Field(None, description="Disk bytes read")
    disk_write_bytes: CoercedInt = Field(None, description="Disk bytes written")

    # Network
    network_rx_bytes: CoercedInt = Field(None, description="Network bytes received")
    network_tx_bytes: CoercedInt = Field(None, description="Network bytes transmitted")

    # Configuration
    autostart: bool | None = Field(None, description="VM autostart enabled")
    persistent: bool | None = Field(None, description="VM is persistent")

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ShareInfo(BaseModel):
    """User share information response."""

    name: str | None = Field(None, description="Share name")
    path: str | None = Field(None, description="Share path")

    # Capacity
    total_bytes: CoercedInt = Field(None, description="Total size in bytes")
    used_bytes: CoercedInt = Field(None, description="Used space in bytes")
    free_bytes: CoercedInt = Field(None, description="Free space in bytes")
    usage_percent: CoercedFloat = Field(None, description="Usage percentage")

    # Configuration
    comment: str | None = Field(None, description="Share comment/description")
    security: str | None = Field(
        None, description="Security setting (public, private, secure)"
    )
    use_cache: str | None = Field(
        None, description="Cache usage (yes, no, only, prefer)"
    )
    storage: str | None = Field(
        None, description="Storage type (cache, array, cache+array, unknown)"
    )

    # Export settings
    smb_export: bool | None = Field(None, description="Is share exported via SMB?")
    nfs_export: bool | None = Field(None, description="Is share exported via NFS?")

    # Cache configuration
    cache_pool: str | None = Field(
        None, description="Primary cache pool name (empty/null = no cache)"
    )
    cache_pool2: str | None = Field(
        None, description="Secondary cache pool for 'prefer' destinations"
    )
    mover_action: str | None = Field(
        None,
        description="Computed mover action: no_cache, cache_only, cache_to_array, "
        "array_to_cache, cache_prefer",
    )

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def computed_used_percent(self) -> float | None:
        """
        Calculate used percentage from total_bytes and used_bytes.

        Falls back to the API-provided usage_percent if available,
        otherwise computes from raw byte values.

        Returns:
            Usage percentage (0-100), or None if insufficient data.

        Example:
            >>> share = ShareInfo(total_bytes=2000, used_bytes=500)
            >>> share.computed_used_percent
            25.0

        """
        if self.usage_percent is not None:
            return self.usage_percent
        if self.total_bytes and self.used_bytes is not None and self.total_bytes > 0:
            return round((self.used_bytes / self.total_bytes) * 100, 1)
        return None


class NetworkInterface(BaseModel):
    """Network interface information response."""

    # Basic info
    name: str | None = Field(None, description="Interface name")
    mac_address: str | None = Field(None, description="MAC address")
    ip_address: str | None = Field(None, description="IP address")
    netmask: str | None = Field(None, description="Network mask")
    broadcast: str | None = Field(None, description="Broadcast address")
    mtu: int | None = Field(None, description="MTU size")
    state: str | None = Field(None, description="Interface state")
    speed_mbps: int | None = Field(None, description="Link speed in Mbps")

    # Traffic stats - API uses bytes_received/bytes_sent, packets_received/packets_sent
    bytes_received: int | None = Field(None, description="Bytes received")
    bytes_sent: int | None = Field(None, description="Bytes transmitted")
    packets_received: int | None = Field(None, description="Packets received")
    packets_sent: int | None = Field(None, description="Packets transmitted")
    errors_received: int | None = Field(None, description="Receive errors")
    errors_sent: int | None = Field(None, description="Transmit errors")

    # Ethtool information
    duplex: str | None = Field(None, description="Duplex mode (Full, Half)")
    auto_negotiation: str | None = Field(None, description="Auto-negotiation status")
    link_detected: bool | None = Field(None, description="Link detected")
    port: str | None = Field(None, description="Port type")
    transceiver: str | None = Field(None, description="Transceiver type")
    mdix: str | None = Field(None, description="MDI-X status")
    phyad: int | None = Field(None, description="PHY address")
    message_level: str | None = Field(None, description="Message level")
    wake_on: str | None = Field(None, description="Wake-on-LAN status")

    # Supported capabilities
    supported_ports: list[str] | None = Field(None, description="Supported ports")
    supported_link_modes: list[str] | None = Field(
        None, description="Supported link modes"
    )
    supported_pause_frame: str | None = Field(None, description="Supported pause frame")
    supported_fec_modes: list[str] | None = Field(
        None, description="Supported FEC modes"
    )
    supports_auto_negotiation: bool | None = Field(
        None, description="Supports auto-negotiation"
    )
    supports_wake_on: list[str] | None = Field(
        None, description="Supported wake-on modes"
    )

    # Advertised capabilities
    advertised_link_modes: list[str] | None = Field(
        None, description="Advertised link modes"
    )
    advertised_pause_frame: str | None = Field(
        None, description="Advertised pause frame"
    )
    advertised_auto_negotiation: bool | None = Field(
        None, description="Advertised auto-negotiation"
    )
    advertised_fec_modes: list[str] | None = Field(
        None, description="Advertised FEC modes"
    )

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def is_physical(self) -> bool:
        """
        Check if this is a physical network interface.

        Matches common physical interface naming patterns including
        ethernet (eth, eno, enp), wireless (wlan), bonded (bond), and bridge (br0).

        Returns:
            True if the interface name matches known physical interface patterns.

        Example:
            >>> iface = NetworkInterface(name="eth0")
            >>> iface.is_physical
            True
            >>> iface2 = NetworkInterface(name="docker0")
            >>> iface2.is_physical
            False

        """
        if self.name is None:
            return False
        pattern = r"^(eth\d+|wlan\d+|bond\d+|eno\d+|enp\d+s\d+|br\d+)$"
        return bool(re.match(pattern, self.name))


class HardwareInfo(BaseModel):
    """Hardware information response (extracted from system info)."""

    cpu_model: str | None = Field(None, description="CPU model name")
    cpu_cores: int | None = Field(None, description="Number of CPU cores")
    cpu_threads: int | None = Field(None, description="Number of CPU threads")
    motherboard_model: str | None = Field(None, description="Motherboard model")
    bios_version: str | None = Field(None, description="BIOS version")
    bios_date: str | None = Field(None, description="BIOS date")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class GPUInfo(BaseModel):
    """GPU information response."""

    available: bool | None = Field(None, description="Whether GPU is available")
    index: CoercedInt = Field(None, description="GPU index")
    pci_id: str | None = Field(None, description="PCI device ID")
    name: str | None = Field(None, description="GPU name")
    vendor: str | None = Field(None, description="GPU vendor")
    driver_version: str | None = Field(None, description="GPU driver version")
    utilization_gpu_percent: CoercedFloat = Field(
        None, description="GPU utilization percentage"
    )
    utilization_memory_percent: CoercedFloat = Field(
        None, description="Memory utilization percentage"
    )
    memory_total_bytes: CoercedInt = Field(
        None, description="Total GPU memory in bytes"
    )
    memory_used_bytes: CoercedInt = Field(None, description="Used GPU memory in bytes")
    temperature_celsius: CoercedFloat = Field(
        None, description="GPU temperature in Celsius"
    )
    cpu_temperature_celsius: CoercedFloat = Field(
        None, description="CPU temperature in Celsius"
    )
    power_draw_watts: CoercedFloat = Field(None, description="Power draw in watts")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def gpu_temperature(self) -> float | None:
        """
        Get GPU temperature, preferring GPU-specific over CPU temp.

        Falls back to cpu_temperature_celsius if temperature_celsius is None.

        Returns:
            GPU temperature in Celsius, or None if unavailable.

        Example:
            >>> gpu = GPUInfo(temperature_celsius=65.0, cpu_temperature_celsius=45.0)
            >>> gpu.gpu_temperature
            65.0
            >>> gpu2 = GPUInfo(cpu_temperature_celsius=45.0)
            >>> gpu2.gpu_temperature
            45.0

        """
        if self.temperature_celsius is not None:
            return self.temperature_celsius
        return self.cpu_temperature_celsius


class UPSInfo(BaseModel):
    """UPS information response (from apcupsd)."""

    # Basic info
    model: str | None = Field(None, description="UPS model")
    status: str | None = Field(None, description="UPS status (e.g., OL, OB)")

    # Battery info
    battery_charge_percent: CoercedFloat = Field(
        None, description="Battery charge percentage"
    )
    load_percent: CoercedFloat = Field(None, description="Load percentage")

    # Runtime - API may use different field names
    runtime_left_seconds: CoercedInt = Field(
        None,
        description="Battery runtime remaining in secs",
        validation_alias=AliasChoices(
            "runtime_left_seconds",
            "battery_runtime_seconds",
            "runtime_seconds",
        ),
    )

    # Power - API uses power_watts and nominal_power_watts
    power_watts: CoercedFloat = Field(None, description="Current power draw in watts")
    nominal_power_watts: CoercedFloat = Field(
        None, description="Nominal power in watts"
    )

    # Connection status
    connected: bool | None = Field(None, description="Whether UPS is connected")

    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow", "populate_by_name": True}

    @property
    def runtime_minutes(self) -> float | None:
        """
        Get runtime remaining in minutes.

        Returns:
            Runtime in minutes, or None if runtime_left_seconds is None.

        Example:
            >>> ups = UPSInfo(runtime_left_seconds=3600)
            >>> ups.runtime_minutes
            60.0

        """
        if self.runtime_left_seconds is None:
            return None
        return round(self.runtime_left_seconds / 60, 1)


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")

    model_config = {"frozen": True, "extra": "allow"}


class ActionResponse(BaseModel):
    """Response from action endpoints (start, stop, etc.)."""

    success: bool = Field(..., description="Whether the action succeeded")
    message: str | None = Field(None, description="Response message")
    timestamp: str | None = Field(None, description="Action timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class APIError(BaseModel):
    """API error response."""

    success: bool = Field(False, description="Always false for errors")
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    timestamp: str | None = Field(None, description="Error timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class RegistrationInfo(BaseModel):
    """Unraid registration/license information."""

    type: str | None = Field(None, description="License type")
    state: str | None = Field(None, description="Registration state")
    key_file: str | None = Field(None, description="Key file path")
    guid: str | None = Field(None, description="Server GUID")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class LogFile(BaseModel):
    """Log file information."""

    name: str | None = Field(None, description="Log filename")
    path: str | None = Field(None, description="Log file path")
    size_bytes: int | None = Field(None, description="File size in bytes")
    modified_at: str | None = Field(None, description="Last modified timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class LogList(BaseModel):
    """List of available log files."""

    logs: list[LogFile] | None = Field(None, description="Available log files")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class LogContent(BaseModel):
    """Log file content response."""

    path: str | None = Field(None, description="Log file path")
    content: str | None = Field(None, description="Raw log content")
    lines: list[str] | None = Field(None, description="Log content as lines")
    total_lines: int | None = Field(None, description="Total lines in file")
    lines_returned: int | None = Field(None, description="Number of lines returned")
    start_line: int | None = Field(None, description="Start line number")
    end_line: int | None = Field(None, description="End line number")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class Notification(BaseModel):
    """Notification information."""

    id: str | None = Field(None, description="Notification ID")
    subject: str | None = Field(None, description="Notification subject")
    description: str | None = Field(None, description="Notification description")
    importance: str | None = Field(None, description="Importance level")
    timestamp: str | None = Field(None, description="Notification timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class NotificationCounts(BaseModel):
    """Notification counts by type."""

    info: int | None = Field(None, description="Info notifications")
    warning: int | None = Field(None, description="Warning notifications")
    alert: int | None = Field(None, description="Alert notifications")
    total: int | None = Field(None, description="Total notifications")

    model_config = {"frozen": True, "extra": "allow"}


class NotificationOverview(BaseModel):
    """Notification overview/summary."""

    unread: NotificationCounts | None = Field(None, description="Unread counts")
    archive: NotificationCounts | None = Field(None, description="Archive counts")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def unread_count(self) -> int:
        """
        Get total unread notification count.

        Returns:
            Total unread notifications, or 0 if unread data is unavailable.

        Example:
            >>> overview = NotificationOverview(
            ...     unread=NotificationCounts(total=5)
            ... )
            >>> overview.unread_count
            5

        """
        if self.unread is not None and self.unread.total is not None:
            return self.unread.total
        return 0


class NotificationsResponse(BaseModel):
    """Full notifications response."""

    overview: NotificationOverview | None = Field(None, description="Overview")
    notifications: list[Notification] | None = Field(
        None, description="Notification list"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def unread_count(self) -> int:
        """
        Get total unread notification count from the overview.

        Returns:
            Total unread notifications, or 0 if overview is unavailable.

        Example:
            >>> resp = NotificationsResponse(
            ...     overview=NotificationOverview(
            ...         unread=NotificationCounts(total=3)
            ...     )
            ... )
            >>> resp.unread_count
            3

        """
        if self.overview is not None:
            return self.overview.unread_count
        return 0


class UnassignedDevice(BaseModel):
    """Unassigned device information."""

    device: str | None = Field(None, description="Device path")
    name: str | None = Field(None, description="Device name")
    size_bytes: int | None = Field(None, description="Device size in bytes")
    mounted: bool | None = Field(None, description="Whether mounted")
    filesystem: str | None = Field(None, description="Filesystem type")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class RemoteShare(BaseModel):
    """Remote share information."""

    name: str | None = Field(None, description="Share name")
    protocol: str | None = Field(None, description="Protocol (SMB, NFS)")
    server: str | None = Field(None, description="Remote server")
    mounted: bool | None = Field(None, description="Whether mounted")
    mount_point: str | None = Field(None, description="Mount point path")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class UnassignedDevicesResponse(BaseModel):
    """Unassigned devices response."""

    devices: list[UnassignedDevice] | None = Field(
        None, description="Unassigned devices"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class RemoteSharesResponse(BaseModel):
    """Remote shares response."""

    remote_shares: list[RemoteShare] | None = Field(None, description="Remote shares")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class UnassignedInfo(BaseModel):
    """Full unassigned devices and remote shares response."""

    devices: list[UnassignedDevice] | None = Field(
        None, description="Unassigned devices"
    )
    remote_shares: list[RemoteShare] | None = Field(None, description="Remote shares")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class HardwareFullInfo(BaseModel):
    """Full hardware information from /hardware/full."""

    bios: dict[str, Any] | None = Field(None, description="BIOS information")
    system: dict[str, Any] | None = Field(None, description="System information")
    baseboard: dict[str, Any] | None = Field(None, description="Baseboard information")
    chassis: dict[str, Any] | None = Field(None, description="Chassis information")
    processor: dict[str, Any] | None = Field(None, description="Processor information")
    memory: dict[str, Any] | None = Field(None, description="Memory information")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class BIOSInfo(BaseModel):
    """BIOS information from DMI data."""

    vendor: str | None = Field(None, description="BIOS vendor")
    version: str | None = Field(None, description="BIOS version")
    release_date: str | None = Field(None, description="BIOS release date")
    revision: str | None = Field(None, description="BIOS revision")
    rom_size: str | None = Field(None, description="BIOS ROM size")
    runtime_size: str | None = Field(None, description="BIOS runtime size")
    address: str | None = Field(None, description="BIOS address")
    characteristics: list[str] | None = Field(None, description="BIOS characteristics")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class BaseboardInfo(BaseModel):
    """Motherboard/baseboard information from DMI data."""

    manufacturer: str | None = Field(None, description="Board manufacturer")
    product_name: str | None = Field(None, description="Board product name")
    serial_number: str | None = Field(None, description="Board serial number")
    asset_tag: str | None = Field(None, description="Asset tag")
    location_in_chassis: str | None = Field(None, description="Location in chassis")
    features: list[str] | None = Field(None, description="Board features")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class CPUHardwareInfo(BaseModel):
    """CPU hardware information from DMI data."""

    socket_designation: str | None = Field(None, description="CPU socket")
    processor_type: str | None = Field(None, description="Processor type")
    processor_family: str | None = Field(None, description="Processor family")
    processor_manufacturer: str | None = Field(
        None, description="Processor manufacturer"
    )
    processor_version: str | None = Field(None, description="Processor version")
    max_speed: str | None = Field(None, description="Maximum CPU speed")
    current_speed: str | None = Field(None, description="Current CPU speed")
    core_count: int | None = Field(None, description="Number of cores")
    thread_count: int | None = Field(None, description="Number of threads")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class MemoryArrayInfo(BaseModel):
    """Physical memory array information from DMI data."""

    location: str | None = Field(None, description="Memory location")
    use: str | None = Field(None, description="Memory use")
    error_correction_type: str | None = Field(None, description="Error correction type")
    maximum_capacity: str | None = Field(None, description="Maximum memory capacity")
    number_of_devices: int | None = Field(None, description="Number of memory devices")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class MemoryDeviceInfo(BaseModel):
    """Individual memory device (DIMM) information from DMI data."""

    locator: str | None = Field(None, description="DIMM locator")
    bank_locator: str | None = Field(None, description="Bank locator")
    type: str | None = Field(None, description="Memory type")
    size: str | None = Field(None, description="Memory size")
    speed: str | None = Field(None, description="Memory speed")
    manufacturer: str | None = Field(None, description="Memory manufacturer")
    serial_number: str | None = Field(None, description="Memory serial number")
    part_number: str | None = Field(None, description="Memory part number")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class CPUCacheInfo(BaseModel):
    """CPU cache information from DMI data."""

    socket_designation: str | None = Field(None, description="Cache designation")
    configuration: str | None = Field(None, description="Cache configuration")
    operational_mode: str | None = Field(None, description="Operational mode")
    location: str | None = Field(None, description="Cache location")
    installed_size: str | None = Field(None, description="Installed cache size")
    maximum_size: str | None = Field(None, description="Maximum cache size")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class AccessUrl(BaseModel):
    """Network access URL."""

    type: str | None = Field(None, description="URL type (lan, wan, mdns, ipv6)")
    name: str | None = Field(None, description="URL name")
    ipv4: str | None = Field(None, description="IPv4 URL")
    ipv6: str | None = Field(None, description="IPv6 URL")

    model_config = {"frozen": True, "extra": "allow"}


class NetworkAccessUrls(BaseModel):
    """Network access URLs."""

    urls: list[AccessUrl] | None = Field(None, description="Access URLs")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class SystemSettings(BaseModel):
    """System settings."""

    server_name: str | None = Field(None, description="Server name")
    timezone: str | None = Field(None, description="Timezone")
    use_ssl: bool | None = Field(None, description="SSL enabled")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class DockerSettings(BaseModel):
    """Docker settings."""

    enabled: bool | None = Field(None, description="Docker enabled")
    image_path: str | None = Field(None, description="Docker image path")
    auto_start: bool | None = Field(None, description="Auto start enabled")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class VMSettings(BaseModel):
    """VM settings."""

    enabled: bool | None = Field(None, description="VMs enabled")
    default_path: str | None = Field(None, description="Default VM path")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class DiskSettings(BaseModel):
    """Disk settings from /settings/disk-thresholds endpoint."""

    spindown_delay_minutes: CoercedInt = Field(
        None, description="Spindown delay in minutes"
    )
    start_array: bool | None = Field(None, description="Auto-start array on boot")
    spinup_groups: bool | None = Field(None, description="Enable spinup groups")
    shutdown_timeout_seconds: CoercedInt = Field(
        None, description="Shutdown timeout in seconds"
    )
    default_filesystem: str | None = Field(None, description="Default filesystem")
    hdd_temp_warning_celsius: CoercedInt = Field(
        None, description="HDD warning temperature threshold in Celsius"
    )
    hdd_temp_critical_celsius: CoercedInt = Field(
        None, description="HDD critical temperature threshold in Celsius"
    )
    ssd_temp_warning_celsius: CoercedInt = Field(
        None, description="SSD warning temperature threshold in Celsius"
    )
    ssd_temp_critical_celsius: CoercedInt = Field(
        None, description="SSD critical temperature threshold in Celsius"
    )
    warning_utilization_percent: CoercedInt = Field(
        None, description="Warning disk utilization percentage"
    )
    critical_utilization_percent: CoercedInt = Field(
        None, description="Critical disk utilization percentage"
    )
    nvme_power_monitoring: bool | None = Field(
        None, description="Enable NVMe power monitoring"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ShareConfig(BaseModel):
    """User share configuration."""

    name: str | None = Field(None, description="Share name")
    comment: str | None = Field(None, description="Share comment/description")
    allocator: str | None = Field(None, description="Disk allocation method")
    floor: str | None = Field(None, description="Minimum free space floor")
    split_level: str | None = Field(None, description="Split level setting")
    include_disks: list[str] | None = Field(None, description="Included disks")
    exclude_disks: list[str] | None = Field(None, description="Excluded disks")
    use_cache: str | None = Field(None, description="Cache usage setting")
    export: str | None = Field(None, description="Export setting")
    security: str | None = Field(None, description="Security setting")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class NetworkConfig(BaseModel):
    """Network interface configuration."""

    interface: str | None = Field(None, description="Interface name")
    description: str | None = Field(None, description="Interface description")
    protocol: str | None = Field(None, description="Protocol (ipv4, ipv6)")
    use_dhcp: bool | None = Field(None, description="Whether DHCP is enabled")
    ip_address: str | None = Field(None, description="Static IP address")
    netmask: str | None = Field(None, description="Network mask")
    gateway: str | None = Field(None, description="Default gateway")
    dns_server: str | None = Field(None, description="DNS server")
    mtu: int | None = Field(None, description="MTU size")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class UserScript(BaseModel):
    """User script information."""

    name: str | None = Field(None, description="Script name")
    description: str | None = Field(None, description="Script description")
    script_path: str | None = Field(None, description="Script path")
    schedule: str | None = Field(None, description="Schedule")
    running: bool | None = Field(None, description="Currently running")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class UserScriptExecuteResponse(BaseModel):
    """User script execution response."""

    success: bool = Field(..., description="Whether execution succeeded")
    message: str | None = Field(None, description="Response message")
    output: str | None = Field(None, description="Script output")
    exit_code: int | None = Field(None, description="Script exit code")
    timestamp: str | None = Field(None, description="Execution timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ParityCheckRecord(BaseModel):
    """Parity check history record."""

    action: str | None = Field(None, description="Action type (e.g., 'Parity-Check')")
    date: str | None = Field(None, description="Check date (ISO 8601 format)")
    duration_seconds: int | None = Field(None, description="Duration in seconds")
    speed_mbps: float | None = Field(None, description="Check speed in MB/s")
    status: str | None = Field(
        None, description="Check status (e.g., 'OK' or error message)"
    )
    errors: int | None = Field(None, description="Errors found")
    size_bytes: int | None = Field(None, description="Size checked in bytes")

    model_config = {"frozen": True, "extra": "allow"}


class ParityHistory(BaseModel):
    """Parity check history."""

    records: list[ParityCheckRecord] | None = Field(None, description="History records")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def most_recent(self) -> ParityCheckRecord | None:
        """
        Get the most recent parity check record.

        Returns:
            The first record in the list (most recent), or None if no records.

        Example:
            >>> history = ParityHistory(records=[
            ...     ParityCheckRecord(action="Parity-Check", status="OK")
            ... ])
            >>> history.most_recent.status
            'OK'

        """
        if self.records:
            return self.records[0]
        return None


class ParityStatus(BaseModel):
    """Parity check status response."""

    running: bool | None = Field(None, description="Whether parity check is running")
    paused: bool | None = Field(None, description="Whether parity check is paused")
    progress_percent: float | None = Field(None, description="Progress percentage")
    errors: int | None = Field(None, description="Errors found so far")
    speed_mb_per_sec: float | None = Field(None, description="Speed in MB/s")
    eta_seconds: int | None = Field(
        None, description="Estimated time remaining in seconds"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ZFSPool(BaseModel):
    """ZFS pool information."""

    name: str | None = Field(None, description="Pool name")
    state: str | None = Field(None, description="Pool state")
    size_bytes: CoercedInt = Field(None, description="Pool size in bytes")
    used_bytes: CoercedInt = Field(None, description="Used space in bytes")
    free_bytes: CoercedInt = Field(None, description="Free space in bytes")
    health: str | None = Field(None, description="Pool health")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def computed_used_percent(self) -> float | None:
        """
        Calculate used percentage from size_bytes and used_bytes.

        Returns:
            Usage percentage (0-100), or None if insufficient data.

        Example:
            >>> pool = ZFSPool(size_bytes=10000, used_bytes=2500)
            >>> pool.computed_used_percent
            25.0

        """
        if self.size_bytes and self.used_bytes is not None and self.size_bytes > 0:
            return round((self.used_bytes / self.size_bytes) * 100, 1)
        return None


class ZFSDataset(BaseModel):
    """ZFS dataset information."""

    name: str | None = Field(None, description="Dataset name")
    pool: str | None = Field(None, description="Parent pool")
    used_bytes: int | None = Field(None, description="Used space in bytes")
    available_bytes: int | None = Field(None, description="Available space in bytes")
    mountpoint: str | None = Field(None, description="Mount point")
    compression: str | None = Field(None, description="Compression type")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ZFSSnapshot(BaseModel):
    """ZFS snapshot information."""

    name: str | None = Field(None, description="Snapshot name")
    dataset: str | None = Field(None, description="Parent dataset")
    creation: str | None = Field(None, description="Creation timestamp")
    used_bytes: int | None = Field(None, description="Used space in bytes")
    referenced_bytes: int | None = Field(None, description="Referenced space in bytes")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ZFSArcStats(BaseModel):
    """ZFS ARC statistics."""

    hit_ratio_percent: float | None = Field(
        None, description="ARC hit ratio percentage"
    )
    size_bytes: int | None = Field(None, description="ARC size in bytes")
    target_size_bytes: int | None = Field(None, description="ARC target size in bytes")
    hits: int | None = Field(None, description="ARC hits")
    misses: int | None = Field(None, description="ARC misses")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class NUTInfo(BaseModel):
    """NUT (Network UPS Tools) information."""

    installed: bool | None = Field(None, description="NUT installed")
    running: bool | None = Field(None, description="NUT service running")
    config_mode: str | None = Field(None, description="Configuration mode")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class CollectorDetails(BaseModel):
    """Individual collector details from API."""

    name: str | None = Field(None, description="Collector name")
    enabled: bool | None = Field(None, description="Whether collector is enabled")
    interval_seconds: int | None = Field(
        None, description="Collection interval in seconds (0 if disabled)"
    )
    last_run: str | None = Field(None, description="Last collection timestamp")
    status: str | None = Field(
        None, description="Collector status (running, stopped, disabled, registered)"
    )
    required: bool | None = Field(
        None, description="True if collector cannot be disabled"
    )
    error_count: int | None = Field(None, description="Error count")

    model_config = {"frozen": True, "extra": "allow"}


class CollectorInfo(BaseModel):
    """
    Individual collector response (nested structure from API).

    The API returns: {"success": bool, "message": str, "collector": {...}, "timestamp": str}
    """

    success: bool | None = Field(None, description="Whether the request succeeded")
    message: str | None = Field(None, description="Response message")
    collector: CollectorDetails | None = Field(None, description="Collector details")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class CollectorStatus(BaseModel):
    """Collector status information (list of all collectors)."""

    total: int | None = Field(None, description="Total collectors")
    enabled_count: int | None = Field(None, description="Enabled collectors")
    disabled_count: int | None = Field(None, description="Disabled collectors")
    collectors: list[CollectorDetails] | None = Field(
        None, description="Collector details"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    def get_collector_by_name(self, name: str) -> CollectorDetails | None:
        """
        Look up a collector by name.

        Args:
            name: The collector name to search for (case-insensitive).

        Returns:
            The matching CollectorDetails, or None if not found.

        Example:
            >>> status = CollectorStatus(collectors=[
            ...     CollectorDetails(name="system", enabled=True)
            ... ])
            >>> status.get_collector_by_name("system").enabled
            True

        """
        if self.collectors is None:
            return None
        for collector in self.collectors:
            if collector.name and collector.name.lower() == name.lower():
                return collector
        return None


# Issue #27: Parity schedule support
class ParitySchedule(BaseModel):
    """Parity check schedule configuration from /array/parity-check/schedule endpoint."""

    mode: str | None = Field(
        None,
        description="Schedule mode: disabled, daily, weekly, monthly, yearly",
        validation_alias=AliasChoices("mode", "schedule_mode", "parity_mode"),
    )
    day: CoercedInt = Field(
        None,
        description="Day of week (0-6) for weekly mode",
        validation_alias=AliasChoices(
            "day", "day_of_week", "weekday", "schedule_day", "dayOfWeek"
        ),
    )
    hour: CoercedInt = Field(
        None,
        description="Hour to run",
        validation_alias=AliasChoices("hour", "schedule_hour", "start_hour"),
    )
    minute: CoercedInt = Field(
        None,
        description="Minute to run (0-59)",
        validation_alias=AliasChoices("minute", "schedule_minute", "start_minute"),
    )
    day_of_month: CoercedInt = Field(None, description="Day of month for monthly mode")
    month: CoercedInt = Field(
        None,
        description="Month (1-12) for yearly mode",
        validation_alias=AliasChoices("month", "schedule_month"),
    )
    frequency: CoercedInt = Field(None, description="Frequency multiplier")
    duration_hours: CoercedInt = Field(None, description="Maximum duration in hours")
    cumulative: bool | None = Field(
        None, description="Enable cumulative/incremental parity"
    )
    correcting: bool | None = Field(
        None,
        description="Auto-correct errors during check",
        validation_alias=AliasChoices(
            "correcting", "write_corrections", "auto_correct"
        ),
    )
    enabled: bool | None = Field(
        None,
        description="Whether the schedule is enabled",
        validation_alias=AliasChoices("enabled", "schedule_enabled", "scheduled"),
    )
    pause_hour: CoercedInt = Field(None, description="Hour to pause check (0-23)")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow", "populate_by_name": True}

    @property
    def is_enabled(self) -> bool:
        """
        Check if the parity schedule is enabled.

        Uses the explicit enabled field if set, otherwise checks if mode
        is not 'disabled'.

        Returns:
            True if the schedule is enabled.

        Example:
            >>> sched = ParitySchedule(mode="weekly", day=1, hour=2)
            >>> sched.is_enabled
            True

        """
        if self.enabled is not None:
            return self.enabled
        if self.mode is not None:
            return self.mode.lower() != "disabled"
        return False

    @property
    def next_check_datetime(self) -> datetime | None:
        """
        Calculate the next scheduled parity check datetime.

        Computes the next occurrence based on mode, day, hour, and minute.
        For weekly mode, finds the next matching weekday.
        For monthly mode, finds the next matching day of month.

        Returns:
            The next datetime when a parity check is scheduled, or None
            if schedule is disabled or insufficient data.

        Example:
            >>> sched = ParitySchedule(mode="daily", hour=3, minute=0)
            >>> next_check = sched.next_check_datetime
            >>> next_check is not None
            True

        """
        if not self.is_enabled or self.mode is None:
            return None

        now = datetime.now(tz=UTC)
        hour = self.hour or 0
        minute = self.minute or 0
        mode = self.mode.lower()

        if mode == "daily":
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        if mode == "weekly":
            if self.day is None:
                return None
            target_weekday = self.day  # 0=Monday in Python
            days_ahead = target_weekday - now.weekday()
            if days_ahead < 0:
                days_ahead += 7
            candidate = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            ) + timedelta(days=days_ahead)
            if candidate <= now:
                candidate += timedelta(weeks=1)
            return candidate

        if mode == "monthly":
            day_of_month = self.day_of_month or 1
            try:
                candidate = now.replace(
                    day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0
                )
                if candidate <= now:
                    # Move to next month
                    if now.month == 12:
                        candidate = candidate.replace(year=now.year + 1, month=1)
                    else:
                        candidate = candidate.replace(month=now.month + 1)
            except ValueError:
                # Day doesn't exist in current month, try next month
                if now.month == 12:
                    try:
                        candidate = now.replace(
                            year=now.year + 1,
                            month=1,
                            day=day_of_month,
                            hour=hour,
                            minute=minute,
                            second=0,
                            microsecond=0,
                        )
                    except ValueError:
                        return None
                else:
                    try:
                        candidate = now.replace(
                            month=now.month + 1,
                            day=day_of_month,
                            hour=hour,
                            minute=minute,
                            second=0,
                            microsecond=0,
                        )
                    except ValueError:
                        return None
            return candidate

        if mode == "yearly":
            month = self.month or 1
            day_of_month = self.day_of_month or 1
            try:
                candidate = now.replace(
                    month=month,
                    day=day_of_month,
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )
                if candidate <= now:
                    candidate = candidate.replace(year=now.year + 1)
            except ValueError:
                # Invalid month/day combination, try next year
                try:
                    candidate = now.replace(
                        year=now.year + 1,
                        month=month,
                        day=day_of_month,
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0,
                    )
                except ValueError:
                    return None
            return candidate

        return None


# Issue #28: Mover settings support
class MoverSettings(BaseModel):
    """Mover settings from /settings/mover endpoint."""

    active: bool | None = Field(None, description="Is mover currently running")
    schedule: str | None = Field(None, description="Cron expression for mover schedule")
    logging: bool | None = Field(None, description="Enable mover logging")
    cache_floor_kb: int | None = Field(
        None, description="Minimum free space to leave on cache (KB)"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #29: Docker/VM service status
class ServiceStatus(BaseModel):
    """Docker and VM service status from /settings/services endpoint."""

    docker_enabled: bool | None = Field(None, description="Docker service enabled")
    docker_autostart: bool | None = Field(None, description="Docker autostart enabled")
    vm_manager_enabled: bool | None = Field(None, description="VM manager enabled")
    vm_autostart: bool | None = Field(None, description="VM autostart enabled")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #30: Update status
class UpdateStatus(BaseModel):
    """Update availability status from /updates endpoint."""

    current_version: str | None = Field(None, description="Current Unraid version")
    latest_version: str | None = Field(
        None, description="The version available for update"
    )
    os_update_available: bool | None = Field(None, description="OS update available")
    total_plugins: int | None = Field(None, description="Total installed plugins")
    plugin_updates_count: int | None = Field(
        None, description="Number of plugins with updates"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #31: Flash drive info
class FlashDriveInfo(BaseModel):
    """USB flash boot drive information from /system/flash endpoint."""

    device: str | None = Field(None, description="Device path (e.g., /dev/sda)")
    model: str | None = Field(None, description="Flash drive model")
    vendor: str | None = Field(None, description="Flash drive vendor")
    guid: str | None = Field(None, description="Server GUID from flash drive")
    size_bytes: CoercedInt = Field(None, description="Flash drive size in bytes")
    used_bytes: CoercedInt = Field(None, description="Used space in bytes")
    free_bytes: CoercedInt = Field(None, description="Free space in bytes")
    usage_percent: CoercedFloat = Field(None, description="Usage percentage")
    smart_available: bool | None = Field(None, description="SMART data available")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def computed_used_percent(self) -> float | None:
        """
        Calculate used percentage from size_bytes and used_bytes.

        Falls back to the API-provided usage_percent if available,
        otherwise computes from raw byte values.

        Returns:
            Usage percentage (0-100), or None if insufficient data.

        Example:
            >>> flash = FlashDriveInfo(size_bytes=4000, used_bytes=1000)
            >>> flash.computed_used_percent
            25.0

        """
        if self.usage_percent is not None:
            return self.usage_percent
        if self.size_bytes and self.used_bytes is not None and self.size_bytes > 0:
            return round((self.used_bytes / self.size_bytes) * 100, 1)
        return None

    @property
    def is_healthy(self) -> bool:
        """
        Check if flash drive usage is below 90% threshold.

        A flash drive nearing capacity is a risk since Unraid boots from it.

        Returns:
            True if usage is below 90%, or True if usage data is unavailable.

        Example:
            >>> flash = FlashDriveInfo(usage_percent=95.0)
            >>> flash.is_healthy
            False

        """
        percent = self.computed_used_percent
        if percent is None:
            return True
        return percent < 90.0


# Issue #32: Plugin list
class PluginInfo(BaseModel):
    """Individual plugin information."""

    name: str | None = Field(None, description="Plugin name")
    version: str | None = Field(None, description="Installed version")
    update_available: bool | None = Field(
        None, description="Update available for this plugin"
    )

    model_config = {"frozen": True, "extra": "allow"}


class PluginList(BaseModel):
    """Plugin list from /plugins endpoint."""

    plugins: list[PluginInfo] | None = Field(
        None, description="List of installed plugins"
    )
    total_plugins: int | None = Field(None, description="Total number of plugins")
    plugins_with_updates: int | None = Field(
        None, description="Plugins with available updates"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #34: Network services status
class NetworkServiceInfo(BaseModel):
    """Individual network service information."""

    name: str | None = Field(None, description="Service display name")
    enabled: bool | None = Field(None, description="Service is enabled")
    running: bool | None = Field(None, description="Service is currently running")
    port: int | None = Field(None, description="Service port number")
    description: str | None = Field(None, description="Service description")

    model_config = {"frozen": True, "extra": "allow"}


class NetworkServicesStatus(BaseModel):
    """Network services status from /settings/network-services endpoint."""

    smb: NetworkServiceInfo | None = Field(
        None, description="SMB (Windows file sharing)"
    )
    nfs: NetworkServiceInfo | None = Field(
        None, description="NFS (Network File System)"
    )
    afp: NetworkServiceInfo | None = Field(
        None, description="AFP (Apple Filing Protocol)"
    )
    ftp: NetworkServiceInfo | None = Field(
        None, description="FTP (File Transfer Protocol)"
    )
    ssh: NetworkServiceInfo | None = Field(None, description="SSH (Secure Shell)")
    telnet: NetworkServiceInfo | None = Field(None, description="Telnet (insecure)")
    avahi: NetworkServiceInfo | None = Field(None, description="Avahi (mDNS/DNS-SD)")
    netbios: NetworkServiceInfo | None = Field(None, description="NetBIOS name service")
    wsd: NetworkServiceInfo | None = Field(
        None, description="WSD (Web Services Discovery)"
    )
    wireguard: NetworkServiceInfo | None = Field(None, description="WireGuard VPN")
    upnp: NetworkServiceInfo | None = Field(
        None, description="UPnP (Universal Plug and Play)"
    )
    ntp: NetworkServiceInfo | None = Field(None, description="NTP server")
    syslog: NetworkServiceInfo | None = Field(None, description="Remote syslog server")
    services_enabled: int | None = Field(None, description="Number of enabled services")
    services_running: int | None = Field(None, description="Number of running services")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #39: Docker container logs, size, and update management
class ContainerLogs(BaseModel):
    """Log output from a Docker container."""

    container_id: str | None = Field(None, description="Container ID")
    container_name: str | None = Field(None, description="Container name")
    logs: str | None = Field(None, description="Log content")
    line_count: int | None = Field(None, description="Number of log lines")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ContainerSizeInfo(BaseModel):
    """Size information for a Docker container."""

    container_id: str | None = Field(None, description="Container ID")
    container_name: str | None = Field(None, description="Container name")
    size_rw_bytes: int | None = Field(
        None, description="Read-write layer size in bytes"
    )
    size_root_fs_bytes: int | None = Field(
        None, description="Total root filesystem size in bytes"
    )
    image_size_bytes: int | None = Field(None, description="Base image size in bytes")
    size_display: str | None = Field(None, description="Human-readable size string")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ContainerUpdateInfo(BaseModel):
    """Update status for a single Docker container."""

    container_id: str | None = Field(None, description="Container ID")
    container_name: str | None = Field(None, description="Container name")
    image: str | None = Field(None, description="Container image")
    current_digest: str | None = Field(None, description="Current image digest")
    latest_digest: str | None = Field(None, description="Latest available image digest")
    update_available: bool | None = Field(
        None, description="Whether an update is available"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ContainerUpdateResult(BaseModel):
    """Result of updating a single Docker container."""

    container_id: str | None = Field(None, description="Container ID")
    container_name: str | None = Field(None, description="Container name")
    image: str | None = Field(None, description="Container image")
    previous_digest: str | None = Field(None, description="Previous image digest")
    new_digest: str | None = Field(None, description="New image digest")
    updated: bool | None = Field(None, description="Whether the container was updated")
    recreated: bool | None = Field(
        None, description="Whether the container was recreated"
    )
    message: str | None = Field(None, description="Result message")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ContainerUpdatesResult(BaseModel):
    """Update status for multiple Docker containers."""

    containers: list[ContainerUpdateInfo] | None = Field(
        None, description="Update status per container"
    )
    total_count: int | None = Field(None, description="Total number of containers")
    updates_available: int | None = Field(
        None, description="Number of containers with updates available"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class ContainerBulkUpdateResult(BaseModel):
    """Results of updating multiple Docker containers."""

    results: list[ContainerUpdateResult] | None = Field(
        None, description="Individual update results"
    )
    succeeded: int | None = Field(None, description="Number of successful updates")
    failed: int | None = Field(None, description="Number of failed updates")
    skipped: int | None = Field(None, description="Number of skipped containers")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #40: VM snapshot management
class VMSnapshot(BaseModel):
    """Information about a VM snapshot."""

    name: str | None = Field(None, description="Snapshot name")
    vm_name: str | None = Field(None, description="Parent VM name")
    description: str | None = Field(None, description="Snapshot description")
    state: str | None = Field(None, description="Snapshot state")
    created_at: str | None = Field(None, description="Creation timestamp")
    parent: str | None = Field(None, description="Parent snapshot name")
    is_current: bool | None = Field(
        None, description="Whether this is the current snapshot"
    )

    model_config = {"frozen": True, "extra": "allow"}


class VMSnapshotList(BaseModel):
    """List of VM snapshots."""

    vm_name: str | None = Field(None, description="VM name")
    snapshots: list[VMSnapshot] | None = Field(None, description="List of snapshots")
    count: int | None = Field(None, description="Number of snapshots")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #41: Process monitoring
class ProcessInfo(BaseModel):
    """Information about a running process."""

    pid: int | None = Field(None, description="Process ID")
    user: str | None = Field(None, description="Process owner")
    cpu_percent: float | None = Field(None, description="CPU usage percentage")
    memory_percent: float | None = Field(None, description="Memory usage percentage")
    vsz_bytes: int | None = Field(None, description="Virtual memory size in bytes")
    rss_bytes: int | None = Field(None, description="Resident set size in bytes")
    tty: str | None = Field(None, description="Controlling terminal")
    state: str | None = Field(None, description="Process state")
    started: str | None = Field(None, description="Process start time")
    time: str | None = Field(None, description="Cumulative CPU time")
    command: str | None = Field(None, description="Command line")

    model_config = {"frozen": True, "extra": "allow"}


class ProcessList(BaseModel):
    """List of running processes."""

    processes: list[ProcessInfo] | None = Field(None, description="Running processes")
    total_count: int | None = Field(None, description="Total number of processes")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #42: System service management
class SystemService(BaseModel):
    """System service information."""

    name: str | None = Field(None, description="Service name")
    running: bool | None = Field(None, description="Whether service is running")

    model_config = {"frozen": True, "extra": "allow"}


class SystemServiceList(BaseModel):
    """List of system services."""

    count: int | None = Field(None, description="Number of services")
    services: list[SystemService] | None = Field(None, description="List of services")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #43: Plugin update management
class PluginUpdateInfo(BaseModel):
    """Plugin with update information from check-updates endpoint."""

    name: str | None = Field(None, description="Plugin name")
    version: str | None = Field(None, description="Current version")
    update_available: bool | None = Field(
        None, description="Whether an update is available"
    )
    new_version: str | None = Field(None, description="New version available")

    model_config = {"frozen": True, "extra": "allow"}


class PluginUpdatesResult(BaseModel):
    """Result of checking for plugin updates."""

    count: int | None = Field(None, description="Number of plugins with updates")
    plugins_with_updates: list[PluginUpdateInfo] | None = Field(
        None, description="Plugins with available updates"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def update_count(self) -> int:
        """
        Get the number of plugins with available updates.

        Uses the count field if available, otherwise counts from the list.

        Returns:
            Number of plugins with available updates.

        Example:
            >>> result = PluginUpdatesResult(count=3)
            >>> result.update_count
            3

        """
        if self.count is not None:
            return self.count
        if self.plugins_with_updates is not None:
            return len(self.plugins_with_updates)
        return 0


class PluginUpdateResult(BaseModel):
    """Result of updating a single plugin."""

    name: str | None = Field(None, description="Plugin name")
    success: bool | None = Field(None, description="Whether the update succeeded")
    message: str | None = Field(None, description="Result message")
    previous_version: str | None = Field(None, description="Previous version")
    new_version: str | None = Field(None, description="New version installed")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class PluginBulkUpdateResult(BaseModel):
    """Results of updating multiple plugins."""

    results: list[PluginUpdateResult] | None = Field(
        None, description="Individual update results"
    )
    succeeded: int | None = Field(None, description="Number of successful updates")
    failed: int | None = Field(None, description="Number of failed updates")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #44: MQTT support
class MQTTStatus(BaseModel):
    """MQTT connection status and configuration."""

    enabled: bool | None = Field(None, description="Whether MQTT is enabled")
    connected: bool | None = Field(None, description="Whether MQTT is connected")
    broker: str | None = Field(None, description="MQTT broker address")
    client_id: str | None = Field(None, description="MQTT client ID")
    topic_prefix: str | None = Field(None, description="MQTT topic prefix")
    last_connected: str | None = Field(None, description="Last connected timestamp")
    last_error: str | None = Field(None, description="Last error message")
    messages_sent: int | None = Field(None, description="Total messages sent")
    messages_errors: int | None = Field(None, description="Total message errors")
    uptime_seconds: int | None = Field(
        None, description="MQTT connection uptime in seconds"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class MQTTTestResponse(BaseModel):
    """MQTT connection test result."""

    success: bool | None = Field(None, description="Whether the test succeeded")
    message: str | None = Field(None, description="Test result message")
    broker: str | None = Field(None, description="Broker address tested")
    latency_ms: float | None = Field(
        None, description="Connection latency in milliseconds"
    )
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class MQTTPublishResponse(BaseModel):
    """MQTT publish result."""

    success: bool | None = Field(None, description="Whether the publish succeeded")
    message: str | None = Field(None, description="Result message")
    topic: str | None = Field(None, description="Topic published to")
    timestamp: str | None = Field(None, description="Data collection timestamp")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #45: Alerting engine
class AlertRule(BaseModel):
    """User-configurable alert rule."""

    id: str | None = Field(None, description="Alert rule ID")
    name: str | None = Field(None, description="Alert rule name")
    expression: str | None = Field(None, description="Alert expression (expr-lang)")
    duration_seconds: int | None = Field(
        None, description="Duration in seconds before firing"
    )
    severity: str | None = Field(
        None, description="Severity level (info, warning, critical)"
    )
    channels: list[str] | None = Field(None, description="Notification channels")
    enabled: bool | None = Field(None, description="Whether the rule is enabled")
    cooldown_minutes: int | None = Field(None, description="Minutes between re-fires")

    model_config = {"frozen": True, "extra": "allow"}


class AlertStatus(BaseModel):
    """Current state of a single alert rule."""

    rule_id: str | None = Field(None, description="Alert rule ID")
    rule_name: str | None = Field(None, description="Alert rule name")
    state: str | None = Field(None, description="Alert state (ok, pending, firing)")
    severity: str | None = Field(None, description="Severity level")
    since: str | None = Field(None, description="State since timestamp")
    eval_count: int | None = Field(None, description="Evaluation count")
    message: str | None = Field(None, description="Alert message")

    model_config = {"frozen": True, "extra": "allow"}


class AlertEvent(BaseModel):
    """Alert state transition event."""

    rule_id: str | None = Field(None, description="Alert rule ID")
    rule_name: str | None = Field(None, description="Alert rule name")
    severity: str | None = Field(None, description="Severity level")
    state: str | None = Field(None, description="Alert state (firing, resolved)")
    message: str | None = Field(None, description="Alert message")
    fired_at: str | None = Field(None, description="Firing timestamp")
    resolved_at: str | None = Field(None, description="Resolution timestamp")

    model_config = {"frozen": True, "extra": "allow"}


class AlertsStatusResponse(BaseModel):
    """Current status of all alert rules."""

    statuses: list[AlertStatus] | None = Field(None, description="Alert statuses")

    model_config = {"frozen": True, "extra": "allow"}


class AlertHistoryResponse(BaseModel):
    """Recent alert events."""

    events: list[AlertEvent] | None = Field(None, description="Alert events")
    total: int | None = Field(None, description="Total number of events")

    model_config = {"frozen": True, "extra": "allow"}


# Issue #46: Health checks (watchdog)
class HealthCheck(BaseModel):
    """User-configured health check probe."""

    id: str | None = Field(None, description="Health check ID")
    name: str | None = Field(None, description="Health check name")
    type: str | None = Field(None, description="Check type (http, tcp, container)")
    target: str | None = Field(
        None, description="Check target (URL, host:port, container name)"
    )
    interval_seconds: int | None = Field(None, description="Check interval in seconds")
    timeout_seconds: int | None = Field(None, description="Check timeout in seconds")
    success_code: int | None = Field(None, description="Expected HTTP status code")
    on_fail: str | None = Field(None, description="Remediation action on failure")
    enabled: bool | None = Field(None, description="Whether the check is enabled")

    model_config = {"frozen": True, "extra": "allow"}


class HealthCheckStatus(BaseModel):
    """Current status of a health check."""

    check_id: str | None = Field(None, description="Health check ID")
    check_name: str | None = Field(None, description="Health check name")
    check_type: str | None = Field(None, description="Check type")
    target: str | None = Field(None, description="Check target")
    healthy: bool | None = Field(None, description="Whether the check is healthy")
    last_check: str | None = Field(None, description="Last check timestamp")
    last_error: str | None = Field(None, description="Last error message")
    consecutive_fails: int | None = Field(None, description="Consecutive failure count")
    last_remediation: str | None = Field(None, description="Last remediation timestamp")
    remediation_action: str | None = Field(
        None, description="Remediation action configured"
    )

    model_config = {"frozen": True, "extra": "allow"}


class HealthCheckEvent(BaseModel):
    """Health check state change event."""

    check_id: str | None = Field(None, description="Health check ID")
    check_name: str | None = Field(None, description="Health check name")
    state: str | None = Field(None, description="State (healthy, unhealthy)")
    message: str | None = Field(None, description="Event message")
    timestamp: str | None = Field(None, description="Event timestamp")
    remediation_taken: str | None = Field(None, description="Remediation action taken")

    model_config = {"frozen": True, "extra": "allow"}


class HealthChecksStatusResponse(BaseModel):
    """Status of all health checks."""

    checks: list[HealthCheckStatus] | None = Field(
        None, description="Health check statuses"
    )

    model_config = {"frozen": True, "extra": "allow"}


class HealthCheckHistoryResponse(BaseModel):
    """Health check event history."""

    events: list[HealthCheckEvent] | None = Field(
        None, description="Health check events"
    )

    model_config = {"frozen": True, "extra": "allow"}
