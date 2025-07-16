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
        logger.info(f"[Service] Starting directory processing: {input_dir}")
        
        # 发送管道开始事件
        progress_callback(PipelineEvents.PIPELINE_START, {'total_subdirs': 1})
        
        # 扫描目录中的PCAP文件
        pcap_files = []
        for file in os.scandir(input_dir):
            if file.name.endswith(('.pcap', '.pcapng')):
                pcap_files.append(file.path)
        
        if not pcap_files:
            progress_callback(PipelineEvents.LOG, {'message': 'No PCAP files found in directory'})
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
        
        # 处理每个文件
        for input_path in pcap_files:
            if not is_running_check():
                break
                
            # 发送文件开始事件
            progress_callback(PipelineEvents.FILE_START, {'path': input_path})
            
            try:
                # 构造输出文件名
                base_name, ext = os.path.splitext(os.path.basename(input_path))
                output_path = os.path.join(output_dir, f"{base_name}_processed{ext}")
                
                # 使用 executor 处理文件
                result = executor.run(input_path, output_path, progress_cb=lambda stage, stats: _handle_stage_progress(stage, stats, progress_callback))
                
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
                progress_callback(PipelineEvents.ERROR, {
                    'message': f"Error processing file {os.path.basename(input_path)}: {str(e)}"
                })
            
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
    """处理阶段进度回调"""
    # Get standardized display name for the stage
    stage_display_name = _get_stage_display_name(stage.name)

    # Emit log with stage-specific action wording and correct statistics
    if stage.name == 'DedupStage' or stage.name == 'DeduplicationStage':
        msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, removed {stats.packets_modified} pkts"
    elif stage.name == 'AnonStage':
        # For IP anonymization, show IP statistics instead of packet statistics
        original_ips = getattr(stats, 'original_ips', 0) or stats.extra_metrics.get('original_ips', 0)
        anonymized_ips = getattr(stats, 'anonymized_ips', 0) or stats.extra_metrics.get('anonymized_ips', 0)
        if original_ips > 0:
            msg = f"- {stage_display_name}: processed {original_ips} IPs, anonymized {anonymized_ips} IPs"
        else:
            # Fallback to packet count if IP statistics are not available
            msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, anonymized {stats.packets_modified} IPs"
    else:
        msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, masked {stats.packets_modified} pkts"
    progress_callback(PipelineEvents.LOG, {'message': msg})


def _get_stage_display_name(stage_name: str) -> str:
    """Get standardized display name for stage based on naming consistency guide"""
    stage_name_mapping = {
        'DedupStage': 'Deduplication Stage',
        'DeduplicationStage': 'Deduplication Stage',
        'AnonStage': 'IP Anonymization Stage',
        'NewMaskPayloadStage': 'Payload Masking Stage',
        'MaskStage': 'Payload Masking Stage',
        'MaskPayloadStage': 'Payload Masking Stage',
        'Mask Payloads (v2)': 'Payload Masking Stage'
    }
    return stage_name_mapping.get(stage_name, stage_name)

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

