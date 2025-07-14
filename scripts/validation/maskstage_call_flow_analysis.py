#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MaskStage调用流程详细分析脚本

梳理GUI调用maskstage的完整过程和直接调用的过程，
进行详细的对比分析，识别所有差异点。
"""

import sys
import json
import logging
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def setup_logging():
    """设置详细日志记录"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('maskstage_call_flow_analysis.log', mode='w', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

class CallFlowTracker:
    """调用流程跟踪器"""
    
    def __init__(self, name: str):
        self.name = name
        self.steps = []
        self.configs = {}
        self.objects = {}
        self.results = {}
    
    def add_step(self, step_name: str, description: str, data: Any = None):
        """添加步骤"""
        step = {
            "step": step_name,
            "description": description,
            "data": data,
            "timestamp": self._get_timestamp()
        }
        self.steps.append(step)
        return step
    
    def add_config(self, config_name: str, config_data: Any):
        """添加配置"""
        self.configs[config_name] = config_data
    
    def add_object(self, obj_name: str, obj_info: Any):
        """添加对象信息"""
        self.objects[obj_name] = obj_info
    
    def add_result(self, result_name: str, result_data: Any):
        """添加结果"""
        self.results[result_name] = result_data
    
    def _get_timestamp(self):
        """获取时间戳"""
        import time
        return time.time()
    
    def to_dict(self):
        """转换为字典"""
        return {
            "name": self.name,
            "steps": self.steps,
            "configs": self.configs,
            "objects": self.objects,
            "results": self.results
        }

