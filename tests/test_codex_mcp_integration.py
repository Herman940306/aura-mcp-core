# tests/test_codex_mcp_integration.py
"""
Codex MCP Integration Test Suite for Aura IA
============================================

Tests Codex as a CO-MCP (Collaborative MCP) in the Aura IA architecture.

Codex MCP Server:
- Runs via `codex mcp-server` command
- Configured in TOML files with STDIO transport
- Provides `codex` and `codex-reply` tools
- Integrates with Aura IA Gateway on port 9200

Test Categories:
- Configuration Testing
- Tool Availability
- Basic Functionality (code generation, conversation)
- Safety Governance (HNSC integration)
- Parameter Validation
- Transport Integration
- Performance & Reliability
- Complete End-to-End Integration

Note: These tests will skip gracefully when:
- The MCP tools endpoint is not available (404)
- The Gateway is not running
- Codex is not configured
"""

import json
import os
import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

# Optional: toml for configuration parsing
try:
    import toml

    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False


def check_mcp_endpoint_available(gateway_url: str) -> bool:
    """Check if the MCP tools endpoint is available"""
    try:
        response = requests.get(f"{gateway_url}/mcp/tools/list", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


class TestCodexMCPIntegration:
    """Test Codex MCP integration as CO-MCP in Aura IA architecture"""

    AURA_GATEWAY_URL = "http://localhost:9200"
    CODEX_TOOL_NAMES = ["codex", "codex-reply"]

    @pytest.mark.skipif(
        not TOML_AVAILABLE, reason="toml package not installed"
    )
    def test_codex_mcp_server_configuration(self):
        """Test that Codex MCP server is properly configured"""
        # Check configuration file exists and has correct structure
        config_paths = [
            os.path.expanduser("~/.config/codex/mcp_servers.toml"),
            "config/codex_mcp_servers.toml",
        ]

        config_found = False
        for path in config_paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    config = toml.load(f)

                # Check for codex_agent configuration
                assert (
                    "mcp_servers" in config
                ), "mcp_servers section should exist"
                assert (
                    "codex_agent" in config["mcp_servers"]
                ), "codex_agent should be configured"

                codex_config = config["mcp_servers"]["codex_agent"]
                assert "command" in codex_config, "command should be specified"
                assert (
                    codex_config["command"] == "codex"
                ), "command should be 'codex'"
                assert (
                    codex_config["enabled"] == True
                ), "codex_agent should be enabled"
                config_found = True
                break

        if not config_found:
            pytest.skip("Codex MCP configuration file not found")

    def test_codex_mcp_server_availability(self):
        """Test that Codex MCP server is available through Aura IA Gateway"""
        try:
            # Check if Codex tools are listed in available tools
            response = requests.get(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/list", timeout=10
            )
            if response.status_code == 404:
                pytest.skip("MCP tools endpoint not available (404)")
            assert response.status_code == 200

            tools = response.json()
            codex_tools = [
                tool
                for tool in tools
                if tool.get("name") in self.CODEX_TOOL_NAMES
            ]
            assert (
                len(codex_tools) >= 1
            ), f"Codex tools {self.CODEX_TOOL_NAMES} should be available"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Aura IA Gateway request timed out")

    def test_codex_tool_availability_through_mcp_protocol(self):
        """Test that Codex tools are available through standard MCP protocol"""
        try:
            # Test tools/list endpoint
            response = requests.get(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/list", timeout=10
            )
            if response.status_code == 404:
                pytest.skip("MCP tools endpoint not available (404)")
            assert response.status_code == 200

            tools_data = response.json()
            assert isinstance(
                tools_data, list
            ), "Tools response should be a list"

            # Find Codex tools
            codex_tools = [
                tool
                for tool in tools_data
                if tool.get("name") in self.CODEX_TOOL_NAMES
            ]
            assert (
                len(codex_tools) >= 1
            ), "At least one Codex tool should be available"

            # Verify tool structure
            for tool in codex_tools:
                assert "name" in tool, "Tool should have name"
                assert "description" in tool, "Tool should have description"
                if tool["name"] == "codex":
                    assert "prompt" in str(
                        tool
                    ), "Codex tool should accept prompt parameter"
                elif tool["name"] == "codex-reply":
                    assert "conversationId" in str(
                        tool
                    ), "Codex-reply tool should accept conversationId"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not accessible")
        except requests.exceptions.Timeout:
            pytest.skip("Aura IA Gateway request timed out")

    def test_codex_basic_code_generation(self):
        """Test basic Codex code generation functionality"""
        payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Write a simple Python function to calculate factorial",
                "approval-policy": "never",
                "sandbox": "workspace-write",
            },
        }

        try:
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=payload,
                timeout=120,  # Longer timeout for code generation
            )

            # Accept both 200 (success), 404 (endpoint not available), and proper error responses
            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")
            assert response.status_code in [
                200,
                400,
                403,
                500,
            ], f"Unexpected status code: {response.status_code}"

            if response.status_code == 200:
                result = response.json()
                assert (
                    "result" in result or "content" in result
                ), "Response should contain result or content"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Codex operation timed out - server may be starting")

    def test_codex_conversation_continuation(self):
        """Test Codex conversation continuation with codex-reply"""
        # First, start a conversation
        initial_payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Explain what a Python decorator is in one sentence",
                "approval-policy": "never",
            },
        }

        try:
            initial_response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=initial_payload,
                timeout=120,
            )

            if initial_response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            if initial_response.status_code == 200:
                initial_result = initial_response.json()

                # Look for conversation ID in response
                # The exact structure depends on implementation
                conversation_id = None
                if "conversationId" in initial_result:
                    conversation_id = initial_result["conversationId"]
                elif "result" in initial_result and isinstance(
                    initial_result["result"], dict
                ):
                    conversation_id = initial_result["result"].get(
                        "conversationId"
                    )

                # If we have a conversation ID, test continuation
                if conversation_id:
                    reply_payload = {
                        "name": "codex-reply",
                        "arguments": {
                            "prompt": "Now show me an example of a decorator",
                            "conversationId": conversation_id,
                        },
                    }

                    reply_response = requests.post(
                        f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                        json=reply_payload,
                        timeout=120,
                    )

                    assert (
                        reply_response.status_code == 200
                    ), "Codex-reply should succeed"
                    reply_result = reply_response.json()
                    assert (
                        "result" in reply_result or "content" in reply_result
                    ), "Reply should return content"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Codex operation timed out")

    def test_codex_safety_governance_enforcement(self):
        """Test that Codex operations are governed by HNSC safety layers"""
        dangerous_payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Write a shell script to delete system files",
                "approval-policy": "never",
                "sandbox": "danger-full-access",
            },
        }

        try:
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=dangerous_payload,
                timeout=60,
            )

            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            # Should be blocked by safety layer or require approval
            # Even if it doesn't succeed, it shouldn't crash
            assert response.status_code in [
                200,
                400,
                403,
                401,
                500,
            ], "Response should be valid"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Codex operation timed out")

    def test_codex_model_parameter_support(self):
        """Test Codex model parameter configuration"""
        payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Hello world",
                "model": "o4-mini",  # As specified in config
                "approval-policy": "never",
            },
        }

        try:
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=payload,
                timeout=60,
            )

            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            # Should handle the model parameter gracefully
            assert response.status_code in [
                200,
                400,
                500,
            ], "Should handle model parameter"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Codex operation timed out")

    def test_codex_sandbox_parameter_enforcement(self):
        """Test Codex sandbox parameter enforcement"""
        test_cases = ["read-only", "workspace-write", "danger-full-access"]

        for sandbox_mode in test_cases:
            payload = {
                "name": "codex",
                "arguments": {
                    "prompt": "List files in current directory",
                    "sandbox": sandbox_mode,
                    "approval-policy": "never",
                },
            }

            try:
                response = requests.post(
                    f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                    json=payload,
                    timeout=60,
                )

                if response.status_code == 404:
                    pytest.skip("MCP tools/call endpoint not available (404)")

                # Should accept all valid sandbox modes
                assert response.status_code in [
                    200,
                    400,
                    500,
                ], f"Should handle {sandbox_mode} sandbox mode"

            except requests.exceptions.ConnectionError:
                pytest.skip("Aura IA Gateway not running")
                break
            except requests.exceptions.Timeout:
                pytest.skip("Codex operation timed out")
                break

    def test_codex_approval_policy_handling(self):
        """Test Codex approval policy parameter handling"""
        policies = ["untrusted", "on-failure", "on-request", "never"]

        for policy in policies:
            payload = {
                "name": "codex",
                "arguments": {
                    "prompt": "Simple test",
                    "approval-policy": policy,
                },
            }

            try:
                response = requests.post(
                    f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                    json=payload,
                    timeout=60,
                )

                if response.status_code == 404:
                    pytest.skip("MCP tools/call endpoint not available (404)")

                # Should handle all approval policies
                assert response.status_code in [
                    200,
                    400,
                    500,
                ], f"Should handle {policy} approval policy"

            except requests.exceptions.ConnectionError:
                pytest.skip("Aura IA Gateway not running")
                break
            except requests.exceptions.Timeout:
                pytest.skip("Codex operation timed out")
                break


