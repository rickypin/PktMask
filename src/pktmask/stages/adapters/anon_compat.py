"""
IpAnonymizationStage 兼容性适配器

将新的 AnonStage 包装为旧的 IpAnonymizationStage 接口，
确保向后兼容性。
"""
from typing import Optional, Dict, List
from ...core.pipeline.stages.anon_ip import AnonStage
from ...core.base_step import ProcessingStep
from ...common.constants import ProcessingConstants


class IpAnonymizationStageCompat(ProcessingStep):
    """
    IpAnonymizationStage 兼容性适配器
    
    包装新的 AnonStage 以提供旧的 IpAnonymizationStage 接口。
    这确保了现有代码可以无缝使用新实现。
    
    注意：这个适配器简化了旧接口的复杂构造函数，
    使用新架构的默认策略和报告器。
    """
    
    suffix: str = ProcessingConstants.MASK_IP_SUFFIX
    
    def __init__(self, strategy=None, reporter=None):
        """
        兼容旧的构造函数签名
        
        注意：strategy 和 reporter 参数被忽略，
        因为新实现使用内置的处理器架构。
        """
        super().__init__()
        
        if strategy is not None or reporter is not None:
            import warnings
            warnings.warn(
                "IpAnonymizationStage 的 strategy 和 reporter 参数已废弃。"
                "新实现使用内置的处理器架构。",
                DeprecationWarning,
                stacklevel=2
            )
        
        # 创建底层的新实现
        self._stage = AnonStage()
        self._stage.initialize()
        
        # 保存用于兼容性的属性
        self._strategy = strategy
        self._reporter = reporter
        self._rel_subdir = None
    
    @property
    def name(self) -> str:
        return "Mask IP"
    
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        """
        处理单个文件 - 兼容旧接口
        
        这个方法保持与旧 IpAnonymizationStage.process_file 完全相同的签名和行为。
        """
        # 调用新实现
        result = self._stage.process_file(input_path, output_path)
        
        if result is None:
            return None
        
        # 将 StageStats 转换为旧格式的字典
        if hasattr(result, 'extra_metrics') and result.extra_metrics:
            # 使用 extra_metrics 中的详细信息
            stats = result.extra_metrics
            return {
                'subdir': stats.get('subdir', ''),
                'input_filename': stats.get('input_filename', ''),
                'output_filename': stats.get('output_filename', ''),
                'total_packets': result.packets_processed,
                'anonymized_packets': result.packets_modified,
                'original_ips': stats.get('original_ips', 0),
                'anonymized_ips': stats.get('anonymized_ips', 0),
                'file_ip_mappings': stats.get('file_ip_mappings', {})
            }
        else:
            # 基本转换
            import os
            return {
                'subdir': os.path.basename(os.path.dirname(input_path)),
                'input_filename': os.path.basename(input_path),
                'output_filename': os.path.basename(output_path),
                'total_packets': result.packets_processed,
                'anonymized_packets': result.packets_modified,
                'original_ips': 0,  # 新实现可能不提供这些统计
                'anonymized_ips': 0,
                'file_ip_mappings': {}
            }
    
    def set_reporter_path(self, path: str, rel_path: str):
        """保持与旧接口兼容"""
        self._rel_subdir = rel_path
        # 新实现可能不需要这个方法，但保持接口
        if self._reporter and hasattr(self._reporter, 'set_report_path'):
            self._reporter.set_report_path(path, rel_path)
    
    def prepare_for_directory(self, subdir_path: str, all_pcap_files: List[str]):
        """保持与旧接口兼容"""
        # 新实现可能不需要这个方法，但保持接口
        if hasattr(self._stage, 'prepare_for_directory'):
            self._stage.prepare_for_directory(subdir_path, all_pcap_files)
        
        # 兼容旧的策略接口
        if self._strategy and hasattr(self._strategy, 'build_mapping_from_directory'):
            self._strategy.build_mapping_from_directory(all_pcap_files)
    
    def finalize_directory_processing(self) -> Optional[Dict]:
        """保持与旧接口兼容"""
        # 新实现可能不支持这个方法
        if hasattr(self._stage, 'finalize_directory_processing'):
            return self._stage.finalize_directory_processing()
        
        # 兼容旧的策略和报告器接口
        if not self._rel_subdir or not self._strategy or not self._reporter:
            return None
        
        try:
            ip_map = self._strategy.get_ip_map()
            summary_stats = {
                "total_unique_ips": len(ip_map),
                "total_mapped_ips": len(ip_map)
            }
            report = self._reporter.finalize_report_for_directory(
                self._rel_subdir, summary_stats, ip_map
            )
            
            self._strategy.reset()
            
            return {'report': report}
        except Exception:
            # 如果兼容性操作失败，返回 None
            return None
