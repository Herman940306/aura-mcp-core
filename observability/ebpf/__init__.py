"""
eBPF Observability Module for Aura IA MCP.

This module provides deep kernel-level observability through eBPF probes,
integrating with Pixie and Cilium Hubble for comprehensive network and
application monitoring.
"""

from .ebpf_integration import (
    CiliumHubbleIntegration,
    EBPFConfig,
    EBPFManager,
    EBPFProbe,
    EBPFProbeType,
    GILMonitor,
    PixieIntegration,
    get_ebpf_manager,
    init_ebpf,
)

__all__ = [
    "EBPFConfig",
    "EBPFProbe",
    "EBPFProbeType",
    "EBPFManager",
    "PixieIntegration",
    "CiliumHubbleIntegration",
    "GILMonitor",
    "get_ebpf_manager",
    "init_ebpf",
]
