#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
去重处理步骤 - 集成错误处理系统示例
展示如何在现有代码中集成新的错误处理机制
"""

from pathlib import Path
from typing import Optional
from scapy.all import rdpcap, wrpcap, Packet

# 导入错误处理组件
from ..infrastructure.error_handling import (
    handle_errors, handle_processing_errors, ErrorHandlingContext,
    set_current_operation, add_recent_action
)
from ..common.exceptions import FileError, ProcessingError
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


class DeduplicationProcessor:
    """去重处理器 - 集成错误处理示例"""
    
    def __init__(self):
        self.processed_files = 0
        self.skipped_files = 0
        self.error_files = 0
    
    @handle_errors(
        operation="file_deduplication",
        component="deduplication_processor",
        auto_recover=True,
        reraise_on_failure=False,
        fallback_return_value=None,
        log_success=True
    )
    def process_file(self, input_file: str, output_file: str) -> Optional[str]:
        """
        处理单个文件的去重
        使用错误处理装饰器自动处理错误
        """
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        # 记录用户操作
        add_recent_action(f"Starting deduplication: {input_file}")
        
        # 验证输入文件
        if not input_path.exists():
            raise FileError(f"Input file does not exist: {input_file}", file_path=input_file)
        
        if not input_path.suffix.lower() in ['.pcap', '.pcapng']:
            raise FileError(f"Unsupported file format: {input_path.suffix}", file_path=input_file)
        
        # 读取数据包
        try:
            packets = rdpcap(str(input_path))
            logger.info(f"Loaded {len(packets)} packets from {input_file}")
        except Exception as e:
            raise ProcessingError(f"Failed to read pcap file: {e}", file_path=input_file, step_name="read_packets")
        
        # 执行去重
        unique_packets = self._deduplicate_packets(packets)
        duplicate_count = len(packets) - len(unique_packets)
        
        logger.info(f"Removed {duplicate_count} duplicate packets")
        add_recent_action(f"Deduplication complete: removed {duplicate_count} duplicates")
        
        # 保存结果
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            wrpcap(str(output_path), unique_packets)
            logger.info(f"Saved {len(unique_packets)} unique packets to {output_file}")
        except Exception as e:
            raise ProcessingError(f"Failed to save pcap file: {e}", file_path=output_file, step_name="save_packets")
        
        self.processed_files += 1
        return str(output_path)
    
    @handle_processing_errors(
        step_name="packet_deduplication",
        skip_on_error=True,
        max_retries=2
    )
    def _deduplicate_packets(self, packets: list) -> list:
        """
        执行数据包去重逻辑
        使用处理步骤装饰器
        """
        seen_hashes = set()
        unique_packets = []
        
        for i, packet in enumerate(packets):
            try:
                # 计算数据包哈希
                packet_hash = self._calculate_packet_hash(packet)
                
                if packet_hash not in seen_hashes:
                    seen_hashes.add(packet_hash)
                    unique_packets.append(packet)
                
            except Exception as e:
                # 单个数据包处理失败，记录但继续
                logger.warning(f"Failed to process packet {i}: {e}")
                continue
        
        return unique_packets
    
    def _calculate_packet_hash(self, packet: Packet) -> str:
        """计算数据包哈希值"""
        # 简化的哈希计算
        packet_bytes = bytes(packet)
        return str(hash(packet_bytes))
    
    def process_directory(self, input_dir: str, output_dir: str) -> dict:
        """
        处理目录中的所有文件
        使用错误处理上下文管理器
        """
        with ErrorHandlingContext("directory_deduplication", "deduplication_processor"):
            input_path = Path(input_dir)
            output_path = Path(output_dir)
            
            if not input_path.exists():
                raise FileError(f"Input directory does not exist: {input_dir}")
            
            # 查找所有PCAP文件
            pcap_files = list(input_path.glob("*.pcap")) + list(input_path.glob("*.pcapng"))
            
            if not pcap_files:
                logger.warning(f"No PCAP files found in {input_dir}")
                return {"processed": 0, "skipped": 0, "errors": 0}
            
            add_recent_action(f"Found {len(pcap_files)} files to process")
            
            results = {
                "processed": 0,
                "skipped": 0,
                "errors": 0,
                "files": []
            }
            
            for pcap_file in pcap_files:
                output_file = output_path / f"{pcap_file.stem}_deduped{pcap_file.suffix}"
                
                try:
                    result = self.process_file(str(pcap_file), str(output_file))
                    if result:
                        results["processed"] += 1
                        results["files"].append({
                            "input": str(pcap_file),
                            "output": result,
                            "status": "success"
                        })
                    else:
                        results["skipped"] += 1
                        results["files"].append({
                            "input": str(pcap_file),
                            "output": None,
                            "status": "skipped"
                        })
                
                except Exception as e:
                    results["errors"] += 1
                    results["files"].append({
                        "input": str(pcap_file),
                        "output": None,
                        "status": "error",
                        "error": str(e)
                    })
                    logger.error(f"Failed to process {pcap_file}: {e}")
            
            logger.info(f"Deduplication complete: {results['processed']} processed, "
                       f"{results['skipped']} skipped, {results['errors']} errors")
            
            return results


# 使用示例
def main():
    """错误处理系统使用示例"""
    from ..infrastructure.error_handling import install_global_exception_handler
    
    # 安装全局异常处理器
    install_global_exception_handler()
    
    processor = DeduplicationProcessor()
    
    try:
        # 处理单个文件
        result = processor.process_file(
            "input.pcap", 
            "output_deduped.pcap"
        )
        print(f"Processing result: {result}")
        
        # 处理目录
        directory_results = processor.process_directory(
            "input_directory",
            "output_directory"
        )
        print(f"Directory processing results: {directory_results}")
        
    except Exception as e:
        logger.error(f"Unhandled error in main: {e}")


if __name__ == "__main__":
    main() 