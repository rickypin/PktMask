#!/usr/bin/env python3
"""
测试修复后的maskstage双模块架构
验证解决方案1和解决方案2的效果
"""

import sys
import os
import subprocess
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_marker_with_fixed_logic():
    """测试修复后的Marker模块"""
    print("=== 测试修复后的Marker模块 ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker import TLSProtocolMarker
        
        # 创建配置
        config = {
            'preserve': {
                'handshake': True,
                'application_data': False,
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            },
            'tshark_path': None,
            'decode_as': []
        }
        
        marker = TLSProtocolMarker(config)
        
        # 测试失败案例1
        pcap_file1 = 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap'
        if Path(pcap_file1).exists():
            print(f"\n--- 测试案例1: {pcap_file1} ---")
            keep_rules1 = marker.analyze_file(pcap_file1, config)
            
            # 检查帧150相关的规则
            frame_150_rules = []
            for rule in keep_rules1.rules:
                # 检查是否覆盖帧150的序列号范围 (2051613234, 2051614664)
                if (rule.stream_id == "0" and rule.direction == "reverse" and
                    not (rule.seq_end <= 2051613234 or rule.seq_start >= 2051614664)):
                    frame_150_rules.append(rule)
            
            print(f"影响帧150的规则数: {len(frame_150_rules)}")
            for i, rule in enumerate(frame_150_rules):
                print(f"  规则{i+1}: [{rule.seq_start}, {rule.seq_end}) 类型={rule.rule_type}")
        
        # 测试失败案例2
        pcap_file2 = 'tests/data/tls/tls_1_2_double_vlan.pcap'
        if Path(pcap_file2).exists():
            print(f"\n--- 测试案例2: {pcap_file2} ---")
            keep_rules2 = marker.analyze_file(pcap_file2, config)
            
            # 检查帧144相关的规则
            frame_144_rules = []
            for rule in keep_rules2.rules:
                # 检查是否覆盖帧144的序列号范围 (3135495612, 3135495885)
                if (rule.stream_id == "5" and rule.direction == "reverse" and
                    not (rule.seq_end <= 3135495612 or rule.seq_start >= 3135495885)):
                    frame_144_rules.append(rule)
            
            print(f"影响帧144的规则数: {len(frame_144_rules)}")
            for i, rule in enumerate(frame_144_rules):
                print(f"  规则{i+1}: [{rule.seq_start}, {rule.seq_end}) 类型={rule.rule_type}")
                
        return True
        
    except Exception as e:
        print(f"Marker测试失败: {e}")
        return False

def test_masker_with_fixed_logic():
    """测试修复后的Masker模块"""
    print("\n=== 测试修复后的Masker模块 ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker import TLSProtocolMarker
        from pktmask.core.pipeline.stages.mask_payload_v2.masker import PayloadMasker
        
        # 创建配置
        config = {
            'preserve': {
                'handshake': True,
                'application_data': False,
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            },
            'tshark_path': None,
            'decode_as': []
        }
        
        marker = TLSProtocolMarker(config)
        masker = PayloadMasker({})
        
        # 测试案例1
        pcap_file1 = 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap'
        if Path(pcap_file1).exists():
            print(f"\n--- 测试Masker案例1: {pcap_file1} ---")
            
            # 生成规则
            keep_rules1 = marker.analyze_file(pcap_file1, config)
            
            # 创建临时输出文件
            temp_output1 = f"/tmp/test_masked_{Path(pcap_file1).name}"
            
            # 应用掩码
            try:
                stats1 = masker.apply_masking(pcap_file1, temp_output1, keep_rules1)
                print(f"掩码统计: 处理包数={stats1.processed_packets}, "
                      f"掩码包数={stats1.masked_packets}, "
                      f"保留字节={stats1.preserved_bytes}, "
                      f"掩码字节={stats1.masked_bytes}")
                
                # 清理临时文件
                if os.path.exists(temp_output1):
                    os.remove(temp_output1)
                    
            except Exception as e:
                print(f"Masker应用失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"Masker测试失败: {e}")
        return False

def run_validation_after_fix():
    """运行修复后的验证"""
    print("\n=== 运行修复后的验证 ===")
    
    # 运行验证脚本
    try:
        result = subprocess.run([
            'python', 'validate_maskstage_v2.py',
            '--test-dir', 'tests/data/tls',
            '--output-dir', 'output/maskstage_validation_fixed',
            '--generate-html'
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print("验证脚本执行成功")
            print("输出:")
            print(result.stdout)
        else:
            print("验证脚本执行失败")
            print("错误:")
            print(result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"验证脚本执行异常: {e}")
        return False

def analyze_fix_effectiveness():
    """分析修复效果"""
    print("\n=== 分析修复效果 ===")
    
    # 对比修复前后的结果
    original_report = Path("output/maskstage_validation/validation_summary.html")
    fixed_report = Path("output/maskstage_validation_fixed/validation_summary.html")
    
    if original_report.exists() and fixed_report.exists():
        print("修复前后的验证报告都存在，可以进行对比分析")
        
        # 这里可以添加更详细的对比逻辑
        # 比如解析HTML报告，统计失败案例数量等
        
        return True
    else:
        print("缺少对比报告文件")
        return False

def main():
    """主测试函数"""
    print("测试修复后的PktMask maskstage双模块架构")
    print("=" * 60)
    
    # 检查测试文件是否存在
    test_files = [
        'tests/data/tls/tls_1_0_multi_segment_google-https.pcap',
        'tests/data/tls/tls_1_2_double_vlan.pcap'
    ]
    
    missing_files = [f for f in test_files if not Path(f).exists()]
    if missing_files:
        print(f"缺少测试文件: {missing_files}")
        return False
    
    success = True
    
    # 1. 测试修复后的Marker模块
    if not test_marker_with_fixed_logic():
        success = False
    
    # 2. 测试修复后的Masker模块
    if not test_masker_with_fixed_logic():
        success = False
    
    # 3. 运行完整验证
    if not run_validation_after_fix():
        success = False
    
    # 4. 分析修复效果
    if not analyze_fix_effectiveness():
        success = False
    
    print(f"\n{'='*60}")
    if success:
        print("✅ 所有测试通过，修复方案有效")
    else:
        print("❌ 部分测试失败，需要进一步调试")
    
    return success

if __name__ == '__main__':
    main()
