#!/usr/bin/env python3
"""
PktMask MaskStage 端到端测试脚本

测试目标：
- 验证新实现的maskstage双模块架构（Marker模块 + Masker模块）
- 确认TLS消息掩码规则是否正确执行（TLS-20/21/22/24完全保留，TLS-23仅保留消息头）
- 分析是否存在规则优化过度合并问题

测试样本：tests/samples/tls-single/tls_sample.pcap
"""

import sys
import os
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def setup_logging():
    """设置详细日志"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('test_maskstage_e2e.log', mode='w')
        ]
    )
    return logging.getLogger(__name__)

def test_new_maskstage_architecture():
    """测试新版maskstage双模块架构"""
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("开始PktMask MaskStage端到端测试")
    logger.info("=" * 80)
    
    # 测试配置
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    output_file = "output/test_maskstage_e2e_output.pcap"
    
    # 验证输入文件
    if not Path(input_file).exists():
        logger.error(f"测试样本文件不存在: {input_file}")
        return False
    
    # 确保输出目录存在
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # 导入新版maskstage
        logger.info("导入新版MaskStage...")
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 创建测试配置
        config = {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "preserve": {
                    "handshake": True,           # TLS-22 完全保留
                    "application_data": False,   # TLS-23 仅保留消息头
                    "alert": True,              # TLS-21 完全保留
                    "change_cipher_spec": True, # TLS-20 完全保留
                    "heartbeat": True           # TLS-24 完全保留
                }
            },
            "masker_config": {
                "enable_optimization": True,
                "debug_mode": True
            }
        }
        
        logger.info(f"测试配置: {json.dumps(config, indent=2)}")
        
        # 创建maskstage实例
        logger.info("创建NewMaskPayloadStage实例...")
        stage = NewMaskPayloadStage(config)
        
        # 执行处理
        logger.info(f"开始处理文件: {input_file} -> {output_file}")
        start_time = time.time()
        
        stats = stage.process_file(input_file, output_file)
        
        processing_time = time.time() - start_time
        logger.info(f"处理完成，耗时: {processing_time:.2f} 秒")
        
        # 分析处理结果
        logger.info("=" * 60)
        logger.info("处理统计信息:")
        logger.info(f"  阶段名称: {stats.stage_name}")
        logger.info(f"  处理包数: {stats.packets_processed}")
        logger.info(f"  修改包数: {stats.packets_modified}")
        logger.info(f"  处理时长: {stats.duration_ms:.2f} ms")
        
        if hasattr(stats, 'extra_metrics') and stats.extra_metrics:
            logger.info("  额外指标:")
            for key, value in stats.extra_metrics.items():
                logger.info(f"    {key}: {value}")
        
        # 验证输出文件
        if Path(output_file).exists():
            file_size = Path(output_file).stat().st_size
            logger.info(f"输出文件生成成功: {output_file} ({file_size} 字节)")
        else:
            logger.error("输出文件未生成")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def analyze_tls_processing_details():
    """分析TLS处理细节，检查规则优化问题"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("分析TLS处理细节")
    logger.info("=" * 60)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    
    try:
        # 单独测试Marker模块
        logger.info("测试Marker模块...")
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        marker_config = {
            "preserve": {
                "handshake": True,
                "application_data": False,
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True
            }
        }
        
        marker = TLSProtocolMarker(marker_config)
        marker.initialize()
        
        # 生成保留规则
        logger.info("生成保留规则...")
        keep_rules = marker.analyze_file(input_file, marker_config)
        
        # 分析规则详情
        logger.info(f"生成的保留规则数量: {len(keep_rules.rules)}")
        logger.info("保留规则详情:")

        for i, rule in enumerate(keep_rules.rules):
            logger.info(f"  规则 {i+1}:")
            logger.info(f"    流ID: {rule.stream_id}")
            logger.info(f"    方向: {rule.direction}")
            logger.info(f"    序列号范围: {rule.seq_start} - {rule.seq_end}")
            logger.info(f"    长度: {rule.seq_end - rule.seq_start}")
            logger.info(f"    规则类型: {rule.rule_type}")
            if hasattr(rule, 'metadata') and rule.metadata:
                logger.info(f"    元数据: {rule.metadata}")
        
        # 检查规则优化状态
        if hasattr(keep_rules, 'metadata') and keep_rules.metadata:
            logger.info("规则集元数据:")
            for key, value in keep_rules.metadata.items():
                logger.info(f"  {key}: {value}")
        
        # 分析是否存在过度合并问题
        logger.info("=" * 40)
        logger.info("分析规则优化问题:")
        
        # 检查是否有大的保留区间（可能包含了ApplicationData）
        large_rules = [rule for rule in keep_rules.rules if (rule.seq_end - rule.seq_start) > 1000]
        if large_rules:
            logger.warning(f"发现 {len(large_rules)} 个大的保留区间（>1000字节）:")
            for rule in large_rules:
                logger.warning(f"  流{rule.stream_id}:{rule.direction} - {rule.seq_start}:{rule.seq_end} "
                             f"(长度: {rule.seq_end - rule.seq_start})")
                logger.warning("  这可能导致TLS ApplicationData被错误保留")
        
        return True
        
    except Exception as e:
        logger.error(f"TLS处理细节分析失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def compare_with_original_tls_analyzer():
    """与原始tls_flow_analyzer对比分析"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("与原始TLS分析器对比")
    logger.info("=" * 60)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    
    try:
        # 运行原始tls_flow_analyzer
        logger.info("运行原始tls_flow_analyzer...")
        import subprocess
        
        cmd = [
            sys.executable, "-m", "pktmask.tools.tls_flow_analyzer",
            "--pcap", input_file,
            "--formats", "json",
            "--output-dir", "output"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        if result.returncode == 0:
            logger.info("原始tls_flow_analyzer运行成功")
            
            # 读取分析结果
            analysis_file = "output/tls_sample_tls_flow_analysis.json"
            if Path(analysis_file).exists():
                with open(analysis_file, 'r') as f:
                    analysis_data = json.load(f)
                
                logger.info("原始分析器结果:")
                if 'flows' in analysis_data:
                    logger.info(f"  检测到TCP流数量: {len(analysis_data['flows'])}")
                    
                    for flow_id, flow_data in analysis_data['flows'].items():
                        logger.info(f"  流 {flow_id}:")
                        if 'tls_messages' in flow_data:
                            logger.info(f"    TLS消息数量: {len(flow_data['tls_messages'])}")
                            
                            # 分析TLS消息类型分布
                            msg_types = {}
                            for msg in flow_data['tls_messages']:
                                msg_type = msg.get('tls_type', 'unknown')
                                msg_types[msg_type] = msg_types.get(msg_type, 0) + 1
                            
                            logger.info(f"    TLS消息类型分布: {msg_types}")
        else:
            logger.warning(f"原始tls_flow_analyzer运行失败: {result.stderr}")
        
        return True
        
    except Exception as e:
        logger.error(f"对比分析失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """主测试函数"""
    print("PktMask MaskStage 端到端测试")
    print("=" * 80)
    
    success = True
    
    # 测试1: 新版maskstage架构
    print("\n1. 测试新版maskstage双模块架构...")
    if not test_new_maskstage_architecture():
        success = False
        print("❌ 新版maskstage架构测试失败")
    else:
        print("✅ 新版maskstage架构测试成功")
    
    # 测试2: TLS处理细节分析
    print("\n2. 分析TLS处理细节...")
    if not analyze_tls_processing_details():
        success = False
        print("❌ TLS处理细节分析失败")
    else:
        print("✅ TLS处理细节分析完成")
    
    # 测试3: 与原始分析器对比
    print("\n3. 与原始TLS分析器对比...")
    if not compare_with_original_tls_analyzer():
        success = False
        print("❌ 对比分析失败")
    else:
        print("✅ 对比分析完成")
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 所有测试完成，请查看详细日志: test_maskstage_e2e.log")
    else:
        print("⚠️  部分测试失败，请查看详细日志: test_maskstage_e2e.log")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
