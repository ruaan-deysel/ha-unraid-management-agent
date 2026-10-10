"""
SAS storage topology: devices and entity descriptions.

The agent's ``/storage/topology`` endpoint describes storage controllers
(RAID/HBA cards), SES enclosures (disk shelves and backplanes) and the drives
behind them. Each controller and enclosure becomes a child device of the
Unraid server.

Entity design (kept small on purpose; a two-shelf system has ~45 enabled
entities, plus four throughput sensors per controller and enclosure, and the
rest disabled by default):

- Problem binary sensors for what a user replaces or re-cables: one per power
  supply and I/O module, plus enclosure-wide ones for fans, cabling, path
  redundancy, drive health and an overall status; an I/O module firmware
  mismatch sensor (diagnostic); and the controller status.
- A few enabled measurement sensors: controller temperature, HBA port link
  rate and width, enclosure highest temperature and lowest fan speed, and
  per-enclosure drive error and link-rate counts whose attributes name the
  affected slots.
- Read, write and total throughput and link utilization for each controller
  and enclosure, once the agent reports throughput (from its second
  collection cycle on).
- Per-sensor readings (every temperature/fan/voltage/current element) and
  per-slot link rate and error counts are disabled by default.

Controller and enclosure entities are deliberately not part of stale-entity
cleanup (their keys use the ``storage_`` prefix, which cleanup ignores): a
shelf that loses power or a pulled cable must show up as unavailable rather
than be deleted ten minutes later. Users can delete the device of a removed
controller or enclosure from the UI (see ``async_remove_config_entry_device``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .api.models import (
    STORAGE_TOPOLOGY_STATE_OK,
    EnclosureSensor,
    StorageController,
    StorageDrive,
    StorageEnclosure,
    StorageThroughput,
    StorageTopology,
)
from .cleanup import async_prune_seen_names
from .const import DOMAIN
from .entity import UnraidBaseEntity

if TYPE_CHECKING:
    from .coordinator import UnraidConfigEntry, UnraidDataUpdateCoordinator

STORAGE_COLLECTOR: Final = "storage_topology"
CONTROLLER: Final = "controller"
ENCLOSURE: Final = "enclosure"

# Controller statuses storcli reports for a healthy controller.
_HEALTHY_CONTROLLER_STATUSES = frozenset({"optimal", "ok"})

type OwnerKind = Literal["controller", "enclosure"]


def storage_topology(
    coordinator: UnraidDataUpdateCoordinator,
) -> StorageTopology | None:
    """
    Return the collected storage topology, or None when it is not usable.

    None covers an agent without the endpoint (404), a failed fetch, a topology
    that is still pending or unsupported, and a disabled collector (whose last
    snapshot the agent would otherwise keep serving).
    """
    data = coordinator.data
    topology = data.storage_topology if data else None
    if (
        topology is None
        or topology.state != STORAGE_TOPOLOGY_STATE_OK
        or not coordinator.is_collector_enabled(STORAGE_COLLECTOR)
    ):
        return None
    return topology


def device_identifier(entry_id: str, kind: OwnerKind, owner_id: str) -> str:
    """Return the device registry identifier of a controller or enclosure."""
    return f"{entry_id}_storage_{kind}_{owner_id}"


def controller_name(controller: StorageController) -> str:
    """Return the device name of a controller."""
    return f"{controller.model or 'Storage controller'} (c{controller.index})"


def enclosure_name(enclosure: StorageEnclosure) -> str:
    """Return the device name of an enclosure (storcli EID when known)."""
    base = " ".join(p for p in (enclosure.vendor, enclosure.product) if p)
    label = (
        f"e{enclosure.enclosure_device_id}"
        if enclosure.enclosure_device_id is not None
        else enclosure.id[-6:]
    )
    return f"{base or 'Enclosure'} ({label})"


def build_storage_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    kind: OwnerKind,
    owner_id: str,
    name: str,
) -> DeviceInfo | ChildDeviceInfo:
    """Build device info for a controller or enclosure, a child of the server."""
    entry_id = coordinator.config_entry.entry_id
    # The server device is registered during setup, before the platforms load.
    server = dr.async_get(coordinator.hass).async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )
    if server is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return ChildDeviceInfo(
        identifiers={(DOMAIN, device_identifier(entry_id, kind, owner_id))},
        name=name,
        parent_device_id=server.id,
    )


def current_storage_ids(topology: StorageTopology | None, kind: OwnerKind) -> set[str]:
    """Return the IDs of the controllers or enclosures currently reported."""
    if topology is None:
        return set()
    owners = topology.controllers if kind == CONTROLLER else topology.enclosures
    return {owner.id for owner in owners}


# =============================================================================
# Targets: which controller/enclosure (and which element of it) an entity shows
# =============================================================================


@dataclass(frozen=True)
class StorageContext:
    """The data an entity reads: topology, owning device and element."""

    topology: StorageTopology
    owner: Any
    item: Any


def _find_item(topology: StorageTopology, owner: Any, item: tuple[str, int]) -> Any:
    """Return the element of a controller or enclosure an entity refers to."""
    kind, number = item
    if kind == "port":
        candidates: list[Any] = [p for p in owner.ports if p.port == number]
    elif kind == "slot":
        candidates = [d for d in enclosure_drives(topology, owner) if d.slot == number]
    else:
        elements: list[Any] = getattr(owner, _ELEMENT_LISTS[kind])
        candidates = [e for e in elements if e.index == number]
    return candidates[0] if candidates else None


# Enclosure element kinds and the list they live in.
_ELEMENT_LISTS: dict[str, str] = {
    "power_supply": "power_supplies",
    "iom": "ioms",
    "temperature": "temperature_sensors",
    "fan": "fans",
    "voltage": "voltage_sensors",
    "current": "current_sensors",
}


def resolve(
    topology: StorageTopology,
    kind: OwnerKind,
    owner_id: str,
    item: tuple[str, int] | None,
) -> StorageContext | None:
    """Find an entity's controller or enclosure, and element, in the topology."""
    owners: list[Any] = (
        topology.controllers if kind == CONTROLLER else topology.enclosures
    )
    owner = next((o for o in owners if o.id == owner_id), None)
    if owner is None:
        return None
    if item is None:
        return StorageContext(topology, owner, None)
    found = _find_item(topology, owner, item)
    if found is None:
        return None
    return StorageContext(topology, owner, found)


