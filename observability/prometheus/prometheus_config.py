"""
Prometheus Configuration Generator for Aura IA MCP.

Generates Prometheus configuration including scrape configs,
alerting rules, and ServiceMonitor definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class ServiceType(Enum):
    """Types of services to monitor."""

    GATEWAY = "gateway"
    ML_BACKEND = "ml_backend"
    RAG = "rag"
    DASHBOARD = "dashboard"
    ROLE_ENGINE = "role_engine"


@dataclass
class ScrapeTarget:
    """Configuration for a Prometheus scrape target."""

    job_name: str
    service_type: ServiceType
    port: int
    path: str = "/metrics"
    interval: str = "15s"
    timeout: str = "10s"
    scheme: str = "http"
    labels: dict[str, str] = field(default_factory=dict)
    relabel_configs: list[dict[str, Any]] = field(default_factory=list)

    def to_scrape_config(self, namespace: str = "aura-ia") -> dict[str, Any]:
        """Generate Prometheus scrape configuration."""
        config: dict[str, Any] = {
            "job_name": self.job_name,
            "scrape_interval": self.interval,
            "scrape_timeout": self.timeout,
            "metrics_path": self.path,
            "scheme": self.scheme,
            "kubernetes_sd_configs": [
                {"role": "pod", "namespaces": {"names": [namespace]}}
            ],
            "relabel_configs": [
                {
                    "source_labels": ["__meta_kubernetes_pod_label_app"],
                    "action": "keep",
                    "regex": f"aura-ia-{self.service_type.value.replace('_', '-')}",
                },
                {
                    "source_labels": ["__meta_kubernetes_namespace"],
                    "target_label": "namespace",
                },
                {
                    "source_labels": ["__meta_kubernetes_pod_name"],
                    "target_label": "pod",
                },
                {
                    "source_labels": ["__meta_kubernetes_pod_label_app"],
                    "target_label": "app",
                },
            ],
        }

        # Add custom relabel configs
        if self.relabel_configs:
            config["relabel_configs"].extend(self.relabel_configs)

        # Add static labels
        if self.labels:
            for key, value in self.labels.items():
                config["relabel_configs"].append(
                    {"target_label": key, "replacement": value}
                )

        return config


@dataclass
class AlertRule:
    """Configuration for a Prometheus alerting rule."""

    name: str
    expr: str
    duration: str
    severity: str
    summary: str
    description: str
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def to_rule(self) -> dict[str, Any]:
        """Generate Prometheus alerting rule."""
        rule: dict[str, Any] = {
            "alert": self.name,
            "expr": self.expr,
            "for": self.duration,
            "labels": {"severity": self.severity, **self.labels},
            "annotations": {
                "summary": self.summary,
                "description": self.description,
                **self.annotations,
            },
        }
        return rule


@dataclass
class RecordingRule:
    """Configuration for a Prometheus recording rule."""

    record: str
    expr: str
    labels: dict[str, str] = field(default_factory=dict)

    def to_rule(self) -> dict[str, Any]:
        """Generate Prometheus recording rule."""
        rule: dict[str, Any] = {"record": self.record, "expr": self.expr}
        if self.labels:
            rule["labels"] = self.labels
        return rule


class PrometheusConfigGenerator:
    """Generator for Prometheus configurations."""

    # Canonical ports from PRD
    CANONICAL_PORTS = {
        ServiceType.GATEWAY: 9200,
        ServiceType.ML_BACKEND: 9201,
        ServiceType.RAG: 9202,
        ServiceType.DASHBOARD: 9205,
        ServiceType.ROLE_ENGINE: 9206,
    }

    def __init__(self, namespace: str = "aura-ia"):
        self.namespace = namespace
        self._scrape_targets: list[ScrapeTarget] = []
        self._alert_rules: list[AlertRule] = []
        self._recording_rules: list[RecordingRule] = []
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default scrape targets and rules."""
        # Default scrape targets for all Aura IA services
        for service_type, port in self.CANONICAL_PORTS.items():
            self._scrape_targets.append(
                ScrapeTarget(
                    job_name=f"aura-ia-{service_type.value.replace('_', '-')}",
                    service_type=service_type,
                    port=port,
                    labels={"service": service_type.value},
                )
            )

        # Default alerting rules
        self._initialize_alert_rules()

        # Default recording rules
        self._initialize_recording_rules()

    def _initialize_alert_rules(self) -> None:
        """Initialize default alerting rules."""
        # High error rate alert
        self._alert_rules.append(
            AlertRule(
                name="AuraHighErrorRate",
                expr='sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.01',
                duration="5m",
                severity="critical",
                summary="High error rate detected in Aura IA",
                description='Error rate is above 1% for the last 5 minutes. Current value: {{ $value | printf "%.2f" }}%',
            )
        )

        # High latency alert
        self._alert_rules.append(
            AlertRule(
                name="AuraHighLatency",
                expr="histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)) > 2",
                duration="5m",
                severity="warning",
                summary="High P99 latency in Aura IA",
                description='P99 latency is above 2 seconds for {{ $labels.service }}. Current value: {{ $value | printf "%.2f" }}s',
            )
        )

        # Pod restart alert
        self._alert_rules.append(
            AlertRule(
                name="AuraPodRestarting",
                expr='increase(kube_pod_container_status_restarts_total{namespace="aura-ia"}[1h]) > 3',
                duration="10m",
                severity="warning",
                summary="Pod restarting frequently",
                description="Pod {{ $labels.pod }} has restarted more than 3 times in the last hour",
            )
        )

        # Gateway unavailable alert
        self._alert_rules.append(
            AlertRule(
                name="AuraGatewayUnavailable",
                expr='up{job="aura-ia-gateway"} == 0',
                duration="2m",
                severity="critical",
                summary="Aura IA Gateway is unavailable",
                description="The Aura IA Gateway has been down for more than 2 minutes",
            )
        )

        # ML Backend queue depth alert
        self._alert_rules.append(
            AlertRule(
                name="AuraMLQueueDepthHigh",
                expr="aura_ml_queue_depth > 100",
                duration="5m",
                severity="warning",
                summary="ML Backend queue is filling up",
                description="ML request queue depth is {{ $value }}, above threshold of 100",
            )
        )

        # RAG query failure rate
        self._alert_rules.append(
            AlertRule(
                name="AuraRAGQueryFailures",
                expr="rate(aura_rag_query_failures_total[5m]) / rate(aura_rag_queries_total[5m]) > 0.1",
                duration="5m",
                severity="warning",
                summary="RAG query failure rate is high",
                description='RAG query failure rate is above 10%. Current value: {{ $value | printf "%.2f" }}%',
            )
        )

        # Memory pressure alert
        self._alert_rules.append(
            AlertRule(
                name="AuraMemoryPressure",
                expr='container_memory_usage_bytes{namespace="aura-ia"} / container_spec_memory_limit_bytes > 0.85',
                duration="10m",
                severity="warning",
                summary="Container memory usage is high",
                description='Container {{ $labels.container }} is using {{ $value | printf "%.0f" }}% of its memory limit',
            )
        )

        # CPU throttling alert
        self._alert_rules.append(
            AlertRule(
                name="AuraCPUThrottling",
                expr='rate(container_cpu_cfs_throttled_seconds_total{namespace="aura-ia"}[5m]) > 0.1',
                duration="10m",
                severity="warning",
                summary="Container is being CPU throttled",
                description='Container {{ $labels.container }} is being throttled for {{ $value | printf "%.2f" }} seconds per second',
            )
        )

        # Role Engine approval queue
        self._alert_rules.append(
            AlertRule(
                name="AuraApprovalQueueBacklog",
                expr="aura_approval_pending_count > 50",
                duration="15m",
                severity="warning",
                summary="Approval queue backlog is growing",
                description="There are {{ $value }} pending approvals waiting for review",
            )
        )

        # Certificate expiry alert
        self._alert_rules.append(
            AlertRule(
                name="AuraCertificateExpiringSoon",
                expr="(cert_expiry_timestamp_seconds - time()) / 86400 < 30",
                duration="1h",
                severity="warning",
                summary="TLS certificate expiring soon",
                description='Certificate for {{ $labels.domain }} expires in {{ $value | printf "%.0f" }} days',
            )
        )

    def _initialize_recording_rules(self) -> None:
        """Initialize recording rules for commonly used metrics."""
        # Request rate
        self._recording_rules.append(
            RecordingRule(
                record="aura:http_requests:rate5m",
                expr="sum(rate(http_requests_total[5m])) by (service, method, status)",
            )
        )

        # Error rate
        self._recording_rules.append(
            RecordingRule(
                record="aura:http_errors:rate5m",
                expr='sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)',
            )
        )

        # P50 latency
        self._recording_rules.append(
            RecordingRule(
                record="aura:http_latency:p50",
                expr="histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))",
            )
        )

        # P95 latency
        self._recording_rules.append(
            RecordingRule(
                record="aura:http_latency:p95",
                expr="histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))",
            )
        )

        # P99 latency
        self._recording_rules.append(
            RecordingRule(
                record="aura:http_latency:p99",
                expr="histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))",
            )
        )

        # ML throughput
        self._recording_rules.append(
            RecordingRule(
                record="aura:ml_throughput:rate5m",
                expr="sum(rate(aura_ml_predictions_total[5m]))",
            )
        )

        # RAG query rate
        self._recording_rules.append(
            RecordingRule(
                record="aura:rag_queries:rate5m",
                expr="sum(rate(aura_rag_queries_total[5m]))",
            )
        )

    def add_scrape_target(self, target: ScrapeTarget) -> None:
        """Add a custom scrape target."""
        self._scrape_targets.append(target)

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add a custom alerting rule."""
        self._alert_rules.append(rule)

    def add_recording_rule(self, rule: RecordingRule) -> None:
        """Add a custom recording rule."""
        self._recording_rules.append(rule)

    def generate_prometheus_config(self) -> dict[str, Any]:
        """Generate complete Prometheus configuration."""
        config = {
            "global": {
                "scrape_interval": "15s",
                "evaluation_interval": "15s",
                "external_labels": {
                    "cluster": "aura-ia",
                    "environment": "production",
                },
            },
            "alerting": {
                "alertmanagers": [
                    {"static_configs": [{"targets": ["alertmanager:9093"]}]}
                ]
            },
            "rule_files": ["/etc/prometheus/rules/*.yaml"],
            "scrape_configs": [
                target.to_scrape_config(self.namespace)
                for target in self._scrape_targets
            ],
        }
        return config

    def generate_alert_rules_config(self) -> dict[str, Any]:
        """Generate alerting rules configuration."""
        return {
            "groups": [
                {
                    "name": "aura-ia-alerts",
                    "interval": "30s",
                    "rules": [rule.to_rule() for rule in self._alert_rules],
                }
            ]
        }

    def generate_recording_rules_config(self) -> dict[str, Any]:
        """Generate recording rules configuration."""
        return {
            "groups": [
                {
                    "name": "aura-ia-recording-rules",
                    "interval": "30s",
                    "rules": [
                        rule.to_rule() for rule in self._recording_rules
                    ],
                }
            ]
        }

    def generate_service_monitor(
        self, service_type: ServiceType
    ) -> dict[str, Any]:
        """Generate Kubernetes ServiceMonitor for a service."""
        service_name = f"aura-ia-{service_type.value.replace('_', '-')}"
        return {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "ServiceMonitor",
            "metadata": {
                "name": service_name,
                "namespace": self.namespace,
                "labels": {"app": service_name, "release": "prometheus"},
            },
            "spec": {
                "selector": {"matchLabels": {"app": service_name}},
                "namespaceSelector": {"matchNames": [self.namespace]},
                "endpoints": [
                    {
                        "port": "metrics",
                        "path": "/metrics",
                        "interval": "15s",
                        "scrapeTimeout": "10s",
                    }
                ],
            },
        }

    def export_configs(self, output_dir: Path) -> dict[str, Path]:
        """Export all configurations to files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        exported_files: dict[str, Path] = {}

        # Prometheus main config
        prom_config = output_dir / "prometheus.yml"
        with prom_config.open("w", encoding="utf-8") as f:
            yaml.dump(
                self.generate_prometheus_config(), f, default_flow_style=False
            )
        exported_files["prometheus_config"] = prom_config

        # Alert rules
        alert_rules = output_dir / "alert_rules.yaml"
        with alert_rules.open("w", encoding="utf-8") as f:
            yaml.dump(
                self.generate_alert_rules_config(), f, default_flow_style=False
            )
        exported_files["alert_rules"] = alert_rules

        # Recording rules
        recording_rules = output_dir / "recording_rules.yaml"
        with recording_rules.open("w", encoding="utf-8") as f:
            yaml.dump(
                self.generate_recording_rules_config(),
                f,
                default_flow_style=False,
            )
        exported_files["recording_rules"] = recording_rules

        # ServiceMonitors
        sm_dir = output_dir / "servicemonitors"
        sm_dir.mkdir(exist_ok=True)
        for service_type in ServiceType:
            sm_file = sm_dir / f"{service_type.value}-servicemonitor.yaml"
            with sm_file.open("w", encoding="utf-8") as f:
                yaml.dump(
                    self.generate_service_monitor(service_type),
                    f,
                    default_flow_style=False,
                )
            exported_files[f"servicemonitor_{service_type.value}"] = sm_file

        return exported_files


# Convenience function for quick setup
def create_default_prometheus_config(
    namespace: str = "aura-ia",
) -> PrometheusConfigGenerator:
    """Create a pre-configured Prometheus config generator."""
    return PrometheusConfigGenerator(namespace=namespace)


if __name__ == "__main__":
    # Example usage
    generator = create_default_prometheus_config()

    # Add custom alert
    generator.add_alert_rule(
        AlertRule(
            name="CustomHighLoad",
            expr="avg(load_average_1m) > 10",
            duration="10m",
            severity="warning",
            summary="System load is very high",
            description="System load average is {{ $value }}",
        )
    )

    # Export to files
    export_path = Path("observability/prometheus/generated")
    exported = generator.export_configs(export_path)
    print(f"Exported {len(exported)} configuration files")
    for name, path in exported.items():
        print(f"  - {name}: {path}")
