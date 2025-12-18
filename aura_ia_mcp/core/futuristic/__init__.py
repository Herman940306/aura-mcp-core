"""
Futuristic Computing Module for Aura IA MCP.

This module provides next-generation compute capabilities including:
- Green Compute: Carbon-aware job scheduling
- WASM Sandbox: Secure plugin execution via WebAssembly
- Confidential Computing: Secure enclave execution

These features represent Phase 6 of the Aura IA roadmap.
"""

from .confidential_compute import (
    EnclaveConfig,
    EnclaveManager,
    EnclaveManifest,
    EnclaveType,
    GramineEnclave,
    SCONEEnclave,
    SecureEnclave,
    get_enclave_manager,
)
from .green_compute import (
    CarbonAwareScheduler,
    CarbonDataSource,
    CarbonIntensity,
    ElectricityMapsSource,
    JobPriority,
    JobState,
    ScheduledJob,
    WattTimeSource,
    get_carbon_scheduler,
)
from .wasm_sandbox import (
    PluginManifest,
    PluginState,
    WASMCapability,
    WASMConfig,
    WASMPlugin,
    WASMSandbox,
    get_wasm_sandbox,
)

__all__ = [
    # Green Compute
    "CarbonIntensity",
    "CarbonAwareScheduler",
    "ScheduledJob",
    "JobPriority",
    "JobState",
    "CarbonDataSource",
    "ElectricityMapsSource",
    "WattTimeSource",
    "get_carbon_scheduler",
    # WASM Sandbox
    "WASMConfig",
    "WASMPlugin",
    "WASMSandbox",
    "WASMCapability",
    "PluginManifest",
    "PluginState",
    "get_wasm_sandbox",
    # Confidential Computing
    "EnclaveConfig",
    "EnclaveType",
    "EnclaveManifest",
    "SecureEnclave",
    "GramineEnclave",
    "SCONEEnclave",
    "EnclaveManager",
    "get_enclave_manager",
]
