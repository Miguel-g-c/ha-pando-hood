"""Correlate HTTPS commands with asynchronous MQTT acknowledgements."""

import asyncio
from uuid import uuid4

from .client import PandoError


class Requests:
    def __init__(self, timeout=20):
        self.timeout = timeout
        self.pending = {}

    async def send(self, uid, command, values, post):
        request_id = str(uuid4())
        key = (uid, request_id)
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        body = {
            "command": command,
            "requestId": request_id,
            "parameters": [{"id": k, "value": v} for k, v in values.items()],
            "deviceType": "smartphone",
        }
        try:
            async with asyncio.timeout(self.timeout):
                await post(uid, body)
                response = await future
                if response.get("status") != 0:
                    raise PandoError("Hood rejected the command")
        except TimeoutError as error:
            raise PandoError(
                "Timed out waiting for hood acknowledgement; result is unknown"
            ) from error
        finally:
            self.pending.pop(key, None)
            # A simultaneous HTTP failure/disconnect must not leave an unobserved future.
            if future.done() and not future.cancelled():
                future.exception()
            else:
                future.cancel()

    def receive(self, uid, request_id, payload):
        future = self.pending.get((uid, request_id))
        if future is not None and not future.done():
            future.set_result(payload)

    def disconnect(self):
        for future in self.pending.values():
            if not future.done():
                future.set_exception(PandoError("MQTT disconnected; command result is unknown"))
