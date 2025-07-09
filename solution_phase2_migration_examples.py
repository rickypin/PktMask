#!/usr/bin/env python3
"""
阶段二：现有实现迁移示例
展示如何将现有的 ProcessingStep 子类迁移到新架构
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, List
from scapy.all import PcapReader, PcapNgReader, wrpcap

from ..core.pipeline.base_stage import StageBase
from ..core.pipeline.models import StageStats
from ..core.processors.deduplicator import DeduplicationProcessor, ProcessorConfig
from ..core.processors.ip_anonymizer import IPAnonymizer
from ..infrastructure.logging import get_logger


# 示例1：去重阶段的迁移
class DeduplicationStage_Before(StageBase):
    """迁移前：复杂的旧实现"""
    
    @property
    def name(self) -> str:
        return "Remove Dupes"
    
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        """旧版实现：直接操作 scapy"""
        start_time = time.time()
        
        packets = []
        total_count = 0
        seen_packets = set()
        
        ext = os.path.splitext(input_path)[1].lower()
        reader_cls = PcapNgReader if ext == ".pcapng" else PcapReader
        
        with reader_cls(input_path) as reader:
            for pkt in reader:
                total_count += 1
                raw_bytes = bytes(pkt)
                if raw_bytes not in seen_packets:
                    seen_packets.add(raw_bytes)
                    packets.append(pkt)
        
        wrpcap(output_path, packets, append=False)
        
        duration_ms = (time.time() - start_time) * 1000
        unique_count = len(packets)
        removed_count = total_count - unique_count
        
        return {
            'total_packets': total_count,
            'unique_packets': unique_count,
            'removed_count': removed_count,
            'duration_ms': duration_ms
        }


class DeduplicationStage_After(StageBase):
    """迁移后：使用处理器的现代实现"""
    
    name: str = "DeduplicationStage"
    
    def __init__(self, config: Optional[Dict] = None):
        self._config = config or {}
        proc_cfg = ProcessorConfig(enabled=True, name="dedup_packet")
        self._processor = DeduplicationProcessor(proc_cfg)
        super().__init__()
    
    def initialize(self, config: Optional[Dict] = None) -> None:
        if config:
            self._config.update(config)
        self._processor.initialize()
        super().initialize(self._config)
    
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
        """现代实现：委托给专门的处理器"""
        start_time = time.time()
        
        result = self._processor.process_file(str(input_path), str(output_path))
        duration_ms = (time.time() - start_time) * 1000
        
        if not result.success:
            return StageStats(
                stage_name=self.name,
                packets_processed=0,
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={"error": result.error or "unknown"}
            )
        
        stats_dict = result.stats or {}
        return StageStats(
            stage_name=self.name,
            packets_processed=int(stats_dict.get("total_packets", 0)),
            packets_modified=int(stats_dict.get("removed_count", 0)),
            duration_ms=duration_ms,
            extra_metrics=stats_dict
        )


# 示例2：IP匿名化阶段的迁移
class IpAnonymizationStage_Before(StageBase):
    """迁移前：复杂的策略模式实现"""
    
    def __init__(self, strategy=None, reporter=None):
        super().__init__()
        self._strategy = strategy
        self._reporter = reporter
        self._logger = get_logger('ip_anonymization')
    
    @property
    def name(self) -> str:
        return "Mask IP"
    
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        """旧版实现：复杂的策略处理"""
        # 复杂的策略初始化和处理逻辑...
        return {
            'total_packets': 100,
            'anonymized_packets': 80,
            'duration_ms': 2000.0
        }


class IpAnonymizationStage_After(StageBase):
    """迁移后：使用处理器的现代实现"""
    
    name: str = "AnonStage"
    
    def __init__(self, config: Optional[Dict] = None):
        self._config = config or {}
        proc_cfg = ProcessorConfig(enabled=True, name="anon_ip")
        self._processor = IPAnonymizer(proc_cfg)
        super().__init__()
    
    def initialize(self, config: Optional[Dict] = None) -> None:
        if config:
            self._config.update(config)
        self._processor.initialize()
        super().initialize(self._config)
    
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
        """现代实现：委托给专门的处理器"""
        start_time = time.time()
        
        result = self._processor.process_file(str(input_path), str(output_path))
        duration_ms = (time.time() - start_time) * 1000
        
        if not result.success:
            return StageStats(
                stage_name=self.name,
                packets_processed=0,
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={"error": result.error or "unknown"}
            )
        
        stats_dict = result.stats or {}
        return StageStats(
            stage_name=self.name,
            packets_processed=int(stats_dict.get("total_packets", 0)),
            packets_modified=int(stats_dict.get("anonymized_packets", 0)),
            duration_ms=duration_ms,
            extra_metrics=stats_dict
        )


# 迁移工具函数
def migrate_processing_step_to_stage_base(old_class):
    """自动迁移工具：将 ProcessingStep 子类转换为 StageBase 子类"""
    
    class MigratedStage(StageBase):
        name: str = getattr(old_class, 'name', old_class.__name__)
        
        def __init__(self, *args, **kwargs):
            # 创建旧实例但不调用其 __init__
            self._old_instance = object.__new__(old_class)
            # 手动初始化必要的属性
            if hasattr(old_class, '__init__'):
                old_class.__init__(self._old_instance, *args, **kwargs)
            super().__init__()
        
        def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
            # 调用旧实例的方法
            if hasattr(self._old_instance, 'process_file_legacy'):
                result = self._old_instance.process_file_legacy(str(input_path), str(output_path))
            else:
                result = self._old_instance.process_file(str(input_path), str(output_path))
            
            # 转换结果
            if isinstance(result, dict):
                return StageStats(
                    stage_name=self.name,
                    packets_processed=result.get('total_packets', 0),
                    packets_modified=result.get('modified_packets', 0),
                    duration_ms=result.get('duration_ms', 0.0),
                    extra_metrics=result
                )
            return result or StageStats(stage_name=self.name)
    
    return MigratedStage
