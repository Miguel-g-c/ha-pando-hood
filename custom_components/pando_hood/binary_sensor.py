"""Reported filter maintenance indicators."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import PandoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities(
        [
            PandoFilter(c, key, name)
            for key, name in (
                ("device.filter1.worn", "Filter 1 needs cleaning"),
                ("device.filter2.worn", "Filter 2 needs cleaning"),
            )
            if key in c.hood.capabilities
        ]
    )


class PandoFilter(PandoEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        return bool(self.value)
