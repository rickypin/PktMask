#!/usr/bin/env python3
"""
分析GUI实际输出的pcap文件

验证GUI操作后输出的pcap文件是否真的没有掩码处理，
对比直接调用NewMaskPayloadStage的结果。
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import subprocess

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

# 配置日志
logging.basicConfig(
    level=logging.WARNING,  # 只显示警告和错误
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_gui_output_files():
    """分析GUI输出的pcap文件"""

    print("🔍 分析GUI实际输出的pcap文件")
    print("=" * 60)

    # 直接使用指定的GUI输出目录
    gui_output_dir = Path("tests/samples/tls-collector/tls-collector-Masked-20250714_143336")

    if not gui_output_dir.exists():
        print(f"❌ GUI输出目录不存在: {gui_output_dir}")
        return

    print(f"📁 分析GUI输出目录: {gui_output_dir}")

    # 分析该目录中的pcap文件
    analyze_output_directory(gui_output_dir)

def find_gui_output_directories() -> List[Path]:
    """查找GUI输出目录"""
    
    # 常见的GUI输出目录模式
    patterns = [
        "*_MaskIP_Dedup_Trim_*",
        "*_processed_*",
        "output_*",
        "result_*"
    ]
    
    output_dirs = []
    current_dir = Path(".")
    
    for pattern in patterns:
        for path in current_dir.glob(pattern):
            if path.is_dir():
                # 检查是否包含pcap文件
                pcap_files = list(path.glob("*.pcap")) + list(path.glob("*.pcapng"))
                if pcap_files:
                    output_dirs.append(path)
    
    # 按修改时间排序，最新的在前
    output_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    return output_dirs

def analyze_output_directory(output_dir: Path):
    """分析输出目录中的pcap文件"""
    
    # 查找pcap文件
    pcap_files = list(output_dir.glob("*.pcap")) + list(output_dir.glob("*.pcapng"))
    
    if not pcap_files:
        print(f"❌ 目录中没有pcap文件: {output_dir}")
        return
    
    print(f"\n📋 找到 {len(pcap_files)} 个pcap文件:")
    for pcap_file in pcap_files:
        print(f"   • {pcap_file.name}")
    
    # 分析前几个文件
    for i, pcap_file in enumerate(pcap_files[:3]):
        print(f"\n📁 [{i+1}] 分析文件: {pcap_file.name}")
        
        # 查找对应的原始文件
        original_file = find_original_file(pcap_file)
        if original_file:
            print(f"   📄 原始文件: {original_file}")
            compare_files(original_file, pcap_file)
        else:
            print(f"   ❌ 未找到对应的原始文件")
            analyze_single_gui_output(pcap_file)

def find_original_file(gui_output_file: Path) -> Optional[Path]:
    """查找GUI输出文件对应的原始文件"""

    # 移除可能的后缀
    base_name = gui_output_file.stem

    # 移除常见的处理后缀
    suffixes_to_remove = [
        "_processed", "_masked", "_output", "_result",
        "_MaskIP", "_Dedup", "_Trim", "_anonymized"
    ]

    for suffix in suffixes_to_remove:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]
            break

    # 在测试数据目录中查找
    test_dirs = [
        Path("tests/data/tls"),
        Path("tests/samples/tls-collector"),  # 添加原始文件目录
        Path("tests/data"),
        Path(".")
    ]

    for test_dir in test_dirs:
        if test_dir.exists():
            # 查找匹配的文件
            for ext in [".pcap", ".pcapng"]:
                candidate = test_dir / f"{base_name}{ext}"
                if candidate.exists():
                    return candidate

    return None

def compare_files(original_file: Path, gui_output_file: Path):
    """对比原始文件和GUI输出文件"""
    
    print(f"   🔍 对比分析:")
    
    # 基本文件信息
    orig_size = original_file.stat().st_size
    output_size = gui_output_file.stat().st_size
    
    print(f"      原始文件大小: {orig_size:,} 字节")
    print(f"      输出文件大小: {output_size:,} 字节")
    print(f"      大小变化: {((output_size - orig_size) / orig_size * 100):+.2f}%")
    
    # 使用tshark分析包数量和内容
    orig_analysis = analyze_pcap_with_tshark(original_file)
    output_analysis = analyze_pcap_with_tshark(gui_output_file)
    
    if orig_analysis and output_analysis:
        print(f"      原始包数: {orig_analysis['packet_count']}")
        print(f"      输出包数: {output_analysis['packet_count']}")
        
        if orig_analysis['tls_packets'] and output_analysis['tls_packets']:
            print(f"      原始TLS包: {len(orig_analysis['tls_packets'])}")
            print(f"      输出TLS包: {len(output_analysis['tls_packets'])}")
            
            # 检查TLS-23消息的掩码情况
            check_tls23_masking(orig_analysis['tls_packets'], output_analysis['tls_packets'])
    
    # 使用NewMaskPayloadStage直接处理原始文件进行对比
    print(f"   🎯 直接调用NewMaskPayloadStage对比:")
    direct_result = process_with_newmask_stage(original_file)
    if direct_result:
        print(f"      直接处理修改包数: {direct_result['packets_modified']}")
        print(f"      直接处理掩码字节: {direct_result['masked_bytes']}")
        
        # 对比结论
        if direct_result['packets_modified'] > 0:
            if output_analysis and len(output_analysis.get('tls_packets', [])) > 0:
                print(f"   🚨 问题确认: GUI输出文件应该有掩码但可能没有正确处理")
            else:
                print(f"   ✅ 一致: 都没有需要掩码的内容")
        else:
            print(f"   ✅ 一致: 原始文件确实没有需要掩码的内容")

def analyze_pcap_with_tshark(pcap_file: Path) -> Optional[Dict[str, Any]]:
    """使用tshark分析pcap文件"""
    
    try:
        # 获取基本包信息
        cmd_basic = [
            "tshark", "-r", str(pcap_file), "-T", "json",
            "-e", "frame.number", "-e", "tcp.payload"
        ]
        
        result_basic = subprocess.run(cmd_basic, capture_output=True, text=True, timeout=30)
        if result_basic.returncode != 0:
            return None
        
        packets = json.loads(result_basic.stdout) if result_basic.stdout.strip() else []
        
        # 获取TLS信息
        cmd_tls = [
            "tshark", "-r", str(pcap_file), "-T", "json",
            "-e", "frame.number", "-e", "tls.record.content_type", "-e", "tcp.payload"
        ]
        
        result_tls = subprocess.run(cmd_tls, capture_output=True, text=True, timeout=30)
        tls_packets = []
        if result_tls.returncode == 0 and result_tls.stdout.strip():
            tls_data = json.loads(result_tls.stdout)
            tls_packets = [p for p in tls_data if p.get("_source", {}).get("layers", {}).get("tls.record.content_type")]
        
        return {
            'packet_count': len(packets),
            'tls_packets': tls_packets
        }
        
    except Exception as e:
        print(f"      ❌ tshark分析失败: {e}")
        return None

def check_tls23_masking(orig_tls_packets: List[Dict], output_tls_packets: List[Dict]):
    """检查TLS-23消息的掩码情况"""
    
    # 统计TLS-23消息
    orig_tls23_count = 0
    output_tls23_count = 0
    
    for packet in orig_tls_packets:
        content_types = packet.get("_source", {}).get("layers", {}).get("tls.record.content_type", [])
        if not isinstance(content_types, list):
            content_types = [content_types] if content_types else []
        
        for ct in content_types:
            if str(ct) == "23":
                orig_tls23_count += 1
                break
    
    for packet in output_tls_packets:
        content_types = packet.get("_source", {}).get("layers", {}).get("tls.record.content_type", [])
        if not isinstance(content_types, list):
            content_types = [content_types] if content_types else []
        
        for ct in content_types:
            if str(ct) == "23":
                output_tls23_count += 1
                break
    
    print(f"      原始TLS-23消息: {orig_tls23_count}")
    print(f"      输出TLS-23消息: {output_tls23_count}")
    
    if orig_tls23_count > 0:
        if output_tls23_count == orig_tls23_count:
            print(f"      🚨 TLS-23消息数量未变，可能没有正确掩码")
        else:
            print(f"      ✅ TLS-23消息数量有变化，可能已掩码")

def process_with_newmask_stage(original_file: Path) -> Optional[Dict[str, Any]]:
    """使用NewMaskPayloadStage直接处理文件"""
    
    try:
        config = {
            'protocol': 'tls',
            'mode': 'enhanced',
            'marker_config': {
                'preserve': {
                    'handshake': True,
                    'application_data': False,
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                }
            },
            'masker_config': {}
        }
        
        stage = NewMaskPayloadStage(config)
        if not stage.initialize():
            return None
        
        temp_output = f"temp_direct_{original_file.stem}.pcap"
        stats = stage.process_file(str(original_file), temp_output)
        
        # 清理临时文件
        if Path(temp_output).exists():
            Path(temp_output).unlink()
        
        return {
            'packets_processed': stats.packets_processed,
            'packets_modified': stats.packets_modified,
            'masked_bytes': stats.extra_metrics.get('masked_bytes', 0),
            'preserved_bytes': stats.extra_metrics.get('preserved_bytes', 0)
        }
        
    except Exception as e:
        print(f"      ❌ 直接处理失败: {e}")
        return None

def analyze_single_gui_output(gui_output_file: Path):
    """分析单个GUI输出文件"""
    
    print(f"   📊 分析GUI输出文件:")
    
    # 基本信息
    file_size = gui_output_file.stat().st_size
    print(f"      文件大小: {file_size:,} 字节")
    
    # tshark分析
    analysis = analyze_pcap_with_tshark(gui_output_file)
    if analysis:
        print(f"      包数量: {analysis['packet_count']}")
        if analysis['tls_packets']:
            print(f"      TLS包数量: {len(analysis['tls_packets'])}")

if __name__ == "__main__":
    try:
        analyze_gui_output_files()
    except KeyboardInterrupt:
        print("\n\n⏹️  分析被用户中断")
    except Exception as e:
        print(f"\n\n❌ 分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
