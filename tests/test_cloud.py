import pytest

from custom_components.pando_hood.client import AuthenticationError, PandoError
from custom_components.pando_hood.cloud import Cloud


class Reply:
    def __init__(self, status, data):
        self.status, self.data = status, data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self.data


class HTTP:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.count = 0

    def request(self, *args, **kwargs):
        self.count += 1
        return next(self.replies)


async def test_expired_session_renews_once_and_returns_devices():
    http = HTTP(
        [
            Reply(200, {"JWT": "old"}),
            Reply(401, {}),
            Reply(200, {"JWT": "new"}),
            Reply(200, [{"uid": "hood", "description": "Kitchen", "capabilities": []}]),
        ]
    )
    cloud = Cloud(http, "user", "secret")
    assert [h.uid for h in await cloud.devices()] == ["hood"]
    assert http.count == 4


async def test_rejected_credentials_do_not_loop_or_expose_response():
    http = HTTP([Reply(401, {"private": "secret"})])
    with pytest.raises(AuthenticationError) as error:
        await Cloud(http, "user", "secret").devices()
    assert "secret" not in str(error.value)
    assert http.count == 1


@pytest.mark.parametrize(
    "device",
    [
        None,
        {
            "uid": "hood",
            "capabilities": [
                {"capabilityUid": "device.fanSpeed", "minValue": 0, "maxValue": 10**500}
            ],
        },
        {"uid": "hood", "capabilities": [{"capabilityUid": "device.fanSpeed"}]},
        {
            "uid": "hood",
            "capabilities": [{"capabilityUid": "device.fanSpeed", "minValue": 4, "maxValue": 0}],
        },
        {
            "uid": "hood",
            "capabilities": [
                {"capabilityUid": "device.fanSpeed", "minValue": 0, "maxValue": float("nan")}
            ],
        },
    ],
)
async def test_invalid_device_metadata_fails_before_entity_or_command_creation(device):
    http = HTTP([Reply(200, {"JWT": "token"}), Reply(200, [device])])
    with pytest.raises(PandoError, match="metadata"):
        await Cloud(http, "user", "secret").devices()


async def test_read_only_and_unknown_capabilities_do_not_require_control_bounds():
    http = HTTP(
        [
            Reply(200, {"JWT": "token"}),
            Reply(
                200,
                [
                    {
                        "uid": "hood",
                        "capabilities": [
                            {"capabilityUid": "device.hoodPower"},
                            {"capabilityUid": "future.readonly"},
                        ],
                    }
                ],
            ),
        ]
    )
    (hood,) = await Cloud(http, "user", "secret").devices()
    assert set(hood.capabilities) == {"device.hoodPower", "future.readonly"}
    assert hood.update({"deviceId": "hood", "values": [{"id": "device.hoodPower", "value": 42}]})
    assert hood.values == {"device.hoodPower": 42}
