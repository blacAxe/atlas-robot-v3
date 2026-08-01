from __future__ import annotations

import re
from datetime import datetime
from typing import Any


SENSOR_PATTERN = re.compile(
    r"Distance=(?P<distance>NO_ECHO|-?\d+(?:\.\d+)?)"
    r"(?:cm)?\s*\|\s*FRONT_LEFT=(?P<front_left>CLEAR|BLOCKED)"
    r"\s*\|\s*FRONT_RIGHT=(?P<front_right>CLEAR|BLOCKED)"
    r"\s*\|\s*REAR=(?P<rear>CLEAR|BLOCKED)"
    r"\s*\|\s*LEFT_WING=(?P<left_wing>CLEAR|BLOCKED)"
    r"\s*\|\s*RIGHT_WING=(?P<right_wing>CLEAR|BLOCKED)",
    re.IGNORECASE,
)

SCAN_PATTERN = re.compile(
    r"^(?P<direction>Left|Right|Centre) scan\s*=\s*(?P<distance>NO ECHO|-?\d+(?:\.\d+)?)"
    r"(?:\s*cm)?$",
    re.IGNORECASE,
)

REVERSE_TARGET_PATTERN = re.compile(
    r"^Reverse target\s*=\s*(?P<duration>\d+)\s*ms$",
    re.IGNORECASE,
)

CONTINUOUS_TURN_PATTERN = re.compile(
    r"^Continuous\s+(?P<direction>LEFT|RIGHT)\s+turn\s*\|\s*target="
    r"(?P<target>-?\d+(?:\.\d+)?)\s*cm$",
    re.IGNORECASE,
)

TURN_EXTENSION_PATTERN = re.compile(
    r"^Turn extension\s+(?P<attempt>\d+)\/(?P<maximum>\d+)$",
    re.IGNORECASE,
)

HEADING_CHECK_PATTERN = re.compile(
    r"^Heading check\s*=\s*(?P<distance>NO ECHO|-?\d+(?:\.\d+)?)"
    r"(?:\s*cm)?\s*\|\s*FRONT_LEFT=(?P<front_left>CLEAR|BLOCKED)"
    r"\s*\|\s*FRONT_RIGHT=(?P<front_right>CLEAR|BLOCKED)$",
    re.IGNORECASE,
)

CHOSEN_DISTANCE_PATTERN = re.compile(
    r"^Chosen distance\s*=\s*(?P<distance>-?\d+(?:\.\d+)?)\s*cm$",
    re.IGNORECASE,
)

HEADING_TARGET_PATTERN = re.compile(
    r"^Heading target\s*=\s*(?P<distance>-?\d+(?:\.\d+)?)\s*cm$",
    re.IGNORECASE,
)


