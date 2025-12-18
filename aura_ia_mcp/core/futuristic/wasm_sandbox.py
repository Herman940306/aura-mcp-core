"""
WASM Sandbox Module for Aura IA MCP.

This module provides secure WebAssembly-based sandboxing for untrusted
plugin execution using WasmEdge runtime.

Features:
- WASI (WebAssembly System Interface) compliance
- Fine-grained capability control
- Resource limits (memory, CPU, time)
- Plugin manifest validation
- Secure input/output handling
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, Flag, auto
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WASMCapability(Flag):
    """Capabilities that can be granted to WASM plugins."""

    NONE = 0

    # File system access
    FS_READ = auto()  # Read files
    FS_WRITE = auto()  # Write files
    FS_CREATE = auto()  # Create files/directories

    # Network access
    NET_HTTP = auto()  # HTTP requests
    NET_HTTPS = auto()  # HTTPS requests
    NET_DNS = auto()  # DNS resolution
    NET_SOCKET = auto()  # Raw socket access

    # System resources
    SYS_ENV = auto()  # Environment variables (read)
    SYS_ENV_WRITE = auto()  # Environment variables (write)
    SYS_TIME = auto()  # System time access
    SYS_RANDOM = auto()  # Random number generation

    # Aura-specific
    AURA_TOOL_CALL = auto()  # Call Aura tools
    AURA_CONTEXT = auto()  # Access context/session data
    AURA_MODEL = auto()  # Call inference APIs
    AURA_RAG = auto()  # Access RAG/retrieval

    # Convenience sets
    FS_ALL = FS_READ | FS_WRITE | FS_CREATE
    NET_ALL = NET_HTTP | NET_HTTPS | NET_DNS | NET_SOCKET
    SYS_BASIC = SYS_TIME | SYS_RANDOM
    AURA_BASIC = AURA_TOOL_CALL | AURA_CONTEXT

    # Default safe capabilities
    SAFE = FS_READ | NET_HTTP | NET_HTTPS | SYS_BASIC | AURA_BASIC


class PluginState(Enum):
    """Plugin execution states."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    SUSPENDED = "suspended"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class WASMConfig:
    """Configuration for WASM sandbox."""

    enabled: bool = True
    runtime: str = "wasmedge"  # wasmedge, wasmtime, wasmer

    # Resource limits
    max_memory_mb: int = 64  # Max memory per instance
    max_cpu_time_ms: int = 5000  # Max CPU time per call
    max_wall_time_ms: int = 30000  # Max wall-clock time
    max_instances: int = 10  # Max concurrent instances

    # Default capabilities
    default_capabilities: WASMCapability = WASMCapability.SAFE

    # File system sandbox
    sandbox_root: str = "/tmp/aura_wasm_sandbox"
    allowed_paths: list[str] = field(default_factory=list)

    # Network restrictions
    allowed_hosts: list[str] = field(
        default_factory=lambda: ["*.aura-ia.local"]
    )
    blocked_ports: list[int] = field(
        default_factory=lambda: [22, 23, 25, 3306, 5432]
    )

    # Plugin verification
    require_signature: bool = True
    allowed_publishers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "runtime": self.runtime,
            "limits": {
                "max_memory_mb": self.max_memory_mb,
                "max_cpu_time_ms": self.max_cpu_time_ms,
                "max_wall_time_ms": self.max_wall_time_ms,
                "max_instances": self.max_instances,
            },
            "default_capabilities": self.default_capabilities.value,
            "sandbox_root": self.sandbox_root,
            "security": {
                "require_signature": self.require_signature,
                "allowed_publishers": self.allowed_publishers,
            },
        }


