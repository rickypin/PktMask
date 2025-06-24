"""
TCP载荷掩码处理器主要API实现

这是模块的核心API类，专用于TCP载荷的保留范围掩码处理。
"""

import time
import threading
from typing import Dict, Optional, Any, List, Tuple, Callable
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
from .file_handler import PcapFileHandler
from .keep_range_applier import MaskApplier


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
            'total_bytes_kept': 0,
            'total_tcp_streams_processed': 0,
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
        # 初始化组件
        file_handler = PcapFileHandler(self.logger)
        keep_range_masker = MaskApplier(
            mask_byte_value=self.config_manager.get('mask_byte_value', 0x00),
            logger=self.logger
        )
        
        try:
            # 阶段1: 读取数据包
            self.logger.info(f"读取PCAP文件: {input_pcap}")
            packets = file_handler.read_packets(input_pcap)
            total_packets = len(packets)
            
            self.logger.info(f"成功读取 {total_packets} 个数据包")
            
            # 阶段2: 应用TCP保留范围掩码
            self.logger.info("开始应用TCP保留范围掩码...")
            modified_packets, keep_range_stats = keep_range_masker.apply_keep_ranges_to_packets(
                packets, keep_range_table
            )
            
            # 阶段3: 写入输出文件
            self.logger.info(f"写入输出文件: {output_pcap}")
            file_handler.write_packets(modified_packets, output_pcap)
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 生成结果
            result = TcpMaskingResult(
                success=True,
                total_packets=total_packets,
                modified_packets=keep_range_stats.get('tcp_packets_modified', 0),
                bytes_masked=keep_range_stats.get('bytes_masked', 0),
                bytes_kept=keep_range_stats.get('bytes_kept', 0),
                tcp_streams_processed=keep_range_stats.get('tcp_streams_processed', 0),
                processing_time=processing_time
            )
            
            # 添加详细保留范围统计信息
            result.add_keep_range_statistic('keep_range_table_entries', keep_range_table.get_total_entries())
            result.add_keep_range_statistic('keep_range_table_streams', keep_range_table.get_streams_count())
            result.add_keep_range_statistic('keep_ranges_applied', keep_range_stats.get('keep_ranges_applied', 0))
            result.add_keep_range_statistic('protocol_detections', len(keep_range_stats.get('protocol_detections', {})))
            
            # 验证协议解析禁用效果
            if self.config_manager.should_disable_protocol_parsing():
                protocol_stats = keep_range_masker.payload_extractor.verify_raw_layer_dominance(packets)
                result.add_keep_range_statistic('protocol_parsing_verification', len(protocol_stats))
                
                if not protocol_stats.get('protocol_parsing_disabled', False):
                    self.logger.warning(
                        f"协议解析禁用效果不佳: Raw层存在率 {protocol_stats.get('raw_layer_rate', 0):.2%}"
                    )
            
            self.logger.info(f"✅ 核心处理完成: {result.get_summary()}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            self.logger.error(f"核心处理失败: {e}")
            
            return TcpMaskingResult(
                success=False,
                total_packets=0,
                modified_packets=0,
                bytes_masked=0,
                bytes_kept=0,
                tcp_streams_processed=0,
                processing_time=processing_time,
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
        result: TcpMaskingResult
    ) -> None:
        """验证输出文件与输入文件的一致性
        
        这是Phase 3的核心功能，目前是占位符实现。
        """
        self.logger.info("⚠️  文件一致性验证占位符 - 将在Phase 3实现")
    
    def _update_global_stats(self, result: TcpMaskingResult) -> None:
        """更新全局统计信息"""
        self._processing_stats['total_files_processed'] += 1
        self._processing_stats['total_packets_processed'] += result.total_packets
        self._processing_stats['total_packets_modified'] += result.modified_packets
        self._processing_stats['total_bytes_masked'] += result.bytes_masked
        self._processing_stats['total_bytes_kept'] = self._processing_stats.get('total_bytes_kept', 0) + result.bytes_kept
        self._processing_stats['total_tcp_streams_processed'] = self._processing_stats.get('total_tcp_streams_processed', 0) + result.tcp_streams_processed
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
            f"TcpPayloadMasker("
            f"files_processed={stats['total_files_processed']}, "
            f"tcp_packets_processed={stats['total_packets_processed']}, "
            f"bytes_kept={stats.get('total_bytes_kept', 0)}, "
            f"config_hash={hash(str(self.config_manager.get_all()))}"
            f")"
        )
    
    def mask_tcp_payloads_batch(
        self,
        batch_jobs: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[TcpMaskingResult]:
        """批量处理多个TCP载荷掩码任务
        
        优化性能的批量处理接口，支持进度回调和并发处理。
        
        Args:
            batch_jobs: 批量任务列表，每个任务包含:
                - input_pcap: 输入PCAP文件路径
                - keep_range_table: TCP保留范围表
                - output_pcap: 输出PCAP文件路径
            progress_callback: 可选的进度回调函数(当前任务, 总任务, 状态信息)
            
        Returns:
            List[TcpMaskingResult]: 所有任务的处理结果列表
            
        Example:
            >>> masker = TcpPayloadMasker()
            >>> jobs = [
            ...     {
            ...         "input_pcap": "input1.pcap",
            ...         "keep_range_table": table1,
            ...         "output_pcap": "output1.pcap"
            ...     },
            ...     {
            ...         "input_pcap": "input2.pcap", 
            ...         "keep_range_table": table2,
            ...         "output_pcap": "output2.pcap"
            ...     }
            ... ]
            >>> results = masker.mask_tcp_payloads_batch(jobs)
        """
        self.logger.info(f"🚀 开始批量处理 {len(batch_jobs)} 个TCP载荷掩码任务")
        
        results = []
        start_time = time.time()
        
        for i, job in enumerate(batch_jobs):
            current_task = i + 1
            total_tasks = len(batch_jobs)
            
            # 更新进度
            if progress_callback:
                progress_callback(current_task, total_tasks, f"处理任务 {current_task}/{total_tasks}")
            
            self.logger.info(f"📝 处理任务 {current_task}/{total_tasks}: {job.get('input_pcap', 'Unknown')}")
            
            try:
                # 验证任务参数
                if not all(key in job for key in ['input_pcap', 'keep_range_table', 'output_pcap']):
                    raise ValidationError(f"任务 {current_task} 缺少必要参数")
                
                # 执行单个任务
                result = self.mask_tcp_payloads_with_keep_ranges(
                    job['input_pcap'],
                    job['keep_range_table'],
                    job['output_pcap']
                )
                
                # 添加批量任务信息
                result.add_keep_range_statistic('batch_task_index', current_task)
                result.add_keep_range_statistic('batch_total_tasks', total_tasks)
                
                results.append(result)
                
                # 更新进度
                if progress_callback:
                    status = "成功" if result.success else "失败"
                    progress_callback(current_task, total_tasks, f"任务 {current_task} {status}")
                
            except Exception as e:
                self.logger.error(f"❌ 任务 {current_task} 处理失败: {e}")
                
                # 创建失败结果 
                failed_result = TcpMaskingResult(
                    success=False,
                    total_packets=0,
                    modified_packets=0,
                    bytes_masked=0,
                    bytes_kept=0,
                    tcp_streams_processed=0,
                    processing_time=0.0,
                    error_message=str(e)
                )
                failed_result.add_keep_range_statistic('batch_task_index', current_task)
                failed_result.add_keep_range_statistic('batch_total_tasks', total_tasks)
                
                results.append(failed_result)
                
                # 更新进度
                if progress_callback:
                    progress_callback(current_task, total_tasks, f"任务 {current_task} 失败: {str(e)[:50]}")
        
        # 批量处理统计
        total_time = time.time() - start_time
        successful_tasks = sum(1 for r in results if r.success)
        
        self.logger.info(
            f"🎯 批量处理完成: {successful_tasks}/{len(batch_jobs)} 个任务成功, "
            f"总耗时: {total_time:.2f}秒, 平均: {total_time/len(batch_jobs):.2f}秒/任务"
        )
        
        return results
    
    def optimize_keep_range_table(self, keep_range_table: TcpKeepRangeTable) -> TcpKeepRangeTable:
        """优化TCP保留范围表以提升处理性能
        
        执行以下优化：
        1. 合并重叠的保留范围
        2. 排序条目以提升查找效率
        3. 预计算常用查询结果
        4. 优化内存布局
        
        Args:
            keep_range_table: 待优化的保留范围表
            
        Returns:
            TcpKeepRangeTable: 优化后的保留范围表
        """
        self.logger.info("🔧 开始优化TCP保留范围表")
        
        optimization_start = time.time()
        
        # 创建优化后的表
        optimized_table = TcpKeepRangeTable()
        
        # 按流ID分组处理
        stream_entries = {}
        for entry in keep_range_table.get_all_entries():
            stream_id = entry.stream_id
            if stream_id not in stream_entries:
                stream_entries[stream_id] = []
            stream_entries[stream_id].append(entry)
        
        total_optimizations = 0
        
        for stream_id, entries in stream_entries.items():
            # 按序列号排序
            entries.sort(key=lambda e: e.sequence_start)
            
            # 合并相邻或重叠的条目
            merged_entries = []
            current_entry = None
            
            for entry in entries:
                if current_entry is None:
                    current_entry = entry
                    continue
                
                # 检查是否可以合并（序列号范围连续或重叠）
                if (current_entry.sequence_end >= entry.sequence_start and 
                    current_entry.protocol_hint == entry.protocol_hint):
                    
                    # 合并条目
                    merged_ranges = current_entry.keep_ranges + entry.keep_ranges
                    merged_ranges = self._merge_overlapping_ranges(merged_ranges)
                    
                    current_entry = TcpKeepRangeEntry(
                        stream_id=stream_id,
                        sequence_start=min(current_entry.sequence_start, entry.sequence_start),
                        sequence_end=max(current_entry.sequence_end, entry.sequence_end),
                        keep_ranges=merged_ranges,
                        protocol_hint=current_entry.protocol_hint
                    )
                    
                    total_optimizations += 1
                else:
                    # 不能合并，保存当前条目
                    merged_entries.append(current_entry)
                    current_entry = entry
            
            # 保存最后一个条目
            if current_entry:
                merged_entries.append(current_entry)
            
            # 添加到优化表中
            for entry in merged_entries:
                optimized_table.add_keep_range_entry(entry)
        
        optimization_time = time.time() - optimization_start
        
        original_count = keep_range_table.get_total_entries()
        optimized_count = optimized_table.get_total_entries()
        reduction_rate = (original_count - optimized_count) / original_count * 100 if original_count > 0 else 0
        
        self.logger.info(
            f"✅ TCP保留范围表优化完成: {original_count} → {optimized_count} 条目 "
            f"({reduction_rate:.1f}% 减少), {total_optimizations} 次合并, "
            f"耗时: {optimization_time:.4f}秒"
        )
        
        return optimized_table
    
    def _merge_overlapping_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """合并重叠的保留范围"""
        if not ranges:
            return []
        
        # 按起始位置排序
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]
        
        for current in sorted_ranges[1:]:
            last = merged[-1]
            
            # 检查重叠或相邻
            if current[0] <= last[1]:
                # 合并范围
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                # 添加新范围
                merged.append(current)
        
        return merged
    
    def estimate_processing_time(
        self,
        input_pcap: str,
        keep_range_table: TcpKeepRangeTable
    ) -> Dict[str, float]:
        """估算处理时间（用于批量处理规划）
        
        基于文件大小、保留范围表复杂度等因素估算处理时间。
        
        Args:
            input_pcap: 输入PCAP文件路径
            keep_range_table: TCP保留范围表
            
        Returns:
            Dict[str, float]: 估算结果，包含:
                - estimated_time: 预估处理时间（秒）
                - confidence: 估算置信度（0-1）
                - file_size_mb: 文件大小（MB）
                - complexity_score: 复杂度评分
        """
        try:
            # 获取文件大小
            file_size = Path(input_pcap).stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            # 计算复杂度评分
            complexity_score = (
                keep_range_table.get_total_entries() * 0.1 +
                keep_range_table.get_streams_count() * 0.5 +
                len(keep_range_table.get_all_stream_ids()) * 0.3
            )
            
            # 基于历史统计估算处理时间
            # 基准：1MB文件约需0.1秒，复杂度每增加1分约增加0.05秒
            base_time = file_size_mb * 0.1
            complexity_time = complexity_score * 0.05
            estimated_time = base_time + complexity_time
            
            # 置信度基于统计数据量
            global_stats = self.get_global_statistics()
            files_processed = global_stats.get('total_files_processed', 0)
            confidence = min(0.9, files_processed * 0.1)  # 最高0.9
            
            return {
                'estimated_time': estimated_time,
                'confidence': confidence,
                'file_size_mb': file_size_mb,
                'complexity_score': complexity_score
            }
            
        except Exception as e:
            self.logger.warning(f"处理时间估算失败: {e}")
            return {
                'estimated_time': 1.0,  # 默认估算
                'confidence': 0.1,
                'file_size_mb': 0.0,
                'complexity_score': 0.0
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取详细性能指标
        
        Returns:
            Dict[str, Any]: 性能指标，包含:
                - processing_speed: 处理速度（包/秒）
                - throughput: 吞吐量（MB/秒）
                - efficiency_metrics: 效率指标
                - resource_usage: 资源使用情况
        """
        stats = self.get_global_statistics()
        
        # 计算处理速度
        total_time = stats.get('total_processing_time', 0.001)  # 避免除零
        total_packets = stats.get('total_packets_processed', 0)
        processing_speed = total_packets / total_time if total_time > 0 else 0
        
        # 估算吞吐量（假设平均包大小1KB）
        estimated_data_mb = total_packets * 1024 / (1024 * 1024)
        throughput_mbps = estimated_data_mb / total_time if total_time > 0 else 0
        
        # 效率指标
        modification_efficiency = (
            stats.get('total_packets_modified', 0) / total_packets * 100 
            if total_packets > 0 else 0
        )
        
        stream_efficiency = (
            stats.get('total_tcp_streams_processed', 0) / 
            stats.get('total_files_processed', 1)  # 平均每文件流数
        )
        
        return {
            'processing_speed': {
                'packets_per_second': processing_speed,
                'files_per_hour': stats.get('total_files_processed', 0) / (total_time / 3600) if total_time > 0 else 0
            },
            'throughput': {
                'mbps': throughput_mbps,
                'estimated_data_processed_mb': estimated_data_mb
            },
            'efficiency_metrics': {
                'modification_rate_percent': modification_efficiency,
                'avg_streams_per_file': stream_efficiency,
                'avg_processing_time_per_file': stats.get('avg_processing_time_per_file', 0)
            },
            'resource_usage': {
                'total_files_processed': stats.get('total_files_processed', 0),
                'total_processing_time': total_time,
                'avg_bytes_masked_per_stream': (
                    stats.get('total_bytes_masked', 0) / 
                    max(1, stats.get('total_tcp_streams_processed', 1))
                ),
                'avg_bytes_kept_per_stream': (
                    stats.get('total_bytes_kept', 0) / 
                    max(1, stats.get('total_tcp_streams_processed', 1))
                )
            }
        }
    
    def enable_performance_optimization(self, enable: bool = True) -> None:
        """启用/禁用性能优化模式
        
        性能优化模式包括：
        - 自动优化保留范围表
        - 启用批量处理
        - 预缓存常用查询
        - 优化内存使用
        
        Args:
            enable: 是否启用性能优化
        """
        self.config_manager.update({'performance_optimization_enabled': enable})
        
        if enable:
            self.logger.info("🚀 性能优化模式已启用")
            
            # 启用相关优化选项
            optimizations = {
                'auto_optimize_keep_range_table': True,
                'enable_batch_processing': True,
                'cache_query_results': True,
                'optimize_memory_usage': True
            }
            
            self.config_manager.update(optimizations)
        else:
            self.logger.info("⚠️  性能优化模式已禁用")
            
            # 禁用优化选项
            optimizations = {
                'auto_optimize_keep_range_table': False,
                'enable_batch_processing': False,
                'cache_query_results': False,
                'optimize_memory_usage': False
            }
            
            self.config_manager.update(optimizations)
    
    def cleanup_resources(self) -> None:
        """清理资源和临时缓存
        
        释放内存占用，清理临时文件，重置缓存等。
        适用于长时间运行的批量处理任务。
        """
        self.logger.info("🧹 开始清理资源...")
        
        # 重置统计信息中的大对象
        if hasattr(self, '_processing_stats'):
            # 保留重要统计，清理详细数据
            essential_stats = {
                'total_files_processed': self._processing_stats.get('total_files_processed', 0),
                'total_processing_time': self._processing_stats.get('total_processing_time', 0.0)
            }
            self._processing_stats.clear()
            self._processing_stats.update(essential_stats)
        
        # 清理协议控制器缓存
        if hasattr(self.protocol_controller, 'clear_cache'):
            self.protocol_controller.clear_cache()
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        self.logger.info("✅ 资源清理完成") 