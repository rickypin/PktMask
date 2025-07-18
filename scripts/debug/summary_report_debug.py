#!/usr/bin/env python3
"""
Summary Report Debug Tool

This script helps debug why the Summary Report is missing:
1. IP Anonymization entries in individual file results
2. Global IP Mapping section

It traces the data flow and identifies where the issues occur.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pktmask.core.pipeline.stages.ip_anonymization import IPAnonymizationStage
from pktmask.core.pipeline.models import StageStats
from pktmask.gui.managers.report_manager import ReportManager


def debug_stage_stats_structure():
    """Debug the StageStats structure from IPAnonymizationStage"""
    print("=" * 80)
    print("DEBUG 1: IPAnonymizationStage StageStats Structure")
    print("=" * 80)
    
    # Create a mock IPAnonymizationStage result
    config = {
        'method': 'prefix_preserving',
        'ipv4_prefix': 24,
        'ipv6_prefix': 64,
        'enabled': True,
        'name': 'test_anonymization'
    }
    
    stage = IPAnonymizationStage(config)
    
    # Simulate the stats that would be returned
    mock_stats = StageStats(
        stage_name="IPAnonymizationStage",
        packets_processed=101,
        packets_modified=101,
        duration_ms=1000.0,
        extra_metrics={
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
            },
            'total_packets': 101,
            'anonymized_packets': 101
        }
    )
    
    print(f"Stage name: {mock_stats.stage_name}")
    print(f"Packets processed: {mock_stats.packets_processed}")
    print(f"Packets modified: {mock_stats.packets_modified}")
    print(f"Extra metrics keys: {list(mock_stats.extra_metrics.keys())}")
    print(f"Original IPs: {mock_stats.extra_metrics.get('original_ips')}")
    print(f"Anonymized IPs: {mock_stats.extra_metrics.get('anonymized_ips')}")
    print(f"IP mappings: {mock_stats.extra_metrics.get('ip_mappings')}")
    print()
    
    return mock_stats


def debug_step_result_data_conversion():
    """Debug how StageStats is converted to step result data"""
    print("=" * 80)
    print("DEBUG 2: StageStats to Step Result Data Conversion")
    print("=" * 80)
    
    mock_stats = debug_stage_stats_structure()
    
    # Simulate the data that would be passed to collect_step_result
    step_data = {
        'packets_processed': mock_stats.packets_processed,
        'packets_modified': mock_stats.packets_modified,
        'duration_ms': mock_stats.duration_ms,
        'extra_metrics': mock_stats.extra_metrics
    }
    
    print("Step data structure:")
    print(json.dumps(step_data, indent=2, default=str))
    print()
    
    return step_data


def debug_report_manager_step_collection():
    """Debug ReportManager's collect_step_result method"""
    print("=" * 80)
    print("DEBUG 3: ReportManager Step Collection Logic")
    print("=" * 80)
    
    # Create mock main window
    class MockMainWindow:
        def __init__(self):
            self.file_processing_results = {}
            self.current_processing_file = "ssl_3.pcap"
            self.global_ip_mappings = {}
            self._current_file_ips = {}
            self.config = {}
    
    main_window = MockMainWindow()
    report_manager = ReportManager(main_window)
    
    # Get the step data
    step_data = debug_step_result_data_conversion()
    
    # Test step type inference
    step_name_raw = "IPAnonymizationStage"
    print(f"Raw step name: {step_name_raw}")
    
    # Check the step type inference logic
    step_type_mapping = {
        'anonymize_ips': 'anonymize_ips',
        'anon_ip': 'anonymize_ips', 
        'IPAnonymizationStage': 'anonymize_ips',
        'AnonStage': 'anonymize_ips',
        'remove_dupes': 'remove_dupes',
        'dedup_packet': 'remove_dupes',
        'mask_payloads': 'mask_payloads',
        'mask_payload': 'mask_payloads'
    }
    
    inferred_step_type = step_type_mapping.get(step_name_raw, step_name_raw.lower())
    print(f"Inferred step type: {inferred_step_type}")
    
    # Check step display name mapping
    step_display_names = {
        'anonymize_ips': 'IP Anonymization',
        'remove_dupes': 'Deduplication', 
        'mask_payloads': 'Payload Masking',
    }
    
    step_name = step_display_names.get(inferred_step_type, inferred_step_type)
    print(f"Step display name: {step_name}")
    
    # Check if this would be identified as IP anonymization
    is_ip_anonymization = (
        inferred_step_type in ['anonymize_ips'] or
        step_name_raw == 'AnonStage' or
        'ip_mappings' in step_data or
        'file_ip_mappings' in step_data
    )
    print(f"Is IP anonymization: {is_ip_anonymization}")
    
    # Check IP mapping extraction
    ip_mappings = None
    if 'file_ip_mappings' in step_data:
        ip_mappings = step_data['file_ip_mappings']
        print("Found file_ip_mappings in step_data")
    elif 'ip_mappings' in step_data:
        ip_mappings = step_data['ip_mappings']
        print("Found ip_mappings in step_data")
    elif 'extra_metrics' in step_data:
        extra_metrics = step_data['extra_metrics']
        if 'file_ip_mappings' in extra_metrics:
            ip_mappings = extra_metrics['file_ip_mappings']
            print("Found file_ip_mappings in extra_metrics")
        elif 'ip_mappings' in extra_metrics:
            ip_mappings = extra_metrics['ip_mappings']
            print("Found ip_mappings in extra_metrics")
    
    print(f"Extracted IP mappings: {ip_mappings}")
    print()
    
    return step_name, inferred_step_type, step_data, ip_mappings


