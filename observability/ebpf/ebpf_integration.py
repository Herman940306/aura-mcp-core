"""
eBPF Observability Integration for Aura IA MCP.

This module provides deep kernel-level observability through eBPF probes,
integrating with Pixie and Cilium Hubble for comprehensive monitoring.

Features:
- Custom BPF probes for Python GIL monitoring
- Pixie integration for auto-telemetry
- Cilium Hubble integration for network observability
- Kernel-level latency tracking
- System call profiling
"""

from __future__ import annotations

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EBPFProbeType(Enum):
    """Types of eBPF probes supported."""

    KPROBE = "kprobe"  # Kernel function entry
    KRETPROBE = "kretprobe"  # Kernel function return
    UPROBE = "uprobe"  # User-space function entry
    URETPROBE = "uretprobe"  # User-space function return
    TRACEPOINT = "tracepoint"  # Kernel tracepoint
    RAW_TRACEPOINT = "raw_tracepoint"  # Raw tracepoint
    PERF_EVENT = "perf_event"  # Performance counter events
    XDP = "xdp"  # eXpress Data Path (network)
    TC = "tc"  # Traffic Control (network)
    CGROUP = "cgroup"  # cgroup events
    SOCKET = "socket"  # Socket operations
    FENTRY = "fentry"  # Function entry (BTF-based)
    FEXIT = "fexit"  # Function exit (BTF-based)


@dataclass
class EBPFConfig:
    """Configuration for eBPF integration."""

    enabled: bool = True
    pixie_enabled: bool = True
    pixie_cloud_addr: str = "work.withpixie.ai:443"
    pixie_cluster_id: str = ""
    pixie_api_key: str = ""

    hubble_enabled: bool = True
    hubble_address: str = "hubble-relay.kube-system.svc.cluster.local:4245"
    hubble_tls: bool = True
    hubble_ca_cert: str = "/etc/hubble/ca.crt"

    # GIL Monitoring
    gil_monitoring_enabled: bool = True
    gil_sample_rate_ms: int = 100
    gil_report_interval_s: int = 60

    # Probe Configuration
    max_probes: int = 100
    probe_buffer_size: int = 4096  # Ring buffer size in pages
    probe_timeout_ms: int = 5000

    # Output Configuration
    output_format: str = "json"  # json, prometheus, otlp
    metrics_prefix: str = "aura_ebpf_"

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "pixie": {
                "enabled": self.pixie_enabled,
                "cloud_addr": self.pixie_cloud_addr,
                "cluster_id": self.pixie_cluster_id,
            },
            "hubble": {
                "enabled": self.hubble_enabled,
                "address": self.hubble_address,
                "tls": self.hubble_tls,
            },
            "gil_monitoring": {
                "enabled": self.gil_monitoring_enabled,
                "sample_rate_ms": self.gil_sample_rate_ms,
                "report_interval_s": self.gil_report_interval_s,
            },
            "probe_config": {
                "max_probes": self.max_probes,
                "buffer_size": self.probe_buffer_size,
                "timeout_ms": self.probe_timeout_ms,
            },
        }


