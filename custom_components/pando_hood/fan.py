"""Hood motor control; switching off preserves the light."""

import math

from homeassistant.components.fan import FanEntity, FanEntityFeature

from .entity import PandoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if "device.fanSpeed" in entry.runtime_data.hood.capabilities:
        async_add_entities([PandoFan(entry.runtime_data)])


class PandoFan(PandoEntity, FanEntity):
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator):
        super().__init__(coordinator, "device.fanSpeed", "Motor")
        self._attr_speed_count = coordinator.hood.bounds_for(self.key).maximum
        self.last_speed = 1

    @property
    # HA exposes this as a writable cached_property; live state needs a property.
    def percentage(self):  # ty: ignore[invalid-property-type-override]
        if self.value is None:
            return None
        return round(self.value * 100 / self._attr_speed_count)

    @property
    def is_on(self):
        return self.value is not None and self.value > 0

    async def async_set_percentage(self, percentage):
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        speed = math.ceil(percentage * self._attr_speed_count / 100)
        await self.coordinator.set_values({self.key: speed})
        if speed:
            self.last_speed = speed

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        await self.async_set_percentage(
            percentage if percentage is not None else self.last_speed * 100 / self._attr_speed_count
        )

    async def async_turn_off(self, **kwargs):
        if self.value:
            self.last_speed = int(self.value)
        await self.async_set_percentage(0)
