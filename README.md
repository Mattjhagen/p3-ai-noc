# r510-noc: SSH-First Operations Dashboard

A lightweight, fast, terminal-based operations panel for the Dell PowerEdge R510 running Ubuntu 22.04 LTS and Ollama. This dashboard is designed to run automatically when you SSH into the server, presenting system metrics, Ollama API performance details, active alerts, and operator quick commands.

---

## ╔══════════════════════════════════════╗
## ║      P3 AI INFERENCE NODE (R510)     ║
## ╚══════════════════════════════════════╝

## Features

1. **Lightweight & Fast**: Executes in ~150-200ms upon login, ensuring no noticeable delay when starting an SSH session.
2. **Ollama Integration**: Polls active models, memory footprint (VRAM), installed models, version, and server health.
3. **Incremental Log Parsing**: Uses a stateful `journalctl` parsing system mapping SQLite database records to journal entry cursors, enabling rapid, delta-based request audits.
4. **Local SQLite Cache**: Saves request counts, timestamps, latencies, and endpoints locally in `data/metrics.db`.
5. **System Resource Monitoring**: Inspects CPU, RAM, swap, disk capacity, load averages, uptime, and identifies the top 5 memory-consuming processes.
6. **Dynamic Alerts**: Evaluates thresholds and triggers colored status panels (RED / YELLOW / GREEN) for instant health visual queues.
7. **Quick Commands Console**: Keeps common commands (Ollama operations, logs streaming, system monitors) visible for copy-paste speed.

---

## Repository Structure

```
r510-noc/
├── dashboard.py          # Main layout builder & CLI entry point
├── services/             # Core service modules
│   ├── __init__.py       # Package indicator
│   ├── metrics_service.py # SQLite operations and journal log parsing
│   ├── ollama_service.py  # REST API requests to Ollama
│   └── system_service.py  # Host diagnostics using psutil
├── data/
│   └── metrics.db        # Dynamically created SQLite database
├── install.sh            # Setup venv and system launcher
├── requirements.txt      # Dependency specification
└── README.md             # This document
```

---

## System Requirements

- **Operating System**: Ubuntu 22.04 LTS (or compatible Linux/macOS environment)
- **Python**: Version 3.10+
- **Privileges**: User should belong to the `systemd-journal` or `adm` group to query `journalctl -u ollama` without root. If not, the script falls back gracefully to display cached local metrics.

---

## Installation

1. **Clone the repository** to a directory on your R510 server:
   ```bash
   git clone git@github.com:Mattjhagen/p3-ai-noc.git r510-noc
   cd r510-noc
   ```

2. **Run the installer script**:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
   This will:
   - Create a Python virtual environment at `.venv/`.
   - Install required dependencies (`rich`, `psutil`, `requests`).
   - Create the launcher script at `/usr/local/bin/r510-status`.

3. **Verify the installation**:
   ```bash
   r510-status
   ```

---

## SSH Login Integration

To trigger the dashboard automatically whenever you log in via SSH, add the following connection guard to the bottom of your `~/.bashrc` (or `~/.zshrc`):

```bash
# Display R510 status dashboard on SSH connections
if [ -n "$SSH_CONNECTION" ]; then
    r510-status
fi
```

Now, the dashboard will render a clean, professional display upon every SSH login, then immediately exit and place you at your command prompt.

---

## Alert Rules

The dashboard dynamically reports system status based on:

* 🔴 **RED ALERT**:
  - Ollama Service is `OFFLINE`
  - RAM Usage exceeds `90%`
  - Root Disk Usage exceeds `90%`
* 🟡 **YELLOW WARNING**:
  - RAM Usage is between `80%` and `90%`
  - 1-minute System Load Average exceeds the host CPU core count
* 🟢 **GREEN HEALTHY**:
  - All status parameters are within normal ranges.
