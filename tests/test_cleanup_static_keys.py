"""Guard: static entity keys must never look like stale dynamic keys."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from homeassistant.helpers.entity import EntityDescription

from custom_components.unraid_management_agent import (
    binary_sensor,
    button,
    number,
    sensor,
    switch,
)
from custom_components.unraid_management_agent.cleanup import (
    _ALWAYS_VALID_KEYS,
    _DYNAMIC_KEY_PREFIXES,
    _build_valid_dynamic_entity_keys,
)
from custom_components.unraid_management_agent.coordinator import UnraidData

# Description tuples whose keys are only ever used inside a per-item key
# (e.g. vm_<id>_<key>), never as a whole unique-ID key.
_PER_ITEM_DESCRIPTIONS = {"VM_SENSOR_DESCRIPTIONS", "NUT_DEVICE_SENSOR_DESCRIPTIONS"}


def _static_description_keys() -> Iterator[tuple[str, str]]:
    for module in (binary_sensor, button, number, sensor, switch):
        for name, value in vars(module).items():
            if not name.endswith("_DESCRIPTIONS") or name in _PER_ITEM_DESCRIPTIONS:
                continue
            for description in value:
                if isinstance(description, EntityDescription):
                    yield (
                        f"{module.__name__.rsplit('.', 1)[-1]}.{name}",
                        description.key,
                    )


@pytest.mark.parametrize(("where", "key"), list(_static_description_keys()))
def test_static_key_is_not_treated_as_stale(where: str, key: str) -> None:
    """A static key that starts with a dynamic prefix must be allowlisted."""
    if key.startswith(_DYNAMIC_KEY_PREFIXES):
        assert key in _ALWAYS_VALID_KEYS, (
            f"{where} key {key!r} starts with a dynamic prefix and would be "
            "removed by stale cleanup; add it to _ALWAYS_VALID_KEYS"
        )


def test_container_updates_sensor_survives_cleanup() -> None:
    """The Container Updates Available sensor is valid even with no containers."""
    assert "container_updates_available" in _build_valid_dynamic_entity_keys(
        UnraidData(containers=[])
    )
