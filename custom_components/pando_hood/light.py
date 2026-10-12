"""Dimmable, tunable-white hood light."""

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)

from .entity import PandoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if "device.lightOnOff" in entry.runtime_data.hood.capabilities:
        async_add_entities([PandoLight(entry.runtime_data)])


class PandoLight(PandoEntity, LightEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "device.lightOnOff", "Light")
        caps = coordinator.hood.capabilities
        if "device.lightColorTemperature" in caps:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            spec = coordinator.hood.bounds_for("device.lightColorTemperature")
            self._attr_min_color_temp_kelvin, self._attr_max_color_temp_kelvin = (
                spec.minimum,
                spec.maximum,
            )
        elif "device.lightBrightness" in caps:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = next(iter(self._attr_supported_color_modes))

    @property
    # HA exposes this as a writable cached_property; live state needs a property.
    def is_on(self):  # ty: ignore[invalid-property-type-override]
        return bool(self.value)

    @property
    # HA exposes this as a writable cached_property; live state needs a property.
    def brightness(self):  # ty: ignore[invalid-property-type-override]
        value = (self.coordinator.data or {}).get("device.lightBrightness")
        return round(value * 255 / 100) if value is not None else None

    @property
    def color_temp_kelvin(self):
        return (self.coordinator.data or {}).get("device.lightColorTemperature")

    async def async_turn_on(self, **kwargs):
        if kwargs.get(ATTR_BRIGHTNESS) == 0:
            await self.async_turn_off()
            return
        values = {self.key: 1}
        if ATTR_BRIGHTNESS in kwargs:
            spec = self.coordinator.hood.bounds_for("device.lightBrightness")
            values["device.lightBrightness"] = max(
                spec.minimum,
                min(spec.maximum, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)),
            )
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            values["device.lightColorTemperature"] = int(kwargs[ATTR_COLOR_TEMP_KELVIN])
        await self.coordinator.set_values(values)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.set_values({self.key: 0})