def enclosure_drives(
    topology: StorageTopology, enclosure: StorageEnclosure
) -> list[StorageDrive]:
    """Return the drives storcli reports in an enclosure."""
    return [d for d in topology.drives if d.enclosure_id == enclosure.id]


# =============================================================================
# Value and attribute helpers
# =============================================================================


def _true_flags(element: Any, names: tuple[str, ...]) -> list[str]:
    """Return the names of the element's flags that are set."""
    return [name for name in names if getattr(element, name, False)]


_PSU_FLAGS = (
    "fail",
    "ac_fail",
    "dc_fail",
    "over_temp_fail",
    "temp_warning",
    "dc_over_voltage",
    "dc_under_voltage",
    "dc_over_current",
    "off",
    "predicted_failure",
)
_SENSOR_FLAGS = ("fail", "warn_over", "warn_under", "crit_over", "crit_under")


def _controller_problem(ctx: StorageContext) -> bool:
    controller: StorageController = ctx.owner
    status = (controller.status or "").lower()
    return status not in _HEALTHY_CONTROLLER_STATUSES or bool(
        controller.memory_uncorrectable_errors
    )


def _controller_attrs(ctx: StorageContext) -> dict[str, Any]:
    controller: StorageController = ctx.owner
    return {
        "status": controller.status,
        "personality": controller.personality,
        "physical_drives": controller.physical_drives,
        "memory_correctable_errors": controller.memory_correctable_errors,
        "memory_uncorrectable_errors": controller.memory_uncorrectable_errors,
        "bbu_status": controller.bbu_status,
    }


def _firmware_attrs(ctx: StorageContext) -> dict[str, Any]:
    controller: StorageController = ctx.owner
    return {
        "firmware_package": controller.firmware_package,
        "bios_version": controller.bios_version,
        "driver_name": controller.driver_name,
        "driver_version": controller.driver_version,
    }


def _pcie_link(ctx: StorageContext) -> str | None:
    controller: StorageController = ctx.owner
    if not controller.pcie_link_speed:
        return None
    width = controller.pcie_link_width
    return (
        f"{controller.pcie_link_speed} x{width}"
        if width
        else controller.pcie_link_speed
    )


def _pcie_attrs(ctx: StorageContext) -> dict[str, Any]:
    controller: StorageController = ctx.owner
    return {
        "max_link_speed": controller.pcie_max_link_speed,
        "max_link_width": controller.pcie_max_link_width,
        "pci_address": controller.pci_address,
    }