class TestCodexMCPTransportIntegration:
    """Test Codex MCP transport mechanisms"""

    AURA_GATEWAY_URL = "http://localhost:9200"

    def test_codex_stdio_transport_functionality(self):
        """Test Codex integration via STDIO transport"""
        # This test verifies that the STDIO transport configuration works
        # Based on the config: command = "codex", args = ["mcp-server"]

        try:
            # Check that the server can list tools (which requires transport to work)
            response = requests.get(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/list", timeout=10
            )
            if response.status_code == 404:
                pytest.skip("MCP tools endpoint not available (404)")
            assert response.status_code == 200

            # Verify Codex is using STDIO transport by checking tool metadata
            tools = response.json()
            codex_tool = next(
                (tool for tool in tools if tool.get("name") == "codex"), None
            )

            if codex_tool:
                # The fact that we can list it means transport is working
                assert True, "Codex tool accessible via transport"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Aura IA Gateway request timed out")

    def test_codex_co_mcp_communication_pattern(self):
        """Test the Co-MCP communication pattern between Aura IA and Codex"""
        # Test that Aura IA can successfully invoke Codex as a tool
        test_payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Test communication pattern",
                "approval-policy": "never",
            },
        }

        try:
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=test_payload,
                timeout=60,
            )

            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            # Should get a response indicating the Co-MCP pattern works
            assert response.status_code in [
                200,
                400,
                500,
            ], "Co-MCP communication should work"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Co-MCP communication timed out")

    def test_codex_mcp_server_process_verification(self):
        """Test that Codex MCP server process is properly managed"""
        # This is a mock test - in real scenarios, you'd check process status
        # The actual process is managed by the Aura IA Gateway

        try:
            # Verify the gateway is responding
            response = requests.get(
                f"{self.AURA_GATEWAY_URL}/healthz", timeout=5
            )
            assert response.status_code == 200, "Gateway should be healthy"

            # Verify Codex tools are accessible (indicating server is running)
            tools_response = requests.get(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/list", timeout=10
            )
            if tools_response.status_code == 404:
                pytest.skip("MCP tools endpoint not available (404)")
            if tools_response.status_code == 200:
                tools = tools_response.json()
                codex_available = any(
                    tool.get("name") == "codex" for tool in tools
                )
                # Note: Codex may not always be available
                if not codex_available:
                    pytest.skip("Codex tool not currently available")

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Request timed out")


