const state = {
  ws: null,
  metrics: {},
  timeline: [],
  runStartedAt: null,
  lastRecordAt: null,
  distanceChart: null,
  controlMode: "AUTO",
  heldCommand: null,
  commandRepeatTimer: null,
};

const counterDefinitions = [
  ["FORWARD", "Forward commands"],
  ["STOPPED", "Stops"],
  ["BACKING", "Backups"],
  ["TURNING_LEFT", "Left turns"],
  ["TURNING_RIGHT", "Right turns"],
  ["CORRECTING_LEFT", "Left corrections"],
  ["CORRECTING_RIGHT", "Right corrections"],
  ["CENTRE_OBSTACLE", "Centre obstacles"],
  ["EMERGENCY_CENTRE_OBSTACLE", "Emergency obstacles"],
  ["BOTH_FRONT_BLOCKED", "Both-front blocks"],
  ["RECOVERY_LOCKED", "Recovery locks"],
  ["RECOVERY_CLEARED", "Recovery successes"],
  ["RECOVERY_UNRESOLVED", "Unresolved recoveries"],
  ["DIRECTION_UNVERIFIED", "Failed headings"],
  ["TURN_EXTENSION", "Turn extensions"],
  ["REVERSE_COMPLETED", "Completed reverses"],
];

function $(id) {
  return document.getElementById(id);
}

function setStatus(message, isError = false) {
  const element = $("statusMessage");
  element.textContent = message;
  element.style.color = isError ? "#fda4af" : "";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return body;
}

async function sendRemoteCommand(command, quiet = false) {
  const transport = selectedTransport();

  if (transport !== "udp" && transport !== "cloud") {
      if (!quiet) {
          setStatus("Remote controls require Wi-Fi UDP or Cloud mode.", true);
      }
      return false;
  }

  try {
    await api("/api/command", {
      method: "POST",
      body: JSON.stringify({ command }),
    });

    if (!quiet) {
      const labels = {
        ESTOP: "Emergency stop sent. Atlas is latched stopped.",
        CLEAR_ESTOP: "E-STOP cleared. Atlas remains stopped until a mode or movement command.",
        AUTO: "AUTO mode selected.",
        MANUAL: "MANUAL mode selected.",
        PING: "PING sent to Atlas.",
        S: "Manual stop sent.",
      };
      setStatus(labels[command] || `Command ${command} sent.`);
    }

    return true;
  } catch (error) {
    if (!quiet) setStatus(`Command failed: ${error.message}`, true);
    return false;
  }
}

function updateControlMode(mode) {
  state.controlMode = mode;
  $("controlModeBadge").textContent = mode;
  const mobileModeLabel = $("mobileModeLabel");
  if (mobileModeLabel) mobileModeLabel.textContent = mode;
  $("autoModeButton").classList.toggle("active", mode === "AUTO");
  $("manualModeButton").classList.toggle("active", mode === "MANUAL");

  document.querySelectorAll(".drive-button").forEach((button) => {
    const transport = selectedTransport();

    button.disabled =
        (transport !== "udp" && transport !== "cloud")
        || mode !== "MANUAL";
  });
}

async function selectControlMode(mode) {
  stopHeldMovement(false);
  const sent = await sendRemoteCommand(mode);
  if (sent) updateControlMode(mode);
}

async function startHeldMovement(command, button) {
  if (state.controlMode !== "MANUAL") {
    setStatus("Select MANUAL mode before driving.", true);
    return;
  }

  if (state.heldCommand === command) return;

  stopHeldMovement(false);
  state.heldCommand = command;
  button.classList.add("pressed");

  await sendRemoteCommand(command, true);
  state.commandRepeatTimer = window.setInterval(() => {
    sendRemoteCommand(command, true);
  }, 150);
}

function stopHeldMovement(sendStop = true) {
  if (state.commandRepeatTimer !== null) {
    window.clearInterval(state.commandRepeatTimer);
    state.commandRepeatTimer = null;
  }

  document.querySelectorAll(".drive-button.pressed").forEach((button) => {
    button.classList.remove("pressed");
  });

  const wasMoving = state.heldCommand !== null;
  state.heldCommand = null;

  if (sendStop && wasMoving) {
    sendRemoteCommand("S", true);
  }
}

function setupDriveControls() {
  document.querySelectorAll(".drive-button").forEach((button) => {
    const command = button.dataset.command;

    if (command === "S") {
      button.addEventListener("click", () => {
        stopHeldMovement(false);
        sendRemoteCommand("S");
      });
      return;
    }

    const start = (event) => {
      event.preventDefault();
      startHeldMovement(command, button);
    };

    const stop = (event) => {
      event.preventDefault();
      stopHeldMovement(true);
    };

    button.addEventListener("pointerdown", start);
    button.addEventListener("pointerup", stop);
    button.addEventListener("pointercancel", stop);
    button.addEventListener("pointerleave", stop);
    button.addEventListener("contextmenu", (event) => event.preventDefault());
  });

  window.addEventListener("pointerup", () => stopHeldMovement(true));
  window.addEventListener("blur", () => stopHeldMovement(true));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopHeldMovement(true);
  });
}