def _attached_enclosure_name(
    topology: StorageTopology, enclosure_id: str | None
) -> str | None:
    """Return the device name of an enclosure by ID."""
    for enclosure in topology.enclosures:
        if enclosure.id == enclosure_id:
            return enclosure_name(enclosure)
    return None


def _port_attrs(ctx: StorageContext) -> dict[str, Any]:
    port = ctx.item
    return {
        "phys": port.phys,
        "width": port.width,
        "attached_sas_address": port.attached_sas_address,
        "attached_device_type": port.attached_device_type,
        "attached_enclosure": _attached_enclosure_name(
            ctx.topology, port.attached_enclosure_id
        ),
        "attached_iom": port.attached_iom,
    }


def _enclosure_attrs(ctx: StorageContext) -> dict[str, Any]:
    enclosure: StorageEnclosure = ctx.owner
    return {
        "status": enclosure.status,
        "problems": enclosure.problems,
        "slots": enclosure.slots,
        "slots_populated": enclosure.slots_populated,
        "enclosure_device_id": enclosure.enclosure_device_id,
        "partner_device_id": enclosure.partner_device_id,
        "connector_name": enclosure.connector_name,
        "port_mode": enclosure.port_mode,
        "ses_devices": [d.device for d in enclosure.ses_devices],
    }


def _psu_attrs(ctx: StorageContext) -> dict[str, Any]:
    psu = ctx.item
    return {
        "status": psu.status,
        "flags": _true_flags(psu, _PSU_FLAGS),
        "rated_watts": psu.rated_watts,
        "firmware": psu.firmware,
        "part_number": psu.part_number,
        "serial_number": psu.serial_number,
    }


def _iom_attrs(ctx: StorageContext) -> dict[str, Any]:
    iom = ctx.item
    return {
        "status": iom.status,
        "firmware": iom.firmware,
        "part_number": iom.part_number,
        "serial_number": iom.serial_number,
        "host_visible": iom.host_visible,
        "expander_sas_address": iom.expander_sas_address,
    }


def _fans_attrs(ctx: StorageContext) -> dict[str, Any]:
    enclosure: StorageEnclosure = ctx.owner
    return {
        "fans": [
            {"index": f.index, "status": f.status, "rpm": f.rpm, "speed": f.speed}
            for f in enclosure.fans
        ]
    }


def _attached_to(ctx: StorageContext, connector: Any) -> str | None:
    """Describe what a connector's cable is plugged into."""
    if connector.attached_kind == CONTROLLER:
        controller = next(
            (c for c in ctx.topology.controllers if c.id == connector.attached_id),
            None,
        )
        name = controller_name(controller) if controller else connector.attached_id
        if connector.attached_port is not None:
            return f"{name} port {connector.attached_port}"
        return name
    if connector.attached_kind == ENCLOSURE:
        name = _attached_enclosure_name(ctx.topology, connector.attached_id)
        return f"{name or connector.attached_id} I/O module {connector.attached_iom}"
    return connector.attached_sas_address


def _cabling_problem(ctx: StorageContext) -> bool:
    enclosure: StorageEnclosure = ctx.owner
    return any(c.problem and c.installed for c in enclosure.connectors)


def _cabling_attrs(ctx: StorageContext) -> dict[str, Any]:
    enclosure: StorageEnclosure = ctx.owner
    return {
        "connectors": [
            {
                "connector": c.index,
                "status": c.status,
                "attached_to": _attached_to(ctx, c),
                "cable": " ".join(p for p in (c.cable_vendor, c.cable_part_number) if p)
                or None,
            }
            for c in enclosure.connectors
            if c.installed
        ]
    }


def _redundancy_attrs(ctx: StorageContext) -> dict[str, Any]:
    redundancy = ctx.owner.redundancy
    return {
        "expected_paths": redundancy.expected_paths,
        "active_paths": redundancy.active_paths,
        "single_path_drives": redundancy.single_path_drives,
        "reasons": redundancy.reasons,
    }


def iom_firmware(enclosure: StorageEnclosure) -> list[str]:
    """Return the distinct I/O module firmware versions of an enclosure."""
    return sorted({iom.firmware for iom in enclosure.ioms if iom.firmware})


