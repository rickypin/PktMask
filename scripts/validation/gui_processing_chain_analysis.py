#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI处理链条分析脚本

分析GUI调用路径与后端接口直接调用路径的差异，
识别GUI处理链条中导致掩码结果不符合预期的具体问题点。

执行步骤：
1. 模拟GUI完整调用链条
2. 对比后端接口直接调用
3. 分析参数传递和配置差异
4. 识别问题根源
"""

import sys
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def setup_logging():
    """设置详细日志记录"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('gui_chain_analysis.log', mode='w', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

def simulate_gui_call_chain(test_file: Path, logger: logging.Logger) -> Dict[str, Any]:
    """模拟完整的GUI调用链条
    
    从MainWindow按钮点击到NewMaskPayloadStage执行的完整路径
    """
    logger.info("=== 模拟GUI调用链条 ===")
    
    try:
        # 步骤1: 模拟MainWindow的复选框状态
        logger.debug("步骤1: 模拟MainWindow复选框状态")
        mask_ip_checked = False      # mask_ip_cb.isChecked()
        dedup_packet_checked = False # dedup_packet_cb.isChecked()  
        mask_payload_checked = True  # mask_payload_cb.isChecked()
        
        logger.debug(f"复选框状态: mask_ip={mask_ip_checked}, dedup={dedup_packet_checked}, mask_payload={mask_payload_checked}")
        
        # 步骤2: 模拟PipelineManager.toggle_pipeline_processing()
        logger.debug("步骤2: 模拟PipelineManager配置构建")
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        gui_config = build_pipeline_config(
            enable_anon=mask_ip_checked,
            enable_dedup=dedup_packet_checked,
            enable_mask=mask_payload_checked
        )
        logger.debug(f"GUI配置构建结果: {json.dumps(gui_config, indent=2)}")
        
        # 步骤3: 模拟create_pipeline_executor调用
        logger.debug("步骤3: 模拟PipelineExecutor创建")
        executor = create_pipeline_executor(gui_config)
        logger.debug(f"执行器创建成功，包含stages: {[stage.name for stage in executor.stages]}")
        
        # 步骤4: 检查NewMaskPayloadStage的配置
        logger.debug("步骤4: 检查NewMaskPayloadStage配置")
        mask_stage = None
        for stage in executor.stages:
            if hasattr(stage, '__class__') and 'NewMaskPayloadStage' in stage.__class__.__name__:
                mask_stage = stage
                break
        
        if mask_stage:
            logger.debug(f"找到NewMaskPayloadStage: {mask_stage.__class__.__name__}")
            logger.debug(f"Stage配置: protocol={getattr(mask_stage, 'protocol', 'N/A')}")
            logger.debug(f"Stage模式: mode={getattr(mask_stage, 'mode', 'N/A')}")
            logger.debug(f"Marker配置: {getattr(mask_stage, 'marker_config', {})}")
            logger.debug(f"Masker配置: {getattr(mask_stage, 'masker_config', {})}")
        else:
            logger.error("未找到NewMaskPayloadStage实例")
            return {"success": False, "error": "未找到NewMaskPayloadStage实例"}
        
        # 步骤5: 模拟文件处理
        logger.debug("步骤5: 模拟GUI文件处理")
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        try:
            result = executor.run(str(test_file), str(output_file))
            
            gui_result = {
                "success": result.success,
                "errors": result.errors,
                "stage_stats": [],
                "total_duration_ms": result.duration_ms,
                "config_used": gui_config,
                "mask_stage_config": {
                    "protocol": getattr(mask_stage, 'protocol', 'N/A'),
                    "mode": getattr(mask_stage, 'mode', 'N/A'),
                    "marker_config": getattr(mask_stage, 'marker_config', {}),
                    "masker_config": getattr(mask_stage, 'masker_config', {})
                }
            }
            
            for stats in result.stage_stats:
                gui_result["stage_stats"].append({
                    "stage_name": stats.stage_name,
                    "packets_processed": stats.packets_processed,
                    "packets_modified": stats.packets_modified,
                    "duration_ms": stats.duration_ms,
                    "extra_metrics": stats.extra_metrics
                })
            
            logger.info(f"GUI调用链条执行完成: success={result.success}")
            return gui_result
            
        finally:
            if output_file.exists():
                output_file.unlink()
                
    except Exception as e:
        logger.error(f"GUI调用链条模拟失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {"success": False, "error": str(e)}

def direct_backend_call(test_file: Path, logger: logging.Logger) -> Dict[str, Any]:
    """直接调用后端接口
    
    绕过GUI，直接使用NewMaskPayloadStage
    """
    logger.info("=== 直接后端接口调用 ===")
    
    try:
        # 直接创建NewMaskPayloadStage配置
        logger.debug("步骤1: 直接创建NewMaskPayloadStage配置")
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
        logger.debug(f"直接配置: {json.dumps(direct_config, indent=2)}")
        
        # 直接实例化NewMaskPayloadStage
        logger.debug("步骤2: 直接实例化NewMaskPayloadStage")
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        stage = NewMaskPayloadStage(direct_config)
        if not stage.initialize():
            logger.error("NewMaskPayloadStage初始化失败")
            return {"success": False, "error": "Stage初始化失败"}
        
        logger.debug(f"Stage初始化成功: protocol={stage.protocol}, mode={stage.mode}")
        
        # 直接调用process_file
        logger.debug("步骤3: 直接调用process_file")
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        try:
            stats = stage.process_file(str(test_file), str(output_file))
            
            direct_result = {
                "success": True,
                "errors": [],
                "stage_stats": [{
                    "stage_name": stats.stage_name,
                    "packets_processed": stats.packets_processed,
                    "packets_modified": stats.packets_modified,
                    "duration_ms": stats.duration_ms,
                    "extra_metrics": stats.extra_metrics
                }],
                "total_duration_ms": stats.duration_ms,
                "config_used": direct_config,
                "mask_stage_config": {
                    "protocol": stage.protocol,
                    "mode": stage.mode,
                    "marker_config": stage.marker_config,
                    "masker_config": stage.masker_config
                }
            }
            
            logger.info(f"直接后端调用完成: success=True")
            return direct_result
            
        finally:
            if output_file.exists():
                output_file.unlink()
                
    except Exception as e:
        logger.error(f"直接后端调用失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {"success": False, "error": str(e)}

def analyze_differences(gui_result: Dict[str, Any], direct_result: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    """分析GUI调用与直接调用的差异"""
    logger.info("=== 分析调用差异 ===")
    
    differences = {
        "config_differences": {},
        "result_differences": {},
        "potential_issues": []
    }
    
    # 配置差异分析
    logger.debug("分析配置差异")
    gui_config = gui_result.get("config_used", {})
    direct_config = direct_result.get("config_used", {})
    
    if gui_config != direct_config:
        differences["config_differences"]["gui_config"] = gui_config
        differences["config_differences"]["direct_config"] = direct_config
        differences["potential_issues"].append("配置参数不一致")
        logger.warning("发现配置差异")
    else:
        logger.debug("配置参数一致")
    
    # Stage配置差异分析
    logger.debug("分析Stage配置差异")
    gui_stage_config = gui_result.get("mask_stage_config", {})
    direct_stage_config = direct_result.get("mask_stage_config", {})
    
    if gui_stage_config != direct_stage_config:
        differences["config_differences"]["gui_stage_config"] = gui_stage_config
        differences["config_differences"]["direct_stage_config"] = direct_stage_config
        differences["potential_issues"].append("Stage配置不一致")
        logger.warning("发现Stage配置差异")
    else:
        logger.debug("Stage配置一致")
    
    # 结果差异分析
    logger.debug("分析处理结果差异")
    gui_success = gui_result.get("success", False)
    direct_success = direct_result.get("success", False)
    
    if gui_success != direct_success:
        differences["result_differences"]["success_status"] = {
            "gui": gui_success,
            "direct": direct_success
        }
        differences["potential_issues"].append("执行成功状态不一致")
        logger.warning(f"执行状态差异: GUI={gui_success}, Direct={direct_success}")
    
    # 统计信息差异分析
    gui_stats = gui_result.get("stage_stats", [])
    direct_stats = direct_result.get("stage_stats", [])
    
    if len(gui_stats) != len(direct_stats):
        differences["result_differences"]["stats_count"] = {
            "gui": len(gui_stats),
            "direct": len(direct_stats)
        }
        differences["potential_issues"].append("统计信息数量不一致")
        logger.warning(f"统计信息数量差异: GUI={len(gui_stats)}, Direct={len(direct_stats)}")
    
    # 查找NewMaskPayloadStage的统计信息
    gui_mask_stats = None
    direct_mask_stats = None
    
    for stats in gui_stats:
        if "MaskPayload" in stats.get("stage_name", ""):
            gui_mask_stats = stats
            break
    
    for stats in direct_stats:
        if "MaskPayload" in stats.get("stage_name", ""):
            direct_mask_stats = stats
            break
    
    if gui_mask_stats and direct_mask_stats:
        if (gui_mask_stats.get("packets_processed") != direct_mask_stats.get("packets_processed") or
            gui_mask_stats.get("packets_modified") != direct_mask_stats.get("packets_modified")):
            differences["result_differences"]["mask_stats"] = {
                "gui": gui_mask_stats,
                "direct": direct_mask_stats
            }
            differences["potential_issues"].append("掩码处理统计不一致")
            logger.warning("发现掩码处理统计差异")
    
    return differences

def main():
    """主函数"""
    logger = setup_logging()
    logger.info("开始GUI处理链条分析")
    
    # 使用测试文件
    test_file = Path("tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap")
    if not test_file.exists():
        logger.error(f"测试文件不存在: {test_file}")
        return False
    
    logger.info(f"使用测试文件: {test_file}")
    
    # 执行GUI调用链条模拟
    gui_result = simulate_gui_call_chain(test_file, logger)
    
    # 执行直接后端调用
    direct_result = direct_backend_call(test_file, logger)
    
    # 分析差异
    differences = analyze_differences(gui_result, direct_result, logger)
    
    # 输出分析结果
    logger.info("=== 分析结果汇总 ===")
    
    if differences["potential_issues"]:
        logger.warning(f"发现 {len(differences['potential_issues'])} 个潜在问题:")
        for i, issue in enumerate(differences["potential_issues"], 1):
            logger.warning(f"  {i}. {issue}")
    else:
        logger.info("未发现明显差异")
    
    # 保存详细分析结果
    analysis_file = Path("gui_chain_analysis_result.json")
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump({
            "gui_result": gui_result,
            "direct_result": direct_result,
            "differences": differences
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"详细分析结果已保存到: {analysis_file}")
    
    return len(differences["potential_issues"]) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
