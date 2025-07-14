#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask实际掩码处理效果验证脚本

验证NewMaskPayloadStage处理后输出的pcap文件中TLS消息的实际掩码效果。
严格禁止修改主程序代码，仅用于问题分析和验证。

验证要点：
1. TLS-23 ApplicationData消息体是否被零化掩码
2. TLS-20/21/22/24消息是否被完整保留
3. 对比输入输出文件，确认掩码策略的实际执行效果
4. 定位Marker模块规则生成vs Masker模块掩码应用的问题
"""

import sys
import logging
import tempfile
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('actual_masking_verification.log')
        ]
    )
    return logging.getLogger(__name__)

def analyze_tls_messages_in_pcap(pcap_file: Path) -> List[Dict]:
    """分析pcap文件中的TLS消息"""
    logger.info(f"分析TLS消息: {pcap_file.name}")
    
    try:
        # 使用tshark提取TLS消息信息
        cmd = [
            'tshark', '-r', str(pcap_file),
            '-Y', 'tls',
            '-T', 'json',
            '-e', 'frame.number',
            '-e', 'tcp.stream',
            '-e', 'tcp.seq_raw',
            '-e', 'tcp.len',
            '-e', 'tls.record.content_type',
            '-e', 'tls.record.length',
            '-e', 'tls.handshake.type',
            '-e', 'tcp.payload'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"tshark执行失败: {result.stderr}")
            return []
        
        if not result.stdout.strip():
            logger.warning("未找到TLS消息")
            return []
        
        tls_messages = json.loads(result.stdout)
        logger.info(f"找到 {len(tls_messages)} 个TLS消息包")
        
        return tls_messages
        
    except Exception as e:
        logger.error(f"分析TLS消息时发生异常: {e}")
        return []

def extract_tcp_payload_hex(pcap_file: Path, frame_number: int) -> Optional[str]:
    """提取指定帧的TCP载荷十六进制数据"""
    try:
        cmd = [
            'tshark', '-r', str(pcap_file),
            '-Y', f'frame.number == {frame_number}',
            '-T', 'fields',
            '-e', 'tcp.payload'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().replace(':', '')
        return None
        
    except Exception as e:
        logger.error(f"提取TCP载荷时发生异常: {e}")
        return None

def analyze_tls_message_masking(original_payload: str, masked_payload: str, tls_type: str) -> Dict:
    """分析TLS消息的掩码效果"""
    if not original_payload or not masked_payload:
        return {"error": "载荷数据缺失"}
    
    # 转换为字节数组进行比较
    try:
        orig_bytes = bytes.fromhex(original_payload)
        mask_bytes = bytes.fromhex(masked_payload)
    except ValueError as e:
        return {"error": f"十六进制转换失败: {e}"}
    
    if len(orig_bytes) != len(mask_bytes):
        return {"error": f"载荷长度不匹配: 原始{len(orig_bytes)} vs 掩码{len(mask_bytes)}"}
    
    # 分析掩码效果
    total_bytes = len(orig_bytes)
    changed_bytes = sum(1 for i in range(total_bytes) if orig_bytes[i] != mask_bytes[i])
    unchanged_bytes = total_bytes - changed_bytes
    
    # 检查是否有零化掩码
    zero_bytes = sum(1 for b in mask_bytes if b == 0)
    
    # 分析TLS记录结构
    tls_analysis = analyze_tls_record_structure(orig_bytes, mask_bytes)
    
    return {
        "tls_type": tls_type,
        "total_bytes": total_bytes,
        "changed_bytes": changed_bytes,
        "unchanged_bytes": unchanged_bytes,
        "zero_bytes": zero_bytes,
        "change_ratio": changed_bytes / total_bytes if total_bytes > 0 else 0,
        "zero_ratio": zero_bytes / total_bytes if total_bytes > 0 else 0,
        "tls_structure": tls_analysis
    }

def analyze_tls_record_structure(orig_bytes: bytes, mask_bytes: bytes) -> Dict:
    """分析TLS记录结构的掩码效果"""
    if len(orig_bytes) < 5:
        return {"error": "TLS记录太短"}
    
    # TLS记录头部 (5字节): Type(1) + Version(2) + Length(2)
    header_orig = orig_bytes[:5]
    header_mask = mask_bytes[:5]
    header_preserved = header_orig == header_mask
    
    # TLS记录体
    body_orig = orig_bytes[5:]
    body_mask = mask_bytes[5:]
    
    if len(body_orig) > 0:
        body_changed = sum(1 for i in range(len(body_orig)) if body_orig[i] != body_mask[i])
        body_zero = sum(1 for b in body_mask if b == 0)
        body_analysis = {
            "length": len(body_orig),
            "changed_bytes": body_changed,
            "zero_bytes": body_zero,
            "change_ratio": body_changed / len(body_orig),
            "zero_ratio": body_zero / len(body_orig)
        }
    else:
        body_analysis = {"length": 0}
    
    return {
        "header_preserved": header_preserved,
        "header_bytes": header_orig.hex(),
        "body_analysis": body_analysis
    }

def process_single_file(test_file: Path) -> Dict:
    """处理单个测试文件并分析掩码效果"""
    logger.info(f"=== 处理文件: {test_file.name} ===")
    
    # 创建临时输出文件
    with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
        output_file = Path(tmp.name)
    
    try:
        # 使用NewMaskPayloadStage处理文件
        from pktmask.core.pipeline.executor import PipelineExecutor
        from pktmask.services import build_pipeline_config
        
        config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False,
            enable_mask=True
        )
        
        executor = PipelineExecutor(config)
        result = executor.run(str(test_file), str(output_file))
        
        if not result.success:
            return {"error": f"处理失败: {result.errors}"}
        
        # 分析原始文件的TLS消息
        original_tls = analyze_tls_messages_in_pcap(test_file)
        if not original_tls:
            return {"error": "原始文件中未找到TLS消息"}
        
        # 分析输出文件的TLS消息
        masked_tls = analyze_tls_messages_in_pcap(output_file)
        if not masked_tls:
            return {"error": "输出文件中未找到TLS消息"}
        
        # 对比分析
        comparison_results = []
        
        for i, (orig_msg, mask_msg) in enumerate(zip(original_tls, masked_tls)):
            frame_num = orig_msg['_source']['layers'].get('frame.number', ['unknown'])[0]
            tls_type = orig_msg['_source']['layers'].get('tls.record.content_type', ['unknown'])[0]
            
            # 提取TCP载荷
            orig_payload = extract_tcp_payload_hex(test_file, int(frame_num))
            mask_payload = extract_tcp_payload_hex(output_file, int(frame_num))
            
            if orig_payload and mask_payload:
                analysis = analyze_tls_message_masking(orig_payload, mask_payload, tls_type)
                analysis['frame_number'] = frame_num
                comparison_results.append(analysis)
        
        # 统计分析
        stats = analyze_masking_statistics(comparison_results)
        
        return {
            "file": test_file.name,
            "processing_success": True,
            "stage_stats": {
                "packets_processed": result.stage_stats[0].packets_processed if result.stage_stats else 0,
                "packets_modified": result.stage_stats[0].packets_modified if result.stage_stats else 0
            },
            "tls_message_count": len(comparison_results),
            "message_analysis": comparison_results,
            "overall_stats": stats
        }
        
    except Exception as e:
        logger.error(f"处理文件 {test_file.name} 时发生异常: {e}")
        return {"error": str(e)}
    
    finally:
        if output_file.exists():
            output_file.unlink()

def analyze_masking_statistics(comparison_results: List[Dict]) -> Dict:
    """分析掩码统计信息"""
    if not comparison_results:
        return {}
    
    # 按TLS类型分组统计
    type_stats = {}
    total_messages = len(comparison_results)
    total_changed = 0
    total_zero_masked = 0
    
    for result in comparison_results:
        if "error" in result:
            continue
            
        tls_type = result.get("tls_type", "unknown")
        if tls_type not in type_stats:
            type_stats[tls_type] = {
                "count": 0,
                "total_bytes": 0,
                "changed_bytes": 0,
                "zero_bytes": 0
            }
        
        stats = type_stats[tls_type]
        stats["count"] += 1
        stats["total_bytes"] += result.get("total_bytes", 0)
        stats["changed_bytes"] += result.get("changed_bytes", 0)
        stats["zero_bytes"] += result.get("zero_bytes", 0)
        
        if result.get("changed_bytes", 0) > 0:
            total_changed += 1
        if result.get("zero_bytes", 0) > 0:
            total_zero_masked += 1
    
    # 计算比例
    for tls_type, stats in type_stats.items():
        if stats["total_bytes"] > 0:
            stats["change_ratio"] = stats["changed_bytes"] / stats["total_bytes"]
            stats["zero_ratio"] = stats["zero_bytes"] / stats["total_bytes"]
    
    return {
        "total_messages": total_messages,
        "messages_with_changes": total_changed,
        "messages_with_zero_masking": total_zero_masked,
        "type_breakdown": type_stats
    }

def main():
    """主验证流程"""
    global logger
    logger = setup_logging()
    
    logger.info("开始PktMask实际掩码处理效果验证")
    
    # 测试文件列表
    test_files = [
        "tls_1_2_plainip.pcap",
        "tls_1_3_0-RTT-2_22_23_mix.pcap",
        "ssl_3.pcap",
        "tls_1_2_double_vlan.pcap"
    ]
    
    test_data_dir = project_root / "tests" / "data" / "tls"
    
    results = {}
    
    for filename in test_files:
        test_file = test_data_dir / filename
        if test_file.exists():
            logger.info(f"\n{'='*60}")
            results[filename] = process_single_file(test_file)
        else:
            logger.warning(f"测试文件不存在: {test_file}")
            results[filename] = {"error": "文件不存在"}
    
    # 汇总分析
    logger.info(f"\n{'='*60}")
    logger.info("实际掩码效果验证结果汇总")
    logger.info('='*60)
    
    for filename, result in results.items():
        logger.info(f"\n📁 文件: {filename}")
        
        if "error" in result:
            logger.error(f"❌ 处理失败: {result['error']}")
            continue
        
        logger.info(f"✅ 处理成功")
        logger.info(f"   - 处理包数: {result['stage_stats']['packets_processed']}")
        logger.info(f"   - 修改包数: {result['stage_stats']['packets_modified']}")
        logger.info(f"   - TLS消息数: {result['tls_message_count']}")
        
        stats = result.get('overall_stats', {})
        if stats:
            logger.info(f"   - 有变化的消息: {stats.get('messages_with_changes', 0)}")
            logger.info(f"   - 零化掩码的消息: {stats.get('messages_with_zero_masking', 0)}")
            
            # 按TLS类型显示统计
            type_breakdown = stats.get('type_breakdown', {})
            for tls_type, type_stats in type_breakdown.items():
                logger.info(f"   - TLS-{tls_type}: {type_stats['count']}条消息, "
                          f"变化率{type_stats.get('change_ratio', 0):.2%}, "
                          f"零化率{type_stats.get('zero_ratio', 0):.2%}")
    
    # 验证结论
    logger.info(f"\n{'='*60}")
    logger.info("验证结论")
    logger.info('='*60)
    
    success_count = sum(1 for r in results.values() if "error" not in r)
    total_count = len(results)
    
    logger.info(f"成功处理: {success_count}/{total_count} 文件")
    
    # 检查TLS-23掩码效果
    tls23_properly_masked = 0
    tls23_total = 0
    
    for filename, result in results.items():
        if "error" in result:
            continue
        
        type_breakdown = result.get('overall_stats', {}).get('type_breakdown', {})
        if '23' in type_breakdown:  # TLS-23 ApplicationData
            tls23_total += 1
            tls23_stats = type_breakdown['23']
            if tls23_stats.get('zero_ratio', 0) > 0:
                tls23_properly_masked += 1
                logger.info(f"✅ {filename}: TLS-23消息正确掩码 (零化率: {tls23_stats['zero_ratio']:.2%})")
            else:
                logger.warning(f"⚠️ {filename}: TLS-23消息未被掩码")
    
    if tls23_total > 0:
        logger.info(f"\nTLS-23掩码效果: {tls23_properly_masked}/{tls23_total} 文件正确处理")
        
        if tls23_properly_masked == tls23_total:
            logger.info("🎉 所有TLS-23 ApplicationData消息都被正确掩码！")
        else:
            logger.error("❌ 部分TLS-23 ApplicationData消息未被正确掩码，需要进一步分析")
    else:
        logger.warning("⚠️ 未找到TLS-23 ApplicationData消息进行验证")

if __name__ == "__main__":
    main()
