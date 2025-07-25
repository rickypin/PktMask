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


def _process_files_common(
    executor: object,
    pcap_files: list,
    output_dir: str,
    progress_callback: Optional[Callable[[PipelineEvents, Dict], None]] = None,
    is_running_check: Optional[Callable[[], bool]] = None,
    verbose: bool = False,
    interface_type: str = "gui"
) -> Dict[str, Any]:
    """
    Common file processing logic shared between GUI and CLI interfaces

    Args:
        executor: 执行器对象
        pcap_files: PCAP文件列表
        output_dir: 输出目录路径
        progress_callback: 进度回调函数
        is_running_check: 检查是否继续运行的函数 (GUI only)
        verbose: 是否启用详细输出 (CLI only)
        interface_type: 接口类型 ("gui" or "cli")

    Returns:
        处理结果字典，包含统计信息和状态
    """
    import os

    # 处理统计
    processed_files = 0
    failed_files = 0
    all_errors = []
    total_duration = 0.0
    all_stage_stats = []

    # 处理每个文件
    for input_path in pcap_files:
        # Check for interruption (GUI only)
        if is_running_check and not is_running_check():
            break

        # 发送文件开始事件
        if progress_callback:
            progress_callback(PipelineEvents.FILE_START, {"path": input_path})

        try:
            # 构造输出文件名
            base_name, ext = os.path.splitext(os.path.basename(input_path))
            output_path = os.path.join(output_dir, f"{base_name}_processed{ext}")

            # 使用 executor 处理文件
            if interface_type == "gui":
                # GUI直接调用executor.run
                result = executor.run(
                    input_path,
                    output_path,
                    progress_cb=lambda stage, stats: _handle_stage_progress(
                        stage, stats, progress_callback
                    ),
                )
            else:
                # CLI通过process_single_file调用
                single_result = process_single_file(
                    executor, input_path, output_path, progress_callback, verbose
                )
                # 转换为executor.run的结果格式以保持一致性
                class MockResult:
                    def __init__(self, single_result):
                        self.success = single_result["success"]
                        self.errors = single_result.get("errors", [])
                        self.stage_stats = single_result.get("stage_stats", [])
                        self.duration_ms = single_result.get("duration_ms", 0.0)

                result = MockResult(single_result)

            # 处理结果统计
            if result.success:
                processed_files += 1
            else:
                failed_files += 1
                all_errors.extend(result.errors)

            total_duration += getattr(result, 'duration_ms', 0.0)

            # GUI特定的错误和步骤处理
            if interface_type == "gui":
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
                        if hasattr(stage_stats, 'extra_metrics') and "user_message" in stage_stats.extra_metrics:
                            progress_callback(
                                PipelineEvents.ERROR,
                                {
                                    "message": f"File {os.path.basename(input_path)}: {stage_stats.extra_metrics['user_message']}"
                                },
                            )

                # 发送步骤摘要事件 (for both successful and failed stages)
                for stage_stats in result.stage_stats:
                    if hasattr(stage_stats, 'stage_name'):
                        progress_callback(
                            PipelineEvents.STEP_SUMMARY,
                            {
                                "step_name": stage_stats.stage_name,
                                "filename": os.path.basename(input_path),
                                "packets_processed": getattr(stage_stats, 'packets_processed', 0),
                                "packets_modified": getattr(stage_stats, 'packets_modified', 0),
                                "duration_ms": getattr(stage_stats, 'duration_ms', 0.0),
                                **(stage_stats.extra_metrics if hasattr(stage_stats, 'extra_metrics') else {}),
                            },
                        )

            # 收集stage统计信息
            if hasattr(result, 'stage_stats'):
                all_stage_stats.extend(result.stage_stats)

        except Exception as e:
            failed_files += 1
            error_msg = f"Failed to process {input_path}: {str(e)}"
            all_errors.append(error_msg)

            # Log the exception with full context
            logger.error(f"[Service] Unexpected error processing file {input_path}: {e}", exc_info=True)

            # Send user-friendly error message
            if progress_callback:
                if interface_type == "gui":
                    progress_callback(
                        PipelineEvents.ERROR,
                        {
                            "message": f"Unexpected error processing file {os.path.basename(input_path)}: {str(e)}"
                        },
                    )
                else:
                    progress_callback(PipelineEvents.ERROR, {"message": error_msg})

        # 发送文件完成事件
        if progress_callback:
            progress_callback(PipelineEvents.FILE_END, {"path": input_path})

    return {
        "processed_files": processed_files,
        "failed_files": failed_files,
        "errors": all_errors,
        "total_duration": total_duration,
        "stage_stats": all_stage_stats,
        "total_files": len(pcap_files)
    }


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

        # 扫描目录中的PCAP文件 (GUI-specific file discovery)
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

        # 发送子目录开始事件 (GUI-specific)
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

        # 使用共同的文件处理逻辑
        _process_files_common(
            executor=executor,
            pcap_files=pcap_files,
            output_dir=output_dir,
            progress_callback=progress_callback,
            is_running_check=is_running_check,
            verbose=True,  # GUI always wants detailed progress
            interface_type="gui"
        )

        # 发送子目录结束事件 (GUI-specific)
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
    elif stage.name in ["AnonStage", "IPAnonymizationStage", "UnifiedIPAnonymizationStage", "AnonymizationStage"]:
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
        "AnonymizationStage": "Anonymize IPs Stage",  # Standardized naming
        "NewMaskPayloadStage": "Mask Payloads Stage",
        "MaskStage": "Mask Payloads Stage",
        "MaskPayloadStage": "Mask Payloads Stage",
        "MaskingStage": "Mask Payloads Stage",  # Standardized naming
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
    anonymize_ips: bool, remove_dupes: bool, mask_payloads: bool
) -> Dict:
    """Build pipeline configuration based on feature switches (using standard naming conventions)"""
    # Use unified configuration service
    from pktmask.services.config_service import get_config_service

    service = get_config_service()
    options = service.create_options_from_gui(
        remove_dupes_checked=remove_dupes, anonymize_ips_checked=anonymize_ips, mask_payloads_checked=mask_payloads
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

        # 扫描匹配的文件 (CLI-specific file discovery with glob)
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

        # 发送处理开始事件 (CLI-specific)
        if progress_callback:
            progress_callback(
                PipelineEvents.PIPELINE_START, {"total_files": len(pcap_files)}
            )

        # 使用共同的文件处理逻辑
        result = _process_files_common(
            executor=executor,
            pcap_files=pcap_files,
            output_dir=output_dir,
            progress_callback=progress_callback,
            is_running_check=None,  # CLI doesn't support interruption
            verbose=verbose,
            interface_type="cli"
        )

        # 发送处理完成事件
        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_END, {})

        # 返回CLI期望的格式
        return {
            "success": result["failed_files"] == 0,
            "input_dir": input_dir,
            "output_dir": output_dir,
            "duration_ms": result["total_duration"],
            "total_files": result["total_files"],
            "processed_files": result["processed_files"],
            "failed_files": result["failed_files"],
            "errors": result["errors"],
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
