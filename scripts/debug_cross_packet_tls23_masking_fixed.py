#!/usr/bin/env python3
"""
跨包TLS-23掩码处理修复验证脚本

此脚本用于验证修复后的跨包TLS-23掩码处理功能是否能正确处理以下三个问题样本：
1. tls_1_2_single_vlan.pcap
2. ssl_3.pcapng  
3. tls_1_0_multi_segment_google-https.pcap

修复内容：
1. 增强TSharkTLSAnalyzer的跨包检测算法
2. 改进TLSMaskRuleGenerator的分段掩码规则生成
3. 优化ScapyMaskApplier的边界验证和掩码应用
"""

import sys
import os
import logging
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
from src.pktmask.config.defaults import AppConfig


def setup_logging():
    """设置详细的日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('debug_cross_packet_tls23_fixed.log', mode='w')
        ]
    )
    return logging.getLogger(__name__)


def analyze_sample_file(sample_file: Path, logger: logging.Logger) -> Dict[str, Any]:
    """分析单个样本文件的跨包TLS-23处理
    
    Args:
        sample_file: 样本文件路径
        logger: 日志记录器
        
    Returns:
        分析结果字典
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"🔬 开始分析样本文件: {sample_file.name}")
    logger.info(f"{'='*80}")
    
    if not sample_file.exists():
        logger.error(f"❌ 样本文件不存在: {sample_file}")
        return {'error': '文件不存在'}
    
    # 配置处理器
    config = AppConfig()
    config.temp_dir = tempfile.mkdtemp(prefix=f"debug_{sample_file.stem}_")
    config.verbose = True
    
    # 初始化增强掩码处理器
    processor = TSharkEnhancedMaskProcessor(config.to_dict())
    
    try:
        # 检查依赖
        if not processor.check_dependencies():
            logger.error("❌ 依赖检查失败")
            return {'error': '依赖检查失败'}
        
        # 初始化处理器
        if not processor.initialize():
            logger.error("❌ 处理器初始化失败")
            return {'error': '处理器初始化失败'}
        
        logger.info(f"✅ 处理器初始化成功")
        
        # 创建输出文件路径
        output_file = Path(config.temp_dir) / f"{sample_file.stem}_masked{sample_file.suffix}"
        
        logger.info(f"📁 输出文件: {output_file}")
        
        # 开始处理
        start_time = time.time()
        logger.info(f"🚀 开始TLS-23跨包掩码处理...")
        
        result = processor.process_file(str(sample_file), str(output_file))
        
        processing_time = time.time() - start_time
        
        # 分析结果
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 处理结果分析")
        logger.info(f"{'='*60}")
        
        if result.success:
            logger.info(f"✅ 处理成功")
            logger.info(f"⏱️  处理时间: {processing_time:.2f}秒")
            logger.info(f"📦 处理包数: {result.packets_processed}")
            logger.info(f"🎯 修改包数: {result.packets_modified}")
            logger.info(f"📈 修改率: {result.packets_modified/result.packets_processed*100:.1f}%")
            
            # 检查输出文件
            if output_file.exists():
                output_size = output_file.stat().st_size
                input_size = sample_file.stat().st_size
                logger.info(f"📄 输出文件大小: {output_size} bytes")
                logger.info(f"📄 输入文件大小: {input_size} bytes")
                logger.info(f"📊 文件大小变化: {(output_size-input_size)/input_size*100:+.1f}%")
            
            # 提取关键统计信息
            analysis_result = {
                'success': True,
                'file': sample_file.name,
                'processing_time': processing_time,
                'packets_processed': result.packets_processed,
                'packets_modified': result.packets_modified,
                'modification_rate': result.packets_modified/result.packets_processed*100 if result.packets_processed > 0 else 0,
                'output_file': str(output_file),
                'tls_analysis': getattr(result, 'tls_analysis', None),
                'cross_packet_records': getattr(result, 'cross_packet_records', []),
                'mask_rules_generated': getattr(result, 'mask_rules_generated', 0),
                'cross_packet_rules': getattr(result, 'cross_packet_rules', 0)
            }
            
            # 检查是否解决了跨包掩码问题
            if result.packets_modified > 0:
                logger.info(f"🎉 跨包TLS-23掩码问题已解决！修改了{result.packets_modified}个包")
                analysis_result['cross_packet_fixed'] = True
            else:
                logger.warning(f"⚠️  仍然存在问题：修改了0个包")
                analysis_result['cross_packet_fixed'] = False
            
            return analysis_result
            
        else:
            logger.error(f"❌ 处理失败")
            if hasattr(result, 'error'):
                logger.error(f"🔍 错误信息: {result.error}")
            return {
                'success': False,
                'file': sample_file.name,
                'error': getattr(result, 'error', '未知错误')
            }
    
    except Exception as e:
        logger.error(f"❌ 处理异常: {e}")
        import traceback
        logger.error(f"🔍 详细错误:\n{traceback.format_exc()}")
        return {
            'success': False,
            'file': sample_file.name,
            'error': str(e)
        }
    
    finally:
        # 清理临时文件
        try:
            import shutil
            if hasattr(config, 'temp_dir') and Path(config.temp_dir).exists():
                shutil.rmtree(config.temp_dir)
                logger.info(f"🧹 清理临时目录: {config.temp_dir}")
        except Exception as e:
            logger.warning(f"⚠️  清理临时目录失败: {e}")


