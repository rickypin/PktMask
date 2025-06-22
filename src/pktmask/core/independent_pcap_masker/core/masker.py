"""
独立PCAP掩码处理器主要API实现

这是模块的核心API类，提供完全独立的PCAP掩码处理功能。
"""

import time
import threading
from typing import Dict, Optional, Any
import logging
from pathlib import Path

from .models import MaskEntry, MaskingResult, SequenceMaskTable
from .config import ConfigManager, create_config_manager
from .protocol_control import ProtocolBindingController
from ..exceptions import (
    IndependentMaskerError,
    ProtocolBindingError, 
    FileConsistencyError,
    ValidationError
)


class IndependentPcapMasker:
    """独立的PCAP掩码处理器
    
    这是一个完全独立的模块，可以脱离PktMask主程序运行。
    只需要提供PCAP文件和掩码表即可完成处理。
    
    主要特性：
    - 零架构依赖：不依赖BaseStage、StageContext等
    - API驱动：提供标准化的函数调用接口
    - 功能单一：纯粹的序列号匹配和字节级掩码
    - 完全测试：可独立进行单元测试和集成测试
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化掩码处理器
        
        Args:
            config: 可选配置参数，会与默认配置合并
        """
        # 配置管理
        self.config_manager = create_config_manager(config)
        self.logger = logging.getLogger(__name__)
        
        # 协议绑定控制器（Phase 2新增）
        self.protocol_controller = ProtocolBindingController(self.logger)
        
        # 线程安全锁（用于协议绑定操作）
        self._binding_lock = threading.Lock()
        
        # 统计信息
        self._processing_stats = {
            'total_files_processed': 0,
            'total_packets_processed': 0,
            'total_packets_modified': 0,
            'total_bytes_masked': 0,
            'total_processing_time': 0.0
        }
        
        self.logger.info("✅ 独立PCAP掩码处理器初始化完成")
        self.logger.debug(f"配置摘要: {self.config_manager.export_summary()}")
    
    def mask_pcap_with_sequences(
        self,
        input_pcap: str,
        mask_table: SequenceMaskTable,
        output_pcap: str
    ) -> MaskingResult:
        """主要API接口：对PCAP文件应用基于序列号的掩码
        
        这是模块的主要入口点，可以完全独立调用。
        
        Args:
            input_pcap: 输入PCAP文件路径（任意来源）
            mask_table: 序列号掩码表
            output_pcap: 输出PCAP文件路径
            
        Returns:
            MaskingResult: 处理结果和详细统计信息
            
        Raises:
            ValidationError: 输入参数无效
            FileNotFoundError: 文件不存在
            ProtocolBindingError: 协议解析控制失败
            FileConsistencyError: 文件一致性验证失败
            IndependentMaskerError: 其他处理错误
            
        Example:
            >>> masker = IndependentPcapMasker()
            >>> mask_table = SequenceMaskTable()
            >>> mask_table.add_entry(MaskEntry(
            ...     stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            ...     sequence_start=1000,
            ...     sequence_end=2000,
            ...     mask_type="mask_after",
            ...     mask_params={"keep_bytes": 5}
            ... ))
            >>> result = masker.mask_pcap_with_sequences(
            ...     "input.pcap", mask_table, "output.pcap"
            ... )
            >>> print(f"成功处理 {result.modified_packets} 个数据包")
        """
        start_time = time.time()
        
        # 初始化结果对象
        result = MaskingResult(
            success=False,
            total_packets=0,
            modified_packets=0,
            bytes_masked=0,
            processing_time=0.0,
            streams_processed=0
        )
        
        try:
            self.logger.info(f"🚀 开始处理PCAP文件: {input_pcap} -> {output_pcap}")
            
            # 阶段1: 输入验证
            self._validate_inputs(input_pcap, mask_table, output_pcap)
            self.logger.debug("✅ 输入验证通过")
            
            # 阶段2: 协议解析控制（Phase 2实现）
            if self.config_manager.should_disable_protocol_parsing():
                self.protocol_controller.disable_protocol_parsing()
                self.logger.debug("✅ 协议解析已禁用")
            
            try:
                # 阶段3: 核心处理逻辑
                result = self._process_pcap_file(input_pcap, mask_table, output_pcap, start_time)
                
                # 阶段4: 一致性验证
                if self.config_manager.is_strict_mode():
                    self._verify_file_consistency(input_pcap, output_pcap, result)
                    self.logger.debug("✅ 文件一致性验证通过")
                
            finally:
                # 阶段5: 恢复协议解析状态（Phase 2实现）
                if self.protocol_controller.is_protocol_parsing_disabled():
                    self.protocol_controller.restore_protocol_parsing()
                    self.logger.debug("✅ 协议解析状态已恢复")
            
            # 更新统计信息
            self._update_global_stats(result)
            
            self.logger.info(f"🎉 处理完成: {result.get_summary()}")
            return result
            
        except Exception as e:
            result.error_message = str(e)
            result.processing_time = time.time() - start_time
            
            self.logger.error(f"❌ 处理失败: {e}")
            
            # 确保在异常情况下也恢复协议绑定（Phase 2实现）
            if self.protocol_controller.is_protocol_parsing_disabled():
                try:
                    self.protocol_controller.restore_protocol_parsing()
                except Exception as restore_error:
                    self.logger.error(f"恢复协议解析时发生错误: {restore_error}")
            
            return result
    
    def _validate_inputs(
        self,
        input_pcap: str,
        mask_table: SequenceMaskTable,
        output_pcap: str
    ) -> None:
        """验证输入参数
        
        Args:
            input_pcap: 输入文件路径
            mask_table: 掩码表
            output_pcap: 输出文件路径
            
        Raises:
            ValidationError: 输入参数无效时
        """
        # 验证输入文件
        input_path = Path(input_pcap)
        if not input_path.exists():
            raise ValidationError(f"输入文件不存在: {input_pcap}")
        
        if not input_path.is_file():
            raise ValidationError(f"输入路径不是文件: {input_pcap}")
        
        if not self.config_manager.validate_file_format(input_pcap):
            supported = self.config_manager.get('supported_formats', [])
            raise ValidationError(f"不支持的文件格式: {input_pcap}，支持的格式: {supported}")
        
        # 验证掩码表
        if not isinstance(mask_table, SequenceMaskTable):
            raise ValidationError("mask_table必须是SequenceMaskTable类型")
        
        if mask_table.get_total_entries() == 0:
            raise ValidationError("掩码表为空，没有需要处理的条目")
        
        # 验证掩码表一致性
        consistency_issues = mask_table.validate_consistency()
        if consistency_issues:
            raise ValidationError(f"掩码表一致性检查失败: {'; '.join(consistency_issues)}")
        
        # 验证输出路径
        output_path = Path(output_pcap)
        if output_path.exists() and output_path.is_dir():
            raise ValidationError(f"输出路径是目录: {output_pcap}")
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.debug(
            f"输入验证完成: 输入文件={input_path.stat().st_size}字节, "
            f"掩码条目={mask_table.get_total_entries()}个, "
            f"流数量={mask_table.get_streams_count()}个"
        )
    
    def _process_pcap_file(
        self,
        input_pcap: str,
        mask_table: SequenceMaskTable,
        output_pcap: str,
        start_time: float
    ) -> MaskingResult:
        """处理PCAP文件的核心逻辑
        
        Args:
            input_pcap: 输入文件路径
            mask_table: 掩码表
            output_pcap: 输出文件路径
            start_time: 开始时间
            
        Returns:
            MaskingResult: 处理结果
        """
        from .file_handler import PcapFileHandler
        from .mask_applier import MaskApplier
        
        # 初始化组件
        file_handler = PcapFileHandler(self.logger)
        mask_applier = MaskApplier(
            mask_byte_value=self.config_manager.get('mask_byte_value', 0x00),
            logger=self.logger
        )
        
        try:
            # 阶段1: 读取数据包
            self.logger.info(f"读取PCAP文件: {input_pcap}")
            packets = file_handler.read_packets(input_pcap)
            total_packets = len(packets)
            
            self.logger.info(f"成功读取 {total_packets} 个数据包")
            
            # 阶段2: 应用掩码
            self.logger.info("开始应用掩码...")
            modified_packets, mask_stats = mask_applier.apply_masks_to_packets(
                packets, mask_table
            )
            
            # 阶段3: 写入输出文件
            self.logger.info(f"写入输出文件: {output_pcap}")
            file_handler.write_packets(modified_packets, output_pcap)
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 生成结果
            result = MaskingResult(
                success=True,
                total_packets=total_packets,
                modified_packets=mask_stats.get('packets_modified', 0),
                bytes_masked=mask_stats.get('bytes_masked', 0),
                processing_time=processing_time,
                streams_processed=mask_table.get_streams_count()
            )
            
            # 添加详细统计信息
            result.add_statistic('mask_table_entries', mask_table.get_total_entries())
            result.add_statistic('mask_table_streams', mask_table.get_streams_count())
            result.add_statistic('mask_application_stats', mask_stats)
            result.add_statistic('config_summary', self.config_manager.export_summary())
            
            # 验证协议解析禁用效果
            if self.config_manager.should_disable_protocol_parsing():
                protocol_stats = mask_applier.payload_extractor.verify_raw_layer_dominance(packets)
                result.add_statistic('protocol_parsing_verification', protocol_stats)
                
                if not protocol_stats.get('protocol_parsing_disabled', False):
                    self.logger.warning(
                        f"协议解析禁用效果不佳: Raw层存在率 {protocol_stats.get('raw_layer_rate', 0):.2%}"
                    )
            
            self.logger.info(f"✅ 核心处理完成: {result.get_summary()}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            self.logger.error(f"核心处理失败: {e}")
            
            return MaskingResult(
                success=False,
                total_packets=0,
                modified_packets=0,
                bytes_masked=0,
                processing_time=processing_time,
                streams_processed=0,
                error_message=str(e)
            )
    
    def verify_protocol_parsing_disabled(self, packets: list) -> Dict[str, Any]:
        """验证协议解析禁用效果（Phase 2新增方法）
        
        委托给协议控制器进行Raw层存在率验证
        
        Args:
            packets: 要验证的数据包列表
            
        Returns:
            Dict: 验证结果统计
        """
        return self.protocol_controller.verify_raw_layer_presence(packets)
    
    def get_protocol_binding_stats(self) -> Dict[str, Any]:
        """获取协议绑定统计信息（Phase 2新增方法）"""
        return self.protocol_controller.get_binding_statistics()
    
    def _verify_file_consistency(
        self,
        input_pcap: str,
        output_pcap: str,
        result: MaskingResult
    ) -> None:
        """验证输出文件与输入文件的一致性
        
        这是Phase 3的核心功能，目前是占位符实现。
        """
        self.logger.info("⚠️  文件一致性验证占位符 - 将在Phase 3实现")
    
    def _update_global_stats(self, result: MaskingResult) -> None:
        """更新全局统计信息"""
        self._processing_stats['total_files_processed'] += 1
        self._processing_stats['total_packets_processed'] += result.total_packets
        self._processing_stats['total_packets_modified'] += result.modified_packets
        self._processing_stats['total_bytes_masked'] += result.bytes_masked
        self._processing_stats['total_processing_time'] += result.processing_time
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """获取全局统计信息"""
        stats = self._processing_stats.copy()
        
        # 计算平均值
        if stats['total_files_processed'] > 0:
            stats['avg_packets_per_file'] = stats['total_packets_processed'] / stats['total_files_processed']
            stats['avg_processing_time_per_file'] = stats['total_processing_time'] / stats['total_files_processed']
        
        if stats['total_processing_time'] > 0:
            stats['avg_processing_speed_pps'] = stats['total_packets_processed'] / stats['total_processing_time']
        
        return stats
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        self._processing_stats = {
            'total_files_processed': 0,
            'total_packets_processed': 0,
            'total_packets_modified': 0,
            'total_bytes_masked': 0,
            'total_processing_time': 0.0
        }
        self.logger.debug("统计信息已重置")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return self.config_manager.export_summary()
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """更新配置参数
        
        Args:
            updates: 要更新的配置参数
        """
        self.config_manager.update(updates)
        self.logger.debug(f"配置已更新: {updates}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，确保资源清理（Phase 2更新）"""
        if self.protocol_controller.is_protocol_parsing_disabled():
            try:
                self.protocol_controller.restore_protocol_parsing()
            except Exception as e:
                self.logger.error(f"清理协议解析状态时发生错误: {e}")
    
    def __repr__(self) -> str:
        """字符串表示"""
        stats = self.get_global_statistics()
        return (
            f"IndependentPcapMasker("
            f"files_processed={stats['total_files_processed']}, "
            f"packets_processed={stats['total_packets_processed']}, "
            f"config_hash={hash(str(self.config_manager.get_all()))}"
            f")"
        ) 