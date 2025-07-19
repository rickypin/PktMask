"""
统一IP匿名化阶段 - 纯StageBase实现

完全移除BaseProcessor依赖，直接集成HierarchicalAnonymizationStrategy逻辑。
消除适配器层，统一返回StageStats格式。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.strategy import HierarchicalAnonymizationStrategy
from pktmask.utils.reporting import FileReporter
from pktmask.infrastructure.logging import get_logger


class UnifiedIPAnonymizationStage(StageBase):
    """统一IP匿名化阶段 - 消除BaseProcessor依赖
    
    直接集成IP匿名化逻辑，无适配器层，统一接口。
    保持所有现有功能：层次化匿名化、子网结构保持、统计信息收集。
    """
    
    name: str = "UnifiedIPAnonymizationStage"
    
    def __init__(self, config: Dict[str, Any]):
        """初始化统一IP匿名化阶段
        
        Args:
            config: 配置字典，支持以下参数：
                - method: 匿名化方法 (默认: "prefix_preserving")
                - ipv4_prefix: IPv4前缀长度 (默认: 24)
                - ipv6_prefix: IPv6前缀长度 (默认: 64)
                - enabled: 是否启用 (默认: True)
                - name: 阶段名称
                - priority: 优先级
        """
        super().__init__()
        
        # 配置解析
        self.method = config.get('method', 'prefix_preserving')
        self.ipv4_prefix = config.get('ipv4_prefix', 24)
        self.ipv6_prefix = config.get('ipv6_prefix', 64)
        self.enabled = config.get('enabled', True)
        self.stage_name = config.get('name', 'ip_anonymization')
        self.priority = config.get('priority', 0)
        
        # 日志记录器
        self.logger = get_logger('unified_ip_anonymization')
        
        # 核心组件 - 直接初始化，无延迟加载
        self._strategy: Optional[HierarchicalAnonymizationStrategy] = None
        self._reporter: Optional[FileReporter] = None

        # 使用完整的HierarchicalAnonymizationStrategy进行IP匿名化
        self._use_simple_strategy = False
        
        # 统计信息
        self._stats = {}
        
        self.logger.info(f"UnifiedIPAnonymizationStage created: method={self.method}")
    
    def initialize(self, config: Optional[Dict] = None) -> None:
        """初始化IP匿名化组件"""
        try:
            if self._use_simple_strategy:
                # 使用简化策略，避免encapsulation adapter问题
                self._strategy = SimpleIPAnonymizationStrategy()
            else:
                # 使用完整的HierarchicalAnonymizationStrategy
                self._strategy = HierarchicalAnonymizationStrategy()

            self._reporter = FileReporter()

            super().initialize(config)
            self.logger.info("Unified IP anonymization stage initialization successful")

        except Exception as e:
            self.logger.error(f"Unified IP anonymization stage initialization failed: {e}")
            raise
    
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
        """处理文件 - 直接实现IP匿名化，无适配器层
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            StageStats: 标准统计信息格式
        """
        if not self._initialized:
            self.initialize()
            if not self._initialized:
                raise RuntimeError("UnifiedIPAnonymizationStage 未初始化")
        
        # 路径标准化
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        # 验证输入
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"输入路径不是文件: {input_path}")
        
        self.logger.info(f"Starting IP anonymization: {input_path} -> {output_path}")
        
        start_time = time.time()
        
        try:
            # 重置统计信息
            self._stats.clear()
            
            # 使用Scapy处理PCAP文件
            from scapy.all import rdpcap, wrpcap
            
            # 读取数据包
            packets = rdpcap(str(input_path))
            total_packets = len(packets)
            
            self.logger.info(f"Loaded {total_packets} packets from {input_path}")
            
            # 关键修复：先构建IP映射表
            self.logger.info("Analyzing IP addresses and building mapping table...")
            self._strategy.build_mapping_from_directory([str(input_path)])
            ip_mappings = self._strategy.get_ip_map()
            self.logger.info(f"IP mapping construction completed: {len(ip_mappings)} IP addresses")
            
            # 开始匿名化数据包
            self.logger.info("Starting packet anonymization")
            anonymized_packets = 0
            
            # 处理每个数据包
            anonymized_pkts = []
            for packet in packets:
                modified_packet, was_modified = self._strategy.anonymize_packet(packet)
                anonymized_pkts.append(modified_packet)
                if was_modified:
                    anonymized_packets += 1
            
            # 保存匿名化后的数据包
            if anonymized_pkts:
                wrpcap(str(output_path), anonymized_pkts)
                self.logger.info(f"Saved {len(anonymized_pkts)} anonymized packets to {output_path}")
            else:
                # 如果没有数据包，创建空文件
                output_path.touch()
                self.logger.warning("No packets to save, created empty output file")
            
            processing_time = time.time() - start_time
            duration_ms = processing_time * 1000
            
            # 构建统计信息
            ip_mappings = self._strategy.get_ip_map()
            original_ips = len([ip for ip in ip_mappings.keys()])
            anonymized_ips = len([ip for ip in ip_mappings.values()])
            
            # 计算匿名化率
            anonymization_rate = (anonymized_ips / original_ips * 100.0) if original_ips > 0 else 0.0
            
            # 更新内部统计
            self._stats.update({
                'original_ips': original_ips,
                'anonymized_ips': anonymized_ips,
                'total_packets': total_packets,
                'anonymized_packets': anonymized_packets,
                'ip_mappings': ip_mappings,
                'anonymization_rate': anonymization_rate,
                'processing_time': processing_time
            })
            
            self.logger.info(
                f"IP anonymization completed: {anonymized_ips} IPs anonymized, "
                f"{anonymized_packets}/{total_packets} packets modified"
            )
            
            # 返回标准StageStats格式
            return StageStats(
                stage_name=self.name,
                packets_processed=total_packets,
                packets_modified=anonymized_packets,
                duration_ms=duration_ms,
                extra_metrics={
                    'method': self.method,
                    'ipv4_prefix': self.ipv4_prefix,
                    'ipv6_prefix': self.ipv6_prefix,
                    'original_ips': original_ips,
                    'anonymized_ips': anonymized_ips,
                    'anonymization_rate': anonymization_rate,
                    'ip_mappings_count': len(ip_mappings),
                    'ip_mappings': ip_mappings,  # 添加实际的IP映射数据
                    'file_ip_mappings': ip_mappings,  # 为兼容性添加file_ip_mappings字段
                    'enabled': self.enabled,
                    'stage_name': self.stage_name,
                    'success': True
                }
            )
            
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            self.logger.error(error_msg)
            raise
            
        except Exception as e:
            error_msg = f"IP anonymization processing failed: {e}"
            self.logger.error(error_msg)
            raise
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        return "Anonymize IPs"
    
    def get_description(self) -> str:
        """获取描述"""
        return "Anonymize IP addresses in packets while maintaining subnet structure consistency"
    
    def get_ip_mappings(self) -> dict:
        """获取IP映射表"""
        if self._strategy:
            return self._strategy.get_ip_map()
        return {}
    
    def prepare_for_directory(self, directory: str | Path, all_files: List[str]) -> None:
        """目录级预处理 - 构建全局IP映射"""
        if not self._initialized:
            self.initialize()
        
        self.logger.info(f"Preparing IP mapping for directory: {directory}")
        
        # 使用策略的build_mapping_from_directory方法构建IP映射
        self._strategy.build_mapping_from_directory(all_files)
        
        ip_count = len(self._strategy.get_ip_map())
        self.logger.info(f"Directory IP mapping prepared: {ip_count} unique IP addresses")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return self._stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats.clear()


class SimpleIPAnonymizationStrategy:
    """简化的IP匿名化策略 - 避免复杂依赖"""

    def __init__(self):
        self._ip_map = {}

    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """构建IP映射 - 简化版本"""
        # 简化实现：为测试目的创建空映射
        self._ip_map = {}

    def get_ip_map(self):
        """获取IP映射"""
        return self._ip_map

    def anonymize_packet(self, pkt):
        """匿名化数据包 - 简化版本"""
        # 简化实现：直接返回原包，标记为未修改
        return pkt, False
