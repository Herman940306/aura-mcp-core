#!/usr/bin/env python3
"""
Aura IA V.1.9.8 - Test Report Generator
========================================

Generates comprehensive test reports from pytest results in multiple formats:
- JSON summary
- Markdown report
- HTML dashboard
- JUnit XML aggregation
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any


class TestReportGenerator:
    """Generates test reports from pytest results."""

    def __init__(self, report_dir: str = "test-reports"):
        self.report_dir = Path(report_dir)
        self.junit_dir = self.report_dir / "junit"
        self.output_dir = self.report_dir / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "version": "V.1.9.8",
            "test_suites": [],
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
                "duration": 0.0,
            },
        }

    def parse_junit_files(self) -> None:
        """Parse all JUnit XML files in the junit directory."""
        if not self.junit_dir.exists():
            print(f"Warning: JUnit directory not found: {self.junit_dir}")
            return

        for xml_file in self.junit_dir.glob("*.xml"):
            self._parse_junit_file(xml_file)

    def _parse_junit_file(self, xml_path: Path) -> None:
        """Parse a single JUnit XML file."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Handle both testsuite and testsuites root elements
            if root.tag == "testsuites":
                for testsuite in root.findall("testsuite"):
                    self._process_testsuite(testsuite)
            elif root.tag == "testsuite":
                self._process_testsuite(root)

        except ET.ParseError as e:
            print(f"Error parsing {xml_path}: {e}")

    def _process_testsuite(self, testsuite: ET.Element) -> None:
        """Process a testsuite element."""
        suite_name = testsuite.get("name", "Unknown Suite")
        tests = int(testsuite.get("tests", 0))
        failures = int(testsuite.get("failures", 0))
        errors = int(testsuite.get("errors", 0))
        skipped = int(testsuite.get("skipped", 0))
        time = float(testsuite.get("time", 0))

        suite_data = {
            "name": suite_name,
            "tests": tests,
            "passed": tests - failures - errors - skipped,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "duration": time,
            "test_cases": [],
        }

        # Process individual test cases
        for testcase in testsuite.findall("testcase"):
            case_data = {
                "name": testcase.get("name", "Unknown"),
                "classname": testcase.get("classname", ""),
                "time": float(testcase.get("time", 0)),
                "status": "passed",
            }

            # Check for failures/errors/skips
            failure = testcase.find("failure")
            error = testcase.find("error")
            skip = testcase.find("skipped")

            if failure is not None:
                case_data["status"] = "failed"
                case_data["message"] = failure.get("message", "")
            elif error is not None:
                case_data["status"] = "error"
                case_data["message"] = error.get("message", "")
            elif skip is not None:
                case_data["status"] = "skipped"
                case_data["message"] = skip.get("message", "")

            suite_data["test_cases"].append(case_data)

        self.results["test_suites"].append(suite_data)

        # Update summary
        self.results["summary"]["total_tests"] += tests
        self.results["summary"]["passed"] += suite_data["passed"]
        self.results["summary"]["failed"] += failures
        self.results["summary"]["errors"] += errors
        self.results["summary"]["skipped"] += skipped
        self.results["summary"]["duration"] += time

    def generate_json_report(self) -> Path:
        """Generate JSON report."""
        output_path = self.output_dir / "test_report.json"
        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"Generated JSON report: {output_path}")
        return output_path

    def generate_markdown_report(self) -> Path:
        """Generate Markdown report."""
        output_path = self.output_dir / "test_report.md"

        summary = self.results["summary"]
        pass_rate = (
            (summary["passed"] / summary["total_tests"] * 100)
            if summary["total_tests"] > 0
            else 0
        )

        md_content = f"""# Aura IA V.1.9.8 - Test Report

**Generated:** {self.results["timestamp"]}  
**Version:** {self.results["version"]}  

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tests** | {summary["total_tests"]} |
| **Passed** | {summary["passed"]} ✅ |
| **Failed** | {summary["failed"]} ❌ |
| **Errors** | {summary["errors"]} ⚠️ |
| **Skipped** | {summary["skipped"]} ⏭️ |
| **Pass Rate** | {pass_rate:.1f}% |
| **Duration** | {summary["duration"]:.2f}s |

---

## Test Suites

"""

        for suite in self.results["test_suites"]:
            status_emoji = (
                "✅" if suite["failed"] == 0 and suite["errors"] == 0 else "❌"
            )
            md_content += f"""### {status_emoji} {suite["name"]}

| Metric | Value |
|--------|-------|
| Tests | {suite["tests"]} |
| Passed | {suite["passed"]} |
| Failed | {suite["failed"]} |
| Duration | {suite["duration"]:.2f}s |

"""

            # List failed tests if any
            failed_tests = [
                tc
                for tc in suite["test_cases"]
                if tc["status"] in ("failed", "error")
            ]
            if failed_tests:
                md_content += "**Failed Tests:**\n\n"
                for tc in failed_tests:
                    md_content += f"- `{tc['classname']}.{tc['name']}`: {tc.get('message', 'No message')[:100]}\n"
                md_content += "\n"

        md_content += f"""---

## Certification Status

"""

        if summary["failed"] == 0 and summary["errors"] == 0:
            md_content += """✅ **CERTIFIED** - All tests passed. System is ready for deployment.
"""
        else:
            md_content += f"""❌ **NOT CERTIFIED** - {summary["failed"]} failures, {summary["errors"]} errors must be resolved.
"""

        with open(output_path, "w") as f:
            f.write(md_content)

        print(f"Generated Markdown report: {output_path}")
        return output_path

    def generate_html_report(self) -> Path:
        """Generate HTML dashboard report."""
        output_path = self.output_dir / "test_report.html"

        summary = self.results["summary"]
        pass_rate = (
            (summary["passed"] / summary["total_tests"] * 100)
            if summary["total_tests"] > 0
            else 0
        )
        status_color = "#22c55e" if summary["failed"] == 0 else "#ef4444"

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aura IA V.1.9.8 - Test Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #f8fafc; margin-bottom: 0.5rem; }}
        .subtitle {{ color: #94a3b8; margin-bottom: 2rem; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; }}
        .card-label {{ color: #94a3b8; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        .card-value {{ font-size: 2rem; font-weight: 700; color: #f8fafc; }}
        .card-value.success {{ color: #22c55e; }}
        .card-value.error {{ color: #ef4444; }}
        .card-value.warning {{ color: #f59e0b; }}
        .progress-bar {{ background: #334155; border-radius: 8px; height: 8px; margin-top: 0.5rem; overflow: hidden; }}
        .progress-fill {{ background: {status_color}; height: 100%; transition: width 0.3s ease; }}
        .suite {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }}
        .suite-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }}
        .suite-name {{ font-size: 1.25rem; font-weight: 600; }}
        .suite-status {{ padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 500; }}
        .suite-status.pass {{ background: #166534; color: #bbf7d0; }}
        .suite-status.fail {{ background: #991b1b; color: #fecaca; }}
        .suite-stats {{ display: flex; gap: 2rem; color: #94a3b8; font-size: 0.875rem; }}
        .certification {{ background: linear-gradient(135deg, {status_color}22, {status_color}11); border: 1px solid {status_color}44; border-radius: 12px; padding: 2rem; text-align: center; margin-top: 2rem; }}
        .certification-title {{ font-size: 1.5rem; font-weight: 700; color: {status_color}; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Aura IA Test Report</h1>
        <p class="subtitle">Version {self.results["version"]} | Generated: {self.results["timestamp"]}</p>
        
        <div class="cards">
            <div class="card">
                <div class="card-label">Total Tests</div>
                <div class="card-value">{summary["total_tests"]}</div>
            </div>
            <div class="card">
                <div class="card-label">Passed</div>
                <div class="card-value success">{summary["passed"]}</div>
            </div>
            <div class="card">
                <div class="card-label">Failed</div>
                <div class="card-value error">{summary["failed"]}</div>
            </div>
            <div class="card">
                <div class="card-label">Pass Rate</div>
                <div class="card-value">{pass_rate:.1f}%</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {pass_rate}%"></div>
                </div>
            </div>
            <div class="card">
                <div class="card-label">Duration</div>
                <div class="card-value">{summary["duration"]:.1f}s</div>
            </div>
        </div>
        
        <h2 style="margin-bottom: 1rem;">Test Suites</h2>
"""

        for suite in self.results["test_suites"]:
            status_class = (
                "pass"
                if suite["failed"] == 0 and suite["errors"] == 0
                else "fail"
            )
            status_text = "PASS" if status_class == "pass" else "FAIL"

            html_content += f"""
        <div class="suite">
            <div class="suite-header">
                <span class="suite-name">{suite["name"]}</span>
                <span class="suite-status {status_class}">{status_text}</span>
            </div>
            <div class="suite-stats">
                <span>✅ {suite["passed"]} passed</span>
                <span>❌ {suite["failed"]} failed</span>
                <span>⏭️ {suite["skipped"]} skipped</span>
                <span>⏱️ {suite["duration"]:.2f}s</span>
            </div>
        </div>
"""

        cert_status = (
            "✅ CERTIFIED" if summary["failed"] == 0 else "❌ NOT CERTIFIED"
        )
        cert_message = (
            "All tests passed. System ready for deployment."
            if summary["failed"] == 0
            else f"{summary['failed']} failures must be resolved."
        )

        html_content += f"""
        <div class="certification">
            <div class="certification-title">{cert_status}</div>
            <p style="color: #94a3b8; margin-top: 0.5rem;">{cert_message}</p>
        </div>
    </div>
</body>
</html>
"""

        with open(output_path, "w") as f:
            f.write(html_content)

        print(f"Generated HTML report: {output_path}")
        return output_path

    def run(self) -> int:
        """Run the report generator."""
        print("=" * 60)
        print("Aura IA V.1.9.8 - Test Report Generator")
        print("=" * 60)
        print()

        self.parse_junit_files()

        if self.results["summary"]["total_tests"] == 0:
            print("Warning: No test results found!")
            print(f"Make sure JUnit XML files exist in: {self.junit_dir}")
            return 1

        self.generate_json_report()
        self.generate_markdown_report()
        self.generate_html_report()

        print()
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        summary = self.results["summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Errors: {summary['errors']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"Duration: {summary['duration']:.2f}s")
        print()

        return 0 if summary["failed"] == 0 and summary["errors"] == 0 else 1


def main():
    """Main entry point."""
    report_dir = sys.argv[1] if len(sys.argv) > 1 else "test-reports"
    generator = TestReportGenerator(report_dir)
    sys.exit(generator.run())


if __name__ == "__main__":
    main()
