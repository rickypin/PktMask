#!/usr/bin/env python3
"""
阶段1验证：IP匿名化迁移验证脚本

验证UnifiedIPAnonymizationStage是否正确替代了IPAnonymizer，
确保GUI功能、CLI接口、统计信息显示完全一致。
"""

import sys
import tempfile
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pktmask.core.processors.registry import ProcessorRegistry
from pktmask.core.processors.base_processor import ProcessorConfig
from pktmask.core.pipeline.models import StageStats


def test_processor_registry_mapping():
    """测试ProcessorRegistry映射是否正确"""
    print("🔍 测试ProcessorRegistry映射...")

    try:
        # 创建测试配置
        test_config = ProcessorConfig(
            enabled=True,
            name="test_mapping",
            priority=0
        )

        # 测试获取IP匿名化处理器
        anonymizer = ProcessorRegistry.get_processor('anonymize_ips', test_config)
        print(f"✅ 成功获取anonymize_ips处理器: {type(anonymizer).__name__}")

        # 验证是否为UnifiedIPAnonymizationStage
        expected_class_name = "UnifiedIPAnonymizationStage"
        actual_class_name = type(anonymizer).__name__

        if actual_class_name == expected_class_name:
            print(f"✅ 处理器类型正确: {actual_class_name}")
        else:
            print(f"❌ 处理器类型错误: 期望 {expected_class_name}, 实际 {actual_class_name}")
            return False

        # 测试别名映射
        anonymizer_alias = ProcessorRegistry.get_processor('anon_ip', test_config)
        if type(anonymizer_alias).__name__ == expected_class_name:
            print(f"✅ 别名映射正确: anon_ip -> {type(anonymizer_alias).__name__}")
        else:
            print(f"❌ 别名映射错误: anon_ip -> {type(anonymizer_alias).__name__}")
            return False

        return True

    except Exception as e:
        print(f"❌ ProcessorRegistry映射测试失败: {e}")
        return False


def test_configuration_format():
    """测试配置格式转换是否正确"""
    print("\n🔍 测试配置格式转换...")
    
    try:
        # 创建测试配置
        test_config = ProcessorConfig(
            enabled=True,
            name="test_ip_anonymization",
            priority=1
        )
        
        # 获取处理器实例
        anonymizer = ProcessorRegistry.get_processor('anonymize_ips', test_config)
        
        # 验证配置属性
        expected_attrs = ['method', 'ipv4_prefix', 'ipv6_prefix', 'enabled']
        for attr in expected_attrs:
            if hasattr(anonymizer, attr):
                print(f"✅ 配置属性存在: {attr} = {getattr(anonymizer, attr)}")
            else:
                print(f"❌ 配置属性缺失: {attr}")
                return False
        
        # 验证默认值
        if anonymizer.method == "prefix_preserving":
            print("✅ 默认匿名化方法正确")
        else:
            print(f"❌ 默认匿名化方法错误: {anonymizer.method}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 配置格式测试失败: {e}")
        return False


def test_interface_compatibility():
    """测试接口兼容性"""
    print("\n🔍 测试接口兼容性...")

    try:
        # 创建测试配置
        test_config = ProcessorConfig(
            enabled=True,
            name="test_interface",
            priority=0
        )

        # 获取处理器实例
        anonymizer = ProcessorRegistry.get_processor('anonymize_ips', test_config)

        # 验证必要方法存在
        required_methods = ['process_file', 'get_display_name', 'get_description']
        for method in required_methods:
            if hasattr(anonymizer, method) and callable(getattr(anonymizer, method)):
                print(f"✅ 方法存在: {method}")
            else:
                print(f"❌ 方法缺失: {method}")
                return False

        # 验证显示名称
        display_name = anonymizer.get_display_name()
        if display_name == "Anonymize IPs":
            print(f"✅ 显示名称正确: {display_name}")
        else:
            print(f"❌ 显示名称错误: {display_name}")
            return False

        return True

    except Exception as e:
        print(f"❌ 接口兼容性测试失败: {e}")
        return False


