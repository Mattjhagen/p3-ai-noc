#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone
import math

# Add the repository path to Python's path so we can import services
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

from services.ollama_service import OllamaService
from services.system_service import SystemService, format_bytes
from services.metrics_service import MetricsService

# Import Rich elements
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.box import DOUBLE, ROUNDED, SQUARE, HEAVY

def get_time_ago(iso_str) -> str:
    """Calculates human-readable time difference from an ISO timestamp in UTC."""
    if not iso_str:
        return "Never"
    try:
        # Parse ISO string
        # Handle formats with/without Z or offset
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        diff = now - dt

        seconds = diff.total_seconds()
        if seconds < 0:
            return "Just now"
        if seconds < 60:
            return f"{int(seconds)}s ago"
        minutes = seconds / 60
        if minutes < 60:
            return f"{int(minutes)}m ago"
        hours = minutes / 60
        if hours < 24:
            return f"{int(hours)}h ago"
        days = hours / 24
        return f"{int(days)}d ago"
    except Exception:
        return "N/A"

def make_progress_bar(percent: float, width: int = 15) -> str:
    """Generates a simple colored text-based progress bar."""
    filled = int(round((percent / 100.0) * width))
    empty = width - filled
    
    # Choose color based on percent
    if percent > 90:
        color = "red"
    elif percent > 80:
        color = "yellow"
    else:
        color = "green"
        
    bar_chars = "█" * filled
    empty_chars = "░" * empty
    return f"[{color}]{bar_chars}[/{color}]{empty_chars}"