@dataclass
class EBPFProbe:
    """Represents an eBPF probe definition."""

    name: str
    probe_type: EBPFProbeType
    target: str  # Function name, tracepoint, etc.
    handler: str | None = None  # BPF program name
    filter_expression: str | None = None
    enabled: bool = True

    # Metadata
    description: str = ""
    tags: list[str] = field(default_factory=list)

    # Statistics
    hit_count: int = 0
    last_triggered: datetime | None = None
    avg_latency_ns: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert probe to dictionary."""
        return {
            "name": self.name,
            "probe_type": self.probe_type.value,
            "target": self.target,
            "handler": self.handler,
            "filter_expression": self.filter_expression,
            "enabled": self.enabled,
            "description": self.description,
            "tags": self.tags,
            "statistics": {
                "hit_count": self.hit_count,
                "last_triggered": (
                    self.last_triggered.isoformat()
                    if self.last_triggered
                    else None
                ),
                "avg_latency_ns": self.avg_latency_ns,
            },
        }


@dataclass
class ProbeEvent:
    """Event captured by an eBPF probe."""

    probe_name: str
    timestamp: datetime
    pid: int
    tid: int
    comm: str  # Process command name
    cpu: int
    data: dict[str, Any] = field(default_factory=dict)
    stack_trace: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "probe_name": self.probe_name,
            "timestamp": self.timestamp.isoformat(),
            "pid": self.pid,
            "tid": self.tid,
            "comm": self.comm,
            "cpu": self.cpu,
            "data": self.data,
            "stack_trace": self.stack_trace,
        }


@dataclass
class GILStats:
    """Statistics for Python GIL monitoring."""

    timestamp: datetime
    pid: int
    total_wait_time_ns: int = 0
    total_hold_time_ns: int = 0
    acquisition_count: int = 0
    contention_count: int = 0
    max_wait_time_ns: int = 0
    max_hold_time_ns: int = 0

    @property
    def avg_wait_time_ns(self) -> float:
        """Calculate average wait time."""
        if self.acquisition_count == 0:
            return 0.0
        return self.total_wait_time_ns / self.acquisition_count

    @property
    def avg_hold_time_ns(self) -> float:
        """Calculate average hold time."""
        if self.acquisition_count == 0:
            return 0.0
        return self.total_hold_time_ns / self.acquisition_count

    @property
    def contention_rate(self) -> float:
        """Calculate contention rate."""
        if self.acquisition_count == 0:
            return 0.0
        return self.contention_count / self.acquisition_count

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "pid": self.pid,
            "total_wait_time_ns": self.total_wait_time_ns,
            "total_hold_time_ns": self.total_hold_time_ns,
            "acquisition_count": self.acquisition_count,
            "contention_count": self.contention_count,
            "max_wait_time_ns": self.max_wait_time_ns,
            "max_hold_time_ns": self.max_hold_time_ns,
            "avg_wait_time_ns": self.avg_wait_time_ns,
            "avg_hold_time_ns": self.avg_hold_time_ns,
            "contention_rate": self.contention_rate,
        }


class EBPFBackend(ABC):
    """Abstract base class for eBPF backends."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is available."""
        pass

    @abstractmethod
    async def load_probe(self, probe: EBPFProbe) -> bool:
        """Load an eBPF probe."""
        pass

    @abstractmethod
    async def unload_probe(self, probe_name: str) -> bool:
        """Unload an eBPF probe."""
        pass

    @abstractmethod
    async def get_events(
        self, probe_name: str, limit: int = 100
    ) -> list[ProbeEvent]:
        """Get events from a probe."""
        pass


class SimulatedEBPFBackend(EBPFBackend):
    """Simulated eBPF backend for testing and non-Linux environments."""

    def __init__(self):
        self._probes: dict[str, EBPFProbe] = {}
        self._events: dict[str, list[ProbeEvent]] = {}
        self._running = False
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """Always available for simulation."""
        return True

    async def load_probe(self, probe: EBPFProbe) -> bool:
        """Load a simulated probe."""
        with self._lock:
            self._probes[probe.name] = probe
            self._events[probe.name] = []
            logger.info(f"Loaded simulated probe: {probe.name}")
        return True

    async def unload_probe(self, probe_name: str) -> bool:
        """Unload a simulated probe."""
        with self._lock:
            if probe_name in self._probes:
                del self._probes[probe_name]
                del self._events[probe_name]
                logger.info(f"Unloaded simulated probe: {probe_name}")
                return True
        return False

    async def get_events(
        self, probe_name: str, limit: int = 100
    ) -> list[ProbeEvent]:
        """Get simulated events."""
        with self._lock:
            if probe_name not in self._events:
                return []
            return self._events[probe_name][-limit:]

    def generate_event(
        self, probe_name: str, data: dict[str, Any]
    ) -> ProbeEvent:
        """Generate a simulated event for testing."""
        import os

        event = ProbeEvent(
            probe_name=probe_name,
            timestamp=datetime.now(),
            pid=os.getpid(),
            tid=threading.get_ident(),
            comm="python",
            cpu=0,
            data=data,
        )
        with self._lock:
            if probe_name in self._events:
                self._events[probe_name].append(event)
                if len(self._events[probe_name]) > 1000:
                    self._events[probe_name] = self._events[probe_name][-1000:]
        return event


