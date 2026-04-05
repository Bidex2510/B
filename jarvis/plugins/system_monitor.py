"""System monitoring plugin - CPU, memory, disk, and network stats."""

import re
import platform
import os
import shutil
from datetime import datetime

from jarvis.core.plugin_base import PluginBase


class SystemMonitorPlugin(PluginBase):

    name = "system_monitor"
    description = "Monitor system resources (CPU, memory, disk, network, uptime)"

    TRIGGERS = [
        r"\b(system|status|cpu|memory|ram|disk|storage|network|uptime|health|diagnostics)\b",
        r"\b(how.*(computer|system|machine).*(doing|running|performing))\b",
    ]

    def can_handle(self, text):
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text):
        lower = text.lower()

        if "cpu" in lower:
            return self._cpu_info()
        elif "memory" in lower or "ram" in lower:
            return self._memory_info()
        elif "disk" in lower or "storage" in lower:
            return self._disk_info()
        elif "uptime" in lower:
            return self._uptime_info()
        else:
            return self._full_status()

    def _cpu_info(self):
        cpu_count = os.cpu_count() or "Unknown"
        arch = platform.machine()
        processor = platform.processor() or "Unknown"
        return (
            f"CPU Report:\n"
            f"  Processor : {processor}\n"
            f"  Cores     : {cpu_count}\n"
            f"  Arch      : {arch}"
        )

    def _memory_info(self):
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            mem = {}
            for line in lines[:5]:
                key, val = line.split(":")
                mem[key.strip()] = val.strip()
            total = mem.get("MemTotal", "Unknown")
            free = mem.get("MemAvailable", mem.get("MemFree", "Unknown"))
            return f"Memory Report:\n  Total     : {total}\n  Available : {free}"
        except FileNotFoundError:
            return "Memory info is not available on this platform."

    def _disk_info(self):
        total, used, free = shutil.disk_usage("/")
        gb = 1024 ** 3
        return (
            f"Disk Report (/):\n"
            f"  Total : {total / gb:.1f} GB\n"
            f"  Used  : {used / gb:.1f} GB\n"
            f"  Free  : {free / gb:.1f} GB\n"
            f"  Usage : {used / total * 100:.1f}%"
        )

    def _uptime_info(self):
        try:
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.read().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"System uptime: {hours} hours, {minutes} minutes."
        except FileNotFoundError:
            return "Uptime info is not available on this platform."

    def _full_status(self):
        parts = [
            f"=== System Status Report ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===",
            f"  OS       : {platform.system()} {platform.release()}",
            f"  Hostname : {platform.node()}",
            f"  Python   : {platform.python_version()}",
            "",
            self._cpu_info(),
            "",
            self._memory_info(),
            "",
            self._disk_info(),
        ]
        return "\n".join(parts)
