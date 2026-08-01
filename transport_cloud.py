from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Callable

import websockets


class CloudTransport:
    """
    Atlas Cloud Transport

    Replaces UDP with a secure WebSocket connection to the Atlas Cloud.

    Responsibilities
    ----------------
    • Connect to Render
    • Send telemetry
    • Receive commands
    • Automatic reconnect
    • Heartbeat
    """

    def __init__(
        self,
        on_line: Callable[[str], None],
        on_status: Callable[[dict], None],
    ) -> None:

        self._on_line = on_line
        self._on_status = on_status

        self.server_url = "ws://localhost:8000/ws/robot"

        self.robot_name = "atlas-v3"

        self.websocket: websockets.WebSocketClientProtocol | None = None

        self.connected = False

        self.last_error = None

        self.last_message = None

        self.last_ping = 0.0

        self._thread = None

        self._stop_event = threading.Event()

        self._loop = None

    def connect(self, url: str) -> None:

        if self.connected:
            self.disconnect()

        self.server_url = url

        self.last_error = None

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="atlas-cloud",
        )

        self._thread.start()

        self._on_status(self.status())

    def disconnect(self) -> None:

        self._stop_event.set()

        self.connected = False

        self.websocket: websockets.WebSocketClientProtocol | None = None

        self._on_status(self.status())


    def _run_loop(self):

        self._loop = asyncio.new_event_loop()

        asyncio.set_event_loop(self._loop)

        self._loop.run_until_complete(
            self._cloud_loop()
        )

    async def _cloud_loop(self):

        while not self._stop_event.is_set():

            try:

                print(f"[CLOUD] Connecting to {self.server_url}")

                async with websockets.connect(
                    self.server_url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:

                    self.websocket = ws

                    self.connected = True

                    self.last_error = None

                    self._on_status(self.status())

                    print("[CLOUD] Connected")

                    await self._send_hello()

                    await self._receive_loop()

            except Exception as exc:

                self.connected = False

                self.last_error = str(exc)

                self._on_status(self.status())

                print(f"[CLOUD ERROR] {exc}")

                await asyncio.sleep(3)


    async def _send_hello(self):

        hello = {

            "type": "hello",

            "robot": self.robot_name,

            "firmware": "v3",

            "transport": "cloud",

        }

        await self.websocket.send(
            json.dumps(hello)
        )

    async def _receive_loop(self):

        while self.connected and not self._stop_event.is_set():

            try:

                message = await self.websocket.recv()

                self.last_message = time.time()

                packet = json.loads(message)

                self._handle_packet(packet)

            except Exception:

                break

        self.connected = False

        self._on_status(self.status())

    def _handle_packet(self, packet: dict):

        packet_type = packet.get("type")

        if packet_type == "command":

            command = packet.get("command", "").strip()

            if command:

                print(f"[CLOUD COMMAND] {command}")

                self._on_line(f"COMMAND:{command}")

        elif packet_type == "heartbeat":

            self.last_ping = time.time()

        else:

            print(f"[CLOUD] Unknown packet: {packet}")


    async def send_telemetry(self, line: str):

        if not self.connected:

            return

        packet = {

            "type": "telemetry",

            "line": line,

        }

        await self.websocket.send(

            json.dumps(packet)

        )

    def send_command(self, command: str):

        asyncio.run_coroutine_threadsafe(

            self._send_command(command),

            self._loop,

        )

    async def _send_command(self, command: str):

        if not self.connected:

            return

        packet = {

            "type": "command",

            "command": command,

        }

        await self.websocket.send(

            json.dumps(packet)

        )

    async def send_heartbeat(self):

        if not self.connected:

            return

        packet = {

            "type": "heartbeat"

        }

        await self.websocket.send(

            json.dumps(packet)

        )

    def status(self):

        return {

            "connected": self.connected,

            "server": self.server_url,

            "robot": self.robot_name,

            "last_error": self.last_error,

            "last_ping": self.last_ping,

            "last_message": self.last_message,

        }