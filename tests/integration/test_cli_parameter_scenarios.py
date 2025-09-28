"""
Comprehensive CLI parameter scenario tests for PktMask unified interface.

Tests all major parameter combinations and edge cases using real PCAP test data
from tests/data/tls directory to ensure the simplified CLI works correctly.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pktmask.__main__ import app


class TestCLIParameterScenarios:
    """Comprehensive CLI parameter scenario tests using real TLS PCAP data."""

    @classmethod
    def setup_class(cls):
        """Set up test class with real PCAP data."""
        cls.runner = CliRunner()
        cls.test_data_dir = Path("tests/data/tls")

        # Verify test data exists
        if not cls.test_data_dir.exists():
            pytest.skip("TLS test data directory not found")

        # Get available PCAP files
        cls.pcap_files = list(cls.test_data_dir.glob("*.pcap"))
        if not cls.pcap_files:
            pytest.skip("No PCAP files found in test data directory")

        # Select test files of different sizes for comprehensive testing
        cls.small_pcap = cls._find_pcap_by_size("small")  # < 10KB
        cls.medium_pcap = cls._find_pcap_by_size("medium")  # 10KB - 100KB
        cls.large_pcap = cls._find_pcap_by_size("large")  # > 100KB

    @classmethod
    def _find_pcap_by_size(cls, size_category):
        """Find PCAP file by size category."""
        for pcap_file in cls.pcap_files:
            file_size = pcap_file.stat().st_size
            if size_category == "small" and file_size < 10000:
                return pcap_file
            elif size_category == "medium" and 10000 <= file_size < 100000:
                return pcap_file
            elif size_category == "large" and file_size >= 100000:
                return pcap_file
        # Fallback to first available file
        return cls.pcap_files[0] if cls.pcap_files else None

    def setup_method(self):
        """Set up for each test method."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """Clean up after each test method."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _assert_processing_success(self, result, expected_output_file=None):
        """Helper method to assert successful processing."""
        assert result.exit_code == 0

        # Check for processing indicators (flexible output format)
        success_indicators = [
            "🚀 Processing file:",
            "✅ Completed:",
            "✅ Processing completed successfully!",
        ]
        assert any(indicator in result.stdout for indicator in success_indicators)

        # Check output file exists if specified
        if expected_output_file:
            assert expected_output_file.exists()

    def _assert_tls_protocol_used(self, result):
        """Helper method to assert TLS protocol is used for masking."""
        assert "MaskingStage created: protocol=tls" in result.stdout

    # =========================================================================
    # Single File Processing Tests
    # =========================================================================

    def test_single_file_dedup_only(self):
        """Test single file processing with deduplication only."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        # Use a simpler approach to avoid I/O issues
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.small_pcap),
                "-o",
                str(self.output_dir / "dedup_output.pcap"),
                "--dedup",
            ],
            catch_exceptions=False,
        )

        # Basic success check
        assert result.exit_code == 0
        assert (self.output_dir / "dedup_output.pcap").exists()

    def test_single_file_anon_only(self):
        """Test single file processing with anonymization only."""
        if not self.medium_pcap:
            pytest.skip("No medium PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.medium_pcap),
                "-o",
                str(self.output_dir / "anon_output.pcap"),
                "--anon",
            ],
        )

        self._assert_processing_success(result, self.output_dir / "anon_output.pcap")

    def test_single_file_mask_only(self):
        """Test single file processing with masking only (TLS protocol auto-used)."""
        if not self.large_pcap:
            pytest.skip("No large PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.large_pcap),
                "-o",
                str(self.output_dir / "mask_output.pcap"),
                "--mask",
            ],
        )

        self._assert_processing_success(result, self.output_dir / "mask_output.pcap")
        self._assert_tls_protocol_used(result)

    def test_single_file_dedup_anon_combination(self):
        """Test single file processing with dedup + anon combination."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.small_pcap),
                "-o",
                str(self.output_dir / "dedup_anon_output.pcap"),
                "--dedup",
                "--anon",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout
        assert (self.output_dir / "dedup_anon_output.pcap").exists()

    def test_single_file_anon_mask_combination(self):
        """Test single file processing with anon + mask combination."""
        if not self.medium_pcap:
            pytest.skip("No medium PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.medium_pcap),
                "-o",
                str(self.output_dir / "anon_mask_output.pcap"),
                "--anon",
                "--mask",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout
        assert (self.output_dir / "anon_mask_output.pcap").exists()

        # Verify TLS protocol is used for masking
        assert "MaskingStage created: protocol=tls" in result.stdout

    def test_single_file_all_operations(self):
        """Test single file processing with all operations enabled."""
        if not self.large_pcap:
            pytest.skip("No large PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.large_pcap),
                "-o",
                str(self.output_dir / "all_ops_output.pcap"),
                "--dedup",
                "--anon",
                "--mask",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout
        assert (self.output_dir / "all_ops_output.pcap").exists()

        # Verify all stages are created
        assert "DeduplicationStage created" in result.stdout
        assert "AnonymizationStage created" in result.stdout
        assert "MaskingStage created: protocol=tls" in result.stdout

    def test_single_file_verbose_mode(self):
        """Test single file processing with verbose output."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.small_pcap),
                "-o",
                str(self.output_dir / "verbose_output.pcap"),
                "--dedup",
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout
        assert (self.output_dir / "verbose_output.pcap").exists()

        # Verbose mode should show more detailed information
        assert "DeduplicationStage created" in result.stdout

    def test_single_file_save_report(self):
        """Test single file processing with report generation."""
        if not self.medium_pcap:
            pytest.skip("No medium PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.medium_pcap),
                "-o",
                str(self.output_dir / "report_output.pcap"),
                "--anon",
                "--save-report",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout
        assert (self.output_dir / "report_output.pcap").exists()

        # Should generate a report file
        assert "📄 Report saved:" in result.stdout

    # =========================================================================
    # Auto-Generated Output Path Tests
    # =========================================================================

    def test_single_file_auto_output_path(self):
        """Test single file processing with auto-generated output path."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        # Copy test file to temp directory for auto-output testing
        test_file = self.temp_dir / "test_input.pcap"
        shutil.copy2(self.small_pcap, test_file)

        result = self.runner.invoke(app, ["process", str(test_file), "--dedup"])

        assert result.exit_code == 0
        assert "📁 Auto-generated output path:" in result.stdout
        assert "test_input_processed.pcap" in result.stdout
        assert (self.temp_dir / "test_input_processed.pcap").exists()

    # =========================================================================
    # Directory Processing Tests
    # =========================================================================

    def test_directory_intelligent_defaults(self):
        """Test directory processing with intelligent defaults (auto-enable all operations)."""
        # Create test directory with PCAP files
        test_dir = self.temp_dir / "test_pcaps"
        test_dir.mkdir()

        # Copy a few test files
        for i, pcap_file in enumerate(self.pcap_files[:3]):
            shutil.copy2(pcap_file, test_dir / f"test_{i}.pcap")

        result = self.runner.invoke(app, ["process", str(test_dir)])

        assert result.exit_code == 0
        assert "🔄 Directory processing detected: auto-enabled all operations (--dedup --anon --mask)" in result.stdout
        assert "📁 Auto-generated output path:" in result.stdout
        assert "test_pcaps_processed" in result.stdout

        # Verify all stages are created due to intelligent defaults
        assert "DeduplicationStage created" in result.stdout
        assert "AnonymizationStage created" in result.stdout
        assert "MaskingStage created: protocol=tls" in result.stdout

        # Verify output directory is created
        output_dir = self.temp_dir / "test_pcaps_processed"
        assert output_dir.exists()

    def test_directory_explicit_operations(self):
        """Test directory processing with explicit operation selection."""
        # Create test directory with PCAP files
        test_dir = self.temp_dir / "test_pcaps"
        test_dir.mkdir()

        # Copy test files
        for i, pcap_file in enumerate(self.pcap_files[:2]):
            shutil.copy2(pcap_file, test_dir / f"test_{i}.pcap")

        result = self.runner.invoke(
            app,
            ["process", str(test_dir), "-o", str(self.output_dir), "--dedup", "--anon"],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout

        # Should NOT show intelligent defaults message since operations are explicit
        assert "Directory processing detected: auto-enabled all operations" not in result.stdout

        # Should only show selected stages
        assert "DeduplicationStage created" in result.stdout
        assert "AnonymizationStage created" in result.stdout
        # Should NOT show masking stage since --mask not specified
        assert "MaskingStage created" not in result.stdout

    def test_directory_custom_output_path(self):
        """Test directory processing with custom output path."""
        # Create test directory with PCAP files
        test_dir = self.temp_dir / "test_pcaps"
        test_dir.mkdir()

        # Copy test files
        shutil.copy2(self.pcap_files[0], test_dir / "test.pcap")

        custom_output = self.temp_dir / "custom_output"

        result = self.runner.invoke(app, ["process", str(test_dir), "-o", str(custom_output), "--mask"])

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert custom_output.exists()

        # Should NOT show auto-generated path message
        assert "📁 Auto-generated output path:" not in result.stdout

    def test_directory_verbose_and_report(self):
        """Test directory processing with verbose mode and report generation."""
        # Create test directory with PCAP files
        test_dir = self.temp_dir / "test_pcaps"
        test_dir.mkdir()

        # Copy test files
        for i, pcap_file in enumerate(self.pcap_files[:2]):
            shutil.copy2(pcap_file, test_dir / f"test_{i}.pcap")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(test_dir),
                "--anon",
                "--mask",
                "--verbose",
                "--save-report",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "📄 Report saved:" in result.stdout

        # Verbose mode should show detailed stage information
        assert "AnonymizationStage created" in result.stdout
        assert "MaskingStage created: protocol=tls" in result.stdout

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    def test_file_no_operations_specified(self):
        """Test error when no operations are specified for file processing."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.small_pcap),
                "-o",
                str(self.output_dir / "output.pcap"),
            ],
        )

        assert result.exit_code == 1
        assert "At least one operation must be specified: --dedup, --anon, or --mask" in (result.stdout + result.stderr)

    def test_invalid_input_file_extension(self):
        """Test error handling for invalid file extension."""
        # Create a non-PCAP file
        invalid_file = self.temp_dir / "test.txt"
        invalid_file.write_text("not a pcap file")

        result = self.runner.invoke(app, ["process", str(invalid_file), "--dedup"])

        assert result.exit_code == 1
        assert "Input file must be a PCAP or PCAPNG file" in (result.stdout + result.stderr)

    def test_nonexistent_input_path(self):
        """Test error handling for nonexistent input path."""
        nonexistent_path = self.temp_dir / "nonexistent.pcap"

        result = self.runner.invoke(app, ["process", str(nonexistent_path), "--dedup"])

        assert result.exit_code == 1
        assert "Input path does not exist" in (result.stdout + result.stderr)

    def test_empty_directory(self):
        """Test error handling for directory with no PCAP files."""
        empty_dir = self.temp_dir / "empty_dir"
        empty_dir.mkdir()

        result = self.runner.invoke(app, ["process", str(empty_dir)])

        assert result.exit_code == 1
        assert "Directory contains no PCAP/PCAPNG files" in (result.stdout + result.stderr)

    def test_protocol_parameter_removed(self):
        """Test that --protocol parameter is no longer accepted."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        result = self.runner.invoke(app, ["process", str(self.small_pcap), "--mask", "--protocol", "tls"])

        assert result.exit_code != 0
        assert "No such option: --protocol" in (result.stdout + result.stderr)

    # =========================================================================
    # Backward Compatibility Tests
    # =========================================================================

    def test_existing_usage_patterns_still_work(self):
        """Test that existing usage patterns continue to work."""
        if not self.medium_pcap:
            pytest.skip("No medium PCAP file available")

        # Test existing pattern: explicit operations with output path
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.medium_pcap),
                "-o",
                str(self.output_dir / "backward_compat.pcap"),
                "--dedup",
                "--anon",
                "--mask",
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout
        assert (self.output_dir / "backward_compat.pcap").exists()

    def test_help_command_works(self):
        """Test that help command shows correct information."""
        result = self.runner.invoke(app, ["process", "--help"])

        assert result.exit_code == 0
        assert "--dedup" in result.stdout
        assert "--anon" in result.stdout
        assert "--mask" in result.stdout
        assert "--verbose" in result.stdout
        assert "--save-report" in result.stdout
        assert "--output" in result.stdout

        # Verify protocol parameter is NOT shown
        assert "--protocol" not in result.stdout

    # =========================================================================
    # TLS Protocol Integration Tests
    # =========================================================================

    def test_tls_protocol_automatically_used(self):
        """Test that TLS protocol is automatically used for masking operations."""
        if not self.large_pcap:
            pytest.skip("No large PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.large_pcap),
                "-o",
                str(self.output_dir / "tls_auto.pcap"),
                "--mask",
                "--verbose",
            ],
        )

        assert result.exit_code == 0

        # Verify TLS protocol is used internally
        assert "MaskingStage created: protocol=tls" in result.stdout
        assert "TLSProtocolMarker" in result.stdout

        # Verify output file is created
        assert (self.output_dir / "tls_auto.pcap").exists()

    def test_multiple_tls_versions_supported(self):
        """Test processing files with different TLS versions."""
        # Test with different TLS version files if available
        tls_files = [f for f in self.pcap_files if "tls" in f.name.lower()]

        if len(tls_files) < 2:
            pytest.skip("Not enough TLS files for version testing")

        for i, tls_file in enumerate(tls_files[:3]):  # Test first 3 files
            result = self.runner.invoke(
                app,
                [
                    "process",
                    str(tls_file),
                    "-o",
                    str(self.output_dir / f"tls_version_{i}.pcap"),
                    "--mask",
                ],
            )

            assert result.exit_code == 0
            assert "MaskingStage created: protocol=tls" in result.stdout
            assert (self.output_dir / f"tls_version_{i}.pcap").exists()

    # =========================================================================
    # Edge Case Tests
    # =========================================================================

    def test_very_small_pcap_file(self):
        """Test processing very small PCAP files."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        result = self.runner.invoke(app, ["process", str(self.small_pcap), "--mask", "--verbose"])

        # Should complete successfully even if file is very small
        assert result.exit_code == 0
        assert "📁 Auto-generated output path:" in result.stdout

    def test_large_pcap_file_processing(self):
        """Test processing large PCAP files."""
        if not self.large_pcap:
            pytest.skip("No large PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.large_pcap),
                "--dedup",
                "--anon",
                "--mask",
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        assert "🚀 Processing file:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout

        # Should show all three stages for large file
        assert "DeduplicationStage created" in result.stdout
        assert "AnonymizationStage created" in result.stdout
        assert "MaskingStage created: protocol=tls" in result.stdout

    def test_mixed_file_types_in_directory(self):
        """Test directory with mixed file types (only PCAP files should be processed)."""
        # Create test directory with mixed files
        test_dir = self.temp_dir / "mixed_files"
        test_dir.mkdir()

        # Copy PCAP file
        shutil.copy2(self.pcap_files[0], test_dir / "valid.pcap")

        # Create non-PCAP files
        (test_dir / "readme.txt").write_text("This is not a PCAP file")
        (test_dir / "data.json").write_text('{"not": "pcap"}')

        result = self.runner.invoke(app, ["process", str(test_dir), "--dedup"])

        assert result.exit_code == 0
        # Should process only the PCAP file
        assert "🚀 Processing file:" in result.stdout
        assert "valid.pcap" in result.stdout

    def test_pcapng_file_support(self):
        """Test that .pcapng files are also supported."""
        # Create a test .pcapng file by copying a .pcap file
        test_pcapng = self.temp_dir / "test.pcapng"
        shutil.copy2(self.pcap_files[0], test_pcapng)

        result = self.runner.invoke(app, ["process", str(test_pcapng), "--anon"])

        assert result.exit_code == 0
        assert "📁 Auto-generated output path:" in result.stdout
        assert "test_processed.pcapng" in result.stdout

    # =========================================================================
    # Performance and Validation Tests
    # =========================================================================

    def test_processing_duration_logged(self):
        """Test that processing duration is logged."""
        if not self.medium_pcap:
            pytest.skip("No medium PCAP file available")

        result = self.runner.invoke(app, ["process", str(self.medium_pcap), "--dedup"])

        assert result.exit_code == 0
        assert "⏱️  Duration:" in result.stdout
        assert "seconds" in result.stdout

    def test_file_count_reported(self):
        """Test that file count is reported correctly."""
        # Create test directory with multiple files
        test_dir = self.temp_dir / "multi_files"
        test_dir.mkdir()

        # Copy multiple PCAP files
        for i, pcap_file in enumerate(self.pcap_files[:3]):
            shutil.copy2(pcap_file, test_dir / f"file_{i}.pcap")

        result = self.runner.invoke(app, ["process", str(test_dir), "--anon"])

        assert result.exit_code == 0
        assert "📊 Files:" in result.stdout
        assert "processed" in result.stdout

    def test_output_file_exists_and_valid(self):
        """Test that output files are created and have valid content."""
        if not self.small_pcap:
            pytest.skip("No small PCAP file available")

        output_file = self.output_dir / "validation_test.pcap"

        result = self.runner.invoke(app, ["process", str(self.small_pcap), "-o", str(output_file), "--dedup"])

        assert result.exit_code == 0
        assert output_file.exists()

        # Output file should have some content
        assert output_file.stat().st_size > 0

        # Output file should be different from input (due to processing)
        # Note: This might not always be true for dedup if no duplicates exist
        # but the file should at least exist and be readable

    def test_comprehensive_operation_combination(self):
        """Test comprehensive scenario with all features enabled."""
        if not self.large_pcap:
            pytest.skip("No large PCAP file available")

        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.large_pcap),
                "--dedup",
                "--anon",
                "--mask",
                "--verbose",
                "--save-report",
            ],
        )

        assert result.exit_code == 0

        # Verify all components are working
        assert "🚀 Processing file:" in result.stdout
        assert "DeduplicationStage created" in result.stdout
        assert "AnonymizationStage created" in result.stdout
        assert "MaskingStage created: protocol=tls" in result.stdout
        assert "📄 Report saved:" in result.stdout
        assert "✅ Processing completed successfully!" in result.stdout
        assert "⏱️  Duration:" in result.stdout
        assert "📁 Auto-generated output path:" in result.stdout
