#!/usr/bin/env python3
"""
调试GUI配置传递流程

追踪从GUI复选框到NewMaskPayloadStage的完整配置传递过程，
找出配置不匹配导致掩码失效的根本原因。
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_gui_config_flow():
    """调试GUI配置传递流程"""
    
    print("🔍 调试GUI配置传递流程")
    print("=" * 60)
    
    # 步骤1: 模拟GUI复选框状态
    print("📋 步骤1: 模拟GUI复选框状态")
    mask_ip_checked = False
    dedup_packet_checked = False  
    mask_payload_checked = True
    
    print(f"   mask_ip_cb.isChecked(): {mask_ip_checked}")
    print(f"   dedup_packet_cb.isChecked(): {dedup_packet_checked}")
    print(f"   mask_payload_cb.isChecked(): {mask_payload_checked}")
    
    # 步骤2: 分析build_pipeline_config
    print(f"\n🔧 步骤2: 分析build_pipeline_config")
    from src.pktmask.services.pipeline_service import build_pipeline_config
    
    gui_config = build_pipeline_config(
        enable_anon=mask_ip_checked,
        enable_dedup=dedup_packet_checked,
        enable_mask=mask_payload_checked
    )
    
    print(f"   GUI配置: {json.dumps(gui_config, indent=4)}")
    
    # 步骤3: 分析PipelineExecutor配置处理
    print(f"\n⚙️ 步骤3: 分析PipelineExecutor配置处理")
    from src.pktmask.core.pipeline.executor import PipelineExecutor
    
    executor = PipelineExecutor(gui_config)
    
    print(f"   创建的Stage数量: {len(executor.stages)}")
    for i, stage in enumerate(executor.stages):
        print(f"   Stage[{i}]: {stage.__class__.__name__}")
        if hasattr(stage, 'protocol'):
            print(f"      协议: {stage.protocol}")
        if hasattr(stage, 'mode'):
            print(f"      模式: {stage.mode}")
        if hasattr(stage, 'marker_config'):
            print(f"      Marker配置: {stage.marker_config}")
        if hasattr(stage, 'masker_config'):
            print(f"      Masker配置: {stage.masker_config}")
    
    # 步骤4: 分析NewMaskPayloadStage配置解析
    print(f"\n🎯 步骤4: 分析NewMaskPayloadStage配置解析")
    
    if executor.stages:
        mask_stage = None
        for stage in executor.stages:
            if stage.__class__.__name__ == 'NewMaskPayloadStage':
                mask_stage = stage
                break
        
        if mask_stage:
            print(f"   找到NewMaskPayloadStage:")
            print(f"      原始配置: {mask_stage.config}")
            print(f"      协议: {mask_stage.protocol}")
            print(f"      模式: {mask_stage.mode}")
            print(f"      Marker配置: {mask_stage.marker_config}")
            print(f"      Masker配置: {mask_stage.masker_config}")
            
            # 步骤5: 分析Marker模块配置
            print(f"\n🎭 步骤5: 分析Marker模块配置")
            try:
                marker = mask_stage._create_marker()
                print(f"      Marker类型: {marker.__class__.__name__}")
                if hasattr(marker, 'preserve_config'):
                    print(f"      保留配置: {marker.preserve_config}")
                else:
                    print(f"      ❌ Marker没有preserve_config属性")
                
                # 检查配置传递问题
                print(f"\n🔍 配置传递分析:")
                print(f"      GUI配置中的marker_config: {gui_config.get('mask', {}).get('marker_config', {})}")
                print(f"      NewMaskPayloadStage.marker_config: {mask_stage.marker_config}")
                print(f"      TLSProtocolMarker接收的config: {marker.config}")
                print(f"      TLSProtocolMarker.preserve_config: {getattr(marker, 'preserve_config', 'N/A')}")
                
            except Exception as e:
                print(f"      ❌ 创建Marker失败: {e}")
        else:
            print(f"   ❌ 未找到NewMaskPayloadStage")
    else:
        print(f"   ❌ 没有创建任何Stage")
    
    # 步骤6: 对比正确的配置
    print(f"\n✅ 步骤6: 对比正确的配置")
    
    correct_config = {
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
    
    print(f"   正确的配置应该是:")
    print(f"   {json.dumps(correct_config, indent=4)}")
    
    # 步骤7: 测试正确配置的效果
    print(f"\n🧪 步骤7: 测试正确配置的效果")
    
    test_file = "tests/data/tls/tls_1_2_plainip.pcap"
    if Path(test_file).exists():
        print(f"   使用测试文件: {test_file}")
        
        # 使用GUI配置测试
        print(f"   📊 GUI配置测试:")
        gui_result = test_config_with_file(gui_config.get('mask', {}), test_file)
        print(f"      处理包数: {gui_result.get('packets_processed', 0)}")
        print(f"      修改包数: {gui_result.get('packets_modified', 0)}")
        print(f"      掩码字节: {gui_result.get('masked_bytes', 0)}")
        
        # 使用正确配置测试
        print(f"   ✅ 正确配置测试:")
        correct_result = test_config_with_file(correct_config, test_file)
        print(f"      处理包数: {correct_result.get('packets_processed', 0)}")
        print(f"      修改包数: {correct_result.get('packets_modified', 0)}")
        print(f"      掩码字节: {correct_result.get('masked_bytes', 0)}")
        
        # 对比结果
        print(f"\n🔍 结果对比:")
        if gui_result.get('packets_modified', 0) != correct_result.get('packets_modified', 0):
            print(f"   🚨 发现问题: GUI配置和正确配置的结果不同!")
            print(f"      GUI配置修改包数: {gui_result.get('packets_modified', 0)}")
            print(f"      正确配置修改包数: {correct_result.get('packets_modified', 0)}")
        else:
            print(f"   ✅ 配置结果一致")
    else:
        print(f"   ❌ 测试文件不存在: {test_file}")

def test_config_with_file(config: Dict[str, Any], test_file: str) -> Dict[str, Any]:
    """使用指定配置测试文件处理"""
    
    try:
        from src.pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        stage = NewMaskPayloadStage(config)
        if not stage.initialize():
            return {'error': 'Stage初始化失败'}
        
        temp_output = f"temp_config_test_{Path(test_file).stem}.pcap"
        stats = stage.process_file(test_file, temp_output)
        
        # 清理临时文件
        if Path(temp_output).exists():
            Path(temp_output).unlink()
        
        return {
            'packets_processed': stats.packets_processed,
            'packets_modified': stats.packets_modified,
            'masked_bytes': stats.extra_metrics.get('masked_bytes', 0),
            'preserved_bytes': stats.extra_metrics.get('preserved_bytes', 0),
            'success': stats.extra_metrics.get('success', False)
        }
        
    except Exception as e:
        return {'error': str(e)}

if __name__ == "__main__":
    try:
        debug_gui_config_flow()
    except KeyboardInterrupt:
        print("\n\n⏹️  调试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 调试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