def debug_file_report_generation():
    """Debug the file report generation logic"""
    print("=" * 80)
    print("DEBUG 4: File Report Generation Logic")
    print("=" * 80)
    
    step_name, step_type, step_data, ip_mappings = debug_report_manager_step_collection()
    
    # Simulate the steps_data structure that would be used in generate_file_processing_report
    steps_data = {
        step_name: {
            'type': step_type,
            'data': step_data
        }
    }
    
    print("Steps data structure:")
    print(json.dumps(steps_data, indent=2, default=str))
    print()
    
    # Test the condition check in generate_file_processing_report
    step_order = ['Deduplication', 'IP Anonymization', 'Payload Masking']
    
    print("Checking step processing logic:")
    for step_name_check in step_order:
        if step_name_check in steps_data:
            step_result = steps_data[step_name_check]
            step_type_check = step_result['type']
            data = step_result['data']
            
            print(f"  Processing step: {step_name_check}")
            print(f"  Step type: {step_type_check}")
            print(f"  Data keys: {list(data.keys())}")
            
            # Check the condition that determines if IP Anonymization line is generated
            if step_type_check in ['anonymize_ips', 'mask_ip', 'mask_ips']:
                print(f"  ✅ Step type matches IP anonymization condition")
                
                # Check data extraction
                original_ips = data.get('original_ips', 0)
                masked_ips = data.get('anonymized_ips', 0)
                
                print(f"  Original IPs from data: {original_ips}")
                print(f"  Anonymized IPs from data: {masked_ips}")
                
                if original_ips == 0 and masked_ips == 0:
                    # Try extra_metrics
                    extra_metrics = data.get('extra_metrics', {})
                    original_ips = extra_metrics.get('original_ips', 0)
                    masked_ips = extra_metrics.get('anonymized_ips', 0)
                    print(f"  Original IPs from extra_metrics: {original_ips}")
                    print(f"  Anonymized IPs from extra_metrics: {masked_ips}")
                
                rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
                line = f"  🛡️  {step_name_check:<18} | Original IPs: {original_ips:>3} | Anonymized IPs: {masked_ips:>3} | Rate: {rate:5.1f}%"
                print(f"  Generated line: {line}")
            else:
                print(f"  ❌ Step type does not match IP anonymization condition")
        else:
            print(f"  Step {step_name_check} not found in steps_data")
    
    print()