EXACT_EVENTS: dict[str, tuple[str, str, str]] = {
    "Forward": ("motion", "FORWARD", "info"),
    "Back": ("motion", "BACKING", "info"),
    "Left": ("motion", "TURNING_LEFT", "info"),
    "Right": ("motion", "TURNING_RIGHT", "info"),
    "Steer left": ("motion", "CORRECTING_LEFT", "info"),
    "Steer right": ("motion", "CORRECTING_RIGHT", "info"),
    "STOP": ("motion", "STOPPED", "info"),

    "Centre obstacle detected": ("obstacle", "CENTRE_OBSTACLE", "warning"),
    "Emergency centre obstacle": ("obstacle", "EMERGENCY_CENTRE_OBSTACLE", "critical"),
    "Both front IR sensors blocked": ("obstacle", "BOTH_FRONT_BLOCKED", "critical"),
    "Front left blocked - escape RIGHT": ("decision", "ESCAPE_RIGHT", "warning"),
    "Front right blocked - escape LEFT": ("decision", "ESCAPE_LEFT", "warning"),
    "Left wing near wall - gentle correction RIGHT": ("decision", "CORRECT_RIGHT", "warning"),
    "Right wing near wall - gentle correction LEFT": ("decision", "CORRECT_LEFT", "warning"),
    "Both wings blocked - full recovery": ("recovery", "BOTH_WINGS_RECOVERY", "critical"),

    "Rear blocked - reverse cancelled": ("recovery", "REVERSE_CANCELLED_REAR_BLOCKED", "critical"),
    "Rear obstacle detected - reverse stopped": ("recovery", "REVERSE_STOPPED_REAR_BLOCKED", "critical"),
    "Reverse completed": ("recovery", "REVERSE_COMPLETED", "success"),

    "LEFT selected": ("decision", "CHOOSE_LEFT", "info"),
    "RIGHT selected": ("decision", "CHOOSE_RIGHT", "info"),
    "Left IR blocked - choosing RIGHT": ("decision", "CHOOSE_RIGHT", "warning"),
    "Right IR blocked - choosing LEFT": ("decision", "CHOOSE_LEFT", "warning"),
    "Only LEFT scan valid - choosing LEFT": ("decision", "CHOOSE_LEFT", "warning"),
    "Only RIGHT scan valid - choosing RIGHT": ("decision", "CHOOSE_RIGHT", "warning"),
    "Both scans NO ECHO - alternating fallback": ("decision", "ALTERNATING_FALLBACK", "warning"),

    "Heading target reached": ("heading", "HEADING_TARGET_REACHED", "success"),
    "Heading accepted within target tolerance": ("heading", "HEADING_ACCEPTED_TOLERANCE", "success"),
    "Heading accepted: NO ECHO + front IR clear": ("heading", "HEADING_ACCEPTED_NO_ECHO", "success"),
    "Heading rejected: front IR blocked": ("heading", "HEADING_REJECTED_FRONT_BLOCKED", "warning"),
    "Direction could not be verified": ("heading", "DIRECTION_UNVERIFIED", "critical"),
    "Chosen direction failed - remaining committed": ("recovery", "CHOSEN_DIRECTION_FAILED", "critical"),

    "RECOVERY LOCK - normal forward disabled": ("recovery", "RECOVERY_LOCKED", "critical"),
    "Recovery lock cleared": ("recovery", "RECOVERY_CLEARED", "success"),
    "Recovery still unresolved": ("recovery", "RECOVERY_UNRESOLVED", "critical"),

    "Escape failed - forward movement locked": ("recovery", "ESCAPE_FAILED_LOCKED", "critical"),
    "Emergency escape failed - locked": ("recovery", "EMERGENCY_ESCAPE_FAILED_LOCKED", "critical"),
    "Front escape failed - locked": ("recovery", "FRONT_ESCAPE_FAILED_LOCKED", "critical"),
    "RIGHT escape failed - forward locked": ("recovery", "RIGHT_ESCAPE_FAILED_LOCKED", "critical"),
    "LEFT escape failed - forward locked": ("recovery", "LEFT_ESCAPE_FAILED_LOCKED", "critical"),
    "Wing recovery reverse failed - locked": ("recovery", "WING_REVERSE_FAILED_LOCKED", "critical"),
    "Wing escape failed - forward locked": ("recovery", "WING_ESCAPE_FAILED_LOCKED", "critical"),

    "NO ECHO + front IR clear -> cautious forward": ("sensor", "NO_ECHO_CAUTIOUS_FORWARD", "warning"),
    "Atlas started": ("system", "ATLAS_STARTED", "success"),
    "Stabilizing sensors...": ("system", "SENSOR_STABILIZATION", "info"),
}


