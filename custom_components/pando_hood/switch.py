"""Overall hood power and air-clean mode."""

from homeassistant.components.switch import SwitchEntity

from .entity import PandoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities(
        [
            PandoSwitch(c, key, name)
            for key, name in (("device.onOff", "Power"), ("device.cleanAirEnabled", "Air clean"))
            if key in c.hood.capabilities
        ]
    )


class PandoSwitch(PandoEntity, SwitchEntity):
    @property
    def is_on(self):
        return bool(self.value)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.set_values({self.key: 1})

    async def async_turn_off(self, **kwargs):
        await self.coordinator.set_values({self.key: 0})
