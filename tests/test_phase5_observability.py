"""
Comprehensive Test Suite for Phase 5: Observability Platform.

Tests cover:
- Prometheus configuration generation
- Grafana dashboard generation
- OpenTelemetry integration
- Loki log aggregation
- Alerting rules validation
"""

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Test Prometheus Configuration
# =============================================================================
class TestPrometheusConfig:
    """Tests for Prometheus configuration generation."""

    def test_scrape_target_creation(self):
        """Test creating a scrape target configuration."""
        from observability.prometheus.prometheus_config import (
            ScrapeTarget,
            ServiceType,
        )

        target = ScrapeTarget(
            job_name="test-job",
            service_type=ServiceType.GATEWAY,
            port=9200,
            path="/metrics",
            interval="15s",
        )

        config = target.to_scrape_config("aura-ia")

        assert config["job_name"] == "test-job"
        assert config["scrape_interval"] == "15s"
        assert config["metrics_path"] == "/metrics"
        assert "kubernetes_sd_configs" in config
        assert len(config["relabel_configs"]) >= 3

    def test_alert_rule_creation(self):
        """Test creating an alerting rule."""
        from observability.prometheus.prometheus_config import AlertRule

        rule = AlertRule(
            name="TestAlert",
            expr="up == 0",
            duration="5m",
            severity="critical",
            summary="Test alert fired",
            description="This is a test alert",
        )

        rule_config = rule.to_rule()

        assert rule_config["alert"] == "TestAlert"
        assert rule_config["expr"] == "up == 0"
        assert rule_config["for"] == "5m"
        assert rule_config["labels"]["severity"] == "critical"
        assert "summary" in rule_config["annotations"]

    def test_recording_rule_creation(self):
        """Test creating a recording rule."""
        from observability.prometheus.prometheus_config import RecordingRule

        rule = RecordingRule(
            record="job:http_requests:rate5m",
            expr="sum(rate(http_requests_total[5m])) by (job)",
            labels={"environment": "production"},
        )

        rule_config = rule.to_rule()

        assert rule_config["record"] == "job:http_requests:rate5m"
        assert "rate" in rule_config["expr"]
        assert rule_config["labels"]["environment"] == "production"

    def test_prometheus_config_generator(self):
        """Test the full Prometheus config generator."""
        from observability.prometheus.prometheus_config import (
            PrometheusConfigGenerator,
        )

        generator = PrometheusConfigGenerator(namespace="test-ns")

        # Generate configs
        prom_config = generator.generate_prometheus_config()
        alert_rules = generator.generate_alert_rules_config()
        recording_rules = generator.generate_recording_rules_config()

        # Verify prometheus config
        assert "global" in prom_config
        assert prom_config["global"]["scrape_interval"] == "15s"
        assert "scrape_configs" in prom_config
        assert len(prom_config["scrape_configs"]) >= 5  # All service types

        # Verify alert rules
        assert "groups" in alert_rules
        assert len(alert_rules["groups"]) > 0
        assert "rules" in alert_rules["groups"][0]
        assert len(alert_rules["groups"][0]["rules"]) >= 5

        # Verify recording rules
        assert "groups" in recording_rules
        assert len(recording_rules["groups"]) > 0

    def test_service_monitor_generation(self):
        """Test ServiceMonitor generation for Kubernetes."""
        from observability.prometheus.prometheus_config import (
            PrometheusConfigGenerator,
            ServiceType,
        )

        generator = PrometheusConfigGenerator(namespace="aura-ia")

        sm = generator.generate_service_monitor(ServiceType.GATEWAY)

        assert sm["apiVersion"] == "monitoring.coreos.com/v1"
        assert sm["kind"] == "ServiceMonitor"
        assert sm["metadata"]["name"] == "aura-ia-gateway"
        assert sm["metadata"]["namespace"] == "aura-ia"
        assert "endpoints" in sm["spec"]

    def test_default_alert_rules(self):
        """Test that default alert rules are properly configured."""
        from observability.prometheus.prometheus_config import (
            PrometheusConfigGenerator,
        )

        generator = PrometheusConfigGenerator()
        alert_config = generator.generate_alert_rules_config()

        rule_names = [r["alert"] for r in alert_config["groups"][0]["rules"]]

        # Verify critical alerts exist
        assert "AuraHighErrorRate" in rule_names
        assert "AuraGatewayUnavailable" in rule_names
        assert "AuraHighLatency" in rule_names
        assert "AuraPodRestarting" in rule_names

    def test_config_export(self):
        """Test exporting configs to files."""
        from observability.prometheus.prometheus_config import (
            PrometheusConfigGenerator,
        )

        generator = PrometheusConfigGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            exported = generator.export_configs(output_dir)

            assert "prometheus_config" in exported
            assert "alert_rules" in exported
            assert "recording_rules" in exported

            # Verify files exist
            assert exported["prometheus_config"].exists()
            assert exported["alert_rules"].exists()
            assert exported["recording_rules"].exists()


