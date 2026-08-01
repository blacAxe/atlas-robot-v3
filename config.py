from pathlib import Path

APP_NAME = "Atlas Dashboard"
BAUD_RATE = 115200
SERIAL_TIMEOUT_SECONDS = 0.25
RUNS_DIRECTORY = Path(__file__).resolve().parent / "runs"
MAX_TIMELINE_EVENTS = 500
MAX_CHART_POINTS = 600

UDP_PORT = 4210
