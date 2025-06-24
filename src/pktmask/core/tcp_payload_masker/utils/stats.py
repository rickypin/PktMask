"""
掩码处理统计信息工具

提供统计信息的计算、格式化和报告功能。
"""

import time
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MaskingStatistics:
    """
    掩码处理统计信息
    
    跟踪掩码处理过程中的各种指标，包括处理数量、时间、字节统计等。
    """
    processed_packets: int = 0
    modified_packets: int = 0
    skipped_packets: int = 0
    error_packets: int = 0
    total_bytes_processed: int = 0
    total_bytes_masked: int = 0
    processing_start_time: float = 0.0
    processing_end_time: float = 0.0
    processing_time_seconds: float = 0.0  # 兼容性属性
    
    def start_processing(self):
        """开始处理计时"""
        self.processing_start_time = time.time()
    
    def end_processing(self):
        """结束处理计时"""
        self.processing_end_time = time.time()
    
    def get_processing_time(self) -> float:
        """获取处理时间（秒）"""
        if self.processing_end_time > 0:
            return self.processing_end_time - self.processing_start_time
        return 0.0
    
    def get_modification_rate(self) -> float:
        """获取修改率（百分比）"""
        if self.processed_packets == 0:
            return 0.0
        return (self.modified_packets / self.processed_packets) * 100
    
    def get_processing_speed(self) -> float:
        """获取处理速度（包/秒）"""
        processing_time = self.get_processing_time()
        if processing_time == 0:
            return 0.0
        return self.processed_packets / processing_time
    
    def increment_processed(self, packet_size: int = 0):
        """增加已处理包计数"""
        self.processed_packets += 1
        self.total_bytes_processed += packet_size
    
    def increment_modified(self, masked_bytes: int = 0):
        """增加已修改包计数"""
        self.modified_packets += 1
        self.total_bytes_masked += masked_bytes
    
    def increment_skipped(self):
        """增加跳过包计数"""
        self.skipped_packets += 1
    
    def increment_error(self):
        """增加错误包计数"""
        self.error_packets += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "processed_packets": self.processed_packets,
            "modified_packets": self.modified_packets,
            "skipped_packets": self.skipped_packets,
            "error_packets": self.error_packets,
            "total_bytes_processed": self.total_bytes_processed,
            "total_bytes_masked": self.total_bytes_masked,
            "processing_time_seconds": self.get_processing_time(),
            "modification_rate_percent": self.get_modification_rate(),
            "processing_speed_pps": self.get_processing_speed(),
            "start_time": self.processing_start_time,
            "end_time": self.processing_end_time
        }
    
    def get_summary_report(self) -> str:
        """获取统计摘要报告"""
        processing_time = self.get_processing_time()
        modification_rate = self.get_modification_rate()
        processing_speed = self.get_processing_speed()
        
        return f"""
TCP载荷掩码处理统计报告:
================================
总处理包数: {self.processed_packets}
修改包数: {self.modified_packets}
跳过包数: {self.skipped_packets}
错误包数: {self.error_packets}
修改率: {modification_rate:.2f}%
处理时间: {processing_time:.3f}秒
处理速度: {processing_speed:.1f}包/秒
总处理字节: {self.total_bytes_processed:,}
掩码字节数: {self.total_bytes_masked:,}
================================"""
    
    def reset(self):
        """重置所有统计信息"""
        self.processed_packets = 0
        self.modified_packets = 0
        self.skipped_packets = 0
        self.error_packets = 0
        self.total_bytes_processed = 0
        self.total_bytes_masked = 0
        self.processing_start_time = 0.0
        self.processing_end_time = 0.0 