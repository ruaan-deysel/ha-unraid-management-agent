"""
VM guest agent: sensors for data read from inside the VMs.

The agent's ``/vm/guest`` endpoint (and ``vm_guest_update`` websocket event)
reports, for each VM configured in the agent's ``vm_guest_agent`` settings,
what it reads through the QEMU guest agent: GPU, disk and filesystem figures
and the output of custom commands. While a VM is off the entries seen last
stay in the lists with every reading null.

With the "Show virtual machines as separate devices" option on, the sensors
sit on the VM's own device:

- per GPU (by index): temperature, utilization, memory used (total as an
  attribute), power, fan speed and clock;
- per disk (by serial number): temperature and wear;
- per filesystem (by mount point): used percent (bytes as attributes);
- per custom sensor (by name): a number when the output parses as one, else
  the text, with the last error and run time as attributes;
- the guest hostname (diagnostic), with the OS name and agent state.

Entities stay available with an unknown state while the VM is off or a
reading is null; they only become unavailable when the agent cannot be
reached. Unique IDs are ``vmguest_<VM UUID>_<kind>_<id>_<metric>``, where the id of a disk, filesystem
or sensor is its slug plus a short hash of the original, so names that slugify
alike stay apart.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.util import slugify

from .api.models import VMGuestInfo

if TYPE_CHECKING:
    from .coordinator import UnraidData

VM_GUEST_KEY_PREFIX: Final = "vmguest_"
# Home Assistant rejects states longer than this
MAX_STATE_LENGTH: Final = 255


@dataclass(frozen=True, kw_only=True)
class UnraidVMGuestSensorEntityDescription(SensorEntityDescription):
    """Describes one guest sensor of one VM."""

    vm_identifier: str
    vm_name: str
    value_fn: Callable[[VMGuestInfo], Any]
    attributes_fn: Callable[[VMGuestInfo], dict[str, Any]] | None = None
    # Custom sensors: a number when the output parses as one, else text
    parse_number: bool = False


def parse_number(value: str | None) -> float | None:
    """Return the number a custom sensor's output holds, or None."""
    try:
        number = float(value) if value is not None else None
    except ValueError:
        return None
    return number if number is not None and isfinite(number) else None


def _find(items: list[Any] | None, attribute: str, wanted: Any) -> Any | None:
    """Return the first item whose attribute equals wanted."""
    return next(
        (item for item in items or [] if getattr(item, attribute, None) == wanted),
        None,
    )


def _reader(
    items: Callable[[VMGuestInfo], list[Any] | None],
    attribute: str,
    wanted: Any,
    field: str,
) -> Callable[[VMGuestInfo], Any]:
    """Return a getter for one reading of the item with this identity."""
    return lambda guest: getattr(_find(items(guest), attribute, wanted), field, None)


def _gpus(guest: VMGuestInfo) -> list[Any] | None:
    return guest.gpus


def _disks(guest: VMGuestInfo) -> list[Any] | None:
    return guest.disks


# (key, name, field, description settings) of the per-GPU sensors
_GPU_SENSORS: Final[tuple[tuple[str, str, str, dict[str, Any]], ...]] = (
    (
        "temperature",
        "temperature",
        "temperature_celsius",
        {
            "device_class": SensorDeviceClass.TEMPERATURE,
            "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
            "suggested_display_precision": 0,
        },
    ),
    (
        "utilization",
        "utilization",
        "utilization_percent",
        {"native_unit_of_measurement": PERCENTAGE, "suggested_display_precision": 0},
    ),
    (
        "memory_used",
        "memory used",
        "memory_used_bytes",
        {
            "device_class": SensorDeviceClass.DATA_SIZE,
            "native_unit_of_measurement": UnitOfInformation.BYTES,
            "suggested_unit_of_measurement": UnitOfInformation.GIBIBYTES,
            "suggested_display_precision": 1,
        },
    ),
    (
        "power",
        "power",
        "power_watts",
        {
            "device_class": SensorDeviceClass.POWER,
            "native_unit_of_measurement": UnitOfPower.WATT,
            "suggested_display_precision": 1,
        },
    ),
    (
        "fan",
        "fan speed",
        "fan_percent",
        {"native_unit_of_measurement": PERCENTAGE, "suggested_display_precision": 0},
    ),
    (
        "clock",
        "clock",
        "clock_mhz",
        {
            "device_class": SensorDeviceClass.FREQUENCY,
            "native_unit_of_measurement": UnitOfFrequency.MEGAHERTZ,
            "suggested_display_precision": 0,
        },
    ),
)