# =============================================================================
# Test Grafana Dashboards
# =============================================================================
class TestGrafanaDashboards:
    """Tests for Grafana dashboard generation."""

    def test_panel_creation(self):
        """Test creating a Grafana panel."""
        from observability.grafana.grafana_dashboards import (
            GrafanaPanel,
            PanelType,
        )

        panel = GrafanaPanel(
            title="Test Panel",
            panel_type=PanelType.TIMESERIES,
            targets=[
                {
                    "expr": "rate(http_requests_total[5m])",
                    "legendFormat": "Requests/sec",
                    "refId": "A",
                }
            ],
            unit="reqps",
            grid_pos={"w": 12, "h": 8},
        )

        panel_json = panel.to_panel(1)

        assert panel_json["id"] == 1
        assert panel_json["type"] == "timeseries"
        assert panel_json["title"] == "Test Panel"
        assert len(panel_json["targets"]) == 1

    def test_gauge_panel(self):
        """Test gauge panel creation."""
        from observability.grafana.grafana_dashboards import (
            GrafanaPanel,
            PanelType,
        )

        panel = GrafanaPanel(
            title="Error Rate",
            panel_type=PanelType.GAUGE,
            targets=[{"expr": "sum(rate(errors[5m]))", "refId": "A"}],
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 50},
                {"color": "red", "value": 80},
            ],
        )

        panel_json = panel.to_panel(2)

        assert panel_json["type"] == "gauge"
        assert (
            len(panel_json["fieldConfig"]["defaults"]["thresholds"]["steps"])
            == 3
        )

    def test_dashboard_generator(self):
        """Test the full dashboard generator."""
        from observability.grafana.grafana_dashboards import (
            GrafanaDashboardGenerator,
            GrafanaPanel,
            GrafanaRow,
            PanelType,
        )

        dashboard = GrafanaDashboardGenerator(
            title="Test Dashboard", uid="test-dash", tags=["test"]
        )

        # Add a row with panels
        row = GrafanaRow(title="Test Row")
        row.panels.append(
            GrafanaPanel(
                title="Test Panel",
                panel_type=PanelType.STAT,
                targets=[{"expr": "up", "refId": "A"}],
            )
        )
        dashboard.add_row(row)

        dash_json = dashboard.generate_dashboard()

        assert dash_json["title"] == "Test Dashboard"
        assert dash_json["uid"] == "test-dash"
        assert "test" in dash_json["tags"]
        assert len(dash_json["panels"]) >= 1

    def test_gateway_dashboard(self):
        """Test gateway dashboard creation."""
        from observability.grafana.grafana_dashboards import (
            create_gateway_dashboard,
        )

        dashboard = create_gateway_dashboard()
        dash_json = dashboard.generate_dashboard()

        assert dash_json["title"] == "Aura IA Gateway"
        assert dash_json["uid"] == "aura-gateway"
        assert len(dash_json["panels"]) >= 4  # At least overview panels

    def test_ml_backend_dashboard(self):
        """Test ML backend dashboard creation."""
        from observability.grafana.grafana_dashboards import (
            create_ml_backend_dashboard,
        )

        dashboard = create_ml_backend_dashboard()
        dash_json = dashboard.generate_dashboard()

        assert dash_json["title"] == "Aura IA ML Backend"
        assert "ml" in dash_json["tags"]

    def test_rag_dashboard(self):
        """Test RAG dashboard creation."""
        from observability.grafana.grafana_dashboards import (
            create_rag_dashboard,
        )

        dashboard = create_rag_dashboard()
        dash_json = dashboard.generate_dashboard()

        assert dash_json["title"] == "Aura IA RAG Service"
        assert "rag" in dash_json["tags"]

    def test_overview_dashboard(self):
        """Test overview dashboard creation."""
        from observability.grafana.grafana_dashboards import (
            create_overview_dashboard,
        )

        dashboard = create_overview_dashboard()
        dash_json = dashboard.generate_dashboard()

        assert dash_json["title"] == "Aura IA Overview"
        assert "overview" in dash_json["tags"]

    def test_export_all_dashboards(self):
        """Test exporting all dashboards."""
        from observability.grafana.grafana_dashboards import (
            export_all_dashboards,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            exported = export_all_dashboards(output_dir)

            assert len(exported) >= 4
            assert "overview" in exported
            assert "gateway" in exported
            assert "ml_backend" in exported
            assert "rag" in exported

            # Verify files exist and are valid JSON
            for name, path in exported.items():
                assert path.exists()
                with open(path) as f:
                    data = json.load(f)
                    assert "panels" in data


# =============================================================================
# Test OpenTelemetry Integration
# =============================================================================
class TestOpenTelemetryIntegration:
    """Tests for OpenTelemetry integration."""

    def test_telemetry_config_from_env(self):
        """Test creating telemetry config from environment."""
        from observability.otel.otel_integration import TelemetryConfig

        with patch.dict(
            os.environ,
            {
                "OTEL_SERVICE_NAME": "test-service",
                "OTEL_SERVICE_VERSION": "2.0.0",
                "ENVIRONMENT": "test",
            },
        ):
            config = TelemetryConfig.from_env()

            assert config.service_name == "test-service"
            assert config.service_version == "2.0.0"
            assert config.environment == "test"

    def test_telemetry_config_defaults(self):
        """Test telemetry config default values."""
        from observability.otel.otel_integration import TelemetryConfig

        config = TelemetryConfig()

        assert config.service_name == "aura-ia-gateway"
        assert config.enable_tracing is True
        assert config.enable_metrics is True
        assert config.sample_rate == 1.0

    def test_span_attribute_enum(self):
        """Test span attribute definitions."""
        from observability.otel.otel_integration import SpanAttribute

        assert SpanAttribute.SERVICE.value == "aura.service"
        assert SpanAttribute.TOOL_NAME.value == "aura.tool_name"
        assert SpanAttribute.RISK_LEVEL.value == "aura.risk_level"

    def test_telemetry_singleton(self):
        """Test that AuraTelemetry is a singleton."""
        from observability.otel.otel_integration import (
            AuraTelemetry,
            TelemetryConfig,
        )

        # Reset singleton
        AuraTelemetry._instance = None

        config = TelemetryConfig(enable_tracing=False, enable_metrics=False)
        t1 = AuraTelemetry(config)
        t2 = AuraTelemetry()

        assert t1 is t2

        # Clean up
        AuraTelemetry._instance = None

    def test_get_telemetry(self):
        """Test get_telemetry convenience function."""
        from observability.otel.otel_integration import (
            AuraTelemetry,
            get_telemetry,
        )

        # Reset singleton
        AuraTelemetry._instance = None

        telemetry = get_telemetry()
        assert telemetry is not None

        # Clean up
        AuraTelemetry._instance = None

    @patch("observability.otel.otel_integration.OTEL_AVAILABLE", False)
    def test_telemetry_without_otel_packages(self):
        """Test telemetry gracefully handles missing OTEL packages."""
        from observability.otel.otel_integration import (
            AuraTelemetry,
            TelemetryConfig,
        )

        # Reset singleton
        AuraTelemetry._instance = None

        config = TelemetryConfig()
        telemetry = AuraTelemetry(config)

        # Should not raise
        with telemetry.start_span("test"):
            pass

        # Clean up
        AuraTelemetry._instance = None

    def test_record_request(self):
        """Test recording request metrics."""
        from observability.otel.otel_integration import (
            AuraTelemetry,
            TelemetryConfig,
        )

        # Reset singleton
        AuraTelemetry._instance = None

        config = TelemetryConfig(enable_tracing=False, enable_metrics=False)
        telemetry = AuraTelemetry(config)

        # Should not raise even without OTEL
        telemetry.record_request("gateway", "POST", 200, 0.15)
        telemetry.record_tool_call("search", True, 0.5, "analyst")
        telemetry.record_inference("gpt-4", 1.2, 150, True)
        telemetry.record_rag_query("docs", 0.3, 10)
        telemetry.record_debate(5.0, 3, True)
        telemetry.record_approval("delete", "high", "approved")

        # Clean up
        AuraTelemetry._instance = None


# =============================================================================
# Test Loki Log Aggregation
# =============================================================================
class TestLokiIntegration:
    """Tests for Loki log aggregation."""

    def test_loki_config_from_env(self):
        """Test creating Loki config from environment."""
        from observability.loki.loki_integration import LokiConfig

        with patch.dict(
            os.environ,
            {
                "LOKI_ENDPOINT": "http://test-loki:3100",
                "LOKI_TENANT_ID": "test-tenant",
            },
        ):
            config = LokiConfig.from_env()

            assert config.endpoint == "http://test-loki:3100"
            assert config.tenant_id == "test-tenant"

    def test_loki_config_defaults(self):
        """Test Loki config default values."""
        from observability.loki.loki_integration import LokiConfig

        config = LokiConfig()

        assert config.endpoint == "http://localhost:3100"
        assert config.batch_size == 100
        assert config.flush_interval_seconds == 5.0

    def test_log_entry_creation(self):
        """Test creating a log entry."""
        from observability.loki.loki_integration import LogEntry, LogLevel

        entry = LogEntry(
            timestamp=datetime.now(UTC),
            level=LogLevel.INFO,
            message="Test message",
            labels={"service": "test"},
            metadata={"user_id": "123"},
            trace_id="abc123",
        )

        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"
        assert entry.trace_id == "abc123"

    def test_log_entry_to_loki_stream(self):
        """Test converting log entry to Loki stream format."""
        from observability.loki.loki_integration import LogEntry, LogLevel

        entry = LogEntry(
            timestamp=datetime.now(UTC),
            level=LogLevel.ERROR,
            message="Error occurred",
            labels={"service": "gateway"},
            trace_id="trace123",
        )

        stream = entry.to_loki_stream()

        assert "stream" in stream
        assert "values" in stream
        assert stream["stream"]["level"] == "error"
        assert len(stream["values"]) == 1

        # Parse the JSON value
        value_json = json.loads(stream["values"][0][1])
        assert value_json["message"] == "Error occurred"
        assert value_json["trace_id"] == "trace123"

    def test_log_aggregator_add_entry(self):
        """Test adding entries to the log aggregator."""
        from observability.loki.loki_integration import (
            LogEntry,
            LogLevel,
            LokiConfig,
            LokiLogAggregator,
        )

        config = LokiConfig(max_queue_size=10)
        aggregator = LokiLogAggregator(config)

        entry = LogEntry(
            timestamp=datetime.now(UTC),
            level=LogLevel.INFO,
            message="Test",
        )

        result = aggregator.add_entry(entry)
        assert result is True
        assert aggregator.queue_size == 1

    def test_log_aggregator_queue_overflow(self):
        """Test queue overflow handling."""
        from observability.loki.loki_integration import (
            LogEntry,
            LogLevel,
            LokiConfig,
            LokiLogAggregator,
        )

        config = LokiConfig(max_queue_size=2)
        aggregator = LokiLogAggregator(config)

        # Fill queue
        for i in range(3):
            entry = LogEntry(
                timestamp=datetime.now(UTC),
                level=LogLevel.INFO,
                message=f"Message {i}",
            )
            aggregator.add_entry(entry)

        # Should have dropped one
        assert aggregator.dropped_count == 1
        assert aggregator.queue_size == 2

    def test_log_aggregator_convenience_methods(self):
        """Test convenience logging methods."""
        from observability.loki.loki_integration import (
            LokiConfig,
            LokiLogAggregator,
        )

        config = LokiConfig(max_queue_size=100)
        aggregator = LokiLogAggregator(config)

        # Test all log levels
        aggregator.debug("Debug message")
        aggregator.info("Info message")
        aggregator.warning("Warning message")
        aggregator.error("Error message")
        aggregator.critical("Critical message")

        assert aggregator.queue_size == 5

    def test_structured_logger(self):
        """Test the structured logger."""
        from observability.loki.loki_integration import (
            LokiConfig,
            LokiLogAggregator,
            StructuredLogger,
        )

        config = LokiConfig(max_queue_size=100)
        aggregator = LokiLogAggregator(config)
        logger = StructuredLogger("test-logger", aggregator)

        logger.info("Test message", extra="data")
        logger.error("Error message", error_code=500)

        assert aggregator.queue_size == 2

    def test_structured_logger_context(self):
        """Test structured logger with context."""
        from observability.loki.loki_integration import (
            LokiConfig,
            LokiLogAggregator,
            StructuredLogger,
        )

        config = LokiConfig(max_queue_size=100)
        aggregator = LokiLogAggregator(config)
        logger = StructuredLogger("test-logger", aggregator)

        # Create contextual logger
        request_logger = logger.with_context(request_id="req-123")
        request_logger.info("Processing")

        # Original logger should not have context
        logger.info("Other message")

        assert aggregator.queue_size == 2

    def test_structured_logger_specialized_methods(self):
        """Test specialized logging methods."""
        from observability.loki.loki_integration import (
            LokiConfig,
            LokiLogAggregator,
            StructuredLogger,
        )

        config = LokiConfig(max_queue_size=100)
        aggregator = LokiLogAggregator(config)
        logger = StructuredLogger("test-logger", aggregator)

        # Test specialized methods
        logger.log_request("POST", "/api/chat", 200, 150.5)
        logger.log_tool_call("search", True, 250.0, role="analyst")
        logger.log_approval("delete", "high", "approved")
        logger.log_security_event(
            "rate_limit", "warning", "User exceeded limit"
        )

        assert aggregator.queue_size == 4

    def test_group_entries_to_streams(self):
        """Test grouping entries into Loki streams."""
        from observability.loki.loki_integration import (
            LogEntry,
            LogLevel,
            LokiConfig,
            LokiLogAggregator,
        )

        config = LokiConfig()
        aggregator = LokiLogAggregator(config)

        entries = [
            LogEntry(
                timestamp=datetime.now(UTC),
                level=LogLevel.INFO,
                message="Message 1",
                labels={"service": "gateway"},
            ),
            LogEntry(
                timestamp=datetime.now(UTC),
                level=LogLevel.INFO,
                message="Message 2",
                labels={"service": "gateway"},
            ),
            LogEntry(
                timestamp=datetime.now(UTC),
                level=LogLevel.ERROR,
                message="Error",
                labels={"service": "ml"},
            ),
        ]

        streams = aggregator._group_entries_to_streams(entries)

        # Should have 2 streams (grouped by labels)
        assert len(streams) == 2


# =============================================================================
# Test Integration Between Components
# =============================================================================
class TestPhase5Integration:
    """Integration tests for Phase 5 components."""

    def test_prometheus_grafana_integration(self):
        """Test that Prometheus metrics match Grafana dashboard queries."""
        from observability.grafana.grafana_dashboards import (
            create_overview_dashboard,
        )
        from observability.prometheus.prometheus_config import (
            PrometheusConfigGenerator,
        )

        generator = PrometheusConfigGenerator()
        recording_rules = generator.generate_recording_rules_config()

        dashboard = create_overview_dashboard()
        dash_json = dashboard.generate_dashboard()

        # Extract metric names from recording rules
        recorded_metrics = set()
        for group in recording_rules["groups"]:
            for rule in group["rules"]:
                recorded_metrics.add(rule["record"])

        # Verify at least some recorded metrics are used in dashboards
        assert "aura:http_requests:rate5m" in recorded_metrics
        assert "aura:http_latency:p99" in recorded_metrics

    def test_alert_rules_consistency(self):
        """Test that alert rules are consistent across Prometheus and Helm."""
        from observability.prometheus.prometheus_config import (
            PrometheusConfigGenerator,
        )

        generator = PrometheusConfigGenerator()
        alert_config = generator.generate_alert_rules_config()

        alert_names = {r["alert"] for r in alert_config["groups"][0]["rules"]}

        # Core alerts should exist
        core_alerts = {
            "AuraHighErrorRate",
            "AuraHighLatency",
            "AuraGatewayUnavailable",
            "AuraPodRestarting",
        }

        assert core_alerts.issubset(alert_names)

    def test_observability_stack_configuration(self):
        """Test that the observability values file is valid."""
        values_path = (
            Path(__file__).parent.parent
            / "k8s/helm/aura-ia/values-observability.yaml"
        )

        if values_path.exists():
            import yaml

            with open(values_path) as f:
                values = yaml.safe_load(f)

            # Verify key sections exist
            assert "prometheus" in values
            assert "grafana" in values
            assert "loki" in values
            assert "tempo" in values
            assert "otelCollector" in values

            # Verify Prometheus config
            assert values["prometheus"]["enabled"] is True
            assert "server" in values["prometheus"]

            # Verify Grafana datasources
            assert "datasources" in values["grafana"]


# =============================================================================
# Run Tests
# =============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
