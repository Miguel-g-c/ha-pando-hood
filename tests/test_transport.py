import asyncio
import json
from types import SimpleNamespace

from test_cloud import Reply

from custom_components.pando_hood.cloud import Cloud


class Broker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.subscriptions = set()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def subscribe(self, topic):
        self.subscriptions.add(topic)

    @property
    def messages(self):
        return self.stream()

    async def stream(self):
        while True:
            yield await self.queue.get()

    def incoming(self, topic, payload):
        self.queue.put_nowait(
            SimpleNamespace(topic=topic, payload=json.dumps(payload).encode(), retain=False)
        )


class HTTP:
    def __init__(self, broker):
        self.broker = broker
        self.speed = 2

    def request(self, method, url, **kwargs):
        if url.endswith("/users/login"):
            return Reply(200, {"JWT": "test-token"})
        if url.endswith("/devices/"):
            return Reply(
                200,
                [
                    {
                        "uid": "test",
                        "description": "Hood",
                        "capabilities": [
                            {"capabilityUid": "device.fanSpeed", "minValue": 0, "maxValue": 4}
                        ],
                    }
                ],
            )
        body = kwargs["json"]
        if body["command"] == "getStatus":
            self.broker.incoming(
                "root/pando/devices/test/status",
                {"deviceId": "test", "values": [{"id": "device.fanSpeed", "value": self.speed}]},
            )
        else:
            self.speed = body["parameters"][0]["value"]
        self.broker.incoming("root/pando/devices/test/response/" + body["requestId"], {"status": 0})
        return Reply(204, None)


async def test_fresh_state_and_command_ack_are_distinct_across_the_real_transport():
    broker = Broker()
    cloud = Cloud(HTTP(broker), "user", "secret", mqtt_factory=lambda *a, **kw: broker)
    hoods = await cloud.devices()
    pushed = []
    await cloud.start(hoods, lambda uid: pushed.append(uid), lambda: None)
    try:
        assert (await cloud.refresh("test"))["device.fanSpeed"] == 2
        await hoods[0].set_values(cloud, {"device.fanSpeed": 0})
        assert hoods[0].values["device.fanSpeed"] == 2  # ACK alone never guesses state.
        assert (await cloud.refresh("test"))["device.fanSpeed"] == 0
        assert pushed == ["test", "test"]
    finally:
        await cloud.close()
    assert not cloud.ready.is_set()


async def test_malformed_status_item_does_not_stop_later_state_updates():
    broker = Broker()
    cloud = Cloud(HTTP(broker), "user", "secret", mqtt_factory=lambda *a, **kw: broker)
    hoods = await cloud.devices()
    await cloud.start(hoods, lambda uid: None, lambda: None)
    try:
        broker.incoming(
            "root/pando/devices/test/status",
            {"deviceId": "test", "values": [{"id": [], "value": 1}, {"id": {}, "value": 2}]},
        )
        async with asyncio.timeout(1):
            assert (await cloud.refresh("test"))["device.fanSpeed"] == 2
    finally:
        await cloud.close()
