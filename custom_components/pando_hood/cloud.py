"""Pando HTTPS + MQTT transport, independent of Home Assistant."""

import asyncio
import contextlib
import json
from urllib.parse import quote
from uuid import uuid4

import aiohttp
import aiomqtt

from .client import AuthenticationError, Hood, PandoError
from .requests import Requests
from .tls import mqtt_context

HOST = "pando.iotpga.it"
BASE = f"https://{HOST}"


class Cloud:
    def __init__(self, session, email, password, fingerprint="", *, mqtt_factory=None):
        self.session, self.email, self.password = session, email, password
        self.fingerprint = fingerprint
        self.mqtt_factory = mqtt_factory or aiomqtt.Client
        self.token = None
        self.login_lock = asyncio.Lock()
        self.requests = Requests()
        self.ready = asyncio.Event()
        self.states = {}
        self.task = None
        self.hoods = {}
        self.on_state = lambda uid: None
        self.on_disconnect = lambda: None
        self.failure = None
        self.closing = False

    async def login(self):
        data = await self._http(
            "POST",
            "/users/login",
            {"email": self.email, "password": self.password},
            authenticated=False,
        )
        if not isinstance(data, dict) or not isinstance(data.get("JWT"), str) or not data["JWT"]:
            raise PandoError("Unexpected login response")
        self.token = data["JWT"]

    async def _http(self, method, path, body=None, *, authenticated=True):
        if authenticated and self.token is None:
            async with self.login_lock:
                if self.token is None:
                    await self.login()
        for attempt in range(2):
            token = self.token
            headers = {"Accept": "application/json"}
            if authenticated:
                headers["Authorization"] = f"Bearer {token}"
            try:
                async with self.session.request(
                    method,
                    BASE + path,
                    json=body,
                    headers=headers,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    status = response.status
                    if status not in (401, 403):
                        if not 200 <= status < 300:
                            raise PandoError(f"Pando HTTP {status}; command result may be unknown")
                        if status == 204 or path.endswith("/set_value"):
                            return None
                        return await response.json()
            except (aiohttp.ClientError, TimeoutError, ValueError) as error:
                raise PandoError(
                    "Pando HTTPS request failed; command result may be unknown"
                ) from error
            if not authenticated or attempt:
                raise AuthenticationError("Pando credentials rejected")
            async with self.login_lock:
                if self.token == token:
                    await self.login()
        raise AuthenticationError("Pando credentials rejected")

    async def devices(self):
        data = await self._http("GET", "/devices/")
        if not isinstance(data, list):
            raise PandoError("Unexpected device response")
        try:
            return [
                Hood(
                    d["uid"],
                    d.get("description") or "Pando hood",
                    {c["capabilityUid"]: c for c in d["capabilities"]},
                )
                for d in data
                if d.get("enable", True)
            ]
        except (KeyError, TypeError) as error:
            raise PandoError("Unexpected device metadata") from error

    async def start(self, hoods, on_state, on_disconnect):
        self.closing = False
        self.hoods = {h.uid: h for h in hoods}
        self.states = {h.uid: asyncio.Event() for h in hoods}
        self.on_state, self.on_disconnect = on_state, on_disconnect
        self.task = asyncio.create_task(self._listen(), name="pando-mqtt")
        try:
            async with asyncio.timeout(25):
                while not self.ready.is_set():
                    if self.failure:
                        raise self.failure
                    await asyncio.sleep(0.1)
        except (TimeoutError, PandoError):
            await self.close()
            raise self.failure or PandoError(
                "MQTT connection timed out; check certificate settings"
            )

    async def _listen(self):
        delay = 1
        # Certificate loading can block; never do it on HA's event loop.
        context = await asyncio.to_thread(mqtt_context, self.fingerprint)
        while True:
            try:
                async with self.mqtt_factory(
                    HOST,
                    8883,
                    username=self.email,
                    password=self.password,
                    identifier=f"pando-ha-{uuid4().hex[:16]}",
                    tls_context=context,
                    tls_insecure=bool(self.fingerprint),
                    protocol=aiomqtt.ProtocolVersion.V311,
                    timeout=15,
                    max_queued_incoming_messages=256,
                ) as mqtt:
                    for uid in self.hoods:
                        await mqtt.subscribe(f"root/pando/devices/{uid}/status")
                        await mqtt.subscribe(f"root/pando/devices/{uid}/response/#")
                    delay = 1
                    self.failure = None
                    self.ready.set()
                    async for message in mqtt.messages:
                        if not message.retain:
                            self.receive(str(message.topic), bytes(message.payload))
            except aiomqtt.MqttError as error:
                if isinstance(error, aiomqtt.MqttCodeError) and error.rc in (4, 5):
                    self.failure = AuthenticationError("Pando MQTT credentials rejected")
                else:
                    self.failure = PandoError("MQTT connection failed; check certificate settings")
            finally:
                self.ready.clear()
                self.requests.disconnect()
                if not self.closing:
                    self.on_disconnect()
            if isinstance(self.failure, AuthenticationError):
                return
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    def receive(self, topic, payload):
        parts = topic.split("/")
        if len(parts) not in (5, 6) or parts[:3] != ["root", "pando", "devices"]:
            return
        uid = parts[3]
        if uid not in self.hoods:
            return
        try:
            data = json.loads(payload)
            if not isinstance(data, dict):
                return
        except (ValueError, UnicodeDecodeError):
            return
        if parts[4] == "response" and len(parts) == 6:
            self.requests.receive(uid, parts[5], data)
        elif parts[4] == "status" and len(parts) == 5 and self.hoods[uid].update(data):
            self.states[uid].set()
            self.on_state(uid)

    async def command(self, uid, command, values):
        if not self.ready.is_set() or uid not in self.hoods:
            raise PandoError("Hood connection is unavailable")

        async def post(device, body):
            await self._http("POST", f"/devices/{quote(device, safe='')}/set_value", body)

        await self.requests.send(uid, command, values, post)

    async def refresh(self, uid):
        self.states[uid].clear()
        await self.command(uid, "getStatus", {})
        try:
            async with asyncio.timeout(20):
                await self.states[uid].wait()
        except TimeoutError as error:
            raise PandoError("No fresh hood state received") from error
        return dict(self.hoods[uid].values)

    async def close(self):
        self.closing = True
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        self.ready.clear()
        self.requests.disconnect()
