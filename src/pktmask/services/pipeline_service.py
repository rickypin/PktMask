"""
Pipeline 服务接口
提供 GUI 与核心管道的解耦接口
"""

from typing import Any, Callable, Dict, Optional, Tuple

from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger


# 定义服务层异常
class PipelineServiceError(Exception):
    """服务层基础异常"""


class ConfigurationError(PipelineServiceError):
    """配置错误"""


logger = get_logger("PipelineService")

# 创建管道执行器
# Dummy implementation; replace ... with real logic


def create_pipeline_executor(config: Dict) -> object:
    """
    创建管道执行器

    Args:
        config: 管道配置字典，包含各阶段的启用状态和参数

    Returns:
        执行器对象（对 GUI 不透明）
    """
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor

        return PipelineExecutor(config)
    except Exception as e:
        logger.error(f"[Service] Failed to create executor: {e}")
        raise PipelineServiceError("Failed to create executor")


# 处理目录中的所有 PCAP 文件
# Dummy implementation; replace ... with real logic


def process_directory(
    executor: object,
    input_dir: str,
    output_dir: str,
    progress_callback: Callable[[PipelineEvents, Dict], None],
    is_running_check: Callable[[], bool],
) -> None:
    """
    处理目录中的所有 PCAP 文件

    Args:
        executor: 执行器对象
        input_dir: 输入目录路径
        output_dir: 输出目录路径
        progress_callback: 进度回调函数
        is_running_check: 检查是否继续运行的函数
    """
    try:
        import os

        logger.info(f"[Service] Starting directory processing: {input_dir}")

        # 发送管道开始事件
        progress_callback(PipelineEvents.PIPELINE_START, {"total_subdirs": 1})

        # 扫描目录中的PCAP文件
        pcap_files = []
        for file in os.scandir(input_dir):
            if file.name.endswith((".pcap", ".pcapng")):
                pcap_files.append(file.path)

        if not pcap_files:
            progress_callback(
                PipelineEvents.LOG, {"message": "No PCAP files found in directory"}
            )
            progress_callback(PipelineEvents.PIPELINE_END, {})
            return

        # 发送子目录开始事件
        rel_subdir = os.path.relpath(input_dir, input_dir)
        progress_callback(
            PipelineEvents.SUBDIR_START,
            {
                "name": rel_subdir,
                "current": 1,
                "total": 1,
                "file_count": len(pcap_files),
            },
        )

        # 处理每个文件
        for input_path in pcap_files:
            if not is_running_check():
                break

            # 发送文件开始事件
            progress_callback(PipelineEvents.FILE_START, {"path": input_path})

            try:
                # 构造输出文件名
                base_name, ext = os.path.splitext(os.path.basename(input_path))
                output_path = os.path.join(output_dir, f"{base_name}_processed{ext}")

                # 使用 executor 处理文件
                result = executor.run(
                    input_path,
                    output_path,
                    progress_cb=lambda stage, stats: _handle_stage_progress(
                        stage, stats, progress_callback
                    ),
                )

                # Check if processing was successful
                if not result.success:
                    # Send error information to GUI for failed processing
                    for error in result.errors:
                        progress_callback(
                            PipelineEvents.ERROR,
                            {
                                "message": f"File {os.path.basename(input_path)}: {error}"
                            },
                        )

                    # Send user-friendly error messages from stage statistics
                    for stage_stats in result.stage_stats:
                        if "user_message" in stage_stats.extra_metrics:
                            progress_callback(
                                PipelineEvents.ERROR,
                                {
                                    "message": f"File {os.path.basename(input_path)}: {stage_stats.extra_metrics['user_message']}"
                                },
                            )

                # 发送步骤摘要事件 (for both successful and failed stages)
                for stage_stats in result.stage_stats:
                    progress_callback(
                        PipelineEvents.STEP_SUMMARY,
                        {
                            "step_name": stage_stats.stage_name,
                            "filename": os.path.basename(input_path),
                            "packets_processed": stage_stats.packets_processed,
                            "packets_modified": stage_stats.packets_modified,
                            "duration_ms": stage_stats.duration_ms,
                            **stage_stats.extra_metrics,
                        },
                    )

            except Exception as e:
                # Log the exception with full context
                logger.error(
                    f"[Service] Unexpected error processing file {input_path}: {e}",
                    exc_info=True,
                )

                # Send user-friendly error message to GUI
                progress_callback(
                    PipelineEvents.ERROR,
                    {
                        "message": f"Unexpected error processing file {os.path.basename(input_path)}: {str(e)}"
                    },
                )

            # 发送文件完成事件
            progress_callback(PipelineEvents.FILE_END, {"path": input_path})

        # 发送子目录结束事件
        progress_callback(PipelineEvents.SUBDIR_END, {"name": rel_subdir})

        # 发送管道结束事件
        progress_callback(PipelineEvents.PIPELINE_END, {})

        logger.info(f"[Service] Completed directory processing: {input_dir}")

    except Exception as e:
        logger.error(f"[Service] Directory processing failed: {e}")
        raise PipelineServiceError(f"Directory processing failed: {str(e)}")


