#!/usr/bin/env python3
"""
PktMask Marker模块静默失败检测工具

检测Marker模块是否在静默失败，导致返回空的保留规则集。
通过模拟Marker模块的关键步骤来识别可能的失败点。
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
import shutil

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarkerSilentFailureDetector:
    """Marker模块静默失败检测器"""
    
    def __init__(self):
        self.test_data_dir = Path("tests/data/tls")
        
    def detect_silent_failures(self):
        """检测静默失败"""
        logger.info("开始检测Marker模块静默失败")
        
        # 分析失败案例
        test_cases = [
            "tls_1_2_pop_mix.pcapng",  # 完全未掩码
            "tls_1_2-2.pcapng"         # 成功案例（对比）
        ]
        
        for test_case in test_cases:
            logger.info(f"\n{'='*60}")
            logger.info(f"检测测试案例: {test_case}")
            self._detect_single_case_failures(test_case)
    
    def _detect_single_case_failures(self, test_file: str):
        """检测单个测试案例的静默失败"""
        file_path = self.test_data_dir / test_file
        
        if not file_path.exists():
            logger.error(f"测试文件不存在: {file_path}")
            return
        
        # 1. 检查tshark可用性
        logger.info("步骤1: 检查tshark可用性")
        tshark_available = self._check_tshark_availability()
        
        # 2. 检查TLS消息扫描
        logger.info("步骤2: 检查TLS消息扫描")
        tls_scan_result = self._check_tls_message_scanning(file_path)
        
        # 3. 检查TCP流分析
        logger.info("步骤3: 检查TCP流分析")
        tcp_flow_result = self._check_tcp_flow_analysis(file_path)
        
        # 4. 检查载荷重组
        logger.info("步骤4: 检查载荷重组")
        payload_reassembly_result = self._check_payload_reassembly(file_path)
        
        # 5. 检查TLS记录解析
        logger.info("步骤5: 检查TLS记录解析")
        tls_parsing_result = self._check_tls_record_parsing(file_path)
        
        # 6. 综合分析失败点
        logger.info("步骤6: 综合分析失败点")
        self._analyze_failure_points(test_file, {
            "tshark_available": tshark_available,
            "tls_scan": tls_scan_result,
            "tcp_flow": tcp_flow_result,
            "payload_reassembly": payload_reassembly_result,
            "tls_parsing": tls_parsing_result
        })
    
    def _check_tshark_availability(self) -> Dict[str, Any]:
        """检查tshark可用性"""
        logger.info("检查tshark可用性")
        
        try:
            # 检查tshark版本
            result = subprocess.run(["tshark", "-v"], capture_output=True, text=True, check=True)
            version_info = result.stdout.split('\n')[0] if result.stdout else "Unknown"
            
            logger.info(f"✅ tshark可用: {version_info}")
            return {"available": True, "version": version_info}
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ tshark执行失败: {e}")
            return {"available": False, "error": str(e)}
        except FileNotFoundError:
            logger.error("❌ tshark未找到")
            return {"available": False, "error": "tshark not found"}
        except Exception as e:
            logger.error(f"❌ tshark检查异常: {e}")
            return {"available": False, "error": str(e)}
    
    def _check_tls_message_scanning(self, file_path: Path) -> Dict[str, Any]:
        """检查TLS消息扫描"""
        logger.info(f"检查TLS消息扫描: {file_path}")
        
        try:
            # 模拟Marker模块的TLS消息扫描逻辑
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tls",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "tls.record.content_type"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                logger.warning("⚠️ tshark返回空结果")
                return {"success": False, "error": "empty_result", "packets": []}
            
            packets = json.loads(result.stdout)
            tls_packets = len(packets)
            
            # 统计TLS消息类型
            tls_types = {}
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                content_types = layers.get("tls.record.content_type", [])
                
                if isinstance(content_types, list):
                    for ct in content_types:
                        tls_types[ct] = tls_types.get(ct, 0) + 1
                elif content_types:
                    tls_types[content_types] = tls_types.get(content_types, 0) + 1
            
            logger.info(f"✅ TLS消息扫描成功: {tls_packets}个包, 类型分布: {tls_types}")
            return {
                "success": True,
                "packets": packets,
                "tls_packet_count": tls_packets,
                "tls_types": tls_types
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ TLS消息扫描失败: {e}")
            return {"success": False, "error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON解析失败: {e}")
            return {"success": False, "error": f"json_decode_error: {e}"}
        except Exception as e:
            logger.error(f"❌ TLS消息扫描异常: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_tcp_flow_analysis(self, file_path: Path) -> Dict[str, Any]:
        """检查TCP流分析"""
        logger.info(f"检查TCP流分析: {file_path}")
        
        try:
            # 模拟Marker模块的TCP流分析逻辑
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tcp",
                "-e", "tcp.stream",
                "-e", "frame.number"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                logger.warning("⚠️ TCP流分析返回空结果")
                return {"success": False, "error": "empty_result"}
            
            packets = json.loads(result.stdout)
            
            # 统计TCP流
            streams = set()
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                stream_id = self._get_first_value(layers.get("tcp.stream"))
                if stream_id:
                    streams.add(stream_id)
            
            logger.info(f"✅ TCP流分析成功: {len(packets)}个包, {len(streams)}个流")
            return {
                "success": True,
                "tcp_packet_count": len(packets),
                "stream_count": len(streams),
                "streams": list(streams)
            }
            
        except Exception as e:
            logger.error(f"❌ TCP流分析失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_payload_reassembly(self, file_path: Path) -> Dict[str, Any]:
        """检查载荷重组"""
        logger.info(f"检查载荷重组: {file_path}")
        
        try:
            # 模拟载荷重组逻辑
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tcp and tcp.len > 0",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "tcp.seq_raw",
                "-e", "tcp.len",
                "-e", "tcp.payload",
                "-o", "tcp.desegment_tcp_streams:TRUE"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                logger.warning("⚠️ 载荷重组返回空结果")
                return {"success": False, "error": "empty_result"}
            
            packets = json.loads(result.stdout)
            
            # 统计载荷信息
            payload_packets = 0
            total_payload_bytes = 0
            
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                tcp_len = self._get_first_value(layers.get("tcp.len"))
                tcp_payload = self._get_first_value(layers.get("tcp.payload"))
                
                if tcp_len and int(tcp_len) > 0:
                    payload_packets += 1
                    total_payload_bytes += int(tcp_len)
            
            logger.info(f"✅ 载荷重组成功: {payload_packets}个载荷包, {total_payload_bytes}字节")
            return {
                "success": True,
                "payload_packet_count": payload_packets,
                "total_payload_bytes": total_payload_bytes
            }
            
        except Exception as e:
            logger.error(f"❌ 载荷重组失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_tls_record_parsing(self, file_path: Path) -> Dict[str, Any]:
        """检查TLS记录解析"""
        logger.info(f"检查TLS记录解析: {file_path}")
        
        try:
            # 检查TLS-23记录的详细信息
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tls.record.content_type == 23",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "tcp.seq_raw",
                "-e", "tls.record.length",
                "-e", "tls.record.version"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                logger.warning("⚠️ 没有找到TLS-23记录")
                return {"success": True, "tls23_count": 0, "records": []}
            
            packets = json.loads(result.stdout)
            
            # 解析TLS-23记录
            tls23_records = []
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                
                frame = self._get_first_value(layers.get("frame.number"))
                stream = self._get_first_value(layers.get("tcp.stream"))
                tcp_seq = self._get_first_value(layers.get("tcp.seq_raw"))
                tls_length = self._get_first_value(layers.get("tls.record.length"))
                tls_version = self._get_first_value(layers.get("tls.record.version"))
                
                if frame and stream and tcp_seq and tls_length:
                    tls23_records.append({
                        "frame": frame,
                        "stream": stream,
                        "tcp_seq": tcp_seq,
                        "tls_length": tls_length,
                        "tls_version": tls_version
                    })
            
            logger.info(f"✅ TLS记录解析成功: {len(tls23_records)}个TLS-23记录")
            return {
                "success": True,
                "tls23_count": len(tls23_records),
                "records": tls23_records
            }
            
        except Exception as e:
            logger.error(f"❌ TLS记录解析失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _analyze_failure_points(self, test_file: str, results: Dict[str, Any]):
        """综合分析失败点"""
        logger.info("综合分析失败点")
        
        failure_points = []
        
        # 检查各个步骤的结果
        if not results["tshark_available"]["available"]:
            failure_points.append("tshark不可用")
        
        if not results["tls_scan"]["success"]:
            failure_points.append(f"TLS消息扫描失败: {results['tls_scan']['error']}")
        
        if not results["tcp_flow"]["success"]:
            failure_points.append(f"TCP流分析失败: {results['tcp_flow']['error']}")
        
        if not results["payload_reassembly"]["success"]:
            failure_points.append(f"载荷重组失败: {results['payload_reassembly']['error']}")
        
        if not results["tls_parsing"]["success"]:
            failure_points.append(f"TLS记录解析失败: {results['tls_parsing']['error']}")
        
        # 分析结果
        if failure_points:
            logger.error(f"❌ 发现 {len(failure_points)} 个失败点:")
            for i, point in enumerate(failure_points, 1):
                logger.error(f"  {i}. {point}")
            
            logger.error("这些失败点可能导致Marker模块静默失败并返回空规则集")
        else:
            logger.info("✅ 所有检查步骤都成功")
            
            # 检查是否有TLS-23消息但没有生成规则
            tls23_count = results["tls_parsing"].get("tls23_count", 0)
            if tls23_count > 0:
                logger.warning(f"⚠️ 发现 {tls23_count} 个TLS-23消息，但掩码可能仍然失败")
                logger.warning("这表明问题可能在规则生成或应用的后续步骤中")
            else:
                logger.info("ℹ️ 没有TLS-23消息，掩码失败是正常的")
        
        # 输出诊断建议
        logger.info("\n诊断建议:")
        if failure_points:
            logger.info("1. 修复上述失败点")
            logger.info("2. 检查tshark配置和权限")
            logger.info("3. 验证输入文件格式")
        else:
            logger.info("1. 检查Marker模块的规则生成逻辑")
            logger.info("2. 检查Masker模块的规则应用逻辑")
            logger.info("3. 验证双模块间的数据传递")
    
    def _get_first_value(self, value):
        """获取第一个值（处理tshark的数组输出）"""
        if isinstance(value, list) and value:
            return value[0]
        return value

def main():
    """主函数"""
    detector = MarkerSilentFailureDetector()
    detector.detect_silent_failures()

if __name__ == "__main__":
    main()
