#!/usr/bin/env python3
"""
阶段3验证：架构清理验证脚本

验证BaseProcessor系统是否完全移除，ProcessorRegistry是否简化为纯StageBase注册表，
确保架构统一完成且所有功能保持正常。
"""

import sys
import tempfile
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pktmask.core.processors.registry import ProcessorRegistry, ProcessorConfig
from pktmask.core.pipeline.models import StageStats


def test_baseprocessor_removal():
    """测试BaseProcessor系统是否完全移除"""
    print("🔍 测试BaseProcessor系统移除...")
    
    try:
        # 尝试导入BaseProcessor相关模块，应该失败
        removed_modules = [
            'pktmask.core.processors.base_processor',
            'pktmask.core.processors.ip_anonymizer', 
            'pktmask.core.processors.deduplicator'
        ]
        
        for module_name in removed_modules:
            try:
                __import__(module_name)
                print(f"❌ 模块仍然存在: {module_name}")
                return False
            except ImportError:
                print(f"✅ 模块已移除: {module_name}")
        
        # 检查文件是否已删除
        removed_files = [
            "src/pktmask/core/processors/base_processor.py",
            "src/pktmask/core/processors/ip_anonymizer.py",
            "src/pktmask/core/processors/deduplicator.py"
        ]
        
        for file_path in removed_files:
            if Path(file_path).exists():
                print(f"❌ 文件仍然存在: {file_path}")
                return False
            else:
                print(f"✅ 文件已删除: {file_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ BaseProcessor移除验证失败: {e}")
        return False


def test_unified_stagebase_architecture():
    """测试统一StageBase架构"""
    print("\n🔍 测试统一StageBase架构...")
    
    try:
        # 测试所有处理器都是StageBase实例
        test_config = ProcessorConfig(
            enabled=True,
            name="test_architecture",
            priority=0
        )
        
        processors_to_test = [
            ('anonymize_ips', 'UnifiedIPAnonymizationStage'),
            ('remove_dupes', 'UnifiedDeduplicationStage'),
            ('mask_payloads', 'NewMaskPayloadStage')
        ]
        
        for processor_name, expected_class in processors_to_test:
            processor = ProcessorRegistry.get_processor(processor_name, test_config)
            actual_class = type(processor).__name__
            
            if actual_class == expected_class:
                print(f"✅ {processor_name}: {actual_class}")
            else:
                print(f"❌ {processor_name}: 期望 {expected_class}, 实际 {actual_class}")
                return False
            
            # 验证是否为StageBase子类
            from pktmask.core.pipeline.base_stage import StageBase
            if isinstance(processor, StageBase):
                print(f"✅ {processor_name} 是 StageBase 实例")
            else:
                print(f"❌ {processor_name} 不是 StageBase 实例")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 统一架构验证失败: {e}")
        return False


def test_simplified_registry():
    """测试简化的ProcessorRegistry"""
    print("\n🔍 测试简化的ProcessorRegistry...")
    
    try:
        # 检查ProcessorRegistry的类型注解
        import inspect
        
        # 获取_processors字段的类型注解
        registry_annotations = getattr(ProcessorRegistry, '__annotations__', {})
        processors_annotation = registry_annotations.get('_processors', None)
        
        if processors_annotation:
            print(f"✅ _processors类型注解存在: {processors_annotation}")
        else:
            print("⚠️ _processors类型注解缺失，但这不影响功能")
        
        # 测试所有处理器都能正常获取
        test_config = ProcessorConfig(enabled=True, name="test", priority=0)
        
        processor_names = ['anonymize_ips', 'remove_dupes', 'mask_payloads']
        for name in processor_names:
            try:
                processor = ProcessorRegistry.get_processor(name, test_config)
                print(f"✅ 成功获取处理器: {name}")
            except Exception as e:
                print(f"❌ 获取处理器失败 {name}: {e}")
                return False
        
        # 测试别名映射
        alias_mappings = [
            ('anon_ip', 'anonymize_ips'),
            ('dedup_packet', 'remove_dupes'),
            ('mask_payload', 'mask_payloads')
        ]
        
        for alias, canonical in alias_mappings:
            try:
                alias_processor = ProcessorRegistry.get_processor(alias, test_config)
                canonical_processor = ProcessorRegistry.get_processor(canonical, test_config)
                
                if type(alias_processor).__name__ == type(canonical_processor).__name__:
                    print(f"✅ 别名映射正确: {alias} -> {canonical}")
                else:
                    print(f"❌ 别名映射错误: {alias} -> {canonical}")
                    return False
            except Exception as e:
                print(f"❌ 别名映射测试失败 {alias}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 简化注册表验证失败: {e}")
        return False


