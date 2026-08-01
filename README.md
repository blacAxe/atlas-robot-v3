# Atlas Robot v3

<p align="center">

<a href="docs/atlas_driving1.mp4">
    <img src="docs/atlas_demo3.gif" width="900"/>
</a>

</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Arduino](https://img.shields.io/badge/Arduino-Uno_R4_WiFi-00979D)
![Render](https://img.shields.io/badge/Cloud-Render-46E3B7)
![Version](https://img.shields.io/badge/Version-v3-blue)
![Status](https://img.shields.io/badge/Status-Active-success)

</p>

<p align="center">

**Autonomous Robotics • Embedded Systems • Cloud Robotics • Real-Time Telemetry**

</p>

<p align="center">

🎥 <b>Full Driving Demo:</b>
<a href="docs/atlas_driving1.mp4">Watch Atlas Navigate Obstacles</a>

</p>

---

## Overview

Atlas Robot is a cloud-connected autonomous robotics platform built to explore embedded software, real-time robotics, networking, and intelligent decision-making.

Rather than creating isolated demonstrations, Atlas evolves through incremental engineering milestones. Each version expands the same physical robot with new hardware, software, and infrastructure while keeping the system observable, testable, and modular.

The current platform combines:

- Autonomous obstacle avoidance
- Remote driving over the Internet
- Secure cloud communication
- Live telemetry streaming
- Mobile and desktop dashboard control
- Structured run recording
- Embedded safety systems

Atlas serves as the physical robotics platform for future ROS 2, micro-ROS, MCCA, and AI integration.

---

# Highlights

✅ Autonomous obstacle avoidance

✅ Manual and autonomous driving modes

✅ Secure cloud communication using WebSockets (WSS)

✅ Mobile-friendly dashboard

✅ Live robot telemetry

✅ Real-time sensor visualization

✅ Remote emergency stop

✅ Structured run recording

✅ Event logging and telemetry playback

✅ Designed for future ROS 2 and AI integration

---

# Current Capabilities

### Autonomous Navigation

- Multi-sensor obstacle avoidance
- Ultrasonic distance sensing
- Five infrared obstacle sensors
- Dynamic path selection
- Direction commitment
- Recovery behaviours
- Emergency stop handling
- Automatic obstacle recovery

### Remote Operation

- Cloud dashboard
- Desktop browser support
- Mobile browser support
- Manual driving controls
- Autonomous mode switching
- Remote emergency stop
- Clear E-Stop
- Live connection monitoring

### Telemetry

- Live robot state
- Navigation decisions
- Recovery state
- Sensor values
- Event timeline
- Motion counters
- Run summaries
- JSON logging

---

# System Architecture

```text
                    Desktop Dashboard
                          │
                          │
                    Mobile Dashboard
                          │
                          │
                  Secure WebSocket (WSS)
                          │
                          ▼
                 Atlas Cloud (Render)
                          │
                          │
                  Secure WebSocket (WSS)
                          │
                          ▼
                Arduino Uno R4 WiFi
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   IR Sensors         HC-SR04         Motor Driver
        │                 │                 │
        └─────────────────┴─────────────────┘
                    Autonomous Controller
```

---

# Hardware

Atlas is built around an Arduino Uno R4 WiFi using a modular four-wheel robot chassis designed for rapid experimentation and incremental upgrades.

### Controller

- Arduino Uno R4 WiFi
- Sensor Shield V5

### Sensors

- HC-SR04 Ultrasonic Sensor
- SG90 Servo Scanner
- Five Infrared Obstacle Sensors

### Drive System

- L298N Dual H-Bridge
- Four TT Geared Motors
- Four-Wheel Skid Steering

### Power

- USB-C for controller power
- Dedicated LiPo battery for motors
- Shared common ground

---

# Software Architecture

Atlas is divided into two major components.

## Embedded Firmware

Running on the Arduino Uno R4 WiFi.

Responsible for:

- Sensor acquisition
- Obstacle avoidance
- Motion control
- Safety systems
- Cloud communication
- Telemetry generation

---

## Atlas Dashboard

Built with:

- FastAPI
- Python
- HTML
- CSS
- JavaScript
- WebSockets

Responsible for:

- Remote control
- Live telemetry
- Robot monitoring
- Run recording
- Event visualization
- Cloud connectivity
- Mobile support

---

# Dashboard

<p align="center">

![Atlas Dashboard](docs/atlas-dashboard1.png)

</p>

Atlas Dashboard provides a live view of the robot while it is operating. Rather than acting as a simple serial monitor, it functions as a real-time robotics control station capable of monitoring, recording, and remotely controlling Atlas from any modern web browser.

The dashboard was designed to make every robot decision observable, allowing embedded software behavior to be analyzed after each run.

---

## Dashboard Features

### Live Robot Status

- Current robot state
- Latest navigation decision
- Recovery state
- Obstacle reasoning
- Connection status
- Control mode
- Run timer

---

### Sensor Monitoring

- Ultrasonic distance
- Five infrared sensor states
- Live sensor updates
- Event timeline
- Telemetry parsing

---

### Remote Driving

Atlas supports both autonomous and manual operation through the same dashboard.

#### Autonomous Mode

The onboard controller performs all navigation decisions independently while the dashboard monitors its behavior in real time.

#### Manual Mode

Operators can remotely drive Atlas using:

- Forward
- Reverse
- Pivot left
- Pivot right
- Forward-left
- Forward-right
- Reverse-left
- Reverse-right

Movement commands are streamed over the cloud while the robot continues reporting live telemetry.

---

### Safety Features

Atlas includes multiple layers of safety.

- Emergency Stop
- Clear E-Stop
- Manual timeout protection
- Automatic obstacle avoidance
- Cloud connection monitoring

If communication stops while driving manually, Atlas automatically halts to prevent uncontrolled movement.

---

# Cloud Robotics

One of the biggest improvements introduced in Version 3 is cloud connectivity.

Instead of requiring a direct USB connection, Atlas can now communicate securely with a cloud-hosted dashboard over the public Internet.

```text
Robot
   │
Secure WebSocket (WSS)
   │
Render Cloud Server
   │
Desktop Browser
   │
Mobile Browser
```

This architecture allows Atlas to be monitored and controlled from virtually anywhere while maintaining a single shared source of telemetry.

---

## Communication

Atlas currently uses secure WebSockets (WSS) for bidirectional communication between the robot and the dashboard.

Current communication includes:

- Robot telemetry
- Live status updates
- Manual driving commands
- Control mode switching
- Emergency stop commands
- Heartbeats
- Connection monitoring

This provides a reliable cloud-based communication layer while remaining simple to deploy and maintain.

---

## Networking Roadmap

Current cloud communication prioritizes reliability and simplicity.

Future versions will migrate toward a hybrid networking architecture:

- UDP for low-latency motion commands
- Secure WebSockets for telemetry
- Dashboard synchronization
- Run recording
- Robot state updates

This combines the responsiveness of UDP with the reliability and flexibility of persistent WebSocket connections.

---

# Run Recording

Every Atlas session can be recorded for later analysis.

Each run stores structured information such as:

- Telemetry
- Robot events
- Motion history
- Sensor values
- Run metadata
- Summary statistics

This allows navigation algorithms to be compared between firmware versions while keeping physical testing repeatable.

---

# Tech Stack

## Embedded

- Arduino C++
- Arduino Uno R4 WiFi
- WiFiS3
- NuSock WebSocket Client
- Servo Library

---

## Backend

- Python
- FastAPI
- Uvicorn
- WebSockets
- PySerial

---

## Frontend

- HTML
- CSS
- JavaScript
- Chart.js

---

## Cloud

- Render
- Secure WebSockets (WSS)
- GitHub Deployment

---

# Getting Started

## Clone the Repository

```bash
git clone https://github.com/blacAxe/atlas-robot-v3.git

cd atlas-robot-v3
```

---

## Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## Start the Dashboard

```powershell
.\start-dashboard.ps1
```

The dashboard automatically displays:

- Local dashboard URL
- Mobile dashboard URL
- Cloud connection support

Open the displayed address in any modern browser to begin controlling or monitoring Atlas.

---

# Repository Structure

```text
atlas-robot-v3/
│
├── app.py                  # FastAPI backend
├── start-dashboard.ps1     # Dashboard launcher
├── requirements.txt
│
├── static/                 # Dashboard frontend
│   ├── dashboard.js
│   ├── dashboard.css
│   └── ...
│
├── templates/
│   └── index.html
│
├── transport/
│   ├── serial
│   ├── udp
│   └── cloud
│
├── docs/
│   ├── images
│   ├── gifs
│   └── videos
│
└── arduino/
    └── atlas_robot_v3.ino
```

---

# Gallery

<p align="center">

![Robot](docs/atlas_front.jfif)

![Dashboard](docs/atlas_dashboard2.png)

![Hardware](docs/atlas_top.jfif)

</p>

More photos, videos, and demonstrations can be found inside the **docs/** directory.

---

# Project Roadmap

Atlas is intentionally built in small engineering milestones. Each version expands the same physical robot while improving the underlying software architecture.

## ✅ Version 1

- Four-wheel robot platform
- Autonomous obstacle avoidance
- Ultrasonic sensing
- Infrared obstacle detection
- Embedded recovery behaviours
- USB Serial telemetry

---

## ✅ Version 2

- Interactive dashboard
- Live telemetry visualization
- Structured run recording
- Event logging
- Manual driving
- Autonomous mode switching
- Emergency stop system

---

## ✅ Version 3 (Current)

- Arduino Uno R4 WiFi
- Cloud-hosted dashboard
- Secure WebSocket communication
- Remote Internet control
- Mobile browser support
- Live cloud telemetry
- Render deployment
- Real-time robot monitoring

---

# Future Roadmap

Atlas is designed as a long-term robotics platform rather than a single demonstration project.

The next milestones focus on improving real-time control, autonomy, and intelligent decision making.

---

## Networking

- Hybrid UDP + WebSocket communication
- Low-latency motion commands
- Automatic transport failover
- Connection quality monitoring
- Multi-robot support
- Robot authentication

---

## Embedded Robotics

- Wheel encoder integration
- Closed-loop motor control
- IMU integration
- Battery monitoring
- OTA firmware updates
- Watchdog recovery

---

## Navigation

- Mapping
- Waypoint navigation
- Autonomous mission execution
- Route planning
- Dynamic obstacle avoidance
- Indoor localization

---

## Dashboard

- Live camera streaming
- Telemetry playback
- Sensor history graphs
- Battery visualization
- Performance analytics
- Multiple robot support

---

## Intelligence

Atlas is ultimately intended to become the embedded robotics platform for larger AI systems.

Planned integrations include:

- ROS 2
- micro-ROS
- MCCA (Memory-Conditioned Cognitive Architecture)
- Atlas memory system
- LLM-assisted navigation
- Natural language robot interaction
- Autonomous task planning

---

# Engineering Goals

Rather than optimizing for the fastest possible robot, Atlas is built to understand how complete robotics systems are engineered.

The project emphasizes:

- Embedded software
- Robotics algorithms
- Networking
- Cloud infrastructure
- Real-time telemetry
- Distributed systems
- Software architecture
- AI integration

Each milestone is designed to improve both the robot and the engineering practices used to build it.

---

# Acknowledgements

This project builds upon the Arduino ecosystem together with many excellent open-source tools and libraries.

Special thanks to the maintainers of:

- Arduino
- FastAPI
- Uvicorn
- Render
- NuSock
- WiFiS3
- GitHub

and the broader open-source robotics community.

---

---

<p align="center">

<b>Atlas Robot v3</b>

Cloud Robotics • Embedded Systems • Real-Time Control • Autonomous Navigation

Building toward the next generation of intelligent robotics.

</p>