async function refreshPorts() {
  try {
    const data = await api("/api/ports");
    const select = $("portSelect");
    const previous = select.value;
    select.innerHTML = "";

    if (!data.ports.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No serial ports detected";
      select.appendChild(option);
      return;
    }

    data.ports.forEach((port) => {
      const option = document.createElement("option");
      option.value = port.device;
      option.textContent = `${port.device} — ${port.description}`;
      select.appendChild(option);
    });

    if ([...select.options].some((option) => option.value === previous)) {
      select.value = previous;
    }
  } catch (error) {
    setStatus(`Could not list serial ports: ${error.message}`, true);
  }
}

function selectedTransport() {
  return $("transportSelect").value;
}

function updateTransportFields() {

    const transport = selectedTransport();

    const isUdp = transport === "udp";

    const isCloud = transport === "cloud";

    $("serialPortField").classList.toggle(
        "hidden",
        isUdp || isCloud
    );

    $("baudField").classList.toggle(
        "hidden",
        isUdp || isCloud
    );

    $("refreshPortsButton").classList.toggle(
        "hidden",
        isUdp || isCloud
    );

    $("udpPortField").classList.toggle(
        "hidden",
        !isUdp
    );

    $("cloudUrlField").classList.toggle(
        "hidden",
        !isCloud
    );

}

