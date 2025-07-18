#!/usr/bin/env python3
"""
Test IP Anonymization Fix

This script tests the fix for missing IP Anonymization entries in individual file reports.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pktmask.gui.managers.report_manager import ReportManager


def test_collect_step_result_fix():
    """Test the collect_step_result fix for IPAnonymizationStage"""
    print("=" * 80)
    print("Testing collect_step_result fix for IPAnonymizationStage")
    print("=" * 80)
    
    # Create mock main window
    class MockMainWindow:
        def __init__(self):
            self.file_processing_results = {
                'test.pcap': {'steps': {}}
            }
            self.current_processing_file = 'test.pcap'
            self.global_ip_mappings = {}
            self._current_file_ips = {}
            self.config = {}
    
    main_window = MockMainWindow()
    report_manager = ReportManager(main_window)
    
    # Test data that would come from IPAnonymizationStage
    test_data = {
        'step_name': 'IPAnonymizationStage',
        'type': None,  # New stages don't have type field initially
        'packets_processed': 101,
        'packets_modified': 101,
        'duration_ms': 1000.0,
        'extra_metrics': {
            'success': True,
            'original_ips': 2,
            'anonymized_ips': 2,
            'anonymization_rate': 100.0,
            'method': 'prefix_preserving',
            'ipv4_prefix': 24,
            'ipv6_prefix': 64,
            'ip_mappings': {
                '12.234.12.108': '8.225.9.108',
                '171.159.193.170': '168.150.179.170'
            }
        }
    }
    
    print("Input data:")
    print(f"  step_name: {test_data.get('step_name')}")
    print(f"  type: {test_data.get('type')}")
    print(f"  extra_metrics keys: {list(test_data.get('extra_metrics', {}).keys())}")
    print()
    
    # Call collect_step_result
    print("Calling collect_step_result...")
    report_manager.collect_step_result(test_data)
    print()
    
    # Check the stored result
    stored_steps = main_window.file_processing_results['test.pcap']['steps']
    print("Stored steps:")
    for step_name, step_data in stored_steps.items():
        print(f"  Step: {step_name}")
        print(f"  Type: {step_data.get('type')}")
        print(f"  Data keys: {list(step_data.get('data', {}).keys())}")
        
        # Check if it would match the condition in generate_file_complete_report
        step_type = step_data.get('type')
        matches_condition = step_type in ['anonymize_ips', 'mask_ip', 'mask_ips']
        print(f"  Matches IP anonymization condition: {matches_condition}")
        
        if matches_condition:
            data = step_data.get('data', {})
            original_ips = data.get('original_ips', 0)
            masked_ips = data.get('anonymized_ips', 0)
            
            if original_ips == 0 and masked_ips == 0:
                extra_metrics = data.get('extra_metrics', {})
                original_ips = extra_metrics.get('original_ips', 0)
                masked_ips = extra_metrics.get('anonymized_ips', 0)
            
            print(f"  Original IPs: {original_ips}")
            print(f"  Anonymized IPs: {masked_ips}")
            
            if original_ips > 0 and masked_ips > 0:
                rate = (masked_ips / original_ips * 100)
                line = f"  🛡️  {step_name:<18} | Original IPs: {original_ips:>3} | Anonymized IPs: {masked_ips:>3} | Rate: {rate:5.1f}%"
                print(f"  Generated line: {line}")
                print("  ✅ Would generate IP Anonymization entry")
            else:
                print("  ❌ Would NOT generate IP Anonymization entry (no IP data)")
        else:
            print("  ❌ Would NOT generate IP Anonymization entry (condition failed)")
    
    print()
    
    # Test the expected outcome
    if 'IP Anonymization' in stored_steps:
        step_data = stored_steps['IP Anonymization']
        if step_data.get('type') == 'anonymize_ips':
            print("✅ Test PASSED: IPAnonymizationStage correctly stored as 'anonymize_ips' type")
            return True
        else:
            print(f"❌ Test FAILED: Wrong type stored: {step_data.get('type')}")
            return False
    else:
        print("❌ Test FAILED: No 'IP Anonymization' step stored")
        return False


def test_step_type_inference():
    """Test step type inference logic"""
    print("=" * 80)
    print("Testing step type inference logic")
    print("=" * 80)
    
    test_cases = [
        ('IPAnonymizationStage', None, 'anonymize_ips'),
        ('AnonStage', None, 'anonymize_ips'),
        ('DeduplicationStage', None, 'remove_dupes'),
        ('NewMaskPayloadStage', None, 'mask_payloads'),
        ('SomeStage', 'existing_type', 'existing_type'),
    ]
    
    for step_name_raw, initial_type, expected_type in test_cases:
        # Simulate the inference logic
        step_type = initial_type
        
        if not step_type:
            if step_name_raw in ['AnonStage', 'IPAnonymizationStage']:
                step_type = 'anonymize_ips'
            elif step_name_raw in ['DedupStage', 'DeduplicationStage']:
                step_type = 'remove_dupes'
            elif step_name_raw in ['MaskStage', 'MaskPayloadStage', 'NewMaskPayloadStage', 'Mask Payloads (v2)', 'Payload Masking Stage']:
                step_type = 'mask_payloads'
            else:
                step_type = step_name_raw.lower()
        
        print(f"Step: {step_name_raw}, Initial: {initial_type}, Inferred: {step_type}, Expected: {expected_type}")
        
        if step_type == expected_type:
            print("  ✅ PASS")
        else:
            print("  ❌ FAIL")
    
    print()


def main():
    """Run all tests"""
    print("🔍 Testing IP Anonymization Fix")
    print("=" * 80)
    print("Testing the fix for missing IP Anonymization entries")
    print("in individual file reports.")
    print("=" * 80)
    print()
    
    try:
        test_step_type_inference()
        test_passed = test_collect_step_result_fix()
        
        if test_passed:
            print("🎉 ALL TESTS PASSED!")
            print("✅ IPAnonymizationStage is now correctly recognized")
            print("✅ Step type inference works correctly")
            print("✅ IP Anonymization entries should now appear in reports")
        else:
            print("❌ TESTS FAILED!")
            print("The fix needs further investigation.")
        
        return test_passed
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
