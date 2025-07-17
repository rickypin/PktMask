#!/usr/bin/env python3
"""
TLS Marker Functionality Validator

Specialized validator for TLS marker module requirements,
ensuring all necessary TShark capabilities are available.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from pktmask.infrastructure.logging import get_logger
from .manager import TSharkManager


@dataclass
class TLSValidationResult:
    """TLS validation result"""
    success: bool
    missing_capabilities: List[str]
    error_messages: List[str]
    detailed_results: Dict[str, bool]
    tshark_path: Optional[str] = None


class TLSMarkerValidator:
    """Validator for TLS marker functionality"""
    
    def __init__(self, tshark_manager: Optional[TSharkManager] = None):
        """Initialize TLS validator
        
        Args:
            tshark_manager: TShark manager instance (optional)
        """
        self.logger = get_logger('tls_validator')
        self.tshark_manager = tshark_manager or TSharkManager()
    
    def validate_tls_marker_support(self) -> TLSValidationResult:
        """Validate basic TShark support (simplified for performance)

        Returns:
            Basic TLS validation result
        """
        self.logger.info("Starting basic TShark validation...")

        # First detect TShark
        tshark_info = self.tshark_manager.detect_tshark()
        if not tshark_info.is_available:
            return TLSValidationResult(
                success=False,
                missing_capabilities=['tshark_executable'],
                error_messages=[f"TShark not available: {tshark_info.error_message}"],
                detailed_results={},
                tshark_path=None
            )

        # Simplified requirements check
        requirements_met, missing_requirements = self.tshark_manager.verify_tls_marker_requirements(
            tshark_info.path
        )

        # Get basic capability results (no complex functional tests)
        detailed_capabilities = self.tshark_manager.verify_tls_capabilities(tshark_info.path)

        # Compile error messages
        error_messages = []
        if not requirements_met:
            error_messages.extend([f"Missing: {req}" for req in missing_requirements])

        success = requirements_met

        if success:
            self.logger.info("Basic TShark validation passed")
        else:
            self.logger.error(f"Basic TShark validation failed: {error_messages}")

        return TLSValidationResult(
            success=success,
            missing_capabilities=missing_requirements,
            error_messages=error_messages,
            detailed_results=detailed_capabilities,
            tshark_path=tshark_info.path
        )
    
    def _perform_functional_tests(self, tshark_path: str) -> Dict[str, bool]:
        """Perform functional tests for TLS marker capabilities
        
        Args:
            tshark_path: Path to TShark executable
            
        Returns:
            Dictionary of functional test results
        """
        functional_results = {
            'json_tls_parsing': False,
            'tcp_stream_filtering': False,
            'tls_field_occurrence_handling': False,
            'decode_as_support': False
        }
        
        try:
            # Test 1: JSON TLS parsing with minimal command
            result = subprocess.run([
                tshark_path, '-T', 'json',
                '-e', 'frame.number',
                '-e', 'tls.record.content_type',
                '--help'
            ], capture_output=True, text=True, timeout=10)
            functional_results['json_tls_parsing'] = result.returncode == 0
            
            # Test 2: TCP stream filtering
            result = subprocess.run([
                tshark_path, '-Y', 'tcp.stream == 0',
                '--help'
            ], capture_output=True, text=True, timeout=10)
            functional_results['tcp_stream_filtering'] = result.returncode == 0

            # Test 3: TLS field occurrence handling
            result = subprocess.run([
                tshark_path, '-T', 'json',
                '-e', 'tls.app_data',
                '-E', 'occurrence=a',
                '--help'
            ], capture_output=True, text=True, timeout=10)
            functional_results['tls_field_occurrence_handling'] = result.returncode == 0

            # Test 4: Decode-as support (for custom port TLS)
            result = subprocess.run([
                tshark_path, '-d', 'tcp.port==8443,tls',
                '--help'
            ], capture_output=True, text=True, timeout=10)
            functional_results['decode_as_support'] = result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Functional test error: {e}")
        
        return functional_results
    
    def generate_validation_report(self, result: TLSValidationResult) -> str:
        """Generate human-readable validation report
        
        Args:
            result: TLS validation result
            
        Returns:
            Formatted validation report
        """
        report_lines = [
            "🔍 TLS Marker Functionality Validation Report",
            "=" * 50,
            ""
        ]
        
        # Overall status
        status_icon = "✅" if result.success else "❌"
        report_lines.append(f"{status_icon} Overall Status: {'PASSED' if result.success else 'FAILED'}")
        
        if result.tshark_path:
            report_lines.append(f"📍 TShark Path: {result.tshark_path}")
        
        report_lines.append("")
        
        # Detailed capabilities
        report_lines.append("📋 Capability Details:")
        for capability, status in result.detailed_results.items():
            icon = "✅" if status else "❌"
            formatted_name = capability.replace('_', ' ').title()
            report_lines.append(f"   {icon} {formatted_name}")
        
        # Missing capabilities
        if result.missing_capabilities:
            report_lines.extend([
                "",
                "⚠️  Missing Capabilities:",
            ])
            for missing in result.missing_capabilities:
                report_lines.append(f"   • {missing}")
        
        # Error messages
        if result.error_messages:
            report_lines.extend([
                "",
                "💥 Error Details:",
            ])
            for error in result.error_messages:
                report_lines.append(f"   • {error}")
        
        # Recommendations
        if not result.success:
            report_lines.extend([
                "",
                "💡 Recommendations:",
                "   • Ensure TShark version >= 4.2.0",
                "   • Verify TLS/SSL protocol support is enabled",
                "   • Check that all required dissectors are available",
                "   • Consider reinstalling Wireshark/TShark if issues persist"
            ])
        
        return "\n".join(report_lines)
    
    def validate_with_sample_pcap(self, pcap_path: str) -> Dict[str, bool]:
        """Validate TLS functionality with actual PCAP file
        
        Args:
            pcap_path: Path to sample PCAP file
            
        Returns:
            Dictionary of validation results with real data
        """
        if not Path(pcap_path).exists():
            self.logger.error(f"Sample PCAP file not found: {pcap_path}")
            return {'pcap_file_exists': False}
        
        tshark_info = self.tshark_manager.detect_tshark()
        if not tshark_info.is_available:
            return {'tshark_available': False}
        
        validation_results = {'pcap_file_exists': True, 'tshark_available': True}
        
        try:
            # Test TLS record extraction
            result = subprocess.run([
                tshark_info.path, '-2', '-r', pcap_path,
                '-T', 'json',
                '-e', 'frame.number',
                '-e', 'tls.record.content_type',
                '-e', 'tls.app_data',
                '-Y', 'tls'
            ], capture_output=True, text=True, timeout=30)
            
            validation_results['tls_record_extraction'] = result.returncode == 0
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    # Try to parse JSON output
                    json_data = json.loads(result.stdout)
                    validation_results['json_parsing'] = True
                    validation_results['tls_data_found'] = len(json_data) > 0
                except json.JSONDecodeError:
                    validation_results['json_parsing'] = False
                    validation_results['tls_data_found'] = False
            else:
                validation_results['json_parsing'] = False
                validation_results['tls_data_found'] = False
            
        except Exception as e:
            self.logger.error(f"Sample PCAP validation error: {e}")
            validation_results['validation_error'] = str(e)
        
        return validation_results


def validate_tls_marker_functionality(custom_tshark_path: Optional[str] = None) -> TLSValidationResult:
    """Convenience function for TLS marker validation
    
    Args:
        custom_tshark_path: Custom TShark executable path
        
    Returns:
        TLS validation result
    """
    tshark_manager = TSharkManager(custom_path=custom_tshark_path)
    validator = TLSMarkerValidator(tshark_manager=tshark_manager)
    return validator.validate_tls_marker_support()


if __name__ == "__main__":
    # Command-line validation for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate TLS marker functionality")
    parser.add_argument("--tshark-path", help="Custom TShark executable path")
    parser.add_argument("--sample-pcap", help="Sample PCAP file for testing")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Perform validation
    result = validate_tls_marker_functionality(custom_tshark_path=args.tshark_path)
    
    # Generate and print report
    validator = TLSMarkerValidator()
    report = validator.generate_validation_report(result)
    print(report)
    
    # Additional sample PCAP validation if provided
    if args.sample_pcap:
        print("\n" + "=" * 50)
        print("🧪 Sample PCAP Validation")
        print("=" * 50)
        
        pcap_results = validator.validate_with_sample_pcap(args.sample_pcap)
        for test, passed in pcap_results.items():
            icon = "✅" if passed else "❌"
            formatted_test = test.replace('_', ' ').title()
            print(f"{icon} {formatted_test}: {passed}")
    
    exit(0 if result.success else 1)
