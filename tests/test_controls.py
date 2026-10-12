import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN

from custom_components.pando_hood.client import Hood
from custom_components.pando_hood.fan import PandoFan
from custom_components.pando_hood.light import PandoLight


class Coordinator:
    def __init__(self):
        self.hood = Hood(
            "test",
            "Hood",
            {
                "device.fanSpeed": {"maxValue": 4},
                "device.lightOnOff": {},
                "device.lightBrightness": {"minValue": 10, "maxValue": 100},
                "device.lightColorTemperature": {"minValue": 2700, "maxValue": 6000},
            },
        )
        self.data = {"device.fanSpeed": 3, "device.lightOnOff": 1}
        self.sent = []
        self.last_update_success = True

    async def set_values(self, values):
        self.sent.append(values)


@pytest.mark.asyncio
async def test_motor_off_leaves_light_alone_and_speed_percentages_match_four_steps():
    c = Coordinator()
    fan = PandoFan(c)
    assert fan.percentage == 75
    await fan.async_turn_off()
    await fan.async_set_percentage(26)
    assert c.sent == [{"device.fanSpeed": 0}, {"device.fanSpeed": 2}]
    assert c.data["device.lightOnOff"] == 1


@pytest.mark.asyncio
async def test_light_clamps_low_brightness_and_zero_turns_it_off():
    c = Coordinator()
    light = PandoLight(c)
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 1, ATTR_COLOR_TEMP_KELVIN: 6000})
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 0})
    assert c.sent == [
        {
            "device.lightOnOff": 1,
            "device.lightBrightness": 10,
            "device.lightColorTemperature": 6000,
        },
        {"device.lightOnOff": 0},
    ]
