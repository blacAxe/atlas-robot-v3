from __future__ import annotations

import socket
import threading
from typing import Callable


class UdpReader:
    def __init__(
        self,
        on_line: Callable[[str], None],
        on_status: Callable[[dict], None],
    ) -> None:
        self._on_line = on_line
        self._on_status = on_status
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self.host = "0.0.0.0"
        self.port: int | None = None
        self.last_error: str | None = None
        self.last_sender: str | None = None
        self.last_sender_ip: str | None = None

    @property
    def connected(self) -> bool:
        return self._socket is not None and not self._stop_event.is_set()

    def connect(self, port: int) -> None:
        if not 1 <= port <= 65535:
            raise RuntimeError("UDP port must be between 1 and 65535.")

        if self.connected:
            self.disconnect()

        self.port = port
        self.last_error = None
        self.last_sender = None
        self.last_sender_ip = None
        self._stop_event.clear()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, port))
            sock.settimeout(0.5)
            self._socket = sock

            self._thread = threading.Thread(
                target=self._read_loop,
                name="atlas-udp-reader",
                daemon=True,
            )
            self._thread.start()
            print(f"[UDP] Listening on {self.host}:{port}")
            self._on_status(self.status())
        except Exception as exc:
            self.last_error = str(exc)
            self._close_socket()
            raise RuntimeError(str(exc)) from exc

    def disconnect(self) -> None:
        self._stop_event.set()
        self._close_socket()
        if (
            self._thread is not None
            and self._thread.is_alive()
            and threading.current_thread() is not self._thread
        ):
            self._thread.join(timeout=1.0)
        self._thread = None
        self._on_status(self.status())

    def _read_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                sock = self._socket
                if sock is None:
                    break
                try:
                    data, address = sock.recvfrom(8192)
                except socket.timeout:
                    continue
                except OSError:
                    break

                line = data.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                self.last_sender_ip = address[0]
                self.last_sender = f"{address[0]}:{address[1]}"
                print(f"[ATLAS UDP {self.last_sender}] {line}")
                self._on_line(line)
                self._on_status(self.status())
        except Exception as exc:
            self.last_error = f"UDP read error: {exc}"
            print(f"[UDP ERROR] {self.last_error}")
        finally:
            self._close_socket()
            self._on_status(self.status())
            print("[UDP] Reader stopped.")

    def send_command(self, command: str, command_port: int = 4211) -> None:
        if not self.connected or self._socket is None:
            raise RuntimeError("Connect the dashboard to Wi-Fi UDP first.")
        if not self.last_sender_ip:
            raise RuntimeError("No Atlas telemetry received yet. Wait for packets first.")

        clean_command = command.strip().upper()
        allowed_commands = {
            "ESTOP", "CLEAR_ESTOP", "PING",
            "AUTO", "MANUAL",
            "F", "FL", "FR", "L", "R", "B", "BL", "BR", "S",
        }
        if clean_command not in allowed_commands:
            raise RuntimeError(f"Unsupported Atlas command: {clean_command}")

        self._socket.sendto(clean_command.encode("utf-8"), (self.last_sender_ip, command_port))
        print(f"[UDP COMMAND] {clean_command} -> {self.last_sender_ip}:{command_port}")

    def _close_socket(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
        self._socket = None

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "last_sender": self.last_sender,
            "last_sender_ip": self.last_sender_ip,
            "last_error": self.last_error,
        }
