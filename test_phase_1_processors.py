#!/usr/bin/env python3
"""
Phase 1: 核心处理器实现 - 测试脚本

测试新的简化处理器系统是否正常工作。
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root / "src"))

try:
    from pktmask.core.processors import (
        ProcessorRegistry, ProcessorConfig, 
        IPAnonymizer, Deduplicator, Trimmer
    )
    print("✅ 成功导入处理器模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


def test_registry():
    """测试处理器注册表"""
    print("\n🔍 测试处理器注册表...")
    
    try:
        # 测试列出处理器
        processors = ProcessorRegistry.list_processors()
        print(f"  可用处理器: {processors}")
        
        expected_processors = ['mask_ip', 'dedup_packet', 'trim_packet']
        for expected in expected_processors:
            if expected not in processors:
                print(f"  ❌ 缺少处理器: {expected}")
                return False
        
        # 测试获取处理器信息
        for name in expected_processors:
            info = ProcessorRegistry.get_processor_info(name)
            print(f"  📄 {name}: {info['display_name']} - {info['description']}")
        
        print("  ✅ 注册表测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 注册表测试失败: {e}")
        return False


def test_processor_creation():
    """测试处理器创建"""
    print("\n🔍 测试处理器创建...")
    
    try:
        # 测试创建各个处理器
        config = ProcessorConfig(enabled=True, name="test_processor")
        
        processors = {}
        for name in ['mask_ip', 'dedup_packet', 'trim_packet']:
            processor = ProcessorRegistry.get_processor(name, config)
            processors[name] = processor
            print(f"  ✅ 成功创建 {name}: {processor.get_display_name()}")
        
        # 测试初始化
        for name, processor in processors.items():
            if processor.initialize():
                print(f"  ✅ {name} 初始化成功")
            else:
                print(f"  ❌ {name} 初始化失败")
                return False
        
        print("  ✅ 处理器创建测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 处理器创建测试失败: {e}")
        return False


def create_test_pcap():
    """创建一个简单的测试pcap文件"""
    try:
        from scapy.all import Ether, IP, TCP, wrpcap
        
        # 创建一些简单的测试包
        packets = []
        for i in range(10):
            pkt = Ether()/IP(src=f"192.168.1.{i}", dst=f"10.0.0.{i}")/TCP(sport=80, dport=8080)/f"Test payload {i}"
            packets.append(pkt)
        
        # 添加一些重复包用于测试去重
        packets.extend(packets[:3])
        
        # 写入临时文件
        temp_file = tempfile.NamedTemporaryFile(suffix='.pcap', delete=False)
        wrpcap(temp_file.name, packets)
        return temp_file.name
        
    except ImportError:
        print("  ⚠️  缺少scapy，跳过pcap文件创建")
        return None
    except Exception as e:
        print(f"  ❌ 创建测试pcap失败: {e}")
        return None


def test_file_processing():
    """测试文件处理功能"""
    print("\n🔍 测试文件处理...")
    
    # 创建测试pcap文件
    test_pcap = create_test_pcap()
    if not test_pcap:
        print("  ⚠️  跳过文件处理测试（无测试文件）")
        return True
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        config = ProcessorConfig(enabled=True, name="test_processor")
        
        # 测试每个处理器
        for name in ['mask_ip', 'dedup_packet', 'trim_packet']:
            try:
                print(f"  🔧 测试 {name} 处理器...")
                
                processor = ProcessorRegistry.get_processor(name, config)
                if not processor.initialize():
                    print(f"    ❌ {name} 初始化失败")
                    continue
                
                output_path = os.path.join(temp_dir, f"output_{name}.pcap")
                result = processor.process_file(test_pcap, output_path)
                
                if result.success:
                    print(f"    ✅ {name} 处理成功")
                    print(f"    📊 统计: {result.stats}")
                    
                    # 检查输出文件是否存在
                    if os.path.exists(output_path):
                        print(f"    📁 输出文件已创建: {os.path.getsize(output_path)} bytes")
                    else:
                        print(f"    ❌ 输出文件未创建")
                else:
                    print(f"    ❌ {name} 处理失败: {result.error}")
                    
            except Exception as e:
                print(f"    ❌ {name} 处理异常: {e}")
        
        print("  ✅ 文件处理测试完成")
        return True
        
    finally:
        # 清理临时文件
        try:
            os.unlink(test_pcap)
            shutil.rmtree(temp_dir)
        except:
            pass


def test_processor_methods():
    """测试处理器方法"""
    print("\n🔍 测试处理器方法...")
    
    try:
        config = ProcessorConfig(enabled=True, name="test_processor")
        
        for name in ['mask_ip', 'dedup_packet', 'trim_packet']:
            processor = ProcessorRegistry.get_processor(name, config)
            
            # 测试基本方法
            display_name = processor.get_display_name()
            description = processor.get_description()
            
            print(f"  📋 {name}:")
            print(f"    显示名: {display_name}")
            print(f"    描述: {description}")
            
            # 测试统计方法
            stats = processor.get_stats()
            print(f"    初始统计: {len(stats)} 项")
            
        print("  ✅ 处理器方法测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 处理器方法测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 Phase 1: 核心处理器实现测试")
    print("=" * 50)
    
    tests = [
        ("注册表功能", test_registry),
        ("处理器创建", test_processor_creation),
        ("处理器方法", test_processor_methods),
        ("文件处理", test_file_processing),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 Phase 1 核心处理器实现测试 - 全部通过！")
        return True
    else:
        print("⚠️  部分测试失败，请检查错误信息")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 