#!/bin/bash
set -e

# Get absolute path of script directory
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing r510-noc operations dashboard..."
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

# 4. Create launcher script
LAUNCHER_PATH="/usr/local/bin/r510-status"
echo "Creating launcher at $LAUNCHER_PATH..."

TEMP_LAUNCHER=$(mktemp)
cat <<EOF > "$TEMP_LAUNCHER"
#!/bin/bash
# r510-status launcher script
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

# Ensure data directory exists and is writeable
mkdir -p "$REPO_DIR/data"
chmod 777 "$REPO_DIR/data" || true

echo "========================================================"
echo "Installation complete!"
echo "You can now run 'r510-status' in your terminal."
echo ""
echo "To automatically display the dashboard upon SSH login,"
echo "add the following snippet to the end of your ~/.bashrc:"
echo ""
echo 'if [ -n "$SSH_CONNECTION" ]; then'
echo '    r510-status'
echo 'fi'
echo "========================================================"