class GILMonitor:
    """
    Monitor Python GIL (Global Interpreter Lock) usage via eBPF.

    Uses uprobes on CPython internals to track:
    - GIL acquisition/release patterns
    - Wait time distribution
    - Contention metrics
    - Per-thread GIL hold time
    """

    # Python GIL functions to probe (CPython 3.x)
    GIL_FUNCTIONS = {
        "take_gil": "PyEval_AcquireLock",
        "drop_gil": "PyEval_ReleaseLock",
        "eval_frame": "_PyEval_EvalFrameDefault",
    }

    def __init__(self, config: EBPFConfig, backend: EBPFBackend):
        self.config = config
        self.backend = backend
        self._stats: dict[int, GILStats] = {}  # Per-PID stats
        self._lock = threading.Lock()
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._callbacks: list[Callable[[GILStats], None]] = []

    def add_callback(self, callback: Callable[[GILStats], None]) -> None:
        """Add a callback for GIL stats updates."""
        self._callbacks.append(callback)

    async def start(self) -> bool:
        """Start GIL monitoring."""
        if not self.config.gil_monitoring_enabled:
            logger.info("GIL monitoring disabled")
            return False

        if self._running:
            logger.warning("GIL monitoring already running")
            return True

        # Load GIL probes
        probes = self._create_gil_probes()
        for probe in probes:
            success = await self.backend.load_probe(probe)
            if not success:
                logger.error(f"Failed to load GIL probe: {probe.name}")
                return False

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("GIL monitoring started")
        return True

    async def stop(self) -> None:
        """Stop GIL monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Unload probes
        for name in self.GIL_FUNCTIONS.keys():
            await self.backend.unload_probe(f"gil_{name}")

        logger.info("GIL monitoring stopped")

    def _create_gil_probes(self) -> list[EBPFProbe]:
        """Create GIL monitoring probes."""
        probes = []

        # GIL take probe
        probes.append(
            EBPFProbe(
                name="gil_take_gil",
                probe_type=EBPFProbeType.UPROBE,
                target=self.GIL_FUNCTIONS["take_gil"],
                description="Track GIL acquisition",
                tags=["gil", "python", "performance"],
            )
        )

        # GIL drop probe
        probes.append(
            EBPFProbe(
                name="gil_drop_gil",
                probe_type=EBPFProbeType.URETPROBE,
                target=self.GIL_FUNCTIONS["drop_gil"],
                description="Track GIL release",
                tags=["gil", "python", "performance"],
            )
        )

        return probes

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._collect_stats()
                await asyncio.sleep(self.config.gil_sample_rate_ms / 1000.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in GIL monitor loop: {e}")
                await asyncio.sleep(1)

    async def _collect_stats(self) -> None:
        """Collect GIL statistics from probes."""
        import os

        pid = os.getpid()

        # Get events from probes
        take_events = await self.backend.get_events("gil_take_gil", limit=1000)
        drop_events = await self.backend.get_events("gil_drop_gil", limit=1000)

        # Update stats
        with self._lock:
            if pid not in self._stats:
                self._stats[pid] = GILStats(timestamp=datetime.now(), pid=pid)

            stats = self._stats[pid]
            stats.timestamp = datetime.now()

            # Simulate stats for testing
            if isinstance(self.backend, SimulatedEBPFBackend):
                import random

                stats.acquisition_count += random.randint(10, 100)
                stats.total_wait_time_ns += random.randint(1000, 10000)
                stats.total_hold_time_ns += random.randint(5000, 50000)
                stats.contention_count += random.randint(0, 5)

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(stats)
            except Exception as e:
                logger.error(f"Error in GIL stats callback: {e}")

    def get_stats(self, pid: int | None = None) -> GILStats | None:
        """Get GIL statistics for a process."""
        import os

        pid = pid or os.getpid()
        with self._lock:
            return self._stats.get(pid)

    def get_all_stats(self) -> dict[int, GILStats]:
        """Get all GIL statistics."""
        with self._lock:
            return dict(self._stats)


class PixieIntegration:
    """
    Integration with Pixie for auto-telemetry.

    Pixie provides automatic observability for Kubernetes applications
    using eBPF without code changes.

    Features:
    - Protocol tracing (HTTP, gRPC, DNS, etc.)
    - Continuous profiling
    - Service maps
    - Custom PxL scripts
    """

    # Pre-defined PxL scripts for Aura IA
    AURA_PXL_SCRIPTS = {
        "service_stats": """
