from __future__ import annotations

import threading
import time
from typing import Callable

import serial
from serial.tools import list_ports

from config import SERIAL_TIMEOUT_SECONDS


def available_ports() -> list[dict[str, str]]:
    ports: list[dict[str, str]] = []

    for port in list_ports.comports():
        ports.append(
            {
                "device": port.device,
                "description": port.description or "Unknown serial device",
                "hwid": port.hwid or "",
            }
        )

    return ports


class SerialReader:
    def __init__(
        self,
        on_line: Callable[[str], None],
        on_status: Callable[[dict], None],
    ) -> None:
        self._on_line = on_line
        self._on_status = on_status

        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self.port: str | None = None
        self.baud: int | None = None
        self.last_error: str | None = None

    @property
    def connected(self) -> bool:
        return bool(self._serial is not None and self._serial.is_open)

    def connect(self, port: str, baud: int) -> None:
        port = port.strip().upper()

        if not port:
            raise RuntimeError("No COM port was selected.")

        if self.connected:
            self.disconnect()

        visible_ports = {
            item["device"].upper()
            for item in available_ports()
        }

        if port not in visible_ports:
            raise RuntimeError(
                f"{port} is not currently visible. "
                "Reconnect Atlas and press Refresh ports."
            )

        self.port = port
        self.baud = baud
        self.last_error = None
        self._stop_event.clear()

        try:
            print(f"[SERIAL] Opening {port} at {baud} baud...")

            self._serial = serial.Serial(
                port=port,
                baudrate=baud,
                timeout=SERIAL_TIMEOUT_SECONDS,
                write_timeout=1,
                dsrdtr=False,
                rtscts=False,
            )

            self._serial.dtr = True
            self._serial.rts = True

            print("[SERIAL] Port opened. Waiting for Uno R4 reset...")
            time.sleep(2.5)

            if not self._serial.is_open:
                raise RuntimeError("The serial port closed unexpectedly.")

            self._serial.reset_input_buffer()

            print("[SERIAL] Reader started. Waiting for Arduino messages...")

            self._thread = threading.Thread(
                target=self._read_loop,
                name="atlas-serial-reader",
                daemon=True,
            )
            self._thread.start()

            self._on_status(self.status())

        except Exception as exc:
            self.last_error = str(exc)
            self._close_port()
            print(f"[SERIAL ERROR] {exc}")
            raise RuntimeError(str(exc)) from exc

    def disconnect(self) -> None:
        print("[SERIAL] Disconnect requested.")

        self._stop_event.set()
        self._close_port()

        if (
            self._thread is not None
            and self._thread.is_alive()
            and threading.current_thread() is not self._thread
        ):
            self._thread.join(timeout=1.5)

        self._thread = None
        self._on_status(self.status())

    def _read_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                current_serial = self._serial

                if current_serial is None or not current_serial.is_open:
                    break

                raw = current_serial.readline()

                if not raw:
                    continue

                line = raw.decode(
                    "utf-8",
                    errors="replace",
                ).rstrip("\r\n")

                if not line:
                    continue

                print(f"[ARDUINO] {line}")

                self._on_line(line)

        except serial.SerialException as exc:
            self.last_error = f"Serial read error: {exc}"
            print(f"[SERIAL ERROR] {self.last_error}")

        except Exception as exc:
            self.last_error = f"Reader error: {exc}"
            print(f"[SERIAL ERROR] {self.last_error}")

        finally:
            self._close_port()
            self._on_status(self.status())
            print("[SERIAL] Reader stopped.")

    def _close_port(self) -> None:
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass

        self._serial = None

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "port": self.port,
            "baud": self.baud,
            "last_error": self.last_error,
        }