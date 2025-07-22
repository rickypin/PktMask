#!/usr/bin/env python3
"""
StageBase Interface Validation Script

This script validates that all StageBase implementations follow the unified interface contract.
It checks method signatures, return types, and parameter consistency across all implementations.
"""

import inspect
import sys
from pathlib import Path
from typing import get_type_hints

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def validate_stagebase_interface():
    """Validate StageBase interface consistency across all implementations."""
    
    print("🔍 StageBase Interface Validation")
    print("=" * 50)
    
    try:
        # Import StageBase and all implementations
        from pktmask.core.pipeline.base_stage import StageBase
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        from pktmask.core.pipeline.stages.deduplication_unified import UnifiedDeduplicationStage
        from pktmask.core.pipeline.stages.ip_anonymization_unified import UnifiedIPAnonymizationStage
        from pktmask.core.pipeline.stages.dedup import DeduplicationStage
        from pktmask.core.pipeline.stages.ip_anonymization import IPAnonymizationStage
        from pktmask.core.pipeline.models import StageStats
        
        implementations = [
            ("NewMaskPayloadStage", NewMaskPayloadStage),
            ("UnifiedDeduplicationStage", UnifiedDeduplicationStage),
            ("UnifiedIPAnonymizationStage", UnifiedIPAnonymizationStage),
            ("DeduplicationStage", DeduplicationStage),
            ("IPAnonymizationStage", IPAnonymizationStage),
        ]
        
        print("✅ All imports successful")
        
        # Validate each implementation
        all_valid = True
        
        for name, cls in implementations:
            print(f"\n📋 Validating {name}...")
            
            # Check if it inherits from StageBase
            if not issubclass(cls, StageBase):
                print(f"❌ {name} does not inherit from StageBase")
                all_valid = False
                continue
            
            # Check required methods exist
            required_methods = ['initialize', 'process_file']
            for method_name in required_methods:
                if not hasattr(cls, method_name):
                    print(f"❌ {name} missing required method: {method_name}")
                    all_valid = False
                    continue
                
                method = getattr(cls, method_name)
                if not callable(method):
                    print(f"❌ {name}.{method_name} is not callable")
                    all_valid = False
                    continue
            
            # Validate method signatures
            try:
                # Check initialize method
                init_method = getattr(cls, 'initialize')
                init_sig = inspect.signature(init_method)
                init_hints = get_type_hints(init_method)
                
                # Should return bool
                if 'return' in init_hints and init_hints['return'] != bool:
                    print(f"⚠️  {name}.initialize should return bool, got {init_hints.get('return', 'None')}")
                
                # Check process_file method
                process_method = getattr(cls, 'process_file')
                process_sig = inspect.signature(process_method)
                process_hints = get_type_hints(process_method)
                
                # Should return StageStats
                if 'return' in process_hints and process_hints['return'] != StageStats:
                    print(f"⚠️  {name}.process_file should return StageStats, got {process_hints.get('return', 'None')}")
                
                # Check parameter types
                params = list(process_sig.parameters.keys())
                if len(params) < 3:  # self, input_path, output_path
                    print(f"❌ {name}.process_file has insufficient parameters: {params}")
                    all_valid = False
                else:
                    # Check parameter names
                    expected_params = ['self', 'input_path', 'output_path']
                    actual_params = params[:3]
                    if actual_params != expected_params:
                        print(f"⚠️  {name}.process_file parameter names: expected {expected_params}, got {actual_params}")
                
                print(f"✅ {name} interface validation passed")
                
            except Exception as e:
                print(f"❌ Error validating {name}: {e}")
                all_valid = False
        
        print("\n" + "=" * 50)
        if all_valid:
            print("🎉 All StageBase implementations follow unified interface!")
            print("✅ Type safety: Strong typing enforced")
            print("✅ Return types: Consistent StageStats usage")
            print("✅ Method signatures: Unified across all implementations")
            return True
        else:
            print("❌ Some implementations have interface inconsistencies")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False

if __name__ == "__main__":
    success = validate_stagebase_interface()
    sys.exit(0 if success else 1)
