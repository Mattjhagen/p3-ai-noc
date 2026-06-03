import os
import sqlite3
import subprocess
import json
import re
from datetime import datetime, timezone

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(REPO_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "metrics.db")

# Regex pattern for Gin HTTP logs:
# Example: [GIN] 2026/06/03 - 15:49:37 | 200 |   1.849201s |       127.0.0.1 | POST     "/api/chat"
# Example: [GIN] 2024/05/21 - 10:15:30 | 200 |   82.985212ms |       127.0.0.1 | POST     "/api/chat"
# We match status, latency, IP, method, and endpoint path.
gin_pattern = re.compile(
    r'\[GIN\]\s+\d{4}/\d{2}/\d{2}\s+-\s+\d{2}:\d{2}:\d{2}\s+\|\s+'
    r'(?P<status>\d{3})\s+\|\s+'
    r'(?P<latency>[\d\.]+(?:µs|ms|s|ns|us))\s+\|\s+'
    r'(?P<ip>\S+)\s+\|\s+'
    r'(?P<method>[A-Z]+)\s+'
    r'"?(?P<path>/api/[a-zA-Z0-9_\-/]+)"?'
)

# Regex pattern for Ollama standard HTTP access logs (no duration/latency):
# Example: HTTP Request: POST http://127.0.0.1:11434/api/generate "HTTP/1.1 200 OK"
std_pattern = re.compile(
    r'HTTP Request:\s+(?P<method>[A-Z]+)\s+'
    r'https?://[\d\.\:]+(?P<path>/api/[a-zA-Z0-9_\-/]+)\s+'
    r'"HTTP/\d\.\d\s+(?P<status>\d{3})\s+[^"]*"'
)

def parse_latency_to_ms(latency_str: str) -> float:
    """Converts Gin latency string (e.g. 1.2s, 80ms, 450µs) into milliseconds."""
    match = re.match(r'([\d\.]+)(µs|us|ms|s|ns)', latency_str)
    if not match:
        return 0.0
    val, unit = match.groups()
    val = float(val)
    if unit == 's':
        return val * 1000.0
    elif unit == 'ms':
        return val
    elif unit in ('µs', 'us'):
        return val / 1000.0
    elif unit == 'ns':
        return val / 1000000.0
    return val

class MetricsService:
    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cursor TEXT UNIQUE,
                    timestamp DATETIME NOT NULL,
                    status_code INTEGER,
                    latency_ms REAL,
                    endpoint TEXT,
                    method TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    def update_metrics_from_journal(self):
        """Reads systemd journal logs, parses requests, and updates SQLite DB."""
        # 1. Fetch last cursor from metadata
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_cursor'")
        row = cursor.fetchone()
        last_cursor = row['value'] if row else None

        # 2. Build journalctl command
        # We query journalctl in json format.
        cmd = ["journalctl", "-u", "ollama", "-o", "json"]
        if last_cursor:
            cmd.extend(["--after-cursor", last_cursor])
        else:
            # First run, fetch logs since 24 hours ago
            cmd.extend(["--since", "24 hours ago"])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            log_output = result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # journalctl may fail if the user lacks permissions or journalctl is missing
            return False, f"Journalctl error: {str(e)}"

        # 3. Parse lines
        lines = log_output.strip().split("\n")
        new_requests = []
        new_last_cursor = last_cursor

        for line in lines:
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_cursor = data.get("__CURSOR")
            if entry_cursor:
                new_last_cursor = entry_cursor

            message = data.get("MESSAGE", "")
            if not message:
                continue

            # Try parsing with GIN pattern (with latency)
            match = gin_pattern.search(message)
            if match:
                group = match.groupdict()
                status_code = int(group['status'])
                latency_ms = parse_latency_to_ms(group['latency'])
                method = group['method']
                endpoint = group['path']

                rt_ts = data.get("__REALTIME_TIMESTAMP")
                if rt_ts:
                    ts = datetime.fromtimestamp(int(rt_ts) / 1000000.0, tz=timezone.utc)
                else:
                    ts = datetime.now(timezone.utc)

                new_requests.append((entry_cursor, ts.isoformat(), status_code, latency_ms, endpoint, method))
                continue

            # Try parsing with standard request pattern (no latency)
            match = std_pattern.search(message)
            if match:
                group = match.groupdict()
                status_code = int(group['status'])
                latency_ms = None
                method = group['method']
                endpoint = group['path']

                rt_ts = data.get("__REALTIME_TIMESTAMP")
                if rt_ts:
                    ts = datetime.fromtimestamp(int(rt_ts) / 1000000.0, tz=timezone.utc)
                else:
                    ts = datetime.now(timezone.utc)

                new_requests.append((entry_cursor, ts.isoformat(), status_code, latency_ms, endpoint, method))

        # 4. Save to DB
        if new_requests:
            with self.conn:
                self.conn.executemany("""
                    INSERT OR IGNORE INTO requests (cursor, timestamp, status_code, latency_ms, endpoint, method)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, new_requests)

        # 5. Save progress cursor
        if new_last_cursor and new_last_cursor != last_cursor:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO metadata (key, value)
                    VALUES ('last_cursor', ?)
                """, (new_last_cursor,))

        return True, None

    def get_metrics(self):
        """
        Retrieves aggregated stats from SQLite DB.
        Returns:
            {
                "total_requests": int,
                "requests_today": int,
                "avg_latency_ms": float or None,
                "failures": int,
                "last_request_time": str or None
            }
        """
        stats = {
            "total_requests": 0,
            "requests_today": 0,
            "avg_latency_ms": None,
            "failures": 0,
            "last_request_time": None
        }

        try:
            cursor = self.conn.cursor()

            # Total requests
            cursor.execute("SELECT COUNT(*) FROM requests")
            stats["total_requests"] = cursor.fetchone()[0]

            # Requests today (local timezone midnight start)
            # Find start of today in UTC to query ISO-stored timestamps
            local_now = datetime.now()
            local_today_start = datetime(local_now.year, local_now.month, local_now.day)
            utc_today_start = local_today_start.astimezone(timezone.utc)

            cursor.execute("SELECT COUNT(*) FROM requests WHERE timestamp >= ?", (utc_today_start.isoformat(),))
            stats["requests_today"] = cursor.fetchone()[0]

            # Average latency (only of requests that had latency parsed)
            cursor.execute("SELECT AVG(latency_ms) FROM requests WHERE latency_ms IS NOT NULL")
            val = cursor.fetchone()[0]
            stats["avg_latency_ms"] = float(val) if val is not None else None

            # Failures (status >= 400)
            cursor.execute("SELECT COUNT(*) FROM requests WHERE status_code >= 400")
            stats["failures"] = cursor.fetchone()[0]

            # Last request time
            cursor.execute("SELECT timestamp FROM requests ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            stats["last_request_time"] = row[0] if row else None

        except sqlite3.Error:
            pass

        return stats

    def get_active_requests(self, port=11434):
        """
        Estimates active/established TCP connections to Ollama's port.
        """
        # Try 'ss' command
        try:
            cmd = f"ss -t -n state established '( sport = :{port} or dport = :{port} )' | wc -l"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                lines = int(res.stdout.strip())
                return max(0, lines - 1)
        except Exception:
            pass

        # Fallback to psutil
        try:
            import psutil
            count = 0
            for conn in psutil.net_connections(kind='tcp'):
                if (conn.laddr and conn.laddr.port == port) or (conn.raddr and conn.raddr.port == port):
                    if conn.status == 'ESTABLISHED':
                        count += 1
            return count
        except Exception:
            return 0

    def close(self):
        self.conn.close()