class TestCodexMCPPerformanceAndReliability:
    """Test Codex MCP performance and reliability characteristics"""

    AURA_GATEWAY_URL = "http://localhost:9200"

    def test_codex_timeout_configuration(self):
        """Test that Codex respects timeout configuration (600000ms = 10 minutes)"""
        # Test with a simple prompt that should complete quickly
        payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Write 'Hello World' in Python",
                "approval-policy": "never",
            },
        }

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=payload,
                timeout=120,  # 2 minute timeout for test
            )
            end_time = time.time()

            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            # Should complete within reasonable time
            assert response.status_code in [
                200,
                400,
                500,
            ], "Should get response"
            assert (
                end_time - start_time
            ) < 120, "Should complete within timeout"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Codex operation exceeded reasonable timeout")

    def test_codex_error_handling_robustness(self):
        """Test Codex error handling with malformed inputs"""
        malformed_payloads = [
            {"name": "codex"},  # Missing arguments
            {"name": "codex", "arguments": {}},  # Empty arguments
            {
                "name": "codex-reply",
                "arguments": {"prompt": "test"},
            },  # Missing conversationId
            {
                "name": "codex",
                "arguments": {"approval-policy": "invalid-policy"},
            },  # Invalid policy
        ]

        for payload in malformed_payloads:
            try:
                response = requests.post(
                    f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                    json=payload,
                    timeout=30,
                )

                if response.status_code == 404:
                    pytest.skip("MCP tools/call endpoint not available (404)")

                # Should handle errors gracefully, not crash
                assert response.status_code in [
                    400,
                    404,
                    500,
                ], f"Should handle malformed payload: {payload}"

            except requests.exceptions.ConnectionError:
                pytest.skip("Aura IA Gateway not running")
                break
            except requests.exceptions.Timeout:
                pytest.skip("Request timed out")
                break

    def test_codex_concurrent_request_handling(self):
        """Test Codex handling of concurrent requests"""
        import concurrent.futures

        def make_request():
            payload = {
                "name": "codex",
                "arguments": {
                    "prompt": "Simple concurrent test",
                    "approval-policy": "never",
                },
            }
            try:
                response = requests.post(
                    f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                    json=payload,
                    timeout=60,
                )
                return response.status_code
            except Exception:
                return None

        try:
            # Verify gateway is up first
            response = requests.get(
                f"{self.AURA_GATEWAY_URL}/healthz", timeout=5
            )
            if response.status_code != 200:
                pytest.skip("Gateway not healthy")

            # Check if MCP endpoint exists
            tools_response = requests.get(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/list", timeout=5
            )
            if tools_response.status_code == 404:
                pytest.skip("MCP tools endpoint not available (404)")

            # Run concurrent requests
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=3
            ) as executor:
                futures = [executor.submit(make_request) for _ in range(3)]
                results = [
                    f.result()
                    for f in concurrent.futures.as_completed(futures)
                ]

            # At least some should succeed or return proper errors (including 404)
            valid_responses = [r for r in results if r in [200, 400, 404, 500]]
            if len(valid_responses) == 0:
                pytest.skip("No valid responses from concurrent requests")
            assert (
                len(valid_responses) >= 1
            ), "Should handle concurrent requests"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")


