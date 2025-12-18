#!/usr/bin/env python3
"""
System Monitoring Service for Aura IA Dashboard

Provides real-time system metrics including:
- CPU usage and frequency
- RAM usage and availability
- Disk usage and I/O
- Network statistics
- GPU monitoring (when available)
- Temperature sensors (when available)

Project Creator: Herman Swanepoel
Document Version: 1.0
Last Updated: December 13, 2025
"""

import logging
import platform
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aura_ia.system_monitor")

# Try to import psutil for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - system monitoring disabled")

# Try to import GPUtil for GPU monitoring
try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False
    logger.info("GPUtil not available - GPU monitoring disabled")


@dataclass
class SystemMonitorConfig:
    """Configuration for System Monitor."""
    enable_gpu_monitoring: bool = True
    enable_temperature_monitoring: bool = True
    disk_path: str = "/"
    network_interface: Optional[str] = None


class SystemMonitor:
    """
    System monitoring service for real-time metrics collection.

    Collects:
    - CPU metrics (usage, frequency, core count)
    - Memory metrics (total, available, used, percent)
    - Disk metrics (total, used, free, percent)
    - Network metrics (bytes sent/received, packets)
    - GPU metrics (utilization, memory, temperature) - optional
    - Temperature metrics (CPU, system temps) - optional
    """

    def __init__(self, config: Optional[SystemMonitorConfig] = None):
        self.config = config or SystemMonitorConfig()
        self._gpu_available = self._check_gpu_availability()
        self._temp_available = self._check_temperature_availability()
        self._last_network_io = None
        self._last_network_time = None
        self._last_disk_io = None
        self._last_disk_time = None

        logger.info(
            "SystemMonitor initialized: psutil=%s, gpu=%s, temp=%s",
            PSUTIL_AVAILABLE,
            self._gpu_available,
            self._temp_available
        )

    def _check_gpu_availability(self) -> bool:
        """Check if GPU monitoring is available."""
        if not self.config.enable_gpu_monitoring:
            return False
        if not GPUTIL_AVAILABLE:
            return False
        try:
            gpus = GPUtil.getGPUs()
            return len(gpus) > 0
        except Exception:
            return False

    def _check_temperature_availability(self) -> bool:
        """Check if temperature monitoring is available."""
        if not self.config.enable_temperature_monitoring:
            return False
        if not PSUTIL_AVAILABLE:
            return False
        try:
            temps = psutil.sensors_temperatures()
            return bool(temps)
        except (AttributeError, NotImplementedError):
            # sensors_temperatures not available on all platforms
            return False
        except Exception:
            return False

    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Collect all system metrics.

        Returns comprehensive system metrics dictionary.
        """
        if not PSUTIL_AVAILABLE:
            return {
                "error": "psutil not available",
                "timestamp": datetime.now(UTC).isoformat()
            }

        metrics: Dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor()
            }
        }

        # CPU metrics
        metrics["cpu"] = self._get_cpu_metrics()

        # Memory metrics
        metrics["memory"] = self._get_memory_metrics()

        # Disk metrics
        metrics["disk"] = self._get_disk_metrics()

        # Network metrics
        metrics["network"] = self._get_network_metrics()

        # GPU metrics (if available)
        if self._gpu_available:
            metrics["gpu"] = self._get_gpu_metrics()

        # Temperature metrics (if available)
        if self._temp_available:
            metrics["temperature"] = self._get_temperature_metrics()

        return metrics

    def _get_cpu_metrics(self) -> Dict[str, Any]:
        """Get CPU metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_freq = psutil.cpu_freq()
            cpu_count = psutil.cpu_count()
            cpu_count_logical = psutil.cpu_count(logical=True)

            # Per-CPU usage
            per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

            return {
                "usage_percent": cpu_percent,
                "count_physical": cpu_count,
                "count_logical": cpu_count_logical,
                "frequency": {
                    "current": cpu_freq.current if cpu_freq else None,
                    "min": cpu_freq.min if cpu_freq else None,
                    "max": cpu_freq.max if cpu_freq else None
                } if cpu_freq else None,
                "per_cpu_percent": per_cpu,
                "load_average": list(psutil.getloadavg())
                if hasattr(psutil, "getloadavg") else None
            }
        except Exception as e:
            logger.warning("Error getting CPU metrics: %s", e)
            return {"error": str(e)}

    def _get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory metrics."""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "total": mem.total,
                "available": mem.available,
                "used": mem.used,
                "percent": mem.percent,
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "swap": {
                    "total": swap.total,
                    "used": swap.used,
                    "free": swap.free,
                    "percent": swap.percent
                }
            }
        except Exception as e:
            logger.warning("Error getting memory metrics: %s", e)
            return {"error": str(e)}

    def _get_disk_metrics(self) -> Dict[str, Any]:
        """Get disk metrics."""
        try:
            disk_path = self.config.disk_path
            # Handle Windows paths
            if platform.system() == "Windows":
                disk_path = "C:\\"

            disk = psutil.disk_usage(disk_path)

            # Disk I/O
            disk_io = psutil.disk_io_counters()
            io_stats = None
            if disk_io:
                current_time = time.time()
                if self._last_disk_io and self._last_disk_time:
                    time_delta = current_time - self._last_disk_time
                    if time_delta > 0:
                        read_speed = (
                            disk_io.read_bytes - self._last_disk_io.read_bytes
                        ) / time_delta
                        write_speed = (
                            disk_io.write_bytes - self._last_disk_io.write_bytes
                        ) / time_delta
                        io_stats = {
                            "read_speed_mb": round(read_speed / (1024**2), 2),
                            "write_speed_mb": round(write_speed / (1024**2), 2)
                        }
                self._last_disk_io = disk_io
                self._last_disk_time = current_time

            return {
                "path": disk_path,
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "io": io_stats
            }
        except Exception as e:
            logger.warning("Error getting disk metrics: %s", e)
            return {"error": str(e)}

    def _get_network_metrics(self) -> Dict[str, Any]:
        """Get network metrics."""
        try:
            net_io = psutil.net_io_counters()

            # Calculate network speed
            speed_stats = None
            current_time = time.time()
            if self._last_network_io and self._last_network_time:
                time_delta = current_time - self._last_network_time
                if time_delta > 0:
                    bytes_sent_speed = (
                        net_io.bytes_sent - self._last_network_io.bytes_sent
                    ) / time_delta
                    bytes_recv_speed = (
                        net_io.bytes_recv - self._last_network_io.bytes_recv
                    ) / time_delta
                    speed_stats = {
                        "upload_mb": round(bytes_sent_speed / (1024**2), 2),
                        "download_mb": round(bytes_recv_speed / (1024**2), 2)
                    }

            self._last_network_io = net_io
            self._last_network_time = current_time

            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errors_in": net_io.errin,
                "errors_out": net_io.errout,
                "speed": speed_stats
            }
        except Exception as e:
            logger.warning("Error getting network metrics: %s", e)
            return {"error": str(e)}

    def _get_gpu_metrics(self) -> List[Dict[str, Any]]:
        """Get GPU metrics using GPUtil."""
        if not GPUTIL_AVAILABLE:
            return []

        try:
            gpus = GPUtil.getGPUs()
            return [
                {
                    "id": gpu.id,
                    "name": gpu.name,
                    "load_percent": round(gpu.load * 100, 1),
                    "memory_used_mb": round(gpu.memoryUsed, 1),
                    "memory_total_mb": round(gpu.memoryTotal, 1),
                    "memory_percent": round(
                        (gpu.memoryUsed / gpu.memoryTotal) * 100, 1
                    ) if gpu.memoryTotal > 0 else 0,
                    "temperature": gpu.temperature,
                    "uuid": gpu.uuid
                }
                for gpu in gpus
            ]
        except Exception as e:
            logger.warning("Error getting GPU metrics: %s", e)
            return []

    def _get_temperature_metrics(self) -> Dict[str, Any]:
        """Get temperature sensor metrics."""
        if not PSUTIL_AVAILABLE:
            return {}

        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return {}

            result = {}
            for name, entries in temps.items():
                result[name] = [
                    {
                        "label": entry.label or f"sensor_{i}",
                        "current": entry.current,
                        "high": entry.high,
                        "critical": entry.critical
                    }
                    for i, entry in enumerate(entries)
                ]

            return result
        except (AttributeError, NotImplementedError):
            return {}
        except Exception as e:
            logger.warning("Error getting temperature metrics: %s", e)
            return {}

    def get_quick_status(self) -> Dict[str, Any]:
        """Get a quick status summary without detailed metrics."""
        if not PSUTIL_AVAILABLE:
            return {"status": "unavailable"}

        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(
                "C:\\" if platform.system() == "Windows" else "/"
            )

            status = {
                "status": "ok",
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "disk_percent": disk.percent,
                "timestamp": datetime.now(UTC).isoformat()
            }

            # Add GPU if available
            if self._gpu_available:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        status["gpu_percent"] = round(gpus[0].load * 100, 1)
                        status["gpu_temp"] = gpus[0].temperature
                except Exception:
                    pass

            return status
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global system monitor instance
_system_monitor: Optional[SystemMonitor] = None


def get_system_monitor() -> SystemMonitor:
    """Get or create the global system monitor instance."""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor
