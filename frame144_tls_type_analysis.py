#!/usr/bin/env python3
"""
帧144 TLS消息类型错误匹配问题深入分析

问题描述：
- 帧144包含正常的TLS-23 ApplicationData消息
- 载荷以170303010c...开头（其中17=23表示TLS ApplicationData，0303表示TLS 1.2版本）
- 错误现象：该消息被错误匹配到了tls_changecipherspec规则
- 影响范围：整个273字节载荷被错误地应用了ChangeCipherSpec的保留规则

分析目标：
1. 验证帧144的实际TLS消息类型
2. 分析Marker模块的TLS类型识别逻辑
3. 找出错误标记的具体原因
4. 提供修复方案
"""

import json
import subprocess
import sys
from pathlib import Path

class Frame144TLSAnalyzer:
    def __init__(self):
        self.test_file = "tests/data/tls/tls_1_2_double_vlan.pcap"
        self.target_frame = 144
        
    def analyze_frame_with_tshark(self):
        """使用tshark分析帧144的详细信息"""
        print("=== 1. tshark原始数据分析 ===")
        
        # 分析帧144的基本信息
        cmd = [
            "tshark", "-r", self.test_file,
            "-Y", f"frame.number == {self.target_frame}",
            "-T", "json",
            "-e", "frame.number",
            "-e", "tcp.seq_raw",
            "-e", "tcp.len", 
            "-e", "tcp.payload",
            "-e", "tls.record.content_type",
            "-e", "tls.record.version",
            "-e", "tls.record.length",
            "-e", "tls.app_data",
            "-e", "tls.segment.data"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            frame_data = json.loads(result.stdout)[0]["_source"]["layers"]
            
            print(f"帧号: {frame_data.get('frame.number', ['N/A'])[0]}")
            print(f"TCP序列号: {frame_data.get('tcp.seq_raw', ['N/A'])[0]}")
            print(f"TCP载荷长度: {frame_data.get('tcp.len', ['N/A'])[0]}")
            
            # 分析TCP载荷
            tcp_payload = frame_data.get('tcp.payload', [''])[0]
            if tcp_payload:
                print(f"TCP载荷前20字节: {tcp_payload[:40]}")
                print(f"载荷第一字节(十进制): {int(tcp_payload[:2], 16)}")
                print(f"载荷第二三字节(版本): {tcp_payload[2:6]}")
                
            # 分析TLS字段
            tls_content_type = frame_data.get('tls.record.content_type', [])
            tls_version = frame_data.get('tls.record.version', [])
            tls_length = frame_data.get('tls.record.length', [])
            tls_app_data = frame_data.get('tls.app_data', [])
            tls_segment_data = frame_data.get('tls.segment.data', [])
            
            print(f"TLS内容类型: {tls_content_type}")
            print(f"TLS版本: {tls_version}")
            print(f"TLS记录长度: {tls_length}")
            print(f"TLS应用数据: {tls_app_data}")
            print(f"TLS段数据: {tls_segment_data}")
            
            return frame_data
            
        except subprocess.CalledProcessError as e:
            print(f"tshark执行失败: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return None
    
    def analyze_marker_processing(self):
        """分析Marker模块如何处理帧144"""
        print("\n=== 2. Marker模块处理分析 ===")
        
        try:
            # 导入Marker模块
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
            
            # 查找帧144相关的规则
            frame144_rules = []
            for rule in ruleset.rules:
                if hasattr(rule, 'metadata') and rule.metadata:
                    frame_num = rule.metadata.get('frame_number')
                    if frame_num and str(frame_num) == str(self.target_frame):
                        frame144_rules.append(rule)
            
            print(f"\n帧144生成的规则数量: {len(frame144_rules)}")
            
            for i, rule in enumerate(frame144_rules):
                print(f"\n规则 {i+1}:")
                print(f"  规则类型: {rule.rule_type}")
                print(f"  序列号范围: {rule.seq_start} - {rule.seq_end}")
                print(f"  流ID: {rule.stream_id}")
                print(f"  方向: {rule.direction}")
                if hasattr(rule, 'metadata') and rule.metadata:
                    print(f"  元数据: {rule.metadata}")
            
            return frame144_rules
            
        except Exception as e:
            print(f"Marker分析失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def analyze_marker_debug(self):
        """深入调试Marker模块为什么没有为帧144生成规则"""
        print("\n=== 3. Marker模块调试分析 ===")

        try:
            # 导入Marker模块
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

            # 创建Marker实例并启用详细日志
            marker = TLSProtocolMarker(test_config)

            # 手动分析帧144
            print("手动分析帧144的处理过程...")

            # 使用tshark获取帧144的详细信息
            cmd = [
                "tshark", "-r", self.test_file,
                "-Y", f"frame.number == {self.target_frame}",
                "-T", "json"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packet_data = json.loads(result.stdout)[0]

            # 检查数据包是否包含TCP和TLS层
            layers = packet_data["_source"]["layers"]

            print(f"数据包层级: {list(layers.keys())}")

            # 检查TCP层
            if "tcp" in layers:
                tcp_layer = layers["tcp"]
                print(f"TCP层存在: {bool(tcp_layer)}")
                print(f"TCP序列号: {tcp_layer.get('tcp.seq_raw')}")
                print(f"TCP载荷长度: {tcp_layer.get('tcp.len')}")
            else:
                print("❌ 没有TCP层!")
                return

            # 检查TLS层
            if "tls" in layers:
                tls_layer = layers["tls"]
                print(f"TLS层存在: {bool(tls_layer)}")
                print(f"TLS内容类型: {tls_layer.get('tls.record.content_type')}")
                print(f"TLS版本: {tls_layer.get('tls.record.version')}")
            else:
                print("❌ 没有TLS层!")
                return

            # 检查Marker的处理条件
            print("\n检查Marker处理条件:")

            # 1. 检查是否为TLS记录开始
            tcp_payload = layers.get("tcp", {}).get("tcp.payload", [""])[0]
            if tcp_payload:
                is_tls_start = marker._is_tls_record_start(packet_data, tcp_payload)
                print(f"是否为TLS记录开始: {is_tls_start}")

                # 2. 检查TLS类型识别
                content_types = layers.get("tls", {}).get("tls.record.content_type", [])
                if content_types and not isinstance(content_types, list):
                    content_types = [content_types]

                print(f"识别的TLS内容类型: {content_types}")

                for content_type in content_types:
                    if content_type and str(content_type).isdigit():
                        type_num = int(content_type)

                        # 3. 检查类型一致性验证
                        is_consistent = marker._validate_tls_type_consistency(tcp_payload, type_num)
                        print(f"TLS类型{type_num}一致性验证: {is_consistent}")

                        # 4. 检查是否应该保留
                        should_preserve = marker._should_preserve_tls_type(type_num)
                        print(f"是否应该保留TLS类型{type_num}: {should_preserve}")

                        # 5. 尝试创建规则
                        if should_preserve and is_consistent:
                            print(f"尝试为TLS类型{type_num}创建规则...")
                            # 这里可以进一步调试规则创建过程
                        else:
                            print(f"跳过TLS类型{type_num}: 保留={should_preserve}, 一致性={is_consistent}")

        except Exception as e:
            print(f"Marker调试分析失败: {e}")
            import traceback
            traceback.print_exc()

    def analyze_existing_rules(self):
        """分析现有的所有规则，查找可能错误匹配帧144的规则"""
        print("\n=== 4. 现有规则分析 ===")

        try:
            # 导入Marker模块
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

            # 创建Marker实例
            marker = TLSProtocolMarker(test_config)

            # 分析文件
            print("分析所有规则...")
            ruleset = marker.analyze_file(self.test_file, test_config)

            print(f"总规则数: {len(ruleset.rules)}")

            # 获取帧144的序列号范围
            frame_data = self.analyze_frame_with_tshark()
            if not frame_data:
                return

            tcp_seq = int(frame_data.get('tcp.seq_raw', ['0'])[0])
            tcp_len = int(frame_data.get('tcp.len', ['0'])[0])
            frame144_start = tcp_seq
            frame144_end = tcp_seq + tcp_len

            print(f"帧144序列号范围: {frame144_start} - {frame144_end}")

            # 查找可能与帧144重叠的规则
            overlapping_rules = []
            for rule in ruleset.rules:
                # 检查序列号范围是否重叠
                rule_start = rule.seq_start
                rule_end = rule.seq_end

                overlap_start = max(rule_start, frame144_start)
                overlap_end = min(rule_end, frame144_end)

                if overlap_start < overlap_end:
                    overlapping_rules.append((rule, overlap_start, overlap_end))

            print(f"\n与帧144重叠的规则数: {len(overlapping_rules)}")

            for i, (rule, overlap_start, overlap_end) in enumerate(overlapping_rules):
                print(f"\n重叠规则 {i+1}:")
                print(f"  规则类型: {rule.rule_type}")
                print(f"  规则范围: {rule.seq_start} - {rule.seq_end}")
                print(f"  重叠范围: {overlap_start} - {overlap_end}")
                print(f"  流ID: {rule.stream_id}")
                print(f"  方向: {rule.direction}")
                if hasattr(rule, 'metadata') and rule.metadata:
                    frame_num = rule.metadata.get('frame_number')
                    tls_type = rule.metadata.get('tls_content_type')
                    print(f"  来源帧: {frame_num}")
                    print(f"  TLS类型: {tls_type}")

                # 这里可能就是错误匹配的规则!
                if rule.rule_type == "tls_changecipherspec":
                    print(f"  ⚠️  发现ChangeCipherSpec规则与帧144重叠!")
                    print(f"  这可能就是错误匹配的原因!")

        except Exception as e:
            print(f"现有规则分析失败: {e}")
            import traceback
            traceback.print_exc()
    
    def analyze_rule_generation_logic(self):
        """深入分析规则生成逻辑"""
        print("\n=== 4. 规则生成逻辑深入分析 ===")
        
        try:
            # 手动模拟TLS类型识别过程
            frame_data = self.analyze_frame_with_tshark()
            if not frame_data:
                return
            
            tcp_payload = frame_data.get('tcp.payload', [''])[0]
            tls_content_types = frame_data.get('tls.record.content_type', [])
            
            print(f"tshark解析的TLS内容类型: {tls_content_types}")
            
            if tcp_payload and len(tcp_payload) >= 2:
                # 手动解析载荷第一字节
                manual_type = int(tcp_payload[:2], 16)
                print(f"手动解析的TLS类型: {manual_type}")
                
                # 检查一致性
                if tls_content_types:
                    tshark_types = [int(t) for t in tls_content_types if str(t).isdigit()]
                    print(f"tshark类型列表: {tshark_types}")
                    
                    if manual_type in tshark_types:
                        print("✅ 手动解析与tshark一致")
                    else:
                        print("❌ 手动解析与tshark不一致!")
                        print("这可能是问题的根源!")
            
            # 分析可能的错误原因
            print("\n可能的错误原因分析:")
            print("1. tshark解析错误 - tshark可能错误识别了TLS类型")
            print("2. 多TLS消息混淆 - 单个TCP包含多个TLS消息时的处理错误")
            print("3. 规则类型映射错误 - TLS类型到规则类型的映射有误")
            print("4. 规则合并错误 - 不同类型的规则被错误合并")
            
        except Exception as e:
            print(f"规则生成逻辑分析失败: {e}")
            import traceback
            traceback.print_exc()
    
    def run_complete_analysis(self):
        """运行完整分析"""
        print("开始帧144 TLS消息类型错误匹配问题分析")
        print("=" * 60)

        # 1. tshark原始数据分析
        self.analyze_frame_with_tshark()

        # 2. Marker模块处理分析
        self.analyze_marker_processing()

        # 3. Marker模块调试分析
        self.analyze_marker_debug()

        # 4. 现有规则分析
        self.analyze_existing_rules()

        # 5. 规则生成逻辑深入分析
        self.analyze_rule_generation_logic()

        print("\n" + "=" * 60)
        print("分析完成")

if __name__ == "__main__":
    analyzer = Frame144TLSAnalyzer()
    analyzer.run_complete_analysis()
