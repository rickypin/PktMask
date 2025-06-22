"""
TCP载荷掩码处理器主要API实现

这是模块的核心API类，专用于TCP载荷的保留范围掩码处理。
"""

import time
import threading
from typing import Dict, Optional, Any
import logging
from pathlib import Path

from .keep_range_models import TcpKeepRangeEntry, TcpMaskingResult, TcpKeepRangeTable
from .config import ConfigManager, create_config_manager
from .protocol_control import ProtocolBindingController
from ..exceptions import (
    TcpPayloadMaskerError,
    ProtocolBindingError, 
    FileConsistencyError,
    ValidationError
)


class TcpPayloadMasker:
    """TCP载荷掩码处理器
    
    专用于TCP载荷的保留范围掩码处理。采用隐私优先设计理念：
    默认掩码所有TCP载荷，但保留指定的协议头部范围。
    
    主要特性：
    - TCP专用：只处理TCP协议，不支持其他协议
    - 保留范围：记录要保留的字节范围，其余全部掩码为0x00
    - 隐私优先：默认掩码所有载荷，最大化隐私保护
    - 协议保留：支持TLS/HTTP/SSH等协议头部自动保留
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
        
        self.logger.info("✅ TCP载荷掩码处理器初始化完成")
        self.logger.debug(f"配置摘要: {self.config_manager.export_summary()}")
    
    def mask_tcp_payloads_with_keep_ranges(
        self,
        input_pcap: str,
        keep_range_table: TcpKeepRangeTable,
        output_pcap: str
    ) -> TcpMaskingResult:
        """主要API接口：对TCP载荷应用保留范围掩码
        
        采用隐私优先原则：默认掩码所有TCP载荷，只保留指定的字节范围。
        专用于TCP协议，不处理其他协议类型。
        
        Args:
            input_pcap: 输入PCAP文件路径
            keep_range_table: TCP保留范围表
            output_pcap: 输出PCAP文件路径
            
        Returns:
            TcpMaskingResult: 处理结果和详细统计信息
            
        Raises:
            ValidationError: 输入参数无效
            FileNotFoundError: 文件不存在
            ProtocolBindingError: 协议解析控制失败
            FileConsistencyError: 文件一致性验证失败
            TcpPayloadMaskerError: 其他处理错误
            
        Example:
            >>> masker = TcpPayloadMasker()
            >>> keep_range_table = TcpKeepRangeTable()
            >>> keep_range_table.add_keep_range_entry(TcpKeepRangeEntry(
            ...     stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            ...     sequence_start=1000,
            ...     sequence_end=2000,
            ...     keep_ranges=[(0, 5)],  # 保留TLS头部5字节
            ...     protocol_hint="TLS"
            ... ))
            >>> result = masker.mask_tcp_payloads_with_keep_ranges(
            ...     "input.pcap", keep_range_table, "output.pcap"
            ... )
            >>> print(f"成功处理 {result.modified_packets} 个TCP数据包")
        """
        start_time = time.time()
        
        # 初始化结果对象
        result = TcpMaskingResult(
            success=False,
            total_packets=0,
            modified_packets=0,
            bytes_masked=0,
            bytes_kept=0,
            tcp_streams_processed=0,
            processing_time=0.0
        )
        
        try:
            self.logger.info(f"🚀 开始处理PCAP文件: {input_pcap} -> {output_pcap}")
            
            # 阶段1: 输入验证
            self._validate_inputs(input_pcap, keep_range_table, output_pcap)
            self.logger.debug("✅ 输入验证通过")
            
            # 阶段2: 协议解析控制（Phase 2实现）
            if self.config_manager.should_disable_protocol_parsing():
                self.protocol_controller.disable_protocol_parsing()
                self.logger.debug("✅ 协议解析已禁用")
            
            try:
                # 阶段3: 核心处理逻辑
                result = self._process_pcap_file(input_pcap, keep_range_table, output_pcap, start_time)
                
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
        keep_range_table: TcpKeepRangeTable,
        output_pcap: str
    ) -> None:
        """验证输入参数
        
        Args:
            input_pcap: 输入文件路径
            keep_range_table: TCP保留范围表
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
        
        # 验证TCP保留范围表
        if not isinstance(keep_range_table, TcpKeepRangeTable):
            raise ValidationError("keep_range_table必须是TcpKeepRangeTable类型")
        
        if keep_range_table.get_total_entries() == 0:
            raise ValidationError("TCP保留范围表为空，没有需要处理的条目")
        
        # 验证保留范围表一致性
        consistency_issues = keep_range_table.validate_consistency()
        if consistency_issues:
            raise ValidationError(f"TCP保留范围表一致性检查失败: {'; '.join(consistency_issues)}")
        
        # 验证输出路径
        output_path = Path(output_pcap)
        if output_path.exists() and output_path.is_dir():
            raise ValidationError(f"输出路径是目录: {output_pcap}")
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.debug(
            f"输入验证完成: 输入文件={input_path.stat().st_size}字节, "
            f"TCP保留范围条目={keep_range_table.get_total_entries()}个, "
            f"TCP流数量={keep_range_table.get_streams_count()}个"
        )
    
    def _process_pcap_file(
        self,
        input_pcap: str,
        keep_range_table: TcpKeepRangeTable,
        output_pcap: str,
        start_time: float
    ) -> TcpMaskingResult:
        """处理PCAP文件的核心逻辑
        
        Args:
            input_pcap: 输入文件路径
            keep_range_table: TCP保留范围表
            output_pcap: 输出文件路径
            start_time: 开始时间
            
        Returns:
            TcpMaskingResult: 处理结果
        """
        from .file_handler import PcapFileHandler
        from .keep_range_applier import TcpPayloadKeepRangeMasker
        
        # 初始化组件
        file_handler = PcapFileHandler(self.logger)
        keep_range_masker = TcpPayloadKeepRangeMasker(
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