"""
Grafana Dashboard Generator for Aura IA MCP.

Generates Grafana dashboard JSON configurations with panels
for monitoring all Aura IA services.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PanelType(Enum):
    """Types of Grafana panels."""

    GRAPH = "graph"
    GAUGE = "gauge"
    STAT = "stat"
    TABLE = "table"
    HEATMAP = "heatmap"
    LOGS = "logs"
    TIMESERIES = "timeseries"
    BAR_GAUGE = "bargauge"
    PIE_CHART = "piechart"


class DataSource(Enum):
    """Available data sources."""

    PROMETHEUS = "Prometheus"
    LOKI = "Loki"
    JAEGER = "Jaeger"
    TEMPO = "Tempo"


@dataclass
class GrafanaPanel:
    """Configuration for a Grafana panel."""

    title: str
    panel_type: PanelType
    targets: list[dict[str, Any]]
    datasource: DataSource = DataSource.PROMETHEUS
    description: str = ""
    unit: str = ""
    grid_pos: dict[str, int] = field(
        default_factory=lambda: {"x": 0, "y": 0, "w": 12, "h": 8}
    )
    thresholds: list[dict[str, Any]] = field(default_factory=list)
    field_config: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def to_panel(self, panel_id: int) -> dict[str, Any]:
        """Generate Grafana panel JSON."""
        panel: dict[str, Any] = {
            "id": panel_id,
            "type": self.panel_type.value,
            "title": self.title,
            "description": self.description,
            "datasource": {"type": "prometheus", "uid": "${DS_PROMETHEUS}"},
            "gridPos": self.grid_pos,
            "targets": self.targets,
        }

        if self.field_config:
            panel["fieldConfig"] = self.field_config
        else:
            panel["fieldConfig"] = {
                "defaults": {
                    "unit": self.unit,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": self.thresholds
                        or [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 70},
                            {"color": "red", "value": 90},
                        ],
                    },
                },
                "overrides": [],
            }

        if self.options:
            panel["options"] = self.options

        return panel


@dataclass
class GrafanaRow:
    """Configuration for a Grafana row."""

    title: str
    collapsed: bool = False
    panels: list[GrafanaPanel] = field(default_factory=list)


class GrafanaDashboardGenerator:
    """Generator for Grafana dashboards."""

    def __init__(
        self,
        title: str,
        uid: str | None = None,
        tags: list[str] | None = None,
        refresh: str = "30s",
    ):
        self.title = title
        self.uid = uid or str(uuid.uuid4())[:8]
        self.tags = tags or ["aura-ia", "mcp"]
        self.refresh = refresh
        self._rows: list[GrafanaRow] = []
        self._panels: list[GrafanaPanel] = []
        self._panel_id_counter = 1

    def add_row(self, row: GrafanaRow) -> None:
        """Add a row with panels."""
        self._rows.append(row)

    def add_panel(self, panel: GrafanaPanel) -> None:
        """Add a standalone panel."""
        self._panels.append(panel)

    def generate_dashboard(self) -> dict[str, Any]:
        """Generate complete Grafana dashboard JSON."""
        all_panels: list[dict[str, Any]] = []
        y_pos = 0

        # Add row panels
        for row in self._rows:
            # Add row header
            row_panel = {
                "id": self._panel_id_counter,
                "type": "row",
                "title": row.title,
                "collapsed": row.collapsed,
                "gridPos": {"x": 0, "y": y_pos, "w": 24, "h": 1},
                "panels": [],
            }
            self._panel_id_counter += 1
            y_pos += 1

            # Add panels in the row
            x_pos = 0
            row_height = 0
            for panel in row.panels:
                panel.grid_pos = {
                    "x": x_pos,
                    "y": y_pos,
                    "w": panel.grid_pos.get("w", 12),
                    "h": panel.grid_pos.get("h", 8),
                }
                all_panels.append(panel.to_panel(self._panel_id_counter))
                self._panel_id_counter += 1
                x_pos += panel.grid_pos["w"]
                row_height = max(row_height, panel.grid_pos["h"])
                if x_pos >= 24:
                    x_pos = 0
                    y_pos += row_height
                    row_height = 0

            all_panels.append(row_panel)
            y_pos += row_height

        # Add standalone panels
        for panel in self._panels:
            all_panels.append(panel.to_panel(self._panel_id_counter))
            self._panel_id_counter += 1

        dashboard = {
            "id": None,
            "uid": self.uid,
            "title": self.title,
            "tags": self.tags,
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 1,
            "refresh": self.refresh,
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 1,
            "links": [],
            "liveNow": False,
            "panels": all_panels,
            "templating": {
                "list": [
                    {
                        "name": "DS_PROMETHEUS",
                        "type": "datasource",
                        "query": "prometheus",
                        "current": {
                            "selected": False,
                            "text": "Prometheus",
                            "value": "Prometheus",
                        },
                        "hide": 0,
                    },
                    {
                        "name": "namespace",
                        "type": "query",
                        "datasource": {
                            "type": "prometheus",
                            "uid": "${DS_PROMETHEUS}",
                        },
                        "query": "label_values(namespace)",
                        "current": {
                            "selected": True,
                            "text": "aura-ia",
                            "value": "aura-ia",
                        },
                        "hide": 0,
                    },
                ]
            },
            "time": {"from": "now-1h", "to": "now"},
            "timepicker": {
                "refresh_intervals": [
                    "5s",
                    "10s",
                    "30s",
                    "1m",
                    "5m",
                    "15m",
                    "30m",
                    "1h",
                ],
                "time_options": [
                    "5m",
                    "15m",
                    "1h",
                    "6h",
                    "12h",
                    "24h",
                    "2d",
                    "7d",
                    "30d",
                ],
            },
            "annotations": {
                "list": [
                    {
                        "builtIn": 1,
                        "datasource": {
                            "type": "grafana",
                            "uid": "-- Grafana --",
                        },
                        "enable": True,
                        "hide": True,
                        "iconColor": "rgba(0, 211, 255, 1)",
                        "name": "Annotations & Alerts",
                        "type": "dashboard",
                    }
                ]
            },
        }

        return dashboard

    def export_to_file(self, output_path: Path) -> None:
        """Export dashboard to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(self.generate_dashboard(), f, indent=2)


