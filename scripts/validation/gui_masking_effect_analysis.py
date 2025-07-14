#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI掩码效果深度分析脚本

对比GUI调用和直接调用的实际掩码效果，
分析输出文件的具体差异，验证掩码规则是否正确应用。
"""

import sys
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def setup_logging():
    """设置详细日志记录"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('gui_masking_effect_analysis.log', mode='w', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

def analyze_pcap_with_tshark(pcap_file: Path, logger: logging.Logger) -> List[Dict]:
    """使用tshark分析pcap文件的TLS消息"""
    logger.debug(f"分析pcap文件: {pcap_file}")
    
    try:
        # 使用tshark提取TLS消息信息
        cmd = [
            'tshark', '-r', str(pcap_file), '-T', 'json',
            '-Y', 'tls',
            '-e', 'frame.number',
            '-e', 'tcp.stream',
            '-e', 'tcp.seq_raw',
            '-e', 'tcp.len',
            '-e', 'tls.record.content_type',
            '-e', 'tls.record.length',
            '-e', 'tcp.payload'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"tshark执行失败: {result.stderr}")
            return []
        
        if not result.stdout.strip():
            logger.warning("tshark未返回任何数据")
            return []
        
        packets = json.loads(result.stdout)
        logger.debug(f"解析到 {len(packets)} 个TLS数据包")
        
        return packets
        
    except Exception as e:
        logger.error(f"分析pcap文件失败: {e}")
        return []

def extract_tcp_payload_hex(pcap_file: Path, frame_number: int, logger: logging.Logger) -> str:
    """提取指定帧的TCP载荷十六进制数据"""
    try:
        cmd = [
            'tshark', '-r', str(pcap_file),
            '-Y', f'frame.number == {frame_number}',
            '-T', 'fields', '-e', 'tcp.payload'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().replace(':', '')
        else:
            return ""
            
    except Exception as e:
        logger.warning(f"提取帧{frame_number}载荷失败: {e}")
        return ""

def compare_tcp_payloads(original_file: Path, gui_file: Path, direct_file: Path, logger: logging.Logger) -> Dict[str, Any]:
    """对比三个文件的TCP载荷差异"""
    logger.info("=== 对比TCP载荷差异 ===")
    
    # 分析原始文件
    original_packets = analyze_pcap_with_tshark(original_file, logger)
    gui_packets = analyze_pcap_with_tshark(gui_file, logger)
    direct_packets = analyze_pcap_with_tshark(direct_file, logger)
    
    logger.debug(f"原始文件: {len(original_packets)} 个TLS包")
    logger.debug(f"GUI处理: {len(gui_packets)} 个TLS包")
    logger.debug(f"直接调用: {len(direct_packets)} 个TLS包")
    
    comparison = {
        "packet_counts": {
            "original": len(original_packets),
            "gui": len(gui_packets),
            "direct": len(direct_packets)
        },
        "payload_differences": [],
        "tls_message_analysis": {
            "original": {},
            "gui": {},
            "direct": {}
        }
    }
    
    # 对比每个TLS数据包的载荷
    for i, orig_pkt in enumerate(original_packets):
        if i >= len(gui_packets) or i >= len(direct_packets):
            break
            
        frame_num = orig_pkt.get('_source', {}).get('layers', {}).get('frame.number', [''])[0]
        if not frame_num:
            continue
            
        frame_num = int(frame_num)
        
        # 提取载荷
        orig_payload = extract_tcp_payload_hex(original_file, frame_num, logger)
        gui_payload = extract_tcp_payload_hex(gui_file, frame_num, logger)
        direct_payload = extract_tcp_payload_hex(direct_file, frame_num, logger)
        
        if orig_payload and (gui_payload != direct_payload):
            comparison["payload_differences"].append({
                "frame_number": frame_num,
                "original_length": len(orig_payload) // 2,
                "gui_length": len(gui_payload) // 2,
                "direct_length": len(direct_payload) // 2,
                "gui_matches_direct": gui_payload == direct_payload,
                "original_payload_preview": orig_payload[:100] + "..." if len(orig_payload) > 100 else orig_payload,
                "gui_payload_preview": gui_payload[:100] + "..." if len(gui_payload) > 100 else gui_payload,
                "direct_payload_preview": direct_payload[:100] + "..." if len(direct_payload) > 100 else direct_payload
            })
    
    return comparison

def run_gui_processing(test_file: Path, logger: logging.Logger) -> Tuple[bool, Path]:
    """运行GUI处理流程"""
    logger.debug("执行GUI处理流程")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        # 构建GUI配置
        gui_config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False,
            enable_mask=True
        )
        
        # 创建执行器
        executor = create_pipeline_executor(gui_config)
        
        # 创建输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        # 执行处理
        result = executor.run(str(test_file), str(output_file))
        
        return result.success, output_file
        
    except Exception as e:
        logger.error(f"GUI处理失败: {e}")
        return False, None

def run_direct_processing(test_file: Path, logger: logging.Logger) -> Tuple[bool, Path]:
    """运行直接处理流程"""
    logger.debug("执行直接处理流程")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 直接配置
        direct_config = {
            "enabled": True,
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "tls": {
                    "preserve_handshake": True,
                    "preserve_application_data": False
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
        
        # 创建Stage
        stage = NewMaskPayloadStage(direct_config)
        stage.initialize()
        
        # 创建输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        # 执行处理
        stats = stage.process_file(str(test_file), str(output_file))
        
        return True, output_file
        
    except Exception as e:
        logger.error(f"直接处理失败: {e}")
        return False, None

def main():
    """主函数"""
    logger = setup_logging()
    logger.info("开始GUI掩码效果深度分析")
    
    # 使用测试文件
    test_file = Path("tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap")
    if not test_file.exists():
        logger.error(f"测试文件不存在: {test_file}")
        return False
    
    logger.info(f"使用测试文件: {test_file}")
    
    try:
        # 执行GUI处理
        logger.info("=== 执行GUI处理 ===")
        gui_success, gui_output = run_gui_processing(test_file, logger)
        if not gui_success or not gui_output:
            logger.error("GUI处理失败")
            return False
        
        # 执行直接处理
        logger.info("=== 执行直接处理 ===")
        direct_success, direct_output = run_direct_processing(test_file, logger)
        if not direct_success or not direct_output:
            logger.error("直接处理失败")
            return False
        
        # 对比载荷差异
        logger.info("=== 对比载荷差异 ===")
        comparison = compare_tcp_payloads(test_file, gui_output, direct_output, logger)
        
        # 分析结果
        logger.info("=== 分析结果 ===")
        
        if comparison["payload_differences"]:
            logger.warning(f"发现 {len(comparison['payload_differences'])} 个载荷差异:")
            for diff in comparison["payload_differences"]:
                logger.warning(f"  帧 {diff['frame_number']}: GUI长度={diff['gui_length']}, 直接长度={diff['direct_length']}")
        else:
            logger.info("未发现载荷差异 - GUI和直接调用结果一致")
        
        # 保存详细分析结果
        analysis_file = Path("gui_masking_effect_analysis.json")
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump({
                "test_file": str(test_file),
                "gui_output": str(gui_output),
                "direct_output": str(direct_output),
                "comparison": comparison
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"详细分析结果已保存到: {analysis_file}")
        
        # 清理临时文件
        try:
            gui_output.unlink()
            direct_output.unlink()
        except:
            pass
        
        return len(comparison["payload_differences"]) == 0
        
    except Exception as e:
        logger.error(f"分析过程失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
