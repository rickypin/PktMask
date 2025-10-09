#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
E2E Test Configuration and Fixtures

This module provides pytest configuration and fixtures for E2E tests,
including HTML report customization.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest
from _pytest.config import Config
from _pytest.nodes import Item
from _pytest.runner import CallInfo

# Store test results for summary report
test_results: List[Dict[str, Any]] = []

# Store validation details for each test
validation_details: Dict[str, Dict[str, Any]] = {}


@pytest.fixture
def validation_tracker(request):
    """Fixture to track validation details for each test"""
    test_id = "Unknown"

    # Extract test ID from test name
    if hasattr(request, "node"):
        test_name = request.node.name
        if "[E2E-" in test_name:
            import re

            match = re.search(r"E2E-\d+", test_name)
            if match:
                test_id = match.group(0)

    # Initialize validation details for this test
    validation_details[test_id] = {
        "test_id": test_id,
        "validations": [],
        "baseline_comparison": {},
    }

    yield validation_details[test_id]


def pytest_configure(config: Config):
    """Configure pytest with custom markers and metadata"""
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")

    # Add metadata for HTML report
    if hasattr(config, "_metadata"):
        config._metadata["Project"] = "PktMask"
        config._metadata["Test Suite"] = "End-to-End Golden Validation"
        config._metadata["Test Framework"] = "pytest + Golden File Testing"


def pytest_html_report_title(report):
    """Customize HTML report title"""
    report.title = "PktMask E2E Test Report"


def pytest_html_results_summary(prefix, summary, postfix):
    """Add custom summary section to HTML report"""
    prefix.extend(
        [
            "<h2>Test Suite Overview</h2>",
            "<p>This report contains end-to-end validation tests for PktMask using Golden File Testing methodology.</p>",
            "<h3>Test Categories:</h3>",
            "<ul>",
            "<li><strong>Core Functionality (E2E-001 to E2E-007):</strong> Tests various combinations of deduplication, anonymization, and masking</li>",
            "<li><strong>Protocol Coverage (E2E-101 to E2E-106):</strong> Tests different protocol versions (TLS 1.0/1.2/1.3, SSL 3.0, HTTP)</li>",
            "<li><strong>Encapsulation Types (E2E-201 to E2E-203):</strong> Tests different network encapsulation (Plain IP, Single/Double VLAN)</li>",
            "</ul>",
        ]
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: CallInfo):
    """Capture test results for custom reporting"""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        # Extract test information
        test_id = None
        test_name = item.name

        # Try to extract test ID from parametrize
        if hasattr(item, "callspec"):
            params = item.callspec.params
            if "test_id" in params:
                test_id = params["test_id"]
            elif "protocol" in params:
                test_id = params.get("test_id", "Unknown")

        # Store result
        result = {
            "test_id": test_id or test_name,
            "test_name": test_name,
            "outcome": report.outcome,
            "duration": report.duration,
            "timestamp": datetime.now().isoformat(),
        }

        # Add failure information if test failed
        if report.failed:
            result["error"] = str(report.longrepr)

        test_results.append(result)

        # Add extra HTML content to report using pytest-html
        from pytest_html import extras

        # Initialize extra list if it doesn't exist
        if not hasattr(report, "extra"):
            report.extra = []
        elif report.extra is None:
            report.extra = []

        # Get validation details from item object (attached by test fixture)
        test_validation = {}
        if hasattr(item, "_validation_data"):
            test_validation = item._validation_data

        validations = test_validation.get("validations", [])
        baseline_comp = test_validation.get("baseline_comparison", {})

        # Build validation details HTML
        validation_html = ""
        if validations or baseline_comp:
            validation_html = "<h4>Baseline Validation Results</h4>"

            # Add baseline comparison table
            if baseline_comp:
                validation_html += """
                <table class="baseline-comparison" style="width:100%; border-collapse: collapse; margin: 10px 0;">
                    <thead>
                        <tr style="background-color: #f0f0f0;">
                            <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Metric</th>
                            <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Baseline</th>
                            <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Current</th>
                            <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                """

                for metric, data in baseline_comp.items():
                    status_icon = "✅" if data.get("match", True) else "❌"
                    status_color = "green" if data.get("match", True) else "red"
                    baseline_val = data.get("baseline", "N/A")
                    current_val = data.get("current", "N/A")

                    validation_html += f"""
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>{metric}</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{baseline_val}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{current_val}</td>
                            <td style="padding: 8px; border: 1px solid #ddd; color: {status_color};">{status_icon} {data.get('status', 'OK')}</td>
                        </tr>
                    """

                validation_html += """
                    </tbody>
                </table>
                """

            # Add validation checks list
            if validations:
                validation_html += "<h5>Validation Checks Performed:</h5><ul style='margin: 10px 0;'>"
                for v in validations:
                    check_icon = "✅" if v.get("passed", True) else "❌"
                    validation_html += f"<li>{check_icon} {v.get('description', 'Unknown check')}</li>"
                validation_html += "</ul>"

        # Add test details
        extra_html = f"""
        <div class="test-details" style="margin: 15px 0; padding: 15px; background-color: #f9f9f9; border-radius: 5px;">
            <h4>Test Details</h4>
            <table style="width:100%; border-collapse: collapse;">
                <tr><th style="padding: 5px; text-align: left; width: 30%;">Test ID</th><td style="padding: 5px;">{test_id or 'N/A'}</td></tr>
                <tr><th style="padding: 5px; text-align: left;">Duration</th><td style="padding: 5px;">{report.duration:.3f}s</td></tr>
                <tr><th style="padding: 5px; text-align: left;">Status</th><td style="padding: 5px;" class="{report.outcome}">{report.outcome.upper()}</td></tr>
            </table>
            {validation_html}
        </div>
        """

        report.extra.append(extras.html(extra_html))


