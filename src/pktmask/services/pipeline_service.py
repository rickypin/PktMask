"""
Pipeline 服务接口
提供 GUI 与核心管道的解耦接口
"""
from typing import Dict, Callable, Optional, Tuple, Any
from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger

# 定义服务层异常
class PipelineServiceError(Exception):
    """服务层基础异常"""
    pass

class ConfigurationError(PipelineServiceError):
    """配置错误"""
    pass

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
    is_running_check: Callable[[], bool]
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
        import platform
        from pathlib import Path

        logger.info(f"[Service] Starting directory processing: {input_dir}")

        # Log directory scanning start
        progress_callback(PipelineEvents.LOG, {'message': '📂 Directory Scanning Started'})
        progress_callback(PipelineEvents.LOG, {'message': f' - Input Directory: {input_dir}'})
        progress_callback(PipelineEvents.LOG, {'message': f' - Output Directory: {output_dir}'})
        progress_callback(PipelineEvents.LOG, {'message': f' - Platform: {platform.system()}'})

        # 发送管道开始事件
        progress_callback(PipelineEvents.PIPELINE_START, {'total_subdirs': 1})

        # Enhanced directory scanning with comprehensive logging
        pcap_files = []
        scan_errors = []

        try:
            # Check if input directory exists and is accessible
            input_path = Path(input_dir)
            if not input_path.exists():
                error_msg = f"Input directory does not exist: {input_dir}"
                progress_callback(PipelineEvents.LOG, {'message': f'❌ {error_msg}'})
                raise FileNotFoundError(error_msg)

            if not input_path.is_dir():
                error_msg = f"Input path is not a directory: {input_dir}"
                progress_callback(PipelineEvents.LOG, {'message': f'❌ {error_msg}'})
                raise NotADirectoryError(error_msg)

            # Log directory access permissions on Windows
            if platform.system() == "Windows":
                try:
                    # Test directory access
                    list(input_path.iterdir())
                    progress_callback(PipelineEvents.LOG, {'message': ' - Directory access: ✅ Readable'})
                except PermissionError as e:
                    progress_callback(PipelineEvents.LOG, {'message': f' - Directory access: ❌ Permission denied: {e}'})
                    scan_errors.append(f"Permission denied: {e}")
                except Exception as e:
                    progress_callback(PipelineEvents.LOG, {'message': f' - Directory access: ❌ Access error: {e}'})
                    scan_errors.append(f"Access error: {e}")

            # Scan for PCAP/PCAPNG files
            progress_callback(PipelineEvents.LOG, {'message': ' - Scanning for pcap/pcapng files...'})

            for file in os.scandir(input_dir):
                try:
                    if file.name.endswith(('.pcap', '.pcapng')):
                        file_path = file.path
                        file_size = file.stat().st_size if file.is_file() else 0

                        # Log each discovered file with details
                        size_mb = file_size / (1024 * 1024)
                        progress_callback(PipelineEvents.LOG, {
                            'message': f' - Found: {file.name} ({size_mb:.2f} MB)'
                        })

                        # Windows-specific file path encoding check
                        if platform.system() == "Windows":
                            try:
                                # Test file path encoding
                                encoded_path = file_path.encode('utf-8').decode('utf-8')
                                if encoded_path != file_path:
                                    progress_callback(PipelineEvents.LOG, {
                                        'message': f' - Path encoding issue detected for: {file.name}'
                                    })
                            except UnicodeError as e:
                                progress_callback(PipelineEvents.LOG, {
                                    'message': f' - Path encoding error for {file.name}: {e}'
                                })
                                scan_errors.append(f"Path encoding error for {file.name}: {e}")
                                continue

                        pcap_files.append(file_path)

                except Exception as e:
                    error_msg = f"Error accessing file {file.name}: {e}"
                    progress_callback(PipelineEvents.LOG, {'message': f' - ❌ {error_msg}'})
                    scan_errors.append(error_msg)
                    continue

        except Exception as e:
            error_msg = f"Directory scanning failed: {e}"
            progress_callback(PipelineEvents.LOG, {'message': f'❌ {error_msg}'})
            logger.error(f"[Service] {error_msg}")
            raise PipelineServiceError(error_msg)

        # Log scanning results
        progress_callback(PipelineEvents.LOG, {'message': '📊 Directory Scanning Completed'})
        progress_callback(PipelineEvents.LOG, {'message': f' - Total files found: {len(pcap_files)}'})

        if scan_errors:
            progress_callback(PipelineEvents.LOG, {'message': f' - Scan errors: {len(scan_errors)}'})
            for error in scan_errors[:5]:  # Show first 5 errors
                progress_callback(PipelineEvents.LOG, {'message': f'   • {error}'})
            if len(scan_errors) > 5:
                progress_callback(PipelineEvents.LOG, {'message': f'   • ... and {len(scan_errors) - 5} more errors'})

        if not pcap_files:
            progress_callback(PipelineEvents.LOG, {'message': '⚠️ No valid pcap/pcapng files found in directory'})
            progress_callback(PipelineEvents.PIPELINE_END, {})
            return
        
        # 发送子目录开始事件
        rel_subdir = os.path.relpath(input_dir, input_dir)
        progress_callback(PipelineEvents.SUBDIR_START, {
            'name': rel_subdir,
            'current': 1,
            'total': 1,
            'file_count': len(pcap_files)
        })

        # Log file processing pipeline start
        progress_callback(PipelineEvents.LOG, {'message': '🔄 File Processing Pipeline Started'})

        # 处理每个文件
        for file_index, input_path in enumerate(pcap_files, 1):
            if not is_running_check():
                progress_callback(PipelineEvents.LOG, {'message': '⏹️ Processing stopped by user'})
                break

            # 发送文件开始事件
            progress_callback(PipelineEvents.FILE_START, {'path': input_path})

            # Log file processing start with details
            file_name = os.path.basename(input_path)
            progress_callback(PipelineEvents.LOG, {
                'message': f'📄 Processing file {file_index}/{len(pcap_files)}: {file_name}'
            })

            try:
                # Log input file details
                input_file_size = os.path.getsize(input_path)
                size_mb = input_file_size / (1024 * 1024)
                progress_callback(PipelineEvents.LOG, {
                    'message': f' - Input size: {size_mb:.2f} MB'
                })

                # 构造输出文件名
                base_name, ext = os.path.splitext(os.path.basename(input_path))
                output_path = os.path.join(output_dir, f"{base_name}_processed{ext}")

                # Log output file path
                progress_callback(PipelineEvents.LOG, {
                    'message': f' - Output path: {os.path.basename(output_path)}'
                })

                # Windows-specific file operation logging
                if platform.system() == "Windows":
                    try:
                        # Check input file permissions
                        if os.access(input_path, os.R_OK):
                            progress_callback(PipelineEvents.LOG, {
                                'message': ' - Input file access: ✅ Readable'
                            })
                        else:
                            progress_callback(PipelineEvents.LOG, {
                                'message': ' - Input file access: ❌ Not readable'
                            })
                            raise PermissionError(f"Cannot read input file: {input_path}")

                        # Check output directory permissions
                        output_dir_path = Path(output_dir)
                        if output_dir_path.exists():
                            if os.access(output_dir, os.W_OK):
                                progress_callback(PipelineEvents.LOG, {
                                    'message': ' - Output directory access: ✅ Writable'
                                })
                            else:
                                progress_callback(PipelineEvents.LOG, {
                                    'message': ' - Output directory access: ❌ Not writable'
                                })
                                raise PermissionError(f"Cannot write to output directory: {output_dir}")
                        else:
                            # Try to create output directory
                            try:
                                output_dir_path.mkdir(parents=True, exist_ok=True)
                                progress_callback(PipelineEvents.LOG, {
                                    'message': ' - Output directory: ✅ Created successfully'
                                })
                            except Exception as e:
                                progress_callback(PipelineEvents.LOG, {
                                    'message': f' - Output directory creation: ❌ Failed: {e}'
                                })
                                raise

                    except Exception as e:
                        progress_callback(PipelineEvents.LOG, {
                            'message': f' - Windows file operation check failed: {e}'
                        })
                        raise

                # Log processing stages start
                progress_callback(PipelineEvents.LOG, {'message': ' - Starting processing stages...'})

                # 使用 executor 处理文件
                result = executor.run(input_path, output_path, progress_cb=lambda stage, stats: _handle_stage_progress(stage, stats, progress_callback))

                # Log processing completion with output file details
                if os.path.exists(output_path):
                    output_file_size = os.path.getsize(output_path)
                    output_size_mb = output_file_size / (1024 * 1024)
                    size_reduction = ((input_file_size - output_file_size) / input_file_size * 100) if input_file_size > 0 else 0

                    progress_callback(PipelineEvents.LOG, {
                        'message': f' - ✅ Output created: {output_size_mb:.2f} MB (reduction: {size_reduction:.1f}%)'
                    })
                else:
                    progress_callback(PipelineEvents.LOG, {
                        'message': ' - ❌ Output file was not created'
                    })

                # 发送步骤摘要事件
                for stage_stats in result.stage_stats:
                    progress_callback(PipelineEvents.STEP_SUMMARY, {
                        'step_name': stage_stats.stage_name,
                        'filename': os.path.basename(input_path),
                        'packets_processed': stage_stats.packets_processed,
                        'packets_modified': stage_stats.packets_modified,
                        'duration_ms': stage_stats.duration_ms,
                        **stage_stats.extra_metrics
                    })

            except Exception as e:
                error_msg = f"Error processing file {os.path.basename(input_path)}: {str(e)}"
                progress_callback(PipelineEvents.LOG, {'message': f' - ❌ {error_msg}'})
                progress_callback(PipelineEvents.ERROR, {'message': error_msg})
                logger.error(f"[Service] {error_msg}", exc_info=True)

            # 发送文件完成事件
            progress_callback(PipelineEvents.FILE_END, {'path': input_path})
        
        # 发送子目录结束事件
        progress_callback(PipelineEvents.SUBDIR_END, {'name': rel_subdir})
        
        # 发送管道结束事件
        progress_callback(PipelineEvents.PIPELINE_END, {})
        
        logger.info(f"[Service] Completed directory processing: {input_dir}")
        
    except Exception as e:
        logger.error(f"[Service] Directory processing failed: {e}")
        raise PipelineServiceError(f"Directory processing failed: {str(e)}")

