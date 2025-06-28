"""
IP匿名化处理器

直接实现IP匿名化功能，不依赖Legacy Steps。
"""
import os
from typing import Optional
from pathlib import Path

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from ...core.strategy import HierarchicalAnonymizationStrategy
from ...utils.reporting import FileReporter
from ...infrastructure.logging import get_logger


class IPAnonymizer(BaseProcessor):
    """IP匿名化处理器
    
    直接使用HierarchicalAnonymizationStrategy实现IP匿名化功能。
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('ip_anonymizer')
        self._strategy: Optional[HierarchicalAnonymizationStrategy] = None
        self._reporter: Optional[FileReporter] = None
        
    def _initialize_impl(self):
        """初始化IP匿名化组件"""
        try:
            # 创建策略和报告器
            self._strategy = HierarchicalAnonymizationStrategy()
            self._reporter = FileReporter()
            
            self._logger.info("IP匿名化处理器初始化成功")
            
        except Exception as e:
            self._logger.error(f"IP匿名化处理器初始化失败: {e}")
            raise
            
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理单个文件的IP匿名化"""
        if not self._is_initialized:
            if not self.initialize():
                return ProcessorResult(
                    success=False, 
                    error="处理器未正确初始化"
                )
        
        try:
            # 验证输入
            self.validate_inputs(input_path, output_path)
            
            # 重置统计信息
            self.reset_stats()
            
            self._logger.info(f"开始IP匿名化: {input_path} -> {output_path}")
            
            # 使用Scapy处理PCAP文件
            from scapy.all import rdpcap, wrpcap
            import time
            
            start_time = time.time()
            
            # 读取数据包
            packets = rdpcap(input_path)
            total_packets = len(packets)
            
            # **关键修复**: 先建立IP映射表
            self._logger.info("分析文件中的IP地址并建立映射表...")
            self._strategy.build_mapping_from_directory([input_path])
            ip_mappings = self._strategy.get_ip_map()
            self._logger.info(f"建立IP映射完成: {len(ip_mappings)} 个IP地址")
            
            # 开始匿名化数据包
            self._logger.info("开始匿名化数据包")
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
                wrpcap(output_path, anonymized_pkts)
            else:
                # 如果没有数据包，创建空文件
                open(output_path, 'a').close()
            
            processing_time = time.time() - start_time
            
            # 构建结果数据
            ip_mappings = self._strategy.get_ip_map()
            result_data = {
                'total_packets': total_packets,
                'anonymized_packets': anonymized_packets,
                'original_ips': len([ip for ip in ip_mappings.keys()]),
                'anonymized_ips': len([ip for ip in ip_mappings.values()]),
                'file_ip_mappings': ip_mappings,
                'processing_time': processing_time
            }
            
            if result_data is None:
                return ProcessorResult(
                    success=False,
                    error="IP匿名化处理失败，未返回结果"
                )
            
            # 更新统计信息
            self.stats.update({
                'original_ips': result_data.get('original_ips', 0),
                'anonymized_ips': result_data.get('anonymized_ips', 0),
                'total_packets': result_data.get('total_packets', 0),
                'anonymized_packets': result_data.get('anonymized_packets', 0),
                'ip_mappings': result_data.get('file_ip_mappings', {}),
                'anonymization_rate': self._calculate_anonymization_rate(result_data)
            })
            
            self._logger.info(
                f"IP匿名化完成: {result_data.get('anonymized_ips', 0)} IPs匿名化"
            )
            
            return ProcessorResult(
                success=True,
                data=result_data,
                stats=self.stats
            )
            
        except FileNotFoundError as e:
            error_msg = f"文件未找到: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"IP匿名化处理失败: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        """获取用户友好的显示名称"""
        return "Mask IPs"
    
    def get_description(self) -> str:
        """获取处理器描述"""
        return "匿名化数据包中的IP地址，保持子网结构一致性"
        
    def _calculate_anonymization_rate(self, result_data: dict) -> float:
        """计算匿名化比率"""
        original_ips = result_data.get('original_ips', 0)
        anonymized_ips = result_data.get('anonymized_ips', 0)
        
        if original_ips == 0:
            return 0.0
        
        return (anonymized_ips / original_ips) * 100.0
        
    def get_ip_mappings(self) -> dict:
        """获取IP映射表"""
        if self._strategy:
            return self._strategy.get_ip_map()
        return {}
        
    def prepare_for_directory(self, directory_path: str, pcap_files: list):
        """为目录处理准备IP映射"""
        if not self._is_initialized:
            if not self.initialize():
                raise RuntimeError("处理器初始化失败")
        
        self._logger.info(f"为目录准备IP映射: {directory_path}")
        # 使用策略的build_mapping_from_directory方法建立IP映射
        self._strategy.build_mapping_from_directory(pcap_files)
        
    def finalize_directory_processing(self) -> Optional[dict]:
        """完成目录处理"""
        if self._strategy:
            return {
                'total_ip_mappings': len(self._strategy.get_ip_map()),
                'ip_mappings': self._strategy.get_ip_map()
            }
        return None 