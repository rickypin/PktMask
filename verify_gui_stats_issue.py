#!/usr/bin/env python3
"""
验证GUI统计信息显示问题

分析GUI显示"masked 0 pkts"与实际掩码处理结果不符的根本原因。
重点检查统计信息转换和传递过程。
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 减少日志噪音
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_gui_stats_issue():
    """验证GUI统计信息显示问题"""
    
    print("🔍 验证GUI统计信息显示问题")
    print("=" * 50)
    
    # 测试文件（从GUI日志中选择的"问题"文件）
    test_files = [
        "tests/data/tls/tls_1_2_plainip.pcap",
        "tests/data/tls/ssl_3.pcap"
    ]
    
    # 创建标准配置
    config = {
        'protocol': 'tls',
        'mode': 'enhanced',
        'marker_config': {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 只保留头部
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        },
        'masker_config': {}
    }
    
    print(f"📋 测试配置:")
    print(f"   协议: {config['protocol']}")
    print(f"   模式: {config['mode']}")
    print(f"   TLS-23保留策略: {'完全保留' if config['marker_config']['preserve']['application_data'] else '仅头部'}")
    print()
    
    for i, filename in enumerate(test_files):
        if not Path(filename).exists():
            print(f"❌ 文件不存在: {filename}")
            continue
            
        print(f"📁 [{i+1}] 验证文件: {filename}")
        result = analyze_stats_conversion(filename, config)
        print_verification_result(result)
        print()

def analyze_stats_conversion(filename: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """分析统计信息转换过程"""
    
    result = {
        'filename': filename,
        'stage_creation': {},
        'processing_result': {},
        'stats_conversion': {},
        'potential_issues': []
    }
    
    try:
        print("   🔧 步骤1: 创建NewMaskPayloadStage...")
        
        # 创建NewMaskPayloadStage实例
        stage = NewMaskPayloadStage(config)
        
        result['stage_creation'] = {
            'success': True,
            'protocol': stage.protocol,
            'mode': stage.mode,
            'marker_type': type(stage.marker).__name__,
            'masker_type': type(stage.masker).__name__
        }
        
        print(f"      ✓ Stage创建成功: {stage.protocol}/{stage.mode}")
        print(f"      ✓ Marker: {result['stage_creation']['marker_type']}")
        print(f"      ✓ Masker: {result['stage_creation']['masker_type']}")
        
        # 初始化
        print("   🚀 步骤2: 初始化Stage...")
        if not stage.initialize():
            result['potential_issues'].append("Stage初始化失败")
            return result
        
        print("      ✓ Stage初始化成功")
        
        # 创建临时输出文件
        output_file = f"temp_verify_{Path(filename).stem}.pcap"
        
        print("   📊 步骤3: 处理文件并分析统计信息...")
        
        # 处理文件
        stage_stats = stage.process_file(filename, output_file)
        
        result['processing_result'] = {
            'stage_name': stage_stats.stage_name,
            'packets_processed': stage_stats.packets_processed,
            'packets_modified': stage_stats.packets_modified,
            'duration_ms': stage_stats.duration_ms,
            'extra_metrics': stage_stats.extra_metrics
        }
        
        print(f"      ✓ Stage统计: 处理{stage_stats.packets_processed}包, 修改{stage_stats.packets_modified}包")
        
        # 分析extra_metrics中的详细信息
        extra = stage_stats.extra_metrics
        result['stats_conversion'] = {
            'masked_bytes': extra.get('masked_bytes', 0),
            'preserved_bytes': extra.get('preserved_bytes', 0),
            'masking_ratio': extra.get('masking_ratio', 0),
            'preservation_ratio': extra.get('preservation_ratio', 0),
            'success': extra.get('success', False),
            'errors': extra.get('errors', []),
            'warnings': extra.get('warnings', [])
        }
        
        print(f"      ✓ 掩码字节: {result['stats_conversion']['masked_bytes']}")
        print(f"      ✓ 保留字节: {result['stats_conversion']['preserved_bytes']}")
        print(f"      ✓ 掩码比例: {result['stats_conversion']['masking_ratio']:.2%}")
        
        # 检查潜在问题
        if stage_stats.packets_modified == 0:
            if result['stats_conversion']['masked_bytes'] > 0:
                result['potential_issues'].append("packets_modified为0但masked_bytes>0，统计不一致")
            else:
                result['potential_issues'].append("确实没有任何掩码操作")
        
        if result['stats_conversion']['errors']:
            result['potential_issues'].extend([f"错误: {err}" for err in result['stats_conversion']['errors']])
        
        if result['stats_conversion']['warnings']:
            result['potential_issues'].extend([f"警告: {warn}" for warn in result['stats_conversion']['warnings']])
        
        # 验证输出文件
        print("   📄 步骤4: 验证输出文件...")
        if Path(output_file).exists():
            output_size = Path(output_file).stat().st_size
            input_size = Path(filename).stat().st_size
            
            result['file_verification'] = {
                'output_exists': True,
                'input_size': input_size,
                'output_size': output_size,
                'size_ratio': output_size / input_size if input_size > 0 else 0
            }
            
            print(f"      ✓ 输出文件存在: {output_size} 字节 (输入: {input_size} 字节)")
            
            # 清理临时文件
            Path(output_file).unlink()
        else:
            result['file_verification'] = {'output_exists': False}
            result['potential_issues'].append("输出文件不存在")
        
        return result
        
    except Exception as e:
        result['error'] = str(e)
        result['potential_issues'].append(f"处理异常: {e}")
        return result

def print_verification_result(result: Dict[str, Any]):
    """打印验证结果"""
    
    if 'error' in result:
        print(f"   ❌ 验证失败: {result['error']}")
        return
    
    # Stage创建结果
    creation = result['stage_creation']
    if creation['success']:
        print(f"   ✅ Stage创建: 成功")
    else:
        print(f"   ❌ Stage创建: 失败")
    
    # 处理结果
    processing = result['processing_result']
    print(f"   📊 处理结果:")
    print(f"      - 处理包数: {processing['packets_processed']}")
    print(f"      - 修改包数: {processing['packets_modified']}")
    print(f"      - 处理时间: {processing['duration_ms']:.1f}ms")
    
    # 统计转换结果
    stats = result['stats_conversion']
    print(f"   🔢 详细统计:")
    print(f"      - 掩码字节: {stats['masked_bytes']}")
    print(f"      - 保留字节: {stats['preserved_bytes']}")
    print(f"      - 掩码比例: {stats['masking_ratio']:.2%}")
    print(f"      - 处理成功: {stats['success']}")
    
    # 文件验证结果
    if 'file_verification' in result:
        file_verify = result['file_verification']
        if file_verify['output_exists']:
            print(f"   📄 文件验证: 输出文件正常 (大小比例: {file_verify['size_ratio']:.2%})")
        else:
            print(f"   📄 文件验证: 输出文件缺失")
    
    # 潜在问题
    issues = result['potential_issues']
    if issues:
        print(f"   🚨 潜在问题:")
        for issue in issues:
            print(f"      • {issue}")
    else:
        print(f"   ✅ 无明显问题")
    
    # 结论
    processing_result = result['processing_result']
    if processing_result['packets_modified'] > 0:
        print(f"   🎯 结论: 双模块架构工作正常，有{processing_result['packets_modified']}个包被掩码")
    else:
        print(f"   🎯 结论: 确实没有包被掩码，需要进一步分析原因")

if __name__ == "__main__":
    try:
        verify_gui_stats_issue()
    except KeyboardInterrupt:
        print("\n\n⏹️  验证被用户中断")
    except Exception as e:
        print(f"\n\n❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
