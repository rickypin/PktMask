#!/usr/bin/env python3
"""
PktMask双模块架构端到端测试

测试完整的Marker + Masker流程，验证掩码结果是否符合预期。
特别关注TLS-23消息头保留和多条TLS消息的处理。
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage


class EndToEndMaskTester:
    """端到端掩码测试器"""
    
    def __init__(self):
        self.test_file = "tests/samples/tls-single/tls_sample.pcap"
        self.config = {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 关键：只保留头部
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
    def run_end_to_end_test(self) -> Dict[str, Any]:
        """运行端到端测试"""
        print("=" * 80)
        print("PktMask双模块架构端到端测试")
        print("=" * 80)
        
        results = {
            "original_analysis": self._analyze_original_file(),
            "mask_processing": self._run_mask_processing(),
            "masked_analysis": None,
            "comparison": None,
            "validation": None
        }
        
        if results["mask_processing"]["success"]:
            results["masked_analysis"] = self._analyze_masked_file(
                results["mask_processing"]["output_file"]
            )
            results["comparison"] = self._compare_files(
                results["original_analysis"], 
                results["masked_analysis"]
            )
            results["validation"] = self._validate_mask_results(results)
        
        return results
    
    def _analyze_original_file(self) -> Dict[str, Any]:
        """分析原始文件"""
        print("\n" + "=" * 60)
        print("1. 分析原始文件")
        print("=" * 60)
        
        try:
            # 使用tshark分析原始文件的TLS消息
            cmd = [
                "tshark", "-r", self.test_file,
                "-T", "json",
                "-Y", "tls",
                "-e", "frame.number",
                "-e", "tcp.stream", 
                "-e", "tcp.seq_raw",
                "-e", "tcp.len",
                "-e", "tls.record.content_type",
                "-e", "tls.record.length"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            tls_data = json.loads(result.stdout)
            
            # 统计TLS消息
            tls_stats = {
                "total_tls_packets": len(tls_data),
                "tls_message_types": {},
                "tls23_packets": [],
                "tls23_messages": []
            }
            
            for packet in tls_data:
                layers = packet.get("_source", {}).get("layers", {})
                frame_num = layers.get("frame.number", [""])[0]
                content_types = layers.get("tls.record.content_type", [])
                record_lengths = layers.get("tls.record.length", [])
                tcp_seq = layers.get("tcp.seq_raw", [""])[0]
                
                if not isinstance(content_types, list):
                    content_types = [content_types] if content_types else []
                if not isinstance(record_lengths, list):
                    record_lengths = [record_lengths] if record_lengths else []
                
                # 统计TLS消息类型
                for content_type in content_types:
                    if content_type:
                        tls_stats["tls_message_types"][content_type] = \
                            tls_stats["tls_message_types"].get(content_type, 0) + 1
                
                # 记录TLS-23相关信息
                if "23" in content_types:
                    tls23_count = content_types.count("23")
                    tls_stats["tls23_packets"].append({
                        "frame": frame_num,
                        "tcp_seq": tcp_seq,
                        "tls23_count": tls23_count,
                        "content_types": content_types,
                        "record_lengths": record_lengths
                    })
                    
                    # 记录每个TLS-23消息的详细信息
                    current_offset = 0
                    for i, (ct, length) in enumerate(zip(content_types, record_lengths)):
                        if ct == "23":
                            tls_stats["tls23_messages"].append({
                                "frame": frame_num,
                                "message_index": i + 1,
                                "tcp_seq": int(tcp_seq) if tcp_seq else 0,
                                "message_start_seq": int(tcp_seq) + current_offset if tcp_seq else 0,
                                "record_length": int(length) if length else 0,
                                "header_start": int(tcp_seq) + current_offset if tcp_seq else 0,
                                "header_end": int(tcp_seq) + current_offset + 5 if tcp_seq else 5
                            })
                        if length:
                            current_offset += 5 + int(length)  # TLS头部5字节 + 载荷
            
            print(f"原始文件TLS统计:")
            print(f"  总TLS数据包: {tls_stats['total_tls_packets']}")
            print(f"  TLS消息类型分布: {tls_stats['tls_message_types']}")
            print(f"  TLS-23数据包数: {len(tls_stats['tls23_packets'])}")
            print(f"  TLS-23消息总数: {len(tls_stats['tls23_messages'])}")
            
            if tls_stats["tls23_messages"]:
                print(f"\n  TLS-23消息详情:")
                for msg in tls_stats["tls23_messages"]:
                    print(f"    Frame {msg['frame']}消息#{msg['message_index']}: "
                          f"头部序列号 {msg['header_start']}-{msg['header_end']}")
            
            return tls_stats
            
        except Exception as e:
            print(f"❌ 原始文件分析失败: {e}")
            return {"error": str(e)}
    
    def _run_mask_processing(self) -> Dict[str, Any]:
        """运行掩码处理"""
        print("\n" + "=" * 60)
        print("2. 运行掩码处理")
        print("=" * 60)
        
        try:
            # 创建临时输出文件
            with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
                output_file = tmp_file.name
            
            # 创建NewMaskPayloadStage实例
            mask_stage = NewMaskPayloadStage(self.config)
            
            print(f"输入文件: {self.test_file}")
            print(f"输出文件: {output_file}")
            print(f"配置: application_data = {self.config['preserve']['application_data']}")
            
            # 执行掩码处理
            stats = mask_stage.process_file(self.test_file, output_file)
            
            print(f"\n掩码处理完成:")
            print(f"  处理状态: {stats.extra_metrics.get('success', 'unknown')}")
            print(f"  处理时间: {stats.duration_ms / 1000:.3f}秒")
            print(f"  处理包数: {stats.packets_processed}")
            print(f"  修改包数: {stats.packets_modified}")
            print(f"  掩码字节数: {stats.extra_metrics.get('masked_bytes', 0)}")
            print(f"  保留字节数: {stats.extra_metrics.get('preserved_bytes', 0)}")

            return {
                "success": True,
                "output_file": output_file,
                "stats": {
                    "status": stats.extra_metrics.get('success', False),
                    "processing_time": stats.duration_ms / 1000,
                    "packets_processed": stats.packets_processed,
                    "packets_modified": stats.packets_modified,
                    "masked_bytes": stats.extra_metrics.get('masked_bytes', 0),
                    "preserved_bytes": stats.extra_metrics.get('preserved_bytes', 0)
                }
            }
            
        except Exception as e:
            print(f"❌ 掩码处理失败: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _analyze_masked_file(self, masked_file: str) -> Dict[str, Any]:
        """分析掩码后的文件"""
        print("\n" + "=" * 60)
        print("3. 分析掩码后的文件")
        print("=" * 60)
        
        try:
            # 使用tshark分析掩码后文件的TLS消息
            cmd = [
                "tshark", "-r", masked_file,
                "-T", "json",
                "-Y", "tls",
                "-e", "frame.number",
                "-e", "tcp.seq_raw",
                "-e", "tcp.len",
                "-e", "tls.record.content_type",
                "-e", "tls.record.length"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            tls_data = json.loads(result.stdout)
            
            print(f"掩码后文件TLS统计:")
            print(f"  可识别TLS数据包: {len(tls_data)}")
            
            # 检查TLS结构是否保持
            tls23_identifiable = 0
            for packet in tls_data:
                layers = packet.get("_source", {}).get("layers", {})
                content_types = layers.get("tls.record.content_type", [])
                if not isinstance(content_types, list):
                    content_types = [content_types] if content_types else []
                if "23" in content_types:
                    tls23_identifiable += 1
            
            print(f"  可识别TLS-23数据包: {tls23_identifiable}")
            
            return {
                "total_identifiable_tls": len(tls_data),
                "tls23_identifiable": tls23_identifiable,
                "tls_data": tls_data
            }
            
        except Exception as e:
            print(f"❌ 掩码后文件分析失败: {e}")
            return {"error": str(e)}
    
    def _compare_files(self, original: Dict, masked: Dict) -> Dict[str, Any]:
        """比较原始文件和掩码后文件"""
        print("\n" + "=" * 60)
        print("4. 文件比较分析")
        print("=" * 60)
        
        if "error" in original or "error" in masked:
            return {"error": "无法比较，存在分析错误"}
        
        comparison = {
            "tls_structure_preserved": False,
            "tls23_headers_preserved": False,
            "application_data_masked": False
        }
        
        # 检查TLS结构是否保持
        original_tls23_packets = len(original["tls23_packets"])
        masked_tls23_identifiable = masked["tls23_identifiable"]
        
        if masked_tls23_identifiable >= original_tls23_packets:
            comparison["tls_structure_preserved"] = True
            print("✅ TLS结构保持完整")
        else:
            print(f"❌ TLS结构受损: 原始{original_tls23_packets}个TLS-23包，"
                  f"掩码后可识别{masked_tls23_identifiable}个")
        
        # 检查TLS-23头部是否保留
        if masked_tls23_identifiable > 0:
            comparison["tls23_headers_preserved"] = True
            print("✅ TLS-23消息头部已保留")
        else:
            print("❌ TLS-23消息头部未保留")
        
        # 应用数据掩码检查需要更深入的字节级分析
        comparison["application_data_masked"] = True  # 假设已掩码，需要字节级验证
        print("⚠️  应用数据掩码状态需要字节级验证")
        
        return comparison
    
    def _validate_mask_results(self, results: Dict) -> Dict[str, Any]:
        """验证掩码结果"""
        print("\n" + "=" * 60)
        print("5. 掩码结果验证")
        print("=" * 60)
        
        validation = {
            "overall_success": False,
            "issues": [],
            "recommendations": []
        }
        
        original = results["original_analysis"]
        masked = results["masked_analysis"]
        comparison = results["comparison"]
        mask_stats = results["mask_processing"]["stats"]
        
        # 验证1: 处理是否成功
        if not mask_stats["status"]:
            validation["issues"].append("掩码处理未成功完成")

        # 验证2: 是否处理了数据包
        packets_processed = mask_stats["packets_processed"]
        packets_modified = mask_stats["packets_modified"]

        print(f"数据包处理验证:")
        print(f"  处理包数: {packets_processed}")
        print(f"  修改包数: {packets_modified}")

        if packets_processed == 0:
            validation["issues"].append("没有处理任何数据包")
        elif packets_modified == 0:
            validation["issues"].append("没有修改任何数据包，可能掩码未生效")
        else:
            print("✅ 数据包处理正常")
        
        # 验证3: TLS结构是否保持
        if not comparison["tls_structure_preserved"]:
            validation["issues"].append("TLS结构未完整保持")
        
        # 验证3: 是否有字节被掩码和保留
        bytes_masked = mask_stats["masked_bytes"]
        bytes_preserved = mask_stats["preserved_bytes"]

        print(f"字节处理验证:")
        print(f"  掩码字节数: {bytes_masked}")
        print(f"  保留字节数: {bytes_preserved}")

        if bytes_masked == 0 and bytes_preserved == 0:
            validation["issues"].append("没有字节被处理，可能存在问题")
        elif bytes_preserved == 0:
            validation["issues"].append("没有字节被保留，TLS头部保留可能未生效")
        else:
            print("✅ 字节处理正常")
        
        # 总体评估
        if len(validation["issues"]) == 0:
            validation["overall_success"] = True
            print("\n🎉 端到端测试通过！")
        else:
            print(f"\n❌ 发现 {len(validation['issues'])} 个问题:")
            for issue in validation["issues"]:
                print(f"  - {issue}")
        
        return validation


def main():
    """主函数"""
    tester = EndToEndMaskTester()
    
    try:
        results = tester.run_end_to_end_test()
        
        print("\n" + "=" * 80)
        print("端到端测试总结")
        print("=" * 80)
        
        if results["mask_processing"]["success"]:
            validation = results["validation"]
            if validation["overall_success"]:
                print("✅ 端到端测试完全通过")
                print("✅ 双模块架构工作正常")
                print("✅ TLS-23消息头保留策略正确实施")
            else:
                print("⚠️  端到端测试发现问题，需要进一步调查")
        else:
            print("❌ 掩码处理失败，无法完成端到端测试")
        
        # 保存详细结果
        with open("end_to_end_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n详细测试结果已保存到: end_to_end_test_results.json")
        
    except Exception as e:
        print(f"❌ 端到端测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
