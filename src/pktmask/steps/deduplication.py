import os
from scapy.all import PcapReader, PcapNgReader, wrpcap
from typing import Optional, Dict

from ..core.base_step import ProcessingStep
from ..core.events import PipelineEvents
from ..utils.file_selector import select_files
from ..utils.time import current_time
from ..common.constants import ProcessingConstants
from ..infrastructure.logging import get_logger


def process_file_dedup(file_path, error_log):
    """
    处理单个 pcap/pcapng 文件，去除完全重复的报文。
    参数：
      file_path：待处理的文件路径；
      error_log：用于记录错误信息的列表。
    返回：
      去重后的报文列表，以及原文件中报文的总数与去重后报文的数量。
    """
    packets = []
    total_count = 0
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pcap":
            reader_cls = PcapReader
        elif ext == ".pcapng":
            reader_cls = PcapNgReader
        else:
            raise ValueError("不支持的文件扩展名")
        seen = set()
        with reader_cls(file_path) as reader:
            for pkt in reader:
                total_count += 1
                raw_bytes = bytes(pkt)
                if raw_bytes in seen:
                    continue
                seen.add(raw_bytes)
                packets.append(pkt)
        return packets, total_count, len(packets)
    except Exception as e:
        error_log.append(f"处理文件 {file_path} 出错：{str(e)}")
        return None, total_count, 0

class DeduplicationStep(ProcessingStep):
    """
    去重处理步骤
    """
    suffix: str = ProcessingConstants.DEDUP_PACKET_SUFFIX

    def __init__(self):
        super().__init__()
        self._logger = get_logger('deduplication')

    @property
    def name(self) -> str:
        return "Remove Dupes"
        
    def process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """
        处理单个 pcap/pcap ng 文件，去除完全重复的报文。
        """
        import time
        from ..infrastructure.logging import log_performance
        
        start_time = time.time()
        
        self._logger.debug(f"开始去重处理: {input_path}")
        packets = []
        total_count = 0
        
        ext = os.path.splitext(input_path)[1].lower()
        reader_cls = PcapNgReader if ext == ".pcapng" else PcapReader

        seen_packets = set()
        with reader_cls(input_path) as reader:
            for pkt in reader:
                total_count += 1
                # 使用数据包的原始字节作为唯一标识符
                raw_bytes = bytes(pkt)
                if raw_bytes not in seen_packets:
                    seen_packets.add(raw_bytes)
                    packets.append(pkt)
        
        # 确保输出文件的目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        wrpcap(output_path, packets, append=False)
        
        unique_count = len(packets)
        removed_count = total_count - unique_count
        
        # 记录性能指标
        end_time = time.time()
        duration = end_time - start_time
        log_performance('deduplication_process_file', duration, 'deduplication.performance',
                       total_packets=total_count, unique_packets=unique_count, 
                       removed_packets=removed_count)
        
        self._logger.info(f"去重完成: {input_path} -> {output_path}, 移除重复包: {removed_count}/{total_count}, 耗时={duration:.2f}秒")
        
        summary = {
            'subdir': os.path.basename(os.path.dirname(input_path)),
            'input_filename': os.path.basename(input_path),
            'output_filename': os.path.basename(output_path),
            'total_packets': total_count,
            'unique_packets': unique_count,
            'removed_count': total_count - unique_count,
        }
        return summary

    def process_directory(self, subdir_path: str, base_path: str = None, progress_callback=None, all_suffixes=None):
        def log(level, message):
            if progress_callback:
                progress_callback(PipelineEvents.LOG, {'level': level, 'message': message})

        if base_path is None:
            base_path = os.path.dirname(subdir_path)
        
        rel_subdir = os.path.relpath(subdir_path, base_path)
        
        files_to_process, reason = select_files(subdir_path, self.suffix, all_suffixes or [])
        
        if not files_to_process:
            log('info', f"[Dedup] In '{rel_subdir}': {reason}")
            return

        log('info', f"[Dedup] In '{rel_subdir}': Found {len(files_to_process)} files to process. Reason: {reason}")
        
        error_log = []
        total_packets_subdir = 0
        total_unique_packets_subdir = 0
        processed_files_count = 0

        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            rel_file_path = os.path.relpath(file_path, base_path)

            log('info', f"[Dedup] Processing: {rel_file_path}")
            
            packets, total, deduped = process_file_dedup(file_path, error_log)

            if packets is None:
                log('error', f"[Dedup] Error processing {rel_file_path}, skipped.")
                continue

            base, ext = os.path.splitext(file_path)
            if not base.endswith(self.suffix):
                new_file_path = f"{base}{self.suffix}{ext}"
            else:
                new_file_path = file_path

            wrpcap(new_file_path, packets)
            
            processed_files_count += 1
            total_packets_subdir += total
            total_unique_packets_subdir += deduped

            rel_new_path = os.path.relpath(new_file_path, base_path)
            log_msg = f"[Dedup] Finished: {rel_new_path}. Original: {total} packets, After dedup: {deduped} packets."
            log('info', log_msg)
            if progress_callback:
                progress_callback(PipelineEvents.FILE_RESULT, {
                    'type': 'dedup',
                    'filename': f,
                    'new_filename': os.path.basename(new_file_path),
                    'original_packets': total,
                    'deduped_packets': deduped
                })

        for error in error_log:
            log('error', f"[Dedup] ERROR: {error}")
        
        if progress_callback:
            progress_callback(PipelineEvents.STEP_SUMMARY, {
                'type': 'dedup',
                'processed_files': processed_files_count,
                'total_packets': total_packets_subdir,
                'total_unique_packets': total_unique_packets_subdir
            }) 