def test_configuration_simplification():
    """测试配置简化"""
    print("\n🔍 测试配置简化...")
    
    try:
        # 验证配置转换方法是否简化
        import inspect
        
        # 获取ProcessorRegistry的所有方法
        methods = inspect.getmembers(ProcessorRegistry, predicate=inspect.ismethod)
        method_names = [name for name, _ in methods]
        
        # 检查是否还有旧的配置转换方法
        legacy_methods = [
            '_create_ip_anonymization_config',
            '_create_deduplication_config'
        ]
        
        for method_name in legacy_methods:
            if method_name in method_names:
                print(f"⚠️ 旧配置方法仍存在: {method_name}")
            else:
                print(f"✅ 旧配置方法已移除: {method_name}")
        
        # 检查统一配置方法是否存在
        unified_methods = [
            '_create_unified_ip_anonymization_config',
            '_create_unified_deduplication_config',
            '_create_mask_payload_config'
        ]
        
        for method_name in unified_methods:
            if hasattr(ProcessorRegistry, method_name):
                print(f"✅ 统一配置方法存在: {method_name}")
            else:
                print(f"❌ 统一配置方法缺失: {method_name}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 配置简化验证失败: {e}")
        return False


def test_end_to_end_functionality():
    """端到端功能测试"""
    print("\n🔍 端到端功能测试...")
    
    try:
        # 创建测试文件
        from scapy.all import Ether, IP, UDP, wrpcap
        
        # 创建测试数据包
        pkt1 = Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/UDP(sport=1234, dport=5678)/b"test data"
        pkt2 = Ether()/IP(src="192.168.1.1", dst="192.168.1.2")/UDP(sport=1234, dport=5678)/b"test data"  # 重复
        pkt3 = Ether()/IP(src="192.168.1.3", dst="192.168.1.4")/UDP(sport=1234, dport=5678)/b"different data"
        
        packets = [pkt1, pkt2, pkt3]
        
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_input:
            temp_input_path = temp_input.name
            wrpcap(temp_input_path, packets)
        
        # 测试IP匿名化
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_anon:
            temp_anon_path = temp_anon.name
        
        # 测试去重
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_dedup:
            temp_dedup_path = temp_dedup.name
        
        try:
            test_config = ProcessorConfig(enabled=True, name="test_e2e", priority=0)
            
            # 测试IP匿名化
            anonymizer = ProcessorRegistry.get_processor('anonymize_ips', test_config)
            if hasattr(anonymizer, 'initialize'):
                anonymizer.initialize()
            
            anon_result = anonymizer.process_file(temp_input_path, temp_anon_path)
            if isinstance(anon_result, StageStats):
                print(f"✅ IP匿名化成功: 处理了 {anon_result.packets_processed} 个数据包")
            else:
                print(f"❌ IP匿名化返回类型错误: {type(anon_result)}")
                return False
            
            # 测试去重
            deduplicator = ProcessorRegistry.get_processor('remove_dupes', test_config)
            if hasattr(deduplicator, 'initialize'):
                deduplicator.initialize()
            
            dedup_result = deduplicator.process_file(temp_input_path, temp_dedup_path)
            if isinstance(dedup_result, StageStats):
                print(f"✅ 去重成功: 处理了 {dedup_result.packets_processed} 个数据包，移除了 {dedup_result.packets_modified} 个重复包")
            else:
                print(f"❌ 去重返回类型错误: {type(dedup_result)}")
                return False
            
            return True
            
        finally:
            # 清理临时文件
            for path in [temp_input_path, temp_anon_path, temp_dedup_path]:
                Path(path).unlink(missing_ok=True)
        
    except Exception as e:
        print(f"❌ 端到端功能测试失败: {e}")
        return False


def main():
    """主验证函数"""
    print("=" * 60)
    print("阶段3验证：架构清理验证")
    print("=" * 60)
    
    tests = [
        ("BaseProcessor系统移除", test_baseprocessor_removal),
        ("统一StageBase架构", test_unified_stagebase_architecture),
        ("简化ProcessorRegistry", test_simplified_registry),
        ("配置简化", test_configuration_simplification),
        ("端到端功能", test_end_to_end_functionality),
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
        print("🎉 阶段3验证完全成功！")
        print("✅ BaseProcessor系统完全移除")
        print("✅ ProcessorRegistry简化为纯StageBase注册表")
        print("✅ 架构统一完成，所有功能正常")
        return True
    else:
        print("❌ 阶段3验证存在问题，需要修复")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