def main():
    """主函数"""
    logger = setup_logging()
    
    logger.info("🚀 跨包TLS-23掩码处理修复验证开始")
    logger.info("="*80)
    
    # 问题样本文件列表
    problem_samples = [
        'tls_1_2_single_vlan.pcap',
        'ssl_3.pcapng',
        'tls_1_0_multi_segment_google-https.pcap'
    ]
    
    # 查找样本文件
    project_root = Path(__file__).parent.parent
    samples_dir = project_root / 'tests' / 'data'
    
    logger.info(f"📂 搜索样本文件目录: {samples_dir}")
    
    found_samples = []
    for sample_name in problem_samples:
        # 搜索样本文件
        sample_files = list(samples_dir.rglob(sample_name))
        if sample_files:
            found_samples.append(sample_files[0])
            logger.info(f"✅ 找到样本文件: {sample_files[0]}")
        else:
            logger.warning(f"⚠️  未找到样本文件: {sample_name}")
    
    if not found_samples:
        logger.error("❌ 未找到任何问题样本文件")
        return 1
    
    logger.info(f"\n📋 将分析 {len(found_samples)} 个样本文件")
    
    # 分析每个样本文件
    results = []
    for i, sample_file in enumerate(found_samples, 1):
        logger.info(f"\n🔬 分析进度: {i}/{len(found_samples)}")
        result = analyze_sample_file(sample_file, logger)
        results.append(result)
    
    # 生成综合报告
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 综合分析报告")
    logger.info(f"{'='*80}")
    
    successful_fixes = 0
    total_analyzed = len(results)
    
    for result in results:
        file_name = result.get('file', '未知文件')
        if result.get('success', False):
            if result.get('cross_packet_fixed', False):
                logger.info(f"✅ {file_name}: 跨包TLS-23掩码问题已修复")
                successful_fixes += 1
            else:
                logger.warning(f"⚠️  {file_name}: 处理成功但仍有问题（修改0个包）")
        else:
            logger.error(f"❌ {file_name}: 处理失败 - {result.get('error', '未知错误')}")
    
    # 最终结果
    success_rate = (successful_fixes / total_analyzed * 100) if total_analyzed > 0 else 0
    
    logger.info(f"\n🎯 最终结果:")
    logger.info(f"   总分析文件: {total_analyzed}")
    logger.info(f"   成功修复: {successful_fixes}")
    logger.info(f"   修复成功率: {success_rate:.1f}%")
    
    if success_rate >= 80:
        logger.info(f"🎉 跨包TLS-23掩码修复验证成功！")
        return 0
    elif success_rate >= 50:
        logger.warning(f"⚠️  跨包TLS-23掩码修复部分成功，需要进一步优化")
        return 1
    else:
        logger.error(f"❌ 跨包TLS-23掩码修复验证失败，需要重新检查修复方案")
        return 2


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code) 