#!/usr/bin/env python3
import os
import sys
import subprocess
from datetime import datetime, timezone

# Add the repository path to Python's path so we can import services
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

from services.ollama_service import OllamaService
from services.system_service import SystemService, format_bytes
from services.metrics_service import MetricsService

# Import Rich and Textual elements
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.box import ROUNDED

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Grid

def get_ssh_sessions() -> str:
    """Executes 'who' command to list currently active SSH/local sessions."""
    try:
        res = subprocess.run(["who"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return "No active user sessions."
    except Exception as e:
        return f"Error retrieving sessions: {e}"

def get_recent_logs() -> str:
    """Retrieves the last 15 lines of Ollama service daemon logs via journalctl."""
    try:
        res = subprocess.run(
            ["journalctl", "-u", "ollama", "-n", "15", "--no-pager"], 
            capture_output=True, 
            text=True, 
            timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return "No Ollama logs found."
    except Exception as e:
        return f"Error retrieving logs: {e}\n(User may need systemd-journal permissions)"

def make_progress_bar(percent: float, width: int = 15) -> str:
    """Generates a simple colored text-based progress bar."""
    filled = int(round((percent / 100.0) * width))
    empty = width - filled
    
    if percent > 90:
        color = "red"
    elif percent > 80:
        color = "yellow"
    else:
        color = "green"
        
    bar_chars = "█" * filled
    empty_chars = "░" * empty
    return f"[{color}]{bar_chars}[/{color}]{empty_chars}"

class P3AiNocDashboard(App):
    TITLE = "P3 AI Inference Node operations dashboard (Dell PowerEdge R510)"
    
    CSS = """
    Grid {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr 1fr 1.3fr;
        padding: 0;
    }
    .panel-widget {
        height: 100%;
        width: 100%;
        padding: 0;
        margin: 0;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit Dashboard"),
    ]

    def __init__(self):
        super().__init__()
        self.ollama_srv = OllamaService()
        self.system_srv = SystemService()
        self.metrics_srv = MetricsService()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Grid():
            yield Static(id="ollama-status", classes="panel-widget")
            yield Static(id="system-metrics", classes="panel-widget")
            yield Static(id="active-jobs", classes="panel-widget")
            yield Static(id="model-inventory", classes="panel-widget")
            yield Static(id="ssh-sessions", classes="panel-widget")
            yield Static(id="ollama-logs", classes="panel-widget")
        yield Footer()

    def on_mount(self) -> None:
        self.update_dashboard()
        self.set_interval(5.0, self.update_dashboard)

    def update_dashboard(self) -> None:
        # Run systemd journal log parsing and SQLite update
        self.metrics_srv.update_metrics_from_journal()

        # Query latest stats
        sys_stats = self.system_srv.get_system_stats()
        ollama_status = self.ollama_srv.get_status()
        db_metrics = self.metrics_srv.get_metrics()
        active_requests = self.metrics_srv.get_active_requests()
        ssh_sessions = get_ssh_sessions()
        recent_logs = get_recent_logs()

        # Update each panel UI
        self.query_one("#ollama-status", Static).update(self.render_ollama_status(ollama_status, active_requests))
        self.query_one("#system-metrics", Static).update(self.render_system_metrics(sys_stats))
        self.query_one("#active-jobs", Static).update(self.render_active_jobs(active_requests, db_metrics, ollama_status["online"]))
        self.query_one("#model-inventory", Static).update(self.render_model_inventory(ollama_status))
        self.query_one("#ssh-sessions", Static).update(self.render_ssh_sessions(ssh_sessions))
        self.query_one("#ollama-logs", Static).update(self.render_ollama_logs(recent_logs))

    # Panel rendering helpers
    def render_ollama_status(self, stats, active_reqs) -> Panel:
        status_val = "[bold green]ONLINE[/bold green]" if stats["online"] else "[bold red]OFFLINE[/bold red]"
        
        if stats["active_models"]:
            active_model = ", ".join([m["name"] for m in stats["active_models"]])
            vram_total = sum([m["vram"] for m in stats["active_models"]])
            vram_str = format_bytes(vram_total)
        else:
            active_model = "None (Idle)"
            vram_str = "0 B"
            
        t = Table.grid(padding=(0, 2))
        t.add_row("[bold]Ollama Status:[/]", status_val)
        t.add_row("[bold]Loaded Model:[/]", f"[cyan]{active_model}[/]")
        t.add_row("[bold]Active Requests:[/]", f"[cyan]{active_reqs}[/]")
        t.add_row("[bold]Model VRAM Usage:[/]", vram_str)
        t.add_row("[bold]Ollama Version:[/]", stats["version"])
        
        return Panel(
            t, 
            title="[bold green]1. Ollama API Service Status[/]", 
            border_style="green" if stats["online"] else "red",
            box=ROUNDED
        )

    def render_system_metrics(self, stats) -> Panel:
        t = Table.grid(padding=(0, 1))
        
        cpu_bar = make_progress_bar(stats["cpu_percent"])
        t.add_row("[bold]CPU Usage:[/]", f"{stats['cpu_percent']:.1f}%", cpu_bar)
        
        ram_used = stats["ram_used"] / (1024**3)
        ram_total = stats["ram_total"] / (1024**3)
        ram_bar = make_progress_bar(stats["ram_percent"])
        t.add_row("[bold]RAM Usage:[/]", f"{ram_used:.1f} GB / {ram_total:.0f} GB ({stats['ram_percent']:.1f}%)", ram_bar)
        
        disk_free = format_bytes(stats["disk_free"])
        disk_total = format_bytes(stats["disk_total"])
        disk_bar = make_progress_bar(stats["disk_percent"])
        t.add_row("[bold]Disk Free:[/]", f"{disk_free} / {disk_total} ({stats['disk_percent']:.1f}% used)", disk_bar)
        
        temp_str = f"{stats['cpu_temp']:.1f} °C" if stats["cpu_temp"] is not None else "N/A"
        t.add_row("[bold]CPU Temp:[/]", temp_str, "")
        
        t.add_row("[bold]Uptime:[/]", stats["uptime_str"], "")
        t.add_row(
            "[bold]Load Avg:[/]", 
            f"{stats['load_1m']:.2f}, {stats['load_5m']:.2f}, {stats['load_15m']:.2f}  [dim](CPUs: {stats['cpu_count']})[/]",
            ""
        )
        
        return Panel(t, title="[bold blue]2. System Metrics Status[/]", border_style="blue", box=ROUNDED)

    def render_active_jobs(self, active_reqs, metrics, online) -> Panel:
        t = Table.grid(padding=(0, 2))
        t.add_row("[bold]Running Generations:[/]", f"[cyan]{active_reqs}[/]")
        t.add_row("[bold]Prompt Count Today:[/]", f"[green]{metrics['requests_today']}[/]")
        t.add_row("[bold]Failures Today:[/]", f"[red]{metrics['failures_today']}[/]" if metrics['failures_today'] > 0 else "0")
        t.add_row("[bold]Total Requests (DB):[/]", str(metrics["total_requests"]))
        
        # Overall status evaluation
        if not online:
            status_text = "[bold red]OFFLINE[/bold red]"
        elif active_reqs > 0:
            status_text = "[bold yellow]PROCESSING[/bold yellow]"
        else:
            status_text = "[bold green]IDLE[/bold green]"
            
        t.add_row("[bold]Inference Status:[/]", status_text)
        
        return Panel(t, title="[bold cyan]3. Active AI Jobs[/]", border_style="cyan", box=ROUNDED)

    def render_model_inventory(self, stats) -> Panel:
        if not stats["installed_models"]:
            return Panel("[dim italic]No models found.[/dim italic]", title="[bold magenta]4. Model Inventory[/]", border_style="magenta", box=ROUNDED)
            
        t = Table(box=None, padding=(0, 1), show_header=True, expand=True)
        t.add_column("Model Name", style="bold cyan")
        t.add_column("Size", justify="right", style="green")
        t.add_column("Params", justify="right", style="yellow")
        t.add_column("Quant", justify="right", style="dim")
        
        for m in stats["installed_models"]:
            t.add_row(
                m["name"],
                format_bytes(m["size"]),
                m["parameter_size"],
                m["quantization"]
            )
            
        return Panel(t, title="[bold magenta]4. Model Inventory[/]", border_style="magenta", box=ROUNDED)

    def render_ssh_sessions(self, sessions_str) -> Panel:
        lines = sessions_str.strip().split("\n")
        formatted = Text()
        for line in lines:
            if not line:
                continue
            formatted.append(f" • {line}\n", style="white")
            
        return Panel(formatted, title="[bold yellow]5. Active SSH Sessions[/]", border_style="yellow", box=ROUNDED)

    def render_ollama_logs(self, logs_str) -> Panel:
        lines = logs_str.strip().split("\n")
        formatted = Text()
        for line in lines:
            if not line:
                continue
            # Color lines by severity
            if "error" in line.lower() or "fail" in line.lower() or "err" in line.lower():
                formatted.append(f"{line}\n", style="bold red")
            elif "warning" in line.lower() or "warn" in line.lower():
                formatted.append(f"{line}\n", style="yellow")
            else:
                formatted.append(f"{line}\n", style="dim")
                
        return Panel(formatted, title="[bold white]6. Recent Ollama Daemon Logs[/]", border_style="white", box=ROUNDED)

    def on_unmount(self) -> None:
        self.metrics_srv.close()

if __name__ == "__main__":
    P3AiNocDashboard().run()
