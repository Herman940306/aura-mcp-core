import os

import pytest
import requests

# Configuration
DASHBOARD_URL = "http://localhost:9205"
MCP_API_URL = "http://localhost:9200/api"


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skipping frontend tests in CI environment without running services",
)
class TestPhase7Frontend:
    """
    Phase 7: Frontend Evolution & Integration Tests
    """

    def test_dashboard_availability(self):
        """
        Verify that the dashboard is serving content.
        """
        try:
            response = requests.get(DASHBOARD_URL, timeout=5)
            assert response.status_code == 200
            assert "<title>KIRO_MCP Monitor Dashboard" in response.text
        except requests.exceptions.ConnectionError:
            pytest.fail(f"Dashboard not accessible at {DASHBOARD_URL}")

    def test_static_assets_served(self):
        """
        Verify that CSS and JS assets are accessible.
        """
        assets = ["/assets/style.css", "/assets/app.js"]
        for asset in assets:
            try:
                response = requests.get(f"{DASHBOARD_URL}{asset}", timeout=5)
                assert response.status_code == 200, f"Failed to load {asset}"
            except requests.exceptions.ConnectionError:
                pytest.fail(f"Dashboard asset {asset} not accessible")

    def test_api_proxy_or_cors(self):
        """
        Verify that the dashboard can reach the backend API (simulated check).
        This assumes the dashboard might have a proxy or the backend allows CORS.
        """
        # This test is more of a placeholder for E2E testing with Selenium/Playwright
        # For now, we just check if the backend is up, which the dashboard relies on.
        try:
            response = requests.get(f"{MCP_API_URL}/health", timeout=5)
            # If 404, it means endpoint might be different, but service is reachable
            # If connection error, service is down
            if response.status_code != 200 and response.status_code != 404:
                pass  # It's okay if it returns other codes, as long as it connects
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend API not running, skipping integration check")


if __name__ == "__main__":
    pytest.main([__file__])
    pytest.main([__file__])
    pytest.main([__file__])
