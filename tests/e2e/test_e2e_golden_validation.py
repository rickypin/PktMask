#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
E2E Golden Validation Tests

This module contains end-to-end tests that validate processing consistency
by comparing outputs against golden baselines.

Test Categories:
- Core Functionality Combinations (E2E-001 to E2E-007)
- Protocol Coverage (E2E-101 to E2E-106)
- Encapsulation Types (E2E-201 to E2E-203)
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import validation_details from conftest - must use absolute import
import tests.e2e.conftest as e2e_conftest
from src.pktmask.core.consistency import ConsistentProcessor

validation_details = e2e_conftest.validation_details


class TestE2EGoldenValidation:
    """End-to-end golden baseline validation tests"""

    @pytest.fixture(scope="class")
    def golden_baselines(self):
        """Load all golden baselines"""
        golden_dir = Path(__file__).parent / "golden"
        baselines = {}
        for baseline_file in golden_dir.glob("*_baseline.json"):
            baseline = json.loads(baseline_file.read_text())
            baselines[baseline["test_id"]] = baseline
        return baselines

    @pytest.fixture(autouse=True)
    def attach_validation_data(self, request):
        """Attach validation data to test item during test execution"""
        # Store reference to request for later use
        self._request = request
        yield

    def _record_validation(
        self, test_id: str, metric: str, baseline_val, current_val, match: bool = True, tolerance: str = ""
    ):
        """Record validation comparison for HTML report"""
        # Store in instance variable instead of global dict
        if not hasattr(self, "_validation_data"):
            self._validation_data = {
                "test_id": test_id,
                "validations": [],
                "baseline_comparison": {},
            }

        status = "MATCH" if match else "MISMATCH"
        if tolerance:
            status += f" (tolerance: {tolerance})"

        self._validation_data["baseline_comparison"][metric] = {
            "baseline": str(baseline_val),
            "current": str(current_val),
            "match": match,
            "status": status,
        }

        # Also attach to request node immediately
        if hasattr(self, "_request"):
            self._request.node._validation_data = self._validation_data

    def _record_check(self, test_id: str, description: str, passed: bool = True):
        """Record a validation check for HTML report"""
        # Store in instance variable instead of global dict
        if not hasattr(self, "_validation_data"):
            self._validation_data = {
                "test_id": test_id,
                "validations": [],
                "baseline_comparison": {},
            }

        self._validation_data["validations"].append(
            {
                "description": description,
                "passed": passed,
            }
        )

        # Also attach to request node immediately
        if hasattr(self, "_request"):
            self._request.node._validation_data = self._validation_data

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    # ========== Core Functionality Combination Tests ==========

    @pytest.mark.parametrize(
        "test_id,config,input_file",
        [
            ("E2E-001", {"dedup": True, "anon": False, "mask": False}, "tls_1_2-2.pcap"),
            ("E2E-002", {"dedup": False, "anon": True, "mask": False}, "tls_1_2-2.pcap"),
            ("E2E-003", {"dedup": False, "anon": False, "mask": True}, "tls_1_2-2.pcap"),
            ("E2E-004", {"dedup": True, "anon": True, "mask": False}, "tls_1_2-2.pcap"),
            ("E2E-005", {"dedup": True, "anon": False, "mask": True}, "tls_1_2-2.pcap"),
            ("E2E-006", {"dedup": False, "anon": True, "mask": True}, "tls_1_2-2.pcap"),
            ("E2E-007", {"dedup": True, "anon": True, "mask": True}, "tls_1_2-2.pcap"),
        ],
    )
    def test_core_functionality_consistency(
        self, test_id, config, input_file, golden_baselines, project_root, tmp_path
    ):
        """Validate core functionality combinations against golden baselines"""
        # 1. Get golden baseline
        baseline = golden_baselines[test_id]

        # 2. Run current version processing
        input_path = project_root / "tests" / "data" / "tls" / input_file
        output_path = tmp_path / f"{test_id}_output.pcap"

        result = self._run_processing(input_path, output_path, config)

        # 3. Verify processing succeeded
        assert result.success, f"Processing failed for {test_id}: {result.errors}"

        # Extract total packets from first stage
        total_packets = result.stage_stats[0].packets_processed if result.stage_stats else 0

        # 4. Verify output hash consistency
        output_hash = self._calculate_file_hash(output_path)
        hash_match = output_hash == baseline["output_hash"]
        self._record_validation(
            test_id,
            "Output File Hash (SHA256)",
            baseline["output_hash"][:16] + "...",
            output_hash[:16] + "...",
            hash_match,
        )
        self._record_check(test_id, "Output file hash matches baseline", hash_match)

        assert (
            output_hash == baseline["output_hash"]
        ), f"Output hash mismatch for {test_id}\nExpected: {baseline['output_hash']}\nGot: {output_hash}"

        # 5. Verify packet count consistency
        packet_count_match = total_packets == baseline["packet_count"]
        self._record_validation(test_id, "Packet Count", baseline["packet_count"], total_packets, packet_count_match)
        self._record_check(test_id, f"Packet count: {total_packets} == {baseline['packet_count']}", packet_count_match)

        assert (
            total_packets == baseline["packet_count"]
        ), f"Packet count mismatch for {test_id}\nExpected: {baseline['packet_count']}\nGot: {total_packets}"

        # 6. Verify file size consistency
        output_size = output_path.stat().st_size
        size_match = output_size == baseline["output_file_size"]
        self._record_validation(
            test_id, "Output File Size (bytes)", baseline["output_file_size"], output_size, size_match
        )
        self._record_check(test_id, f"File size: {output_size} == {baseline['output_file_size']}", size_match)

        assert (
            output_size == baseline["output_file_size"]
        ), f"File size mismatch for {test_id}\nExpected: {baseline['output_file_size']}\nGot: {output_size}"

        # 7. Verify statistics consistency
        self._verify_stats_consistency(result, baseline["stats"], test_id)

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
    def test_protocol_coverage_consistency(
        self, test_id, protocol, input_file, golden_baselines, project_root, tmp_path
    ):
        """Validate different protocol processing against golden baselines"""
        baseline = golden_baselines[test_id]

        # Use full feature configuration for protocol tests
        config = {"dedup": True, "anon": True, "mask": True}

        # Select test data directory based on protocol
        # All TLS/SSL files are in tests/data/tls, HTTP files are in tests/samples/http-collector
        if input_file.startswith("http"):
            input_path = project_root / "tests" / "samples" / "http-collector" / input_file
        else:
            input_path = project_root / "tests" / "data" / "tls" / input_file

        output_path = tmp_path / f"{test_id}_output.pcap"
        result = self._run_processing(input_path, output_path, config)

        # Verify processing succeeded
        assert result.success, f"Processing failed for {test_id} ({protocol}): {result.errors}"

        # Extract total packets from first stage
        total_packets = result.stage_stats[0].packets_processed if result.stage_stats else 0

        # Verify consistency
        output_hash = self._calculate_file_hash(output_path)
        hash_match = output_hash == baseline["output_hash"]
        self._record_validation(
            test_id,
            "Output File Hash (SHA256)",
            baseline["output_hash"][:16] + "...",
            output_hash[:16] + "...",
            hash_match,
        )
        self._record_check(test_id, f"Protocol {protocol}: Output file hash matches baseline", hash_match)

        assert (
            output_hash == baseline["output_hash"]
        ), f"Protocol {protocol} processing inconsistent for {test_id}\nExpected: {baseline['output_hash']}\nGot: {output_hash}"

        packet_count_match = total_packets == baseline["packet_count"]
        self._record_validation(test_id, "Packet Count", baseline["packet_count"], total_packets, packet_count_match)
        self._record_check(test_id, f"Protocol {protocol}: Packet count matches", packet_count_match)

        assert total_packets == baseline["packet_count"], f"Packet count mismatch for {protocol} ({test_id})"

        self._verify_stats_consistency(result, baseline["stats"], test_id)

    # ========== Encapsulation Type Tests ==========

    @pytest.mark.parametrize(
        "test_id,encap_type,input_file",
        [
            ("E2E-201", "Plain IP", "tls_1_2_plainip.pcap"),
            ("E2E-202", "Single VLAN", "tls_1_2_single_vlan.pcap"),
            ("E2E-203", "Double VLAN", "tls_1_2_double_vlan.pcap"),
        ],
    )
    def test_encapsulation_consistency(self, test_id, encap_type, input_file, golden_baselines, project_root, tmp_path):
        """Validate different encapsulation types against golden baselines"""
        baseline = golden_baselines[test_id]

        config = {"dedup": False, "anon": True, "mask": True}
        input_path = project_root / "tests" / "data" / "tls" / input_file
        output_path = tmp_path / f"{test_id}_output.pcap"

        result = self._run_processing(input_path, output_path, config)

        # Verify processing succeeded
        assert result.success, f"Processing failed for {test_id} ({encap_type}): {result.errors}"

        # Extract total packets from first stage
        total_packets = result.stage_stats[0].packets_processed if result.stage_stats else 0

        # Verify consistency
        output_hash = self._calculate_file_hash(output_path)
        hash_match = output_hash == baseline["output_hash"]
        self._record_validation(
            test_id,
            "Output File Hash (SHA256)",
            baseline["output_hash"][:16] + "...",
            output_hash[:16] + "...",
            hash_match,
        )
        self._record_check(test_id, f"Encapsulation {encap_type}: Output file hash matches baseline", hash_match)

        assert (
            output_hash == baseline["output_hash"]
        ), f"Encapsulation {encap_type} processing inconsistent for {test_id}\nExpected: {baseline['output_hash']}\nGot: {output_hash}"

        packet_count_match = total_packets == baseline["packet_count"]
        self._record_validation(test_id, "Packet Count", baseline["packet_count"], total_packets, packet_count_match)
        self._record_check(test_id, f"Encapsulation {encap_type}: Packet count matches", packet_count_match)

        assert total_packets == baseline["packet_count"], f"Packet count mismatch for {encap_type} ({test_id})"

        self._verify_stats_consistency(result, baseline["stats"], test_id)

    # ========== Helper Methods ==========

    def _run_processing(self, input_file, output_file, config):
        """Run processing using current version code"""
        executor = ConsistentProcessor.create_executor(
            dedup=config.get("dedup", False),
            anon=config.get("anon", False),
            mask=config.get("mask", False),
        )

        return executor.run(input_file, output_file)

    def _calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of a file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _verify_stats_consistency(self, result, baseline_stats, test_id: str = "Unknown"):
        """Verify statistics consistency with tolerance for timing"""
        # Extract total packets from first stage
        total_packets = result.stage_stats[0].packets_processed if result.stage_stats else 0

        # Verify packets processed
        self._record_validation(
            test_id,
            "Packets Processed",
            baseline_stats["packets_processed"],
            total_packets,
            total_packets == baseline_stats["packets_processed"],
        )
        self._record_check(
            test_id,
            f"Packets processed: {total_packets} == {baseline_stats['packets_processed']}",
            total_packets == baseline_stats["packets_processed"],
        )

        assert (
            total_packets == baseline_stats["packets_processed"]
        ), f"Packets processed mismatch\nExpected: {baseline_stats['packets_processed']}\nGot: {total_packets}"

        # Verify packets modified
        total_modified = sum(s.packets_modified for s in result.stage_stats)
        self._record_validation(
            test_id,
            "Packets Modified",
            baseline_stats["packets_modified"],
            total_modified,
            total_modified == baseline_stats["packets_modified"],
        )
        self._record_check(
            test_id,
            f"Packets modified: {total_modified} == {baseline_stats['packets_modified']}",
            total_modified == baseline_stats["packets_modified"],
        )

        assert (
            total_modified == baseline_stats["packets_modified"]
        ), f"Packets modified mismatch\nExpected: {baseline_stats['packets_modified']}\nGot: {total_modified}"

        # Verify duration (allow 200% tolerance or minimum 100ms for performance variations)
        # Duration can vary significantly based on system load, so we use a generous tolerance
        duration_tolerance = max(baseline_stats["duration_ms"] * 2.0, 100.0)
        duration_diff = abs(result.duration_ms - baseline_stats["duration_ms"])
        duration_match = duration_diff <= duration_tolerance

        self._record_validation(
            test_id,
            "Duration (ms)",
            f"{baseline_stats['duration_ms']:.2f}",
            f"{result.duration_ms:.2f}",
            duration_match,
            f"±{duration_tolerance:.0f}ms",
        )
        self._record_check(
            test_id,
            f"Duration within tolerance: {result.duration_ms:.2f}ms vs {baseline_stats['duration_ms']:.2f}ms (±{duration_tolerance:.0f}ms)",
            duration_match,
        )

        assert (
            duration_diff <= duration_tolerance
        ), f"Duration significantly different\nExpected: {baseline_stats['duration_ms']}ms\nGot: {result.duration_ms}ms\nDiff: {duration_diff}ms\nTolerance: {duration_tolerance}ms"

        # Verify stage count
        stage_count_match = len(result.stage_stats) == len(baseline_stats["stages"])
        self._record_validation(
            test_id, "Stage Count", len(baseline_stats["stages"]), len(result.stage_stats), stage_count_match
        )
        self._record_check(
            test_id, f"Stage count: {len(result.stage_stats)} == {len(baseline_stats['stages'])}", stage_count_match
        )

        assert len(result.stage_stats) == len(
            baseline_stats["stages"]
        ), f"Stage count mismatch\nExpected: {len(baseline_stats['stages'])}\nGot: {len(result.stage_stats)}"

        # Verify each stage
        for i, (current_stage, baseline_stage) in enumerate(zip(result.stage_stats, baseline_stats["stages"])):
            stage_name_match = current_stage.stage_name == baseline_stage["name"]
            self._record_check(test_id, f"Stage {i} ({baseline_stage['name']}): name matches", stage_name_match)

            assert (
                current_stage.stage_name == baseline_stage["name"]
            ), f"Stage {i} name mismatch\nExpected: {baseline_stage['name']}\nGot: {current_stage.stage_name}"

            packets_proc_match = current_stage.packets_processed == baseline_stage["packets_processed"]
            self._record_check(
                test_id,
                f"Stage {i} ({baseline_stage['name']}): packets processed {current_stage.packets_processed} == {baseline_stage['packets_processed']}",
                packets_proc_match,
            )

            assert (
                current_stage.packets_processed == baseline_stage["packets_processed"]
            ), f"Stage {i} packets processed mismatch"

            packets_mod_match = current_stage.packets_modified == baseline_stage["packets_modified"]
            self._record_check(
                test_id,
                f"Stage {i} ({baseline_stage['name']}): packets modified {current_stage.packets_modified} == {baseline_stage['packets_modified']}",
                packets_mod_match,
            )

            assert (
                current_stage.packets_modified == baseline_stage["packets_modified"]
            ), f"Stage {i} packets modified mismatch"
