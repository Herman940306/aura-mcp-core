"""
Playwright E2E Test Configuration - Enhanced for Full Evidence Collection
Aura IA MCP - Enterprise-Grade Dashboard Testing

Features:
- Video recording
- Network tracing
- Screenshot capture
- Full evidence folder structure
"""

import datetime
import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

# Evidence output directories
EVIDENCE_DIR = Path(__file__).parent.parent.parent / "e2e-evidence"
SCREENSHOTS_DIR = EVIDENCE_DIR / "screenshots"
VIDEOS_DIR = EVIDENCE_DIR / "videos"
NETWORK_DIR = EVIDENCE_DIR / "network"

# Ensure directories exist
for dir_path in [EVIDENCE_DIR, SCREENSHOTS_DIR, VIDEOS_DIR, NETWORK_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Service URLs (Docker stack)
DASHBOARD_URL = "http://localhost:9205"
GATEWAY_URL = "http://localhost:9200"
ML_BACKEND_URL = "http://localhost:9201"
RAG_URL = "http://localhost:9202"
AUDIO_URL = "http://localhost:8001"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for video recording and viewport."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
        "record_video_dir": str(VIDEOS_DIR),
        "record_video_size": {"width": 1920, "height": 1080},
    }


@pytest.fixture
def evidence_path():
    """Return evidence directory path."""
    return EVIDENCE_DIR


@pytest.fixture
def screenshots_path():
    """Return screenshots directory path."""
    return SCREENSHOTS_DIR


def take_screenshot(page: Page, name: str) -> Path:
    """Take a screenshot and save to evidence folder."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{name}.png"
    filepath = SCREENSHOTS_DIR / filename
    page.screenshot(path=str(filepath), full_page=True)
    print(f"📸 Screenshot saved: {filepath}")
    return filepath


def capture_network_log(page: Page, name: str) -> Path:
    """Capture network requests and save to file."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = NETWORK_DIR / f"{timestamp}_{name}_network.json"

    # Get performance entries
    network_entries = page.evaluate(
        """
        () => {
            const entries = performance.getEntriesByType('resource');
            return entries.map(e => ({
                name: e.name,
                type: e.initiatorType,
                duration: e.duration,
                size: e.transferSize,
                startTime: e.startTime
            }));
        }
    """
    )

    with open(filepath, "w") as f:
        json.dump(network_entries, f, indent=2)

    print(f"🌐 Network log saved: {filepath}")
    return filepath


class EvidenceCollector:
    """Collects and organizes test evidence."""

    def __init__(self):
        self.screenshots = []
        self.network_logs = []
        self.console_logs = []
        self.test_results = []

    def add_screenshot(self, path: Path, description: str = ""):
        """Add screenshot to evidence collection."""
        self.screenshots.append(
            {
                "path": str(path),
                "description": description,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )

    def add_test_result(
        self, test_name: str, passed: bool, details: dict = None
    ):
        """Add test result to collection."""
        self.test_results.append(
            {
                "test_name": test_name,
                "passed": passed,
                "details": details or {},
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )

    def generate_summary(self) -> dict:
        """Generate summary of all collected evidence."""
        passed = sum(1 for t in self.test_results if t["passed"])
        failed = len(self.test_results) - passed

        return {
            "summary": {
                "total_tests": len(self.test_results),
                "passed": passed,
                "failed": failed,
                "pass_rate": (
                    f"{passed/len(self.test_results)*100:.1f}%"
                    if self.test_results
                    else "N/A"
                ),
            },
            "evidence": {
                "screenshots": len(self.screenshots),
                "network_logs": len(self.network_logs),
            },
            "test_results": self.test_results,
            "generated_at": datetime.datetime.now().isoformat(),
        }

    def save_summary(self, filename: str = "e2e_summary.json") -> Path:
        """Save summary to file."""
        filepath = EVIDENCE_DIR / filename
        with open(filepath, "w") as f:
            json.dump(self.generate_summary(), f, indent=2)
        return filepath


# Global evidence collector
evidence_collector = EvidenceCollector()


@pytest.fixture(scope="session", autouse=True)
def collect_evidence_summary(request):
    """Collect and save evidence summary at end of session."""
    yield

    # Save final summary
    summary_path = evidence_collector.save_summary()
    print(f"\n{'='*60}")
    print("📊 E2E Test Evidence Summary")
    print(f"{'='*60}")
    print(f"📁 Evidence directory: {EVIDENCE_DIR}")
    print(f"📸 Screenshots: {len(evidence_collector.screenshots)}")
    print(f"📝 Summary saved: {summary_path}")
    print(f"{'='*60}")