def main():
    # Initialize services
    ollama_srv = OllamaService()
    system_srv = SystemService()
    metrics_srv = MetricsService()

    # Update database metrics from journalctl before displaying
    # (Failure here is caught and handled gracefully, e.g. lack of permissions)
    db_updated, db_err = metrics_srv.update_metrics_from_journal()

    # Gather data
    sys_stats = system_srv.get_system_stats()
    ollama_stats = ollama_srv.get_status()
    db_metrics = metrics_srv.get_metrics()
    active_requests = metrics_srv.get_active_requests()

    # Close SQLite connection
    metrics_srv.close()

    # Evaluate alerts
    alerts_red = []
    alerts_yellow = []

    # Red alerts
    if not ollama_stats["online"]:
        alerts_red.append("Ollama status: OFFLINE")
    if sys_stats["ram_percent"] > 90:
        alerts_red.append(f"RAM usage > 90% ({sys_stats['ram_percent']:.1f}%)")
    if sys_stats["disk_percent"] > 90:
        alerts_red.append(f"Disk usage > 90% ({sys_stats['disk_percent']:.1f}%)")

    # Yellow alerts
    if sys_stats["ram_percent"] > 80 and sys_stats["ram_percent"] <= 90:
        alerts_yellow.append(f"RAM usage > 80% ({sys_stats['ram_percent']:.1f}%)")
    if sys_stats["load_1m"] > sys_stats["cpu_count"]:
        alerts_yellow.append(f"Load Average ({sys_stats['load_1m']:.2f}) > CPU count ({sys_stats['cpu_count']})")

    # Determine status color/tag
    if alerts_red:
        status_text = Text(" ● CRITICAL STATUS ", style="bold white on red")
    elif alerts_yellow:
        status_text = Text(" ● WARNING STATUS ", style="bold black on yellow")
    else:
        status_text = Text(" ● HEALTHY STATUS ", style="bold white on green")

    # Initialize Console
    console = Console()

    # 1. HEADER PANEL
    header_content = Text()
    header_content.append("DELL POWEREDGE R510 Operations Dashboard\n", style="bold cyan")
    header_content.append("Ubuntu 22.04 LTS Inference Node status", style="dim italic")
    
    # 2. OLLAMA STATUS PANEL
    ollama_table = Table.grid(padding=(0, 1))
    
    # Status formatting
    if ollama_stats["online"]:
        status_val = "[bold green]ONLINE[/bold green]"
    else:
        status_val = "[bold red]OFFLINE[/bold red]"
    
    # Determine loaded models
    if ollama_stats["active_models"]:
        active_model_names = ", ".join([m["name"] for m in ollama_stats["active_models"]])
    else:
        active_model_names = "None (Idle)"
        
    installed_count = len(ollama_stats["installed_models"])
    
    # Average latency formatting
    avg_latency = db_metrics["avg_latency_ms"]
    if avg_latency is not None:
        avg_latency_str = f"{avg_latency / 1000.0:.2f}s"
    else:
        avg_latency_str = "N/A"
        
    last_req_str = get_time_ago(db_metrics["last_request_time"])

    ollama_table.add_row("[bold]Ollama Status:[/]", status_val)
    ollama_table.add_row("[bold]Active Model:[/]", f"[cyan]{active_model_names}[/]")
    ollama_table.add_row("[bold]Models Installed:[/]", str(installed_count))
    ollama_table.add_row("[bold]Active Requests:[/]", f"[cyan]{active_requests}[/]")
    ollama_table.add_row("[bold]Avg Response Time:[/]", avg_latency_str)
    ollama_table.add_row("[bold]Last Request:[/]", last_req_str)
    
    # Detailed list of installed models
    if installed_count > 0:
        models_text = Text("\nInstalled Models:\n", style="bold underline")
        for m in ollama_stats["installed_models"]:
            size_str = format_bytes(m["size"])
            models_text.append(f" • {m['name']} ({size_str}, {m['parameter_size']}, {m['quantization']})\n", style="dim")
    else:
        models_text = Text("\nNo models installed.", style="dim italic")

    ollama_panel_content = Columns([ollama_table, models_text], expand=True)
    ollama_panel = Panel(
        ollama_panel_content,
        title="[bold green]Ollama API Service[/]",
        border_style="green" if ollama_stats["online"] else "red",
        box=ROUNDED
    )

    # 3. SYSTEM STATS PANEL
    sys_table = Table.grid(padding=(0, 1))
    
    # CPU
    cpu_bar = make_progress_bar(sys_stats["cpu_percent"])
    sys_table.add_row("[bold]CPU Usage:[/]", f"{sys_stats['cpu_percent']:.1f}%", cpu_bar)
    
    # RAM
    ram_used_gb = sys_stats["ram_used"] / (1024**3)
    ram_total_gb = sys_stats["ram_total"] / (1024**3)
    ram_bar = make_progress_bar(sys_stats["ram_percent"])
    sys_table.add_row(
        "[bold]RAM Usage:[/]", 
        f"{ram_used_gb:.1f}GB / {ram_total_gb:.0f}GB ({sys_stats['ram_percent']:.1f}%)", 
        ram_bar
    )
    
    # Swap
    swap_used_gb = sys_stats["swap_used"] / (1024**3)
    swap_total_gb = sys_stats["swap_total"] / (1024**3)
    swap_bar = make_progress_bar(sys_stats["swap_percent"])
    sys_table.add_row(
        "[bold]Swap Usage:[/]", 
        f"{swap_used_gb:.1f}GB / {swap_total_gb:.1f}GB ({sys_stats['swap_percent']:.1f}%)", 
        swap_bar
    )

    # Disk Free
    disk_free_str = format_bytes(sys_stats["disk_free"])
    disk_total_str = format_bytes(sys_stats["disk_total"])
    disk_bar = make_progress_bar(sys_stats["disk_percent"])
    sys_table.add_row(
        "[bold]Disk Free:[/]", 
        f"{disk_free_str} / {disk_total_str} ({sys_stats['disk_percent']:.1f}% used)", 
        disk_bar
    )

    # Load Average
    sys_table.add_row(
        "[bold]Load Average:[/]", 
        f"{sys_stats['load_1m']:.2f}, {sys_stats['load_5m']:.2f}, {sys_stats['load_15m']:.2f}  [dim](CPUs: {sys_stats['cpu_count']})[/]",
        ""
    )

    # Uptime
    sys_table.add_row("[bold]Uptime:[/]", sys_stats["uptime_str"], "")

    sys_panel = Panel(
        sys_table,
        title="[bold blue]System Health Monitoring[/]",
        border_style="blue",
        box=ROUNDED
    )

    # 4. TOP PROCESSES TABLE
    proc_table = Table(
        title="Top 5 Memory-Consuming Processes",
        title_style="bold magenta",
        box=ROUNDED,
        expand=True,
        border_style="magenta"
    )
    proc_table.add_column("PID", justify="right", style="cyan")
    proc_table.add_column("Process Name", style="bold white")
    proc_table.add_column("Memory %", justify="right", style="yellow")
    proc_table.add_column("Memory Usage (RSS)", justify="right", style="green")

    for p in sys_stats["top_processes"]:
        proc_table.add_row(
            str(p["pid"]),
            p["name"],
            f"{p['mem_percent']:.1f}%",
            format_bytes(p["mem_bytes"])
        )

    # 5. ALERTS PANEL
    alerts_lines = []
    if not alerts_red and not alerts_yellow:
        alerts_lines.append(Text(" ✔ All operations healthy. No system warnings.", style="bold green"))
    else:
        for alert in alerts_red:
            alerts_lines.append(Text(f" ✘ CRITICAL: {alert}", style="bold red"))
        for alert in alerts_yellow:
            alerts_lines.append(Text(f" ⚠ WARNING: {alert}", style="bold yellow"))
            
    if not db_updated:
        alerts_lines.append(Text(f" ℹ NOTE: SQLite metrics local sync skipped ({db_err})", style="dim yellow"))

    alerts_content = Text("\n").join(alerts_lines)

    alerts_panel = Panel(
        alerts_content,
        title="System Operations Alerts",
        border_style="red" if alerts_red else ("yellow" if alerts_yellow else "green"),
        box=ROUNDED
    )

    # 6. QUICK COMMANDS
    commands_table = Table.grid(padding=(0, 2))
    commands_table.add_row("[bold yellow]ollama list[/]", "[dim]List locally downloaded LLM models[/]")
    commands_table.add_row("[bold yellow]ollama ps[/]", "[dim]Show running/loaded models & VRAM sizes[/]")
    commands_table.add_row("[bold yellow]systemctl status ollama[/]", "[dim]Check status of Ollama daemon service[/]")
    commands_table.add_row("[bold yellow]journalctl -u ollama -f[/]", "[dim]Stream/follow Ollama daemon journal logs[/]")
    commands_table.add_row("[bold yellow]htop[/]", "[dim]Open interactive system monitor process viewer[/]")

    commands_panel = Panel(
        commands_table,
        title="[bold yellow]NOC Operator Quick Commands[/]",
        border_style="yellow",
        box=ROUNDED
    )

    # 7. AI METRICS STATS PANEL
    metrics_table = Table.grid(padding=(0, 1))
    metrics_table.add_row("[bold]Total Requests (DB):[/]", str(db_metrics["total_requests"]))
    metrics_table.add_row("[bold]Requests Today:[/]", f"[green]{db_metrics['requests_today']}[/]")
    metrics_table.add_row("[bold]Historical Failures:[/]", f"[red]{db_metrics['failures']}[/]" if db_metrics['failures'] > 0 else "0")

    metrics_panel = Panel(
        metrics_table,
        title="[bold cyan]AI Request Metrics[/]",
        border_style="cyan",
        box=ROUNDED
    )

    # RENDER SCREEN
    # Create top header layout
    header_table = Table.grid(expand=True)
    header_table.add_column(justify="left")
    header_table.add_column(justify="right")
    header_table.add_row(header_content, status_text)
    
    console.print(Panel(header_table, border_style="cyan", box=HEAVY))
    
    # 2 columns for services & system
    cols = Columns([ollama_panel, sys_panel], equal=True, expand=True)
    console.print(cols)
 
    # Middle Row: Process Table and Metrics Panel
    middle_cols = Columns([proc_table, metrics_panel], equal=True, expand=True)
    console.print(middle_cols)

    # Bottom Row: Alerts and Quick Commands
    console.print(alerts_panel)
    console.print(commands_panel)

if __name__ == "__main__":
    main()