class TelemetryParser:
    def __init__(self) -> None:
        self.sequence = 0

    def parse(self, raw_line: str) -> dict[str, Any]:
        self.sequence += 1
        line = raw_line.strip()
        now = datetime.now().astimezone().isoformat(timespec="milliseconds")

        base: dict[str, Any] = {
            "seq": self.sequence,
            "host_time": now,
            "raw": line,
        }

        if not line:
            return {**base, "type": "blank", "category": "raw", "event": "BLANK_LINE", "severity": "debug"}

        sensor_match = SENSOR_PATTERN.search(line)
        if sensor_match:
            distance_text = sensor_match.group("distance").upper()
            distance = None if distance_text == "NO_ECHO" else float(distance_text)
            return {
                **base,
                "type": "telemetry",
                "category": "sensors",
                "distance_cm": distance,
                "distance_valid": distance is not None,
                "sensors": {
                    "front_left": sensor_match.group("front_left").upper() == "BLOCKED",
                    "front_right": sensor_match.group("front_right").upper() == "BLOCKED",
                    "rear": sensor_match.group("rear").upper() == "BLOCKED",
                    "left_wing": sensor_match.group("left_wing").upper() == "BLOCKED",
                    "right_wing": sensor_match.group("right_wing").upper() == "BLOCKED",
                },
            }

        scan_match = SCAN_PATTERN.match(line)
        if scan_match:
            distance_text = scan_match.group("distance").upper()
            distance = None if distance_text == "NO ECHO" else float(distance_text)
            return {
                **base,
                "type": "event",
                "category": "scan",
                "event": f"{scan_match.group('direction').upper()}_SCAN",
                "severity": "warning" if distance is None else "info",
                "distance_cm": distance,
                "distance_valid": distance is not None,
            }

        heading_match = HEADING_CHECK_PATTERN.match(line)
        if heading_match:
            distance_text = heading_match.group("distance").upper()
            distance = None if distance_text == "NO ECHO" else float(distance_text)
            return {
                **base,
                "type": "event",
                "category": "heading",
                "event": "HEADING_CHECK",
                "severity": "info",
                "distance_cm": distance,
                "distance_valid": distance is not None,
                "front_left_blocked": heading_match.group("front_left").upper() == "BLOCKED",
                "front_right_blocked": heading_match.group("front_right").upper() == "BLOCKED",
            }

        reverse_match = REVERSE_TARGET_PATTERN.match(line)
        if reverse_match:
            return {
                **base,
                "type": "event",
                "category": "recovery",
                "event": "REVERSE_STARTED",
                "severity": "warning",
                "target_duration_ms": int(reverse_match.group("duration")),
            }

        turn_match = CONTINUOUS_TURN_PATTERN.match(line)
        if turn_match:
            direction = turn_match.group("direction").upper()
            return {
                **base,
                "type": "event",
                "category": "turn",
                "event": f"CONTINUOUS_{direction}_TURN",
                "severity": "warning",
                "direction": direction,
                "target_clearance_cm": float(turn_match.group("target")),
            }

        extension_match = TURN_EXTENSION_PATTERN.match(line)
        if extension_match:
            return {
                **base,
                "type": "event",
                "category": "turn",
                "event": "TURN_EXTENSION",
                "severity": "warning",
                "attempt": int(extension_match.group("attempt")),
                "maximum": int(extension_match.group("maximum")),
            }

        chosen_match = CHOSEN_DISTANCE_PATTERN.match(line)
        if chosen_match:
            return {
                **base,
                "type": "event",
                "category": "decision",
                "event": "CHOSEN_DISTANCE",
                "severity": "info",
                "distance_cm": float(chosen_match.group("distance")),
            }

        target_match = HEADING_TARGET_PATTERN.match(line)
        if target_match:
            return {
                **base,
                "type": "event",
                "category": "heading",
                "event": "HEADING_TARGET",
                "severity": "info",
                "distance_cm": float(target_match.group("distance")),
            }

        if line in EXACT_EVENTS:
            category, event, severity = EXACT_EVENTS[line]
            return {
                **base,
                "type": "event",
                "category": category,
                "event": event,
                "severity": severity,
            }

        if line.startswith("Startup distance ="):
            value = line.split("=", 1)[1].strip()
            no_echo = value.upper().startswith("NO ECHO")
            distance = None
            if not no_echo:
                match = re.search(r"-?\d+(?:\.\d+)?", value)
                distance = float(match.group(0)) if match else None
            return {
                **base,
                "type": "event",
                "category": "system",
                "event": "STARTUP_DISTANCE",
                "severity": "warning" if distance is None else "info",
                "distance_cm": distance,
                "distance_valid": distance is not None,
            }

        if line.startswith("Heading still too close; need at least"):
            match = re.search(r"-?\d+(?:\.\d+)?", line)
            return {
                **base,
                "type": "event",
                "category": "heading",
                "event": "HEADING_TOO_CLOSE",
                "severity": "warning",
                "minimum_required_cm": float(match.group(0)) if match else None,
            }

        if line.startswith("ATLAS ") or line.startswith("5 IR +") or line.startswith("Starting in"):
            return {
                **base,
                "type": "event",
                "category": "system",
                "event": "FIRMWARE_MESSAGE",
                "severity": "info",
                "message": line,
            }

        return {
            **base,
            "type": "event",
            "category": "raw",
            "event": "UNPARSED_SERIAL_LINE",
            "severity": "debug",
            "message": line,
        }