def _iom_firmware_problem(ctx: StorageContext) -> bool:
    enclosure: StorageEnclosure = ctx.owner
    return enclosure.iom_firmware_mismatch or enclosure.iom_firmware_differs_from_peers


def _iom_firmware_attrs(ctx: StorageContext) -> dict[str, Any]:
    enclosure: StorageEnclosure = ctx.owner
    peers = sorted(
        {
            version
            for other in ctx.topology.enclosures
            if other.id != enclosure.id
            and (other.vendor, other.product) == (enclosure.vendor, enclosure.product)
            for version in iom_firmware(other)
        }
    )
    return {
        "firmware": iom_firmware(enclosure),
        "mismatch_within_enclosure": enclosure.iom_firmware_mismatch,
        "differs_from_peers": enclosure.iom_firmware_differs_from_peers,
        "peer_firmware": peers,
    }


def _drives(ctx: StorageContext) -> list[StorageDrive]:
    return enclosure_drives(ctx.topology, ctx.owner)


def _failing_slots(ctx: StorageContext) -> list[int]:
    return [
        d.slot
        for d in _drives(ctx)
        if (d.predictive_failures or 0) > 0 or d.smart_alert
    ]


def _drive_health_attrs(ctx: StorageContext) -> dict[str, Any]:
    return {"slots": _failing_slots(ctx)}


def _highest_temperature(ctx: StorageContext) -> float | None:
    values = [s.value for s in ctx.owner.temperature_sensors if s.value is not None]
    return max(values) if values else None


def _readings(sensors: list[EnclosureSensor]) -> dict[str, float | None]:
    return {str(s.index): s.value for s in sensors}


def _lowest_fan_speed(ctx: StorageContext) -> int | None:
    values = [f.rpm for f in ctx.owner.fans if f.rpm is not None]
    return min(values) if values else None


def _below_max_slots(ctx: StorageContext) -> list[int]:
    return [d.slot for d in _drives(ctx) if d.below_max_link_rate]


def _error_sum(field: str) -> Callable[[StorageContext], int | None]:
    def value(ctx: StorageContext) -> int | None:
        counts = [getattr(d, field) for d in _drives(ctx)]
        known = [c for c in counts if c is not None]
        return sum(known) if known else None

    return value


def _error_slots(field: str) -> Callable[[StorageContext], dict[str, Any]]:
    def attrs(ctx: StorageContext) -> dict[str, Any]:
        return {
            "slots": {
                str(d.slot): getattr(d, field)
                for d in _drives(ctx)
                if (getattr(d, field) or 0) > 0
            }
        }

    return attrs


def _element_attrs(ctx: StorageContext) -> dict[str, Any]:
    element = ctx.item
    return {
        "status": element.status,
        "description": element.description,
        "flags": _true_flags(element, _SENSOR_FLAGS),
    }


def _slot_link_attrs(ctx: StorageContext) -> dict[str, Any]:
    drive: StorageDrive = ctx.item
    return {
        "device": drive.device,
        "model": drive.model,
        "serial_number": drive.serial_number,
        "state": drive.state,
        "max_link_rate_gbps": drive.max_link_rate_gbps,
        "multipath": drive.multipath,
        "active_paths": drive.active_paths,
        "controller_ports": drive.controller_ports,
    }


def _slot_errors(ctx: StorageContext) -> int | None:
    drive: StorageDrive = ctx.item
    if drive.media_errors is None and drive.other_errors is None:
        return None
    return (drive.media_errors or 0) + (drive.other_errors or 0)


def _slot_error_attrs(ctx: StorageContext) -> dict[str, Any]:
    drive: StorageDrive = ctx.item
    return {
        "device": drive.device,
        "media_errors": drive.media_errors,
        "other_errors": drive.other_errors,
        "predictive_failures": drive.predictive_failures,
        "smart_alert": drive.smart_alert,
    }


def _throughput(ctx: StorageContext) -> StorageThroughput | None:
    """Return the throughput of the context's controller or enclosure."""
    throughput: StorageThroughput | None = ctx.owner.throughput
    return throughput


def _has_throughput(ctx: StorageContext) -> bool:
    return _throughput(ctx) is not None


def _throughput_value(field: str) -> Callable[[StorageContext], float | None]:
    def value(ctx: StorageContext) -> float | None:
        throughput = _throughput(ctx)
        return getattr(throughput, field) if throughput else None

    return value


