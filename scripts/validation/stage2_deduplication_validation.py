#!/usr/bin/env python3
"""
阶段2验证：去重功能迁移验证脚本

验证UnifiedDeduplicationStage是否正确替代了Deduplicator，
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
        
        # 测试获取去重处理器
        deduplicator = ProcessorRegistry.get_processor('remove_dupes', test_config)
        print(f"✅ 成功获取remove_dupes处理器: {type(deduplicator).__name__}")
        
        # 验证是否为UnifiedDeduplicationStage
        expected_class_name = "UnifiedDeduplicationStage"
        actual_class_name = type(deduplicator).__name__
        
        if actual_class_name == expected_class_name:
            print(f"✅ 处理器类型正确: {actual_class_name}")
        else:
            print(f"❌ 处理器类型错误: 期望 {expected_class_name}, 实际 {actual_class_name}")
            return False
        
        # 测试别名映射
        deduplicator_alias = ProcessorRegistry.get_processor('dedup_packet', test_config)
        if type(deduplicator_alias).__name__ == expected_class_name:
            print(f"✅ 别名映射正确: dedup_packet -> {type(deduplicator_alias).__name__}")
        else:
            print(f"❌ 别名映射错误: dedup_packet -> {type(deduplicator_alias).__name__}")
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
            name="test_deduplication",
            priority=1
        )
        
        # 获取处理器实例
        deduplicator = ProcessorRegistry.get_processor('remove_dupes', test_config)
        
        # 验证配置属性
        expected_attrs = ['algorithm', 'enabled']
        for attr in expected_attrs:
            if hasattr(deduplicator, attr):
                print(f"✅ 配置属性存在: {attr} = {getattr(deduplicator, attr)}")
            else:
                print(f"❌ 配置属性缺失: {attr}")
                return False
        
        # 验证默认值
        if deduplicator.algorithm == "md5":
            print("✅ 默认哈希算法正确")
        else:
            print(f"❌ 默认哈希算法错误: {deduplicator.algorithm}")
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
        deduplicator = ProcessorRegistry.get_processor('remove_dupes', test_config)
        
        # 验证必要方法存在
        required_methods = ['process_file', 'get_display_name', 'get_description']
        for method in required_methods:
            if hasattr(deduplicator, method) and callable(getattr(deduplicator, method)):
                print(f"✅ 方法存在: {method}")
            else:
                print(f"❌ 方法缺失: {method}")
                return False
        
        # 验证显示名称
        display_name = deduplicator.get_display_name()
        if display_name == "Remove Dupes":
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
            deduplicator = ProcessorRegistry.get_processor('remove_dupes', test_config)
            
            # 初始化处理器
            if hasattr(deduplicator, 'initialize'):
                deduplicator.initialize()
            
            # 处理文件
            result = deduplicator.process_file(temp_input_path, temp_output_path)
            
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
                    expected_metrics = ['algorithm', 'total_packets', 'unique_packets', 'removed_count', 'deduplication_rate']
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


def test_deduplication_algorithm():
    """测试去重算法准确性"""
    print("\n🔍 测试去重算法准确性...")
    
    try:
        # 创建包含重复数据包的测试文件
        from scapy.all import Ether, IP, UDP, wrpcap
        
        # 创建测试数据包
        pkt1 = Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/UDP(sport=1234, dport=5678)/b"test data"
        pkt2 = Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/UDP(sport=1234, dport=5678)/b"test data"  # 重复
        pkt3 = Ether()/IP(src="192.168.1.3", dst="192.168.1.4")/UDP(sport=1234, dport=5678)/b"different data"
        
        packets = [pkt1, pkt2, pkt3]  # 3个包，其中2个重复
        
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_input:
            temp_input_path = temp_input.name
            wrpcap(temp_input_path, packets)
        
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        try:
            # 创建测试配置
            test_config = ProcessorConfig(
                enabled=True,
                name="test_algorithm",
                priority=0
            )
            
            # 获取处理器并处理文件
            deduplicator = ProcessorRegistry.get_processor('remove_dupes', test_config)
            
            # 初始化处理器
            if hasattr(deduplicator, 'initialize'):
                deduplicator.initialize()
            
            # 处理文件
            result = deduplicator.process_file(temp_input_path, temp_output_path)
            
            # 验证去重结果
            total_packets = result.extra_metrics.get('total_packets', 0)
            unique_packets = result.extra_metrics.get('unique_packets', 0)
            removed_count = result.extra_metrics.get('removed_count', 0)
            
            print(f"✅ 总数据包: {total_packets}")
            print(f"✅ 唯一数据包: {unique_packets}")
            print(f"✅ 移除重复: {removed_count}")
            
            # 验证去重逻辑
            if total_packets == 3 and unique_packets == 2 and removed_count == 1:
                print("✅ 去重算法正确：正确识别并移除了1个重复数据包")
                return True
            else:
                print(f"❌ 去重算法错误：期望3->2(移除1)，实际{total_packets}->{unique_packets}(移除{removed_count})")
                return False
                
        finally:
            # 清理临时文件
            Path(temp_input_path).unlink(missing_ok=True)
            Path(temp_output_path).unlink(missing_ok=True)
        
    except Exception as e:
        print(f"❌ 去重算法测试失败: {e}")
        return False


def main():
    """主验证函数"""
    print("=" * 60)
    print("阶段2验证：去重功能迁移验证")
    print("=" * 60)
    
    tests = [
        ("ProcessorRegistry映射", test_processor_registry_mapping),
        ("配置格式转换", test_configuration_format),
        ("接口兼容性", test_interface_compatibility),
        ("返回类型格式", test_return_type_format),
        ("去重算法准确性", test_deduplication_algorithm),
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
        print("🎉 阶段2验证完全成功！")
        print("✅ UnifiedDeduplicationStage已成功替代Deduplicator")
        print("✅ 所有接口和功能保持兼容")
        return True
    else:
        print("❌ 阶段2验证存在问题，需要修复")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
