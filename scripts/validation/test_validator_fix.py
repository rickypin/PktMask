#!/usr/bin/env python3
"""
测试修复后的tls23_maskstage_e2e_validator.py

验证修复后的验证工具能够正常导入和运行基本功能。

Author: PktMask Core Team
Version: v1.0
"""

import sys
import logging
import tempfile
from pathlib import Path

# Add src directory to Python path for module imports
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent  # Go up two levels to project root
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 配置日志
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("test_validator_fix")


def test_validator_import():
    """测试验证工具的导入功能"""
    logger.info("测试验证工具导入功能...")
    
    try:
        # 导入验证工具的主要函数
        validator_path = script_dir / "tls23_maskstage_e2e_validator.py"
        
        # 使用exec来导入和测试模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("validator", validator_path)
        validator_module = importlib.util.module_from_spec(spec)
        
        # 执行模块以检查导入错误
        spec.loader.exec_module(validator_module)
        
        logger.info("✅ 验证工具导入成功")
        return True, validator_module
        
    except Exception as e:
        logger.error("❌ 验证工具导入失败: %s", e)
        return False, None


def test_maskstage_functions(validator_module):
    """测试maskstage处理函数"""
    logger.info("测试maskstage处理函数...")
    
    try:
        # 检查关键函数是否存在
        required_functions = [
            'run_maskstage_internal',
            'run_maskstage_direct',
            'validate_file',
            'validate_enhanced_tls_processing'
        ]
        
        for func_name in required_functions:
            if not hasattr(validator_module, func_name):
                logger.error("❌ 缺少必需函数: %s", func_name)
                return False
            logger.info("   - 函数 %s 存在", func_name)
        
        logger.info("✅ maskstage处理函数检查通过")
        return True
        
    except Exception as e:
        logger.error("❌ maskstage处理函数检查失败: %s", e)
        return False


def test_maskstage_internal_creation(validator_module):
    """测试内部maskstage创建（不实际处理文件）"""
    logger.info("测试内部maskstage创建...")
    
    try:
        # 创建临时文件路径
        with tempfile.NamedTemporaryFile(suffix='.pcap') as tmp_input:
            with tempfile.NamedTemporaryFile(suffix='.pcap') as tmp_output:
                input_path = Path(tmp_input.name)
                output_path = Path(tmp_output.name)
                
                # 创建一个空的pcap文件用于测试
                input_path.write_bytes(b'')
                
                try:
                    # 尝试调用内部处理函数（预期会失败，但不应该是导入错误）
                    result = validator_module.run_maskstage_internal(input_path, output_path, verbose=True)
                    # 如果没有抛出异常，说明处理成功（可能是降级处理）
                    logger.info("✅ 内部maskstage创建成功（处理完成）")
                    return True
                except ImportError as e:
                    logger.error("❌ 内部maskstage创建失败（导入错误）: %s", e)
                    return False
                except Exception as e:
                    # 检查是否是预期的文件格式错误
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['文件太小', 'pcap', '文件格式', 'file', 'invalid']):
                        logger.info("✅ 内部maskstage创建成功（预期的文件格式错误）")
                        return True
                    else:
                        logger.error("❌ 内部maskstage创建失败（意外错误）: %s", str(e)[:100])
                        return False
                    
    except Exception as e:
        logger.error("❌ 内部maskstage创建测试失败: %s", e)
        return False


def test_maskstage_direct_creation(validator_module):
    """测试直接maskstage创建（不实际处理文件）"""
    logger.info("测试直接maskstage创建...")
    
    try:
        # 创建临时文件路径
        with tempfile.NamedTemporaryFile(suffix='.pcap') as tmp_input:
            with tempfile.NamedTemporaryFile(suffix='.pcap') as tmp_output:
                input_path = Path(tmp_input.name)
                output_path = Path(tmp_output.name)
                
                # 创建一个空的pcap文件用于测试
                input_path.write_bytes(b'')
                
                try:
                    # 尝试调用直接处理函数（预期会失败，但不应该是导入错误）
                    result = validator_module.run_maskstage_direct(input_path, output_path, verbose=True)
                    # 如果没有抛出异常，说明处理成功（可能是降级处理）
                    logger.info("✅ 直接maskstage创建成功（处理完成）")
                    return True
                except ImportError as e:
                    logger.error("❌ 直接maskstage创建失败（导入错误）: %s", e)
                    return False
                except Exception as e:
                    # 检查是否是预期的文件格式错误
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['文件太小', 'pcap', '文件格式', 'file', 'invalid']):
                        logger.info("✅ 直接maskstage创建成功（预期的文件格式错误）")
                        return True
                    else:
                        logger.error("❌ 直接maskstage创建失败（意外错误）: %s", str(e)[:100])
                        return False
                    
    except Exception as e:
        logger.error("❌ 直接maskstage创建测试失败: %s", e)
        return False


def test_validation_functions(validator_module):
    """测试验证函数"""
    logger.info("测试验证函数...")
    
    try:
        # 创建临时JSON文件用于测试
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_json:
            # 写入基本的JSON结构
            import json
            test_data = {
                "matches": [
                    {
                        "frame": 1,
                        "protocol_types": [23],
                        "lengths": [100],
                        "zero_bytes": 95,
                        "payload_preview": "1603030000" + "0" * 190
                    }
                ]
            }
            json.dump(test_data, tmp_json)
            tmp_json.flush()
            
            json_path = Path(tmp_json.name)
            
            try:
                # 测试验证函数
                result = validator_module.validate_file(json_path, json_path)
                logger.info("   - validate_file 返回结果: %s", result.get('status', 'unknown'))
                
                # 测试增强验证函数
                enhanced_result = validator_module.validate_enhanced_tls_processing(json_path, json_path)
                logger.info("   - validate_enhanced_tls_processing 返回结果: %s", enhanced_result.get('overall', {}).get('status', 'unknown'))
                
                logger.info("✅ 验证函数测试通过")
                return True
                
            finally:
                # 清理临时文件
                json_path.unlink(missing_ok=True)
                
    except Exception as e:
        logger.error("❌ 验证函数测试失败: %s", e)
        return False


def main():
    """主测试函数"""
    logger.info("开始测试修复后的验证工具...")
    
    # 测试导入
    success, validator_module = test_validator_import()
    if not success:
        logger.error("💥 验证工具导入失败，无法继续测试")
        return 1
    
    tests = [
        ("maskstage处理函数", lambda: test_maskstage_functions(validator_module)),
        ("内部maskstage创建", lambda: test_maskstage_internal_creation(validator_module)),
        ("直接maskstage创建", lambda: test_maskstage_direct_creation(validator_module)),
        ("验证函数", lambda: test_validation_functions(validator_module)),
    ]
    
    passed = 1  # 导入测试已通过
    total = len(tests) + 1  # 包括导入测试
    
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
        logger.info("🎉 所有测试通过！验证工具修复成功")
        return 0
    else:
        logger.error("💥 有 %d 个测试失败", total - passed)
        return 1


if __name__ == "__main__":
    sys.exit(main())
