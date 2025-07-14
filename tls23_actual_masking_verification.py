#!/usr/bin/env python3
"""
TLS-23消息实际掩码状态验证脚本

专门验证输出pcap文件中TLS-23 ApplicationData消息的实际掩码效果。
严格禁止修改主程序代码，仅用于验证分析。
"""

import sys
import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class TLS23MaskingVerifier:
    """TLS-23消息掩码状态验证器"""
    
    def __init__(self):
        self.output_dir = Path("output/tls23_verification")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def verify_tls23_masking(self, pcap_file: str) -> Dict[str, Any]:
        """验证TLS-23消息的实际掩码状态"""
        logger.info(f"验证TLS-23掩码状态: {pcap_file}")
        
        if not Path(pcap_file).exists():
            return {"error": f"文件不存在: {pcap_file}"}
        
        verification_results = {
            "pcap_file": pcap_file,
            "file_exists": True,
            "tls23_messages": [],
            "masking_summary": {
                "total_messages": 0,
                "headers_preserved": 0,
                "bodies_masked": 0,
                "fully_masked": 0,
                "effectiveness": 0.0
            }
        }
        
        try:
            # 使用tshark提取TLS-23消息的详细信息
            tls23_messages = self._extract_tls23_messages(pcap_file)
            verification_results["tls23_messages"] = tls23_messages
            
            # 分析每个TLS-23消息的掩码状态
            for msg in tls23_messages:
                self._analyze_message_masking(msg)
            
            # 生成掩码摘要
            verification_results["masking_summary"] = self._generate_masking_summary(tls23_messages)
            
        except Exception as e:
            logger.error(f"验证失败: {e}")
            verification_results["error"] = str(e)
        
        return verification_results
    
    def _extract_tls23_messages(self, pcap_file: str) -> List[Dict[str, Any]]:
        """提取TLS-23消息的详细信息"""
        logger.info("提取TLS-23消息详细信息")
        
        # 使用tshark提取TLS-23消息
        cmd = [
            'tshark', '-r', pcap_file,
            '-Y', 'tls.record.content_type == 23',
            '-T', 'fields',
            '-e', 'frame.number',
            '-e', 'tcp.stream',
            '-e', 'tcp.seq_raw',
            '-e', 'tcp.len',
            '-e', 'tls.record.length',
            '-e', 'tls.record.opaque_type',
            '-E', 'separator=|'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise RuntimeError(f"tshark执行失败: {result.stderr}")
        
        messages = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            
            fields = line.split('|')
            if len(fields) >= 5:
                try:
                    message = {
                        "frame_number": int(fields[0]) if fields[0] else None,
                        "tcp_stream": int(fields[1]) if fields[1] else None,
                        "tcp_seq_raw": int(fields[2]) if fields[2] else None,
                        "tcp_len": int(fields[3]) if fields[3] else None,
                        "tls_record_length": int(fields[4]) if fields[4] else None,
                        "tls_opaque_type": fields[5] if len(fields) > 5 else None,
                        "raw_data": None,
                        "masking_analysis": {}
                    }
                    
                    # 提取原始数据
                    message["raw_data"] = self._extract_raw_data(pcap_file, message["frame_number"])
                    
                    messages.append(message)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"解析消息失败: {line}, 错误: {e}")
                    continue
        
        logger.info(f"提取到 {len(messages)} 个TLS-23消息")
        return messages
    
    def _extract_raw_data(self, pcap_file: str, frame_number: int) -> str:
        """提取指定帧的原始数据"""
        try:
            cmd = [
                'tshark', '-r', pcap_file,
                '-Y', f'frame.number == {frame_number}',
                '-T', 'fields',
                '-e', 'data.data'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().replace(':', '')
            
        except Exception as e:
            logger.warning(f"提取帧 {frame_number} 原始数据失败: {e}")
        
        return ""
    
    def _analyze_message_masking(self, message: Dict[str, Any]):
        """分析单个TLS-23消息的掩码状态"""
        raw_data = message.get("raw_data", "")
        tls_length = message.get("tls_record_length", 0)
        
        analysis = {
            "has_data": bool(raw_data),
            "data_length": len(raw_data) // 2 if raw_data else 0,
            "header_preserved": False,
            "body_masked": False,
            "fully_masked": False,
            "zero_percentage": 0.0
        }
        
        if raw_data and len(raw_data) >= 10:  # 至少5字节
            try:
                # 转换为字节数组
                data_bytes = bytes.fromhex(raw_data)
                
                # 分析TLS记录头部（前5字节）
                if len(data_bytes) >= 5:
                    header_bytes = data_bytes[:5]
                    
                    # 检查是否为有效的TLS记录头部
                    if header_bytes[0] == 23:  # TLS ApplicationData
                        analysis["header_preserved"] = True
                        
                        # 分析消息体部分（5字节之后）
                        if len(data_bytes) > 5:
                            body_bytes = data_bytes[5:]
                            zero_count = sum(1 for b in body_bytes if b == 0)
                            analysis["zero_percentage"] = zero_count / len(body_bytes) if body_bytes else 0.0
                            
                            # 判断消息体是否被掩码（80%以上为零）
                            analysis["body_masked"] = analysis["zero_percentage"] > 0.8
                        else:
                            # 只有头部，认为消息体已被完全掩码
                            analysis["body_masked"] = True
                            analysis["zero_percentage"] = 1.0
                    
                    # 检查是否完全被掩码
                    total_zeros = sum(1 for b in data_bytes if b == 0)
                    total_zero_percentage = total_zeros / len(data_bytes)
                    analysis["fully_masked"] = total_zero_percentage > 0.95
                
            except Exception as e:
                logger.warning(f"分析消息掩码状态失败: {e}")
                analysis["error"] = str(e)
        
        message["masking_analysis"] = analysis
    
    def _generate_masking_summary(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成掩码效果摘要"""
        summary = {
            "total_messages": len(messages),
            "headers_preserved": 0,
            "bodies_masked": 0,
            "fully_masked": 0,
            "effectiveness": 0.0,
            "details": {
                "with_data": 0,
                "without_data": 0,
                "avg_zero_percentage": 0.0
            }
        }
        
        if not messages:
            return summary
        
        zero_percentages = []
        
        for msg in messages:
            analysis = msg.get("masking_analysis", {})
            
            if analysis.get("has_data"):
                summary["details"]["with_data"] += 1
                zero_percentages.append(analysis.get("zero_percentage", 0.0))
            else:
                summary["details"]["without_data"] += 1
            
            if analysis.get("header_preserved"):
                summary["headers_preserved"] += 1
            
            if analysis.get("body_masked"):
                summary["bodies_masked"] += 1
            
            if analysis.get("fully_masked"):
                summary["fully_masked"] += 1
        
        # 计算平均零字节百分比
        if zero_percentages:
            summary["details"]["avg_zero_percentage"] = sum(zero_percentages) / len(zero_percentages)
        
        # 计算掩码有效性（基于消息体掩码率）
        if summary["total_messages"] > 0:
            summary["effectiveness"] = summary["bodies_masked"] / summary["total_messages"]
        
        return summary
    
    def verify_multiple_files(self, file_list: List[str]) -> Dict[str, Any]:
        """验证多个文件的TLS-23掩码状态"""
        results = {
            "verification_timestamp": __import__('time').time(),
            "files_verified": len(file_list),
            "overall_summary": {
                "total_messages": 0,
                "total_effectiveness": 0.0,
                "files_with_issues": []
            },
            "file_results": {}
        }
        
        total_effectiveness = 0.0
        valid_files = 0
        
        for file_path in file_list:
            logger.info(f"验证文件: {file_path}")
            file_result = self.verify_tls23_masking(file_path)
            results["file_results"][file_path] = file_result
            
            if "error" not in file_result:
                summary = file_result.get("masking_summary", {})
                effectiveness = summary.get("effectiveness", 0.0)
                total_messages = summary.get("total_messages", 0)
                
                results["overall_summary"]["total_messages"] += total_messages
                total_effectiveness += effectiveness
                valid_files += 1
                
                # 检查是否存在问题
                if effectiveness < 0.8:  # 掩码效果低于80%
                    results["overall_summary"]["files_with_issues"].append({
                        "file": file_path,
                        "effectiveness": effectiveness,
                        "total_messages": total_messages
                    })
        
        # 计算总体有效性
        if valid_files > 0:
            results["overall_summary"]["total_effectiveness"] = total_effectiveness / valid_files
        
        # 保存结果
        report_file = self.output_dir / "tls23_masking_verification_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"验证报告已保存: {report_file}")
        
        return results


def main():
    """主函数"""
    verifier = TLS23MaskingVerifier()
    
    # 验证GUI分析生成的输出文件
    test_files = [
        "output/gui_tls23_analysis/gui_output_tls_1_3_0-RTT-2_22_23_mix.pcap",
        "output/gui_tls23_analysis/direct_output_tls_1_3_0-RTT-2_22_23_mix.pcap",
        "output/gui_tls23_analysis/gui_output_tls_1_2_plainip.pcap",
        "output/gui_tls23_analysis/direct_output_tls_1_2_plainip.pcap",
        "output/gui_tls23_analysis/gui_output_https-justlaunchpage.pcap",
        "output/gui_tls23_analysis/direct_output_https-justlaunchpage.pcap"
    ]
    
    # 过滤存在的文件
    existing_files = [f for f in test_files if Path(f).exists()]
    
    if not existing_files:
        print("没有找到要验证的输出文件")
        return
    
    print(f"开始验证 {len(existing_files)} 个输出文件的TLS-23掩码状态...")
    
    results = verifier.verify_multiple_files(existing_files)
    
    # 打印关键结果
    print("\n" + "="*60)
    print("TLS-23消息掩码验证结果")
    print("="*60)
    print(f"验证文件数量: {results['files_verified']}")
    print(f"总TLS-23消息数: {results['overall_summary']['total_messages']}")
    print(f"总体掩码有效性: {results['overall_summary']['total_effectiveness']:.2%}")
    
    if results['overall_summary']['files_with_issues']:
        print(f"\n存在问题的文件 ({len(results['overall_summary']['files_with_issues'])}):")
        for issue in results['overall_summary']['files_with_issues']:
            print(f"  - {Path(issue['file']).name}: {issue['effectiveness']:.2%} ({issue['total_messages']} 消息)")
    else:
        print("\n✅ 所有文件的TLS-23掩码效果良好")
    
    print("="*60)
    
    return results


if __name__ == "__main__":
    main()
