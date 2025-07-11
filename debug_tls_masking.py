#!/usr/bin/env python3
"""
深入分析TLS掩码问题的调试脚本

专门分析 tls_1_0_multi_segment_google-https.pcap 中的TLS-22和TLS-23掩码问题
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
from pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
from pktmask.core.processors.base_processor import ProcessorConfig
from pktmask.core.trim.models.tls_models import TLSRecordInfo, MaskRule, MaskAction

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_pcap_file(pcap_path: str) -> Dict[str, Any]:
    """分析pcap文件中的TLS记录"""
    logger.info(f"开始分析pcap文件: {pcap_path}")

    # 初始化分析器
    analyzer = TSharkTLSAnalyzer({'verbose': True})

    # 初始化分析器
    if not analyzer.initialize():
        raise RuntimeError("TShark分析器初始化失败")

    # 分析TLS记录
    tls_records = analyzer.analyze_file(pcap_path)

    logger.info(f"分析完成:")
    logger.info(f"  TLS记录数: {len(tls_records)}")

    # 统计TLS记录类型
    type_stats = {}
    cross_packet_records = []

    for record in tls_records:
        content_type = record.content_type
        if content_type not in type_stats:
            type_stats[content_type] = []
        type_stats[content_type].append(record)

        # 检查是否为跨包记录
        if record.is_cross_packet:
            cross_packet_records.append(record)

    logger.info("TLS记录类型统计:")
    for content_type, records in type_stats.items():
        logger.info(f"  TLS-{content_type}: {len(records)} 条记录")

    logger.info(f"  跨包记录数: {len(cross_packet_records)}")

    return {
        'tls_records': tls_records,
        'cross_packet_records': cross_packet_records,
        'type_stats': type_stats
    }

def generate_mask_rules(tls_records) -> List[MaskRule]:
    """生成掩码规则"""
    logger.info("开始生成掩码规则...")

    # 初始化规则生成器
    rule_generator = TLSMaskRuleGenerator({'verbose': True})

    # 生成掩码规则
    rules = rule_generator.generate_rules(tls_records)
    
    logger.info(f"生成了 {len(rules)} 条掩码规则")
    
    # 按TLS类型分组统计
    rule_stats = {}
    for rule in rules:
        tls_type = rule.tls_record_type
        if tls_type not in rule_stats:
            rule_stats[tls_type] = {'keep_all': 0, 'mask_payload': 0, 'other': 0}
        
        if rule.action == MaskAction.KEEP_ALL:
            rule_stats[tls_type]['keep_all'] += 1
        elif rule.action == MaskAction.MASK_PAYLOAD:
            rule_stats[tls_type]['mask_payload'] += 1
        else:
            rule_stats[tls_type]['other'] += 1
    
    logger.info("掩码规则统计:")
    for tls_type, stats in rule_stats.items():
        logger.info(f"  TLS-{tls_type}: KEEP_ALL={stats['keep_all']}, MASK_PAYLOAD={stats['mask_payload']}, OTHER={stats['other']}")
    
    return rules

def analyze_problematic_records(tls_records, rules: List[MaskRule]):
    """分析有问题的记录"""
    logger.info("分析可能有问题的记录...")

    # 检查TLS-22记录是否都设置为KEEP_ALL
    tls22_records = [r for r in tls_records if r.content_type == 22]
    tls22_rules = [r for r in rules if r.tls_record_type == 22]
    
    logger.info(f"TLS-22记录分析:")
    logger.info(f"  记录数: {len(tls22_records)}")
    logger.info(f"  规则数: {len(tls22_rules)}")
    
    problematic_tls22 = []
    for rule in tls22_rules:
        if rule.action != MaskAction.KEEP_ALL:
            problematic_tls22.append(rule)
            logger.warning(f"  ❌ 包{rule.packet_number}: TLS-22记录未设置为KEEP_ALL, 实际动作={rule.action}")
    
    if not problematic_tls22:
        logger.info("  ✅ 所有TLS-22记录都正确设置为KEEP_ALL")
    
    # 检查TLS-23记录是否都设置为MASK_PAYLOAD
    tls23_records = [r for r in tls_records if r.content_type == 23]
    tls23_rules = [r for r in rules if r.tls_record_type == 23]
    
    logger.info(f"TLS-23记录分析:")
    logger.info(f"  记录数: {len(tls23_records)}")
    logger.info(f"  规则数: {len(tls23_rules)}")
    
    problematic_tls23 = []
    for rule in tls23_rules:
        if rule.action != MaskAction.MASK_PAYLOAD:
            problematic_tls23.append(rule)
            logger.warning(f"  ❌ 包{rule.packet_number}: TLS-23记录未设置为MASK_PAYLOAD, 实际动作={rule.action}")
    
    if not problematic_tls23:
        logger.info("  ✅ 所有TLS-23记录都正确设置为MASK_PAYLOAD")
    
    return {
        'problematic_tls22': problematic_tls22,
        'problematic_tls23': problematic_tls23
    }

def test_actual_masking(pcap_path: str, output_path: str):
    """测试实际的掩码处理"""
    logger.info(f"测试实际掩码处理: {pcap_path} -> {output_path}")
    
    try:
        # 初始化处理器
        processor = TSharkEnhancedMaskProcessor(
            config=ProcessorConfig(enabled=True, name="TSharkEnhancedMaskProcessor", priority=0)
        )
        
        if not processor.initialize():
            logger.error("处理器初始化失败")
            return False
        
        # 执行掩码处理
        result = processor.process_file(pcap_path, output_path)
        
        if result.success:
            logger.info("✅ 掩码处理成功")
            logger.info(f"  处理统计: {result.stats}")
            return True
        else:
            logger.error(f"❌ 掩码处理失败: {result.error}")
            return False
            
    except Exception as e:
        logger.error(f"掩码处理异常: {e}")
        return False

def main():
    """主函数"""
    pcap_path = "/Users/ricky/Downloads/PktMask/tests/data/tls/tls_1_0_multi_segment_google-https.pcap"
    output_path = "/tmp/debug_masked_output.pcap"
    
    if not Path(pcap_path).exists():
        logger.error(f"输入文件不存在: {pcap_path}")
        return
    
    logger.info("=" * 80)
    logger.info("开始深入分析TLS掩码问题")
    logger.info("=" * 80)
    
    # 1. 分析pcap文件
    analysis_data = analyze_pcap_file(pcap_path)
    tls_records = analysis_data['tls_records']

    # 2. 生成掩码规则
    rules = generate_mask_rules(tls_records)

    # 3. 分析有问题的记录
    problems = analyze_problematic_records(tls_records, rules)
    
    # 4. 测试实际掩码处理
    success = test_actual_masking(pcap_path, output_path)
    
    # 5. 总结
    logger.info("=" * 80)
    logger.info("分析总结:")
    logger.info(f"  TLS-22问题记录数: {len(problems['problematic_tls22'])}")
    logger.info(f"  TLS-23问题记录数: {len(problems['problematic_tls23'])}")
    logger.info(f"  实际掩码处理: {'成功' if success else '失败'}")
    
    if problems['problematic_tls22'] or problems['problematic_tls23']:
        logger.warning("发现掩码规则问题，需要进一步调查")
    else:
        logger.info("掩码规则生成正常，问题可能在其他环节")
    
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