def create_gateway_dashboard() -> GrafanaDashboardGenerator:
    """Create the Gateway monitoring dashboard."""
    dashboard = GrafanaDashboardGenerator(
        title="Aura IA Gateway",
        uid="aura-gateway",
        tags=["aura-ia", "gateway", "mcp"],
    )

    # Overview row
    overview_row = GrafanaRow(title="Overview")
    overview_row.panels.extend(
        [
            GrafanaPanel(
                title="Request Rate",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": 'sum(rate(http_requests_total{service="gateway"}[5m]))',
                        "legendFormat": "Requests/sec",
                        "refId": "A",
                    }
                ],
                unit="reqps",
                grid_pos={"w": 6, "h": 4},
            ),
            GrafanaPanel(
                title="Error Rate",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": 'sum(rate(http_requests_total{service="gateway",status=~"5.."}[5m])) / sum(rate(http_requests_total{service="gateway"}[5m])) * 100',
                        "legendFormat": "Error %",
                        "refId": "A",
                    }
                ],
                unit="percent",
                grid_pos={"w": 6, "h": 4},
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 1},
                    {"color": "red", "value": 5},
                ],
            ),
            GrafanaPanel(
                title="P99 Latency",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="gateway"}[5m])) by (le))',
                        "legendFormat": "P99",
                        "refId": "A",
                    }
                ],
                unit="s",
                grid_pos={"w": 6, "h": 4},
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 1},
                    {"color": "red", "value": 2},
                ],
            ),
            GrafanaPanel(
                title="Active Connections",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": "sum(aura_gateway_active_connections)",
                        "legendFormat": "Connections",
                        "refId": "A",
                    }
                ],
                grid_pos={"w": 6, "h": 4},
            ),
        ]
    )
    dashboard.add_row(overview_row)

    # Latency row
    latency_row = GrafanaRow(title="Latency")
    latency_row.panels.extend(
        [
            GrafanaPanel(
                title="Request Latency Distribution",
                panel_type=PanelType.HEATMAP,
                targets=[
                    {
                        "expr": 'sum(rate(http_request_duration_seconds_bucket{service="gateway"}[1m])) by (le)',
                        "legendFormat": "{{le}}",
                        "refId": "A",
                        "format": "heatmap",
                    }
                ],
                grid_pos={"w": 12, "h": 8},
            ),
            GrafanaPanel(
                title="Latency Percentiles",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": 'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{service="gateway"}[5m])) by (le))',
                        "legendFormat": "P50",
                        "refId": "A",
                    },
                    {
                        "expr": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{service="gateway"}[5m])) by (le))',
                        "legendFormat": "P95",
                        "refId": "B",
                    },
                    {
                        "expr": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="gateway"}[5m])) by (le))',
                        "legendFormat": "P99",
                        "refId": "C",
                    },
                ],
                unit="s",
                grid_pos={"w": 12, "h": 8},
            ),
        ]
    )
    dashboard.add_row(latency_row)

    # Traffic row
    traffic_row = GrafanaRow(title="Traffic")
    traffic_row.panels.extend(
        [
            GrafanaPanel(
                title="Requests by Status",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": 'sum(rate(http_requests_total{service="gateway"}[5m])) by (status)',
                        "legendFormat": "{{status}}",
                        "refId": "A",
                    }
                ],
                unit="reqps",
                grid_pos={"w": 12, "h": 8},
            ),
            GrafanaPanel(
                title="Requests by Endpoint",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": 'topk(10, sum(rate(http_requests_total{service="gateway"}[5m])) by (path))',
                        "legendFormat": "{{path}}",
                        "refId": "A",
                    }
                ],
                unit="reqps",
                grid_pos={"w": 12, "h": 8},
            ),
        ]
    )
    dashboard.add_row(traffic_row)

    return dashboard


