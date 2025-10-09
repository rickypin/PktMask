#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
E2E CLI Blackbox Tests

This module contains completely decoupled end-to-end tests that validate
PktMask through its CLI interface only, without any dependency on internal
Python APIs or data structures.

Test Philosophy:
- Pure blackbox testing through CLI
- No imports from src/pktmask (except for path resolution)
- Only validates output file integrity (SHA256 hash)
- Completely isolated from internal code changes
- Tests the actual user interface (CLI)
- Uses CLI-generated golden baselines (golden_cli/) for 100% decoupling

Complete Decoupling:
- Code: No internal imports ✅
- Execution: subprocess CLI calls ✅
- Validation: Only SHA256 hash ✅
- Baselines: Generated via CLI ✅
- Decoupling Level: 100% ✅

Test Categories:
- Core Functionality Combinations (E2E-001 to E2E-007)
- Protocol Coverage (E2E-101 to E2E-106)
- Encapsulation Types (E2E-201 to E2E-203)
"""

import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Configure logger for CLI output capture
logger = logging.getLogger(__name__)


class TestE2ECLIBlackbox:
    """Completely decoupled CLI blackbox tests"""

    @pytest.fixture(scope="class")
    def cli_executable(self):
        """Get CLI executable path"""
        project_root = Path(__file__).parent.parent.parent

        # Try different CLI entry points
        cli_paths = [
            project_root / "pktmask",  # Shell script
            project_root / "pktmask_launcher.py",  # Python launcher
        ]

        for cli_path in cli_paths:
            if cli_path.exists():
                return str(cli_path)

        # Fallback to python -m pktmask
        return None

    @pytest.fixture(scope="class")
    def golden_baselines(self):
        """Load all CLI golden baselines (completely decoupled from API)"""
        golden_dir = Path(__file__).parent / "golden_cli"
        baselines = {}
        for baseline_file in golden_dir.glob("*_baseline.json"):
            baseline = json.loads(baseline_file.read_text())
            baselines[baseline["test_id"]] = baseline
        return baselines

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _run_cli_command(
        self,
        cli_executable: str,
        input_path: Path,
        output_path: Path,
        dedup: bool = False,
        anon: bool = False,
        mask: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run PktMask CLI command and capture output for pytest logs"""

        # Build command
        if cli_executable:
            # Use shell script or launcher
            cmd = [sys.executable, cli_executable, "process"]
        else:
            # Use python -m pktmask
            cmd = [sys.executable, "-m", "pktmask", "process"]

        # Add arguments
        cmd.extend([str(input_path), "-o", str(output_path)])

        if dedup:
            cmd.append("--dedup")
        if anon:
            cmd.append("--anon")
        if mask:
            cmd.append("--mask")

        # Log command being executed
        logger.info(f"Executing CLI command: {' '.join(cmd)}")

        # Run command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout
        )

        # Log output to pytest capture (this will appear in HTML report)
        if result.stdout:
            logger.info(f"CLI STDOUT:\n{result.stdout}")
            # Also print to ensure pytest captures it
            print(f"\n=== CLI STDOUT ===\n{result.stdout}")

        if result.stderr:
            logger.warning(f"CLI STDERR:\n{result.stderr}")
            # Also print to ensure pytest captures it
            print(f"\n=== CLI STDERR ===\n{result.stderr}")

        logger.info(f"CLI exit code: {result.returncode}")
        print(f"\n=== CLI Exit Code: {result.returncode} ===")

        return result

    # ========== Core Functionality Combination Tests ==========

    @pytest.mark.parametrize(
        "test_id,dedup,anon,mask,input_file",
        [
            ("E2E-001", True, False, False, "tls_1_2-2.pcap"),
            ("E2E-002", False, True, False, "tls_1_2-2.pcap"),
            ("E2E-003", False, False, True, "tls_1_2-2.pcap"),
            ("E2E-004", True, True, False, "tls_1_2-2.pcap"),
            ("E2E-005", True, False, True, "tls_1_2-2.pcap"),
            ("E2E-006", False, True, True, "tls_1_2-2.pcap"),
            ("E2E-007", True, True, True, "tls_1_2-2.pcap"),
        ],
    )
    def test_cli_core_functionality_consistency(
        self, test_id, dedup, anon, mask, input_file, golden_baselines, project_root, cli_executable, tmp_path
    ):
        """Validate core functionality through CLI against golden baselines"""
        logger.info(f"Starting test {test_id}: dedup={dedup}, anon={anon}, mask={mask}")
        print(f"\n{'='*60}\nTest {test_id}: Core Functionality Test\n{'='*60}")

        # 1. Get golden baseline
        baseline = golden_baselines[test_id]
        logger.info(f"Loaded baseline for {test_id}: expected hash={baseline['output_hash'][:16]}...")

        # 2. Run CLI command
        input_path = project_root / "tests" / "data" / "tls" / input_file
        output_path = tmp_path / f"{test_id}_cli_output.pcap"

        # Get input file metrics
        input_size = input_path.stat().st_size
        logger.info(f"Input file: {input_path} ({input_size} bytes)")
        print(f"Input:  {input_path} ({input_size:,} bytes)")

        result = self._run_cli_command(cli_executable, input_path, output_path, dedup, anon, mask)

        # 3. Verify CLI succeeded
        assert result.returncode == 0, (
            f"CLI command failed for {test_id}\n" f"STDOUT: {result.stdout}\n" f"STDERR: {result.stderr}"
        )

        # 4. Verify output file exists and get metrics
        assert output_path.exists(), f"Output file not created for {test_id}"
        output_size = output_path.stat().st_size

        # Calculate size change
        size_change = output_size - input_size
        size_change_pct = (size_change / input_size * 100) if input_size > 0 else 0

        logger.info(f"Output file created successfully: {output_size} bytes")
        logger.info(f"Size change: {size_change:+d} bytes ({size_change_pct:+.2f}%)")

        print(f"\n{'─'*60}")
        print(f"📊 File Metrics:")
        print(f"  Input size:   {input_size:>10,} bytes")
        print(f"  Output size:  {output_size:>10,} bytes")
        print(f"  Change:       {size_change:>+10,} bytes ({size_change_pct:+.2f}%)")
        print(f"{'─'*60}\n")

        # 5. Verify output file hash (ONLY validation - pure blackbox)
        output_hash = self._calculate_file_hash(output_path)
        logger.info(f"Calculated output hash: {output_hash[:16]}...")
        print(f"🔐 Hash Verification:")
        print(f"  Expected: {baseline['output_hash'][:16]}...")
        print(f"  Actual:   {output_hash[:16]}...")

        assert output_hash == baseline["output_hash"], (
            f"CLI output inconsistent for {test_id}\n"
            f"Expected hash: {baseline['output_hash']}\n"
            f"Got hash: {output_hash}\n"
            f"This indicates the CLI output has changed from the baseline."
        )

        logger.info(f"Test {test_id} PASSED: Hash matches baseline")
        print(f"  Status:   ✅ MATCH\n")
        print(f"✅ Test {test_id} PASSED\n")

    # ========== Protocol Coverage Tests ==========

    @pytest.mark.parametrize(
        "test_id,protocol,input_file",
        [
            ("E2E-101", "TLS 1.0", "tls_1_0_multi_segment_google-https.pcap"),
            ("E2E-102", "TLS 1.2", "tls_1_2-2.pcap"),
            ("E2E-103", "TLS 1.3", "tls_1_3_0-RTT-2_22_23_mix.pcap"),
            ("E2E-104", "SSL 3.0", "ssl_3.pcap"),
            ("E2E-105", "HTTP", "http-download-good.pcap"),
            ("E2E-106", "HTTP Error", "http-500error.pcap"),
        ],
    )
    def test_cli_protocol_coverage_consistency(
        self, test_id, protocol, input_file, golden_baselines, project_root, cli_executable, tmp_path
    ):
        """Validate protocol coverage through CLI against golden baselines"""
        logger.info(f"Starting test {test_id}: Protocol={protocol}")
        print(f"\n{'='*60}\nTest {test_id}: Protocol Coverage - {protocol}\n{'='*60}")

        # 1. Get golden baseline
        baseline = golden_baselines[test_id]
        logger.info(f"Loaded baseline for {test_id}: expected hash={baseline['output_hash'][:16]}...")

        # 2. Determine input path
        if input_file.startswith("http"):
            input_path = project_root / "tests" / "samples" / "http-collector" / input_file
        else:
            input_path = project_root / "tests" / "data" / "tls" / input_file

        output_path = tmp_path / f"{test_id}_cli_output.pcap"

        # Get input file metrics
        input_size = input_path.stat().st_size
        logger.info(f"Input file: {input_path} ({input_size} bytes)")
        print(f"Input:  {input_path} ({input_size:,} bytes)")

        # 3. Run CLI with all features enabled
        result = self._run_cli_command(cli_executable, input_path, output_path, dedup=True, anon=True, mask=True)

        # 4. Verify CLI succeeded
        assert result.returncode == 0, (
            f"CLI command failed for {test_id} ({protocol})\n" f"STDOUT: {result.stdout}\n" f"STDERR: {result.stderr}"
        )

        # 5. Verify output file exists and get metrics
        assert output_path.exists(), f"Output file not created for {test_id}"
        output_size = output_path.stat().st_size

        # Calculate size change
        size_change = output_size - input_size
        size_change_pct = (size_change / input_size * 100) if input_size > 0 else 0

        logger.info(f"Output file created successfully: {output_size} bytes")
        logger.info(f"Size change: {size_change:+d} bytes ({size_change_pct:+.2f}%)")

        print(f"\n{'─'*60}")
        print(f"📊 File Metrics ({protocol}):")
        print(f"  Input size:   {input_size:>10,} bytes")
        print(f"  Output size:  {output_size:>10,} bytes")
        print(f"  Change:       {size_change:>+10,} bytes ({size_change_pct:+.2f}%)")
        print(f"{'─'*60}\n")

        # 6. Verify output file hash (ONLY validation - pure blackbox)
        output_hash = self._calculate_file_hash(output_path)
        logger.info(f"Calculated output hash: {output_hash[:16]}...")
        print(f"🔐 Hash Verification:")
        print(f"  Expected: {baseline['output_hash'][:16]}...")
        print(f"  Actual:   {output_hash[:16]}...")

        assert output_hash == baseline["output_hash"], (
            f"CLI output inconsistent for {test_id} ({protocol})\n"
            f"Expected hash: {baseline['output_hash']}\n"
            f"Got hash: {output_hash}"
        )

        logger.info(f"Test {test_id} PASSED: Hash matches baseline")
        print(f"  Status:   ✅ MATCH\n")
        print(f"✅ Test {test_id} PASSED\n")

    # ========== Encapsulation Type Tests ==========

    @pytest.mark.parametrize(
        "test_id,encap_type,input_file",
        [
            ("E2E-201", "Plain IP", "tls_1_2_plainip.pcap"),
            ("E2E-202", "Single VLAN", "tls_1_2_single_vlan.pcap"),
            ("E2E-203", "Double VLAN", "tls_1_2_double_vlan.pcap"),
        ],
    )
    def test_cli_encapsulation_consistency(
        self, test_id, encap_type, input_file, golden_baselines, project_root, cli_executable, tmp_path
    ):
        """Validate encapsulation types through CLI against golden baselines"""
        logger.info(f"Starting test {test_id}: Encapsulation={encap_type}")
        print(f"\n{'='*60}\nTest {test_id}: Encapsulation - {encap_type}\n{'='*60}")

        # 1. Get golden baseline
        baseline = golden_baselines[test_id]
        logger.info(f"Loaded baseline for {test_id}: expected hash={baseline['output_hash'][:16]}...")

        # 2. Run CLI command
        input_path = project_root / "tests" / "data" / "tls" / input_file
        output_path = tmp_path / f"{test_id}_cli_output.pcap"

        # Get input file metrics
        input_size = input_path.stat().st_size
        logger.info(f"Input file: {input_path} ({input_size} bytes)")
        print(f"Input:  {input_path} ({input_size:,} bytes)")

        result = self._run_cli_command(cli_executable, input_path, output_path, dedup=False, anon=True, mask=True)

        # 3. Verify CLI succeeded
        assert result.returncode == 0, (
            f"CLI command failed for {test_id} ({encap_type})\n" f"STDOUT: {result.stdout}\n" f"STDERR: {result.stderr}"
        )

        # 4. Verify output file exists and get metrics
        assert output_path.exists(), f"Output file not created for {test_id}"
        output_size = output_path.stat().st_size

        # Calculate size change
        size_change = output_size - input_size
        size_change_pct = (size_change / input_size * 100) if input_size > 0 else 0

        logger.info(f"Output file created successfully: {output_size} bytes")
        logger.info(f"Size change: {size_change:+d} bytes ({size_change_pct:+.2f}%)")

        print(f"\n{'─'*60}")
        print(f"📊 File Metrics ({encap_type}):")
        print(f"  Input size:   {input_size:>10,} bytes")
        print(f"  Output size:  {output_size:>10,} bytes")
        print(f"  Change:       {size_change:>+10,} bytes ({size_change_pct:+.2f}%)")
        print(f"{'─'*60}\n")

        # 5. Verify output file hash (ONLY validation - pure blackbox)
        output_hash = self._calculate_file_hash(output_path)
        logger.info(f"Calculated output hash: {output_hash[:16]}...")
        print(f"🔐 Hash Verification:")
        print(f"  Expected: {baseline['output_hash'][:16]}...")
        print(f"  Actual:   {output_hash[:16]}...")

        assert output_hash == baseline["output_hash"], (
            f"CLI output inconsistent for {test_id} ({encap_type})\n"
            f"Expected hash: {baseline['output_hash']}\n"
            f"Got hash: {output_hash}"
        )

        logger.info(f"Test {test_id} PASSED: Hash matches baseline")
        print(f"  Status:   ✅ MATCH\n")
        print(f"✅ Test {test_id} PASSED\n")
