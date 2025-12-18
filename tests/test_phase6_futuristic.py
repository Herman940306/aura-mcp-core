"""
Test Suite for Phase 6: Strategic & Futuristic Components.

Tests:
- eBPF Observability (Pixie, Hubble, GIL Monitoring)
- Green Compute (Carbon-Aware Scheduling)
- WASM Sandbox (Plugin Security)
- Confidential Computing (Enclaves)

Run with: pytest tests/test_phase6_futuristic.py -v
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from observability.ebpf import EBPFManager

# ============================================================================
# Fixtures to reset singletons between tests
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests to avoid cross-test contamination."""
    # Reset before test
    import aura_ia_mcp.core.futuristic.confidential_compute as cc
    import aura_ia_mcp.core.futuristic.green_compute as gc
    import aura_ia_mcp.core.futuristic.wasm_sandbox as ws
    import observability.ebpf.ebpf_integration as ebpf

    gc._carbon_scheduler = None
    ws._wasm_sandbox = None
    cc._enclave_manager = None
    ebpf._ebpf_manager = None

    yield  # Run the test

    # Reset after test
    gc._carbon_scheduler = None
    ws._wasm_sandbox = None
    cc._enclave_manager = None
    ebpf._ebpf_manager = None


# ============================================================================
# eBPF Observability Tests
# ============================================================================


