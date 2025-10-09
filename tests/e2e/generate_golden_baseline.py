#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Golden Baseline Generator for E2E Testing

This script generates golden baseline outputs for all E2E test cases.
Run this once on a stable version to create reference outputs for regression testing.

Usage:
    python tests/e2e/generate_golden_baseline.py
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pktmask.core.consistency import ConsistentProcessor


class GoldenBaselineGenerator:
    """Golden baseline generator for E2E testing"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.golden_dir = self.project_root / "tests" / "e2e" / "golden"
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
                "config": {"dedup": True, "anon": False, "mask": False},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-002",
                "name": "Anonymize Only",
                "config": {"dedup": False, "anon": True, "mask": False},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-003",
                "name": "Mask Only",
                "config": {"dedup": False, "anon": False, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-004",
                "name": "Dedup + Anonymize",
                "config": {"dedup": True, "anon": True, "mask": False},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-005",
                "name": "Dedup + Mask",
                "config": {"dedup": True, "anon": False, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-006",
                "name": "Anonymize + Mask",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-007",
                "name": "All Features",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            # ========== Protocol Coverage Tests ==========
            {
                "test_id": "E2E-101",
                "name": "TLS 1.0 Multi-Segment",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_0_multi_segment_google-https.pcap",
            },
            {
                "test_id": "E2E-102",
                "name": "TLS 1.2 Standard",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-103",
                "name": "TLS 1.3 with 0-RTT",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap",
            },
            {
                "test_id": "E2E-104",
                "name": "SSL 3.0",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/ssl_3.pcap",
            },
            {
                "test_id": "E2E-105",
                "name": "HTTP Download",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/samples/http-collector/http-download-good.pcap",
            },
            {
                "test_id": "E2E-106",
                "name": "HTTP 500 Error",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/samples/http-collector/http-500error.pcap",
            },
            # ========== Encapsulation Type Tests ==========
            {
                "test_id": "E2E-201",
                "name": "Plain IP",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2_plainip.pcap",
            },
            {
                "test_id": "E2E-202",
                "name": "Single VLAN",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2_single_vlan.pcap",
            },
            {
                "test_id": "E2E-203",
                "name": "Double VLAN",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2_double_vlan.pcap",
            },
        ]

    def generate_all_baselines(self):
        """Generate all golden baselines"""
        print("🚀 Starting Golden Baseline Generation")
        print(f"📁 Golden directory: {self.golden_dir}")
        print(f"📊 Total test cases: {len(self.test_cases)}\n")

        success_count = 0
        failed_cases = []

        for test_case in self.test_cases:
            try:
                print(f"Processing {test_case['test_id']}: {test_case['name']}...")
                baseline = self.generate_baseline(test_case)
                success_count += 1
                print(f"  ✅ Generated baseline")
                print(f"     Output hash: {baseline['output_hash'][:16]}...")
                print(f"     Packets: {baseline['packet_count']}\n")
            except Exception as e:
                failed_cases.append((test_case["test_id"], str(e)))
                print(f"  ❌ Failed: {e}\n")

        # Print summary
        print("=" * 60)
        print(f"✅ Success: {success_count}/{len(self.test_cases)}")
        if failed_cases:
            print(f"❌ Failed: {len(failed_cases)}")
            for test_id, error in failed_cases:
                print(f"   - {test_id}: {error}")
        print("=" * 60)

        return success_count == len(self.test_cases)

    def generate_baseline(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Generate golden baseline for a single test case"""
        test_id = test_case["test_id"]
        config = test_case["config"]
        input_file = self.project_root / test_case["input_file"]

        # Validate input file exists
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Prepare output file
        output_file = self.golden_dir / f"{test_id}_output.pcap"

        # Run processing
        executor = ConsistentProcessor.create_executor(
            dedup=config.get("dedup", False),
            anon=config.get("anon", False),
            mask=config.get("mask", False),
        )

        result = executor.run(input_file, output_file)

        # Check if processing was successful
        if not result.success:
            raise RuntimeError(f"Processing failed: {', '.join(result.errors)}")

        # Calculate hashes
        input_hash = self._calculate_file_hash(input_file)
        output_hash = self._calculate_file_hash(output_file)

        # Extract total packets from first stage (all stages process same packets)
        total_packets = result.stage_stats[0].packets_processed if result.stage_stats else 0

        # Extract statistics
        stats = {
            "packets_processed": total_packets,
            "packets_modified": sum(s.packets_modified for s in result.stage_stats),
            "duration_ms": result.duration_ms,
            "stages": [
                {
                    "name": s.stage_name,
                    "packets_processed": s.packets_processed,
                    "packets_modified": s.packets_modified,
                    "duration_ms": s.duration_ms,
                }
                for s in result.stage_stats
            ],
        }

        # Build baseline data
        baseline = {
            "test_id": test_id,
            "name": test_case["name"],
            "input_file": test_case["input_file"],
            "input_hash": input_hash,
            "config": config,
            "output_hash": output_hash,
            "output_file_size": output_file.stat().st_size,
            "packet_count": total_packets,
            "stats": stats,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0",
        }

        # Save baseline file
        baseline_file = self.golden_dir / f"{test_id}_baseline.json"
        baseline_file.write_text(json.dumps(baseline, indent=2))

        return baseline

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


def main():
    """Main function"""
    generator = GoldenBaselineGenerator()
    success = generator.generate_all_baselines()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