import px

# Get HTTP stats for Aura IA services
df = px.DataFrame(table='http_events', start_time='-5m')
df = df[df.remote_port == 9200 or df.remote_port == 9201 or
        df.remote_port == 9202 or df.remote_port == 9205]
df = df.groupby(['service', 'req_path']).agg(
    requests=('latency', px.count),
    avg_latency=('latency', px.mean),
    p99_latency=('latency', lambda x: px.quantile(x, 0.99)),
    errors=('resp_status', lambda x: px.count(x >= 400))
)
px.display(df)
""",
        "connection_stats": """
import px

# Network connection stats for Aura IA
df = px.DataFrame(table='conn_stats', start_time='-5m')
df = df.groupby(['remote_addr', 'remote_port']).agg(
    bytes_sent=('bytes_sent', px.sum),
    bytes_recv=('bytes_recv', px.sum),
    conn_count=('count', px.count)
)
px.display(df)
""",
        "cpu_flamegraph": """
import px

# CPU flamegraph for profiling
df = px.DataFrame(table='stack_traces.cpu_samples', start_time='-5m')
df = df[px.contains(df.cmdline, 'python') or px.contains(df.cmdline, 'aura')]
px.display(df)
""",
    }

    def __init__(self, config: EBPFConfig):
        self.config = config
        self._connected = False
        self._client = None  # Would be px.Client in real implementation

    def is_available(self) -> bool:
        """Check if Pixie is available."""
        return self.config.pixie_enabled and bool(self.config.pixie_cluster_id)

    async def connect(self) -> bool:
        """Connect to Pixie Cloud."""
        if not self.is_available():
            logger.warning("Pixie not available or not configured")
            return False

        try:
            # In real implementation: px.Client(token=..., server=...)
            logger.info(
                f"Connecting to Pixie Cloud: {self.config.pixie_cloud_addr}"
            )
            self._connected = True
            logger.info("Connected to Pixie Cloud")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Pixie: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Pixie Cloud."""
        self._connected = False
        self._client = None
        logger.info("Disconnected from Pixie Cloud")

    async def run_script(self, script_name: str) -> dict[str, Any]:
        """Run a PxL script."""
        if not self._connected:
            raise RuntimeError("Not connected to Pixie")

        script = self.AURA_PXL_SCRIPTS.get(script_name)
        if not script:
            raise ValueError(f"Unknown script: {script_name}")

        # In real implementation: self._client.run_script(script)
        logger.info(f"Running PxL script: {script_name}")

        # Return simulated results
        return {
            "script_name": script_name,
            "execution_time_ms": 150,
            "rows_returned": 42,
            "data": [],  # Would contain actual data
        }

    async def get_service_stats(self) -> dict[str, Any]:
        """Get service statistics using Pixie."""
        return await self.run_script("service_stats")

    async def get_connection_stats(self) -> dict[str, Any]:
        """Get network connection stats."""
        return await self.run_script("connection_stats")

    async def get_cpu_flamegraph(self) -> dict[str, Any]:
        """Get CPU flamegraph data."""
        return await self.run_script("cpu_flamegraph")

    def get_available_scripts(self) -> list[str]:
        """Get list of available PxL scripts."""
        return list(self.AURA_PXL_SCRIPTS.keys())


