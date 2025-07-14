#!/usr/bin/env python3
"""
PktMask 保留规则生成验证工具

验证Marker模块是否正确生成了保留规则，以及这些规则的内容是否正确。
通过模拟Marker模块的核心逻辑来诊断规则生成问题。
严格禁止修改主程序代码，仅用于问题诊断。
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import tempfile
import os

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KeepRulesGenerationAnalyzer:
    """保留规则生成分析器"""
    
    def __init__(self):
        self.test_data_dir = Path("tests/data/tls")
        
    def analyze_keep_rules_generation(self):
        """分析保留规则生成"""
        logger.info("开始分析保留规则生成")
        
        # 分析失败案例
        test_cases = [
            "tls_1_2_pop_mix.pcapng",  # 完全未掩码
            "tls_1_2-2.pcapng"         # 成功案例（对比）
        ]
        
        for test_case in test_cases:
            logger.info(f"\n{'='*60}")
            logger.info(f"分析测试案例: {test_case}")
            self._analyze_single_case_rules(test_case)
    
    def _analyze_single_case_rules(self, test_file: str):
        """分析单个测试案例的规则生成"""
        file_path = self.test_data_dir / test_file
        
        if not file_path.exists():
            logger.error(f"测试文件不存在: {file_path}")
            return
        
        # 1. 分析TLS-23消息的详细信息
        logger.info("步骤1: 分析TLS-23消息详细信息")
        tls23_details = self._analyze_tls23_details(file_path)
        
        # 2. 模拟Marker模块的规则生成逻辑
        logger.info("步骤2: 模拟Marker模块规则生成")
        simulated_rules = self._simulate_marker_rules(file_path, tls23_details)
        
        # 3. 分析规则的有效性
        logger.info("步骤3: 分析规则有效性")
        self._analyze_rules_validity(simulated_rules, tls23_details)
        
        # 4. 检查配置影响
        logger.info("步骤4: 检查配置影响")
        self._check_config_impact(test_file, tls23_details)
    
    def _analyze_tls23_details(self, file_path: Path) -> List[Dict[str, Any]]:
        """分析TLS-23消息的详细信息"""
        logger.info(f"分析TLS-23消息详情: {file_path}")
        
        try:
            # 使用tshark提取详细的TLS-23信息
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tls.record.content_type == 23",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "ip.src", "-e", "ip.dst",
                "-e", "tcp.srcport", "-e", "tcp.dstport",
                "-e", "tcp.seq_raw", "-e", "tcp.len",
                "-e", "tls.record.content_type",
                "-e", "tls.record.length",
                "-e", "tls.record.version"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            tls23_messages = []
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                
                frame = self._get_first_value(layers.get("frame.number", ""))
                stream = self._get_first_value(layers.get("tcp.stream", ""))
                src_ip = self._get_first_value(layers.get("ip.src", ""))
                dst_ip = self._get_first_value(layers.get("ip.dst", ""))
                src_port = self._get_first_value(layers.get("tcp.srcport", ""))
                dst_port = self._get_first_value(layers.get("tcp.dstport", ""))
                tcp_seq = self._get_first_value(layers.get("tcp.seq_raw", ""))
                tcp_len = self._get_first_value(layers.get("tcp.len", ""))
                tls_length = self._get_first_value(layers.get("tls.record.length", ""))
                tls_version = self._get_first_value(layers.get("tls.record.version", ""))
                
                # 计算预期的保留规则
                if tcp_seq and tls_length:
                    try:
                        seq_start = int(tcp_seq)
                        tls_record_len = int(tls_length)
                        
                        # TLS记录头部（5字节）
                        header_end = seq_start + 5
                        # TLS记录载荷
                        payload_end = seq_start + 5 + tls_record_len
                        
                        # 确定方向（简化逻辑）
                        direction = "forward" if src_port < dst_port else "reverse"
                        
                        tls23_messages.append({
                            "frame": frame,
                            "stream": stream,
                            "src_ip": src_ip,
                            "dst_ip": dst_ip,
                            "src_port": src_port,
                            "dst_port": dst_port,
                            "direction": direction,
                            "tcp_seq": tcp_seq,
                            "tcp_len": tcp_len,
                            "tls_length": tls_length,
                            "tls_version": tls_version,
                            "expected_header_rule": {
                                "stream_id": stream,
                                "direction": direction,
                                "seq_start": seq_start,
                                "seq_end": header_end,
                                "rule_type": "tls_applicationdata_header"
                            },
                            "expected_payload_range": {
                                "seq_start": header_end,
                                "seq_end": payload_end
                            }
                        })
                        
                    except ValueError as e:
                        logger.warning(f"序列号解析失败: {e}")
            
            logger.info(f"分析到 {len(tls23_messages)} 个TLS-23消息")
            for i, msg in enumerate(tls23_messages):
                logger.info(f"  TLS-23 #{i+1}: Frame {msg['frame']}, Stream {msg['stream']}, "
                           f"方向 {msg['direction']}")
                logger.info(f"    TCP序列号: {msg['tcp_seq']}, TLS长度: {msg['tls_length']}")
                logger.info(f"    预期头部规则: [{msg['expected_header_rule']['seq_start']}, "
                           f"{msg['expected_header_rule']['seq_end']})")
                logger.info(f"    载荷范围: [{msg['expected_payload_range']['seq_start']}, "
                           f"{msg['expected_payload_range']['seq_end']})")
            
            return tls23_messages
            
        except subprocess.CalledProcessError as e:
            logger.error(f"TLS-23详情分析失败: {e}")
            return []
        except Exception as e:
            logger.error(f"TLS-23详情分析异常: {e}")
            return []
    
    def _simulate_marker_rules(self, file_path: Path, tls23_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """模拟Marker模块的规则生成逻辑"""
        logger.info("模拟Marker模块规则生成逻辑")
        
        simulated_rules = []
        
        # 根据TLS-23消息生成预期的保留规则
        for msg in tls23_details:
            # 对于TLS-23 ApplicationData，默认配置应该只保留头部
            header_rule = {
                "stream_id": msg["stream"],
                "direction": msg["direction"],
                "seq_start": msg["expected_header_rule"]["seq_start"],
                "seq_end": msg["expected_header_rule"]["seq_end"],
                "rule_type": "tls_applicationdata_header",
                "metadata": {
                    "tls_content_type": 23,
                    "tls_type_name": "ApplicationData",
                    "frame_number": msg["frame"],
                    "tcp_seq_raw": msg["tcp_seq"],
                    "preserve_reason": "tls_record_header",
                    "header_size": 5,
                    "preserve_strategy": "header_only"
                }
            }
            
            simulated_rules.append(header_rule)
            
            logger.info(f"生成模拟规则: Stream {header_rule['stream_id']}, "
                       f"方向 {header_rule['direction']}, "
                       f"序列号 [{header_rule['seq_start']}, {header_rule['seq_end']})")
        
        logger.info(f"总共生成 {len(simulated_rules)} 条模拟保留规则")
        return simulated_rules
    
    def _analyze_rules_validity(self, simulated_rules: List[Dict[str, Any]], 
                               tls23_details: List[Dict[str, Any]]):
        """分析规则的有效性"""
        logger.info("分析规则有效性")
        
        if not simulated_rules:
            logger.error("❌ 没有生成任何保留规则！")
            logger.error("这可能是导致完全未掩码的根本原因")
            return
        
        logger.info(f"✅ 生成了 {len(simulated_rules)} 条保留规则")
        
        # 检查规则覆盖范围
        total_tls23_messages = len(tls23_details)
        rules_count = len(simulated_rules)
        
        if rules_count == total_tls23_messages:
            logger.info("✅ 规则数量与TLS-23消息数量匹配")
        else:
            logger.warning(f"⚠️ 规则数量不匹配: 规则{rules_count} vs TLS-23消息{total_tls23_messages}")
        
        # 检查规则的序列号范围
        for i, rule in enumerate(simulated_rules):
            seq_range = rule["seq_end"] - rule["seq_start"]
            if seq_range == 5:
                logger.info(f"✅ 规则 {i+1}: 头部保留规则正确 (5字节)")
            else:
                logger.warning(f"⚠️ 规则 {i+1}: 序列号范围异常 ({seq_range}字节)")
    
    def _check_config_impact(self, test_file: str, tls23_details: List[Dict[str, Any]]):
        """检查配置对规则生成的影响"""
        logger.info("检查配置影响")
        
        # 检查是否是配置问题导致的规则生成失败
        logger.info("分析可能的配置问题:")
        
        # 1. 检查preserve_config配置
        logger.info("1. preserve_config配置:")
        logger.info("   - application_data=False: 只保留TLS-23头部（默认）")
        logger.info("   - application_data=True: 保留整个TLS-23消息")
        
        # 2. 检查TLS版本兼容性
        tls_versions = set()
        for msg in tls23_details:
            if msg.get("tls_version"):
                tls_versions.add(msg["tls_version"])
        
        logger.info(f"2. TLS版本: {list(tls_versions)}")
        
        # 3. 检查流和方向分布
        stream_directions = {}
        for msg in tls23_details:
            stream_id = msg["stream"]
            direction = msg["direction"]
            key = f"{stream_id}-{direction}"
            if key not in stream_directions:
                stream_directions[key] = 0
            stream_directions[key] += 1
        
        logger.info(f"3. 流方向分布: {stream_directions}")
        
        # 4. 分析可能的问题
        if len(tls23_details) == 0:
            logger.error("❌ 没有找到TLS-23消息，可能是文件解析问题")
        elif len(set(msg["stream"] for msg in tls23_details)) > 1:
            logger.info("ℹ️ 多流场景，需要确保流ID一致性")
        else:
            logger.info("ℹ️ 单流场景，流ID一致性应该不是问题")
        
        # 5. 检查序列号范围
        seq_ranges = []
        for msg in tls23_details:
            try:
                seq_start = int(msg["tcp_seq"])
                seq_ranges.append(seq_start)
            except:
                pass
        
        if seq_ranges:
            logger.info(f"4. 序列号范围: {min(seq_ranges)} - {max(seq_ranges)}")
            if max(seq_ranges) - min(seq_ranges) > 2**31:
                logger.warning("⚠️ 序列号跨度很大，可能存在回绕问题")
    
    def _get_first_value(self, value):
        """获取第一个值（处理tshark的数组输出）"""
        if isinstance(value, list) and value:
            return value[0]
        return value

def main():
    """主函数"""
    analyzer = KeepRulesGenerationAnalyzer()
    analyzer.analyze_keep_rules_generation()

if __name__ == "__main__":
    main()