def _handle_stage_progress(stage, stats, progress_callback):
    """处理阶段进度回调 - Enhanced with comprehensive logging"""
    # Get standardized display name for the stage
    stage_display_name = _get_stage_display_name(stage.name)

    # Log stage start
    progress_callback(PipelineEvents.LOG, {'message': f'   🔧 {stage_display_name} started'})

    # Log stage completion with detailed statistics
    duration_sec = stats.duration_ms / 1000.0

    # Stage-specific logging with standardized naming
    if stage.name == 'DedupStage' or stage.name == 'DeduplicationStage':
        # Remove Dupes stage
        duplicate_rate = (stats.packets_modified / stats.packets_processed * 100) if stats.packets_processed > 0 else 0
        msg = f"   ✅ Remove Dupes: processed {stats.packets_processed:,} packets, removed {stats.packets_modified:,} duplicates ({duplicate_rate:.1f}%)"

        # Log additional deduplication metrics if available
        if hasattr(stats, 'extra_metrics') and stats.extra_metrics:
            if 'unique_packets' in stats.extra_metrics:
                unique_count = stats.extra_metrics['unique_packets']
                msg += f", {unique_count:,} unique packets retained"

    elif stage.name == 'AnonStage':
        # Anonymize IPs stage
        original_ips = getattr(stats, 'original_ips', 0) or stats.extra_metrics.get('original_ips', 0)
        anonymized_ips = getattr(stats, 'anonymized_ips', 0) or stats.extra_metrics.get('anonymized_ips', 0)

        if original_ips > 0:
            anon_rate = (anonymized_ips / original_ips * 100) if original_ips > 0 else 0
            msg = f"   ✅ Anonymize IPs: processed {original_ips:,} unique IPs, anonymized {anonymized_ips:,} IPs ({anon_rate:.1f}%)"
        else:
            # Fallback to packet count if IP statistics are not available
            msg = f"   ✅ Anonymize IPs: processed {stats.packets_processed:,} packets, modified {stats.packets_modified:,} packets"

        # Log IP mapping statistics if available
        if hasattr(stats, 'extra_metrics') and stats.extra_metrics:
            if 'ipv4_count' in stats.extra_metrics and 'ipv6_count' in stats.extra_metrics:
                ipv4_count = stats.extra_metrics['ipv4_count']
                ipv6_count = stats.extra_metrics['ipv6_count']
                msg += f" (IPv4: {ipv4_count:,}, IPv6: {ipv6_count:,})"

    else:
        # Mask Payloads stage (including various mask stage names)
        if stats.packets_processed > 0:
            mask_rate = (stats.packets_modified / stats.packets_processed * 100)
            msg = f"   ✅ Mask Payloads: processed {stats.packets_processed:,} packets, masked {stats.packets_modified:,} packets ({mask_rate:.1f}%)"
        else:
            msg = f"   ✅ Mask Payloads: processed {stats.packets_processed:,} packets, no masking applied"

        # Log masking-specific metrics if available
        if hasattr(stats, 'extra_metrics') and stats.extra_metrics:
            if 'tls_messages_found' in stats.extra_metrics:
                tls_count = stats.extra_metrics['tls_messages_found']
                msg += f", {tls_count:,} TLS messages analyzed"
            if 'bytes_masked' in stats.extra_metrics:
                bytes_masked = stats.extra_metrics['bytes_masked']
                mb_masked = bytes_masked / (1024 * 1024)
                msg += f", {mb_masked:.2f} MB masked"

    # Add timing information
    msg += f" ({duration_sec:.2f}s)"

    # Log the main stage completion message
    progress_callback(PipelineEvents.LOG, {'message': msg})

    # Log any errors or warnings from the stage
    if hasattr(stats, 'extra_metrics') and stats.extra_metrics:
        if 'errors' in stats.extra_metrics and stats.extra_metrics['errors']:
            error_count = len(stats.extra_metrics['errors'])
            progress_callback(PipelineEvents.LOG, {
                'message': f'   ⚠️ Stage completed with {error_count} error(s)'
            })
            # Log first few errors
            for i, error in enumerate(stats.extra_metrics['errors'][:3]):
                progress_callback(PipelineEvents.LOG, {
                    'message': f'     • Error {i+1}: {error}'
                })
            if error_count > 3:
                progress_callback(PipelineEvents.LOG, {
                    'message': f'     • ... and {error_count - 3} more errors'
                })

        if 'warnings' in stats.extra_metrics and stats.extra_metrics['warnings']:
            warning_count = len(stats.extra_metrics['warnings'])
            progress_callback(PipelineEvents.LOG, {
                'message': f'   ⚠️ Stage completed with {warning_count} warning(s)'
            })
            # Log first few warnings
            for i, warning in enumerate(stats.extra_metrics['warnings'][:2]):
                progress_callback(PipelineEvents.LOG, {
                    'message': f'     • Warning {i+1}: {warning}'
                })
            if warning_count > 2:
                progress_callback(PipelineEvents.LOG, {
                    'message': f'     • ... and {warning_count - 2} more warnings'
                })

    # Log performance metrics if available
    if hasattr(stats, 'extra_metrics') and stats.extra_metrics:
        if 'throughput_mbps' in stats.extra_metrics:
            throughput = stats.extra_metrics['throughput_mbps']
            progress_callback(PipelineEvents.LOG, {
                'message': f'   📊 Throughput: {throughput:.1f} MB/s'
            })