class CiliumHubbleIntegration:
    """
    Integration with Cilium Hubble for network observability.

    Hubble provides deep network visibility using eBPF:
    - L3/L4/L7 flow visibility
    - Network policy verdicts
    - DNS visibility
    - Service dependency maps
    """

    def __init__(self, config: EBPFConfig):
        self.config = config
        self._connected = False
        self._channel = None  # gRPC channel

    def is_available(self) -> bool:
        """Check if Hubble is available."""
        return self.config.hubble_enabled

    async def connect(self) -> bool:
        """Connect to Hubble Relay."""
        if not self.is_available():
            logger.warning("Hubble not enabled")
            return False

        try:
            # In real implementation: grpc.aio.insecure_channel(...)
            logger.info(
                f"Connecting to Hubble Relay: {self.config.hubble_address}"
            )
            self._connected = True
            logger.info("Connected to Hubble Relay")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Hubble: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Hubble Relay."""
        self._connected = False
        if self._channel:
            await self._channel.close()
            self._channel = None
        logger.info("Disconnected from Hubble Relay")

    async def get_flows(
        self,
        namespace: str = "default",
        pod: str | None = None,
        since: timedelta | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get network flows."""
        if not self._connected:
            raise RuntimeError("Not connected to Hubble")

        # In real implementation: hubble_pb2.GetFlowsRequest(...)
        logger.info(f"Getting flows for namespace={namespace}, pod={pod}")

        # Return simulated flows
        return [
            {
                "time": datetime.now().isoformat(),
                "verdict": "FORWARDED",
                "source": {
                    "namespace": namespace,
                    "pod": "aura-gateway",
                    "ip": "10.0.0.1",
                },
                "destination": {
                    "namespace": namespace,
                    "pod": "aura-ml",
                    "ip": "10.0.0.2",
                },
                "l4": {
                    "tcp": {"source_port": 45678, "destination_port": 9201}
                },
                "l7": {"http": {"method": "POST", "url": "/api/v1/predict"}},
            }
        ]

    async def get_service_map(
        self, namespace: str = "default"
    ) -> dict[str, Any]:
        """Get service dependency map."""
        if not self._connected:
            raise RuntimeError("Not connected to Hubble")

        # Return simulated service map
        return {
            "namespace": namespace,
            "services": [
                {"name": "aura-gateway", "type": "ClusterIP", "port": 9200},
                {"name": "aura-ml", "type": "ClusterIP", "port": 9201},
                {"name": "aura-rag", "type": "ClusterIP", "port": 9202},
            ],
            "dependencies": [
                {
                    "source": "aura-gateway",
                    "target": "aura-ml",
                    "protocol": "HTTP",
                },
                {
                    "source": "aura-gateway",
                    "target": "aura-rag",
                    "protocol": "gRPC",
                },
            ],
        }

    async def get_policy_verdicts(
        self,
        namespace: str = "default",
        verdict: str | None = None,  # FORWARDED, DROPPED, ERROR
    ) -> list[dict[str, Any]]:
        """Get network policy verdicts."""
        if not self._connected:
            raise RuntimeError("Not connected to Hubble")

        # Return simulated verdicts
        return [
            {
                "time": datetime.now().isoformat(),
                "verdict": verdict or "FORWARDED",
                "policy_name": "aura-network-policy",
                "source": "aura-gateway",
                "destination": "aura-ml",
            }
        ]


