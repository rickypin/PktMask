#!/usr/bin/env python3
"""
测试修复后的maskstage导入和API兼容性

用于验证tls23_maskstage_e2e_validator.py的修复效果，
确保新的双模块架构导入和配置正确工作。

Author: PktMask Core Team
Version: v1.0
"""

import sys
import logging
from pathlib import Path

# Add src directory to Python path for module imports
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent  # Go up two levels to project root
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 配置日志
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("test_maskstage_import_fix")


def test_pipeline_executor_import():
    """测试PipelineExecutor导入"""
    logger.info("测试PipelineExecutor导入...")
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        logger.info("✅ PipelineExecutor导入成功")
        return True
    except ImportError as e:
        logger.error("❌ PipelineExecutor导入失败: %s", e)
        return False


def test_new_maskstage_import():
    """测试新MaskStage导入"""
    logger.info("测试NewMaskPayloadStage导入...")
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        logger.info("✅ NewMaskPayloadStage导入成功")
        return True
    except ImportError as e:
        logger.error("❌ NewMaskPayloadStage导入失败: %s", e)
        return False


def test_pipeline_executor_creation():
    """测试PipelineExecutor创建和配置"""
    logger.info("测试PipelineExecutor创建...")
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        
        config = {
            "dedup": {"enabled": False},
            "anon": {"enabled": False},
            "mask": {
                "enabled": True,
                "protocol": "tls",
                "mode": "enhanced",
                "marker_config": {
                    "tls": {
                        "preserve_handshake": True,
                        "preserve_application_data": False
                    }
                },
                "masker_config": {
                    "preserve_ratio": 0.3
                }
            }
        }
        
        executor = PipelineExecutor(config)
        logger.info("✅ PipelineExecutor创建成功")
        logger.info("   - 配置的stages数量: %d", len(executor.stages))
        return True
    except Exception as e:
        logger.error("❌ PipelineExecutor创建失败: %s", e)
        return False


def test_new_maskstage_creation():
    """测试NewMaskStage直接创建"""
    logger.info("测试NewMaskPayloadStage直接创建...")
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        config = {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "tls": {
                    "preserve_handshake": True,
                    "preserve_application_data": False
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
        
        mask_stage = NewMaskPayloadStage(config)
        logger.info("✅ NewMaskPayloadStage创建成功")
        logger.info("   - 协议类型: %s", mask_stage.protocol)
        logger.info("   - 处理模式: %s", mask_stage.mode)
        return True
    except Exception as e:
        logger.error("❌ NewMaskPayloadStage创建失败: %s", e)
        return False


def test_maskstage_initialization():
    """测试MaskStage初始化"""
    logger.info("测试NewMaskPayloadStage初始化...")
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        config = {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "tls": {
                    "preserve_handshake": True,
                    "preserve_application_data": False
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
        
        mask_stage = NewMaskPayloadStage(config)
        mask_stage.initialize()
        logger.info("✅ NewMaskPayloadStage初始化成功")
        return True
    except Exception as e:
        logger.error("❌ NewMaskPayloadStage初始化失败: %s", e)
        return False


def test_api_compatibility():
    """测试API兼容性"""
    logger.info("测试API兼容性...")
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        config = {
            "protocol": "tls",
            "mode": "enhanced"
        }
        
        mask_stage = NewMaskPayloadStage(config)
        
        # 检查关键方法是否存在
        required_methods = ['initialize', 'process_file', 'get_display_name']
        for method_name in required_methods:
            if not hasattr(mask_stage, method_name):
                logger.error("❌ 缺少必需方法: %s", method_name)
                return False
            logger.info("   - 方法 %s 存在", method_name)
        
        logger.info("✅ API兼容性检查通过")
        return True
    except Exception as e:
        logger.error("❌ API兼容性检查失败: %s", e)
        return False


def main():
    """主测试函数"""
    logger.info("开始测试maskstage导入修复效果...")
    
    tests = [
        ("PipelineExecutor导入", test_pipeline_executor_import),
        ("NewMaskStage导入", test_new_maskstage_import),
        ("PipelineExecutor创建", test_pipeline_executor_creation),
        ("NewMaskStage创建", test_new_maskstage_creation),
        ("MaskStage初始化", test_maskstage_initialization),
        ("API兼容性", test_api_compatibility),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info("\n" + "="*50)
        logger.info("测试: %s", test_name)
        logger.info("="*50)
        
        if test_func():
            passed += 1
        else:
            logger.error("测试失败: %s", test_name)
    
    logger.info("\n" + "="*50)
    logger.info("测试总结")
    logger.info("="*50)
    logger.info("通过: %d/%d", passed, total)
    
    if passed == total:
        logger.info("🎉 所有测试通过！maskstage导入修复成功")
        return 0
    else:
        logger.error("💥 有 %d 个测试失败", total - passed)
        return 1


if __name__ == "__main__":
    sys.exit(main())
