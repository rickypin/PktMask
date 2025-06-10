#!/usr/bin/env python3

"""
Phase 3: GUI集成 - 测试脚本

测试新的处理器系统与现有GUI的集成是否正常工作。
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root / "src"))

def main():
    """主测试函数"""
    print("🚀 Phase 3: GUI集成测试")
    print("=" * 50)
    
    try:
        from pktmask.core.processors import (
            ProcessorRegistry, ProcessorConfig, ProcessorAdapter, 
            adapt_processors_to_pipeline, BaseProcessor
        )
        print("✅ 成功导入处理器模块")
    except ImportError as e:
        print(f"❌ 导入处理器模块失败: {e}")
        return False
    
    try:
        from pktmask.gui.managers.pipeline_manager import PipelineManager
        print("✅ 成功导入PipelineManager")
    except ImportError as e:
        print(f"❌ 导入PipelineManager失败: {e}")
        return False
    
    # 测试适配器创建
    print("\n🔍 测试处理器适配器...")
    try:
        config = ProcessorConfig(enabled=True, name='mask_ip')
        processor = ProcessorRegistry.get_processor('mask_ip', config)
        adapter = ProcessorAdapter(processor)
        
        assert adapter.name == "Mask IPs"
        assert adapter.suffix == "-Masked"
        print("  ✅ 处理器适配器测试通过")
    except Exception as e:
        print(f"  ❌ 处理器适配器测试失败: {e}")
        return False
    
    # 测试适配功能
    print("\n🔍 测试处理器适配功能...")
    try:
        processors = []
        for name in ['mask_ip', 'dedup_packet', 'trim_packet']:
            config = ProcessorConfig(enabled=True, name=name)
            processor = ProcessorRegistry.get_processor(name, config)
            processors.append(processor)
        
        steps = adapt_processors_to_pipeline(processors)
        assert len(steps) == 3
        print("  ✅ 处理器适配功能测试通过")
    except Exception as e:
        print(f"  ❌ 处理器适配功能测试失败: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 Phase 3 GUI集成测试 - 全部通过！")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 