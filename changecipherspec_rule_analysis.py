#!/usr/bin/env python3
"""
ChangeCipherSpec规则分析

分析导致帧144错误匹配的ChangeCipherSpec规则的来源和生成逻辑
"""

import json
import subprocess
import sys
from pathlib import Path

class ChangeCipherSpecAnalyzer:
    def __init__(self):
        self.test_file = "tests/data/tls/tls_1_2_double_vlan.pcap"
        self.problematic_rule_range = (3135493808, 3135495885)
        
    def find_changecipherspec_frames(self):
        """查找所有ChangeCipherSpec相关的帧"""
        print("=== 查找ChangeCipherSpec相关帧 ===")
        
        # 查找所有TLS-20类型的帧
        cmd = [
            "tshark", "-r", self.test_file,
            "-Y", "tls.record.content_type == 20",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "tcp.seq_raw",
            "-e", "tcp.len",
            "-e", "tcp.payload",
            "-e", "tls.record.content_type",
            "-e", "tls.record.length"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            
            print(f"找到 {len(lines)} 个ChangeCipherSpec帧:")
            
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 6:
                        frame_num = parts[0]
                        tcp_seq = int(parts[1]) if parts[1] else 0
                        tcp_len = int(parts[2]) if parts[2] else 0
                        tcp_payload = parts[3]
                        tls_type = parts[4]
                        tls_length = parts[5]
                        
                        print(f"  帧{frame_num}: TCP序列号{tcp_seq}, 长度{tcp_len}, TLS类型{tls_type}")
                        print(f"    载荷: {tcp_payload[:40]}...")
                        
                        # 检查是否与问题规则范围重叠
                        frame_start = tcp_seq
                        frame_end = tcp_seq + tcp_len
                        rule_start, rule_end = self.problematic_rule_range
                        
                        if (frame_start <= rule_end and frame_end >= rule_start):
                            print(f"    ⚠️  与问题规则范围重叠!")
                            
        except subprocess.CalledProcessError as e:
            print(f"tshark执行失败: {e}")
    
    def analyze_tcp_stream_5(self):
        """分析TCP流5的详细信息"""
        print("\n=== 分析TCP流5 ===")
        
        # 查找TCP流5的所有帧
        cmd = [
            "tshark", "-r", self.test_file,
            "-Y", "tcp.stream == 5",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "tcp.seq_raw",
            "-e", "tcp.len",
            "-e", "tcp.flags.syn",
            "-e", "tcp.flags.ack",
            "-e", "tls.record.content_type"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            
            print(f"TCP流5包含 {len(lines)} 个帧:")
            
            stream_frames = []
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 6:
                        frame_num = int(parts[0]) if parts[0] else 0
                        tcp_seq = int(parts[1]) if parts[1] else 0
                        tcp_len = int(parts[2]) if parts[2] else 0
                        syn_flag = parts[3]
                        ack_flag = parts[4]
                        tls_types = parts[5].split(',') if parts[5] else []
                        
                        stream_frames.append({
                            'frame': frame_num,
                            'seq': tcp_seq,
                            'len': tcp_len,
                            'syn': syn_flag,
                            'ack': ack_flag,
                            'tls_types': tls_types,
                            'seq_end': tcp_seq + tcp_len
                        })
            
            # 按序列号排序
            stream_frames.sort(key=lambda x: x['seq'])
            
            rule_start, rule_end = self.problematic_rule_range
            
            print(f"\n问题规则范围: {rule_start} - {rule_end}")
            print("流5帧详情:")
            
            for frame_info in stream_frames:
                frame_start = frame_info['seq']
                frame_end = frame_info['seq_end']
                
                # 检查与问题规则的重叠
                overlap = ""
                if frame_start <= rule_end and frame_end >= rule_start:
                    overlap_start = max(frame_start, rule_start)
                    overlap_end = min(frame_end, rule_end)
                    overlap = f" [重叠: {overlap_start}-{overlap_end}]"
                
                tls_info = f" TLS:{','.join(frame_info['tls_types'])}" if frame_info['tls_types'] and frame_info['tls_types'][0] else ""
                
                print(f"  帧{frame_info['frame']}: {frame_start}-{frame_end} (长度{frame_info['len']}){tls_info}{overlap}")
                
                # 特别标记帧144
                if frame_info['frame'] == 144:
                    print(f"    ⭐ 这是帧144 (TLS-23 ApplicationData)")
                    
        except subprocess.CalledProcessError as e:
            print(f"tshark执行失败: {e}")
    
    def analyze_marker_rule_generation(self):
        """分析Marker如何生成问题规则"""
        print("\n=== 分析Marker规则生成 ===")
        
        try:
            # 导入Marker模块
            sys.path.insert(0, str(Path.cwd()))
            from src.pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            # 创建测试配置
            test_config = {
                'preserve': {
                    'handshake': True,
                    'application_data': False,
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                }
            }
            
            # 创建Marker实例
            marker = TLSProtocolMarker(test_config)
            
            # 分析文件
            ruleset = marker.analyze_file(self.test_file, test_config)
            
            # 查找ChangeCipherSpec规则
            changecipherspec_rules = []
            for rule in ruleset.rules:
                if "changecipherspec" in rule.rule_type.lower():
                    changecipherspec_rules.append(rule)
            
            print(f"找到 {len(changecipherspec_rules)} 个ChangeCipherSpec规则:")
            
            rule_start, rule_end = self.problematic_rule_range
            
            for i, rule in enumerate(changecipherspec_rules):
                print(f"\nChangeCipherSpec规则 {i+1}:")
                print(f"  规则类型: {rule.rule_type}")
                print(f"  序列号范围: {rule.seq_start} - {rule.seq_end}")
                print(f"  流ID: {rule.stream_id}")
                print(f"  方向: {rule.direction}")
                
                if hasattr(rule, 'metadata') and rule.metadata:
                    print(f"  元数据: {rule.metadata}")
                
                # 检查是否为问题规则
                if (rule.seq_start == rule_start and rule.seq_end == rule_end and 
                    rule.stream_id == "5" and rule.direction == "reverse"):
                    print(f"  ⚠️  这就是导致帧144错误匹配的问题规则!")
                    
                    # 分析这个规则的生成原因
                    if hasattr(rule, 'metadata') and rule.metadata:
                        frame_num = rule.metadata.get('frame_number')
                        if frame_num:
                            print(f"  来源帧: {frame_num}")
                            self.analyze_source_frame(frame_num)
                        
        except Exception as e:
            print(f"Marker规则生成分析失败: {e}")
            import traceback
            traceback.print_exc()
    
    def analyze_source_frame(self, frame_number):
        """分析规则来源帧的详细信息"""
        print(f"\n--- 分析来源帧{frame_number} ---")
        
        cmd = [
            "tshark", "-r", self.test_file,
            "-Y", f"frame.number == {frame_number}",
            "-T", "json"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            frame_data = json.loads(result.stdout)[0]["_source"]["layers"]
            
            tcp_seq = frame_data.get("tcp", {}).get("tcp.seq_raw")
            tcp_len = frame_data.get("tcp", {}).get("tcp.len")
            tcp_payload = frame_data.get("tcp", {}).get("tcp.payload", [""])[0]
            tls_types = frame_data.get("tls", {}).get("tls.record.content_type", [])
            
            print(f"  TCP序列号: {tcp_seq}")
            print(f"  TCP长度: {tcp_len}")
            print(f"  TLS类型: {tls_types}")
            print(f"  载荷前20字节: {tcp_payload[:40] if tcp_payload else 'N/A'}")
            
            # 检查为什么会生成如此大的规则范围
            if tcp_len and int(tcp_len) < (self.problematic_rule_range[1] - self.problematic_rule_range[0]):
                print(f"  ⚠️  规则范围({self.problematic_rule_range[1] - self.problematic_rule_range[0]}字节) 远大于帧长度({tcp_len}字节)!")
                print(f"  这表明可能是跨段消息处理错误!")
                
        except Exception as e:
            print(f"来源帧分析失败: {e}")
    
    def run_analysis(self):
        """运行完整分析"""
        print("开始ChangeCipherSpec规则错误匹配分析")
        print("=" * 60)
        
        self.find_changecipherspec_frames()
        self.analyze_tcp_stream_5()
        self.analyze_marker_rule_generation()
        
        print("\n" + "=" * 60)
        print("分析完成")

if __name__ == "__main__":
    analyzer = ChangeCipherSpecAnalyzer()
    analyzer.run_analysis()
