"""Correlate HTTPS commands with asynchronous MQTT acknowledgements."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from uuid import uuid4

from .client import CommandValues, PandoError


class Requests:
    def __init__(self, timeout: float = 20) -> None:
        self.timeout = timeout
        self.pending: dict[tuple[str, str], asyncio.Future[Mapping[str, object]]] = {}

    async def send(
        self,
        uid: str,
        command: str,
        values: CommandValues,
        post: Callable[[str, dict[str, object]], Awaitable[None]],
    ) -> None:
        request_id = str(uuid4())
        key = (uid, request_id)
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        body: dict[str, object] = {
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

    def receive(self, uid: str, request_id: str, payload: Mapping[str, object]) -> None:
        future = self.pending.get((uid, request_id))
        if future is not None and not future.done():
            future.set_result(payload)

    def disconnect(self) -> None:
        for future in self.pending.values():
            if not future.done():
                future.set_exception(PandoError("MQTT disconnected; command result is unknown"))