async function connectTransport() {

    const transport = selectedTransport();

    const payload = {
        transport: transport
    };

    if (transport === "serial") {

        const port = $("portSelect").value;
        const baud = Number($("baudInput").value || 115200);

        if (!port) {
            setStatus("Select a COM port first.", true);
            return;
        }

        payload.port = port;
        payload.baud = baud;

    }
    else if (transport === "udp") {

        payload.udp_port =
            Number($("udpPortInput").value || 4210);

    }
    else if (transport === "cloud") {

        payload.cloud_url =
            $("cloudUrlInput").value.trim();

    }

    try {

        await api("/api/connect", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        if (transport === "serial") {

            setStatus(
                `Connected to ${payload.port}.`
            );

        }
        else if (transport === "udp") {

            setStatus(
                `Listening on UDP ${payload.udp_port}.`
            );

        }
        else {

            setStatus(
                `Connecting to Atlas Cloud...`
            );

        }

    }
    catch (err) {

        setStatus(
            `Connection failed: ${err.message}`,
            true
        );

    }

}

async function disconnectTransport() {
  try {
    await api("/api/disconnect", { method: "POST" });
    setStatus("Telemetry connection closed.");
  } catch (error) {
    setStatus(`Disconnect failed: ${error.message}`, true);
  }
}

async function startRun() {
  try {
    const data = await api("/api/run/start", {
      method: "POST",
      body: JSON.stringify({ note: "Atlas Stage 1 serial dashboard run" }),
    });
    updateRun(data.run);
    state.timeline = [];
    renderTimeline();
    resetDistanceChart();
    setStatus(`Recording ${data.run.run_id}.`);
  } catch (error) {
    setStatus(`Could not start run: ${error.message}`, true);
  }
}

async function stopRun() {
  try {
    const data = await api("/api/run/stop", { method: "POST" });
    updateRun(data.run);
    setStatus(`Run stopped. Saved under: ${data.run.run_directory || "runs folder"}`);
  } catch (error) {
    setStatus(`Could not stop run: ${error.message}`, true);
  }
}

function updateConnection(connection) {

    const transport =
        connection?.active_transport || "serial";

    let details = null;

    if (transport === "serial") {

        details = connection?.serial;

    }
    else if (transport === "udp") {

        details = connection?.udp;

    }
    else if (transport === "cloud") {

        details = connection?.cloud;

    }

    const connected = Boolean(details?.connected);

    const badge = $("connectionBadge");

    if (connected && transport === "serial") {

        badge.textContent =
            `USB Serial · ${details.port}`;

    }
    else if (connected && transport === "udp") {

        badge.textContent =
            details.last_sender
            ? `Wi-Fi UDP · ${details.last_sender}`
            : `Wi-Fi UDP · port ${details.port}`;

    }
    else if (connected && transport === "cloud") {

        badge.textContent =
            `Atlas Cloud`;

    }
    else {

        badge.textContent =
            "Disconnected";

    }

    badge.classList.toggle(
        "connected",
        connected
    );

    $("connectButton").disabled = connected;

    $("disconnectButton").disabled = !connected;

    $("transportSelect").disabled = connected;

}

function updateRun(run) {
  const active = Boolean(run?.active);
  $("runId").textContent = active ? run.run_id : (run?.run_id || "Not recording");
  $("startRunButton").disabled = active;
  $("stopRunButton").disabled = !active;

  if (active && run.started_at) {
    state.runStartedAt = new Date(run.started_at);
  } else if (!active) {
    state.runStartedAt = null;
  }
}

function updateMetrics(metrics) {
  state.metrics = metrics || {};

  $("currentState").textContent = metrics.current_state || "UNKNOWN";
  $("lastDecision").textContent = metrics.last_decision || "NONE";
  $("lastReason").textContent = metrics.last_reason || "NONE";
  $("recoveryStatus").textContent = metrics.recovery_status || "NORMAL";

  const latestDistance = metrics.latest_distance_cm;
  $("distanceValue").textContent =
    latestDistance == null ? "NO ECHO" : `${latestDistance.toFixed(1)} cm`;

  const min = metrics.minimum_distance_cm;
  const max = metrics.maximum_distance_cm;
  $("distanceRange").textContent =
    `Min ${min == null ? "—" : min.toFixed(1) + " cm"} · ` +
    `Max ${max == null ? "—" : max.toFixed(1) + " cm"} · ` +
    `No echo ${metrics.no_echo_count || 0}`;

  const sensors = metrics.latest_sensors || {};
  const activations = metrics.sensor_activation_counts || {};
  document.querySelectorAll(".sensor[data-sensor]").forEach((element) => {
    const name = element.dataset.sensor;
    const blocked = Boolean(sensors[name]);
    element.classList.toggle("blocked", blocked);
    element.querySelector("strong").textContent = blocked ? "BLOCKED" : "CLEAR";
    element.querySelector("small").textContent =
      `${activations[name] || 0} activations`;
  });

  const counts = metrics.counts || {};
  const grid = $("counterGrid");
  grid.innerHTML = "";
  counterDefinitions.forEach(([key, label]) => {
    const row = document.createElement("div");
    row.className = "counter";
    row.innerHTML = `<span>${label}</span><strong>${counts[key] || 0}</strong>`;
    grid.appendChild(row);
  });
}

function recordLabel(record) {
  if (record.type === "telemetry") {
    const distance = record.distance_cm == null ? "NO ECHO" : `${record.distance_cm.toFixed(1)} cm`;
    const blocked = Object.entries(record.sensors || {})
      .filter(([, value]) => value)
      .map(([key]) => key.replaceAll("_", " ").toUpperCase());
    return `Distance ${distance}${blocked.length ? " · Blocked: " + blocked.join(", ") : ""}`;
  }

  let text = record.event || record.message || record.raw || "Event";
  const details = [];
  if (record.distance_cm != null) details.push(`${record.distance_cm.toFixed(1)} cm`);
  if (record.target_clearance_cm != null) details.push(`target ${record.target_clearance_cm.toFixed(1)} cm`);
  if (record.target_duration_ms != null) details.push(`${record.target_duration_ms} ms`);
  if (record.attempt != null) details.push(`${record.attempt}/${record.maximum}`);
  if (details.length) text += ` · ${details.join(" · ")}`;
  return text;
}

function addRecord(record) {
  if (record.type === "blank") return;

  const rawText = String(record.raw || record.message || record.event || "");
  if (rawText.includes("CONTROL_MODE=AUTO")) updateControlMode("AUTO");
  if (rawText.includes("CONTROL_MODE=MANUAL")) updateControlMode("MANUAL");

  state.lastRecordAt = new Date();
  state.timeline.push(record);
  if (state.timeline.length > 500) state.timeline.shift();
  renderTimeline();

  if (record.type === "telemetry" && record.distance_cm != null) {
    addDistancePoint(record.host_time, record.distance_cm);
  }
}

function renderTimeline() {
  const filter = $("timelineFilter").value;
  const container = $("timeline");
  container.innerHTML = "";

  state.timeline
    .filter((record) => filter === "all" || record.category === filter)
    .slice(-300)
    .reverse()
    .forEach((record) => {
      const row = document.createElement("div");
      row.className = `timeline-row ${record.severity || "info"}`;

      const time = record.host_time
        ? new Date(record.host_time).toLocaleTimeString([], {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            fractionalSecondDigits: 3,
          })
        : "—";

      row.innerHTML = `
        <span class="timeline-time">${time}</span>
        <span class="timeline-category">${record.category || "raw"}</span>
        <span>${escapeHtml(recordLabel(record))}</span>
      `;
      container.appendChild(row);
    });
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function initializeChart() {
  if (typeof Chart === "undefined") {
    setStatus("Chart.js could not load. The rest of the dashboard still works.", true);
    return;
  }

  state.distanceChart = new Chart($("distanceChart"), {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        label: "Distance (cm)",
        data: [],
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.15,
      }],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks: { maxTicksLimit: 10 },
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
          suggestedMax: 120,
          title: { display: true, text: "cm" },
        },
      },
      plugins: {
        legend: { display: false },
      },
    },
  });
}