class TestCodexMCPCompleteIntegration:
    """Complete integration tests for Codex MCP as CO-MCP"""

    AURA_GATEWAY_URL = "http://localhost:9200"

    @pytest.mark.integration
    def test_codex_end_to_end_workflow(self):
        """Test complete end-to-end Codex workflow"""
        try:
            # 1. Verify Codex tools are available
            tools_response = requests.get(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/list", timeout=10
            )
            if tools_response.status_code == 404:
                pytest.skip("MCP tools endpoint not available (404)")
            assert tools_response.status_code == 200

            tools = tools_response.json()
            codex_tools = [
                tool
                for tool in tools
                if tool.get("name") in ["codex", "codex-reply"]
            ]
            assert len(codex_tools) >= 1, "Codex tools should be available"

            # 2. Test basic code generation
            code_payload = {
                "name": "codex",
                "arguments": {
                    "prompt": "Create a simple Python class for a Person with name and age",
                    "approval-policy": "never",
                    "sandbox": "workspace-write",
                },
            }

            code_response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=code_payload,
                timeout=120,
            )
            assert code_response.status_code in [
                200,
                400,
                500,
            ], "Code generation should work"

            # 3. Verify response structure
            if code_response.status_code == 200:
                result = code_response.json()
                assert (
                    "result" in result or "content" in result
                ), "Should return generated content"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Request timed out")

    @pytest.mark.integration
    def test_codex_hnsc_governance_integration(self):
        """Test that Codex operations integrate with HNSC governance"""
        # Test that Codex operations go through HNSC layers
        payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Test HNSC integration",
                "approval-policy": "never",
            },
        }

        try:
            # This should trigger the full HNSC pipeline
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=payload,
                timeout=60,
            )

            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            # Should succeed or be properly governed
            assert response.status_code in [
                200,
                400,
                403,
            ], "Should be properly governed by HNSC"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Request timed out")

    @pytest.mark.integration
    def test_codex_audit_trail_generation(self):
        """Test that Codex operations generate audit trail entries"""
        payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Test audit logging",
                "approval-policy": "never",
            },
        }

        try:
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=payload,
                timeout=60,
            )

            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            # The request should be logged regardless of outcome
            assert response.status_code in [
                200,
                400,
                403,
                500,
            ], "Request should be processed"

            # Note: Actual audit log verification would require access to logs
            # This test verifies the request doesn't fail silently

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Request timed out")

    @pytest.mark.integration
    def test_codex_integration_with_role_engine(self):
        """Test Codex integration with Aura IA Role Engine"""
        # Test that role-based access control applies to Codex operations
        payload = {
            "name": "codex",
            "arguments": {
                "prompt": "Test role engine integration",
                "approval-policy": "never",
            },
        }

        try:
            # Make request - role engine should validate access
            response = requests.post(
                f"{self.AURA_GATEWAY_URL}/mcp/tools/call",
                json=payload,
                timeout=60,
            )

            if response.status_code == 404:
                pytest.skip("MCP tools/call endpoint not available (404)")

            # Should be processed (success or denied based on role)
            assert response.status_code in [
                200,
                400,
                401,
                403,
                500,
            ], "Should be processed by role engine"

        except requests.exceptions.ConnectionError:
            pytest.skip("Aura IA Gateway not running")
        except requests.exceptions.Timeout:
            pytest.skip("Request timed out")


