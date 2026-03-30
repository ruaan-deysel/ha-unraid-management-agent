"""Repair flows for Unraid Management Agent integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import UnraidDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for an issue."""
    if issue_id.startswith("connection_"):
        return ConnectionIssueRepairFlow(hass, issue_id, data)
    if issue_id.startswith("disk_health_"):
        return DiskHealthRepairFlow(hass, issue_id, data)
    if issue_id.startswith("array_"):
        return ArrayIssueRepairFlow(hass, issue_id, data)
    if issue_id.startswith("parity_"):
        return ParityCheckRepairFlow(hass, issue_id, data)
    return RepairsFlow()


class ConnectionIssueRepairFlow(RepairsFlow):
    """Handler for connection issue repairs."""

    def __init__(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self.hass = hass
        self.issue_id = issue_id
        self.data = data or {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Mark issue as resolved
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return self.async_create_entry(title="", data={})

        data = self.data or {}
        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "error": str(data.get("error", "Unknown error")),
                "host": str(data.get("host", "Unknown")),
                "port": str(data.get("port", "Unknown")),
            },
        )


class DiskHealthRepairFlow(RepairsFlow):
    """Handler for disk health issue repairs."""

    def __init__(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self.hass = hass
        self.issue_id = issue_id
        self.data = data or {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Mark issue as resolved
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return self.async_create_entry(title="", data={})

        data = self.data or {}
        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "disk_name": str(data.get("disk_name", "Unknown")),
                "smart_status": str(data.get("smart_status", "Unknown")),
                "smart_errors": str(data.get("smart_errors", 0)),
                "temperature": str(data.get("temperature", "Unknown")),
            },
        )


class ArrayIssueRepairFlow(RepairsFlow):
    """Handler for array issue repairs."""

    def __init__(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self.hass = hass
        self.issue_id = issue_id
        self.data = data or {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Mark issue as resolved
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return self.async_create_entry(title="", data={})

        data = self.data or {}
        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "array_state": str(data.get("array_state", "Unknown")),
                "issue_description": str(
                    data.get("issue_description", "Unknown issue")
                ),
            },
        )


class ParityCheckRepairFlow(RepairsFlow):
    """Handler for parity check issue repairs."""

    def __init__(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self.hass = hass
        self.issue_id = issue_id
        self.data = data or {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Mark issue as resolved
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return self.async_create_entry(title="", data={})

        data = self.data or {}
        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "parity_status": str(data.get("parity_status", "Unknown")),
                "sync_percent": str(data.get("sync_percent", 0)),
                "errors_found": str(data.get("errors_found", 0)),
            },
        )


async def async_check_and_create_issues(
    hass: HomeAssistant, coordinator: UnraidDataUpdateCoordinator
) -> None:
    """Check for issues and create repair flows if needed."""
    entry_id = coordinator.config_entry.entry_id

    # Check for connection issues
    if not coordinator.last_update_success:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"connection_{entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="connection_failed",
            translation_placeholders={
                "host": coordinator.config_entry.data.get("host", "Unknown"),
                "port": str(coordinator.config_entry.data.get("port", "Unknown")),
                "error": (
                    str(coordinator.last_exception)
                    if coordinator.last_exception
                    else "Unknown error"
                ),
            },
        )
    else:
        # Connection is successful, remove any existing connection issue
        ir.async_delete_issue(hass, DOMAIN, f"connection_{entry_id}")

    # Skip further checks if coordinator data is not available
    if not coordinator.data:
        return

    # Get disk settings for temperature thresholds
    disk_settings = coordinator.data.disk_settings

    # Check for disk health issues
    disks = coordinator.data.disks or []
    for disk in disks:
        disk_id = getattr(disk, "id", None) or getattr(disk, "name", None) or "unknown"

        # Check for SMART errors using library property
        smart_issue_id = f"disk_health_{disk_id}_smart_errors"
        if getattr(disk, "has_smart_errors", False):
            smart_errors = getattr(disk, "smart_errors", 0) or 0
            smart_status = getattr(disk, "smart_status", None) or "UNKNOWN"
            ir.async_create_issue(
                hass,
                DOMAIN,
                smart_issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="disk_smart_errors",
                translation_placeholders={
                    "disk_name": getattr(disk, "name", None) or disk_id,
                    "smart_errors": str(int(smart_errors)),
                    "smart_status": smart_status,
                },
            )
        else:
            # No SMART errors, remove any existing issue
            ir.async_delete_issue(hass, DOMAIN, smart_issue_id)

        # Get temperature status using library method
        temp_warning_issue_id = f"disk_health_{disk_id}_high_temp"
        temp_critical_issue_id = f"disk_health_{disk_id}_critical_temp"

        temp_status = disk.temperature_status(disk_settings)
        temperature = getattr(disk, "temperature_celsius", None) or 0

        if temp_status == "critical":
            warning_threshold, critical_threshold = disk.get_temp_thresholds(
                disk_settings
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                temp_critical_issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="disk_critical_temperature",
                translation_placeholders={
                    "disk_name": getattr(disk, "name", None) or disk_id,
                    "temperature": str(int(temperature)),
                    "threshold": str(critical_threshold) if critical_threshold else "?",
                },
            )
            # Remove warning issue if critical is active
            ir.async_delete_issue(hass, DOMAIN, temp_warning_issue_id)
        elif temp_status == "warning":
            warning_threshold, _critical_threshold = disk.get_temp_thresholds(
                disk_settings
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                temp_warning_issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="disk_high_temperature",
                translation_placeholders={
                    "disk_name": getattr(disk, "name", None) or disk_id,
                    "temperature": str(int(temperature)),
                    "threshold": str(warning_threshold) if warning_threshold else "?",
                },
            )
            # Remove critical issue if only warning
            ir.async_delete_issue(hass, DOMAIN, temp_critical_issue_id)
        else:
            # Temperature is normal, remove any existing issues
            ir.async_delete_issue(hass, DOMAIN, temp_warning_issue_id)
            ir.async_delete_issue(hass, DOMAIN, temp_critical_issue_id)

    # Check for array issues (only if parity disks are configured)
    array_data = coordinator.data.array
    num_parity_disks = (
        getattr(array_data, "num_parity_disks", None) if array_data else None
    )
    has_parity = num_parity_disks is not None and num_parity_disks > 0
    # Be strict about parity_valid - only consider it invalid if explicitly False
    # None, missing, or any other value should be treated as valid/unknown
    # Also skip if there are no parity disks (pools-only setups)
    parity_valid = getattr(array_data, "parity_valid", None) if array_data else None
    parity_issue_id = f"array_parity_invalid_{entry_id}"

    if has_parity and parity_valid is False:
        ir.async_create_issue(
            hass,
            DOMAIN,
            parity_issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="array_parity_invalid",
            translation_placeholders={
                "array_state": str(array_data.state)
                if array_data and array_data.state
                else "Unknown",
            },
        )
    else:
        # Parity is valid or unknown, remove any existing issue
        ir.async_delete_issue(hass, DOMAIN, parity_issue_id)

    # Check for parity check issues
    stuck_issue_id = f"parity_check_stuck_{entry_id}"

    if array_data and getattr(array_data, "is_parity_check_stuck", False):
        ir.async_create_issue(
            hass,
            DOMAIN,
            stuck_issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="parity_check_stuck",
            translation_placeholders={
                "sync_percent": str(
                    getattr(array_data, "parity_check_progress", 0) or 0
                ),
            },
        )
    else:
        # Parity check is not stuck, remove any existing issue
        ir.async_delete_issue(hass, DOMAIN, stuck_issue_id)
