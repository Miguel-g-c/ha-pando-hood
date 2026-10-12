import pytest

from custom_components.pando_hood.client import Hood, PandoError
from tools.live_check import light_check


class Remote:
    def __init__(self, fail=False):
        self.light = 0
        self.sent = []
        self.fail = fail

    async def refresh(self, uid):
        return {"device.lightOnOff": self.light}

    async def command(self, uid, command, values):
        self.light = values["device.lightOnOff"]
        self.sent.append(self.light)
        if self.fail:
            self.fail = False
            raise PandoError("Acknowledgement lost after command took effect")


@pytest.mark.parametrize("fail", [False, True])
async def test_light_diagnostic_restores_initial_state_even_after_ambiguous_failure(fail):
    hood = Hood("test", "Hood", {"device.lightOnOff": {"minValue": 0, "maxValue": 1}})
    remote = Remote(fail)
    if fail:
        with pytest.raises(PandoError):
            await light_check(hood, remote, settle_time=0)
    else:
        assert await light_check(hood, remote, settle_time=0)
    assert remote.light == 0 and remote.sent == [1, 0]
