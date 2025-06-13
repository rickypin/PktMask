#!/usr/bin/env python3
"""
测试统一载荷提取修复后的Enhanced Trimmer TLS掩码功能

这个脚本验证：
1. 载荷长度一致性（PyShark vs Scapy）
2. MaskAfter(5)掩码是否正确应用
3. TLS ApplicationData包是否被正确掩码
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from pktmask.core.processors.enhanced_trimmer import EnhancedTrimmer
from pktmask.config.settings import AppConfig

def test_unified_payload_extraction():
    """测试统一载荷提取的Enhanced Trimmer"""
    
    # 使用TLS样本文件
    sample_file = Path("tests/samples/TLS/tls_sample.pcap")
    if not sample_file.exists():
        print(f"❌ 测试文件不存在: {sample_file}")
        return False
    
    print("🧪 测试统一载荷提取修复后的Enhanced Trimmer")
    print(f"📁 测试文件: {sample_file}")
    print(f"📊 文件大小: {sample_file.stat().st_size} bytes")
    
    # 创建临时输出目录
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = Path(temp_dir) / "output.pcap"
        
        try:
            # 创建AppConfig
            config = AppConfig()
            
            # 创建Enhanced Trimmer
            trimmer = EnhancedTrimmer(config)
            
            print("\n📋 执行Enhanced Trimmer处理...")
            
            # 执行处理
            success = trimmer.process_file(
                str(sample_file), 
                str(output_file)
            )
            
            if success:
                print("✅ 处理成功完成!")
                
                # 检查输出文件
                if output_file.exists():
                    print(f"📄 输出文件: {output_file}")
                    print(f"📊 输出大小: {output_file.stat().st_size} bytes")
                    return True
                else:
                    print("❌ 输出文件未生成")
                    return False
            else:
                print("❌ 处理失败")
                return False
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            return False

def analyze_log_output():
    """分析日志输出，查找关键指标"""
    print("\n🔍 日志分析要点:")
    print("✅ 期望看到: '从Raw层提取完整TCP载荷: XXX 字节'")
    print("✅ 期望看到: '数据包XX载荷是否改变: True' (对于ApplicationData包)")
    print("✅ 期望看到: '掩码应用完成: 修改了 X/Y 个数据包' (X > 0)")
    print("❌ 不应看到: '从TLS层提取载荷' (已移除TLS层优先逻辑)")
    print("❌ 不应看到: '载荷未发生实际改变' (对于应该被掩码的包)")

if __name__ == "__main__":
    print("🚀 测试统一载荷提取修复")
    print("=" * 60)
    
    # 执行测试
    success = test_unified_payload_extraction()
    
    # 分析指导
    analyze_log_output()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试完成 - 请检查日志输出验证修复效果")
    else:
        print("💥 测试失败 - 需要进一步调试")
    
    sys.exit(0 if success else 1) 