def _throughput_attrs(ctx: StorageContext) -> dict[str, Any]:
    throughput = _throughput(ctx)
    if throughput is None:
        return {}
    return {
        "drives": throughput.drives,
        "interval_seconds": throughput.interval_seconds,
    }


def _utilization_attrs(ctx: StorageContext) -> dict[str, Any]:
    throughput = _throughput(ctx)
    if throughput is None:
        return {}
    # The agent reports a capacity of 0 when it cannot work out the link speed.
    capacity = throughput.capacity_bytes_per_sec or None
    return {**_throughput_attrs(ctx), "capacity_bytes_per_sec": capacity}


# =============================================================================
# Entity descriptions
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class UnraidStorageSensorEntityDescription(SensorEntityDescription):
    """Description of a storage topology sensor."""

    value_fn: Callable[[StorageContext], StateType]
    attrs_fn: Callable[[StorageContext], dict[str, Any]] | None = None
    # False makes the entity unavailable (data the owner no longer reports).
    exists_fn: Callable[[StorageContext], bool] | None = None


@dataclass(frozen=True, kw_only=True)
class UnraidStorageBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of a storage topology problem binary sensor."""

    device_class: BinarySensorDeviceClass | None = BinarySensorDeviceClass.PROBLEM
    is_on_fn: Callable[[StorageContext], bool]
    attrs_fn: Callable[[StorageContext], dict[str, Any]] | None = None
    exists_fn: Callable[[StorageContext], bool] | None = None


_CONTROLLER_TEMPERATURE = UnraidStorageSensorEntityDescription(
    key="temperature",
    translation_key="storage_controller_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda ctx: ctx.owner.temperature_celsius,
)
_CONTROLLER_FIRMWARE = UnraidStorageSensorEntityDescription(
    key="firmware",
    translation_key="storage_firmware",
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda ctx: ctx.owner.firmware_version,
    attrs_fn=_firmware_attrs,
)
_CONTROLLER_PCIE = UnraidStorageSensorEntityDescription(
    key="pcie_link",
    translation_key="storage_pcie_link",
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=_pcie_link,
    attrs_fn=_pcie_attrs,
)
_PORT_LINK_RATE = UnraidStorageSensorEntityDescription(
    key="link_rate",
    translation_key="storage_port_link_rate",
    device_class=SensorDeviceClass.DATA_RATE,
    native_unit_of_measurement=UnitOfDataRate.GIGABITS_PER_SECOND,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda ctx: ctx.item.link_rate_gbps,
    attrs_fn=_port_attrs,
)
_PORT_WIDTH = UnraidStorageSensorEntityDescription(
    key="width",
    translation_key="storage_port_width",
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda ctx: ctx.item.width,
)
_ENCLOSURE_TEMPERATURE = UnraidStorageSensorEntityDescription(
    key="highest_temperature",
    translation_key="storage_highest_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_highest_temperature,
    attrs_fn=lambda ctx: {"sensors": _readings(ctx.owner.temperature_sensors)},
)
_ENCLOSURE_FAN_SPEED = UnraidStorageSensorEntityDescription(
    key="lowest_fan_speed",
    translation_key="storage_lowest_fan_speed",
    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_lowest_fan_speed,
    attrs_fn=_fans_attrs,
)
_DRIVES_BELOW_MAX = UnraidStorageSensorEntityDescription(
    key="drives_below_max_link_rate",
    translation_key="storage_drives_below_max_link_rate",
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda ctx: len(_below_max_slots(ctx)),
    attrs_fn=lambda ctx: {"slots": _below_max_slots(ctx)},
)
_DRIVE_MEDIA_ERRORS = UnraidStorageSensorEntityDescription(
    key="drive_media_errors",
    translation_key="storage_drive_media_errors",
    state_class=SensorStateClass.TOTAL,
    value_fn=_error_sum("media_errors"),
    attrs_fn=_error_slots("media_errors"),
)
_DRIVE_OTHER_ERRORS = UnraidStorageSensorEntityDescription(
    key="drive_other_errors",
    translation_key="storage_drive_other_errors",
    state_class=SensorStateClass.TOTAL,
    value_fn=_error_sum("other_errors"),
    attrs_fn=_error_slots("other_errors"),
)
_ELEMENT_TEMPERATURE = UnraidStorageSensorEntityDescription(
    key="temperature",
    translation_key="storage_temperature_sensor",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
    value_fn=lambda ctx: ctx.item.value,
    attrs_fn=_element_attrs,
)
_ELEMENT_FAN = UnraidStorageSensorEntityDescription(
    key="speed",
    translation_key="storage_fan_speed",
    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
    value_fn=lambda ctx: ctx.item.rpm,
    attrs_fn=lambda ctx: {"status": ctx.item.status, "speed": ctx.item.speed},
)
_ELEMENT_VOLTAGE = UnraidStorageSensorEntityDescription(
    key="voltage",
    translation_key="storage_voltage_sensor",
    device_class=SensorDeviceClass.VOLTAGE,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=lambda ctx: ctx.item.value,
    attrs_fn=_element_attrs,
)
_ELEMENT_CURRENT = UnraidStorageSensorEntityDescription(
    key="current",
    translation_key="storage_current_sensor",
    device_class=SensorDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=lambda ctx: ctx.item.value,
    attrs_fn=_element_attrs,
)
_SLOT_LINK_RATE = UnraidStorageSensorEntityDescription(
    key="link_rate",
    translation_key="storage_slot_link_rate",
    device_class=SensorDeviceClass.DATA_RATE,
    native_unit_of_measurement=UnitOfDataRate.GIGABITS_PER_SECOND,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=lambda ctx: ctx.item.link_rate_gbps,
    attrs_fn=_slot_link_attrs,
)
_SLOT_ERRORS = UnraidStorageSensorEntityDescription(
    key="errors",
    translation_key="storage_slot_errors",
    state_class=SensorStateClass.TOTAL,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=_slot_errors,
    attrs_fn=_slot_error_attrs,
)


def _throughput_description(
    key: str, field: str
) -> UnraidStorageSensorEntityDescription:
    """Describe a read, write or total throughput sensor."""
    return UnraidStorageSensorEntityDescription(
        key=key,
        translation_key=f"storage_{key}",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_throughput_value(field),
        attrs_fn=_throughput_attrs,
        exists_fn=_has_throughput,
    )


_READ_THROUGHPUT = _throughput_description("read_throughput", "read_bytes_per_sec")
_WRITE_THROUGHPUT = _throughput_description("write_throughput", "write_bytes_per_sec")
_TOTAL_THROUGHPUT = _throughput_description("throughput", "total_bytes_per_sec")
_LINK_UTILIZATION = UnraidStorageSensorEntityDescription(
    key="link_utilization",
    translation_key="storage_link_utilization",
    native_unit_of_measurement=PERCENTAGE,
    suggested_display_precision=1,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_throughput_value("utilization_percent"),
    attrs_fn=_utilization_attrs,
    exists_fn=_has_throughput,
)
_THROUGHPUT_SENSORS = (
    _READ_THROUGHPUT,
    _WRITE_THROUGHPUT,
    _TOTAL_THROUGHPUT,
    _LINK_UTILIZATION,
)

_CONTROLLER_STATUS = UnraidStorageBinarySensorEntityDescription(
    key="status",
    translation_key="storage_status",
    is_on_fn=_controller_problem,
    attrs_fn=_controller_attrs,
)
_ENCLOSURE_STATUS = UnraidStorageBinarySensorEntityDescription(
    key="status",
    translation_key="storage_status",
    is_on_fn=lambda ctx: bool(ctx.owner.problems),
    attrs_fn=_enclosure_attrs,
)
_POWER_SUPPLY = UnraidStorageBinarySensorEntityDescription(
    key="power_supply",
    translation_key="storage_power_supply",
    is_on_fn=lambda ctx: ctx.item.problem,
    attrs_fn=_psu_attrs,
)
_IOM = UnraidStorageBinarySensorEntityDescription(
    key="iom",
    translation_key="storage_iom",
    is_on_fn=lambda ctx: ctx.item.problem,
    attrs_fn=_iom_attrs,
)
_FANS = UnraidStorageBinarySensorEntityDescription(
    key="fans",
    translation_key="storage_fans",
    is_on_fn=lambda ctx: any(f.problem for f in ctx.owner.fans),
    attrs_fn=_fans_attrs,
)
_CABLING = UnraidStorageBinarySensorEntityDescription(
    key="cabling",
    translation_key="storage_cabling",
    is_on_fn=_cabling_problem,
    attrs_fn=_cabling_attrs,
)
_PATH_REDUNDANCY = UnraidStorageBinarySensorEntityDescription(
    key="path_redundancy",
    translation_key="storage_path_redundancy",
    is_on_fn=lambda ctx: ctx.owner.redundancy.degraded,
    attrs_fn=_redundancy_attrs,
)
_IOM_FIRMWARE = UnraidStorageBinarySensorEntityDescription(
    key="iom_firmware",
    translation_key="storage_iom_firmware",
    entity_category=EntityCategory.DIAGNOSTIC,
    is_on_fn=_iom_firmware_problem,
    attrs_fn=_iom_firmware_attrs,
)
_DRIVE_HEALTH = UnraidStorageBinarySensorEntityDescription(
    key="drive_health",
    translation_key="storage_drive_health",
    is_on_fn=lambda ctx: bool(_failing_slots(ctx)),
    attrs_fn=_drive_health_attrs,
)


# =============================================================================
# Entity specs: which entities a topology produces
# =============================================================================


@dataclass(frozen=True)
class StorageEntitySpec:
    """One storage entity to create: what it shows and where it lives."""

    description: (
        UnraidStorageSensorEntityDescription
        | UnraidStorageBinarySensorEntityDescription
    )
    kind: OwnerKind
    owner_id: str
    device_name: str
    item: tuple[str, int] | None = None

    @property
    def key(self) -> str:
        """Return the entity key (the unique ID without the entry ID)."""
        parts = [f"storage_{self.kind}", slugify(self.owner_id)]
        if self.item is not None:
            parts.append(f"{self.item[0]}_{self.item[1]}")
        parts.append(self.description.key)
        return "_".join(parts)

    @property
    def placeholders(self) -> dict[str, str] | None:
        """Return the translation placeholders of the entity name."""
        if self.item is None:
            return None
        return {"index": str(self.item[1])}


def storage_sensor_specs(topology: StorageTopology) -> list[StorageEntitySpec]:
    """Return the sensor entities for a topology."""
    specs: list[StorageEntitySpec] = []
    for controller in topology.controllers:
        name = controller_name(controller)

        def ctrl(
            description: UnraidStorageSensorEntityDescription,
            item: tuple[str, int] | None = None,
            *,
            owner_id: str = controller.id,
            device_name: str = name,
        ) -> StorageEntitySpec:
            return StorageEntitySpec(
                description, CONTROLLER, owner_id, device_name, item
            )

        if controller.temperature_celsius is not None:
            specs.append(ctrl(_CONTROLLER_TEMPERATURE))
        specs.append(ctrl(_CONTROLLER_FIRMWARE))
        if controller.pcie_link_speed:
            specs.append(ctrl(_CONTROLLER_PCIE))
        if controller.throughput is not None:
            specs.extend(ctrl(d) for d in _THROUGHPUT_SENSORS)
        for port in controller.ports:
            specs.append(ctrl(_PORT_LINK_RATE, ("port", port.port)))
            specs.append(ctrl(_PORT_WIDTH, ("port", port.port)))

    for enclosure in topology.enclosures:
        name = enclosure_name(enclosure)

        def encl(
            description: UnraidStorageSensorEntityDescription,
            item: tuple[str, int] | None = None,
            *,
            owner_id: str = enclosure.id,
            device_name: str = name,
        ) -> StorageEntitySpec:
            return StorageEntitySpec(
                description, ENCLOSURE, owner_id, device_name, item
            )

        if enclosure.temperature_sensors:
            specs.append(encl(_ENCLOSURE_TEMPERATURE))
        if any(f.rpm is not None for f in enclosure.fans):
            specs.append(encl(_ENCLOSURE_FAN_SPEED))
        if enclosure.throughput is not None:
            specs.extend(encl(d) for d in _THROUGHPUT_SENSORS)
        if enclosure_drives(topology, enclosure):
            specs.append(encl(_DRIVES_BELOW_MAX))
            specs.append(encl(_DRIVE_MEDIA_ERRORS))
            specs.append(encl(_DRIVE_OTHER_ERRORS))
        for sensor in enclosure.temperature_sensors:
            specs.append(encl(_ELEMENT_TEMPERATURE, ("temperature", sensor.index)))
        for fan in enclosure.fans:
            if fan.rpm is not None:
                specs.append(encl(_ELEMENT_FAN, ("fan", fan.index)))
        for sensor in enclosure.voltage_sensors:
            specs.append(encl(_ELEMENT_VOLTAGE, ("voltage", sensor.index)))
        for sensor in enclosure.current_sensors:
            specs.append(encl(_ELEMENT_CURRENT, ("current", sensor.index)))
        for drive in enclosure_drives(topology, enclosure):
            specs.append(encl(_SLOT_LINK_RATE, ("slot", drive.slot)))
            specs.append(encl(_SLOT_ERRORS, ("slot", drive.slot)))
    return specs


def storage_binary_sensor_specs(topology: StorageTopology) -> list[StorageEntitySpec]:
    """Return the binary sensor entities for a topology."""
    specs = [
        StorageEntitySpec(
            _CONTROLLER_STATUS, CONTROLLER, controller.id, controller_name(controller)
        )
        for controller in topology.controllers
    ]
    for enclosure in topology.enclosures:
        name = enclosure_name(enclosure)

        def encl(
            description: UnraidStorageBinarySensorEntityDescription,
            item: tuple[str, int] | None = None,
            *,
            owner_id: str = enclosure.id,
            device_name: str = name,
        ) -> StorageEntitySpec:
            return StorageEntitySpec(
                description, ENCLOSURE, owner_id, device_name, item
            )

        specs.append(encl(_ENCLOSURE_STATUS))
        specs.extend(
            encl(_POWER_SUPPLY, ("power_supply", psu.index))
            for psu in enclosure.power_supplies
        )
        specs.extend(encl(_IOM, ("iom", iom.index)) for iom in enclosure.ioms)
        if enclosure.fans:
            specs.append(encl(_FANS))
        if enclosure.connectors:
            specs.append(encl(_CABLING))
        if enclosure.redundancy.expected_paths >= 2:
            specs.append(encl(_PATH_REDUNDANCY))
        if iom_firmware(enclosure):
            specs.append(encl(_IOM_FIRMWARE))
        if enclosure_drives(topology, enclosure):
            specs.append(encl(_DRIVE_HEALTH))
    return specs


# =============================================================================
# Entity base
# =============================================================================


class UnraidStorageEntity(UnraidBaseEntity):
    """Base for entities of a storage controller or enclosure device."""

    def __init__(
        self, coordinator: UnraidDataUpdateCoordinator, spec: StorageEntitySpec
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, spec.key)
        self._spec = spec
        self._attr_device_info = build_storage_device_info(
            coordinator, spec.kind, spec.owner_id, spec.device_name
        )
        if spec.placeholders:
            self._attr_translation_placeholders = spec.placeholders

    def _storage_context(self) -> StorageContext | None:
        """Return this entity's data, or None when it is not reported."""
        topology = storage_topology(self.coordinator)
        if topology is None:
            return None
        ctx = resolve(topology, self._spec.kind, self._spec.owner_id, self._spec.item)
        exists_fn = self._spec.description.exists_fn
        if ctx is None or (exists_fn is not None and not exists_fn(ctx)):
            return None
        return ctx

    @property
    def available(self) -> bool:
        """Return True while the controller/enclosure (and element) is reported."""
        return super().available and self._storage_context() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return details about the controller, enclosure or element."""
        attrs_fn = self._spec.description.attrs_fn
        ctx = self._storage_context()
        if attrs_fn is None or ctx is None:
            return None
        return attrs_fn(ctx)


def async_setup_storage_entities(
    entry: UnraidConfigEntry,
    platform_domain: str,
    specs_fn: Callable[[StorageTopology], list[StorageEntitySpec]],
    entity_factory: Callable[[UnraidDataUpdateCoordinator, StorageEntitySpec], Entity],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """
    Add storage entities now and whenever new ones appear in the topology.

    The agent publishes the topology some time after it starts, and shelves
    or ports can appear later, so entities are created from a coordinator
    listener (like other dynamic entities).
    """
    coordinator = entry.runtime_data.coordinator
    hass = coordinator.hass
    seen: set[str] = set()

    @callback
    def _add_entities() -> None:
        topology = storage_topology(coordinator)
        if topology is None:
            return
        # Allow re-creation of entities removed from the registry (see #83)
        async_prune_seen_names(
            hass, platform_domain, seen, lambda key: f"{entry.entry_id}_{key}"
        )
        new_entities: list[Entity] = []
        for spec in specs_fn(topology):
            if spec.key not in seen:
                seen.add(spec.key)
                new_entities.append(entity_factory(coordinator, spec))
        if new_entities:
            async_add_entities(new_entities)

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))
