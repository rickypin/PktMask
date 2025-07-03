#!/usr/bin/env python3
"""
跨包TLS-23掩码问题调试脚本

专门分析用户报告的三个样本文件：
1. tls_1_2_single_vlan.pcap
2. ssl_3.pcapng  
3. tls_1_0_multi_segment_google-https.pcap

问题特征：分拆到多个数据包的TLS-23消息体没有被正确全部打掩码
"""

import sys
import os
from pathlib import Path
import subprocess
import json
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, '/Users/ricky/Downloads/PktMask/src')


class CrossPacketTLS23Debugger:
    """跨包TLS-23掩码调试器"""
    
    def __init__(self):
        self.test_files = [
            "tests/data/tls/tls_1_2_single_vlan.pcap",
            "tests/data/tls/ssl_3.pcapng", 
            "tests/data/tls/tls_1_0_multi_segment_google-https.pcap"
        ]
        self.output_dir = Path("tmp/cross_packet_debug")
        self.output_dir.mkdir(exist_ok=True)
        
    def debug_all_samples(self):
        """调试所有样本文件"""
        print("🔍 开始调试跨包TLS-23掩码问题")
        print("=" * 80)
        
        for test_file in self.test_files:
            file_path = Path(test_file)
            if file_path.exists():
                print(f"\n📁 调试文件: {file_path.name}")
                self.debug_single_file(file_path)
            else:
                print(f"❌ 文件不存在: {file_path}")
                
    def debug_single_file(self, file_path: Path):
        """调试单个文件的跨包TLS-23问题"""
        print(f"\n🚀 开始分析: {file_path.name}")
        
        # 1. 分析原始文件的TLS-23记录分布
        print("📊 Step 1: 分析原始TLS-23记录分布")
        orig_stats = self.analyze_tls23_distribution(file_path, is_masked=False)
        
        # 2. 执行掩码处理
        print("🎭 Step 2: 执行TLS掩码处理") 
        masked_file = self.process_with_mask_stage(file_path)
        
        if masked_file and masked_file.exists():
            # 3. 分析掩码后的TLS-23记录分布
            print("📊 Step 3: 分析掩码后TLS-23记录分布")
            masked_stats = self.analyze_tls23_distribution(masked_file, is_masked=True)
            
            # 4. 对比分析
            print("📈 Step 4: 对比分析掩码效果")
            self.compare_masking_results(file_path.name, orig_stats, masked_stats)
        else:
            print("❌ 掩码处理失败，无法进行后续分析")
            
    def analyze_tls23_distribution(self, file_path: Path, is_masked: bool = False) -> Dict[str, Any]:
        """分析TLS-23记录在各包中的分布"""
        suffix = "masked" if is_masked else "orig"
        json_file = self.output_dir / f"{file_path.stem}_{suffix}_tls23_analysis.json"
        
        # 使用tshark提取TLS-23记录信息
        cmd = [
            "tshark", "-r", str(file_path), 
            "-T", "json",
            "-Y", "tls.record.content_type == 23",
            "-e", "frame.number",
            "-e", "tcp.stream", 
            "-e", "tcp.seq",
            "-e", "tcp.len",
            "-e", "tls.record.length",
            "-e", "tcp.reassembled_in",
            "-e", "tls.reassembled_in"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                tls23_data = json.loads(result.stdout) if result.stdout.strip() else []
                
                # 统计分析
                stats = {
                    "total_tls23_packets": len(tls23_data),
                    "packets": [],
                    "cross_packet_candidates": [],
                    "tcp_streams": set()
                }
                
                for packet in tls23_data:
                    source = packet.get("_source", {})
                    layers = source.get("layers", {})
                    
                    frame_num = int(layers.get("frame.number", [0])[0])
                    tcp_stream = layers.get("tcp.stream", [None])[0]
                    tcp_seq = int(layers.get("tcp.seq", [0])[0])
                    tcp_len = int(layers.get("tcp.len", [0])[0])
                    tls_record_lengths = layers.get("tls.record.length", [])
                    tcp_reassembled_in = layers.get("tcp.reassembled_in", [])
                    tls_reassembled_in = layers.get("tls.reassembled_in", [])
                    
                    # 计算TLS记录总长度
                    total_tls_length = sum(int(length, 16) if isinstance(length, str) else int(length) 
                                         for length in tls_record_lengths)
                    
                    packet_info = {
                        "frame": frame_num,
                        "tcp_stream": tcp_stream,
                        "tcp_seq": tcp_seq,
                        "tcp_len": tcp_len,
                        "tls_record_lengths": tls_record_lengths,
                        "total_tls_length": total_tls_length,
                        "tcp_reassembled_in": tcp_reassembled_in,
                        "tls_reassembled_in": tls_reassembled_in,
                        "has_tcp_reassembly": len(tcp_reassembled_in) > 0,
                        "has_tls_reassembly": len(tls_reassembled_in) > 0,
                        "potential_cross_packet": total_tls_length > tcp_len or len(tcp_reassembled_in) > 0
                    }
                    
                    stats["packets"].append(packet_info)
                    stats["tcp_streams"].add(tcp_stream)
                    
                    # 检测跨包候选
                    if packet_info["potential_cross_packet"] or packet_info["has_tcp_reassembly"] or packet_info["has_tls_reassembly"]:
                        stats["cross_packet_candidates"].append(packet_info)
                
                stats["tcp_streams"] = list(stats["tcp_streams"])
                
                # 保存分析结果
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
                
                print(f"  📋 TLS-23包数: {stats['total_tls23_packets']}")
                print(f"  🌊 TCP流数: {len(stats['tcp_streams'])}")
                print(f"  🔗 跨包候选: {len(stats['cross_packet_candidates'])}")
                
                return stats
                
            else:
                print(f"  ❌ tshark分析失败: {result.stderr}")
                return {}
                
        except Exception as e:
            print(f"  ❌ 分析异常: {e}")
            return {}
            
    def process_with_mask_stage(self, file_path: Path) -> Path:
        """使用CLI命令处理文件"""
        output_file = self.output_dir / f"{file_path.stem}_masked{file_path.suffix}"
        
        try:
            # 使用CLI命令处理
            cmd = [
                "python", "-m", "pktmask.cli", 
                "--input-file", str(file_path),
                "--output-file", str(output_file),
                "--operation", "mask-payloads",
                "--processor", "tshark-enhanced-mask"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd="src")
            
            if result.returncode == 0 and output_file.exists():
                print(f"  ✅ 掩码处理成功: {output_file.name}")
                print(f"  📋 CLI输出: {result.stdout}")
                return output_file
            else:
                print(f"  ❌ 掩码处理失败")
                print(f"  📋 错误输出: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"  ❌ 处理异常: {e}")
            return None
            
    def compare_masking_results(self, filename: str, orig_stats: Dict, masked_stats: Dict):
        """对比原始和掩码后的结果"""
        print(f"\n📈 {filename} 掩码效果分析:")
        print("-" * 60)
        
        orig_count = orig_stats.get("total_tls23_packets", 0)
        masked_count = masked_stats.get("total_tls23_packets", 0)
        
        print(f"TLS-23包数变化: {orig_count} → {masked_count}")
        
        if orig_count != masked_count:
            print("⚠️  包数不一致！可能存在跨包重组问题")
            
        # 分析跨包候选的掩码情况
        orig_cross = orig_stats.get("cross_packet_candidates", [])
        masked_cross = masked_stats.get("cross_packet_candidates", [])
        
        print(f"跨包候选变化: {len(orig_cross)} → {len(masked_cross)}")
        
        if len(orig_cross) > 0:
            print("\n🔍 跨包TLS-23记录详细分析:")
            for candidate in orig_cross:
                frame = candidate["frame"]
                tcp_len = candidate["tcp_len"]
                total_tls = candidate["total_tls_length"]
                print(f"  包{frame}: TCP长度={tcp_len}, TLS总长度={total_tls}, 差异={total_tls - tcp_len}")
                
                # 查找对应的掩码后包
                masked_packet = None
                for p in masked_stats.get("packets", []):
                    if p["frame"] == frame:
                        masked_packet = p
                        break
                        
                if masked_packet:
                    masked_tcp_len = masked_packet["tcp_len"]
                    masked_tls_len = masked_packet["total_tls_length"]
                    print(f"    掩码后: TCP长度={masked_tcp_len}, TLS总长度={masked_tls_len}")
                    
                    if tcp_len != masked_tcp_len:
                        print(f"    ⚠️  TCP长度变化，可能存在掩码问题")
                else:
                    print(f"    ❌ 掩码后未找到对应包，可能被删除或重组")
                    
        # 生成问题总结
        self.generate_problem_summary(filename, orig_stats, masked_stats)
        
    def generate_problem_summary(self, filename: str, orig_stats: Dict, masked_stats: Dict):
        """生成问题总结报告"""
        summary_file = self.output_dir / f"{filename}_problem_summary.md"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"# {filename} 跨包TLS-23掩码问题分析报告\n\n")
            
            f.write("## 基本统计\n")
            f.write(f"- 原始TLS-23包数: {orig_stats.get('total_tls23_packets', 0)}\n")
            f.write(f"- 掩码后TLS-23包数: {masked_stats.get('total_tls23_packets', 0)}\n")
            f.write(f"- 原始跨包候选: {len(orig_stats.get('cross_packet_candidates', []))}\n")
            f.write(f"- 掩码后跨包候选: {len(masked_stats.get('cross_packet_candidates', []))}\n\n")
            
            f.write("## 问题识别\n")
            
            # 识别具体问题
            orig_cross = orig_stats.get("cross_packet_candidates", [])
            if len(orig_cross) > 0:
                f.write("### 检测到的跨包TLS-23记录:\n")
                for candidate in orig_cross:
                    frame = candidate["frame"]
                    tcp_len = candidate["tcp_len"]
                    total_tls = candidate["total_tls_length"]
                    f.write(f"- 包{frame}: TLS记录总长度({total_tls}) > TCP载荷长度({tcp_len})\n")
                    f.write(f"  - 可能需要{(total_tls + tcp_len - 1) // tcp_len}个TCP段来传输\n")
                    f.write(f"  - 超出长度: {total_tls - tcp_len}字节\n")
                    
            f.write("\n## 建议修复方案\n")
            f.write("1. 检查TSharkTLSAnalyzer._detect_cross_packet_in_stream方法\n")
            f.write("2. 验证TLSMaskRuleGenerator对跨包分段的掩码规则生成\n")
            f.write("3. 确认ScapyMaskApplier正确应用跨包掩码规则\n")
            
        print(f"  📄 问题总结已保存: {summary_file.name}")


def main():
    """主函数"""
    print("🔍 跨包TLS-23掩码问题调试器")
    print("目标文件:")
    print("  1. tls_1_2_single_vlan.pcap")
    print("  2. ssl_3.pcapng")
    print("  3. tls_1_0_multi_segment_google-https.pcap")
    print()
    
    debugger = CrossPacketTLS23Debugger()
    debugger.debug_all_samples()
    
    print("\n✅ 调试完成！")
    print(f"📂 结果保存在: {debugger.output_dir}")


if __name__ == "__main__":
    main() 