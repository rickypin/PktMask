#!/usr/bin/env python3
"""
GUI完整调用链模拟器

完全模拟GUI实际运行时的调用链，包括ServicePipelineThread和process_directory
严格禁止修改主程序代码，仅用于验证分析。

Author: PktMask Core Team
Version: v1.0 (GUI完整调用链模拟专用)
"""

import sys
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 配置日志
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("gui_full_simulation")

class ProgressCollector:
    """进度事件收集器"""
    
    def __init__(self):
        self.events = []
        self.log_messages = []
        self.step_summaries = []
    
    def collect_event(self, event_type, data):
        """收集进度事件"""
        if hasattr(event_type, 'value'):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)
        
        event_entry = {
            "event_type": event_type_str,
            "data": data
        }
        self.events.append(event_entry)
        
        # 特别处理LOG和STEP_SUMMARY事件
        if event_type_str == "LOG" and "message" in data:
            self.log_messages.append(data["message"])
            logger.info(f"LOG: {data['message']}")
        elif event_type_str == "STEP_SUMMARY":
            self.step_summaries.append(data)
            logger.info(f"STEP_SUMMARY: {data}")

def simulate_gui_full_pipeline(test_file: Path) -> Dict[str, Any]:
    """完全模拟GUI的完整调用链"""
    logger.info(f"模拟GUI完整调用链: {test_file}")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor, process_directory
        from pktmask.core.events import PipelineEvents
        
        # 创建进度收集器
        progress_collector = ProgressCollector()
        
        # 构建GUI配置（完全模拟GUI的配置）
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=True
        )
        logger.info(f"GUI配置: {config}")
        
        # 创建执行器（完全模拟GUI的执行器创建）
        executor = create_pipeline_executor(config)
        logger.info(f"执行器创建成功，包含stages: {[stage.name for stage in executor.stages]}")
        
        # 创建临时目录模拟GUI的输入输出目录
        with tempfile.TemporaryDirectory(prefix="gui_full_sim_") as temp_dir:
            temp_path = Path(temp_dir)
            
            # 创建输入目录并复制测试文件
            input_dir = temp_path / "input"
            input_dir.mkdir()
            input_file = input_dir / test_file.name
            import shutil
            shutil.copy2(test_file, input_file)
            
            # 创建输出目录
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            # 完全模拟GUI的process_directory调用
            logger.info(f"调用process_directory: {input_dir} -> {output_dir}")
            
            # 模拟is_running_check函数
            def is_running_check():
                return True
            
            # 调用process_directory（这是GUI实际使用的函数）
            process_directory(
                executor=executor,
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                progress_callback=progress_collector.collect_event,
                is_running_check=is_running_check
            )
            
            # 分析结果
            analysis = {
                "success": True,
                "total_events": len(progress_collector.events),
                "log_messages": progress_collector.log_messages,
                "step_summaries": progress_collector.step_summaries,
                "all_events": progress_collector.events
            }
            
            return analysis
        
    except Exception as e:
        logger.error(f"GUI完整调用链模拟失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {"error": str(e)}

def analyze_log_messages(log_messages: List[str]) -> None:
    """分析日志消息"""
    print(f"\n📝 日志消息分析:")
    print(f"   总日志条数: {len(log_messages)}")
    
    # 分类日志消息
    masked_messages = []
    other_stage_messages = []
    general_messages = []
    
    for i, message in enumerate(log_messages, 1):
        print(f"     {i}. {message}")
        
        if "masked" in message and "pkts" in message:
            masked_messages.append(message)
        elif any(keyword in message for keyword in ["processed", "removed", "Anonymized"]):
            other_stage_messages.append(message)
        else:
            general_messages.append(message)
    
    print(f"\n   分类统计:")
    print(f"     掩码相关消息: {len(masked_messages)}")
    print(f"     其他Stage消息: {len(other_stage_messages)}")
    print(f"     一般消息: {len(general_messages)}")
    
    if masked_messages:
        print(f"\n   掩码消息详情:")
        for msg in masked_messages:
            print(f"     - {msg}")
            if "masked 0 pkts" in msg:
                print(f"       ⚠️  发现'masked 0 pkts'消息！")
            elif "masked" in msg and "pkts" in msg:
                print(f"       ✅ 正常掩码消息")

def analyze_step_summaries(step_summaries: List[Dict]) -> None:
    """分析步骤摘要"""
    print(f"\n📊 步骤摘要分析:")
    print(f"   总摘要条数: {len(step_summaries)}")
    
    for i, summary in enumerate(step_summaries, 1):
        step_name = summary.get('step_name', 'Unknown')
        packets_processed = summary.get('packets_processed', 0)
        packets_modified = summary.get('packets_modified', 0)
        filename = summary.get('filename', 'Unknown')
        
        print(f"     {i}. {step_name} ({filename}):")
        print(f"        - processed: {packets_processed}")
        print(f"        - modified: {packets_modified}")
        
        if step_name in ['NewMaskPayloadStage', 'Mask Payloads (v2)'] and packets_modified == 0:
            print(f"        ⚠️  掩码Stage修改包数为0！")
        elif step_name in ['NewMaskPayloadStage', 'Mask Payloads (v2)'] and packets_modified > 0:
            print(f"        ✅ 掩码Stage正常修改了{packets_modified}个包")

def main():
    """主函数"""
    logger.info("开始GUI完整调用链模拟")
    
    # 测试文件
    test_files = [
        "tls_1_2-2.pcap",
        "tls_1_2_plainip.pcap"
    ]
    
    test_dir = project_root / "tests" / "data" / "tls"
    
    for file_name in test_files:
        test_file = test_dir / file_name
        if not test_file.exists():
            logger.warning(f"测试文件不存在: {test_file}")
            continue
        
        print(f"\n{'='*80}")
        print(f"测试文件: {file_name}")
        print(f"{'='*80}")
        
        # 运行完整模拟
        result = simulate_gui_full_pipeline(test_file)
        
        if "error" in result:
            print(f"❌ 模拟失败: {result['error']}")
            continue
        
        print(f"✅ 模拟成功")
        print(f"   总事件数: {result.get('total_events', 0)}")
        
        # 分析日志消息
        analyze_log_messages(result.get('log_messages', []))
        
        # 分析步骤摘要
        analyze_step_summaries(result.get('step_summaries', []))
    
    print(f"\n{'='*80}")
    print("GUI完整调用链模拟完成")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