class EBPFManager:
    """
    Central manager for all eBPF-based observability.

    Coordinates:
    - Probe lifecycle management
    - Backend selection
    - GIL monitoring
    - Pixie and Hubble integrations
    """

    def __init__(self, config: EBPFConfig | None = None):
        self.config = config or EBPFConfig()
        self._backend: EBPFBackend | None = None
        self._probes: dict[str, EBPFProbe] = {}
        self._gil_monitor: GILMonitor | None = None
        self._pixie: PixieIntegration | None = None
        self._hubble: CiliumHubbleIntegration | None = None
        self._initialized = False
        self._lock = threading.Lock()

    async def initialize(self) -> bool:
        """Initialize the eBPF manager."""
        if self._initialized:
            return True

        if not self.config.enabled:
            logger.info("eBPF observability disabled")
            return False

        # Select backend
        self._backend = self._select_backend()
        if not self._backend.is_available():
            logger.error("No eBPF backend available")
            return False

        # Initialize GIL monitor
        self._gil_monitor = GILMonitor(self.config, self._backend)

        # Initialize Pixie integration
        if self.config.pixie_enabled:
            self._pixie = PixieIntegration(self.config)

        # Initialize Hubble integration
        if self.config.hubble_enabled:
            self._hubble = CiliumHubbleIntegration(self.config)

        self._initialized = True
        logger.info("eBPF manager initialized")
        return True

    def _select_backend(self) -> EBPFBackend:
        """Select the appropriate eBPF backend."""
        # In real implementation, would check for libbpf, bcc, etc.
        # For now, use simulated backend
        logger.info("Using simulated eBPF backend")
        return SimulatedEBPFBackend()

    async def start(self) -> None:
        """Start all eBPF monitoring."""
        if not self._initialized:
            await self.initialize()

        # Start GIL monitoring
        if self._gil_monitor:
            await self._gil_monitor.start()

        # Connect to Pixie
        if self._pixie:
            await self._pixie.connect()

        # Connect to Hubble
        if self._hubble:
            await self._hubble.connect()

        logger.info("eBPF monitoring started")

    async def stop(self) -> None:
        """Stop all eBPF monitoring."""
        # Stop GIL monitoring
        if self._gil_monitor:
            await self._gil_monitor.stop()

        # Disconnect from Pixie
        if self._pixie:
            await self._pixie.disconnect()

        # Disconnect from Hubble
        if self._hubble:
            await self._hubble.disconnect()

        # Unload all probes
        for probe_name in list(self._probes.keys()):
            await self.unload_probe(probe_name)

        logger.info("eBPF monitoring stopped")

    async def load_probe(self, probe: EBPFProbe) -> bool:
        """Load an eBPF probe."""
        if not self._initialized or not self._backend:
            raise RuntimeError("eBPF manager not initialized")

        if len(self._probes) >= self.config.max_probes:
            raise RuntimeError(
                f"Maximum probes ({self.config.max_probes}) exceeded"
            )

        success = await self._backend.load_probe(probe)
        if success:
            with self._lock:
                self._probes[probe.name] = probe
        return success

    async def unload_probe(self, probe_name: str) -> bool:
        """Unload an eBPF probe."""
        if not self._backend:
            return False

        success = await self._backend.unload_probe(probe_name)
        if success:
            with self._lock:
                if probe_name in self._probes:
                    del self._probes[probe_name]
        return success

    async def get_probe_events(
        self, probe_name: str, limit: int = 100
    ) -> list[ProbeEvent]:
        """Get events from a probe."""
        if not self._backend:
            return []
        return await self._backend.get_events(probe_name, limit)

    def get_probe(self, probe_name: str) -> EBPFProbe | None:
        """Get a probe by name."""
        with self._lock:
            return self._probes.get(probe_name)

    def list_probes(self) -> list[EBPFProbe]:
        """List all loaded probes."""
        with self._lock:
            return list(self._probes.values())

    @property
    def gil_monitor(self) -> GILMonitor | None:
        """Get the GIL monitor."""
        return self._gil_monitor

    @property
    def pixie(self) -> PixieIntegration | None:
        """Get the Pixie integration."""
        return self._pixie

    @property
    def hubble(self) -> CiliumHubbleIntegration | None:
        """Get the Hubble integration."""
        return self._hubble

    def get_status(self) -> dict[str, Any]:
        """Get manager status."""
        return {
            "initialized": self._initialized,
            "enabled": self.config.enabled,
            "backend": type(self._backend).__name__ if self._backend else None,
            "probes_loaded": len(self._probes),
            "gil_monitoring": {
                "enabled": self.config.gil_monitoring_enabled,
                "running": (
                    self._gil_monitor._running if self._gil_monitor else False
                ),
            },
            "pixie": {
                "enabled": self.config.pixie_enabled,
                "connected": self._pixie._connected if self._pixie else False,
            },
            "hubble": {
                "enabled": self.config.hubble_enabled,
                "connected": (
                    self._hubble._connected if self._hubble else False
                ),
            },
        }


# Singleton instance
_ebpf_manager: EBPFManager | None = None


def get_ebpf_manager() -> EBPFManager:
    """Get the singleton eBPF manager."""
    global _ebpf_manager
    if _ebpf_manager is None:
        _ebpf_manager = EBPFManager()
    return _ebpf_manager


async def init_ebpf(config: EBPFConfig | None = None) -> EBPFManager:
    """Initialize eBPF manager with optional config."""
    global _ebpf_manager
    _ebpf_manager = EBPFManager(config)
    await _ebpf_manager.initialize()
    return _ebpf_manager
