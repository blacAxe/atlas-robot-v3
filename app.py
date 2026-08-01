from __future__ import annotations

import asyncio

import socket

ROS_IP = "172.24.47.135"   # replace with your hostname -I output
ROS_PORT = 5005

ros_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import APP_NAME, BAUD_RATE, MAX_TIMELINE_EVENTS, UDP_PORT
from metrics import Metrics
from run_manager import RunManager
from serial_reader import SerialReader, available_ports
from telemetry_parser import TelemetryParser
from udp_reader import UdpReader

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

parser = TelemetryParser()
metrics = Metrics()
run_manager = RunManager()
timeline: deque[dict[str, Any]] = deque(maxlen=MAX_TIMELINE_EVENTS)
websocket_clients: set[WebSocket] = set()
robot_socket: WebSocket | None = None
robot_info: dict[str, Any] = {
    "connected": False,
    "robot": None,
    "firmware": None,
    "transport": None,
}
main_loop: asyncio.AbstractEventLoop | None = None
active_transport: Literal["serial", "udp", "cloud"] = "serial"

latest_serial_status: dict[str, Any] = {
    "connected": False,
    "port": None,
    "baud": BAUD_RATE,
    "last_error": None,
}
latest_udp_status: dict[str, Any] = {
    "connected": False,
    "host": "0.0.0.0",
    "port": UDP_PORT,
    "last_sender": None,
    "last_error": None,
}

latest_cloud_status: dict[str, Any] = {
    "connected": False,
    "server": None,
    "robot": None,
    "last_error": None,
}

class ConnectRequest(BaseModel):
    transport: Literal["serial", "udp", "cloud"] = "serial"
    port: str | None = None
    baud: int = BAUD_RATE
    udp_port: int = UDP_PORT
    cloud_url: str = "ws://localhost:8000/ws/robot"


class StartRunRequest(BaseModel):
    note: str | None = None


class CommandRequest(BaseModel):
    command: Literal[
        "ESTOP", "CLEAR_ESTOP", "PING",
        "AUTO", "MANUAL",
        "F", "FL", "FR", "L", "R", "B", "BL", "BR", "S",
    ]


def connection_status() -> dict[str, Any]:
    return {
        "active_transport": active_transport,
        "serial": latest_serial_status,
        "udp": latest_udp_status,
        "cloud": latest_cloud_status,
    }


def full_status() -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "server_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "connection": connection_status(),
        "robot": robot_info,
        "serial": latest_serial_status,
        "udp": latest_udp_status,
        "cloud": latest_cloud_status,
        "run": run_manager.status(),
        "metrics": metrics.snapshot(),
        "timeline": list(timeline),
    }


async def broadcast(payload: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for client in list(websocket_clients):
        try:
            await client.send_json(payload)
        except Exception:
            dead.append(client)
    for client in dead:
        websocket_clients.discard(client)


def schedule_broadcast(payload: dict[str, Any]) -> None:
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(payload), main_loop)


def on_serial_status(status: dict[str, Any]) -> None:
    latest_serial_status.update(status)
    schedule_broadcast({"message_type": "connection_status", "data": connection_status()})


def on_udp_status(status: dict[str, Any]) -> None:
    latest_udp_status.update(status)
    schedule_broadcast({"message_type": "connection_status", "data": connection_status()})

def on_cloud_status(status: dict[str, Any]) -> None:
    latest_cloud_status.update(status)

    schedule_broadcast(
        {
            "message_type": "connection_status",
            "data": connection_status(),
        }
    )

def on_transport_line(line: str) -> None:
    parsed = parser.parse(line)

    import json

    try:
        ros_socket.sendto(
            json.dumps(parsed).encode(),
            (ROS_IP, ROS_PORT)
        )
    except Exception:
        pass

    metrics.update(parsed)
    run_manager.record(line, parsed)
    if parsed.get("type") != "blank":
        timeline.append(parsed)

    schedule_broadcast({
        "message_type": "record",
        "data": parsed,
        "metrics": metrics.snapshot(),
        "run": run_manager.status(),
        "connection": connection_status(),
    })


