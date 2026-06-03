# P3 AI NOC: Persistent TUI Dashboard

A persistent, full-screen, terminal-based operations TUI dashboard built using the `textual` library. It monitors system health, AI jobs, model inventory, SSH sessions, and logs for a Dell PowerEdge R510 running Ubuntu 22.04 / 24.04 and Ollama.

---

## TUI Panels (Grid Layout)

1. **Ollama Status**: Displays online/offline status, currently loaded model in memory/VRAM, number of active connections, VRAM footprints, and server version.
2. **System Metrics**: Monitors CPU (percent & bar), RAM (footprint & bar), disk (capacity & bar), system temperature, uptime, and load averages.
3. **Active AI Jobs**: Tracks running generation connections, daily prompt counts, and daily failures today cached in SQLite.
4. **Model Inventory**: Displays installed models list, disk sizes, parameter counts, and quantization levels.
5. **SSH Sessions**: Pulls active user login terminal sessions on the host via the `who` command.
6. **Recent Ollama Logs**: Monochromatic or level-colored log stream tailing the last 15 entries of the `journalctl -u ollama` daemon logs.

---

## Installation & Setup

### 1. Build and Initialize (R510 Node)

To set up the dashboard dependencies, SQLite metrics database, launcher command, and standalone service on the R510 node:

```bash
git clone git@github.com:Mattjhagen/p3-ai-noc.git p3-ai-noc
cd p3-ai-noc
chmod +x install.sh
./install.sh
```

This installs:
- The Python virtual environment (`.venv/`).
- The system launcher: `/usr/local/bin/p3ainoc`.
- The systemd service unit: `/etc/systemd/system/p3-ai-noc.service`.

### 2. Standalone Dashboard Execution

To launch the dashboard manually in full-screen:
```bash
p3ainoc
```
Press **`q`** at any time to exit the dashboard.

---

## Fully Automated Boot Kiosk Experience (T310 Node)

We provide a kiosk installer that sets up a dual-tty headless dashboard environment on the Dell PowerEdge T310:

*   **TTY1**: Automatically logs in user `matty` and launches `p3noc` (located at `/opt/p3-noc`).
*   **TTY2**: Automatically logs in user `matty`, initiates a secure SSH session to the R510 (`192.168.1.47`), and launches `p3ainoc` inside an active terminal session. It automatically reconnects within 5 seconds if the connection drops.

### Prerequisites (Kiosk Mode)
Ensure key-based passwordless SSH authentication is established from the T310 to the R510 for user `matty`:
```bash
ssh-copy-id matty@192.168.1.47
```

### Kiosk Installation
Run the kiosk setup on the T310:
```bash
chmod +x install-kiosk.sh
./install-kiosk.sh
```

---

## Rollback Procedure

If you need to disable autologin kiosk mode and restore standard TTY login shells on the T310 console:

1. Remove the getty systemd override configurations:
   ```bash
   sudo rm -f /etc/systemd/system/getty@tty1.service.d/override.conf
   sudo rm -f /etc/systemd/system/getty@tty2.service.d/override.conf
   ```

2. Delete the login wrapper scripts:
   ```bash
   sudo rm -f /usr/local/bin/kiosk-tty1
   sudo rm -f /usr/local/bin/kiosk-tty2
   ```

3. Reload systemd and restart the terminal gettys to restore password prompt login screens:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart getty@tty1
   sudo systemctl restart getty@tty2
   ```