def _handle_stage_progress(stage, stats, progress_callback):
    """处理阶段进度回调"""
    # Get standardized display name for the stage
    stage_display_name = _get_stage_display_name(stage.name)

    # Emit log with stage-specific action wording and correct statistics
    if stage.name in ["DeduplicationStage", "UnifiedDeduplicationStage"]:
        msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, removed {stats.packets_modified} pkts"
    elif stage.name in ["AnonStage", "IPAnonymizationStage", "UnifiedIPAnonymizationStage"]:
        # For IP anonymization, show IP statistics instead of packet statistics
        original_ips = getattr(stats, "original_ips", 0) or stats.extra_metrics.get(
            "original_ips", 0
        )
        anonymized_ips = getattr(stats, "anonymized_ips", 0) or stats.extra_metrics.get(
            "anonymized_ips", 0
        )
        if original_ips > 0:
            msg = f"- {stage_display_name}: processed {original_ips} IPs, anonymized {anonymized_ips} IPs"
        else:
            # Fallback to packet count if IP statistics are not available
            msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, anonymized {stats.packets_modified} IPs"
    else:
        msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, masked {stats.packets_modified} pkts"
    progress_callback(PipelineEvents.LOG, {"message": msg})


def _get_stage_display_name(stage_name: str) -> str:
    """Get standardized display name for stage based on naming consistency guide"""
    stage_name_mapping = {
        "DeduplicationStage": "Deduplication Stage",
        "UnifiedDeduplicationStage": "Deduplication Stage",  # New Unified implementation
        "AnonStage": "Anonymize IPs Stage",
        "IPAnonymizationStage": "Anonymize IPs Stage",  # Old StageBase implementation
        "UnifiedIPAnonymizationStage": "Anonymize IPs Stage",  # New Unified implementation
        "NewMaskPayloadStage": "Mask Payloads Stage",
        "MaskStage": "Mask Payloads Stage",
        "MaskPayloadStage": "Mask Payloads Stage",
        "Mask Payloads (v2)": "Mask Payloads Stage",
    }
    return stage_name_mapping.get(stage_name, stage_name)


# 停止管道执行
# Dummy implementation; replace ... with real logic


def stop_pipeline(executor: object) -> None:
    """停止管道执行"""
    try:
        # 尝试调用执行器的stop方法
        if hasattr(executor, "stop"):
            executor.stop()
            logger.info("[Service] Pipeline stopped")
        else:
            logger.warning("[Service] Executor does not support stop method")
    except Exception as e:
        logger.error(f"[Service] Failed to stop pipeline: {e}")
        raise PipelineServiceError(f"Failed to stop pipeline: {str(e)}")


# 返回当前执行器的统计信息
# Dummy implementation; replace ... with real logic


def get_pipeline_status(executor: object) -> Dict[str, Any]:
    """返回当前执行器的统计信息，例如已处理文件数等"""
    return {}


# 在真正创建执行器前验证配置
# Dummy implementation; replace ... with real logic


def validate_config(config: Dict) -> Tuple[bool, Optional[str]]:
    """验证配置有效性"""
    if not config:
        return False, "Configuration is empty"
    return True, None


# 根据功能开关构建管道配置
# Dummy implementation; replace ... with real logic


def build_pipeline_config(
    enable_anon: bool, enable_dedup: bool, enable_mask: bool
) -> Dict:
    """Build pipeline configuration based on feature switches (using standard naming conventions)"""
    # 使用统一的配置服务
    from pktmask.services.config_service import get_config_service

    service = get_config_service()
    options = service.create_options_from_gui(
        dedup_checked=enable_dedup, anon_checked=enable_anon, mask_checked=enable_mask
    )

    return service.build_pipeline_config(options)


# ============================================================================
# CLI 统一服务接口
# ============================================================================


