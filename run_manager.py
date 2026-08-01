from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from config import RUNS_DIRECTORY


class RunManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self.active = False
        self.run_id: str | None = None
        self.run_directory: Path | None = None
        self.started_at: datetime | None = None
        self._raw_file = None
        self._telemetry_file = None
        self._events_file = None

    def start(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self.active:
                return self.status()

            RUNS_DIRECTORY.mkdir(parents=True, exist_ok=True)
            self.started_at = datetime.now().astimezone()
            self.run_id = self.started_at.strftime("atlas_%Y%m%d_%H%M%S")
            self.run_directory = RUNS_DIRECTORY / self.run_id
            self.run_directory.mkdir(parents=True, exist_ok=False)

            self._raw_file = (self.run_directory / "raw_serial.log").open("a", encoding="utf-8", buffering=1)
            self._telemetry_file = (self.run_directory / "telemetry.jsonl").open("a", encoding="utf-8", buffering=1)
            self._events_file = (self.run_directory / "events.jsonl").open("a", encoding="utf-8", buffering=1)

            metadata_payload = {
                "run_id": self.run_id,
                "started_at": self.started_at.isoformat(timespec="seconds"),
                **(metadata or {}),
            }
            (self.run_directory / "metadata.json").write_text(
                json.dumps(metadata_payload, indent=2),
                encoding="utf-8",
            )
            self.active = True
            return self.status()

    def record(self, raw_line: str, parsed: dict[str, Any]) -> None:
        with self._lock:
            if not self.active:
                return

            host_time = parsed.get("host_time", datetime.now().astimezone().isoformat(timespec="milliseconds"))
            self._raw_file.write(f"[{host_time}] {raw_line.rstrip()}\n")

            target = self._telemetry_file if parsed.get("type") == "telemetry" else self._events_file
            target.write(json.dumps(parsed, separators=(",", ":")) + "\n")

    def stop(self, summary: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not self.active:
                return self.status()

            stopped_at = datetime.now().astimezone()
            duration = (
                (stopped_at - self.started_at).total_seconds()
                if self.started_at is not None
                else None
            )
            payload = {
                "run_id": self.run_id,
                "started_at": self.started_at.isoformat(timespec="seconds") if self.started_at else None,
                "stopped_at": stopped_at.isoformat(timespec="seconds"),
                "duration_seconds": duration,
                **summary,
            }

            assert self.run_directory is not None
            (self.run_directory / "summary.json").write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )

            for handle in (self._raw_file, self._telemetry_file, self._events_file):
                if handle is not None:
                    handle.flush()
                    handle.close()

            completed = {
                "active": False,
                "run_id": self.run_id,
                "run_directory": str(self.run_directory),
                "duration_seconds": duration,
            }
            self.active = False
            self._raw_file = None
            self._telemetry_file = None
            self._events_file = None
            return completed

    def status(self) -> dict[str, Any]:
        duration = None
        if self.active and self.started_at:
            duration = (datetime.now().astimezone() - self.started_at).total_seconds()
        return {
            "active": self.active,
            "run_id": self.run_id,
            "run_directory": str(self.run_directory) if self.run_directory else None,
            "started_at": self.started_at.isoformat(timespec="seconds") if self.started_at else None,
            "duration_seconds": duration,
        }
