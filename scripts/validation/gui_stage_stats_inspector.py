#!/usr/bin/env python3
"""
GUI Stage统计信息检查器

用于检查GUI实际运行时的stage统计信息，特别是packets_modified字段
严格禁止修改主程序代码，仅用于验证分析。

Author: PktMask Core Team
Version: v1.0 (GUI Stage统计检查专用)
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
logger = logging.getLogger("gui_stage_stats_inspector")

class StageStatsCollector:
    """Stage统计信息收集器"""
    
    def __init__(self):
        self.stage_stats = []
        self.progress_logs = []
    
    def collect_stage_stats(self, stage, stats):
        """收集stage统计信息"""
        stage_info = {
            "stage_name": stage.name,
            "stage_type": type(stage).__name__,
            "packets_processed": stats.packets_processed,
            "packets_modified": stats.packets_modified,
            "duration_ms": stats.duration_ms,
            "extra_metrics": stats.extra_metrics
        }
        self.stage_stats.append(stage_info)
        logger.info(f"收集Stage统计: {stage.name} - processed={stats.packets_processed}, modified={stats.packets_modified}")
    
    def collect_progress_log(self, event_type, data):
        """收集进度日志"""
        if hasattr(event_type, 'value'):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)
        
        log_entry = {
            "event_type": event_type_str,
            "data": data
        }
        self.progress_logs.append(log_entry)
        
        if event_type_str == "LOG" and "message" in data:
            logger.info(f"进度日志: {data['message']}")

def test_gui_pipeline_with_stats_collection(test_file: Path, output_file: Path) -> Dict[str, Any]:
    """测试GUI管道并收集详细的统计信息"""
    logger.info(f"测试GUI管道统计收集: {test_file} -> {output_file}")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        from pktmask.core.events import PipelineEvents
        
        # 创建统计收集器
        stats_collector = StageStatsCollector()
        
        # 构建GUI配置
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=True
        )
        logger.info(f"GUI配置: {config}")
        
        # 创建执行器
        executor = create_pipeline_executor(config)
        logger.info(f"执行器创建成功，包含stages: {[stage.name for stage in executor.stages]}")
        
        # 定义进度回调函数
        def progress_callback(event_type, data):
            stats_collector.collect_progress_log(event_type, data)
        
        # 定义stage进度回调函数
        def stage_progress_callback(stage, stats):
            stats_collector.collect_stage_stats(stage, stats)
            # 模拟pipeline_service中的_handle_stage_progress逻辑
            if stage.name == 'DedupStage':
                msg = f"    - {stage.name}: processed {stats.packets_processed} pkts, removed {stats.packets_modified} pkts"
            elif stage.name == 'AnonStage':
                msg = f"    - {stage.name}: processed {stats.packets_processed} pkts, Anonymized {stats.packets_modified} ips"
            else:
                msg = f"    - {stage.name}: processed {stats.packets_processed} pkts, masked {stats.packets_modified} pkts"
            # 重要：调用progress_callback发送LOG事件
            progress_callback(PipelineEvents.LOG, {'message': msg})
        
        # 执行处理
        result = executor.run(str(test_file), str(output_file), progress_cb=stage_progress_callback)
        
        # 分析结果
        analysis = {
            "success": result.success,
            "errors": result.errors,
            "collected_stage_stats": stats_collector.stage_stats,
            "collected_progress_logs": stats_collector.progress_logs,
            "executor_stage_stats": [],
            "total_duration_ms": result.duration_ms
        }
        
        # 收集执行器返回的stage统计
        for stats in result.stage_stats:
            stage_info = {
                "stage_name": stats.stage_name,
                "packets_processed": stats.packets_processed,
                "packets_modified": stats.packets_modified,
                "duration_ms": stats.duration_ms,
                "extra_metrics": stats.extra_metrics
            }
            analysis["executor_stage_stats"].append(stage_info)
        
        return analysis
        
    except Exception as e:
        logger.error(f"GUI管道统计收集失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {"error": str(e)}

def compare_stage_stats(collected_stats: List[Dict], executor_stats: List[Dict]) -> None:
    """对比收集的统计信息与执行器返回的统计信息"""
    print(f"\n{'='*80}")
    print("Stage统计信息对比分析")
    print(f"{'='*80}")
    
    print(f"\n📊 收集的Stage统计 (来自stage_progress_callback):")
    for i, stats in enumerate(collected_stats, 1):
        print(f"  {i}. {stats['stage_name']} ({stats['stage_type']}):")
        print(f"     - processed: {stats['packets_processed']}")
        print(f"     - modified: {stats['packets_modified']}")
        print(f"     - duration: {stats['duration_ms']:.2f}ms")
        if stats['extra_metrics']:
            print(f"     - extra_metrics: {stats['extra_metrics']}")
    
    print(f"\n📈 执行器返回的Stage统计 (来自result.stage_stats):")
    for i, stats in enumerate(executor_stats, 1):
        print(f"  {i}. {stats['stage_name']}:")
        print(f"     - processed: {stats['packets_processed']}")
        print(f"     - modified: {stats['packets_modified']}")
        print(f"     - duration: {stats['duration_ms']:.2f}ms")
        if stats['extra_metrics']:
            print(f"     - extra_metrics: {stats['extra_metrics']}")
    
    print(f"\n🔍 对比分析:")
    if len(collected_stats) != len(executor_stats):
        print(f"   ⚠️  统计数量不一致: 收集={len(collected_stats)}, 执行器={len(executor_stats)}")
    
    # 按stage名称对比
    collected_by_name = {stats['stage_name']: stats for stats in collected_stats}
    executor_by_name = {stats['stage_name']: stats for stats in executor_stats}
    
    all_stage_names = set(collected_by_name.keys()) | set(executor_by_name.keys())
    
    for stage_name in sorted(all_stage_names):
        collected = collected_by_name.get(stage_name)
        executor = executor_by_name.get(stage_name)
        
        if not collected:
            print(f"   ❌ {stage_name}: 收集统计缺失")
        elif not executor:
            print(f"   ❌ {stage_name}: 执行器统计缺失")
        else:
            if (collected['packets_processed'] == executor['packets_processed'] and
                collected['packets_modified'] == executor['packets_modified']):
                print(f"   ✅ {stage_name}: 统计一致 (processed={collected['packets_processed']}, modified={collected['packets_modified']})")
            else:
                print(f"   ❌ {stage_name}: 统计不一致")
                print(f"      收集: processed={collected['packets_processed']}, modified={collected['packets_modified']}")
                print(f"      执行器: processed={executor['packets_processed']}, modified={executor['packets_modified']}")

def analyze_progress_logs(progress_logs: List[Dict]) -> None:
    """分析进度日志"""
    print(f"\n📝 进度日志分析:")
    
    log_messages = [log for log in progress_logs if log['event_type'] == 'LOG']
    
    print(f"   总日志条数: {len(progress_logs)}")
    print(f"   LOG消息条数: {len(log_messages)}")
    
    print(f"\n   LOG消息详情:")
    for i, log in enumerate(log_messages, 1):
        message = log['data'].get('message', '')
        print(f"     {i}. {message}")
        
        # 检查是否包含"masked 0 pkts"
        if "masked 0 pkts" in message:
            print(f"        ⚠️  发现'masked 0 pkts'消息")
        elif "masked" in message and "pkts" in message:
            print(f"        ✅ 正常掩码消息")

def main():
    """主函数"""
    logger.info("开始GUI Stage统计信息检查")
    
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
        
        with tempfile.TemporaryDirectory(prefix="gui_stats_test_") as temp_dir:
            temp_path = Path(temp_dir)
            output_file = temp_path / f"{test_file.stem}_stats_test.pcap"
            
            # 运行测试
            result = test_gui_pipeline_with_stats_collection(test_file, output_file)
            
            if "error" in result:
                print(f"❌ 测试失败: {result['error']}")
                continue
            
            print(f"✅ 测试成功: {result.get('success', False)}")
            
            # 对比统计信息
            compare_stage_stats(
                result.get('collected_stage_stats', []),
                result.get('executor_stage_stats', [])
            )
            
            # 分析进度日志
            analyze_progress_logs(result.get('collected_progress_logs', []))
    
    print(f"\n{'='*80}")
    print("GUI Stage统计信息检查完成")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