def process_single_file(
    executor: object,
    input_file: str,
    output_file: str,
    progress_callback: Optional[Callable[[PipelineEvents, Dict], None]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    处理单个文件（CLI专用接口）

    Args:
        executor: 执行器对象
        input_file: 输入文件路径
        output_file: 输出文件路径
        progress_callback: 进度回调函数
        verbose: 是否启用详细输出

    Returns:
        处理结果字典，包含统计信息和状态
    """
    try:
        logger.info(f"[Service] Processing single file: {input_file}")

        # 确保输出目录存在
        from pathlib import Path

        output_path = Path(output_file)
        output_dir = output_path.parent

        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"[Service] Created output directory: {output_dir}")
            except Exception as e:
                logger.error(
                    f"[Service] Failed to create output directory {output_dir}: {e}"
                )
                raise PipelineServiceError(
                    f"Failed to create output directory: {str(e)}"
                )

        # 发送处理开始事件
        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_START, {"total_files": 1})
            progress_callback(PipelineEvents.FILE_START, {"path": input_file})

        # 创建进度回调包装器
        def stage_progress_wrapper(stage, stats):
            if progress_callback:
                _handle_stage_progress(stage, stats, progress_callback)

        # 执行处理
        result = executor.run(
            input_file,
            output_file,
            progress_cb=stage_progress_wrapper if verbose else None,
        )

        # 发送处理完成事件
        if progress_callback:
            progress_callback(
                PipelineEvents.FILE_END,
                {
                    "path": input_file,
                    "output_path": output_file,
                    "success": result.success,
                },
            )
            progress_callback(PipelineEvents.PIPELINE_END, {})

        # 返回统一格式的结果
        return {
            "success": result.success,
            "input_file": result.input_file,
            "output_file": result.output_file,
            "duration_ms": result.duration_ms,
            "stage_stats": [
                stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__
                for stats in result.stage_stats
            ],
            "errors": result.errors,
            "total_files": 1,
            "processed_files": 1 if result.success else 0,
        }

    except Exception as e:
        logger.error(f"[Service] Failed to process single file: {e}")
        if progress_callback:
            progress_callback(PipelineEvents.ERROR, {"message": str(e)})
            progress_callback(PipelineEvents.PIPELINE_END, {})
        raise PipelineServiceError(f"Failed to process file: {str(e)}")


def process_directory_cli(
    executor: object,
    input_dir: str,
    output_dir: str,
    progress_callback: Optional[Callable[[PipelineEvents, Dict], None]] = None,
    verbose: bool = False,
    file_pattern: str = "*.pcap,*.pcapng",
) -> Dict[str, Any]:
    """
    处理目录中的所有文件（CLI专用接口）

    Args:
        executor: 执行器对象
        input_dir: 输入目录路径
        output_dir: 输出目录路径
        progress_callback: 进度回调函数
        verbose: 是否启用详细输出
        file_pattern: 文件匹配模式

    Returns:
        处理结果字典，包含统计信息和状态
    """
    try:
        import glob
        import os

        logger.info(f"[Service] Processing directory: {input_dir}")

        # 扫描匹配的文件
        pcap_files = []
        patterns = file_pattern.split(",")
        for pattern in patterns:
            pattern = pattern.strip()
            files = glob.glob(os.path.join(input_dir, pattern))
            pcap_files.extend(files)

        if not pcap_files:
            logger.warning(
                f"[Service] No matching files found in directory: {input_dir}"
            )
            return {
                "success": True,
                "input_dir": input_dir,
                "output_dir": output_dir,
                "duration_ms": 0.0,
                "total_files": 0,
                "processed_files": 0,
                "failed_files": 0,
                "errors": [],
            }

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 发送处理开始事件
        if progress_callback:
            progress_callback(
                PipelineEvents.PIPELINE_START, {"total_files": len(pcap_files)}
            )

        # 处理统计
        processed_files = 0
        failed_files = 0
        all_errors = []
        total_duration = 0.0

        # 处理每个文件
        for i, input_file in enumerate(pcap_files):
            try:
                # 构造输出文件名
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                ext = os.path.splitext(input_file)[1]
                output_file = os.path.join(output_dir, f"{base_name}_processed{ext}")

                # 处理单个文件
                result = process_single_file(
                    executor, input_file, output_file, progress_callback, verbose
                )

                if result["success"]:
                    processed_files += 1
                else:
                    failed_files += 1
                    all_errors.extend(result.get("errors", []))

                total_duration += result["duration_ms"]

            except Exception as e:
                failed_files += 1
                error_msg = f"Failed to process {input_file}: {str(e)}"
                all_errors.append(error_msg)
                logger.error(f"[Service] {error_msg}")

                if progress_callback:
                    progress_callback(PipelineEvents.ERROR, {"message": error_msg})

        # 发送处理完成事件
        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_END, {})

        # 返回统一格式的结果
        return {
            "success": failed_files == 0,
            "input_dir": input_dir,
            "output_dir": output_dir,
            "duration_ms": total_duration,
            "total_files": len(pcap_files),
            "processed_files": processed_files,
            "failed_files": failed_files,
            "errors": all_errors,
        }

    except Exception as e:
        logger.error(f"[Service] Failed to process directory: {e}")
        if progress_callback:
            progress_callback(PipelineEvents.ERROR, {"message": str(e)})
            progress_callback(PipelineEvents.PIPELINE_END, {})
        raise PipelineServiceError(f"Failed to process directory: {str(e)}")


def create_gui_compatible_report_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """创建与GUI兼容的报告数据格式"""
    # 转换CLI结果为GUI报告管理器期望的格式
    gui_report_data = {
        "step_results": {},
        "total_files": result.get("total_files", 1),
        "processed_files": result.get("processed_files", 0),
        "failed_files": result.get("failed_files", 0),
        "duration_ms": result.get("duration_ms", 0.0),
        "output_directory": result.get("output_dir") or result.get("output_file"),
        "success": result.get("success", False),
    }

    # 转换阶段统计数据
    stage_stats = result.get("stage_stats", [])
    for stage_stat in stage_stats:
        if isinstance(stage_stat, dict):
            stage_name = stage_stat.get("stage_name", "Unknown")

            # 映射到GUI期望的格式
            if "dedup" in stage_name.lower():
                gui_report_data["step_results"]["Deduplication"] = {
                    "packets_processed": stage_stat.get("packets_processed", 0),
                    "packets_modified": stage_stat.get("packets_modified", 0),
                    "duration_ms": stage_stat.get("duration_ms", 0.0),
                    "summary": f"Processed {stage_stat.get('packets_processed', 0)} packets, removed {stage_stat.get('packets_modified', 0)} duplicates",
                }
            elif "anon" in stage_name.lower() or "ip" in stage_name.lower():
                gui_report_data["step_results"]["Anonymize IPs"] = {
                    "packets_processed": stage_stat.get("packets_processed", 0),
                    "packets_modified": stage_stat.get("packets_modified", 0),
                    "ips_anonymized": stage_stat.get("packets_modified", 0),
                    "duration_ms": stage_stat.get("duration_ms", 0.0),
                    "summary": f"Anonymized {stage_stat.get('packets_modified', 0)} IP addresses",
                }
            elif "mask" in stage_name.lower() or "payload" in stage_name.lower():
                gui_report_data["step_results"]["Mask Payloads"] = {
                    "packets_processed": stage_stat.get("packets_processed", 0),
                    "packets_modified": stage_stat.get("packets_modified", 0),
                    "total_packets": stage_stat.get("packets_processed", 0),
                    "duration_ms": stage_stat.get("duration_ms", 0.0),
                    "summary": f"Masked {stage_stat.get('packets_modified', 0)} payload packets",
                    "data": {
                        "total_packets": stage_stat.get("packets_processed", 0),
                        "output_filename": result.get("output_file"),
                    },
                }

    return gui_report_data


def generate_gui_style_report(result: Dict[str, Any]) -> str:
    """生成GUI风格的报告文本"""
    gui_data = create_gui_compatible_report_data(result)

    # 使用GUI报告管理器的格式
    report_lines = []

    # 标题
    report_lines.append("=" * 70)
    report_lines.append("📋 PROCESSING SUMMARY")
    report_lines.append("=" * 70)
    report_lines.append("")

    # 基本信息
    report_lines.append(
        f"📊 Files Processed: {gui_data['processed_files']}/{gui_data['total_files']}"
    )
    if gui_data["failed_files"] > 0:
        report_lines.append(f"❌ Failed Files: {gui_data['failed_files']}")
    report_lines.append(f"⏱️  Total Duration: {gui_data['duration_ms']:.1f} ms")
    report_lines.append("")

    # 阶段结果
    if gui_data["step_results"]:
        report_lines.append("📈 Step Statistics:")
        report_lines.append("")

        for step_name, step_data in gui_data["step_results"].items():
            report_lines.append(f"🔧 {step_name}:")
            report_lines.append(
                f"  • Packets Processed: {step_data.get('packets_processed', 0):,}"
            )
            report_lines.append(
                f"  • Packets Modified: {step_data.get('packets_modified', 0):,}"
            )
            report_lines.append(
                f"  • Duration: {step_data.get('duration_ms', 0.0):.1f} ms"
            )
            if "summary" in step_data:
                report_lines.append(f"  • Summary: {step_data['summary']}")
            report_lines.append("")

    # 输出信息
    if gui_data["output_directory"]:
        report_lines.append(f"📁 Output: {gui_data['output_directory']}")
        report_lines.append("")

    # 状态
    status = "✅ Success" if gui_data["success"] else "❌ Failed"
    report_lines.append(f"Status: {status}")

    return "\n".join(report_lines)
