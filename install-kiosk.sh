#!/bin/bash
set -e

echo "Setting up fully automated boot kiosk experience for p3-ai-noc..."

# 1. Install R510 launcher locally (if running on R510)
# (Alternatively, p3ainoc launcher is placed in /usr/local/bin)
LAUNCHER_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/p3ainoc"
LAUNCHER_DST="/usr/local/bin/p3ainoc"

if [ -f "$LAUNCHER_SRC" ]; then
    echo "Installing launcher to $LAUNCHER_DST..."
    if [ -w "/usr/local/bin" ]; then
        cp "$LAUNCHER_SRC" "$LAUNCHER_DST"
        chmod +x "$LAUNCHER_DST"
    else
        sudo cp "$LAUNCHER_SRC" "$LAUNCHER_DST"
        sudo chmod +x "$LAUNCHER_DST"
    fi
fi

# 2. Write Kiosk scripts to /usr/local/bin
echo "Writing kiosk TTY scripts..."

KIOSK_TTY1="/usr/local/bin/kiosk-tty1"
KIOSK_TTY2="/usr/local/bin/kiosk-tty2"

TEMP_TTY1=$(mktemp)
cat <<'EOF' > "$TEMP_TTY1"
#!/bin/bash
# Kiosk TTY1: Auto-login matty and launch p3noc
echo "Starting TTY1 Kiosk (p3noc)..."
exec su - matty -c "p3noc"
EOF

TEMP_TTY2=$(mktemp)
cat <<'EOF' > "$TEMP_TTY2"
#!/bin/bash
# Kiosk TTY2: Auto-login matty and SSH to R510 to run p3ainoc
while true; do
  su - matty -c 'ssh -o ConnectTimeout=5 -o ServerAliveInterval=30 \
      -o ServerAliveCountMax=3 \
      -t matty@192.168.1.47 \
      "p3ainoc"'
  sleep 5
done
EOF

chmod +x "$TEMP_TTY1" "$TEMP_TTY2"

if [ -w "/usr/local/bin" ]; then
    cp "$TEMP_TTY1" "$KIOSK_TTY1"
    cp "$TEMP_TTY2" "$KIOSK_TTY2"
else
    sudo cp "$TEMP_TTY1" "$KIOSK_TTY1"
    sudo cp "$TEMP_TTY2" "$KIOSK_TTY2"
    sudo chmod +x "$KIOSK_TTY1" "$KIOSK_TTY2"
fi

rm "$TEMP_TTY1" "$TEMP_TTY2"

# 3. Create systemd override directories
echo "Creating systemd getty override directories..."
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo mkdir -p /etc/systemd/system/getty@tty2.service.d

# 4. Write systemd getty overrides
echo "Writing getty override configurations..."

sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf > /dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty -n -l /usr/local/bin/kiosk-tty1 %I $TERM
Restart=always
RestartSec=5
EOF

sudo tee /etc/systemd/system/getty@tty2.service.d/override.conf > /dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty -n -l /usr/local/bin/kiosk-tty2 %I $TERM
Restart=always
RestartSec=5
EOF

# 5. Reload systemd and restart services
echo "Reloading systemd daemon and restarting TTY1 & TTY2..."
sudo systemctl daemon-reload
sudo systemctl restart getty@tty1
sudo systemctl restart getty@tty2

echo "========================================================"
echo "Kiosk installation complete!"
echo "TTY1 is now configured to automatically run p3noc as user matty."
echo "TTY2 is now configured to automatically SSH to 192.168.1.47"
echo "and run p3ainoc as user matty."
echo ""
echo "Note: Ensure SSH public key auth is configured from matty@T310"
echo "to matty@R510 (192.168.1.47) so that no password is required."
echo "========================================================"