class TestEBPFIntegration:
    """Test eBPF observability components."""

    def test_ebpf_config_creation(self):
        """Test EBPFConfig dataclass."""
        from observability.ebpf import EBPFConfig

        config = EBPFConfig(
            enabled=True,
            pixie_enabled=True,
            hubble_enabled=True,
            gil_monitoring_enabled=True,
        )

        assert config.enabled is True
        assert config.pixie_enabled is True
        assert config.hubble_enabled is True
        assert config.gil_monitoring_enabled is True
        assert config.gil_sample_rate_ms == 100

    def test_ebpf_config_to_dict(self):
        """Test EBPFConfig serialization."""
        from observability.ebpf import EBPFConfig

        config = EBPFConfig(
            pixie_cluster_id="test-cluster",
            hubble_address="hubble:4245",
        )

        data = config.to_dict()
        assert "pixie" in data
        assert data["pixie"]["cluster_id"] == "test-cluster"
        assert data["hubble"]["address"] == "hubble:4245"

    def test_ebpf_probe_types(self):
        """Test EBPFProbeType enum."""
        from observability.ebpf import EBPFProbeType

        assert EBPFProbeType.KPROBE.value == "kprobe"
        assert EBPFProbeType.UPROBE.value == "uprobe"
        assert EBPFProbeType.TRACEPOINT.value == "tracepoint"
        assert EBPFProbeType.XDP.value == "xdp"

    def test_ebpf_probe_creation(self):
        """Test EBPFProbe dataclass."""
        from observability.ebpf import EBPFProbe, EBPFProbeType

        probe = EBPFProbe(
            name="test_probe",
            probe_type=EBPFProbeType.UPROBE,
            target="func_name",
            description="Test probe",
            tags=["test", "python"],
        )

        assert probe.name == "test_probe"
        assert probe.probe_type == EBPFProbeType.UPROBE
        assert probe.enabled is True
        assert "test" in probe.tags

    def test_ebpf_probe_to_dict(self):
        """Test EBPFProbe serialization."""
        from observability.ebpf import EBPFProbe, EBPFProbeType

        probe = EBPFProbe(
            name="test",
            probe_type=EBPFProbeType.KPROBE,
            target="sys_read",
        )
        probe.hit_count = 100

        data = probe.to_dict()
        assert data["name"] == "test"
        assert data["probe_type"] == "kprobe"
        assert data["statistics"]["hit_count"] == 100

    @pytest.mark.asyncio
    async def test_simulated_backend_load_probe(self):
        """Test simulated eBPF backend probe loading."""
        from observability.ebpf.ebpf_integration import (
            EBPFProbe,
            EBPFProbeType,
            SimulatedEBPFBackend,
        )

        backend = SimulatedEBPFBackend()
        assert backend.is_available() is True

        probe = EBPFProbe(
            name="test_probe",
            probe_type=EBPFProbeType.UPROBE,
            target="test_func",
        )

        success = await backend.load_probe(probe)
        assert success is True

    @pytest.mark.asyncio
    async def test_simulated_backend_unload_probe(self):
        """Test simulated backend probe unloading."""
        from observability.ebpf.ebpf_integration import (
            EBPFProbe,
            EBPFProbeType,
            SimulatedEBPFBackend,
        )

        backend = SimulatedEBPFBackend()
        probe = EBPFProbe(
            name="to_unload",
            probe_type=EBPFProbeType.KPROBE,
            target="test",
        )

        await backend.load_probe(probe)
        success = await backend.unload_probe("to_unload")
        assert success is True

        # Unload non-existent
        success = await backend.unload_probe("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_simulated_backend_events(self):
        """Test simulated backend event generation."""
        from observability.ebpf.ebpf_integration import (
            EBPFProbe,
            EBPFProbeType,
            SimulatedEBPFBackend,
        )

        backend = SimulatedEBPFBackend()
        probe = EBPFProbe(
            name="event_probe",
            probe_type=EBPFProbeType.TRACEPOINT,
            target="test",
        )

        await backend.load_probe(probe)

        # Generate test event
        event = backend.generate_event("event_probe", {"test": "data"})
        assert event.probe_name == "event_probe"
        assert event.data["test"] == "data"

        # Get events
        events = await backend.get_events("event_probe")
        assert len(events) >= 1


class TestGILMonitor:
    """Test Python GIL monitoring."""

    def test_gil_stats_creation(self):
        """Test GILStats dataclass."""
        from observability.ebpf.ebpf_integration import GILStats

        stats = GILStats(
            timestamp=datetime.now(),
            pid=1234,
            total_wait_time_ns=1000000,
            total_hold_time_ns=5000000,
            acquisition_count=100,
            contention_count=10,
        )

        assert stats.pid == 1234
        assert stats.avg_wait_time_ns == 10000.0
        assert stats.avg_hold_time_ns == 50000.0
        assert stats.contention_rate == 0.1

    def test_gil_stats_to_dict(self):
        """Test GILStats serialization."""
        from observability.ebpf.ebpf_integration import GILStats

        stats = GILStats(
            timestamp=datetime.now(),
            pid=5678,
            acquisition_count=50,
        )

        data = stats.to_dict()
        assert data["pid"] == 5678
        assert "avg_wait_time_ns" in data
        assert "contention_rate" in data

    @pytest.mark.asyncio
    async def test_gil_monitor_start_stop(self):
        """Test GIL monitor lifecycle."""
        from observability.ebpf.ebpf_integration import (
            EBPFConfig,
            GILMonitor,
            SimulatedEBPFBackend,
        )

        config = EBPFConfig(gil_monitoring_enabled=True)
        backend = SimulatedEBPFBackend()
        monitor = GILMonitor(config, backend)

        success = await monitor.start()
        assert success is True
        assert monitor._running is True

        await monitor.stop()
        assert monitor._running is False


class TestPixieIntegration:
    """Test Pixie integration."""

    def test_pixie_available(self):
        """Test Pixie availability check."""
        from observability.ebpf import EBPFConfig, PixieIntegration

        config = EBPFConfig(pixie_enabled=True, pixie_cluster_id="test")
        pixie = PixieIntegration(config)

        assert pixie.is_available() is True

        # Disabled
        config2 = EBPFConfig(pixie_enabled=False)
        pixie2 = PixieIntegration(config2)
        assert pixie2.is_available() is False

    def test_pixie_scripts(self):
        """Test PxL script availability."""
        from observability.ebpf import EBPFConfig, PixieIntegration

        pixie = PixieIntegration(EBPFConfig())
        scripts = pixie.get_available_scripts()

        assert "service_stats" in scripts
        assert "connection_stats" in scripts
        assert "cpu_flamegraph" in scripts

    @pytest.mark.asyncio
    async def test_pixie_connect_disconnect(self):
        """Test Pixie connection lifecycle."""
        from observability.ebpf import EBPFConfig, PixieIntegration

        config = EBPFConfig(pixie_cluster_id="test-cluster")
        pixie = PixieIntegration(config)

        success = await pixie.connect()
        assert success is True
        assert pixie._connected is True

        await pixie.disconnect()
        assert pixie._connected is False


class TestCiliumHubbleIntegration:
    """Test Cilium Hubble integration."""

    @pytest.mark.asyncio
    async def test_hubble_connect(self):
        """Test Hubble connection."""
        from observability.ebpf import CiliumHubbleIntegration, EBPFConfig

        config = EBPFConfig(hubble_enabled=True)
        hubble = CiliumHubbleIntegration(config)

        success = await hubble.connect()
        assert success is True

        await hubble.disconnect()

    @pytest.mark.asyncio
    async def test_hubble_get_flows(self):
        """Test getting network flows."""
        from observability.ebpf import CiliumHubbleIntegration, EBPFConfig

        hubble = CiliumHubbleIntegration(EBPFConfig())
        await hubble.connect()

        flows = await hubble.get_flows(namespace="aura-ia")
        assert isinstance(flows, list)

        if flows:
            assert "source" in flows[0]
            assert "destination" in flows[0]


class TestEBPFManager:
    """Test eBPF manager."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test eBPF manager initialization."""
        from observability.ebpf import EBPFConfig

        config = EBPFConfig(enabled=True)
        manager = EBPFManager(config)

        success = await manager.initialize()
        assert success is True
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_manager_start_stop(self):
        """Test manager start/stop."""

        manager = EBPFManager()
        await manager.start()

        status = manager.get_status()
        assert status["initialized"] is True

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_load_probe(self):
        """Test loading probes via manager."""
        from observability.ebpf import EBPFProbe, EBPFProbeType

        manager = EBPFManager()
        await manager.initialize()

        probe = EBPFProbe(
            name="manager_test",
            probe_type=EBPFProbeType.UPROBE,
            target="test",
        )

        success = await manager.load_probe(probe)
        assert success is True

        loaded = manager.get_probe("manager_test")
        assert loaded is not None
        assert loaded.name == "manager_test"


# ============================================================================
# Green Compute Tests
# ============================================================================


class TestCarbonIntensity:
    """Test carbon intensity data."""

    def test_carbon_intensity_creation(self):
        """Test CarbonIntensity dataclass."""
        from aura_ia_mcp.core.futuristic import CarbonIntensity

        intensity = CarbonIntensity(
            timestamp=datetime.now(),
            carbon_intensity=75.5,
            grid_region="US-CAL-CISO",
            renewable_percentage=65.0,
        )

        assert intensity.carbon_intensity == 75.5
        assert intensity.grid_region == "US-CAL-CISO"
        assert intensity.is_green is True

    def test_carbon_intensity_classification(self):
        """Test carbon intensity classification."""
        from aura_ia_mcp.core.futuristic import CarbonIntensity

        green = CarbonIntensity(
            timestamp=datetime.now(),
            carbon_intensity=50,
            grid_region="NO-NO1",
        )
        assert green.is_green is True
        assert green.is_moderate is False
        assert green.is_high is False

        moderate = CarbonIntensity(
            timestamp=datetime.now(),
            carbon_intensity=200,
            grid_region="GB",
        )
        assert moderate.is_green is False
        assert moderate.is_moderate is True
        assert moderate.is_high is False

        high = CarbonIntensity(
            timestamp=datetime.now(),
            carbon_intensity=400,
            grid_region="US-TEX-ERCO",
        )
        assert high.is_green is False
        assert high.is_moderate is False
        assert high.is_high is True


class TestCarbonDataSources:
    """Test carbon data sources."""

    @pytest.mark.asyncio
    async def test_electricity_maps_current(self):
        """Test Electricity Maps current intensity."""
        from aura_ia_mcp.core.futuristic import ElectricityMapsSource

        source = ElectricityMapsSource()
        intensity = await source.get_current_intensity("US-CAL-CISO")

        assert intensity.grid_region == "US-CAL-CISO"
        assert intensity.carbon_intensity > 0
        assert intensity.source == "electricity_maps"

    @pytest.mark.asyncio
    async def test_electricity_maps_forecast(self):
        """Test Electricity Maps forecast."""
        from aura_ia_mcp.core.futuristic import ElectricityMapsSource

        source = ElectricityMapsSource()
        forecast = await source.get_forecast("GB", hours=24)

        assert len(forecast) == 24
        assert all(f.forecast is True for f in forecast)

    def test_electricity_maps_regions(self):
        """Test supported regions."""
        from aura_ia_mcp.core.futuristic import ElectricityMapsSource

        source = ElectricityMapsSource()
        regions = source.get_supported_regions()

        assert "US-CAL-CISO" in regions
        assert "GB" in regions
        assert "FR" in regions

    @pytest.mark.asyncio
    async def test_watttime_current(self):
        """Test WattTime current intensity."""
        from aura_ia_mcp.core.futuristic import WattTimeSource

        source = WattTimeSource()
        intensity = await source.get_current_intensity("CAISO_NORTH")

        assert intensity.grid_region == "CAISO_NORTH"
        assert intensity.source == "watttime"


class TestScheduledJob:
    """Test scheduled job functionality."""

    def test_job_creation(self):
        """Test ScheduledJob creation."""
        from aura_ia_mcp.core.futuristic import (
            JobPriority,
            JobState,
            ScheduledJob,
        )

        job = ScheduledJob(
            id="job-1",
            name="Test Job",
            func=lambda: None,
            priority=JobPriority.NORMAL,
        )

        assert job.id == "job-1"
        assert job.state == JobState.PENDING
        assert job.priority == JobPriority.NORMAL

    def test_job_ordering(self):
        """Test job priority ordering."""
        from aura_ia_mcp.core.futuristic import JobPriority, ScheduledJob

        critical = ScheduledJob(
            id="critical",
            name="Critical",
            func=lambda: None,
            priority=JobPriority.CRITICAL,
        )

        normal = ScheduledJob(
            id="normal",
            name="Normal",
            func=lambda: None,
            priority=JobPriority.NORMAL,
        )

        background = ScheduledJob(
            id="bg",
            name="Background",
            func=lambda: None,
            priority=JobPriority.BACKGROUND,
        )

        # Critical < Normal < Background (lower = higher priority)
        assert critical < normal
        assert normal < background

    def test_job_to_dict(self):
        """Test job serialization."""
        from aura_ia_mcp.core.futuristic import JobPriority, ScheduledJob

        job = ScheduledJob(
            id="j1",
            name="Serialize Test",
            func=lambda: "result",
            priority=JobPriority.HIGH,
        )

        data = job.to_dict()
        assert data["id"] == "j1"
        assert data["priority"] == "HIGH"
        assert data["state"] == "pending"


class TestCarbonAwareScheduler:
    """Test carbon-aware scheduler."""

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """Test scheduler lifecycle."""
        from aura_ia_mcp.core.futuristic import CarbonAwareScheduler

        scheduler = CarbonAwareScheduler(region="US-CAL-CISO")

        await scheduler.start()
        assert scheduler._running is True

        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_scheduler_schedule_job(self):
        """Test scheduling a job."""
        from aura_ia_mcp.core.futuristic import (
            CarbonAwareScheduler,
            JobPriority,
            ScheduledJob,
        )

        scheduler = CarbonAwareScheduler()

        job = ScheduledJob(
            id="test-job",
            name="Test",
            func=lambda: "done",
            priority=JobPriority.NORMAL,
        )

        job_id = scheduler.schedule(job)
        assert job_id == "test-job"

        retrieved = scheduler.get_job(job_id)
        assert retrieved is not None
        assert retrieved.name == "Test"

    @pytest.mark.asyncio
    async def test_scheduler_cancel_job(self):
        """Test cancelling a job."""
        from aura_ia_mcp.core.futuristic import (
            CarbonAwareScheduler,
            JobState,
            ScheduledJob,
        )

        scheduler = CarbonAwareScheduler()

        job = ScheduledJob(
            id="cancel-me",
            name="To Cancel",
            func=lambda: None,
        )

        scheduler.schedule(job)
        success = scheduler.cancel("cancel-me")
        assert success is True

        cancelled = scheduler.get_job("cancel-me")
        assert cancelled.state == JobState.CANCELLED

    @pytest.mark.asyncio
    async def test_scheduler_get_current_carbon(self):
        """Test getting current carbon intensity."""
        from aura_ia_mcp.core.futuristic import CarbonAwareScheduler

        scheduler = CarbonAwareScheduler(region="GB")
        intensity = await scheduler.get_current_carbon()

        assert intensity.grid_region == "GB"
        assert intensity.carbon_intensity > 0

    @pytest.mark.asyncio
    async def test_scheduler_get_optimal_window(self):
        """Test finding optimal carbon window."""
        from aura_ia_mcp.core.futuristic import CarbonAwareScheduler

        scheduler = CarbonAwareScheduler(region="NO-NO1")  # Low carbon region
        window = await scheduler.get_optimal_window(threshold=100, hours=24)

        # Should find a window in low-carbon region
        if window:
            assert "start" in window
            assert "avg_intensity" in window

    def test_scheduler_statistics(self):
        """Test scheduler statistics."""
        from aura_ia_mcp.core.futuristic import CarbonAwareScheduler

        scheduler = CarbonAwareScheduler()
        stats = scheduler.get_statistics()

        assert "region" in stats
        assert "total_jobs" in stats
        assert "budget" in stats


class TestCarbonBudget:
    """Test carbon budget tracking."""

    def test_budget_creation(self):
        """Test CarbonBudget creation."""
        from aura_ia_mcp.core.futuristic.green_compute import CarbonBudget

        budget = CarbonBudget(
            daily_budget_gco2=5000.0,
            monthly_budget_gco2=100000.0,
        )

        assert budget.daily_budget == 5000.0
        assert budget.monthly_budget == 100000.0

    def test_budget_record_usage(self):
        """Test recording carbon usage."""
        from aura_ia_mcp.core.futuristic.green_compute import CarbonBudget

        budget = CarbonBudget(daily_budget_gco2=1000.0)

        budget.record_usage(100.0)
        budget.record_usage(50.0)

        assert budget.daily_remaining == 850.0
        assert budget.daily_usage_percentage == 15.0

    def test_budget_to_dict(self):
        """Test budget serialization."""
        from aura_ia_mcp.core.futuristic.green_compute import CarbonBudget

        budget = CarbonBudget()
        budget.record_usage(500.0)

        data = budget.to_dict()
        assert "daily" in data
        assert "monthly" in data
        assert data["daily"]["used"] == 500.0


# ============================================================================
# WASM Sandbox Tests
# ============================================================================


class TestWASMCapabilities:
    """Test WASM capability system."""

    def test_capability_flags(self):
        """Test WASMCapability flag combinations."""
        from aura_ia_mcp.core.futuristic import WASMCapability

        # Individual flags
        assert WASMCapability.FS_READ.value > 0
        assert WASMCapability.NET_HTTP.value > 0

        # Combined flags
        fs_all = WASMCapability.FS_ALL
        assert WASMCapability.FS_READ in fs_all
        assert WASMCapability.FS_WRITE in fs_all
        assert WASMCapability.FS_CREATE in fs_all

    def test_capability_safe_default(self):
        """Test SAFE capability set."""
        from aura_ia_mcp.core.futuristic import WASMCapability

        safe = WASMCapability.SAFE

        # Should include safe capabilities
        assert WASMCapability.FS_READ in safe
        assert WASMCapability.NET_HTTP in safe
        assert WASMCapability.SYS_TIME in safe

        # Should not include dangerous capabilities
        assert WASMCapability.NET_SOCKET not in safe
        assert WASMCapability.SYS_ENV_WRITE not in safe


class TestWASMConfig:
    """Test WASM configuration."""

    def test_config_defaults(self):
        """Test WASMConfig default values."""
        from aura_ia_mcp.core.futuristic import WASMConfig

        config = WASMConfig()

        assert config.enabled is True
        assert config.runtime == "wasmedge"
        assert config.max_memory_mb == 64
        assert config.max_instances == 10

    def test_config_to_dict(self):
        """Test config serialization."""
        from aura_ia_mcp.core.futuristic import WASMConfig

        config = WASMConfig(max_memory_mb=128, require_signature=False)
        data = config.to_dict()

        assert data["limits"]["max_memory_mb"] == 128
        assert data["security"]["require_signature"] is False


class TestPluginManifest:
    """Test plugin manifest handling."""

    def test_manifest_creation(self):
        """Test PluginManifest creation."""
        from aura_ia_mcp.core.futuristic import PluginManifest

        manifest = PluginManifest(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            exports=["run", "init"],
        )

        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"
        assert "run" in manifest.exports

    def test_manifest_from_dict(self):
        """Test manifest parsing from dict."""
        from aura_ia_mcp.core.futuristic import PluginManifest

        data = {
            "name": "parsed-plugin",
            "version": "2.0.0",
            "main": "main.wasm",
            "required_capabilities": ["FS_READ", "NET_HTTP"],
        }

        manifest = PluginManifest.from_dict(data)

        assert manifest.name == "parsed-plugin"
        assert manifest.main == "main.wasm"

    def test_manifest_validation(self):
        """Test manifest validation."""
        from aura_ia_mcp.core.futuristic import PluginManifest

        # Valid manifest
        valid = PluginManifest(
            name="valid",
            version="1.0",
            main="plugin.wasm",
            exports=["run"],
        )
        errors = valid.validate()
        assert len(errors) == 0

        # Invalid manifest (no name)
        invalid = PluginManifest(
            name="",
            version="1.0",
            main="plugin.wasm",
        )
        errors = invalid.validate()
        assert len(errors) > 0

    def test_manifest_to_dict(self):
        """Test manifest serialization."""
        from aura_ia_mcp.core.futuristic import PluginManifest, WASMCapability

        manifest = PluginManifest(
            name="serialize-test",
            version="1.0.0",
            required_capabilities=WASMCapability.FS_READ
            | WASMCapability.NET_HTTP,
        )

        data = manifest.to_dict()
        assert data["name"] == "serialize-test"
        assert "FS_READ" in data["required_capabilities"]


class TestWASMPlugin:
    """Test WASM plugin handling."""

    def test_plugin_creation(self):
        """Test WASMPlugin creation."""
        from aura_ia_mcp.core.futuristic import (
            PluginManifest,
            PluginState,
            WASMPlugin,
        )

        manifest = PluginManifest(name="test", version="1.0")
        plugin = WASMPlugin(
            id="plugin-1",
            manifest=manifest,
            wasm_path=Path("/tmp/test.wasm"),
        )

        assert plugin.id == "plugin-1"
        assert plugin.state == PluginState.UNLOADED
        assert plugin.call_count == 0

    def test_plugin_to_dict(self):
        """Test plugin serialization."""
        from aura_ia_mcp.core.futuristic import PluginManifest, WASMPlugin

        manifest = PluginManifest(name="dict-test", version="2.0")
        plugin = WASMPlugin(
            id="p-dict",
            manifest=manifest,
            wasm_path=Path("/tmp/dict.wasm"),
        )
        plugin.call_count = 5

        data = plugin.to_dict()
        assert data["id"] == "p-dict"
        assert data["name"] == "dict-test"
        assert data["resources"]["call_count"] == 5


class TestWASMSandbox:
    """Test WASM sandbox."""

    @pytest.mark.asyncio
    async def test_sandbox_initialization(self):
        """Test sandbox initialization."""
        from aura_ia_mcp.core.futuristic import WASMConfig, WASMSandbox

        config = WASMConfig(enabled=True)
        sandbox = WASMSandbox(config)

        success = await sandbox.initialize()
        assert success is True
        assert sandbox._initialized is True

    @pytest.mark.asyncio
    async def test_sandbox_load_plugin(self):
        """Test loading a plugin."""
        from aura_ia_mcp.core.futuristic import (
            PluginManifest,
            PluginState,
            WASMConfig,
            WASMSandbox,
        )

        sandbox = WASMSandbox(WASMConfig(require_signature=False))
        await sandbox.initialize()

        manifest = PluginManifest(
            name="load-test",
            version="1.0",
            exports=["run"],
        )

        # Create temp wasm file
        with tempfile.NamedTemporaryFile(suffix=".wasm", delete=False) as f:
            f.write(b"\x00asm\x01\x00\x00\x00")  # Minimal WASM header
            wasm_path = Path(f.name)

        try:
            plugin = await sandbox.load_plugin(manifest, wasm_path)
            assert plugin.state == PluginState.READY
            assert plugin.manifest.name == "load-test"
        finally:
            wasm_path.unlink()

    @pytest.mark.asyncio
    async def test_sandbox_call_plugin(self):
        """Test calling a plugin function."""
        from aura_ia_mcp.core.futuristic import (
            PluginManifest,
            WASMConfig,
            WASMSandbox,
        )

        sandbox = WASMSandbox(WASMConfig(require_signature=False))
        await sandbox.initialize()

        manifest = PluginManifest(
            name="call-test",
            version="1.0",
            exports=["run", "process"],
        )

        with tempfile.NamedTemporaryFile(suffix=".wasm", delete=False) as f:
            f.write(b"\x00asm\x01\x00\x00\x00")
            wasm_path = Path(f.name)

        try:
            plugin = await sandbox.load_plugin(manifest, wasm_path)
            result = await sandbox.call_plugin(
                plugin.id, "run", args=[1, 2, 3]
            )

            assert result.success is True
            assert result.execution_time_ms > 0
        finally:
            wasm_path.unlink()

    @pytest.mark.asyncio
    async def test_sandbox_unload_plugin(self):
        """Test unloading a plugin."""
        from aura_ia_mcp.core.futuristic import (
            PluginManifest,
            WASMConfig,
            WASMSandbox,
        )

        sandbox = WASMSandbox(WASMConfig(require_signature=False))
        await sandbox.initialize()

        manifest = PluginManifest(name="unload-test", version="1.0")

        with tempfile.NamedTemporaryFile(suffix=".wasm", delete=False) as f:
            f.write(b"\x00asm\x01\x00\x00\x00")
            wasm_path = Path(f.name)

        try:
            plugin = await sandbox.load_plugin(manifest, wasm_path)
            success = await sandbox.unload_plugin(plugin.id)
            assert success is True

            # Should not find after unload
            assert sandbox.get_plugin(plugin.id) is None
        finally:
            wasm_path.unlink()

    def test_sandbox_status(self):
        """Test sandbox status."""
        from aura_ia_mcp.core.futuristic import WASMSandbox

        sandbox = WASMSandbox()
        status = sandbox.get_status()

        assert "initialized" in status
        assert "plugins_loaded" in status
        assert "runtime" in status


class TestPluginTemplate:
    """Test plugin template generation."""

    def test_rust_template(self):
        """Test Rust plugin template."""
        from aura_ia_mcp.core.futuristic.wasm_sandbox import (
            generate_plugin_template,
        )

        template = generate_plugin_template("my-plugin", "rust")

        assert "my-plugin" in template
        assert "#[no_mangle]" in template
        assert "pub extern" in template

    def test_assemblyscript_template(self):
        """Test AssemblyScript plugin template."""
        from aura_ia_mcp.core.futuristic.wasm_sandbox import (
            generate_plugin_template,
        )

        template = generate_plugin_template("as-plugin", "assemblyscript")

        assert "as-plugin" in template
        assert "export function run" in template

    def test_go_template(self):
        """Test Go plugin template."""
        from aura_ia_mcp.core.futuristic.wasm_sandbox import (
            generate_plugin_template,
        )

        template = generate_plugin_template("go-plugin", "go")

        assert "go-plugin" in template
        assert "//export run" in template


# ============================================================================
# Confidential Computing Tests
# ============================================================================


class TestEnclaveConfig:
    """Test enclave configuration."""

    def test_config_defaults(self):
        """Test EnclaveConfig defaults."""
        from aura_ia_mcp.core.futuristic import EnclaveConfig, EnclaveType

        config = EnclaveConfig()

        assert config.enabled is True
        assert config.enclave_type == EnclaveType.SIMULATED
        assert config.sgx_enclave_size_mb == 256
        assert config.enable_attestation is True

    def test_config_to_dict(self):
        """Test config serialization."""
        from aura_ia_mcp.core.futuristic import EnclaveConfig, EnclaveType

        config = EnclaveConfig(
            enclave_type=EnclaveType.INTEL_SGX,
            sgx_debug_mode=True,
        )

        data = config.to_dict()
        assert data["enclave_type"] == "intel_sgx"
        assert data["sgx"]["debug_mode"] is True


class TestEnclaveManifest:
    """Test enclave manifest."""

    def test_manifest_creation(self):
        """Test EnclaveManifest creation."""
        from aura_ia_mcp.core.futuristic import EnclaveManifest

        manifest = EnclaveManifest(
            name="test-enclave",
            version="1.0",
            entrypoint="/usr/bin/python3",
            heap_size_mb=256,
        )

        assert manifest.name == "test-enclave"
        assert manifest.heap_size_mb == 256

    def test_manifest_to_gramine(self):
        """Test Gramine manifest generation."""
        from aura_ia_mcp.core.futuristic import EnclaveManifest

        manifest = EnclaveManifest(
            name="gramine-test",
            version="1.0",
            entrypoint="/app/main.py",
            trusted_files=["/app/model.bin"],
            environment={"PYTHONPATH": "/app"},
        )

        gramine = manifest.to_gramine_manifest()

        assert "gramine-test" in gramine
        assert "/app/main.py" in gramine
        assert "PYTHONPATH" in gramine
        assert "sgx.debug" in gramine

    def test_manifest_to_scone(self):
        """Test SCONE session generation."""
        from aura_ia_mcp.core.futuristic import EnclaveManifest

        manifest = EnclaveManifest(
            name="scone-test",
            version="2.0",
        )

        session = manifest.to_scone_session()

        assert session["name"] == "scone-test-session"
        assert len(session["services"]) == 1
        assert session["services"][0]["name"] == "scone-test"


class TestAttestationReport:
    """Test attestation reports."""

    def test_report_creation(self):
        """Test AttestationReport creation."""
        from aura_ia_mcp.core.futuristic.confidential_compute import (
            AttestationReport,
            AttestationStatus,
            EnclaveType,
        )

        report = AttestationReport(
            timestamp=datetime.now(),
            enclave_type=EnclaveType.INTEL_SGX,
            status=AttestationStatus.VERIFIED,
            mrenclave="abc123",
            valid_until=datetime.now() + timedelta(hours=24),
        )

        assert report.status == AttestationStatus.VERIFIED
        assert report.is_valid is True

    def test_report_validity(self):
        """Test attestation validity check."""
        from aura_ia_mcp.core.futuristic.confidential_compute import (
            AttestationReport,
            AttestationStatus,
            EnclaveType,
        )

        # Expired report
        expired = AttestationReport(
            timestamp=datetime.now() - timedelta(days=2),
            enclave_type=EnclaveType.SIMULATED,
            status=AttestationStatus.VERIFIED,
            valid_until=datetime.now() - timedelta(hours=1),
        )
        assert expired.is_valid is False

        # Failed attestation
        failed = AttestationReport(
            timestamp=datetime.now(),
            enclave_type=EnclaveType.SIMULATED,
            status=AttestationStatus.FAILED,
        )
        assert failed.is_valid is False


class TestSimulatedEnclave:
    """Test simulated enclave."""

    @pytest.mark.asyncio
    async def test_enclave_initialization(self):
        """Test enclave initialization."""
        from aura_ia_mcp.core.futuristic.confidential_compute import (
            EnclaveManifest,
            SimulatedEnclave,
        )

        enclave = SimulatedEnclave()
        assert enclave.is_available() is True

        manifest = EnclaveManifest(name="init-test", version="1.0")
        success = await enclave.initialize(manifest)

        assert success is True
        assert manifest.mrenclave != ""

    @pytest.mark.asyncio
    async def test_enclave_execution(self):
        """Test execution in enclave."""
        from aura_ia_mcp.core.futuristic.confidential_compute import (
            EnclaveManifest,
            SimulatedEnclave,
        )

        enclave = SimulatedEnclave()
        manifest = EnclaveManifest(name="exec-test", version="1.0")
        await enclave.initialize(manifest)

        result = await enclave.execute("predict", {"input": [1, 2, 3]})

        assert result["function"] == "predict"
        assert result["executed_in"] == "simulated_enclave"

    @pytest.mark.asyncio
    async def test_enclave_attestation(self):
        """Test getting attestation."""
        from aura_ia_mcp.core.futuristic.confidential_compute import (
            AttestationStatus,
            EnclaveManifest,
            SimulatedEnclave,
        )

        enclave = SimulatedEnclave()
        manifest = EnclaveManifest(name="attest-test", version="1.0")
        await enclave.initialize(manifest)

        report = await enclave.get_attestation()

        assert report.status == AttestationStatus.VERIFIED
        assert report.is_valid is True

    @pytest.mark.asyncio
    async def test_enclave_sealing(self):
        """Test data sealing/unsealing."""
        from aura_ia_mcp.core.futuristic.confidential_compute import (
            EnclaveManifest,
            SimulatedEnclave,
        )

        enclave = SimulatedEnclave()
        manifest = EnclaveManifest(name="seal-test", version="1.0")
        await enclave.initialize(manifest)

        original = b"secret model weights"
        sealed = await enclave.seal_data(original)

        assert sealed != original

        unsealed = await enclave.unseal_data(sealed)
        assert unsealed == original


class TestEnclaveManager:
    """Test enclave manager."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test manager initialization."""
        from aura_ia_mcp.core.futuristic import EnclaveConfig, EnclaveManager

        config = EnclaveConfig(enabled=True)
        manager = EnclaveManager(config)

        success = await manager.initialize()
        assert success is True

    @pytest.mark.asyncio
    async def test_manager_create_enclave(self):
        """Test creating an enclave via manager."""
        from aura_ia_mcp.core.futuristic import EnclaveManager

        manager = EnclaveManager()
        await manager.initialize()

        enclave_id = await manager.create_enclave(
            name="managed-enclave",
            version="1.0",
        )

        assert "managed-enclave" in enclave_id
        assert enclave_id in manager.list_enclaves()

    @pytest.mark.asyncio
    async def test_manager_execute(self):
        """Test execution via manager."""
        from aura_ia_mcp.core.futuristic import EnclaveManager

        manager = EnclaveManager()
        enclave_id = await manager.create_enclave("exec-enclave")

        result = await manager.execute_in_enclave(
            enclave_id,
            "inference",
            {"model": "bert", "input": "test"},
        )

        assert result["function"] == "inference"

    @pytest.mark.asyncio
    async def test_manager_attestation(self):
        """Test getting attestation via manager."""
        from aura_ia_mcp.core.futuristic import EnclaveManager

        manager = EnclaveManager()
        enclave_id = await manager.create_enclave("attest-enclave")

        report = await manager.get_attestation(enclave_id)
        assert report.is_valid is True

    @pytest.mark.asyncio
    async def test_manager_terminate(self):
        """Test terminating an enclave."""
        from aura_ia_mcp.core.futuristic import EnclaveManager

        manager = EnclaveManager()
        enclave_id = await manager.create_enclave("terminate-enclave")

        success = await manager.terminate_enclave(enclave_id)
        assert success is True
        assert enclave_id not in manager.list_enclaves()

    def test_manager_status(self):
        """Test manager status."""
        from aura_ia_mcp.core.futuristic import EnclaveManager

        manager = EnclaveManager()
        status = manager.get_status()

        assert "initialized" in status
        assert "enclave_type" in status
        assert "enclaves_count" in status


# ============================================================================
# Integration Tests
# ============================================================================


class TestPhase6Integration:
    """Integration tests for Phase 6 components."""

    @pytest.mark.asyncio
    async def test_ebpf_manager_singleton(self):
        """Test eBPF manager singleton."""
        from observability.ebpf import get_ebpf_manager

        m1 = get_ebpf_manager()
        m2 = get_ebpf_manager()

        assert m1 is m2

    @pytest.mark.asyncio
    async def test_carbon_scheduler_singleton(self):
        """Test carbon scheduler singleton."""
        from aura_ia_mcp.core.futuristic import get_carbon_scheduler

        s1 = get_carbon_scheduler()
        s2 = get_carbon_scheduler()

        assert s1 is s2

    @pytest.mark.asyncio
    async def test_wasm_sandbox_singleton(self):
        """Test WASM sandbox singleton."""
        from aura_ia_mcp.core.futuristic import get_wasm_sandbox

        sb1 = get_wasm_sandbox()
        sb2 = get_wasm_sandbox()

        assert sb1 is sb2

    @pytest.mark.asyncio
    async def test_enclave_manager_singleton(self):
        """Test enclave manager singleton."""
        from aura_ia_mcp.core.futuristic import get_enclave_manager

        em1 = get_enclave_manager()
        em2 = get_enclave_manager()

        assert em1 is em2

    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self):
        """Test simulated full workflow across Phase 6 components."""
        from aura_ia_mcp.core.futuristic import (
            CarbonAwareScheduler,
            EnclaveManager,
            JobPriority,
            ScheduledJob,
            WASMSandbox,
        )

        # Initialize all components
        ebpf = EBPFManager()
        await ebpf.initialize()

        scheduler = CarbonAwareScheduler(region="NO-NO1")  # Low carbon
        sandbox = WASMSandbox()
        await sandbox.initialize()

        enclave_mgr = EnclaveManager()
        await enclave_mgr.initialize()

        # Get carbon intensity
        carbon = await scheduler.get_current_carbon()
        assert carbon.carbon_intensity > 0

        # Create secure enclave for model
        enclave_id = await enclave_mgr.create_enclave("model-enclave")

        # Schedule a carbon-aware job
        job = ScheduledJob(
            id="inference-job",
            name="Run Inference",
            func=lambda: "inference_result",
            priority=JobPriority.NORMAL,
            preferred_carbon_threshold=carbon.carbon_intensity + 50,
        )
        scheduler.schedule(job)

        # Verify all components are working
        assert ebpf.get_status()["initialized"]
        assert len(scheduler.list_jobs()) >= 1
        assert sandbox.get_status()["initialized"]
        assert enclave_id in enclave_mgr.list_enclaves()

        # Cleanup
        await ebpf.stop()
        await scheduler.stop()
        await enclave_mgr.terminate_enclave(enclave_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
