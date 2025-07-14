#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI掩码处理失效问题诊断脚本

用于系统性诊断GUI环境下NewMaskPayloadStage处理失效的根本原因。
严格禁止修改主程序代码，仅用于验证分析。

问题描述：
- GUI运行时大量文件显示"masked 0 pkts"
- 输出文件中TLS-23 ApplicationData消息体未被掩码
- 与端到端测试结果不一致

诊断目标：
1. 对比GUI配置与端到端测试配置差异
2. 验证Marker模块在GUI环境下的规则生成
3. 验证Masker模块在GUI环境下的掩码应用
4. 识别导致"masked 0 pkts"的根本原因
"""

import sys
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('gui_masking_diagnosis.log')
        ]
    )
    return logging.getLogger(__name__)

def get_gui_config():
    """获取GUI环境使用的配置（模拟build_pipeline_config函数）"""
    try:
        from pktmask.services import build_pipeline_config
        
        # 模拟GUI中的配置调用
        config = build_pipeline_config(
            enable_anon=False,  # 关闭IP匿名化以专注掩码问题
            enable_dedup=False, # 关闭去重以专注掩码问题
            enable_mask=True    # 启用掩码处理
        )
        return config
    except Exception as e:
        logger.error(f"获取GUI配置失败: {e}")
        return None

def get_e2e_test_config():
    """获取端到端测试使用的配置"""
    return {
        "mask": {
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
    }

def compare_configs(gui_config, e2e_config):
    """对比GUI配置与端到端测试配置"""
    logger.info("=== 配置对比分析 ===")
    logger.info(f"GUI配置: {gui_config}")
    logger.info(f"E2E测试配置: {e2e_config}")
    
    # 检查关键差异
    differences = []
    
    if gui_config and "mask" in gui_config:
        gui_mask = gui_config["mask"]
        e2e_mask = e2e_config["mask"]
        
        # 检查基础配置
        for key in ["protocol", "mode"]:
            gui_val = gui_mask.get(key)
            e2e_val = e2e_mask.get(key)
            if gui_val != e2e_val:
                differences.append(f"{key}: GUI={gui_val}, E2E={e2e_val}")
        
        # 检查子配置
        for sub_key in ["marker_config", "masker_config"]:
            gui_sub = gui_mask.get(sub_key, {})
            e2e_sub = e2e_mask.get(sub_key, {})
            if gui_sub != e2e_sub:
                differences.append(f"{sub_key}: GUI={gui_sub}, E2E={e2e_sub}")
    
    if differences:
        logger.warning(f"发现配置差异: {differences}")
    else:
        logger.info("配置基本一致")
    
    return differences

def test_single_file_with_gui_config(test_file: Path):
    """使用GUI配置测试单个文件"""
    logger.info(f"=== 测试文件: {test_file.name} ===")
    
    # 获取GUI配置
    gui_config = get_gui_config()
    if not gui_config:
        logger.error("无法获取GUI配置")
        return False
    
    # 创建临时输出文件
    with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
        output_file = Path(tmp.name)
    
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        
        # 创建执行器（模拟GUI环境）
        executor = PipelineExecutor(gui_config)
        
        # 执行处理
        result = executor.run(str(test_file), str(output_file))
        
        logger.info(f"处理结果: success={result.success}")
        if result.stage_stats:
            for i, stats in enumerate(result.stage_stats):
                logger.info(f"Stage {i}: {stats.stage_name}")
                logger.info(f"  - 处理包数: {stats.packets_processed}")
                logger.info(f"  - 修改包数: {stats.packets_modified}")
                logger.info(f"  - 处理时间: {stats.processing_time:.3f}s")
        
        if result.errors:
            logger.error(f"处理错误: {result.errors}")
        
        # 修正成功判断逻辑：只要处理成功且有修改包数就算成功
        if result.success and result.stage_stats:
            for stats in result.stage_stats:
                if "mask" in stats.stage_name.lower():
                    logger.info(f"掩码阶段统计: 处理包数={stats.packets_processed}, 修改包数={stats.packets_modified}")
                    return stats.packets_modified > 0
        return False
        
    except Exception as e:
        logger.error(f"测试文件 {test_file.name} 时发生异常: {e}")
        return False
    finally:
        # 清理临时文件
        if output_file.exists():
            output_file.unlink()

def test_marker_module_directly(test_file: Path):
    """直接测试Marker模块的规则生成"""
    logger.info(f"=== 直接测试Marker模块: {test_file.name} ===")

    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker

        # 创建Marker实例
        marker = TLSProtocolMarker()

        # 获取GUI配置中的marker_config
        gui_config = get_gui_config()
        marker_config = gui_config.get("mask", {}).get("marker_config", {}) if gui_config else {}

        # 分析文件生成规则
        keep_rules = marker.analyze_file(str(test_file), marker_config)

        logger.info(f"生成的保留规则数量: {len(keep_rules.rules) if keep_rules else 0}")

        if keep_rules and keep_rules.rules:
            logger.info("前5条规则详情:")
            for i, rule in enumerate(keep_rules.rules[:5]):
                logger.info(f"  规则{i+1}: {rule.stream_id} [{rule.start_seq}-{rule.end_seq}]")
        else:
            logger.warning("未生成任何保留规则！")

        return keep_rules is not None and len(keep_rules.rules) > 0

    except Exception as e:
        logger.error(f"直接测试Marker模块时发生异常: {e}")
        return False

def test_masker_module_directly(test_file: Path):
    """直接测试Masker模块的掩码应用"""
    logger.info(f"=== 直接测试Masker模块: {test_file.name} ===")

    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker

        # 先用Marker生成规则
        marker = TLSProtocolMarker()
        gui_config = get_gui_config()
        marker_config = gui_config.get("mask", {}).get("marker_config", {}) if gui_config else {}
        keep_rules = marker.analyze_file(str(test_file), marker_config)

        if not keep_rules or not keep_rules.rules:
            logger.warning("Marker未生成规则，无法测试Masker")
            return False

        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)

        try:
            # 创建Masker实例并应用掩码
            masker = PayloadMasker()
            masker_config = gui_config.get("mask", {}).get("masker_config", {}) if gui_config else {}

            masking_stats = masker.apply_masking(str(test_file), str(output_file), keep_rules)

            logger.info(f"掩码统计: {masking_stats}")
            logger.info(f"处理包数: {masking_stats.get('packets_processed', 0)}")
            logger.info(f"修改包数: {masking_stats.get('packets_modified', 0)}")

            return masking_stats.get('packets_modified', 0) > 0

        finally:
            if output_file.exists():
                output_file.unlink()

    except Exception as e:
        logger.error(f"直接测试Masker模块时发生异常: {e}")
        return False

def analyze_output_file_issue(test_file: Path):
    """分析输出文件数量不匹配问题"""
    logger.info(f"=== 分析输出文件问题: {test_file.name} ===")

    try:
        # 获取原始文件包数
        import subprocess
        result = subprocess.run(['tshark', '-r', str(test_file), '-T', 'fields', '-e', 'frame.number'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            original_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
            logger.info(f"原始文件包数: {original_count}")
        else:
            logger.warning("无法获取原始文件包数")
            original_count = 0

        # 使用GUI配置处理文件
        gui_config = get_gui_config()
        if not gui_config:
            return False

        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)

        try:
            from pktmask.core.pipeline.executor import PipelineExecutor
            executor = PipelineExecutor(gui_config)
            result = executor.run(str(test_file), str(output_file))

            if result.success and output_file.exists():
                # 检查输出文件包数
                result = subprocess.run(['tshark', '-r', str(output_file), '-T', 'fields', '-e', 'frame.number'],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    output_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
                    logger.info(f"输出文件包数: {output_count}")

                    if output_count != original_count:
                        logger.error(f"❌ 包数量不匹配: 原始{original_count} vs 输出{output_count}")
                        return False
                    else:
                        logger.info(f"✅ 包数量匹配: {output_count}")
                        return True
                else:
                    logger.error("无法读取输出文件")
                    return False
            else:
                logger.error("处理失败或输出文件不存在")
                return False

        finally:
            if output_file.exists():
                output_file.unlink()

    except Exception as e:
        logger.error(f"分析输出文件问题时发生异常: {e}")
        return False

def main():
    """主诊断流程"""
    global logger
    logger = setup_logging()
    
    logger.info("开始PktMask GUI掩码处理失效问题诊断")
    
    # 测试文件列表（重点关注问题文件）
    test_files = [
        "tls_1_2_plainip.pcap",
        "tls_1_3_0-RTT-2_22_23_mix.pcap", 
        "ssl_3.pcap",  # 已知工作的文件
        "tls_1_2_double_vlan.pcap"  # 已知工作的文件
    ]
    
    test_data_dir = project_root / "tests" / "data" / "tls"
    
    # 阶段1: 配置对比分析
    logger.info("\n" + "="*50)
    logger.info("阶段1: 配置对比分析")
    logger.info("="*50)
    
    gui_config = get_gui_config()
    e2e_config = get_e2e_test_config()
    config_differences = compare_configs(gui_config, e2e_config)
    
    # 阶段2: 文件级别测试
    logger.info("\n" + "="*50)
    logger.info("阶段2: 文件级别测试")
    logger.info("="*50)
    
    file_results = {}
    for filename in test_files:
        test_file = test_data_dir / filename
        if test_file.exists():
            file_results[filename] = test_single_file_with_gui_config(test_file)
        else:
            logger.warning(f"测试文件不存在: {test_file}")
    
    # 阶段3: 模块级别测试
    logger.info("\n" + "="*50)
    logger.info("阶段3: 模块级别测试")
    logger.info("="*50)
    
    marker_results = {}
    masker_results = {}
    
    for filename in test_files:
        test_file = test_data_dir / filename
        if test_file.exists():
            marker_results[filename] = test_marker_module_directly(test_file)
            masker_results[filename] = test_masker_module_directly(test_file)

    # 阶段3.5: 输出文件问题分析
    logger.info("\n" + "="*50)
    logger.info("阶段3.5: 输出文件问题分析")
    logger.info("="*50)

    output_file_results = {}
    for filename in test_files:
        test_file = test_data_dir / filename
        if test_file.exists():
            output_file_results[filename] = analyze_output_file_issue(test_file)
    
    # 阶段4: 结果汇总分析
    logger.info("\n" + "="*50)
    logger.info("阶段4: 结果汇总分析")
    logger.info("="*50)
    
    logger.info("文件级别测试结果:")
    for filename, success in file_results.items():
        status = "✅ 成功" if success else "❌ 失败"
        logger.info(f"  {filename}: {status}")
    
    logger.info("Marker模块测试结果:")
    for filename, success in marker_results.items():
        status = "✅ 成功" if success else "❌ 失败"
        logger.info(f"  {filename}: {status}")
    
    logger.info("Masker模块测试结果:")
    for filename, success in masker_results.items():
        status = "✅ 成功" if success else "❌ 失败"
        logger.info(f"  {filename}: {status}")

    logger.info("输出文件问题分析结果:")
    for filename, success in output_file_results.items():
        status = "✅ 正常" if success else "❌ 异常"
        logger.info(f"  {filename}: {status}")

    # 问题模式分析
    failed_files = [f for f, success in file_results.items() if not success]
    failed_marker = [f for f, success in marker_results.items() if not success]
    failed_masker = [f for f, success in masker_results.items() if not success]
    failed_output = [f for f, success in output_file_results.items() if not success]
    
    logger.info(f"\n问题模式分析:")
    logger.info(f"文件级别失败: {failed_files}")
    logger.info(f"Marker模块失败: {failed_marker}")
    logger.info(f"Masker模块失败: {failed_masker}")
    logger.info(f"输出文件异常: {failed_output}")

    if config_differences:
        logger.info(f"配置差异可能是问题原因: {config_differences}")

    # 诊断结论
    if failed_output:
        logger.error("🔍 诊断结论: 输出文件包数量不匹配，可能存在文件写入或处理问题")
    elif failed_marker:
        logger.error("🔍 诊断结论: Marker模块规则生成存在问题")
    elif failed_masker:
        logger.error("🔍 诊断结论: Masker模块掩码应用存在问题")
    elif config_differences:
        logger.error("🔍 诊断结论: GUI配置与测试配置存在关键差异")
    elif not failed_files:
        logger.info("🔍 诊断结论: 实际处理成功，之前的判断逻辑有误")
    else:
        logger.info("🔍 诊断结论: 需要进一步深入分析")

if __name__ == "__main__":
    main()
