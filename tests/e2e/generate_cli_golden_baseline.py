#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI Golden Baseline Generator for E2E Testing

This script generates golden baseline outputs using ONLY the CLI interface,
ensuring complete decoupling from internal APIs.

Key Features:
- Uses subprocess to call CLI (no API imports)
- Only stores output file hash (minimal data)
- Completely independent from internal code
- True blackbox baseline generation

Usage:
    python tests/e2e/generate_cli_golden_baseline.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class CLIGoldenBaselineGenerator:
    """CLI-only golden baseline generator for E2E testing"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.golden_dir = self.project_root / "tests" / "e2e" / "golden_cli"
        self.golden_dir.mkdir(parents=True, exist_ok=True)

        # Define all test cases
        self.test_cases = self._define_test_cases()

    def _define_test_cases(self) -> List[Dict[str, Any]]:
        """Define all test cases according to E2E_TEST_PLAN.md"""
        return [
            # ========== Core Functionality Combination Tests ==========
            {
                "test_id": "E2E-001",
                "name": "Dedup Only",
                "cli_args": ["--dedup"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-002",
                "name": "Anonymize Only",
                "cli_args": ["--anon"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-003",
                "name": "Mask Only",
                "cli_args": ["--mask"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-004",
                "name": "Dedup + Anonymize",
                "cli_args": ["--dedup", "--anon"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-005",
                "name": "Dedup + Mask",
                "cli_args": ["--dedup", "--mask"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-006",
                "name": "Anonymize + Mask",
                "cli_args": ["--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-007",
                "name": "All Features",
                "cli_args": ["--dedup", "--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            # ========== Protocol Coverage Tests ==========
            {
                "test_id": "E2E-101",
                "name": "TLS 1.0 Protocol",
                "cli_args": ["--dedup", "--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_0_multi_segment_google-https.pcap",
            },
            {
                "test_id": "E2E-102",
                "name": "TLS 1.2 Protocol",
                "cli_args": ["--dedup", "--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-103",
                "name": "TLS 1.3 Protocol",
                "cli_args": ["--dedup", "--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap",
            },
            {
                "test_id": "E2E-104",
                "name": "SSL 3.0 Protocol",
                "cli_args": ["--dedup", "--anon", "--mask"],
                "input_file": "tests/data/tls/ssl_3.pcap",
            },
            {
                "test_id": "E2E-105",
                "name": "HTTP Protocol",
                "cli_args": ["--dedup", "--anon", "--mask"],
                "input_file": "tests/samples/http-collector/http-download-good.pcap",
            },
            {
                "test_id": "E2E-106",
                "name": "HTTP Error Response",
                "cli_args": ["--dedup", "--anon", "--mask"],
                "input_file": "tests/samples/http-collector/http-500error.pcap",
            },
            # ========== Encapsulation Type Tests ==========
            {
                "test_id": "E2E-201",
                "name": "Plain IP Encapsulation",
                "cli_args": ["--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_2_plainip.pcap",
            },
            {
                "test_id": "E2E-202",
                "name": "Single VLAN Encapsulation",
                "cli_args": ["--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_2_single_vlan.pcap",
            },
            {
                "test_id": "E2E-203",
                "name": "Double VLAN Encapsulation",
                "cli_args": ["--anon", "--mask"],
                "input_file": "tests/data/tls/tls_1_2_double_vlan.pcap",
            },
        ]

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _run_cli_command(self, input_path: Path, output_path: Path, cli_args: List[str]) -> bool:
        """Run PktMask CLI command"""
        # Build command
        cmd = [sys.executable, "-m", "pktmask", "process"]
        cmd.extend([str(input_path), "-o", str(output_path)])
        cmd.extend(cli_args)

        # Run command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        return result.returncode == 0

    def generate_baseline(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Generate golden baseline for a single test case using CLI"""
        test_id = test_case["test_id"]
        print(f"\n{'='*60}")
        print(f"Generating CLI baseline for {test_id}: {test_case['name']}")
        print(f"{'='*60}")

        # Prepare paths
        input_path = self.project_root / test_case["input_file"]
        output_path = self.golden_dir / f"{test_id}_output.pcap"

        # Verify input file exists
        if not input_path.exists():
            print(f"❌ Input file not found: {input_path}")
            return None

        # Run CLI command
        print(f"Running CLI: python -m pktmask process {input_path} -o {output_path} {' '.join(test_case['cli_args'])}")
        success = self._run_cli_command(input_path, output_path, test_case["cli_args"])

        if not success:
            print(f"❌ CLI command failed for {test_id}")
            return None

        # Verify output file exists
        if not output_path.exists():
            print(f"❌ Output file not created: {output_path}")
            return None

        # Calculate hashes
        input_hash = self._calculate_file_hash(input_path)
        output_hash = self._calculate_file_hash(output_path)

        # Create baseline metadata (minimal - only hash)
        baseline = {
            "test_id": test_id,
            "name": test_case["name"],
            "input_file": test_case["input_file"],
            "input_hash": input_hash,
            "cli_args": test_case["cli_args"],
            "output_hash": output_hash,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0-cli",
            "note": "Generated using CLI only - completely decoupled from API",
        }

        # Save baseline metadata
        baseline_file = self.golden_dir / f"{test_id}_baseline.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline, f, indent=2)

        print(f"✅ Baseline generated successfully")
        print(f"   Input hash:  {input_hash}")
        print(f"   Output hash: {output_hash}")
        print(f"   Baseline:    {baseline_file}")
        print(f"   Output:      {output_path}")

        return baseline

    def generate_all_baselines(self):
        """Generate all golden baselines"""
        print("\n" + "=" * 80)
        print("CLI GOLDEN BASELINE GENERATOR")
        print("=" * 80)
        print(f"Project root: {self.project_root}")
        print(f"Golden dir:   {self.golden_dir}")
        print(f"Total tests:  {len(self.test_cases)}")
        print("=" * 80)

        results = {"success": [], "failed": []}

        for test_case in self.test_cases:
            baseline = self.generate_baseline(test_case)
            if baseline:
                results["success"].append(test_case["test_id"])
            else:
                results["failed"].append(test_case["test_id"])

        # Print summary
        print("\n" + "=" * 80)
        print("GENERATION SUMMARY")
        print("=" * 80)
        print(f"✅ Successful: {len(results['success'])}/{len(self.test_cases)}")
        print(f"❌ Failed:     {len(results['failed'])}/{len(self.test_cases)}")

        if results["failed"]:
            print(f"\nFailed tests: {', '.join(results['failed'])}")

        print("=" * 80)

        return results


def main():
    """Main entry point"""
    generator = CLIGoldenBaselineGenerator()
    results = generator.generate_all_baselines()

    # Exit with error if any tests failed
    if results["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
