"""Transport-neutral hood model. No Home Assistant imports."""

import math
from dataclasses import dataclass, field
from typing import Any, Protocol


class PandoError(Exception):
    """Cloud/protocol failure safe to display without response bodies."""


class AuthenticationError(PandoError):
    """Credentials rejected."""


class Transport(Protocol):
    async def command(self, uid: str, command: str, values: dict[str, Any]) -> None: ...


@dataclass
class Hood:
    uid: str
    name: str
    capabilities: dict[str, dict]
    values: dict[str, Any] = field(default_factory=dict)

    def update(self, payload: dict) -> bool:
        if payload.get("deviceId") != self.uid or not isinstance(payload.get("values"), list):
            return False
        updated = False
        for item in payload["values"]:
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

    async def set_values(self, transport: Transport, values: dict) -> None:
        writable = {
            "device.onOff",
            "device.fanSpeed",
            "device.lightOnOff",
            "device.lightBrightness",
            "device.lightColorTemperature",
            "device.cleanAirEnabled",
        }
        if not values:
            raise ValueError("Empty command")
        for key, value in values.items():
            spec = self.capabilities.get(key)
            if key not in writable or spec is None:
                raise ValueError("Capability is unsupported or read-only")
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or int(value) != value
            ):
                raise ValueError("Command values must be finite integers")
            if not spec["minValue"] <= value <= spec["maxValue"]:
                raise ValueError("Command value outside device range")
        await transport.command(
            self.uid, "setValue", {key: int(value) for key, value in values.items()}
        )
