"""
Simplified CLI parameter scenario tests for PktMask unified interface.

Focuses on core functionality validation without complex I/O handling.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pktmask.__main__ import app


class TestCLISimplifiedScenarios:
    """Simplified CLI parameter scenario tests."""

    @classmethod
    def setup_class(cls):
        """Set up test class."""
        cls.runner = CliRunner()
        cls.test_data_dir = Path("tests/data/tls")

        # Verify test data exists
        if not cls.test_data_dir.exists():
            pytest.skip("TLS test data directory not found")

        # Get available PCAP files
        cls.pcap_files = list(cls.test_data_dir.glob("*.pcap"))
        if not cls.pcap_files:
            pytest.skip("No PCAP files found in test data directory")

        # Use first available file for testing
        cls.test_pcap = cls.pcap_files[0]

    def setup_method(self):
        """Set up for each test method."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """Clean up after each test method."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    # =========================================================================
    # Core Functionality Tests
    # =========================================================================

    def test_help_command_shows_simplified_interface(self):
        """Test that help command shows simplified interface without protocol parameter."""
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

    def test_protocol_parameter_rejected(self):
        """Test that --protocol parameter is no longer accepted."""
        result = self.runner.invoke(
            app, ["process", str(self.test_pcap), "--mask", "--protocol", "tls"]
        )

        assert result.exit_code != 0
        assert "No such option: --protocol" in (result.stdout + result.stderr)

    def test_file_requires_operation_flags(self):
        """Test that file processing requires explicit operation flags."""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_pcap),
                "-o",
                str(self.output_dir / "output.pcap"),
            ],
        )

        assert result.exit_code == 1
        assert (
            "At least one operation must be specified: --dedup, --anon, or --mask"
            in (result.stdout + result.stderr)
        )

    def test_directory_intelligent_defaults_message(self):
        """Test directory processing shows intelligent defaults message."""
        # Create test directory with PCAP files
        test_dir = self.temp_dir / "test_pcaps"
        test_dir.mkdir()
        shutil.copy2(self.test_pcap, test_dir / "test.pcap")

        result = self.runner.invoke(app, ["process", str(test_dir)])

        # Should show intelligent defaults message
        assert (
            "🔄 Directory processing detected: auto-enabled all operations (--dedup --anon --mask)"
            in result.stdout
        )
        assert "📁 Auto-generated output path:" in result.stdout

    def test_auto_output_path_generation(self):
        """Test auto-generated output path functionality."""
        # Copy test file to temp directory
        test_file = self.temp_dir / "test_input.pcap"
        shutil.copy2(self.test_pcap, test_file)

        result = self.runner.invoke(app, ["process", str(test_file), "--dedup"])

        assert "📁 Auto-generated output path:" in result.stdout
        assert "test_input_processed.pcap" in result.stdout

    def test_invalid_file_extension_error(self):
        """Test error handling for invalid file extension."""
        # Create a non-PCAP file
        invalid_file = self.temp_dir / "test.txt"
        invalid_file.write_text("not a pcap file")

        result = self.runner.invoke(app, ["process", str(invalid_file), "--dedup"])

        assert result.exit_code == 1
        assert "Input file must be a PCAP or PCAPNG file" in (
            result.stdout + result.stderr
        )

    def test_nonexistent_path_error(self):
        """Test error handling for nonexistent input path."""
        nonexistent_path = self.temp_dir / "nonexistent.pcap"

        result = self.runner.invoke(app, ["process", str(nonexistent_path), "--dedup"])

        assert result.exit_code == 1
        assert "Input path does not exist" in (result.stdout + result.stderr)

    def test_empty_directory_error(self):
        """Test error handling for directory with no PCAP files."""
        empty_dir = self.temp_dir / "empty_dir"
        empty_dir.mkdir()

        result = self.runner.invoke(app, ["process", str(empty_dir)])

        assert result.exit_code == 1
        assert "Directory contains no PCAP/PCAP files" in (
            result.stdout + result.stderr
        )

    # =========================================================================
    # TLS Protocol Integration Tests
    # =========================================================================

    def test_mask_operation_uses_tls_protocol(self):
        """Test that mask operation automatically uses TLS protocol."""
        # Test with a small operation that should complete quickly
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_pcap),
                "-o",
                str(self.output_dir / "mask_test.pcap"),
                "--mask",
            ],
            standalone_mode=False,
        )

        # Should complete successfully
        assert result.exit_code == 0

        # Output file should be created
        assert (self.output_dir / "mask_test.pcap").exists()

    def test_all_operations_combination(self):
        """Test all operations working together with TLS protocol."""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_pcap),
                "-o",
                str(self.output_dir / "all_ops.pcap"),
                "--dedup",
                "--anon",
                "--mask",
            ],
            standalone_mode=False,
        )

        # Should complete successfully
        assert result.exit_code == 0

        # Output file should be created
        assert (self.output_dir / "all_ops.pcap").exists()

    def test_verbose_mode_functionality(self):
        """Test verbose mode provides additional information."""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_pcap),
                "-o",
                str(self.output_dir / "verbose_test.pcap"),
                "--dedup",
                "--verbose",
            ],
            standalone_mode=False,
        )

        # Should complete successfully
        assert result.exit_code == 0

        # Output file should be created
        assert (self.output_dir / "verbose_test.pcap").exists()

    def test_pcapng_file_support(self):
        """Test that .pcapng files are supported."""
        # Create a test .pcapng file by copying a .pcap file
        test_pcapng = self.temp_dir / "test.pcapng"
        shutil.copy2(self.test_pcap, test_pcapng)

        result = self.runner.invoke(
            app, ["process", str(test_pcapng), "--anon"], standalone_mode=False
        )

        assert result.exit_code == 0
        assert "📁 Auto-generated output path:" in result.stdout
        assert "test_processed.pcapng" in result.stdout

    # =========================================================================
    # Backward Compatibility Tests
    # =========================================================================

    def test_existing_usage_patterns_work(self):
        """Test that existing usage patterns continue to work."""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_pcap),
                "-o",
                str(self.output_dir / "backward_compat.pcap"),
                "--dedup",
                "--anon",
                "--mask",
                "--verbose",
            ],
            standalone_mode=False,
        )

        assert result.exit_code == 0
        assert (self.output_dir / "backward_compat.pcap").exists()

    def test_short_and_long_options_work(self):
        """Test that both short and long options work."""
        result = self.runner.invoke(
            app,
            [
                "process",
                str(self.test_pcap),
                "-o",
                str(self.output_dir / "options_test.pcap"),
                "--dedup",
                "-v",
            ],
            standalone_mode=False,
        )

        assert result.exit_code == 0
        assert (self.output_dir / "options_test.pcap").exists()

    def test_mixed_file_types_in_directory(self):
        """Test directory with mixed file types processes only PCAP files."""
        # Create test directory with mixed files
        test_dir = self.temp_dir / "mixed_files"
        test_dir.mkdir()

        # Copy PCAP file
        shutil.copy2(self.test_pcap, test_dir / "valid.pcap")

        # Create non-PCAP files
        (test_dir / "readme.txt").write_text("This is not a PCAP file")
        (test_dir / "data.json").write_text('{"not": "pcap"}')

        result = self.runner.invoke(
            app, ["process", str(test_dir), "--dedup"], standalone_mode=False
        )

        assert result.exit_code == 0
        # Should process only the PCAP file
        assert "valid.pcap" in result.stdout
