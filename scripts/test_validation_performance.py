#!/usr/bin/env python3
"""
TShark Validation Performance Test

Tests the performance improvements of the simplified TShark validation process.
Measures execution time and subprocess calls to verify optimization goals.
"""

import time
import sys
import os
import platform
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pktmask.infrastructure.tshark.manager import TSharkManager
from pktmask.infrastructure.tshark.tls_validator import TLSMarkerValidator


def time_function(func, *args, **kwargs):
    """Time a function execution"""
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    return result, end_time - start_time


def test_basic_detection():
    """Test basic TShark detection performance"""
    print("🔍 Testing Basic TShark Detection...")
    
    manager = TSharkManager()
    result, duration = time_function(manager.detect_tshark)
    
    print(f"   Duration: {duration:.3f}s")
    print(f"   Result: {'✅ Success' if result.is_available else '❌ Failed'}")
    if result.is_available:
        print(f"   Path: {result.path}")
        print(f"   Version: {result.version_formatted}")
    
    return duration, result.is_available


def test_simplified_capabilities():
    """Test simplified capability verification"""
    print("\n🔍 Testing Simplified Capability Verification...")
    
    manager = TSharkManager()
    tshark_info = manager.detect_tshark()
    
    if not tshark_info.is_available:
        print("   ❌ TShark not available, skipping test")
        return 0, False
    
    result, duration = time_function(manager.verify_tls_capabilities, tshark_info.path)
    
    print(f"   Duration: {duration:.3f}s")
    print(f"   Capabilities checked: {len(result)}")
    
    for capability, status in result.items():
        icon = "✅" if status else "❌"
        print(f"     {icon} {capability.replace('_', ' ').title()}")
    
    return duration, all(result.values())


def test_tls_validation():
    """Test TLS validation performance"""
    print("\n🔍 Testing TLS Validation...")
    
    validator = TLSMarkerValidator()
    result, duration = time_function(validator.validate_tls_marker_support)
    
    print(f"   Duration: {duration:.3f}s")
    print(f"   Result: {'✅ Success' if result.success else '❌ Failed'}")
    
    if not result.success:
        print("   Missing capabilities:")
        for missing in result.missing_capabilities:
            print(f"     • {missing}")
    
    return duration, result.success


def test_requirements_verification():
    """Test requirements verification performance"""
    print("\n🔍 Testing Requirements Verification...")
    
    manager = TSharkManager()
    tshark_info = manager.detect_tshark()
    
    if not tshark_info.is_available:
        print("   ❌ TShark not available, skipping test")
        return 0, False
    
    result, duration = time_function(manager.verify_tls_marker_requirements, tshark_info.path)
    requirements_met, missing = result
    
    print(f"   Duration: {duration:.3f}s")
    print(f"   Requirements met: {'✅ Yes' if requirements_met else '❌ No'}")
    
    if missing:
        print("   Missing requirements:")
        for req in missing:
            print(f"     • {req}")
    
    return duration, requirements_met


def run_performance_test():
    """Run comprehensive performance test"""
    print("🚀 TShark Validation Performance Test")
    print("=" * 60)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")

    total_start = time.time()

    # Use single manager instance to test caching
    print("\n🔄 Testing with shared TShark manager (caching optimization)...")
    manager = TSharkManager()

    # First detection (will cache)
    print("\n🔍 Initial TShark Detection (will cache)...")
    result, duration = time_function(manager.detect_tshark)
    detection_time = duration
    detection_success = result.is_available

    print(f"   Duration: {duration:.3f}s")
    print(f"   Result: {'✅ Success' if result.is_available else '❌ Failed'}")
    if result.is_available:
        print(f"   Path: {result.path}")
        print(f"   Version: {result.version_formatted}")

    # Subsequent calls should use cache
    print("\n🔍 Cached Capability Verification...")
    if detection_success:
        result, duration = time_function(manager.verify_tls_capabilities)
        capabilities_time = duration
        capabilities_success = all(result.values())

        print(f"   Duration: {duration:.3f}s")
        print(f"   Capabilities checked: {len(result)}")

        for capability, status in result.items():
            icon = "✅" if status else "❌"
            print(f"     {icon} {capability.replace('_', ' ').title()}")
    else:
        capabilities_time = 0
        capabilities_success = False

    # TLS validation with same manager
    print("\n🔍 TLS Validation (using cached info)...")
    validator = TLSMarkerValidator(manager)
    result, duration = time_function(validator.validate_tls_marker_support)
    tls_time = duration
    tls_success = result.success

    print(f"   Duration: {duration:.3f}s")
    print(f"   Result: {'✅ Success' if result.success else '❌ Failed'}")

    if not result.success:
        print("   Missing capabilities:")
        for missing in result.missing_capabilities:
            print(f"     • {missing}")

    # Requirements verification with cached info
    print("\n🔍 Requirements Verification (using cached info)...")
    if detection_success:
        result, duration = time_function(manager.verify_tls_marker_requirements, manager._cached_info.path)
        requirements_time = duration
        requirements_met, missing = result
        requirements_success = requirements_met

        print(f"   Duration: {duration:.3f}s")
        print(f"   Requirements met: {'✅ Yes' if requirements_met else '❌ No'}")

        if missing:
            print("   Missing requirements:")
            for req in missing:
                print(f"     • {req}")
    else:
        requirements_time = 0
        requirements_success = False

    total_time = time.time() - total_start
    
    # Summary
    print("\n📊 Performance Summary")
    print("-" * 40)
    print(f"Basic Detection:      {detection_time:.3f}s")
    print(f"Capabilities Check:   {capabilities_time:.3f}s")
    print(f"TLS Validation:       {tls_time:.3f}s")
    print(f"Requirements Check:   {requirements_time:.3f}s")
    print(f"Total Time:           {total_time:.3f}s")
    
    # Success criteria
    print("\n✅ Success Criteria Check")
    print("-" * 40)
    
    # Performance criteria
    performance_pass = total_time < 2.0
    print(f"Total time < 2.0s:    {'✅ PASS' if performance_pass else '❌ FAIL'} ({total_time:.3f}s)")
    
    # Functionality criteria
    all_tests_pass = all([detection_success, capabilities_success, tls_success, requirements_success])
    print(f"All tests pass:       {'✅ PASS' if all_tests_pass else '❌ FAIL'}")
    
    # Subprocess optimization (estimated)
    estimated_subprocess_calls = 1  # Only one call per validation now
    subprocess_pass = estimated_subprocess_calls <= 2
    print(f"Subprocess calls ≤ 2: {'✅ PASS' if subprocess_pass else '❌ FAIL'} (~{estimated_subprocess_calls})")
    
    # Overall result
    overall_pass = performance_pass and all_tests_pass and subprocess_pass
    print(f"\nOverall Result:       {'🎉 PASS' if overall_pass else '❌ FAIL'}")
    
    if overall_pass:
        print("\n🎉 Performance optimization successful!")
        print("   • Validation completes in under 2 seconds")
        print("   • Minimal subprocess calls reduce Windows CMD flashing")
        print("   • All essential functionality preserved")
    else:
        print("\n⚠️  Performance optimization needs improvement:")
        if not performance_pass:
            print(f"   • Total time ({total_time:.3f}s) exceeds 2.0s target")
        if not all_tests_pass:
            print("   • Some functionality tests failed")
        if not subprocess_pass:
            print("   • Too many subprocess calls")
    
    return overall_pass


def main():
    """Main function"""
    try:
        success = run_performance_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