def _gpu_descriptions(
    vm_identifier: str, vm_name: str, index: int
) -> list[UnraidVMGuestSensorEntityDescription]:
    def attributes(guest: VMGuestInfo) -> dict[str, Any]:
        gpu = _find(guest.gpus, "index", index)
        return {
            "gpu_name": getattr(gpu, "name", None),
            "memory_total_bytes": getattr(gpu, "memory_total_bytes", None),
        }

    return [
        UnraidVMGuestSensorEntityDescription(
            key=f"{_prefix(vm_identifier)}gpu_{index}_{key}",
            name=f"GPU {index} {name}",
            state_class=SensorStateClass.MEASUREMENT,
            vm_identifier=vm_identifier,
            vm_name=vm_name,
            value_fn=_reader(_gpus, "index", index, field),
            attributes_fn=attributes if key == "memory_used" else None,
            **settings,
        )
        for key, name, field, settings in _GPU_SENSORS
    ]


def _disk_descriptions(
    vm_identifier: str, vm_name: str, disk: Any
) -> list[UnraidVMGuestSensorEntityDescription]:
    serial = disk.serial
    label = disk.model or serial

    def attributes(guest: VMGuestInfo) -> dict[str, Any]:
        found = _find(guest.disks, "serial", serial)
        return {
            "model": getattr(found, "model", None),
            "serial": serial,
            "bus": getattr(found, "bus", None),
        }

    base = f"{_prefix(vm_identifier)}disk_{_ident(serial)}"
    return [
        UnraidVMGuestSensorEntityDescription(
            key=f"{base}_temperature",
            name=f"Disk {label} temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            vm_identifier=vm_identifier,
            vm_name=vm_name,
            value_fn=_reader(_disks, "serial", serial, "temperature_celsius"),
            attributes_fn=lambda guest: {
                **attributes(guest),
                "temperature_max_celsius": getattr(
                    _find(guest.disks, "serial", serial),
                    "temperature_max_celsius",
                    None,
                ),
            },
        ),
        UnraidVMGuestSensorEntityDescription(
            key=f"{base}_wear",
            name=f"Disk {label} wear",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            vm_identifier=vm_identifier,
            vm_name=vm_name,
            value_fn=_reader(_disks, "serial", serial, "wear_percent"),
            attributes_fn=attributes,
        ),
    ]


def _filesystem_used_percent(guest: VMGuestInfo, mountpoint: str) -> float | None:
    fs = _find(guest.filesystems, "mountpoint", mountpoint)
    used = getattr(fs, "used_bytes", None)
    total = getattr(fs, "total_bytes", None)
    if used is None or not total:
        return None
    return used / total * 100


def _filesystem_description(
    vm_identifier: str, vm_name: str, mountpoint: str
) -> UnraidVMGuestSensorEntityDescription:
    def attributes(guest: VMGuestInfo) -> dict[str, Any]:
        fs = _find(guest.filesystems, "mountpoint", mountpoint)
        return {
            "mountpoint": mountpoint,
            "type": getattr(fs, "type", None),
            "total_bytes": getattr(fs, "total_bytes", None),
            "used_bytes": getattr(fs, "used_bytes", None),
        }

    return UnraidVMGuestSensorEntityDescription(
        key=f"{_prefix(vm_identifier)}fs_{_ident(mountpoint)}_used",
        name=f"Filesystem {mountpoint} used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        vm_identifier=vm_identifier,
        vm_name=vm_name,
        value_fn=lambda guest: _filesystem_used_percent(guest, mountpoint),
        attributes_fn=attributes,
    )


