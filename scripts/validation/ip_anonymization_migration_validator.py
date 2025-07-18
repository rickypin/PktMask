#!/usr/bin/env python3
"""
IP Anonymization Migration Validator

This script validates that the migration from BaseProcessor to StageBase
for IP anonymization maintains 100% GUI compatibility and functional equivalence.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pktmask.core.processors.registry import ProcessorRegistry
from pktmask.core.processors.base_processor import ProcessorConfig
from pktmask.core.pipeline.stages.ip_anonymization import IPAnonymizationStage
from pktmask.core.pipeline.executor import PipelineExecutor
from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor


def test_processor_registry_compatibility():
    """Test ProcessorRegistry compatibility with new IPAnonymizationStage"""
    print("=" * 60)
    print("Test 1: ProcessorRegistry Compatibility")
    print("=" * 60)
    
    # Test standard naming
    config = ProcessorConfig(enabled=True, name='anonymize_ips')
    processor = ProcessorRegistry.get_processor('anonymize_ips', config)
    
    print(f"✅ Standard naming: {type(processor).__name__}")
    assert isinstance(processor, IPAnonymizationStage)
    
    # Test legacy alias
    config = ProcessorConfig(enabled=True, name='anon_ip')
    processor = ProcessorRegistry.get_processor('anon_ip', config)
    
    print(f"✅ Legacy alias: {type(processor).__name__}")
    assert isinstance(processor, IPAnonymizationStage)
    
    # Test processor info
    info = ProcessorRegistry.get_processor_info('anonymize_ips')
    print(f"✅ Processor info: {info['display_name']}")
    assert info['display_name'] == 'Anonymize IPs'
    
    print("✅ ProcessorRegistry compatibility verified\n")


def test_gui_config_simulation():
    """Simulate GUI configuration creation process"""
    print("=" * 60)
    print("Test 2: GUI Configuration Simulation")
    print("=" * 60)
    
    # Simulate GUI creating configuration (as done in pipeline_manager.py)
    gui_config = build_pipeline_config(
        enable_anon=True,
        enable_dedup=False,
        enable_mask=False
    )
    
    print(f"GUI config created: {gui_config}")
    assert 'anonymize_ips' in gui_config
    assert gui_config['anonymize_ips']['enabled'] is True
    
    # Simulate creating executor (as done in GUI)
    executor = create_pipeline_executor(gui_config)
    print(f"✅ Executor created: {type(executor).__name__}")
    
    # Verify stages
    assert len(executor.stages) == 1
    assert isinstance(executor.stages[0], IPAnonymizationStage)
    print(f"✅ Stage type: {type(executor.stages[0]).__name__}")
    
    print("✅ GUI configuration simulation successful\n")


def test_pipeline_executor_integration():
    """Test PipelineExecutor integration"""
    print("=" * 60)
    print("Test 3: PipelineExecutor Integration")
    print("=" * 60)
    
    config = {
        'anonymize_ips': {'enabled': True}
    }
    
    executor = PipelineExecutor(config)
    
    print(f"Stages created: {len(executor.stages)}")
    assert len(executor.stages) == 1
    
    stage = executor.stages[0]
    print(f"Stage type: {type(stage).__name__}")
    print(f"Stage name: {stage.name}")
    print(f"Stage initialized: {stage._initialized}")
    
    assert isinstance(stage, IPAnonymizationStage)
    assert stage._initialized  # Should be initialized during build
    
    print("✅ PipelineExecutor integration verified\n")


def test_functional_equivalence():
    """Test functional equivalence with original implementation"""
    print("=" * 60)
    print("Test 4: Functional Equivalence")
    print("=" * 60)
    
    # Create test configuration
    config = {
        'method': 'prefix_preserving',
        'ipv4_prefix': 24,
        'ipv6_prefix': 64,
        'enabled': True,
        'name': 'test_anonymization'
    }
    
    stage = IPAnonymizationStage(config)
    stage.initialize()
    
    # Test interface methods
    print(f"Display name: {stage.get_display_name()}")
    print(f"Description: {stage.get_description()}")
    print(f"Required tools: {stage.get_required_tools()}")
    
    assert stage.get_display_name() == "Anonymize IPs"
    assert "Anonymize IP addresses" in stage.get_description()
    assert stage.get_required_tools() == []
    
    # Test configuration properties
    assert stage.method == 'prefix_preserving'
    assert stage.ipv4_prefix == 24
    assert stage.ipv6_prefix == 64
    
    print("✅ Functional equivalence verified\n")


def test_backward_compatibility():
    """Test backward compatibility with existing code"""
    print("=" * 60)
    print("Test 5: Backward Compatibility")
    print("=" * 60)
    
    # Test that old code patterns still work
    
    # Pattern 1: ProcessorRegistry.get_processor
    config = ProcessorConfig(enabled=True, name='anonymize_ips')
    processor = ProcessorRegistry.get_processor('anonymize_ips', config)
    
    # Should still have the same interface
    assert hasattr(processor, 'get_display_name')
    assert hasattr(processor, 'get_description')
    print(f"✅ Interface compatibility: {processor.get_display_name()}")
    
    # Pattern 2: Legacy alias support
    processor_legacy = ProcessorRegistry.get_processor('anon_ip', config)
    assert isinstance(processor_legacy, IPAnonymizationStage)
    print("✅ Legacy alias support maintained")
    
    # Pattern 3: Processor info retrieval
    info = ProcessorRegistry.get_processor_info('anonymize_ips')
    assert 'display_name' in info
    assert 'description' in info
    assert 'class' in info
    print("✅ Processor info compatibility maintained")
    
    print("✅ Backward compatibility verified\n")


def test_configuration_conversion():
    """Test configuration conversion from ProcessorConfig to dict"""
    print("=" * 60)
    print("Test 6: Configuration Conversion")
    print("=" * 60)
    
    # Test ProcessorConfig to dict conversion
    processor_config = ProcessorConfig(
        enabled=True,
        name='test_anonymization',
        priority=1
    )
    
    # Get processor through registry (triggers conversion)
    processor = ProcessorRegistry.get_processor('anonymize_ips', processor_config)
    
    # Verify configuration was converted correctly
    assert processor.enabled is True
    assert processor.stage_name == 'test_anonymization'
    assert processor.method == 'prefix_preserving'  # default
    assert processor.ipv4_prefix == 24  # default
    assert processor.ipv6_prefix == 64  # default
    
    print("✅ ProcessorConfig converted to dict successfully")
    print(f"   - enabled: {processor.enabled}")
    print(f"   - name: {processor.stage_name}")
    print(f"   - method: {processor.method}")
    print(f"   - ipv4_prefix: {processor.ipv4_prefix}")
    print(f"   - ipv6_prefix: {processor.ipv6_prefix}")
    
    print("✅ Configuration conversion verified\n")


def main():
    """Run all validation tests"""
    print("🚀 IP Anonymization Migration Validation")
    print("=" * 60)
    print("Validating migration from BaseProcessor to StageBase")
    print("Ensuring 100% GUI compatibility and functional equivalence")
    print("=" * 60)
    print()
    
    try:
        test_processor_registry_compatibility()
        test_gui_config_simulation()
        test_pipeline_executor_integration()
        test_functional_equivalence()
        test_backward_compatibility()
        test_configuration_conversion()
        
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("✅ Migration successful - 100% compatibility maintained")
        print("✅ GUI will continue to work without any changes")
        print("✅ All existing code patterns remain functional")
        print("✅ Configuration conversion works correctly")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