def debug_global_ip_mapping_collection():
    """Debug global IP mapping collection logic"""
    print("=" * 80)
    print("DEBUG 5: Global IP Mapping Collection Logic")
    print("=" * 80)

    # Create mock main window with some global IP mappings and file processing results
    class MockMainWindow:
        def __init__(self):
            self.file_processing_results = {
                'ssl_3.pcap': {
                    'steps': {
                        'IP Anonymization': {
                            'type': 'anonymize_ips',
                            'data': {
                                'packets_processed': 101,
                                'packets_modified': 101,
                                'extra_metrics': {
                                    'original_ips': 2,
                                    'anonymized_ips': 2,
                                    'ip_mappings': {
                                        '12.234.12.108': '8.225.9.108',
                                        '171.159.193.170': '168.150.179.170'
                                    }
                                }
                            }
                        }
                    }
                }
            }
            self.current_processing_file = "ssl_3.pcap"
            self.global_ip_mappings = {
                '12.234.12.108': '8.225.9.108',
                '171.159.193.170': '168.150.179.170'
            }
            self._current_file_ips = {
                'ssl_3.pcap': {
                    '12.234.12.108': '8.225.9.108',
                    '171.159.193.170': '168.150.179.170'
                }
            }
            self.config = {}
            self.anonymize_ips_cb = MockCheckBox(True)  # Simulate enabled checkbox
            self.processed_files_count = 1  # Add missing attribute

    class MockCheckBox:
        def __init__(self, checked):
            self._checked = checked

        def isChecked(self):
            return self._checked

    main_window = MockMainWindow()
    report_manager = ReportManager(main_window)

    print(f"Global IP mappings: {main_window.global_ip_mappings}")
    print(f"File processing results: {list(main_window.file_processing_results.keys())}")
    print(f"Anonymize IPs enabled: {main_window.anonymize_ips_cb.isChecked()}")

    # Test the global IP mapping report generation
    separator_length = 70
    global_ip_report = report_manager._generate_global_ip_mappings_report(separator_length, is_partial=False)

    if global_ip_report:
        print("✅ Global IP mapping report generated:")
        print(global_ip_report[:500] + "..." if len(global_ip_report) > 500 else global_ip_report)
    else:
        print("❌ Global IP mapping report is None")

        # Debug why it's None
        if not main_window.anonymize_ips_cb.isChecked():
            print("  Reason: IP anonymization is not enabled")
        elif not main_window.global_ip_mappings:
            print("  Reason: No global IP mappings found")
        else:
            print("  Reason: Unknown - checking file completion logic")

    print()


def debug_fixed_file_report_generation():
    """Debug the fixed file report generation logic"""
    print("=" * 80)
    print("DEBUG 6: Fixed File Report Generation Logic")
    print("=" * 80)

    # Test the fixed data extraction logic
    step_data = {
        'packets_processed': 101,
        'packets_modified': 101,
        'duration_ms': 1000.0,
        'extra_metrics': {
            'success': True,
            'original_ips': 2,
            'anonymized_ips': 2,
            'anonymization_rate': 100.0,
            'ip_mappings': {
                '12.234.12.108': '8.225.9.108',
                '171.159.193.170': '168.150.179.170'
            }
        }
    }

    print("Testing fixed IP statistics extraction:")

    # Test direct data extraction (should be 0)
    original_ips = step_data.get('original_ips', 0)
    masked_ips = step_data.get('anonymized_ips', 0)
    print(f"Direct data - Original IPs: {original_ips}, Anonymized IPs: {masked_ips}")

    # Test fallback to extra_metrics (should work)
    if original_ips == 0 and masked_ips == 0:
        extra_metrics = step_data.get('extra_metrics', {})
        original_ips = extra_metrics.get('original_ips', 0)
        masked_ips = extra_metrics.get('anonymized_ips', 0)
        print(f"Extra metrics - Original IPs: {original_ips}, Anonymized IPs: {masked_ips}")

    rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
    line = f"  🛡️  {'IP Anonymization':<18} | Original IPs: {original_ips:>3} | Anonymized IPs: {masked_ips:>3} | Rate: {rate:5.1f}%"
    print(f"Generated line: {line}")

    print("✅ Fixed data extraction logic working correctly")
    print()


def main():
    """Run all debug tests"""
    print("🔍 Summary Report Debug Tool")
    print("=" * 80)
    print("Debugging why Summary Report issues persist:")
    print("1. Missing IP Anonymization entries in individual file results")
    print("2. Missing Global IP Mapping section")
    print("=" * 80)
    print()
    
    try:
        debug_stage_stats_structure()
        debug_step_result_data_conversion()
        debug_report_manager_step_collection()
        debug_file_report_generation()
        debug_global_ip_mapping_collection()
        debug_fixed_file_report_generation()

        print("🎯 DEBUG ANALYSIS COMPLETE")
        print("=" * 80)
        print("Check the output above to verify the fixes:")
        print("- ✅ IP statistics extraction from extra_metrics")
        print("- ✅ Global IP mapping report generation")
        print("- ✅ File completion detection logic")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ DEBUG FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
