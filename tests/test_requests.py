import pytest

from custom_components.pando_hood.client import PandoError
from custom_components.pando_hood.requests import Requests


async def test_ack_can_arrive_before_https_returns_and_does_not_change_state():
    requests = Requests(timeout=0.1)

    async def post(uid, body):
        requests.receive("unrelated", body["requestId"], {"status": 0})
        requests.receive(uid, body["requestId"], {"status": 0})

    await requests.send("hood", "setValue", {"device.lightOnOff": 1}, post)


async def test_rejected_missing_and_disconnected_acknowledgements_fail_commands():
    for mode in ("rejected", "missing", "disconnect"):
        requests = Requests(timeout=0.01)

        async def post(uid, body):
            if mode == "rejected":
                requests.receive(uid, body["requestId"], {"status": 1})
            if mode == "disconnect":
                requests.disconnect()

        with pytest.raises(PandoError):
            await requests.send("hood", "setValue", {"device.lightOnOff": 1}, post)
