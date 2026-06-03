import os
import time
import psutil

def format_bytes(bytes_num: float) -> str:
    """Formats bytes into human-readable strings (e.g. 1.3TB, 45.2GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if bytes_num < 1024.0:
            # If it's B, return integer, else 1 decimal place
            if unit == 'B':
                return f"{int(bytes_num)} {unit}"
            # For larger units like TB/GB, format to 1 decimal place (e.g. 1.3 TB)
            return f"{bytes_num:.1f} {unit}"
            # Or without space: return f"{bytes_num:.1f}{unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} EB"

def format_uptime(seconds: float) -> str:
    """Formats seconds into human-readable uptime (e.g. 37 Days)."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        if days == 1:
            return f"1 Day" if hours == 0 else f"1d {hours}h"
        return f"{days} Days" if hours == 0 else f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

class SystemService:
    def __init__(self):
        pass

    def get_system_stats(self) -> dict:
        """
        Retrieves current system statistics.
        """
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()

        # Virtual Memory (RAM)
        virtual_mem = psutil.virtual_memory()
        ram_total = virtual_mem.total
        ram_used = virtual_mem.used
        ram_percent = virtual_mem.percent

        # Swap Memory
        swap_mem = psutil.swap_memory()
        swap_total = swap_mem.total
        swap_used = swap_mem.used
        swap_percent = swap_mem.percent

        # Disk (Root partition)
        disk_usage = psutil.disk_usage('/')
        disk_total = disk_usage.total
        disk_used = disk_usage.used
        disk_free = disk_usage.free
        disk_percent = disk_usage.percent

        # Load Average (1m, 5m, 15m)
        try:
            load_1m, load_5m, load_15m = os.getloadavg()
        except (AttributeError, OSError):
            load_1m, load_5m, load_15m = 0.0, 0.0, 0.0

        # Uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time

        # Top 5 memory-consuming processes
        top_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_percent']):
            try:
                info = proc.info
                if info['memory_info']:
                    top_processes.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "mem_percent": info['memory_percent'] or 0.0,
                        "mem_bytes": info['memory_info'].rss
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Sort descending by RSS bytes
        top_processes.sort(key=lambda x: x['mem_bytes'], reverse=True)
        top_processes = top_processes[:5]

        return {
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "ram_total": ram_total,
            "ram_used": ram_used,
            "ram_percent": ram_percent,
            "swap_total": swap_total,
            "swap_used": swap_used,
            "swap_percent": swap_percent,
            "disk_total": disk_total,
            "disk_used": disk_used,
            "disk_free": disk_free,
            "disk_percent": disk_percent,
            "load_1m": load_1m,
            "load_5m": load_5m,
            "load_15m": load_15m,
            "uptime_seconds": uptime_seconds,
            "uptime_str": format_uptime(uptime_seconds),
            "top_processes": top_processes
        }