function addDistancePoint(timeText, distance) {
  if (!state.distanceChart) return;
  const chart = state.distanceChart;
  chart.data.labels.push(new Date(timeText).toLocaleTimeString());
  chart.data.datasets[0].data.push(distance);
  while (chart.data.labels.length > 600) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update("none");
}

function resetDistanceChart() {
  if (!state.distanceChart) return;
  state.distanceChart.data.labels = [];
  state.distanceChart.data.datasets[0].data = [];
  state.distanceChart.update();
}

function connectWebSocket() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  state.ws = new WebSocket(`${protocol}//${location.host}/ws/dashboard`);

  state.ws.onopen = () => {
    setStatus(
        "Dashboard connected. Choose USB Serial, Wi-Fi UDP, or Atlas Cloud."
    );
    state.ws.send("ready");
  };

  state.ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.message_type === "initial_status") {
      const data = message.data;
      updateConnection(data.connection);
      updateRun(data.run);
      updateMetrics(data.metrics);
      state.timeline = data.timeline || [];
      renderTimeline();
      return;
    }

    if (message.message_type === "connection_status") {
      updateConnection(message.data);
      return;
    }

    if (message.message_type === "run_status") {
      updateRun(message.data);
      if (message.metrics) updateMetrics(message.metrics);
      return;
    }

    if (message.message_type === "record") {
      updateConnection(message.connection);
      updateRun(message.run);
      updateMetrics(message.metrics);
      addRecord(message.data);
    }
  };

  state.ws.onclose = () => {
    updateConnection({ active_transport: selectedTransport(), serial: { connected: false }, udp: { connected: false } });
    setStatus("Lost connection to Python server. Retrying...", true);
    setTimeout(connectWebSocket, 1500);
  };
}

function updateTimers() {
  if (state.runStartedAt) {
    const seconds = Math.max(0, Math.floor((Date.now() - state.runStartedAt.getTime()) / 1000));
    const hours = String(Math.floor(seconds / 3600)).padStart(2, "0");
    const minutes = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
    const remainder = String(seconds % 60).padStart(2, "0");
    $("runDuration").textContent = `${hours}:${minutes}:${remainder}`;
  } else {
    $("runDuration").textContent = "00:00:00";
  }

  if (state.lastRecordAt) {
    const ageMs = Date.now() - state.lastRecordAt.getTime();
    $("latestMessageAge").textContent =
      ageMs < 1000 ? `${ageMs} ms ago` : `${(ageMs / 1000).toFixed(1)} s ago`;
  }
}

$("refreshPortsButton").addEventListener("click", refreshPorts);
$("transportSelect").addEventListener("change", updateTransportFields);
$("connectButton").addEventListener("click", connectTransport);
$("disconnectButton").addEventListener("click", disconnectTransport);
$("startRunButton").addEventListener("click", startRun);
$("stopRunButton").addEventListener("click", stopRun);
$("timelineFilter").addEventListener("change", renderTimeline);
$("clearTimelineButton").addEventListener("click", () => {
  state.timeline = [];
  renderTimeline();
});

$("remoteStopButton").addEventListener("click", () => sendRemoteCommand("ESTOP"));
$("remoteResumeButton").addEventListener("click", () => sendRemoteCommand("CLEAR_ESTOP"));
$("remotePingButton").addEventListener("click", () => sendRemoteCommand("PING"));

initializeChart();
updateTransportFields();
refreshPorts();
connectWebSocket();
setInterval(updateTimers, 250);


document.addEventListener("DOMContentLoaded", () => {
  setupDriveControls();

  $("autoModeButton").addEventListener("click", () => selectControlMode("AUTO"));
  $("manualModeButton").addEventListener("click", () => selectControlMode("MANUAL"));

  updateControlMode("AUTO");
});


document.addEventListener("DOMContentLoaded", () => {
  const desktopConnectionBadge = $("connectionBadge");
  const mobileConnectionLabel = $("mobileConnectionLabel");
  const mobileStopButton = $("mobileStopButton");

  if (desktopConnectionBadge && mobileConnectionLabel) {
    const syncMobileConnection = () => {
      mobileConnectionLabel.textContent =
        desktopConnectionBadge.textContent || "Disconnected";
    };

    syncMobileConnection();

    new MutationObserver(syncMobileConnection).observe(
      desktopConnectionBadge,
      { childList: true, subtree: true, characterData: true }
    );
  }

  if (mobileStopButton) {
    mobileStopButton.addEventListener("click", () => {
      stopHeldMovement(false);
      sendRemoteCommand("ESTOP");
    });
  }
});