def create_ml_backend_dashboard() -> GrafanaDashboardGenerator:
    """Create the ML Backend monitoring dashboard."""
    dashboard = GrafanaDashboardGenerator(
        title="Aura IA ML Backend",
        uid="aura-ml",
        tags=["aura-ia", "ml", "backend"],
    )

    # Overview row
    overview_row = GrafanaRow(title="Overview")
    overview_row.panels.extend(
        [
            GrafanaPanel(
                title="Predictions/sec",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": "sum(rate(aura_ml_predictions_total[5m]))",
                        "legendFormat": "Predictions",
                        "refId": "A",
                    }
                ],
                unit="ops",
                grid_pos={"w": 6, "h": 4},
            ),
            GrafanaPanel(
                title="Queue Depth",
                panel_type=PanelType.GAUGE,
                targets=[
                    {
                        "expr": "aura_ml_queue_depth",
                        "legendFormat": "Queue",
                        "refId": "A",
                    }
                ],
                grid_pos={"w": 6, "h": 4},
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 50},
                    {"color": "red", "value": 100},
                ],
            ),
            GrafanaPanel(
                title="Inference Latency (P95)",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(aura_ml_inference_duration_seconds_bucket[5m])) by (le))",
                        "legendFormat": "P95",
                        "refId": "A",
                    }
                ],
                unit="s",
                grid_pos={"w": 6, "h": 4},
            ),
            GrafanaPanel(
                title="Model Memory Usage",
                panel_type=PanelType.GAUGE,
                targets=[
                    {
                        "expr": "aura_ml_model_memory_bytes / (1024*1024*1024)",
                        "legendFormat": "Memory GB",
                        "refId": "A",
                    }
                ],
                unit="decgbytes",
                grid_pos={"w": 6, "h": 4},
            ),
        ]
    )
    dashboard.add_row(overview_row)

    # Model Performance row
    model_row = GrafanaRow(title="Model Performance")
    model_row.panels.extend(
        [
            GrafanaPanel(
                title="Inference Latency by Model",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(aura_ml_inference_duration_seconds_bucket[5m])) by (le, model))",
                        "legendFormat": "{{model}}",
                        "refId": "A",
                    }
                ],
                unit="s",
                grid_pos={"w": 12, "h": 8},
            ),
            GrafanaPanel(
                title="Batch Size Distribution",
                panel_type=PanelType.HEATMAP,
                targets=[
                    {
                        "expr": "sum(rate(aura_ml_batch_size_bucket[5m])) by (le)",
                        "legendFormat": "{{le}}",
                        "refId": "A",
                        "format": "heatmap",
                    }
                ],
                grid_pos={"w": 12, "h": 8},
            ),
        ]
    )
    dashboard.add_row(model_row)

    # Dual Model Engine row
    dual_model_row = GrafanaRow(title="Dual Model Engine")
    dual_model_row.panels.extend(
        [
            GrafanaPanel(
                title="Debate Sessions",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": "rate(aura_debate_sessions_total[5m])",
                        "legendFormat": "Sessions/sec",
                        "refId": "A",
                    }
                ],
                grid_pos={"w": 8, "h": 8},
            ),
            GrafanaPanel(
                title="Consensus Rate",
                panel_type=PanelType.GAUGE,
                targets=[
                    {
                        "expr": "sum(aura_debate_consensus_reached_total) / sum(aura_debate_sessions_total) * 100",
                        "legendFormat": "Consensus %",
                        "refId": "A",
                    }
                ],
                unit="percent",
                grid_pos={"w": 8, "h": 8},
            ),
            GrafanaPanel(
                title="Average Debate Rounds",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": "avg(aura_debate_rounds_total)",
                        "legendFormat": "Rounds",
                        "refId": "A",
                    }
                ],
                grid_pos={"w": 8, "h": 8},
            ),
        ]
    )
    dashboard.add_row(dual_model_row)

    return dashboard


