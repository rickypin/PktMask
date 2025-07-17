#!/usr/bin/env python3
"""
TShark Setup Validation Script

Comprehensive validation script for TShark installation and TLS marker functionality.
Can be used for troubleshooting and verification of cross-platform TShark setup.
"""

import argparse
import sys
import os
import platform
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pktmask.infrastructure.tshark import (
    TSharkManager, validate_tls_marker_functionality,
    TLSMarkerValidator
)
from pktmask.infrastructure.startup import validate_startup_dependencies


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_section(title: str):
    """Print formatted section header"""
    print(f"\n📋 {title}")
    print("-" * 40)


def validate_basic_tshark(custom_path: str = None):
    """Validate basic TShark functionality"""
    print_section("Basic TShark Detection")
    
    tshark_manager = TSharkManager(custom_path=custom_path)
    tshark_info = tshark_manager.detect_tshark()
    
    if tshark_info.is_available:
        print(f"✅ TShark found: {tshark_info.path}")
        print(f"✅ Version: {tshark_info.version_formatted}")
        print(f"✅ Status: {tshark_info.status.value}")
        return True
    else:
        print(f"❌ TShark not available: {tshark_info.error_message}")
        print(f"❌ Status: {tshark_info.status.value}")
        
        # Show installation guide
        guide = tshark_manager.get_installation_guide()
        if guide:
            print(f"\n💡 Installation guide for {guide.get('platform', 'your system')}:")
            methods = guide.get('methods', [])
            if methods:
                primary_method = methods[0]
                print(f"   • {primary_method['description']}")
                if primary_method.get('commands'):
                    for cmd in primary_method['commands']:
                        print(f"     $ {cmd}")
        
        return False


def validate_tls_functionality(custom_path: str = None):
    """Validate basic TShark functionality (simplified for performance)"""
    print_section("Basic TShark Functionality")

    tshark_manager = TSharkManager(custom_path)
    tshark_info = tshark_manager.detect_tshark()

    if tshark_info.is_available:
        print("✅ Basic TShark functionality validation passed")
        print(f"   TShark path: {tshark_info.path}")
        print(f"   Version: {tshark_info.version_formatted}")

        # Quick capability check (simplified)
        requirements_met, missing = tshark_manager.verify_tls_marker_requirements(tshark_info.path)
        if requirements_met:
            print("   Basic requirements: ✅ All met")
        else:
            print(f"   Basic requirements: ❌ Missing: {', '.join(missing)}")
            return False
    else:
        print("❌ Basic TShark functionality validation failed")
        print(f"   Error: {tshark_info.error_message}")
        return False

    return True


def validate_startup_dependencies_check(custom_path: str = None):
    """Validate startup dependencies"""
    print_section("Startup Dependencies Validation")
    
    validation_result = validate_startup_dependencies(
        custom_tshark_path=custom_path,
        strict_mode=True
    )
    
    if validation_result.success:
        print("✅ All startup dependencies satisfied")
    else:
        print("❌ Startup dependency validation failed")
        print(f"\nMissing dependencies: {', '.join(validation_result.missing_dependencies)}")
        
        print("\nError messages:")
        for error in validation_result.error_messages:
            print(f"   • {error}")
    
    return validation_result.success


def test_with_sample_pcap(custom_path: str = None, pcap_path: str = None):
    """Test TLS functionality with sample PCAP"""
    if not pcap_path or not Path(pcap_path).exists():
        print_section("Sample PCAP Test - Skipped")
        print("⚠️  No sample PCAP file provided or file not found")
        return True
    
    print_section("Sample PCAP Test")
    print(f"Testing with: {pcap_path}")
    
    tshark_manager = TSharkManager(custom_path=custom_path)
    validator = TLSMarkerValidator(tshark_manager=tshark_manager)
    
    pcap_results = validator.validate_with_sample_pcap(pcap_path)
    
    all_passed = True
    for test, passed in pcap_results.items():
        icon = "✅" if passed else "❌"
        formatted_test = test.replace('_', ' ').title()
        print(f"   {icon} {formatted_test}")
        if not passed:
            all_passed = False
    
    return all_passed


