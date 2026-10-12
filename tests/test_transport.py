import asyncio
import json
from types import SimpleNamespace

import aiomqtt
import pytest
from test_cloud import Reply

from custom_components.pando_hood import cloud as cloud_module
from custom_components.pando_hood.client import AuthenticationError, PandoError
from custom_components.pando_hood.cloud import Cloud


class Broker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.subscriptions = set()
        self.connections = asyncio.Queue()

    async def __aenter__(self):
        self.connections.put_nowait(None)
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
            item = await self.queue.get()
            if isinstance(item, Exception):
                raise item
            yield item

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


async def test_tls_startup_failure_is_reported_promptly_and_close_is_safe(monkeypatch):
    def failed_context(fingerprint):
        raise ValueError("private TLS detail")

    monkeypatch.setattr(cloud_module, "mqtt_context", failed_context)
    broker = Broker()
    cloud = Cloud(HTTP(broker), "user", "secret", mqtt_factory=lambda *a, **kw: broker)
    hoods = await cloud.devices()
    with pytest.raises(PandoError, match="MQTT") as error:
        async with asyncio.timeout(1):
            await cloud.start(hoods, lambda uid: None, lambda: None)
    assert "private TLS detail" not in str(error.value)
    await cloud.close()
    await cloud.close()
    assert not cloud.ready.is_set()


@pytest.mark.parametrize(
    "failure", [RuntimeError("private broker detail"), aiomqtt.MqttCodeError(4)]
)
async def test_broker_startup_failures_keep_authentication_distinct_and_cleanup(failure):
    class FailedBroker(Broker):
        async def __aenter__(self):
            raise failure

    broker = FailedBroker()
    cloud = Cloud(HTTP(broker), "user", "secret", mqtt_factory=lambda *a, **kw: broker)
    hoods = await cloud.devices()
    with pytest.raises(PandoError) as error:
        async with asyncio.timeout(1):
            await cloud.start(hoods, lambda uid: None, lambda: None)
    assert isinstance(error.value, AuthenticationError) == isinstance(
        failure, aiomqtt.MqttCodeError
    )
    assert "private broker detail" not in str(error.value)
    await cloud.close()
    assert not cloud.ready.is_set()


async def test_disconnect_reconnects_and_resumes_fresh_state():
    broker = Broker()
    cloud = Cloud(HTTP(broker), "user", "secret", mqtt_factory=lambda *a, **kw: broker)
    disconnected = asyncio.Event()
    await cloud.start(await cloud.devices(), lambda uid: None, disconnected.set)
    try:
        await broker.connections.get()
        broker.queue.put_nowait(aiomqtt.MqttError("connection lost"))
        async with asyncio.timeout(3):
            await disconnected.wait()
            assert not cloud.ready.is_set()
            await broker.connections.get()
            assert (await cloud.refresh("test"))["device.fanSpeed"] == 2
    finally:
        await cloud.close()


async def test_cancelled_startup_closes_listener_and_preserves_cancellation():
    entering = asyncio.Event()
    exited = asyncio.Event()

    class WaitingBroker(Broker):
        async def __aenter__(self):
            entering.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()

    broker = WaitingBroker()
    cloud = Cloud(HTTP(broker), "user", "secret", mqtt_factory=lambda *a, **kw: broker)
    task = asyncio.create_task(cloud.start(await cloud.devices(), lambda uid: None, lambda: None))
    async with asyncio.timeout(1):
        await entering.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert exited.is_set()
    assert not cloud.ready.is_set()
    await cloud.close()