def pytest_html_results_table_header(cells):
    """Customize HTML report table headers"""
    cells.insert(1, "<th>Test ID</th>")
    cells.insert(2, "<th>Category</th>")
    cells.insert(3, "<th>Duration (s)</th>")


def pytest_html_results_table_row(report, cells):
    """Customize HTML report table rows"""
    # Extract test ID from test name
    test_id = "N/A"
    category = "Unknown"

    if hasattr(report, "nodeid"):
        # Parse test ID from node ID
        if "[E2E-" in report.nodeid:
            start = report.nodeid.index("[E2E-")
            end = report.nodeid.index("]", start)
            test_id = report.nodeid[start + 1 : end].split("-")[0] + "-" + report.nodeid[start + 1 : end].split("-")[1]

            # Determine category
            if test_id.startswith("E2E-00"):
                category = "Core Functionality"
            elif test_id.startswith("E2E-10"):
                category = "Protocol Coverage"
            elif test_id.startswith("E2E-20"):
                category = "Encapsulation"

    cells.insert(1, f"<td>{test_id}</td>")
    cells.insert(2, f"<td>{category}</td>")
    cells.insert(3, f"<td>{report.duration:.3f}</td>")


def pytest_sessionfinish(session, exitstatus):
    """Generate summary statistics after test session"""
    if not test_results:
        return

    # Calculate statistics
    total = len(test_results)
    passed = sum(1 for r in test_results if r["outcome"] == "passed")
    failed = sum(1 for r in test_results if r["outcome"] == "failed")
    skipped = sum(1 for r in test_results if r["outcome"] == "skipped")

    total_duration = sum(r["duration"] for r in test_results)
    avg_duration = total_duration / total if total > 0 else 0

    # Group by category
    core_tests = [r for r in test_results if r["test_id"].startswith("E2E-00")]
    protocol_tests = [r for r in test_results if r["test_id"].startswith("E2E-10")]
    encap_tests = [r for r in test_results if r["test_id"].startswith("E2E-20")]

    # Print summary to console
    print("\n" + "=" * 80)
    print("E2E TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests:     {total}")
    print(f"Passed:          {passed} ({passed/total*100:.1f}%)")
    print(f"Failed:          {failed} ({failed/total*100:.1f}%)")
    print(f"Skipped:         {skipped} ({skipped/total*100:.1f}%)")
    print(f"Total Duration:  {total_duration:.2f}s")
    print(f"Average Duration: {avg_duration:.3f}s")
    print("-" * 80)
    print(
        f"Core Functionality Tests:  {len(core_tests)} ({sum(1 for r in core_tests if r['outcome']=='passed')}/{len(core_tests)} passed)"
    )
    print(
        f"Protocol Coverage Tests:   {len(protocol_tests)} ({sum(1 for r in protocol_tests if r['outcome']=='passed')}/{len(protocol_tests)} passed)"
    )
    print(
        f"Encapsulation Tests:       {len(encap_tests)} ({sum(1 for r in encap_tests if r['outcome']=='passed')}/{len(encap_tests)} passed)"
    )
    print("=" * 80)

    # Save detailed results to JSON
    results_file = Path(__file__).parent / "test_results.json"
    results_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total_duration": total_duration,
            "average_duration": avg_duration,
        },
        "categories": {
            "core_functionality": {
                "total": len(core_tests),
                "passed": sum(1 for r in core_tests if r["outcome"] == "passed"),
                "failed": sum(1 for r in core_tests if r["outcome"] == "failed"),
            },
            "protocol_coverage": {
                "total": len(protocol_tests),
                "passed": sum(1 for r in protocol_tests if r["outcome"] == "passed"),
                "failed": sum(1 for r in protocol_tests if r["outcome"] == "failed"),
            },
            "encapsulation": {
                "total": len(encap_tests),
                "passed": sum(1 for r in encap_tests if r["outcome"] == "passed"),
                "failed": sum(1 for r in encap_tests if r["outcome"] == "failed"),
            },
        },
        "tests": test_results,
    }

    results_file.write_text(json.dumps(results_data, indent=2))
    print(f"\nDetailed results saved to: {results_file}")


def pytest_html_results_table_html(report, data):
    """Add custom CSS styling to HTML report"""
    if report.passed:
        data.append("<style>.passed { color: green; font-weight: bold; }</style>")
    elif report.failed:
        data.append("<style>.failed { color: red; font-weight: bold; }</style>")
    elif report.skipped:
        data.append("<style>.skipped { color: orange; font-weight: bold; }</style>")