def trace_gui_call_flow(test_file: Path, logger: logging.Logger) -> CallFlowTracker:
    """跟踪GUI调用流程"""
    tracker = CallFlowTracker("GUI调用流程")
    logger.info("=== 开始跟踪GUI调用流程 ===")
    
    try:
        # 步骤1: MainWindow复选框状态模拟
        tracker.add_step("step_1", "MainWindow复选框状态模拟")
        checkbox_states = {
            "mask_ip_cb": False,
            "dedup_packet_cb": False,
            "mask_payload_cb": True
        }
        tracker.add_config("checkbox_states", checkbox_states)
        logger.debug(f"复选框状态: {checkbox_states}")
        
        # 步骤2: PipelineManager.toggle_pipeline_processing()
        tracker.add_step("step_2", "PipelineManager.toggle_pipeline_processing()调用")
        
        # 步骤3: build_pipeline_config()调用
        tracker.add_step("step_3", "build_pipeline_config()调用")
        from pktmask.services.pipeline_service import build_pipeline_config
        
        gui_config = build_pipeline_config(
            enable_anon=checkbox_states["mask_ip_cb"],
            enable_dedup=checkbox_states["dedup_packet_cb"],
            enable_mask=checkbox_states["mask_payload_cb"]
        )
        tracker.add_config("pipeline_config", gui_config)
        logger.debug(f"Pipeline配置: {json.dumps(gui_config, indent=2)}")
        
        # 步骤4: create_pipeline_executor()调用
        tracker.add_step("step_4", "create_pipeline_executor()调用")
        from pktmask.services.pipeline_service import create_pipeline_executor
        
        executor = create_pipeline_executor(gui_config)
        executor_info = {
            "class_name": executor.__class__.__name__,
            "stages_count": len(executor.stages),
            "stage_names": [stage.name for stage in executor.stages]
        }
        tracker.add_object("pipeline_executor", executor_info)
        logger.debug(f"执行器信息: {executor_info}")
        
        # 步骤5: PipelineExecutor._build_pipeline()内部调用
        tracker.add_step("step_5", "PipelineExecutor._build_pipeline()内部处理")
        
        # 检查mask配置提取
        mask_cfg = gui_config.get("mask", {})
        tracker.add_config("extracted_mask_config", mask_cfg)
        logger.debug(f"提取的mask配置: {json.dumps(mask_cfg, indent=2)}")
        
        # 步骤6: NewMaskPayloadStage实例化
        tracker.add_step("step_6", "NewMaskPayloadStage实例化")
        
        # 找到NewMaskPayloadStage实例
        mask_stage = None
        for stage in executor.stages:
            if hasattr(stage, '__class__') and 'NewMaskPayloadStage' in stage.__class__.__name__:
                mask_stage = stage
                break
        
        if mask_stage:
            stage_info = {
                "class_name": mask_stage.__class__.__name__,
                "protocol": getattr(mask_stage, 'protocol', 'N/A'),
                "mode": getattr(mask_stage, 'mode', 'N/A'),
                "marker_config": getattr(mask_stage, 'marker_config', {}),
                "masker_config": getattr(mask_stage, 'masker_config', {}),
                "initialized": getattr(mask_stage, '_initialized', False)
            }
            tracker.add_object("mask_stage", stage_info)
            logger.debug(f"MaskStage信息: {json.dumps(stage_info, indent=2)}")
        else:
            tracker.add_step("error", "未找到NewMaskPayloadStage实例")
            return tracker
        
        # 步骤7: ServicePipelineThread创建和启动
        tracker.add_step("step_7", "ServicePipelineThread创建和启动")
        
        # 步骤8: process_directory()调用
        tracker.add_step("step_8", "process_directory()调用")
        
        # 步骤9: executor.run()调用
        tracker.add_step("step_9", "executor.run()调用")
        
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        try:
            # 执行处理
            result = executor.run(str(test_file), str(output_file))
            
            # 步骤10: 结果收集
            tracker.add_step("step_10", "结果收集和统计")
            
            result_info = {
                "success": result.success,
                "errors": result.errors,
                "duration_ms": result.duration_ms,
                "stage_stats_count": len(result.stage_stats)
            }
            
            if result.stage_stats:
                for stats in result.stage_stats:
                    if "MaskPayload" in stats.stage_name:
                        result_info["mask_stats"] = {
                            "stage_name": stats.stage_name,
                            "packets_processed": stats.packets_processed,
                            "packets_modified": stats.packets_modified,
                            "duration_ms": stats.duration_ms,
                            "extra_metrics": stats.extra_metrics
                        }
                        break
            
            tracker.add_result("execution_result", result_info)
            logger.debug(f"执行结果: {json.dumps(result_info, indent=2)}")
            
        finally:
            if output_file.exists():
                output_file.unlink()
        
        # 步骤11: GUI事件处理
        tracker.add_step("step_11", "GUI事件处理和UI更新")
        
        logger.info("GUI调用流程跟踪完成")
        return tracker
        
    except Exception as e:
        tracker.add_step("error", f"GUI调用流程异常: {str(e)}")
        logger.error(f"GUI调用流程异常: {e}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return tracker

def trace_direct_call_flow(test_file: Path, logger: logging.Logger) -> CallFlowTracker:
    """跟踪直接调用流程"""
    tracker = CallFlowTracker("直接调用流程")
    logger.info("=== 开始跟踪直接调用流程 ===")
    
    try:
        # 步骤1: 直接配置创建
        tracker.add_step("step_1", "直接配置创建")
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
        tracker.add_config("direct_config", direct_config)
        logger.debug(f"直接配置: {json.dumps(direct_config, indent=2)}")
        
        # 步骤2: NewMaskPayloadStage直接实例化
        tracker.add_step("step_2", "NewMaskPayloadStage直接实例化")
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        stage = NewMaskPayloadStage(direct_config)
        
        stage_info = {
            "class_name": stage.__class__.__name__,
            "protocol": getattr(stage, 'protocol', 'N/A'),
            "mode": getattr(stage, 'mode', 'N/A'),
            "marker_config": getattr(stage, 'marker_config', {}),
            "masker_config": getattr(stage, 'masker_config', {}),
            "initialized": getattr(stage, '_initialized', False)
        }
        tracker.add_object("mask_stage", stage_info)
        logger.debug(f"Stage信息: {json.dumps(stage_info, indent=2)}")
        
        # 步骤3: Stage初始化
        tracker.add_step("step_3", "Stage.initialize()调用")
        init_success = stage.initialize()
        tracker.add_result("initialization", {"success": init_success})
        logger.debug(f"初始化结果: {init_success}")
        
        if not init_success:
            tracker.add_step("error", "Stage初始化失败")
            return tracker
        
        # 步骤4: process_file()直接调用
        tracker.add_step("step_4", "process_file()直接调用")
        
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        try:
            # 直接调用process_file
            stats = stage.process_file(str(test_file), str(output_file))
            
            # 步骤5: 结果收集
            tracker.add_step("step_5", "结果收集")
            
            result_info = {
                "stage_name": stats.stage_name,
                "packets_processed": stats.packets_processed,
                "packets_modified": stats.packets_modified,
                "duration_ms": stats.duration_ms,
                "extra_metrics": stats.extra_metrics
            }
            
            tracker.add_result("execution_result", result_info)
            logger.debug(f"执行结果: {json.dumps(result_info, indent=2)}")
            
        finally:
            if output_file.exists():
                output_file.unlink()
        
        logger.info("直接调用流程跟踪完成")
        return tracker
        
    except Exception as e:
        tracker.add_step("error", f"直接调用流程异常: {str(e)}")
        logger.error(f"直接调用流程异常: {e}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return tracker

def compare_call_flows(gui_tracker: CallFlowTracker, direct_tracker: CallFlowTracker, logger: logging.Logger) -> Dict[str, Any]:
    """对比两种调用流程"""
    logger.info("=== 开始对比调用流程 ===")
    
    comparison = {
        "flow_structure": {},
        "config_differences": {},
        "object_differences": {},
        "result_differences": {},
        "step_count": {},
        "key_differences": []
    }
    
    # 对比步骤数量
    gui_steps = len(gui_tracker.steps)
    direct_steps = len(direct_tracker.steps)
    comparison["step_count"] = {
        "gui": gui_steps,
        "direct": direct_steps,
        "difference": gui_steps - direct_steps
    }
    logger.debug(f"步骤数量对比: GUI={gui_steps}, 直接={direct_steps}")
    
    # 对比配置
    gui_configs = gui_tracker.configs
    direct_configs = direct_tracker.configs
    
    # 检查mask配置差异
    gui_mask_config = gui_configs.get("extracted_mask_config", {})
    direct_mask_config = direct_configs.get("direct_config", {})
    
    if gui_mask_config != direct_mask_config:
        comparison["config_differences"]["mask_config"] = {
            "gui": gui_mask_config,
            "direct": direct_mask_config
        }
        comparison["key_differences"].append("Mask配置结构不同")
        logger.warning("发现Mask配置差异")
    else:
        logger.debug("Mask配置一致")
    
    # 对比对象信息
    gui_stage = gui_tracker.objects.get("mask_stage", {})
    direct_stage = direct_tracker.objects.get("mask_stage", {})
    
    stage_diff = {}
    for key in set(gui_stage.keys()) | set(direct_stage.keys()):
        gui_val = gui_stage.get(key)
        direct_val = direct_stage.get(key)
        if gui_val != direct_val:
            stage_diff[key] = {"gui": gui_val, "direct": direct_val}
    
    if stage_diff:
        comparison["object_differences"]["mask_stage"] = stage_diff
        comparison["key_differences"].append("MaskStage对象属性不同")
        logger.warning(f"发现Stage对象差异: {stage_diff}")
    else:
        logger.debug("Stage对象属性一致")
    
    # 对比执行结果
    gui_result = gui_tracker.results.get("execution_result", {})
    direct_result = direct_tracker.results.get("execution_result", {})
    
    # 提取mask相关统计
    gui_mask_stats = gui_result.get("mask_stats", {})
    direct_mask_stats = direct_result
    
    result_diff = {}
    common_keys = ["packets_processed", "packets_modified", "duration_ms"]
    for key in common_keys:
        gui_val = gui_mask_stats.get(key)
        direct_val = direct_mask_stats.get(key)
        if gui_val != direct_val:
            result_diff[key] = {"gui": gui_val, "direct": direct_val}
    
    if result_diff:
        comparison["result_differences"]["mask_stats"] = result_diff
        comparison["key_differences"].append("执行结果统计不同")
        logger.warning(f"发现执行结果差异: {result_diff}")
    else:
        logger.debug("执行结果统计一致")
    
    # 分析流程结构差异
    gui_flow = [step["step"] for step in gui_tracker.steps if not step["step"].startswith("error")]
    direct_flow = [step["step"] for step in direct_tracker.steps if not step["step"].startswith("error")]
    
    comparison["flow_structure"] = {
        "gui_flow": gui_flow,
        "direct_flow": direct_flow,
        "gui_unique_steps": list(set(gui_flow) - set(direct_flow)),
        "direct_unique_steps": list(set(direct_flow) - set(gui_flow))
    }
    
    if comparison["flow_structure"]["gui_unique_steps"]:
        comparison["key_differences"].append("GUI有额外的处理步骤")
    
    logger.info(f"发现 {len(comparison['key_differences'])} 个关键差异")
    
    return comparison

def main():
    """主函数"""
    logger = setup_logging()
    logger.info("开始MaskStage调用流程详细分析")
    
    # 使用测试文件
    test_file = Path("tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap")
    if not test_file.exists():
        logger.error(f"测试文件不存在: {test_file}")
        return False
    
    logger.info(f"使用测试文件: {test_file}")
    
    # 跟踪GUI调用流程
    gui_tracker = trace_gui_call_flow(test_file, logger)
    
    # 跟踪直接调用流程
    direct_tracker = trace_direct_call_flow(test_file, logger)
    
    # 对比两种流程
    comparison = compare_call_flows(gui_tracker, direct_tracker, logger)
    
    # 输出分析结果
    logger.info("=== 分析结果汇总 ===")
    
    if comparison["key_differences"]:
        logger.warning(f"发现 {len(comparison['key_differences'])} 个关键差异:")
        for i, diff in enumerate(comparison["key_differences"], 1):
            logger.warning(f"  {i}. {diff}")
    else:
        logger.info("两种调用流程基本一致")
    
    # 保存详细分析结果
    analysis_file = Path("maskstage_call_flow_analysis.json")
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump({
            "gui_flow": gui_tracker.to_dict(),
            "direct_flow": direct_tracker.to_dict(),
            "comparison": comparison
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"详细分析结果已保存到: {analysis_file}")
    
    return len(comparison["key_differences"]) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
