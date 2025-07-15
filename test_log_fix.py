#!/usr/bin/env python3
"""
Test script to verify the GUI log module fixes.
This script simulates the pipeline processing and checks the log output format.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.services.pipeline_service import _handle_stage_progress, _get_stage_display_name
from pktmask.core.pipeline.models import StageStats
from pktmask.core.pipeline.stages.anon_ip import AnonStage
from pktmask.core.pipeline.stages.dedup import DeduplicationStage
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
from pktmask.core.events import PipelineEvents


class MockStage:
    def __init__(self, name):
        self.name = name


def test_stage_display_names():
    """Test that stage display names are correctly mapped"""
    print("=== Testing Stage Display Names ===")
    
    test_cases = [
        ('DedupStage', 'Deduplication Stage'),
        ('DeduplicationStage', 'Deduplication Stage'),
        ('AnonStage', 'IP Anonymization Stage'),
        ('NewMaskPayloadStage', 'Payload Masking Stage'),
        ('UnnamedStage', 'UnnamedStage'),  # Should fallback to original name
    ]
    
    for stage_name, expected in test_cases:
        result = _get_stage_display_name(stage_name)
        status = "✓" if result == expected else "✗"
        print(f"{status} {stage_name} -> {result} (expected: {expected})")


def test_log_output_format():
    """Test the log output format for different stages"""
    print("\n=== Testing Log Output Format ===")
    
    # Test DeduplicationStage
    dedup_stage = MockStage('DeduplicationStage')
    dedup_stats = StageStats(
        stage_name='DeduplicationStage',
        packets_processed=2111,
        packets_modified=0,
        duration_ms=1000.0
    )
    
    print("DeduplicationStage log:")
    _handle_stage_progress(dedup_stage, dedup_stats, lambda event, data: print(f"  {data['message']}"))
    
    # Test AnonStage with IP statistics
    anon_stage = MockStage('AnonStage')
    anon_stats = StageStats(
        stage_name='AnonStage',
        packets_processed=2111,
        packets_modified=1500,
        duration_ms=2000.0,
        extra_metrics={
            'original_ips': 150,
            'anonymized_ips': 150,
            'ip_mappings_count': 150
        }
    )
    
    print("AnonStage log (with IP statistics):")
    _handle_stage_progress(anon_stage, anon_stats, lambda event, data: print(f"  {data['message']}"))
    
    # Test AnonStage without IP statistics (fallback)
    anon_stats_fallback = StageStats(
        stage_name='AnonStage',
        packets_processed=2111,
        packets_modified=1500,
        duration_ms=2000.0
    )
    
    print("AnonStage log (fallback to packet count):")
    _handle_stage_progress(anon_stage, anon_stats_fallback, lambda event, data: print(f"  {data['message']}"))
    
    # Test NewMaskPayloadStage
    mask_stage = MockStage('NewMaskPayloadStage')
    mask_stats = StageStats(
        stage_name='NewMaskPayloadStage',
        packets_processed=2111,
        packets_modified=1358,
        duration_ms=3000.0
    )
    
    print("NewMaskPayloadStage log:")
    _handle_stage_progress(mask_stage, mask_stats, lambda event, data: print(f"  {data['message']}"))


def test_stage_stats_properties():
    """Test the new StageStats properties for IP statistics"""
    print("\n=== Testing StageStats IP Properties ===")
    
    # Test with IP statistics
    stats_with_ips = StageStats(
        stage_name='AnonStage',
        packets_processed=2111,
        packets_modified=1500,
        duration_ms=2000.0,
        extra_metrics={
            'original_ips': 150,
            'anonymized_ips': 150
        }
    )
    
    print(f"Stats with IP data:")
    print(f"  original_ips: {stats_with_ips.original_ips}")
    print(f"  anonymized_ips: {stats_with_ips.anonymized_ips}")
    
    # Test without IP statistics
    stats_without_ips = StageStats(
        stage_name='DeduplicationStage',
        packets_processed=2111,
        packets_modified=0,
        duration_ms=1000.0
    )
    
    print(f"Stats without IP data:")
    print(f"  original_ips: {stats_without_ips.original_ips}")
    print(f"  anonymized_ips: {stats_without_ips.anonymized_ips}")


def test_actual_stage_names():
    """Test the actual stage name properties"""
    print("\n=== Testing Actual Stage Names ===")
    
    # Test AnonStage
    anon_stage = AnonStage()
    print(f"AnonStage.name: {anon_stage.name}")
    
    # Test DeduplicationStage
    dedup_stage = DeduplicationStage()
    print(f"DeduplicationStage.name: {dedup_stage.name}")
    
    # Test NewMaskPayloadStage
    mask_stage = NewMaskPayloadStage({})
    print(f"NewMaskPayloadStage.name: {mask_stage.name}")
    print(f"NewMaskPayloadStage.get_display_name(): {mask_stage.get_display_name()}")


if __name__ == "__main__":
    print("Testing GUI Log Module Fixes")
    print("=" * 50)
    
    test_stage_display_names()
    test_log_output_format()
    test_stage_stats_properties()
    test_actual_stage_names()
    
    print("\n" + "=" * 50)
    print("Test completed!")
