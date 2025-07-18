#!/usr/bin/env python3
"""
Real GUI Data Inspector

This script helps debug the actual data structure in the GUI environment
to understand why IP Anonymization entries are still missing from individual file reports.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def inspect_report_manager_data():
    """Inspect the actual data structure in ReportManager"""
    print("=" * 80)
    print("Real GUI Data Inspector")
    print("=" * 80)
    print("This tool will help identify the actual data structure differences")
    print("between our simulation and the real GUI environment.")
    print()
    
    # Import the actual ReportManager
    from pktmask.gui.managers.report_manager import ReportManager
    
    print("ReportManager methods:")
    methods = [method for method in dir(ReportManager) if not method.startswith('_')]
    for method in methods:
        print(f"  - {method}")
    print()
    
    # Check the generate_file_complete_report method
    import inspect
    source = inspect.getsource(ReportManager.generate_file_complete_report)
    print("generate_file_complete_report method source (first 20 lines):")
    lines = source.split('\n')[:20]
    for i, line in enumerate(lines, 1):
        print(f"{i:2d}: {line}")
    print("...")
    print()


def create_data_collection_patch():
    """Create a patch to collect actual data from GUI"""
    print("=" * 80)
    print("Data Collection Patch")
    print("=" * 80)
    
    patch_code = '''
# Add this to ReportManager.generate_file_complete_report method
# Right after line: file_results = self.main_window.file_processing_results[original_filename]

print(f"🔍 DEBUG: File results structure for {original_filename}:")
print(f"🔍 DEBUG: Keys: {list(file_results.keys())}")
if 'steps' in file_results:
    print(f"🔍 DEBUG: Steps: {list(file_results['steps'].keys())}")
    for step_name, step_data in file_results['steps'].items():
        print(f"🔍 DEBUG: Step '{step_name}':")
        print(f"🔍 DEBUG:   Type: {step_data.get('type', 'UNKNOWN')}")
        print(f"🔍 DEBUG:   Data keys: {list(step_data.get('data', {}).keys())}")
        if 'data' in step_data and 'extra_metrics' in step_data['data']:
            extra_metrics = step_data['data']['extra_metrics']
            print(f"🔍 DEBUG:   Extra metrics keys: {list(extra_metrics.keys())}")
            if 'original_ips' in extra_metrics:
                print(f"🔍 DEBUG:   Original IPs: {extra_metrics['original_ips']}")
            if 'anonymized_ips' in extra_metrics:
                print(f"🔍 DEBUG:   Anonymized IPs: {extra_metrics['anonymized_ips']}")
'''
    
    print("Add this debug code to ReportManager.generate_file_complete_report:")
    print(patch_code)
    print()


def check_step_type_mapping():
    """Check the step type mapping logic"""
    print("=" * 80)
    print("Step Type Mapping Analysis")
    print("=" * 80)
    
    # Check the actual step type mapping in the code
    from pktmask.gui.managers.report_manager import ReportManager
    
    print("Looking for step type mapping logic...")
    
    # Get the source of generate_file_complete_report
    import inspect
    source = inspect.getsource(ReportManager.generate_file_complete_report)
    
    # Look for step type conditions
    lines = source.split('\n')
    for i, line in enumerate(lines):
        if 'anonymize_ips' in line or 'mask_ip' in line or 'step_type' in line:
            print(f"Line {i+1}: {line.strip()}")
    
    print()
    print("Key questions to investigate:")
    print("1. How is step_type determined from the actual GUI data?")
    print("2. What is the actual step name stored in file_processing_results?")
    print("3. Does the step_type match our expected conditions?")
    print()


def create_minimal_test():
    """Create a minimal test to reproduce the issue"""
    print("=" * 80)
    print("Minimal Reproduction Test")
    print("=" * 80)
    
    test_code = '''
# Test the actual step type inference logic
def test_step_type_inference():
    # These are the possible step names we might see in real GUI data:
    test_cases = [
        "IPAnonymizationStage",
        "IP Anonymization", 
        "anonymize_ips",
        "AnonStage",
        "Anonymize IPs"
    ]
    
    for step_name in test_cases:
        # Test the step type mapping logic from ReportManager
        step_type = None
        
        # This is likely how the step type is determined:
        if step_name.lower() in ['anonymize_ips', 'anon_ip', 'ip_anonymization']:
            step_type = 'anonymize_ips'
        elif 'anonymiz' in step_name.lower() or 'anon' in step_name.lower():
            step_type = 'anonymize_ips'
        else:
            step_type = step_name.lower()
        
        print(f"Step name: '{step_name}' -> Step type: '{step_type}'")
        
        # Check if it matches the condition
        matches_condition = step_type in ['anonymize_ips', 'mask_ip', 'mask_ips']
        print(f"  Matches IP anonymization condition: {matches_condition}")
        print()

test_step_type_inference()
'''
    
    print("Run this test to check step type inference:")
    print(test_code)


def main():
    """Run all debugging tools"""
    print("🔍 Real GUI Data Inspector")
    print("=" * 80)
    print("Investigating why IP Anonymization entries are missing")
    print("from individual file reports in the actual GUI environment.")
    print("=" * 80)
    print()
    
    try:
        inspect_report_manager_data()
        create_data_collection_patch()
        check_step_type_mapping()
        create_minimal_test()
        
        print("🎯 NEXT STEPS")
        print("=" * 80)
        print("1. Add the debug code to ReportManager.generate_file_complete_report")
        print("2. Run the GUI and process a file to see the actual data structure")
        print("3. Compare the actual step names and types with our expectations")
        print("4. Identify the exact mismatch causing the condition to fail")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ INSPECTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