def create_rag_dashboard() -> GrafanaDashboardGenerator:
    """Create the RAG/Qdrant monitoring dashboard."""
    dashboard = GrafanaDashboardGenerator(
        title="Aura IA RAG Service",
        uid="aura-rag",
        tags=["aura-ia", "rag", "qdrant"],
    )

    # Overview row
    overview_row = GrafanaRow(title="Overview")
    overview_row.panels.extend(
        [
            GrafanaPanel(
                title="Query Rate",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": "sum(rate(aura_rag_queries_total[5m]))",
                        "legendFormat": "Queries/sec",
                        "refId": "A",
                    }
                ],
                unit="ops",
                grid_pos={"w": 6, "h": 4},
            ),
            GrafanaPanel(
                title="Cache Hit Rate",
                panel_type=PanelType.GAUGE,
                targets=[
                    {
                        "expr": "sum(rate(aura_rag_cache_hits_total[5m])) / sum(rate(aura_rag_queries_total[5m])) * 100",
                        "legendFormat": "Cache Hit %",
                        "refId": "A",
                    }
                ],
                unit="percent",
                grid_pos={"w": 6, "h": 4},
                thresholds=[
                    {"color": "red", "value": None},
                    {"color": "yellow", "value": 50},
                    {"color": "green", "value": 80},
                ],
            ),
            GrafanaPanel(
                title="Query Latency (P95)",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(aura_rag_query_duration_seconds_bucket[5m])) by (le))",
                        "legendFormat": "P95",
                        "refId": "A",
                    }
                ],
                unit="s",
                grid_pos={"w": 6, "h": 4},
            ),
            GrafanaPanel(
                title="Index Size",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": "aura_rag_index_vectors_total",
                        "legendFormat": "Vectors",
                        "refId": "A",
                    }
                ],
                grid_pos={"w": 6, "h": 4},
            ),
        ]
    )
    dashboard.add_row(overview_row)

    # Query Performance row
    query_row = GrafanaRow(title="Query Performance")
    query_row.panels.extend(
        [
            GrafanaPanel(
                title="Query Latency Distribution",
                panel_type=PanelType.HEATMAP,
                targets=[
                    {
                        "expr": "sum(rate(aura_rag_query_duration_seconds_bucket[1m])) by (le)",
                        "legendFormat": "{{le}}",
                        "refId": "A",
                        "format": "heatmap",
                    }
                ],
                grid_pos={"w": 12, "h": 8},
            ),
            GrafanaPanel(
                title="Results per Query",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": "avg(aura_rag_results_per_query)",
                        "legendFormat": "Avg Results",
                        "refId": "A",
                    }
                ],
                grid_pos={"w": 12, "h": 8},
            ),
        ]
    )
    dashboard.add_row(query_row)

    # Qdrant Health row
    qdrant_row = GrafanaRow(title="Qdrant Health")
    qdrant_row.panels.extend(
        [
            GrafanaPanel(
                title="Qdrant Memory Usage",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": "qdrant_memory_bytes",
                        "legendFormat": "Memory",
                        "refId": "A",
                    }
                ],
                unit="bytes",
                grid_pos={"w": 8, "h": 8},
            ),
            GrafanaPanel(
                title="Qdrant CPU Usage",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": "rate(qdrant_cpu_seconds_total[5m])",
                        "legendFormat": "CPU",
                        "refId": "A",
                    }
                ],
                unit="percentunit",
                grid_pos={"w": 8, "h": 8},
            ),
            GrafanaPanel(
                title="Collections",
                panel_type=PanelType.TABLE,
                targets=[
                    {
                        "expr": "qdrant_collection_vectors_count",
                        "legendFormat": "{{collection}}",
                        "refId": "A",
                        "format": "table",
                    }
                ],
                grid_pos={"w": 8, "h": 8},
            ),
        ]
    )
    dashboard.add_row(qdrant_row)

    return dashboard