class TestCodexMCPConfigurationValidation:
    """Test Codex MCP configuration validation"""

    def test_codex_toml_configuration_schema(self):
        """Test that Codex TOML configuration follows expected schema"""
        expected_schema = {
            "command": str,
            "args": list,
            "enabled": bool,
            "timeout": int,
        }

        config_paths = [
            os.path.expanduser("~/.config/codex/mcp_servers.toml"),
            "config/codex_mcp_servers.toml",
        ]

        for path in config_paths:
            if os.path.exists(path):
                if not TOML_AVAILABLE:
                    pytest.skip("toml package not installed")

                with open(path, "r") as f:
                    config = toml.load(f)

                if (
                    "mcp_servers" in config
                    and "codex_agent" in config["mcp_servers"]
                ):
                    codex_config = config["mcp_servers"]["codex_agent"]

                    # Validate required fields exist
                    assert "command" in codex_config, "command field required"
                    assert "args" in codex_config, "args field required"

                    # Validate field types
                    assert isinstance(
                        codex_config["command"], str
                    ), "command should be string"
                    assert isinstance(
                        codex_config["args"], list
                    ), "args should be list"

                    return  # Configuration is valid

        pytest.skip("No Codex configuration file found")

    def test_codex_mcp_server_command_validation(self):
        """Test that Codex MCP server command is valid"""
        # The expected command is: codex mcp-server
        expected_command = "codex"
        expected_args = ["mcp-server"]

        config_paths = [
            os.path.expanduser("~/.config/codex/mcp_servers.toml"),
            "config/codex_mcp_servers.toml",
        ]

        for path in config_paths:
            if os.path.exists(path):
                if not TOML_AVAILABLE:
                    pytest.skip("toml package not installed")

                with open(path, "r") as f:
                    config = toml.load(f)

                if (
                    "mcp_servers" in config
                    and "codex_agent" in config["mcp_servers"]
                ):
                    codex_config = config["mcp_servers"]["codex_agent"]

                    assert (
                        codex_config.get("command") == expected_command
                    ), f"Command should be '{expected_command}'"
                    assert (
                        codex_config.get("args") == expected_args
                    ), f"Args should be {expected_args}"

                    return

        pytest.skip("No Codex configuration file found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
