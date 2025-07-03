#!/usr/bin/env python3
"""
TSharkTLSAnalyzer单元测试脚本

用于诊断TSharkTLSAnalyzer初始化失败的问题
"""

import sys
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

def test_tshark_availability():
    """测试TShark工具的可用性"""
    print("🔍 测试TShark工具可用性...")
    
    try:
        import subprocess
        from src.pktmask.config.defaults import get_tshark_paths
        
        tshark_paths = get_tshark_paths()
        print(f"📁 检测到的TShark路径: {tshark_paths}")
        
        for tshark_path in tshark_paths:
            try:
                result = subprocess.run(
                    [tshark_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and 'TShark' in result.stdout:
                    print(f"✅ TShark可用: {tshark_path}")
                    version_line = result.stdout.split('\n')[0]
                    print(f"📋 版本信息: {version_line}")
                    return True
                else:
                    print(f"❌ TShark测试失败: {tshark_path} (退出码: {result.returncode})")
                    
            except Exception as e:
                print(f"⚠️ TShark路径测试异常 {tshark_path}: {e}")
                continue
        
        print("❌ 所有TShark路径都不可用")
        return False
        
    except Exception as e:
        print(f"❌ TShark可用性检查异常: {e}")
        return False

def test_tshark_analyzer_import():
    """测试TSharkTLSAnalyzer导入"""
    print("\n🔍 测试TSharkTLSAnalyzer导入...")
    
    try:
        from src.pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
        print("✅ TSharkTLSAnalyzer导入成功")
        return TSharkTLSAnalyzer
        
    except ImportError as e:
        print(f"❌ TSharkTLSAnalyzer导入失败: {e}")
        return None
    except Exception as e:
        print(f"❌ TSharkTLSAnalyzer导入异常: {e}")
        return None

def test_tshark_analyzer_creation(analyzer_class):
    """测试TSharkTLSAnalyzer创建"""
    print("\n🔍 测试TSharkTLSAnalyzer创建...")
    
    try:
        config = {
            'enable_detailed_logging': True,
            'enable_performance_monitoring': True,
            'enable_boundary_safety': True,
            'temp_dir': None
        }
        
        analyzer = analyzer_class(config)
        print("✅ TSharkTLSAnalyzer创建成功")
        return analyzer
        
    except Exception as e:
        print(f"❌ TSharkTLSAnalyzer创建失败: {e}")
        return None

def test_tshark_analyzer_initialization(analyzer):
    """测试TSharkTLSAnalyzer初始化"""
    print("\n🔍 测试TSharkTLSAnalyzer初始化...")
    
    try:
        result = analyzer.initialize()
        
        if result:
            print("✅ TSharkTLSAnalyzer初始化成功")
            return True
        else:
            print("❌ TSharkTLSAnalyzer初始化返回False")
            return False
            
    except Exception as e:
        print(f"❌ TSharkTLSAnalyzer初始化异常: {e}")
        import traceback
        print(f"📋 异常堆栈: {traceback.format_exc()}")
        return False

def test_tshark_analyzer_basic_functionality(analyzer, test_file):
    """测试TSharkTLSAnalyzer基本功能"""
    print(f"\n🔍 测试TSharkTLSAnalyzer基本功能 (文件: {test_file})...")
    
    try:
        if not Path(test_file).exists():
            print(f"⚠️ 测试文件不存在: {test_file}")
            return False
            
        print("🚀 开始分析TLS记录...")
        records = analyzer.analyze_file(test_file)
        
        print(f"✅ TLS分析完成，发现 {len(records)} 个记录")
        
        # 统计记录类型
        if records:
            type_stats = {}
            cross_packet_count = 0
            
            for record in records:
                record_type = record.content_type
                type_stats[record_type] = type_stats.get(record_type, 0) + 1
                
                if len(record.spans_packets) > 1:
                    cross_packet_count += 1
            
            print("📊 TLS记录统计:")
            for record_type, count in type_stats.items():
                print(f"   TLS-{record_type}: {count} 个")
            
            print(f"📊 跨包记录: {cross_packet_count} 个")
            
            # 重点关注TLS-23记录
            tls_23_records = [r for r in records if r.content_type == 23]
            tls_23_cross_packet = [r for r in tls_23_records if len(r.spans_packets) > 1]
            
            print(f"🎯 TLS-23 ApplicationData记录: {len(tls_23_records)} 个")
            print(f"🎯 TLS-23跨包记录: {len(tls_23_cross_packet)} 个")
            
            if tls_23_cross_packet:
                print("🔍 TLS-23跨包记录详情:")
                for i, record in enumerate(tls_23_cross_packet[:3]):  # 只显示前3个
                    print(f"   记录{i+1}: 包{record.packet_number}, 长度{record.length}, 跨包{record.spans_packets}")
            
        return True
        
    except Exception as e:
        print(f"❌ TLS分析异常: {e}")
        import traceback
        print(f"📋 异常堆栈: {traceback.format_exc()}")
        return False

def main():
    """主函数"""
    print("🚀 TSharkTLSAnalyzer诊断测试")
    print("=" * 60)
    
    # 获取测试文件
    if len(sys.argv) < 2:
        test_file = "tests/data/tls/tls_1_0_multi_segment_google-https.pcap"
        print(f"📁 使用默认测试文件: {test_file}")
    else:
        test_file = sys.argv[1]
        print(f"📁 使用指定测试文件: {test_file}")
    
    success_count = 0
    total_tests = 5
    
    # 测试1: TShark工具可用性
    if test_tshark_availability():
        success_count += 1
    
    # 测试2: TSharkTLSAnalyzer导入
    analyzer_class = test_tshark_analyzer_import()
    if analyzer_class:
        success_count += 1
    else:
        print("\n❌ 无法继续测试，TSharkTLSAnalyzer导入失败")
        print(f"📊 测试结果: {success_count}/{total_tests} 通过")
        sys.exit(1)
    
    # 测试3: TSharkTLSAnalyzer创建
    analyzer = test_tshark_analyzer_creation(analyzer_class)
    if analyzer:
        success_count += 1
    else:
        print("\n❌ 无法继续测试，TSharkTLSAnalyzer创建失败")
        print(f"📊 测试结果: {success_count}/{total_tests} 通过")
        sys.exit(1)
    
    # 测试4: TSharkTLSAnalyzer初始化
    if test_tshark_analyzer_initialization(analyzer):
        success_count += 1
    else:
        print("\n❌ 无法继续测试，TSharkTLSAnalyzer初始化失败")
        print(f"📊 测试结果: {success_count}/{total_tests} 通过")
        sys.exit(1)
    
    # 测试5: TSharkTLSAnalyzer基本功能
    if test_tshark_analyzer_basic_functionality(analyzer, test_file):
        success_count += 1
    
    # 最终结果
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！TSharkTLSAnalyzer工作正常")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查上述错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 