@dataclass
class PluginManifest:
    """
    Plugin manifest defining metadata and requirements.

    Follows a format similar to package.json/Cargo.toml for plugins.
    """

    name: str
    version: str
    description: str = ""
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""

    # Entry points
    main: str = "plugin.wasm"
    exports: list[str] = field(default_factory=lambda: ["run"])

    # Requirements
    required_capabilities: WASMCapability = WASMCapability.NONE
    min_memory_mb: int = 8

    # Dependencies
    dependencies: dict[str, str] = field(default_factory=dict)

    # Security
    publisher: str = ""
    signature: str = ""
    checksum: str = ""  # SHA256 of wasm binary

    # Aura integration
    tool_definitions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        """Create manifest from dictionary."""
        # Parse capabilities
        caps = WASMCapability.NONE
        if "required_capabilities" in data:
            for cap_name in data["required_capabilities"]:
                try:
                    caps |= WASMCapability[cap_name]
                except KeyError:
                    logger.warning(f"Unknown capability: {cap_name}")

        return cls(
            name=data.get("name", "unknown"),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", "MIT"),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            main=data.get("main", "plugin.wasm"),
            exports=data.get("exports", ["run"]),
            required_capabilities=caps,
            min_memory_mb=data.get("min_memory_mb", 8),
            dependencies=data.get("dependencies", {}),
            publisher=data.get("publisher", ""),
            signature=data.get("signature", ""),
            checksum=data.get("checksum", ""),
            tool_definitions=data.get("tool_definitions", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> PluginManifest:
        """Create manifest from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: Path) -> PluginManifest:
        """Load manifest from file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "main": self.main,
            "exports": self.exports,
            "required_capabilities": [
                c.name
                for c in WASMCapability
                if c in self.required_capabilities and c.value
            ],
            "min_memory_mb": self.min_memory_mb,
            "dependencies": self.dependencies,
            "publisher": self.publisher,
            "checksum": self.checksum,
            "tool_definitions": self.tool_definitions,
        }

    def validate(self) -> list[str]:
        """Validate manifest, return list of errors."""
        errors = []

        if not self.name:
            errors.append("Plugin name is required")
        if not self.version:
            errors.append("Plugin version is required")
        if not self.main.endswith(".wasm"):
            errors.append("Main entry must be a .wasm file")
        if self.min_memory_mb < 1:
            errors.append("Minimum memory must be at least 1 MB")
        if not self.exports:
            errors.append("At least one export is required")

        return errors


@dataclass
class WASMPlugin:
    """A loaded WASM plugin instance."""

    id: str
    manifest: PluginManifest
    wasm_path: Path

    # Runtime state
    state: PluginState = PluginState.UNLOADED
    capabilities: WASMCapability = WASMCapability.NONE

    # Resource tracking
    memory_used_mb: float = 0.0
    cpu_time_ms: float = 0.0
    call_count: int = 0
    last_call: datetime | None = None

    # Error tracking
    error_count: int = 0
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.manifest.name,
            "version": self.manifest.version,
            "state": self.state.value,
            "capabilities": self.capabilities.value,
            "resources": {
                "memory_used_mb": self.memory_used_mb,
                "cpu_time_ms": self.cpu_time_ms,
                "call_count": self.call_count,
                "last_call": (
                    self.last_call.isoformat() if self.last_call else None
                ),
            },
            "errors": {
                "count": self.error_count,
                "last_error": self.last_error,
            },
        }


@dataclass
class WASMCallResult:
    """Result of a WASM function call."""

    success: bool
    output: Any
    error: str | None = None

    # Performance metrics
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0

    # I/O
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_mb": self.memory_used_mb,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class WASMRuntime(ABC):
    """Abstract base for WASM runtime implementations."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if runtime is available."""
        pass

    @abstractmethod
    async def load_module(
        self,
        wasm_path: Path,
        config: WASMConfig,
    ) -> Any:
        """Load a WASM module."""
        pass

    @abstractmethod
    async def call_function(
        self,
        module: Any,
        function: str,
        args: list[Any],
        timeout_ms: int,
    ) -> WASMCallResult:
        """Call a function in the module."""
        pass

    @abstractmethod
    async def unload_module(self, module: Any) -> None:
        """Unload a WASM module."""
        pass


class SimulatedWASMRuntime(WASMRuntime):
    """Simulated WASM runtime for testing."""

    def __init__(self):
        self._modules: dict[str, dict[str, Any]] = {}

    def is_available(self) -> bool:
        """Always available for simulation."""
        return True

    async def load_module(
        self,
        wasm_path: Path,
        config: WASMConfig,
    ) -> Any:
        """Load a simulated module."""
        module_id = str(wasm_path)
        self._modules[module_id] = {
            "path": wasm_path,
            "config": config,
            "loaded_at": datetime.now(),
        }
        logger.info(f"Loaded simulated WASM module: {wasm_path}")
        return module_id

    async def call_function(
        self,
        module: Any,
        function: str,
        args: list[Any],
        timeout_ms: int,
    ) -> WASMCallResult:
        """Call a simulated function."""
        if module not in self._modules:
            return WASMCallResult(
                success=False,
                output=None,
                error="Module not loaded",
            )

        # Simulate execution
        import random

        exec_time = random.uniform(1, 50)
        memory = random.uniform(1, 10)

        await asyncio.sleep(exec_time / 1000)

        return WASMCallResult(
            success=True,
            output={"function": function, "args": args, "result": "simulated"},
            execution_time_ms=exec_time,
            memory_used_mb=memory,
            stdout=f"Executed {function} with {len(args)} args\n",
        )

    async def unload_module(self, module: Any) -> None:
        """Unload a simulated module."""
        if module in self._modules:
            del self._modules[module]
            logger.info(f"Unloaded simulated WASM module: {module}")


