#!/bin/bash
set -e

# Get absolute path of script directory
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing P3 AI NOC persistent TUI dashboard..."
echo "Repository directory: $REPO_DIR"

# 1. Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed on this host." >&2
    exit 1
fi

# 2. Create venv
if [ ! -d "$REPO_DIR/.venv" ]; then
    echo "Creating Python virtual environment in $REPO_DIR/.venv..."
    python3 -m venv "$REPO_DIR/.venv"
fi

# 3. Upgrade pip and install requirements
echo "Installing dependencies..."
"$REPO_DIR/.venv/bin/pip" install --upgrade pip
"$REPO_DIR/.venv/bin/pip" install -r "$REPO_DIR/requirements.txt"

# 4. Install the launcher script p3ainoc
LAUNCHER_PATH="/usr/local/bin/p3ainoc"
echo "Creating launcher at $LAUNCHER_PATH..."

TEMP_LAUNCHER=$(mktemp)
cat <<EOF > "$TEMP_LAUNCHER"
#!/bin/bash
# p3ainoc launcher script
export PYTHONIOENCODING=utf-8
exec "$REPO_DIR/.venv/bin/python" "$REPO_DIR/dashboard.py" "\$@"
EOF

chmod +x "$TEMP_LAUNCHER"

# Copy to /usr/local/bin using sudo if not writable
if [ -w "/usr/local/bin" ]; then
    cp "$TEMP_LAUNCHER" "$LAUNCHER_PATH"
else
    echo "Requires sudo permission to write to $LAUNCHER_PATH"
    sudo cp "$TEMP_LAUNCHER" "$LAUNCHER_PATH"
    sudo chmod +x "$LAUNCHER_PATH"
fi

rm "$TEMP_LAUNCHER"

# 5. Make sure local scripts/p3ainoc is synchronized
mkdir -p "$REPO_DIR/scripts"
cp "$LAUNCHER_PATH" "$REPO_DIR/scripts/p3ainoc"

# Ensure data directory exists and is writeable
mkdir -p "$REPO_DIR/data"
chmod 777 "$REPO_DIR/data" || true

# 6. Install systemd service
SERVICE_PATH="/etc/systemd/system/p3-ai-noc.service"
if [ -d "/etc/systemd/system" ]; then
    echo "Registering systemd service at $SERVICE_PATH..."
    if [ -w "/etc/systemd/system" ]; then
        cp "$REPO_DIR/p3-ai-noc.service" "$SERVICE_PATH"
    else
        sudo cp "$REPO_DIR/p3-ai-noc.service" "$SERVICE_PATH"
    fi
    echo "Systemd service file copied."
    echo "To run the dashboard as a service on tty2, execute:"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable p3-ai-noc.service"
    echo "  sudo systemctl start p3-ai-noc.service"
fi

echo "========================================================"
echo "Installation complete!"
echo "You can now run 'p3ainoc' to open the full-screen TUI."
echo "========================================================"