def _get_stage_display_name(stage_name: str) -> str:
    """Get standardized display name for stage based on PktMask naming conventions"""
    # Use standardized naming: Remove Dupes, Anonymize IPs, Mask Payloads
    stage_name_mapping = {
        'DedupStage': 'Remove Dupes',
        'DeduplicationStage': 'Remove Dupes',
        'AnonStage': 'Anonymize IPs',
        'AnonymizeStage': 'Anonymize IPs',
        'NewMaskPayloadStage': 'Mask Payloads',
        'MaskStage': 'Mask Payloads',
        'MaskPayloadStage': 'Mask Payloads',
        'Mask Payloads (v2)': 'Mask Payloads',
        # Legacy naming support
        'Trim Packets': 'Remove Dupes',
        'Mask IP': 'Anonymize IPs',
        'Remove Duplicates': 'Remove Dupes'
    }
    return stage_name_mapping.get(stage_name, stage_name)


def format_log_message(message: str, level: int = 0, emoji: str = "") -> str:
    """
    Format log message according to PktMask standards

    Args:
        message: The log message content
        level: Indentation level (0=main, 1=sub-item, 2=detail)
        emoji: Optional emoji prefix

    Returns:
        Formatted log message with proper indentation
    """
    # PktMask standard: 1 space + 1 dash indentation for stage messages
    indent_map = {
        0: "",           # Main messages (no indent)
        1: " - ",        # Sub-items (1 space + 1 dash + 1 space)
        2: "   • ",      # Details (3 spaces + bullet + 1 space)
        3: "     ◦ "     # Sub-details (5 spaces + circle + 1 space)
    }

    indent = indent_map.get(level, " - ")
    emoji_prefix = f"{emoji} " if emoji else ""

    return f"{emoji_prefix}{indent}{message}" if level > 0 else f"{emoji_prefix}{message}"