def generate_full_report(custom_path: str = None):
    """Generate comprehensive validation report"""
    print_section("Comprehensive Validation Report")
    
    tls_validation = validate_tls_marker_functionality(custom_path)
    validator = TLSMarkerValidator()
    report = validator.generate_validation_report(tls_validation)
    
    print(report)
    return tls_validation.success


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Validate TShark setup for PktMask",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_tshark_setup.py                    # Basic validation
  python validate_tshark_setup.py --all              # Comprehensive validation
  python validate_tshark_setup.py --tshark-path /usr/local/bin/tshark
  python validate_tshark_setup.py --sample-pcap test.pcap
  python validate_tshark_setup.py --report           # Generate detailed report
        """
    )
    
    parser.add_argument(
        "--tshark-path",
        help="Custom TShark executable path"
    )
    
    parser.add_argument(
        "--sample-pcap",
        help="Sample PCAP file for testing TLS functionality"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all validation tests"
    )
    
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate comprehensive validation report"
    )
    
    parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Run only basic TShark detection"
    )

    parser.add_argument(
        "--windows-fix",
        action="store_true",
        help="Run Windows-specific TShark fixes (Windows only)"
    )

    args = parser.parse_args()
    
    print_header("PktMask TShark Setup Validation")
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version}")
    
    # Track overall success
    all_tests_passed = True

    # Windows-specific fixes
    if args.windows_fix and platform.system() == 'Windows':
        print_section("Windows TShark Fix")
        try:
            import subprocess
            result = subprocess.run([
                sys.executable,
                'scripts/windows_tshark_fix.py',
                '--auto-fix'
            ], cwd=Path(__file__).parent.parent)

            if result.returncode == 0:
                print("✅ Windows TShark fix completed")
            else:
                print("❌ Windows TShark fix failed")
                print("   Please run: python scripts/windows_tshark_fix.py --auto-fix")
        except Exception as e:
            print(f"❌ Error running Windows fix: {e}")

    # Basic TShark validation (always run unless report-only)
    if not args.report:
        basic_success = validate_basic_tshark(args.tshark_path)
        all_tests_passed = all_tests_passed and basic_success
        
        if not basic_success and not args.all:
            print("\n❌ Basic TShark validation failed. Fix TShark installation before proceeding.")
            sys.exit(1)
    
    # Additional tests based on arguments
    if args.all or not args.basic_only:
        if not args.report:
            # TLS functionality validation
            tls_success = validate_tls_functionality(args.tshark_path)
            all_tests_passed = all_tests_passed and tls_success
            
            # Startup dependencies validation
            startup_success = validate_startup_dependencies_check(args.tshark_path)
            all_tests_passed = all_tests_passed and startup_success
            
            # Sample PCAP test
            pcap_success = test_with_sample_pcap(args.tshark_path, args.sample_pcap)
            all_tests_passed = all_tests_passed and pcap_success
    
    # Generate comprehensive report
    if args.report or args.all:
        report_success = generate_full_report(args.tshark_path)
        all_tests_passed = all_tests_passed and report_success
    
    # Final summary
    print_header("Validation Summary")
    if all_tests_passed:
        print("🎉 All validations passed! TShark is properly configured for PktMask.")
        sys.exit(0)
    else:
        print("❌ Some validations failed. Please address the issues above.")
        print("\n💡 Common solutions:")
        print("   • Install or update TShark/Wireshark")
        print("   • Check TShark is in system PATH")
        print("   • Verify TShark version >= 4.2.0")
        print("   • Ensure TLS/SSL protocol support is enabled")

        # Windows-specific suggestions
        if platform.system() == 'Windows':
            print("\n🪟 Windows-specific solutions:")
            print("   • Run: python scripts/windows_tshark_fix.py --auto-fix")
            print("   • Install Wireshark with 'Command Line Tools' option")
            print("   • Use Chocolatey: choco install wireshark")
            print("   • See: docs/WINDOWS_TSHARK_TROUBLESHOOTING.md")

        sys.exit(1)


if __name__ == "__main__":
    main()