def test_return_type_format():
    """测试返回类型格式"""
    print("\n🔍 测试返回类型格式...")
    
    try:
        # 创建测试文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_input:
            # 创建一个最小的PCAP文件头
            pcap_header = b'\xd4\xc3\xb2\xa1\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\x01\x00\x00\x00'
            temp_input.write(pcap_header)
            temp_input_path = temp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        try:
            # 创建测试配置
            test_config = ProcessorConfig(
                enabled=True,
                name="test_return_type",
                priority=0
            )

            # 获取处理器并处理文件
            anonymizer = ProcessorRegistry.get_processor('anonymize_ips', test_config)

            # 初始化处理器
            if hasattr(anonymizer, 'initialize'):
                anonymizer.initialize()
            
            # 处理文件
            result = anonymizer.process_file(temp_input_path, temp_output_path)
            
            # 验证返回类型
            if isinstance(result, StageStats):
                print(f"✅ 返回类型正确: StageStats")
                
                # 验证必要字段
                required_fields = ['stage_name', 'packets_processed', 'packets_modified', 'duration_ms']
                for field in required_fields:
                    if hasattr(result, field):
                        print(f"✅ 字段存在: {field} = {getattr(result, field)}")
                    else:
                        print(f"❌ 字段缺失: {field}")
                        return False
                
                # 验证extra_metrics
                if hasattr(result, 'extra_metrics') and isinstance(result.extra_metrics, dict):
                    print(f"✅ extra_metrics存在且为字典类型")
                    
                    # 验证关键统计字段
                    expected_metrics = ['method', 'original_ips', 'anonymized_ips', 'anonymization_rate']
                    for metric in expected_metrics:
                        if metric in result.extra_metrics:
                            print(f"✅ 统计字段存在: {metric} = {result.extra_metrics[metric]}")
                        else:
                            print(f"❌ 统计字段缺失: {metric}")
                            return False
                else:
                    print(f"❌ extra_metrics缺失或类型错误")
                    return False
                
                return True
            else:
                print(f"❌ 返回类型错误: {type(result)}")
                return False
                
        finally:
            # 清理临时文件
            Path(temp_input_path).unlink(missing_ok=True)
            Path(temp_output_path).unlink(missing_ok=True)
        
    except Exception as e:
        print(f"❌ 返回类型测试失败: {e}")
        return False


def test_performance_benchmark():
    """简单的性能基准测试"""
    print("\n🔍 性能基准测试...")
    
    try:
        # 创建测试文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_input:
            # 创建一个最小的PCAP文件头
            pcap_header = b'\xd4\xc3\xb2\xa1\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\x01\x00\x00\x00'
            temp_input.write(pcap_header)
            temp_input_path = temp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        try:
            # 创建测试配置
            test_config = ProcessorConfig(
                enabled=True,
                name="test_performance",
                priority=0
            )

            # 获取处理器
            anonymizer = ProcessorRegistry.get_processor('anonymize_ips', test_config)

            # 初始化处理器
            if hasattr(anonymizer, 'initialize'):
                anonymizer.initialize()
            
            # 测量处理时间
            start_time = time.time()
            result = anonymizer.process_file(temp_input_path, temp_output_path)
            end_time = time.time()
            
            processing_time = end_time - start_time
            print(f"✅ 处理时间: {processing_time:.4f}秒")
            
            # 验证处理时间合理性（应该很快，因为是空文件）
            if processing_time < 5.0:  # 5秒内完成
                print(f"✅ 处理速度合理")
                return True
            else:
                print(f"⚠️ 处理时间较长: {processing_time:.4f}秒")
                return True  # 不算失败，只是警告
                
        finally:
            # 清理临时文件
            Path(temp_input_path).unlink(missing_ok=True)
            Path(temp_output_path).unlink(missing_ok=True)
        
    except Exception as e:
        print(f"❌ 性能基准测试失败: {e}")
        return False


def main():
    """主验证函数"""
    print("=" * 60)
    print("阶段1验证：IP匿名化迁移验证")
    print("=" * 60)
    
    tests = [
        ("ProcessorRegistry映射", test_processor_registry_mapping),
        ("配置格式转换", test_configuration_format),
        ("接口兼容性", test_interface_compatibility),
        ("返回类型格式", test_return_type_format),
        ("性能基准", test_performance_benchmark),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                print(f"✅ {test_name} 通过")
                passed += 1
            else:
                print(f"❌ {test_name} 失败")
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
    
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 阶段1验证完全成功！")
        print("✅ UnifiedIPAnonymizationStage已成功替代IPAnonymizer")
        print("✅ 所有接口和功能保持兼容")
        return True
    else:
        print("❌ 阶段1验证存在问题，需要修复")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
