"""Public re-export of the full sync trigger implementation.

Tests import ``SyncTriggerSystem`` from the top-level ``mcp_sync_trigger``
package. We delegate to the production implementation located under
``src.mcp_server.mcp_sync_trigger`` to avoid code duplication and keep
behavior consistent.
"""

from src.mcp_server.mcp_sync_trigger import SyncTriggerSystem  # noqa: F401

__all__ = ["SyncTriggerSystem"]
