"""
IP匿名化处理器

简化版的IP匿名化处理器，包装现有的IpAnonymizationStep实现。
"""
import os
from typing import Optional
from pathlib import Path

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from ...core.strategy import HierarchicalAnonymizationStrategy
from ...steps.ip_anonymization import IpAnonymizationStep
from ...utils.reporting import FileReporter
from ...infrastructure.logging import get_logger


class IPAnonymizer(BaseProcessor):
    """IP匿名化处理器
    
    使用现有的IpAnonymizationStep和HierarchicalAnonymizationStrategy，
    但通过简化的处理器接口暴露功能。
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('ip_anonymizer')
        self._step: Optional[IpAnonymizationStep] = None
        self._strategy: Optional[HierarchicalAnonymizationStrategy] = None
        
    def _initialize_impl(self):
        """初始化IP匿名化组件"""
        try:
            # 创建策略和步骤
            self._strategy = HierarchicalAnonymizationStrategy()
            reporter = FileReporter()
            self._step = IpAnonymizationStep(self._strategy, reporter)
            
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
            
            # 如果需要，先构建目录级映射
            if not self._strategy.get_ip_map():
                self._logger.info("构建目录级IP映射")
                directory_files = [input_path]  # 简化版：单文件处理
                self._step.prepare_for_directory(
                    os.path.dirname(input_path), 
                    directory_files
                )
            
            # 处理文件
            result_data = self._step.process_file(input_path, output_path)
            
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
        self._step.prepare_for_directory(directory_path, pcap_files)
        
    def finalize_directory_processing(self) -> Optional[dict]:
        """完成目录处理"""
        if self._step:
            return self._step.finalize_directory_processing()
        return None 