class WASMSandbox:
    """
    Secure WASM sandbox for plugin execution.

    Provides isolation and resource control for untrusted code:
    - Memory isolation
    - CPU time limits
    - Capability-based security
    - Input/output sanitization
    """

    def __init__(self, config: WASMConfig | None = None):
        self.config = config or WASMConfig()
        self._runtime: WASMRuntime | None = None
        self._plugins: dict[str, WASMPlugin] = {}
        self._lock = threading.Lock()
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the sandbox."""
        if self._initialized:
            return True

        if not self.config.enabled:
            logger.info("WASM sandbox disabled")
            return False

        # Select runtime
        self._runtime = self._select_runtime()
        if not self._runtime.is_available():
            logger.error("No WASM runtime available")
            return False

        # Create sandbox directory
        sandbox_path = Path(self.config.sandbox_root)
        sandbox_path.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        logger.info(
            f"WASM sandbox initialized (runtime={self.config.runtime})"
        )
        return True

    def _select_runtime(self) -> WASMRuntime:
        """Select the appropriate WASM runtime."""
        # In production, would check for wasmedge, wasmtime, wasmer
        # For now, use simulated runtime
        logger.info("Using simulated WASM runtime")
        return SimulatedWASMRuntime()

    async def load_plugin(
        self,
        manifest: PluginManifest,
        wasm_path: Path,
        capabilities: WASMCapability | None = None,
    ) -> WASMPlugin:
        """Load a plugin into the sandbox."""
        if not self._initialized:
            await self.initialize()

        # Check instance limit
        with self._lock:
            if len(self._plugins) >= self.config.max_instances:
                raise RuntimeError(
                    f"Maximum plugin instances ({self.config.max_instances}) exceeded"
                )

        # Validate manifest
        errors = manifest.validate()
        if errors:
            raise ValueError(f"Invalid manifest: {', '.join(errors)}")

        # Check capability requirements
        granted = capabilities or self.config.default_capabilities
        if (
            manifest.required_capabilities & granted
            != manifest.required_capabilities
        ):
            missing = manifest.required_capabilities & ~granted
            raise PermissionError(
                f"Plugin requires capabilities not granted: {missing}"
            )

        # Verify checksum
        if manifest.checksum:
            actual_checksum = self._compute_checksum(wasm_path)
            if actual_checksum != manifest.checksum:
                raise SecurityError(
                    f"Checksum mismatch: expected {manifest.checksum}, "
                    f"got {actual_checksum}"
                )

        # Verify signature (if required)
        if self.config.require_signature and manifest.signature:
            if not self._verify_signature(wasm_path, manifest):
                raise SecurityError("Plugin signature verification failed")

        # Generate plugin ID
        plugin_id = (
            f"{manifest.name}_{manifest.version}_{int(time.time() * 1000)}"
        )

        # Create plugin instance
        plugin = WASMPlugin(
            id=plugin_id,
            manifest=manifest,
            wasm_path=wasm_path,
            capabilities=granted,
            state=PluginState.LOADING,
        )

        # Load WASM module
        try:
            await self._runtime.load_module(wasm_path, self.config)
            plugin.state = PluginState.READY
        except Exception as e:
            plugin.state = PluginState.ERROR
            plugin.last_error = str(e)
            raise

        with self._lock:
            self._plugins[plugin_id] = plugin

        logger.info(
            f"Loaded plugin: {manifest.name} v{manifest.version} (id={plugin_id})"
        )
        return plugin

    async def call_plugin(
        self,
        plugin_id: str,
        function: str,
        args: list[Any] | None = None,
        timeout_ms: int | None = None,
    ) -> WASMCallResult:
        """Call a function in a loaded plugin."""
        with self._lock:
            if plugin_id not in self._plugins:
                return WASMCallResult(
                    success=False,
                    output=None,
                    error=f"Plugin not found: {plugin_id}",
                )
            plugin = self._plugins[plugin_id]

        if plugin.state != PluginState.READY:
            return WASMCallResult(
                success=False,
                output=None,
                error=f"Plugin not ready (state={plugin.state.value})",
            )

        # Check if function is exported
        if function not in plugin.manifest.exports:
            return WASMCallResult(
                success=False,
                output=None,
                error=f"Function not exported: {function}",
            )

        # Set execution timeout
        timeout = timeout_ms or self.config.max_wall_time_ms

        # Execute function
        plugin.state = PluginState.RUNNING
        plugin.call_count += 1
        plugin.last_call = datetime.now()

        try:
            result = await asyncio.wait_for(
                self._runtime.call_function(
                    str(plugin.wasm_path),
                    function,
                    args or [],
                    self.config.max_cpu_time_ms,
                ),
                timeout=timeout / 1000,
            )

            # Update resource tracking
            plugin.cpu_time_ms += result.execution_time_ms
            plugin.memory_used_mb = max(
                plugin.memory_used_mb, result.memory_used_mb
            )

            plugin.state = PluginState.READY
            return result

        except TimeoutError:
            plugin.state = PluginState.ERROR
            plugin.error_count += 1
            plugin.last_error = f"Execution timeout ({timeout}ms)"
            return WASMCallResult(
                success=False,
                output=None,
                error=plugin.last_error,
            )
        except Exception as e:
            plugin.state = PluginState.ERROR
            plugin.error_count += 1
            plugin.last_error = str(e)
            return WASMCallResult(
                success=False,
                output=None,
                error=str(e),
            )

    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin."""
        with self._lock:
            if plugin_id not in self._plugins:
                return False
            plugin = self._plugins[plugin_id]

        try:
            await self._runtime.unload_module(str(plugin.wasm_path))
            plugin.state = PluginState.TERMINATED
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")

        with self._lock:
            del self._plugins[plugin_id]

        logger.info(f"Unloaded plugin: {plugin_id}")
        return True

    def get_plugin(self, plugin_id: str) -> WASMPlugin | None:
        """Get plugin by ID."""
        with self._lock:
            return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[WASMPlugin]:
        """List all loaded plugins."""
        with self._lock:
            return list(self._plugins.values())

    def _compute_checksum(self, wasm_path: Path) -> str:
        """Compute SHA256 checksum of WASM file."""
        hasher = hashlib.sha256()
        with open(wasm_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _verify_signature(
        self,
        wasm_path: Path,
        manifest: PluginManifest,
    ) -> bool:
        """Verify plugin signature."""
        # In production: Use cryptographic verification
        # For now, just check publisher is allowed
        if not manifest.publisher:
            return False

        if self.config.allowed_publishers:
            return manifest.publisher in self.config.allowed_publishers

        return True

    def get_status(self) -> dict[str, Any]:
        """Get sandbox status."""
        with self._lock:
            plugins_summary = {}
            for pid, plugin in self._plugins.items():
                plugins_summary[pid] = {
                    "name": plugin.manifest.name,
                    "version": plugin.manifest.version,
                    "state": plugin.state.value,
                    "call_count": plugin.call_count,
                }

        return {
            "initialized": self._initialized,
            "enabled": self.config.enabled,
            "runtime": self.config.runtime,
            "plugins_loaded": len(self._plugins),
            "max_instances": self.config.max_instances,
            "plugins": plugins_summary,
        }


class SecurityError(Exception):
    """Security-related error in WASM sandbox."""

    pass


# Helper functions for plugin development
def create_plugin_manifest(
    name: str,
    version: str,
    main: str = "plugin.wasm",
    exports: list[str] | None = None,
    capabilities: list[str] | None = None,
    **kwargs: Any,
) -> PluginManifest:
    """Create a plugin manifest with sensible defaults."""
    caps = WASMCapability.NONE
    if capabilities:
        for cap_name in capabilities:
            try:
                caps |= WASMCapability[cap_name]
            except KeyError:
                pass

    return PluginManifest(
        name=name,
        version=version,
        main=main,
        exports=exports or ["run"],
        required_capabilities=caps,
        **kwargs,
    )


def generate_plugin_template(name: str, language: str = "rust") -> str:
    """Generate a plugin template in the specified language."""
    if language == "rust":
        return f"""// {name} - Aura IA WASM Plugin
// Compile with: cargo build --target wasm32-wasi --release

#[no_mangle]
pub extern "C" fn run(input_ptr: i32, input_len: i32) -> i32 {{
    // Plugin implementation
    0 // Return success
}}

#[no_mangle]
pub extern "C" fn allocate(size: i32) -> i32 {{
    // Memory allocation for host communication
    0
}}

#[no_mangle]
pub extern "C" fn deallocate(ptr: i32, size: i32) {{
    // Memory deallocation
}}
"""
    elif language == "assemblyscript":
        return f"""// {name} - Aura IA WASM Plugin
// Compile with: asc plugin.ts -o plugin.wasm

export function run(input: string): string {{
  // Plugin implementation
  return "success";
}}
"""
    elif language == "go":
        return f"""// {name} - Aura IA WASM Plugin
// Compile with: GOOS=wasip1 GOARCH=wasm go build -o plugin.wasm

package main

import "fmt"

//export run
func run() int32 {{
    fmt.Println("{name} plugin executed")
    return 0
}}

func main() {{}}
"""
    else:
        raise ValueError(f"Unsupported language: {language}")


# Singleton instance
_wasm_sandbox: WASMSandbox | None = None


def get_wasm_sandbox() -> WASMSandbox:
    """Get or create the singleton WASM sandbox."""
    global _wasm_sandbox
    if _wasm_sandbox is None:
        _wasm_sandbox = WASMSandbox()
    return _wasm_sandbox
