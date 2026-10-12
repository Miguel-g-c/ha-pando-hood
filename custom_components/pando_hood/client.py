"""Transport-neutral hood model. No Home Assistant imports."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


class PandoError(Exception):
    """Cloud/protocol failure safe to display without response bodies."""


class AuthenticationError(PandoError):
    """Credentials rejected."""


type State = dict[str, int | float]
type CommandValues = dict[str, int]
WRITABLE = frozenset(
    {
        "device.onOff",
        "device.fanSpeed",
        "device.lightOnOff",
        "device.lightBrightness",
        "device.lightColorTemperature",
        "device.cleanAirEnabled",
    }
)


@dataclass(frozen=True)
class Bounds:
    minimum: int
    maximum: int


class Transport(Protocol):
    async def command(self, uid: str, command: str, values: CommandValues) -> None: ...


@dataclass
class Hood:
    uid: str
    name: str
    capabilities: dict[str, Bounds | None]
    values: State = field(default_factory=dict)

    def update(self, payload: Mapping[str, object]) -> bool:
        reported = payload.get("values")
        if payload.get("deviceId") != self.uid or not isinstance(reported, list):
            return False
        updated = False
        for item in reported:
            if not isinstance(item, dict):
                continue
            key, value = item.get("id"), item.get("value")
            if (
                isinstance(key, str)
                and key in self.capabilities
                and isinstance(value, (int, float))
                and math.isfinite(value)
            ):
                self.values[key] = value
                updated = True
        return updated

    def bounds_for(self, key: str) -> Bounds:
        bounds = self.capabilities.get(key)
        if key not in WRITABLE or bounds is None:
            raise ValueError("Capability is unsupported or read-only")
        return bounds

    async def set_values(self, transport: Transport, values: Mapping[str, int | float]) -> None:
        if not values:
            raise ValueError("Empty command")
        for key, value in values.items():
            bounds = self.bounds_for(key)
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or int(value) != value
            ):
                raise ValueError("Command values must be finite integers")
            if not bounds.minimum <= value <= bounds.maximum:
                raise ValueError("Command value outside device range")
        await transport.command(
            self.uid, "setValue", {key: int(value) for key, value in values.items()}
        )


def parse_hoods(payload: object) -> list[Hood]:
    """Validate untrusted metadata once; retain only names and usable control bounds."""
    if not isinstance(payload, list):
        raise PandoError("Unexpected device metadata")
    hoods = []
    for device in payload:
        if not isinstance(device, dict):
            raise PandoError("Unexpected device metadata")
        if not device.get("enable", True):
            continue
        uid = device.get("uid")
        name = device.get("description") or "Pando hood"
        specs = device.get("capabilities")
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(name, str)
            or not isinstance(specs, list)
        ):
            raise PandoError("Unexpected device metadata")
        capabilities: dict[str, Bounds | None] = {}
        for spec in specs:
            if not isinstance(spec, dict) or not isinstance(spec.get("capabilityUid"), str):
                raise PandoError("Unexpected device metadata")
            key = spec["capabilityUid"]
            bounds = None
            if key in WRITABLE:
                minimum = _metadata_bound(spec.get("minValue"))
                maximum = _metadata_bound(spec.get("maxValue"))
                if minimum > maximum or (
                    key == "device.fanSpeed" and (minimum != 0 or maximum <= 0)
                ):
                    raise PandoError("Unexpected control bounds in device metadata")
                bounds = Bounds(minimum, maximum)
            capabilities[key] = bounds
        hoods.append(Hood(uid, name, capabilities))
    return hoods


def _metadata_bound(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PandoError("Unexpected control bounds in device metadata")
    try:
        if not math.isfinite(value) or int(value) != value:
            raise PandoError("Unexpected control bounds in device metadata")
    except OverflowError as error:
        raise PandoError("Unexpected control bounds in device metadata") from error
    return int(value)