serial_reader = SerialReader(on_line=on_transport_line, on_status=on_serial_status)
udp_reader = UdpReader(on_line=on_transport_line, on_status=on_udp_status)
@asynccontextmanager
async def lifespan(_: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    yield
    serial_reader.disconnect()
    udp_reader.disconnect()
    if run_manager.active:
        run_manager.stop(metrics.snapshot())


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def api_status():
    return full_status()


@app.get("/api/ports")
async def api_ports():
    return {"ports": available_ports()}


@app.post("/api/connect")
async def api_connect(request: ConnectRequest):

    global active_transport

    try:

        if request.transport == "serial":

            if not request.port:
                raise RuntimeError("Select a COM port first.")

            udp_reader.disconnect()

            serial_reader.connect(
                request.port,
                request.baud,
            )

            active_transport = "serial"

        elif request.transport == "udp":

            serial_reader.disconnect()

            udp_reader.connect(
                request.udp_port
            )

            active_transport = "udp"

        elif request.transport == "cloud":

            serial_reader.disconnect()
            udp_reader.disconnect()


            active_transport = "cloud"

        else:

            raise RuntimeError("Unknown transport.")

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {

        "ok": True,

        "connection": connection_status(),

    }

@app.post("/api/disconnect")
async def api_disconnect():
    serial_reader.disconnect()
    udp_reader.disconnect()
    return {"ok": True, "connection": connection_status()}


@app.post("/api/command")
async def api_command(request: CommandRequest):

    try:

        if active_transport == "udp":

            udp_reader.send_command(
                request.command
            )

        elif active_transport == "cloud":

            if robot_socket is None:

                raise RuntimeError("Robot is offline.")

            await robot_socket.send_json(
                {
                    "type": "command",
                    "command": request.command,
                }
            )

        else:

            raise RuntimeError(
                "Remote commands require UDP or Cloud mode."
            )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {

        "ok": True,

        "command": request.command,

    }


@app.post("/api/run/start")
async def api_run_start(request: StartRunRequest):
    metrics.reset()
    timeline.clear()

    if active_transport == "udp":
        metadata = {
            "serial_port": None,
            "baud": None,
            "udp_port": udp_reader.port or UDP_PORT,
            "transport": "udp",
            "note": request.note or "Atlas Stage 2 complete Wi-Fi telemetry and control run",
        }
    elif active_transport == "cloud":
        metadata = {
            "transport": "cloud",
            "serial_port": None,
            "baud": None,
            "udp_port": None,
            "note": request.note or "Atlas Cloud run",
        }
    else:
        metadata = {
            "serial_port": serial_reader.port,
            "baud": serial_reader.baud or BAUD_RATE,
            "transport": "serial",
            "note": request.note or "Atlas Stage 1 serial dashboard run",
        }

    result = run_manager.start(metadata)
    await broadcast({
        "message_type": "run_status",
        "data": result,
        "metrics": metrics.snapshot(),
    })
    return {"ok": True, "run": result}


@app.post("/api/run/stop")
async def api_run_stop():
    result = run_manager.stop(metrics.snapshot())
    await broadcast({
        "message_type": "run_status",
        "data": result,
        "metrics": metrics.snapshot(),
    })
    return {"ok": True, "run": result}


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):

    await websocket.accept()

    websocket_clients.add(websocket)

    await websocket.send_json(
        {
            "message_type": "initial_status",
            "data": full_status(),
        }
    )

    try:

        while True:

            await websocket.receive_text()

    except WebSocketDisconnect:

        websocket_clients.discard(websocket)

    except Exception:

        websocket_clients.discard(websocket)

@app.websocket("/ws/robot")
async def robot_websocket(websocket: WebSocket):

    global robot_socket

    await websocket.accept()

    robot_socket = websocket

    robot_info["connected"] = True

    print("[ROBOT] Connected")

    try:

        while True:

            packet = await websocket.receive_json()

            packet_type = packet.get("type")

            if packet_type == "hello":

                robot_info["robot"] = packet.get("robot")

                robot_info["firmware"] = packet.get("firmware")

                robot_info["transport"] = packet.get("transport")

                schedule_broadcast(
                    {
                        "message_type": "robot_status",
                        "data": robot_info,
                    }
                )

            elif packet_type == "telemetry":

                line = packet.get("line", "")

                if line:

                    on_transport_line(line)

            elif packet_type == "heartbeat":

                await websocket.send_json(
                    {
                        "type": "heartbeat"
                    }
                )

    except WebSocketDisconnect:

        print("[ROBOT] Disconnected")

    finally:

        robot_info["connected"] = False

        robot_socket = None

        schedule_broadcast(
            {
                "message_type": "robot_status",
                "data": robot_info,
            }
        )
