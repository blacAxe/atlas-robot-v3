from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any


MOTION_EVENTS = {
    "FORWARD",
    "BACKING",
    "TURNING_LEFT",
    "TURNING_RIGHT",
    "CORRECTING_LEFT",
    "CORRECTING_RIGHT",
    "STOPPED",
}


class Metrics:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.counts: Counter[str] = Counter()
        self.category_counts: Counter[str] = Counter()
        self.distance_samples = 0
        self.no_echo_count = 0
        self.minimum_distance_cm: float | None = None
        self.maximum_distance_cm: float | None = None
        self.latest_distance_cm: float | None = None
        self.latest_sensors = {
            "front_left": False,
            "front_right": False,
            "left_wing": False,
            "right_wing": False,
            "rear": False,
        }
        self.sensor_activation_counts: Counter[str] = Counter()
        self._previous_sensors = dict(self.latest_sensors)
        self.current_state = "UNKNOWN"
        self.last_decision = "NONE"
        self.last_reason = "NONE"
        self.recovery_status = "NORMAL"
        self.latest_record: dict[str, Any] | None = None

    def update(self, record: dict[str, Any]) -> None:
        self.latest_record = record
        category = str(record.get("category", "unknown"))
        self.category_counts[category] += 1

        if record.get("type") == "telemetry":
            self.distance_samples += 1
            distance = record.get("distance_cm")
            if distance is None:
                self.no_echo_count += 1
            else:
                distance = float(distance)
                self.latest_distance_cm = distance
                if self.minimum_distance_cm is None or distance < self.minimum_distance_cm:
                    self.minimum_distance_cm = distance
                if self.maximum_distance_cm is None or distance > self.maximum_distance_cm:
                    self.maximum_distance_cm = distance

            sensors = record.get("sensors", {})
            for name in self.latest_sensors:
                blocked = bool(sensors.get(name, False))
                if blocked and not self._previous_sensors.get(name, False):
                    self.sensor_activation_counts[name] += 1
                self.latest_sensors[name] = blocked
            self._previous_sensors = dict(self.latest_sensors)
            return

        event = str(record.get("event", "UNKNOWN"))
        self.counts[event] += 1

        if event in MOTION_EVENTS:
            self.current_state = event

        if category == "decision":
            self.last_decision = event
            if event == "ESCAPE_RIGHT":
                self.last_reason = "FRONT_LEFT_BLOCKED"
            elif event == "ESCAPE_LEFT":
                self.last_reason = "FRONT_RIGHT_BLOCKED"
            elif event == "CORRECT_RIGHT":
                self.last_reason = "LEFT_WING_BLOCKED"
            elif event == "CORRECT_LEFT":
                self.last_reason = "RIGHT_WING_BLOCKED"

        if event == "CENTRE_OBSTACLE":
            self.last_reason = "CENTRE_OBSTACLE"
        elif event == "EMERGENCY_CENTRE_OBSTACLE":
            self.last_reason = "EMERGENCY_DISTANCE"
        elif event == "BOTH_FRONT_BLOCKED":
            self.last_reason = "BOTH_FRONT_BLOCKED"
        elif event == "BOTH_WINGS_RECOVERY":
            self.last_reason = "BOTH_WINGS_BLOCKED"

        if event == "RECOVERY_LOCKED":
            self.recovery_status = "LOCKED"
            self.current_state = "RECOVERY_LOCKED"
        elif event == "RECOVERY_CLEARED":
            self.recovery_status = "CLEARED"
        elif event in {
            "RECOVERY_UNRESOLVED",
            "ESCAPE_FAILED_LOCKED",
            "EMERGENCY_ESCAPE_FAILED_LOCKED",
            "FRONT_ESCAPE_FAILED_LOCKED",
            "RIGHT_ESCAPE_FAILED_LOCKED",
            "LEFT_ESCAPE_FAILED_LOCKED",
            "WING_REVERSE_FAILED_LOCKED",
            "WING_ESCAPE_FAILED_LOCKED",
        }:
            self.recovery_status = "FAILED"

    def snapshot(self) -> dict[str, Any]:
        return {
            "counts": dict(self.counts),
            "category_counts": dict(self.category_counts),
            "distance_samples": self.distance_samples,
            "no_echo_count": self.no_echo_count,
            "minimum_distance_cm": self.minimum_distance_cm,
            "maximum_distance_cm": self.maximum_distance_cm,
            "latest_distance_cm": self.latest_distance_cm,
            "latest_sensors": deepcopy(self.latest_sensors),
            "sensor_activation_counts": dict(self.sensor_activation_counts),
            "current_state": self.current_state,
            "last_decision": self.last_decision,
            "last_reason": self.last_reason,
            "recovery_status": self.recovery_status,
        }
