#!/usr/bin/env python3
"""
测试帧144 TLS消息类型错误匹配修复效果

验证修复后的Marker模块是否正确处理跨段ChangeCipherSpec消息，
避免生成过大的规则范围导致帧144错误匹配。
"""

import json
import subprocess
import sys
from pathlib import Path

class Frame144FixTester:
    def __init__(self):
        self.test_file = "tests/data/tls/tls_1_2_double_vlan.pcap"
        self.target_frame = 144
        self.problematic_rule_range = (3135493808, 3135495885)
        
    def test_before_after_fix(self):
        """测试修复前后的效果对比"""
        print("=== 测试帧144修复效果 ===")
        
        try:
            # 导入修复后的Marker模块
            sys.path.insert(0, str(Path.cwd()))
            from src.pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            # 创建测试配置
            test_config = {
                'preserve': {
                    'handshake': True,
                    'application_data': False,  # 只保留头部
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                }
            }
            
            print(f"测试配置: {test_config}")
            
            # 创建Marker实例
            marker = TLSProtocolMarker(test_config)
            
            # 分析文件
            print("开始分析文件...")
            ruleset = marker.analyze_file(self.test_file, test_config)
            
            print(f"总规则数: {len(ruleset.rules)}")
            
            # 检查是否还存在问题规则
            problematic_rules = []
            changecipherspec_rules = []
            
            for rule in ruleset.rules:
                if "changecipherspec" in rule.rule_type.lower():
                    changecipherspec_rules.append(rule)
                    
                    # 检查是否为问题规则
                    rule_start, rule_end = self.problematic_rule_range
                    if (rule.seq_start == rule_start and rule.seq_end == rule_end and 
                        rule.stream_id == "5" and rule.direction == "reverse"):
                        problematic_rules.append(rule)
            
            print(f"\nChangeCipherSpec规则总数: {len(changecipherspec_rules)}")
            print(f"问题规则数量: {len(problematic_rules)}")
            
            if problematic_rules:
                print("❌ 修复失败！仍然存在问题规则:")
                for rule in problematic_rules:
                    print(f"  规则范围: {rule.seq_start} - {rule.seq_end}")
                    print(f"  规则长度: {rule.seq_end - rule.seq_start}")
                    if hasattr(rule, 'metadata') and rule.metadata:
                        print(f"  元数据: {rule.metadata}")
            else:
                print("✅ 修复成功！问题规则已被过滤")
            
            # 检查帧144是否有正确的规则
            frame144_rules = []
            frame_data = self.get_frame144_data()
            if frame_data:
                tcp_seq = int(frame_data.get('tcp.seq_raw', ['0'])[0])
                tcp_len = int(frame_data.get('tcp.len', ['0'])[0])
                frame144_start = tcp_seq
                frame144_end = tcp_seq + tcp_len
                
                print(f"\n帧144序列号范围: {frame144_start} - {frame144_end}")
                
                # 查找与帧144重叠的规则
                overlapping_rules = []
                for rule in ruleset.rules:
                    rule_start = rule.seq_start
                    rule_end = rule.seq_end
                    
                    overlap_start = max(rule_start, frame144_start)
                    overlap_end = min(rule_end, frame144_end)
                    
                    if overlap_start < overlap_end:
                        overlapping_rules.append((rule, overlap_start, overlap_end))
                
                print(f"与帧144重叠的规则数: {len(overlapping_rules)}")
                
                for i, (rule, overlap_start, overlap_end) in enumerate(overlapping_rules):
                    print(f"\n重叠规则 {i+1}:")
                    print(f"  规则类型: {rule.rule_type}")
                    print(f"  规则范围: {rule.seq_start} - {rule.seq_end}")
                    print(f"  重叠范围: {overlap_start} - {overlap_end}")
                    
                    if rule.rule_type == "tls_changecipherspec":
                        print(f"  ⚠️  仍然存在ChangeCipherSpec规则与帧144重叠!")
                    elif "applicationdata" in rule.rule_type.lower():
                        print(f"  ✅ 正确的ApplicationData规则")
            
            # 分析ChangeCipherSpec规则的大小分布
            print(f"\nChangeCipherSpec规则大小分析:")
            rule_sizes = []
            for rule in changecipherspec_rules:
                size = rule.seq_end - rule.seq_start
                rule_sizes.append(size)
                
                if size > 100:  # 异常大的规则
                    print(f"  ⚠️  异常大的ChangeCipherSpec规则: {size}字节 (流{rule.stream_id}-{rule.direction})")
                    if hasattr(rule, 'metadata') and rule.metadata:
                        is_cross_segment = rule.metadata.get('is_cross_segment', False)
                        declared_length = rule.metadata.get('declared_length', 0)
                        actual_length = rule.metadata.get('actual_length', 0)
                        print(f"    跨段: {is_cross_segment}, 声明长度: {declared_length}, 实际长度: {actual_length}")
            
            if rule_sizes:
                print(f"  规则大小范围: {min(rule_sizes)} - {max(rule_sizes)}字节")
                print(f"  平均大小: {sum(rule_sizes) / len(rule_sizes):.1f}字节")
                large_rules = [s for s in rule_sizes if s > 50]
                if large_rules:
                    print(f"  大于50字节的规则数: {len(large_rules)}")
                else:
                    print(f"  ✅ 所有ChangeCipherSpec规则都在合理范围内")
            
        except Exception as e:
            print(f"测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    def get_frame144_data(self):
        """获取帧144的数据"""
        cmd = [
            "tshark", "-r", self.test_file,
            "-Y", f"frame.number == {self.target_frame}",
            "-T", "json",
            "-e", "tcp.seq_raw",
            "-e", "tcp.len"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            frame_data = json.loads(result.stdout)[0]["_source"]["layers"]
            return frame_data
        except Exception as e:
            print(f"获取帧144数据失败: {e}")
            return None
    
    def test_specific_changecipherspec_rules(self):
        """测试特定的ChangeCipherSpec规则处理"""
        print("\n=== 测试ChangeCipherSpec规则处理 ===")
        
        try:
            # 查找所有ChangeCipherSpec帧
            cmd = [
                "tshark", "-r", self.test_file,
                "-Y", "tls.record.content_type == 20 and tcp.stream == 5",
                "-T", "fields",
                "-e", "frame.number",
                "-e", "tcp.seq_raw",
                "-e", "tcp.len",
                "-e", "tls.record.length"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            
            print(f"TCP流5中的ChangeCipherSpec帧:")
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        frame_num = parts[0]
                        tcp_seq = parts[1]
                        tcp_len = parts[2]
                        tls_length = parts[3]
                        
                        print(f"  帧{frame_num}: TCP序列号{tcp_seq}, TCP长度{tcp_len}, TLS长度{tls_length}")
                        
                        # 检查是否为异常大的TLS长度
                        if tls_length and int(tls_length) > 100:
                            print(f"    ⚠️  异常大的TLS长度: {tls_length}")
                            
        except Exception as e:
            print(f"ChangeCipherSpec规则测试失败: {e}")
    
    def run_test(self):
        """运行完整测试"""
        print("开始帧144修复效果测试")
        print("=" * 60)
        
        self.test_before_after_fix()
        self.test_specific_changecipherspec_rules()
        
        print("\n" + "=" * 60)
        print("测试完成")

if __name__ == "__main__":
    tester = Frame144FixTester()
    tester.run_test()
