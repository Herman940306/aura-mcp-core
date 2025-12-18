"""MCP Configuration Manager

Manages MCP configuration updates and validation for the Kiro IDE MCP server.

Project Creator: Herman Swanepoel
Version: 1.0
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


class MCPConfigurationManager:
    """Manages MCP configuration updates and validation."""

    def __init__(self, config_path: Path):
        """Initialize with path to mcp.json.

        Args:
            config_path: Path to the mcp.json configuration file
        """
        self.config_path = Path(config_path)
        self.backup_dir = self.config_path.parent / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def read_config(self) -> dict[str, Any]:
        """Read current configuration.

        Returns:
            Dictionary containing the current configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )

        with open(self.config_path, encoding="utf-8") as f:
            return json.load(f)

    def update_config(self, updates: dict[str, Any]) -> bool:
        """Update configuration with new values.

        Args:
            updates: Dictionary of updates to apply to the configuration

        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Read current config
            config = self.read_config()

            # Backup before updating
            self.backup_config()

            # Apply updates (deep merge for nested dicts)
            self._deep_update(config, updates)

            # Write updated config
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            return True

        except Exception as e:
            print(f"Error updating configuration: {e}")
            return False

    def enable_server(self) -> bool:
        """Set disabled=false to enable the MCP server.

        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.read_config()

            # Navigate to the server config
            if (
                "mcpServers" in config
                and "ide-agents-mcp" in config["mcpServers"]
            ):
                config["mcpServers"]["ide-agents-mcp"]["disabled"] = False

                # Write updated config
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)

                print("✅ MCP server enabled (disabled=false)")
                return True
            else:
                print("❌ MCP server configuration not found")
                return False

        except Exception as e:
            print(f"❌ Error enabling server: {e}")
            return False

    def set_working_directory(self, path: str) -> bool:
        """Update cwd to NEW_KIRO_MCP directory.

        Args:
            path: New working directory path

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate path exists
            if not Path(path).exists():
                print(f"❌ Path does not exist: {path}")
                return False

            config = self.read_config()

            # Navigate to the server config
            if (
                "mcpServers" in config
                and "ide-agents-mcp" in config["mcpServers"]
            ):
                old_path = config["mcpServers"]["ide-agents-mcp"].get(
                    "cwd", ""
                )
                config["mcpServers"]["ide-agents-mcp"]["cwd"] = path

                # Write updated config
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)

                print("✅ Working directory updated:")
                print(f"   Old: {old_path}")
                print(f"   New: {path}")
                return True
            else:
                print("❌ MCP server configuration not found")
                return False

        except Exception as e:
            print(f"❌ Error setting working directory: {e}")
            return False

    def enable_all_tools(self) -> bool:
        """Clear disabledTools array to enable all MCP tools.

        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.read_config()

            # Navigate to the server config
            if (
                "mcpServers" in config
                and "ide-agents-mcp" in config["mcpServers"]
            ):
                disabled_tools = config["mcpServers"]["ide-agents-mcp"].get(
                    "disabledTools", []
                )
                tool_count = len(disabled_tools)

                config["mcpServers"]["ide-agents-mcp"]["disabledTools"] = []

                # Write updated config
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)

                print(
                    f"✅ All MCP tools enabled ({tool_count} tools were disabled)"
                )
                return True
            else:
                print("❌ MCP server configuration not found")
                return False

        except Exception as e:
            print(f"❌ Error enabling tools: {e}")
            return False

    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate configuration structure and values.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        try:
            config = self.read_config()

            # Check for required top-level keys
            if "mcpServers" not in config:
                errors.append("Missing 'mcpServers' key")
                return False, errors

            # Check for ide-agents-mcp server
            if "ide-agents-mcp" not in config["mcpServers"]:
                errors.append("Missing 'ide-agents-mcp' server configuration")
                return False, errors

            server_config = config["mcpServers"]["ide-agents-mcp"]

            # Validate required fields
            required_fields = ["command", "args", "env", "cwd"]
            for field in required_fields:
                if field not in server_config:
                    errors.append(f"Missing required field: {field}")

            # Validate command path exists
            if "command" in server_config:
                command_path = Path(server_config["command"])
                if not command_path.exists():
                    errors.append(
                        f"Python executable not found: {server_config['command']}"
                    )

            # Validate working directory exists
            if "cwd" in server_config:
                cwd_path = Path(server_config["cwd"])
                if not cwd_path.exists():
                    errors.append(
                        f"Working directory not found: {server_config['cwd']}"
                    )

            # Validate environment variables
            if "env" in server_config:
                required_env_vars = [
                    "IDE_AGENTS_BACKEND_URL",
                    "IDE_AGENTS_REQUEST_TIMEOUT",
                    "IDE_AGENTS_ULTRA_ENABLED",
                ]
                for env_var in required_env_vars:
                    if env_var not in server_config["env"]:
                        errors.append(
                            f"Missing environment variable: {env_var}"
                        )

            # Check if server is disabled
            if server_config.get("disabled", False):
                errors.append("Server is disabled (disabled=true)")

            # Check if tools are disabled
            disabled_tools = server_config.get("disabledTools", [])
            if disabled_tools:
                errors.append(f"{len(disabled_tools)} tools are disabled")

            is_valid = len(errors) == 0
            return is_valid, errors

        except FileNotFoundError as e:
            errors.append(f"Configuration file not found: {e}")
            return False, errors
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in configuration file: {e}")
            return False, errors
        except Exception as e:
            errors.append(f"Unexpected error during validation: {e}")
            return False, errors

    def backup_config(self) -> Path:
        """Create backup of current config.

        Returns:
            Path to the backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"mcp_config_{timestamp}.json"

        try:
            shutil.copy2(self.config_path, backup_path)
            print(f"✅ Configuration backed up to: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            raise

    def _deep_update(
        self, base_dict: dict[str, Any], update_dict: dict[str, Any]
    ) -> None:
        """Recursively update nested dictionaries.

        Args:
            base_dict: Base dictionary to update
            update_dict: Dictionary with updates to apply
        """
        for key, value in update_dict.items():
            if (
                isinstance(value, dict)
                and key in base_dict
                and isinstance(base_dict[key], dict)
            ):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def get_server_config(self) -> dict[str, Any]:
        """Get the ide-agents-mcp server configuration.

        Returns:
            Dictionary containing the server configuration
        """
        config = self.read_config()
        return config.get("mcpServers", {}).get("ide-agents-mcp", {})

    def is_server_enabled(self) -> bool:
        """Check if the MCP server is enabled.

        Returns:
            True if server is enabled, False otherwise
        """
        server_config = self.get_server_config()
        return not server_config.get("disabled", False)

    def get_working_directory(self) -> str:
        """Get the current working directory from config.

        Returns:
            Current working directory path
        """
        server_config = self.get_server_config()
        return server_config.get("cwd", "")

    def get_disabled_tools(self) -> list[str]:
        """Get list of disabled tools.

        Returns:
            List of disabled tool names
        """
        server_config = self.get_server_config()
        return server_config.get("disabledTools", [])


if __name__ == "__main__":
    # Example usage
    config_path = Path(".kiro/settings/mcp.json")
    manager = MCPConfigurationManager(config_path)

    print("=== MCP Configuration Manager ===\n")

    # Read current config
    print("Current configuration:")
    print(f"  Server enabled: {manager.is_server_enabled()}")
    print(f"  Working directory: {manager.get_working_directory()}")
    print(f"  Disabled tools: {len(manager.get_disabled_tools())}")

    # Validate config
    print("\nValidating configuration...")
    is_valid, errors = manager.validate_config()
    if is_valid:
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration has errors:")
        for error in errors:
            print(f"  - {error}")