def create_overview_dashboard() -> GrafanaDashboardGenerator:
    """Create the main overview dashboard."""
    dashboard = GrafanaDashboardGenerator(
        title="Aura IA Overview",
        uid="aura-overview",
        tags=["aura-ia", "overview"],
    )

    # System Health row
    health_row = GrafanaRow(title="System Health")
    health_row.panels.extend(
        [
            GrafanaPanel(
                title="Services Up",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": 'sum(up{namespace="aura-ia"})',
                        "legendFormat": "Services",
                        "refId": "A",
                    }
                ],
                grid_pos={"w": 4, "h": 4},
            ),
            GrafanaPanel(
                title="Total Request Rate",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": 'sum(rate(http_requests_total{namespace="aura-ia"}[5m]))',
                        "legendFormat": "Req/s",
                        "refId": "A",
                    }
                ],
                unit="reqps",
                grid_pos={"w": 4, "h": 4},
            ),
            GrafanaPanel(
                title="Error Rate",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": 'sum(rate(http_requests_total{namespace="aura-ia",status=~"5.."}[5m])) / sum(rate(http_requests_total{namespace="aura-ia"}[5m])) * 100',
                        "legendFormat": "Error %",
                        "refId": "A",
                    }
                ],
                unit="percent",
                grid_pos={"w": 4, "h": 4},
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 1},
                    {"color": "red", "value": 5},
                ],
            ),
            GrafanaPanel(
                title="Avg Latency",
                panel_type=PanelType.STAT,
                targets=[
                    {
                        "expr": 'avg(histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{namespace="aura-ia"}[5m])) by (le, service)))',
                        "legendFormat": "P95",
                        "refId": "A",
                    }
                ],
                unit="s",
                grid_pos={"w": 4, "h": 4},
            ),
            GrafanaPanel(
                title="CPU Usage",
                panel_type=PanelType.GAUGE,
                targets=[
                    {
                        "expr": 'avg(rate(container_cpu_usage_seconds_total{namespace="aura-ia"}[5m])) * 100',
                        "legendFormat": "CPU %",
                        "refId": "A",
                    }
                ],
                unit="percent",
                grid_pos={"w": 4, "h": 4},
            ),
            GrafanaPanel(
                title="Memory Usage",
                panel_type=PanelType.GAUGE,
                targets=[
                    {
                        "expr": 'avg(container_memory_usage_bytes{namespace="aura-ia"} / container_spec_memory_limit_bytes) * 100',
                        "legendFormat": "Memory %",
                        "refId": "A",
                    }
                ],
                unit="percent",
                grid_pos={"w": 4, "h": 4},
            ),
        ]
    )
    dashboard.add_row(health_row)

    # Service Status row
    service_row = GrafanaRow(title="Service Status")
    service_row.panels.extend(
        [
            GrafanaPanel(
                title="Service Request Rate",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": 'sum(rate(http_requests_total{namespace="aura-ia"}[5m])) by (service)',
                        "legendFormat": "{{service}}",
                        "refId": "A",
                    }
                ],
                unit="reqps",
                grid_pos={"w": 12, "h": 8},
            ),
            GrafanaPanel(
                title="Service Latency (P95)",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{namespace="aura-ia"}[5m])) by (le, service))',
                        "legendFormat": "{{service}}",
                        "refId": "A",
                    }
                ],
                unit="s",
                grid_pos={"w": 12, "h": 8},
            ),
        ]
    )
    dashboard.add_row(service_row)

    # Resource Usage row
    resource_row = GrafanaRow(title="Resource Usage")
    resource_row.panels.extend(
        [
            GrafanaPanel(
                title="CPU by Service",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": 'sum(rate(container_cpu_usage_seconds_total{namespace="aura-ia"}[5m])) by (container)',
                        "legendFormat": "{{container}}",
                        "refId": "A",
                    }
                ],
                unit="percentunit",
                grid_pos={"w": 12, "h": 8},
            ),
            GrafanaPanel(
                title="Memory by Service",
                panel_type=PanelType.TIMESERIES,
                targets=[
                    {
                        "expr": 'sum(container_memory_usage_bytes{namespace="aura-ia"}) by (container)',
                        "legendFormat": "{{container}}",
                        "refId": "A",
                    }
                ],
                unit="bytes",
                grid_pos={"w": 12, "h": 8},
            ),
        ]
    )
    dashboard.add_row(resource_row)

    return dashboard


def export_all_dashboards(output_dir: Path) -> dict[str, Path]:
    """Export all dashboards to JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: dict[str, Path] = {}

    dashboards = [
        ("overview", create_overview_dashboard()),
        ("gateway", create_gateway_dashboard()),
        ("ml_backend", create_ml_backend_dashboard()),
        ("rag", create_rag_dashboard()),
    ]

    for name, dashboard in dashboards:
        output_path = output_dir / f"aura-ia-{name}.json"
        dashboard.export_to_file(output_path)
        exported[name] = output_path

    return exported


if __name__ == "__main__":
    # Export all dashboards
    export_path = Path("observability/grafana/dashboards")
    exported = export_all_dashboards(export_path)
    print(f"Exported {len(exported)} dashboards:")
    for name, path in exported.items():
        print(f"  - {name}: {path}")