def _sensor_description(
    vm_identifier: str, vm_name: str, name: str
) -> UnraidVMGuestSensorEntityDescription:
    def value(guest: VMGuestInfo) -> Any:
        text = getattr(_find(guest.sensors, "name", name), "value", None)
        if text is None:
            return None
        number = parse_number(text)
        return number if number is not None else text[:MAX_STATE_LENGTH]

    def attributes(guest: VMGuestInfo) -> dict[str, Any]:
        found = _find(guest.sensors, "name", name)
        return {
            "error": getattr(found, "error", None) or None,
            "updated_at": getattr(found, "updated_at", None),
        }

    return UnraidVMGuestSensorEntityDescription(
        key=f"{_prefix(vm_identifier)}sensor_{_ident(name)}",
        name=name,
        vm_identifier=vm_identifier,
        vm_name=vm_name,
        value_fn=value,
        attributes_fn=attributes,
        parse_number=True,
    )


def _hostname_description(
    vm_identifier: str, vm_name: str
) -> UnraidVMGuestSensorEntityDescription:
    return UnraidVMGuestSensorEntityDescription(
        key=f"{_prefix(vm_identifier)}hostname",
        name="Guest hostname",
        entity_category=EntityCategory.DIAGNOSTIC,
        vm_identifier=vm_identifier,
        vm_name=vm_name,
        value_fn=lambda guest: guest.hostname or None,
        attributes_fn=lambda guest: {
            "os_name": guest.os_name or None,
            "agent_connected": guest.agent_connected,
            "running": guest.running,
            "error": guest.error or None,
        },
    )


def _ident(value: str) -> str:
    """Return a readable, collision-free key part: slug plus a hash of the original."""
    digest = hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()[:6]
    return f"{slugify(value)}_{digest}"


def _prefix(vm_identifier: str) -> str:
    return f"{VM_GUEST_KEY_PREFIX}{slugify(vm_identifier)}_"


def vm_guest_offline_prefixes(data: UnraidData) -> set[str]:
    """
    Return the key prefixes of VMs whose guest agent is not connected.

    The guest's GPUs, disks, filesystems and sensor keys are only known while
    the agent answers, and an agent restart forgets them, so their absence then
    says nothing about whether they still exist.
    """
    prefixes: set[str] = set()
    for guest in data.vm_guest or []:
        if guest.agent_connected:
            continue
        vm = _find(data.vms, "name", guest.vm_name)
        vm_identifier = getattr(vm, "id", None) or getattr(vm, "name", None)
        if vm_identifier:
            prefixes.add(_prefix(vm_identifier))
    return prefixes


def vm_guest_descriptions(
    data: UnraidData | None,
) -> list[UnraidVMGuestSensorEntityDescription]:
    """
    Return the sensor descriptions for everything the guest agent reports.

    A guest entry is only used when its VM is in the VM list, whose UUID names
    the device and the unique IDs (so renaming a VM keeps both). Items without
    an identity (a disk without serial number, a sensor without name) are
    skipped. Keys are unique within a VM.
    """
    descriptions: dict[str, UnraidVMGuestSensorEntityDescription] = {}
    if not data or not data.vm_guest:
        return []
    for guest in data.vm_guest:
        vm = _find(data.vms, "name", guest.vm_name)
        vm_name = getattr(vm, "name", None)
        vm_identifier = getattr(vm, "id", None) or vm_name
        if not vm_identifier or not vm_name:
            continue
        found = [_hostname_description(vm_identifier, vm_name)]
        for gpu in guest.gpus or []:
            if gpu.index is not None:
                found.extend(_gpu_descriptions(vm_identifier, vm_name, gpu.index))
        for disk in guest.disks or []:
            if disk.serial:
                found.extend(_disk_descriptions(vm_identifier, vm_name, disk))
        found.extend(
            _filesystem_description(vm_identifier, vm_name, fs.mountpoint)
            for fs in guest.filesystems or []
            if fs.mountpoint
        )
        found.extend(
            _sensor_description(vm_identifier, vm_name, sensor.name)
            for sensor in guest.sensors or []
            if sensor.name
        )
        for description in found:
            descriptions.setdefault(description.key, description)
    return list(descriptions.values())
