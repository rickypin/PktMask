#!/usr/bin/env python3
"""
进度回调调试器

专门调试为什么progress_cb没有被调用
严格禁止修改主程序代码，仅用于验证分析。

Author: PktMask Core Team
Version: v1.0 (进度回调调试专用)
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
logger = logging.getLogger("progress_callback_debug")

class DebugProgressCollector:
    """调试进度收集器"""
    
    def __init__(self):
        self.stage_calls = []
        self.handle_calls = []
        self.log_events = []
    
    def debug_stage_progress(self, stage, stats):
        """调试stage进度回调"""
        call_info = {
            "stage_name": stage.name,
            "stage_type": type(stage).__name__,
            "packets_processed": stats.packets_processed,
            "packets_modified": stats.packets_modified,
            "call_stack": self._get_call_stack()
        }
        self.stage_calls.append(call_info)
        logger.info(f"🔍 Stage进度回调被调用: {stage.name} - processed={stats.packets_processed}, modified={stats.packets_modified}")
        
        # 调用原始的_handle_stage_progress函数
        from pktmask.services.pipeline_service import _handle_stage_progress
        _handle_stage_progress(stage, stats, self.debug_progress_callback)
    
    def debug_progress_callback(self, event_type, data):
        """调试进度回调"""
        if hasattr(event_type, 'value'):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)
        
        handle_info = {
            "event_type": event_type_str,
            "data": data,
            "call_stack": self._get_call_stack()
        }
        self.handle_calls.append(handle_info)
        
        if event_type_str == "LOG":
            self.log_events.append(data.get("message", ""))
            logger.info(f"📝 LOG事件生成: {data.get('message', '')}")
        else:
            logger.info(f"📡 事件生成: {event_type_str} - {data}")
    
    def _get_call_stack(self):
        """获取调用栈信息"""
        import traceback
        stack = traceback.extract_stack()
        # 只返回最后几层调用栈
        return [f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in stack[-5:]]

def test_direct_executor_call(test_file: Path) -> Dict[str, Any]:
    """直接测试executor调用"""
    logger.info(f"直接测试executor调用: {test_file}")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        # 创建调试收集器
        debug_collector = DebugProgressCollector()
        
        # 构建配置
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=True
        )
        
        # 创建执行器
        executor = create_pipeline_executor(config)
        logger.info(f"执行器创建成功，包含stages: {[stage.name for stage in executor.stages]}")
        
        # 创建临时输出文件
        with tempfile.TemporaryDirectory(prefix="direct_executor_test_") as temp_dir:
            temp_path = Path(temp_dir)
            output_file = temp_path / f"{test_file.stem}_direct_test.pcap"
            
            logger.info(f"直接调用executor.run: {test_file} -> {output_file}")
            
            # 直接调用executor.run
            result = executor.run(
                input_path=str(test_file),
                output_path=str(output_file),
                progress_cb=debug_collector.debug_stage_progress
            )
            
            # 分析结果
            analysis = {
                "success": result.success,
                "stage_calls": debug_collector.stage_calls,
                "handle_calls": debug_collector.handle_calls,
                "log_events": debug_collector.log_events,
                "executor_stage_stats": []
            }
            
            # 收集执行器返回的stage统计
            for stats in result.stage_stats:
                stage_info = {
                    "stage_name": stats.stage_name,
                    "packets_processed": stats.packets_processed,
                    "packets_modified": stats.packets_modified,
                    "duration_ms": stats.duration_ms
                }
                analysis["executor_stage_stats"].append(stage_info)
            
            return analysis
        
    except Exception as e:
        logger.error(f"直接executor调用失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {"error": str(e)}

def test_process_directory_call(test_file: Path) -> Dict[str, Any]:
    """测试process_directory调用"""
    logger.info(f"测试process_directory调用: {test_file}")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor, process_directory
        
        # 创建调试收集器
        debug_collector = DebugProgressCollector()
        
        # 构建配置
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=True
        )
        
        # 创建执行器
        executor = create_pipeline_executor(config)
        
        # 创建临时目录
        with tempfile.TemporaryDirectory(prefix="process_dir_test_") as temp_dir:
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
            
            logger.info(f"调用process_directory: {input_dir} -> {output_dir}")
            
            # 调用process_directory
            process_directory(
                executor=executor,
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                progress_callback=debug_collector.debug_progress_callback,
                is_running_check=lambda: True
            )
            
            # 分析结果
            analysis = {
                "success": True,
                "stage_calls": debug_collector.stage_calls,
                "handle_calls": debug_collector.handle_calls,
                "log_events": debug_collector.log_events
            }
            
            return analysis
        
    except Exception as e:
        logger.error(f"process_directory调用失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {"error": str(e)}

def analyze_debug_results(direct_result: Dict, process_dir_result: Dict) -> None:
    """分析调试结果"""
    print(f"\n{'='*80}")
    print("进度回调调试结果分析")
    print(f"{'='*80}")
    
    print(f"\n🔍 直接executor调用结果:")
    if "error" in direct_result:
        print(f"   ❌ 失败: {direct_result['error']}")
    else:
        print(f"   ✅ 成功: {direct_result.get('success', False)}")
        print(f"   Stage回调次数: {len(direct_result.get('stage_calls', []))}")
        print(f"   Handle回调次数: {len(direct_result.get('handle_calls', []))}")
        print(f"   LOG事件次数: {len(direct_result.get('log_events', []))}")
        
        # 显示stage回调详情
        for i, call in enumerate(direct_result.get('stage_calls', []), 1):
            print(f"     {i}. {call['stage_name']}: processed={call['packets_processed']}, modified={call['packets_modified']}")
        
        # 显示LOG事件详情
        for i, log in enumerate(direct_result.get('log_events', []), 1):
            print(f"     LOG {i}: {log}")
    
    print(f"\n📁 process_directory调用结果:")
    if "error" in process_dir_result:
        print(f"   ❌ 失败: {process_dir_result['error']}")
    else:
        print(f"   ✅ 成功: {process_dir_result.get('success', False)}")
        print(f"   Stage回调次数: {len(process_dir_result.get('stage_calls', []))}")
        print(f"   Handle回调次数: {len(process_dir_result.get('handle_calls', []))}")
        print(f"   LOG事件次数: {len(process_dir_result.get('log_events', []))}")
        
        # 显示stage回调详情
        for i, call in enumerate(process_dir_result.get('stage_calls', []), 1):
            print(f"     {i}. {call['stage_name']}: processed={call['packets_processed']}, modified={call['packets_modified']}")
        
        # 显示LOG事件详情
        for i, log in enumerate(process_dir_result.get('log_events', []), 1):
            print(f"     LOG {i}: {log}")
    
    print(f"\n🔍 对比分析:")
    direct_stage_calls = len(direct_result.get('stage_calls', []))
    process_stage_calls = len(process_dir_result.get('stage_calls', []))
    direct_log_events = len(direct_result.get('log_events', []))
    process_log_events = len(process_dir_result.get('log_events', []))
    
    if direct_stage_calls == process_stage_calls:
        print(f"   ✅ Stage回调次数一致: {direct_stage_calls}")
    else:
        print(f"   ❌ Stage回调次数不一致: 直接={direct_stage_calls}, process_directory={process_stage_calls}")
    
    if direct_log_events == process_log_events:
        print(f"   ✅ LOG事件次数一致: {direct_log_events}")
    else:
        print(f"   ❌ LOG事件次数不一致: 直接={direct_log_events}, process_directory={process_log_events}")

def main():
    """主函数"""
    logger.info("开始进度回调调试")
    
    # 测试文件
    test_file = project_root / "tests" / "data" / "tls" / "tls_1_2-2.pcap"
    
    if not test_file.exists():
        logger.error(f"测试文件不存在: {test_file}")
        return
    
    print(f"\n{'='*80}")
    print(f"测试文件: {test_file.name}")
    print(f"{'='*80}")
    
    # 测试直接executor调用
    direct_result = test_direct_executor_call(test_file)
    
    # 测试process_directory调用
    process_dir_result = test_process_directory_call(test_file)
    
    # 分析结果
    analyze_debug_results(direct_result, process_dir_result)
    
    print(f"\n{'='*80}")
    print("进度回调调试完成")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
