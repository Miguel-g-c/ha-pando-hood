import pytest

from custom_components.pando_hood.client import Hood


class Network:
    def __init__(self):
        self.sent = []

    async def command(self, uid, command, values):
        self.sent.append((uid, command, values))


async def test_invalid_or_read_only_command_never_reaches_hood():
    hood = Hood(
        "test",
        "Hood",
        {
            "device.fanSpeed": {"minValue": 0, "maxValue": 4},
            "device.hoodPower": {"minValue": 0, "maxValue": 1000},
        },
    )
    network = Network()
    for values in (
        {"device.fanSpeed": 5},
        {"device.fanSpeed": 1.5},
        {"device.hoodPower": 10},
        {"device.fanSpeed": float("nan")},
    ):
        with pytest.raises(ValueError):
            await hood.set_values(network, values)
    assert not network.sent


def test_partial_push_preserves_other_state_and_ignores_other_devices():
    hood = Hood("test", "Hood", {"device.fanSpeed": {}, "device.lightOnOff": {}})
    assert hood.update(
        {
            "deviceId": "test",
            "values": [
                {"id": "device.fanSpeed", "value": 2},
                {"id": "device.lightOnOff", "value": 1},
            ],
        }
    )
    hood.update({"deviceId": "test", "values": [{"id": "device.fanSpeed", "value": 0}]})
    assert hood.values == {"device.fanSpeed": 0, "device.lightOnOff": 1}
    assert not hood.update(
        {"deviceId": "another", "values": [{"id": "device.lightOnOff", "value": 0}]}
    )
    assert hood.values["device.lightOnOff"] == 1