def log_stage_message(progress_callback, message: str, level: int = 1, emoji: str = "") -> None:
    """
    Log a stage message with standardized formatting

    Args:
        progress_callback: The progress callback function
        message: The message content
        level: Indentation level
        emoji: Optional emoji
    """
    formatted_msg = format_log_message(message, level, emoji)
    progress_callback(PipelineEvents.LOG, {'message': formatted_msg})

# 停止管道执行
# Dummy implementation; replace ... with real logic

def stop_pipeline(executor: object) -> None:
    """停止管道执行"""
    try:
        # 尝试调用执行器的stop方法
        if hasattr(executor, 'stop'):
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
    enable_anon: bool,
    enable_dedup: bool,
    enable_mask: bool
) -> Dict:
    """Build pipeline configuration based on feature switches (using standard naming conventions)"""
    config: Dict[str, Dict] = {}
    if enable_anon:
        config["anonymize_ips"] = {"enabled": True}
    if enable_dedup:
        config["remove_dupes"] = {"enabled": True}
    if enable_mask:
        config["mask_payloads"] = {
            "enabled": True,
            "protocol": "tls",  # Protocol type
            "mode": "enhanced",  # Use enhanced mode
            "marker_config": {
                "preserve": {                    # Fix: Add preserve nested level
                    "application_data": False,   # TLSProtocolMarker expected configuration structure
                    "handshake": True,
                    "alert": True,
                    "change_cipher_spec": True,
                    "heartbeat": True
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
    return config

