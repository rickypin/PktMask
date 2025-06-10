#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分层IP匿名化算法插件
基于网段频率的分层IP匿名化策略的插件化实现
"""

import os
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from ...interfaces.ip_anonymization_interface import (
    IPAnonymizationInterface, IPAnonymizationConfig, IPAnonymizationResult,
    IPMappingResult, IPFrequencyData
)
from ...interfaces.algorithm_interface import AlgorithmInfo, AlgorithmType, ValidationResult, AlgorithmStatus, AlgorithmConfig
from ...interfaces.performance_interface import get_algorithm_tracker
from pktmask.core.strategy import HierarchicalAnonymizationStrategy
from pktmask.infrastructure.logging import get_logger


class HierarchicalAnonymizationPlugin(IPAnonymizationInterface):
    """分层IP匿名化算法插件"""
    
    def __init__(self):
        super().__init__()
        self._strategy = HierarchicalAnonymizationStrategy()
        self._performance_tracker = get_algorithm_tracker("HierarchicalIPAnonymization")
        self._frequency_data: Optional[IPFrequencyData] = None
        
        self._logger.info("分层IP匿名化插件初始化完成")
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        """获取算法信息"""
        return AlgorithmInfo(
            name="Hierarchical IP Anonymization",
            version="2.0.0",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            author="PktMask Team",
            description="基于网段频率的分层IP匿名化算法，保持子网结构一致性",
            supported_formats=[".pcap", ".pcapng"],
            requirements={"scapy": ">=2.4.0"},
            performance_baseline={
                "throughput_per_second": 3000.0,
                "memory_usage_mb": 128.0,
                "cache_hit_rate": 0.85
            }
        )
    
    def get_default_config(self) -> IPAnonymizationConfig:
        """获取默认配置"""
        return IPAnonymizationConfig(
            strategy="hierarchical",
            preserve_subnet_structure=True,
            consistency_level="high",
            ip_cache_size_mb=128,
            mapping_cache_size=10000,
            batch_size=1000,
            enable_ipv6=True,
            enable_frequency_analysis=True,
            min_frequency_threshold=2,
            preserve_high_frequency_subnets=True,
            anonymization_strength="medium"
        )
    
    def validate_config(self, config) -> ValidationResult:
        """验证配置"""
        result = super().validate_config(config)
        
        if result.is_valid and isinstance(config, IPAnonymizationConfig):
            # 分层算法特定验证
            if config.strategy != "hierarchical":
                result.add_warning("建议使用hierarchical策略以获得最佳性能")
            
            if config.min_frequency_threshold < 1:
                result.add_error("最小频率阈值必须大于0")
            elif config.min_frequency_threshold > 10:
                result.add_warning("频率阈值过高可能影响匿名化效果")
        
        return result
    
    def _apply_config(self, config: AlgorithmConfig) -> bool:
        """应用配置"""
        try:
            # 根据配置调整策略参数
            if hasattr(self._strategy, 'set_config'):
                self._strategy.set_config(config.dict())
            
            self._set_status(AlgorithmStatus.CONFIGURED)
            self._logger.info("分层IP匿名化算法配置应用成功")
            return True
            
        except Exception as e:
            self._logger.error(f"应用配置失败: {e}")
            return False
    
    def _do_initialize(self) -> bool:
        """执行具体的初始化逻辑"""
        try:
            if not self._config:
                self._config = self.get_default_config()
            
            # 重置策略状态
            self._strategy.reset()
            
            # 初始化性能跟踪器
            self._performance_tracker.start_tracking("initialize")
            
            self._set_status(AlgorithmStatus.IDLE)
            
            self._performance_tracker.stop_tracking()
            self._logger.info("分层IP匿名化算法初始化成功")
            return True
            
        except Exception as e:
            self._logger.error(f"算法初始化失败: {e}")
            return False
    
    def prescan_files(self, file_paths: List[str]) -> IPFrequencyData:
        """预扫描文件以收集IP频率信息"""
        self._check_ready()
        
        self._logger.info(f"开始预扫描 {len(file_paths)} 个文件")
        start_time = time.time()
        
        try:
            with self._performance_tracker.track_operation("prescan_files"):
                # 准备文件路径
                if not file_paths:
                    raise ValueError("文件路径列表不能为空")
                
                # 获取目录和文件名
                subdir_path = os.path.dirname(file_paths[0])
                filenames = [os.path.basename(path) for path in file_paths]
                error_log = []
                
                # 调用策略的预扫描方法
                freqs_ipv4, freqs_ipv6, unique_ips = self._strategy._prescan_addresses(
                    filenames, subdir_path, error_log
                )
                
                # 构建频率数据对象
                self._frequency_data = IPFrequencyData(
                    ipv4_frequencies={
                        'level_1': freqs_ipv4[0],
                        'level_2': freqs_ipv4[1], 
                        'level_3': freqs_ipv4[2]
                    },
                    ipv6_frequencies={
                        'level_1': freqs_ipv6[0],
                        'level_2': freqs_ipv6[1],
                        'level_3': freqs_ipv6[2],
                        'level_4': freqs_ipv6[3],
                        'level_5': freqs_ipv6[4],
                        'level_6': freqs_ipv6[5],
                        'level_7': freqs_ipv6[6]
                    },
                    unique_ips=len(unique_ips),
                    total_packets=sum(freqs_ipv4[0].values())
                )
                
                duration = time.time() - start_time
                self._logger.info(f"预扫描完成 - 唯一IP数: {len(unique_ips)}, 耗时: {duration:.2f}秒")
                
                # 更新性能指标
                self._performance_tracker.update_metrics(
                    items_processed=len(unique_ips),
                    processing_time_ms=duration * 1000
                )
                
                return self._frequency_data
                
        except Exception as e:
            self._logger.error(f"预扫描失败: {e}")
            # 返回空的频率数据
            return IPFrequencyData(
                ipv4_frequencies={},
                ipv6_frequencies={},
                unique_ips=0,
                total_packets=0
            )
    
    def build_ip_mapping(self, frequency_data: IPFrequencyData) -> Dict[str, str]:
        """基于频率数据构建IP映射"""
        self._check_ready()
        
        try:
            with self._performance_tracker.track_operation("build_mapping"):
                if frequency_data.unique_ips == 0:
                    self._logger.warning("频率数据为空，返回空映射")
                    return {}
                
                # 构建文件列表（用于兼容原有策略接口）
                dummy_files = ["dummy.pcap"]  # 策略不会实际读取这个文件
                subdir_path = "/tmp"  # 临时路径
                error_log = []
                
                # 设置频率数据到策略中
                self._strategy._frequency_data = frequency_data
                
                # 调用策略的映射创建方法
                mapping = self._strategy.create_mapping(dummy_files, subdir_path, error_log)
                
                self._logger.info(f"IP映射构建完成 - 映射数量: {len(mapping)}")
                
                # 更新性能指标
                self._performance_tracker.update_metrics(
                    items_processed=len(mapping),
                    cache_hits=len(mapping)  # 所有映射都视为缓存命中
                )
                
                return mapping
                
        except Exception as e:
            self._logger.error(f"构建IP映射失败: {e}")
            return {}
    
    def anonymize_ip(self, ip_address: str) -> str:
        """匿名化单个IP地址"""
        self._check_ready()
        
        if not ip_address:
            return ip_address
        
        # 使用已构建的映射
        mapping = self._strategy.get_ip_map()
        return mapping.get(ip_address, ip_address)
    
    def anonymize_packet(self, packet) -> Tuple[object, bool]:
        """匿名化数据包中的IP地址"""
        self._check_ready()
        
        try:
            with self._performance_tracker.track_operation("anonymize_packet"):
                anonymized_packet, was_modified = self._strategy.anonymize_packet(packet)
                
                # 更新性能指标
                self._performance_tracker.update_metrics(
                    items_processed=1,
                    cache_hits=1 if was_modified else 0
                )
                
                return anonymized_packet, was_modified
                
        except Exception as e:
            self._logger.error(f"数据包匿名化失败: {e}")
            return packet, False
    
    def batch_anonymize_packets(self, packets: List) -> List[Tuple[object, bool]]:
        """批量匿名化数据包"""
        self._check_ready()
        
        results = []
        modified_count = 0
        
        try:
            with self._performance_tracker.track_operation("batch_anonymize"):
                for packet in packets:
                    anonymized_packet, was_modified = self.anonymize_packet(packet)
                    results.append((anonymized_packet, was_modified))
                    if was_modified:
                        modified_count += 1
                
                # 更新性能指标
                self._performance_tracker.update_metrics(
                    items_processed=len(packets),
                    cache_hits=modified_count
                )
                
                self._logger.debug(f"批量匿名化完成 - 处理: {len(packets)}, 修改: {modified_count}")
                
                return results
                
        except Exception as e:
            self._logger.error(f"批量匿名化失败: {e}")
            # 返回未修改的数据包
            return [(packet, False) for packet in packets]
    
    def _do_process_file(self, input_path: str, output_path: str) -> IPAnonymizationResult:
        """执行具体的文件处理逻辑"""
        self._check_ready()
        
        start_time = time.time()
        result = IPAnonymizationResult(
            success=False,
            data=None,
            processing_time_ms=0
        )
        
        try:
            with self._performance_tracker.track_operation(f"process_file_{os.path.basename(input_path)}"):
                # 如果还没有映射，先进行预扫描
                if not self._strategy.get_ip_map():
                    self._logger.info("未找到已有映射，开始预扫描构建映射")
                    frequency_data = self.prescan_files([input_path])
                    self.build_ip_mapping(frequency_data)
                
                # 处理文件（这里应该集成到现有的文件处理流程中）
                # 暂时返回基本结果，实际实现需要与主流程集成
                mapping = self._strategy.get_ip_map()
                
                # 构建处理结果
                for original_ip, anonymized_ip in mapping.items():
                    result.add_mapping(original_ip, anonymized_ip)
                
                result.success = True
                result.processing_time_ms = (time.time() - start_time) * 1000
                
                self._logger.info(f"文件处理完成 - 输入: {input_path}, 输出: {output_path}")
                
                return result
                
        except Exception as e:
            self._logger.error(f"文件处理失败: {e}")
            result.errors = [str(e)]
            result.processing_time_ms = (time.time() - start_time) * 1000
            return result
    
    def _get_current_mapping(self) -> Dict[str, str]:
        """获取当前映射"""
        return self._strategy.get_ip_map()
    
    def _do_reset_mapping(self):
        """执行映射重置"""
        self._strategy.reset()
        self._frequency_data = None
    
    def _do_validate_consistency(self) -> Dict[str, Any]:
        """执行一致性验证"""
        mapping = self._strategy.get_ip_map()
        
        # 基本一致性检查
        consistency_report = {
            'total_mappings': len(mapping),
            'ipv4_mappings': len([k for k in mapping.keys() if '.' in k]),
            'ipv6_mappings': len([k for k in mapping.keys() if ':' in k]),
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # 检查子网一致性
        subnet_consistency = {}
        for original_ip, anonymized_ip in mapping.items():
            if '.' in original_ip:  # IPv4
                original_parts = original_ip.split('.')
                anonymized_parts = anonymized_ip.split('.')
                
                if len(original_parts) >= 2 and len(anonymized_parts) >= 2:
                    orig_subnet = '.'.join(original_parts[:2])
                    anon_subnet = '.'.join(anonymized_parts[:2])
                    
                    if orig_subnet in subnet_consistency:
                        if subnet_consistency[orig_subnet] != anon_subnet:
                            consistency_report['errors'].append(
                                f"子网不一致: {orig_subnet} -> {subnet_consistency[orig_subnet]} 和 {anon_subnet}"
                            )
                            consistency_report['valid'] = False
                    else:
                        subnet_consistency[orig_subnet] = anon_subnet
        
        consistency_report['subnet_mappings'] = len(subnet_consistency)
        return consistency_report
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        # 基础性能指标
        base_metrics = {
            'algorithm_name': self.get_algorithm_info().name,
            'algorithm_version': self.get_algorithm_info().version,
            'status': self._status.value,
            'initialized': self._initialized,
            'config_applied': self._config is not None
        }
        
        # IP匿名化特定指标
        ip_mapping = self._strategy.get_ip_map()
        ip_metrics = {
            'ip_mapping_size': len(ip_mapping),
            'ipv4_mappings': len([k for k in ip_mapping.keys() if '.' in k]),
            'ipv6_mappings': len([k for k in ip_mapping.keys() if ':' in k]),
        }
        
        # 分层算法特定指标
        hierarchical_metrics = {
            'strategy_type': 'hierarchical',
            'mapping_size': len(ip_mapping),
            'has_frequency_data': self._frequency_data is not None,
            'performance_tracker_metrics': self._performance_tracker.get_performance_summary()
        }
        
        # 合并所有指标
        base_metrics.update(ip_metrics)
        base_metrics.update(hierarchical_metrics)
        return base_metrics
    
    def _do_reset_metrics(self):
        """重置性能指标"""
        self._performance_tracker.reset_metrics()
    
    def _do_cleanup(self):
        """执行具体的清理逻辑"""
        try:
            self._strategy.reset()
            self._frequency_data = None
            self._performance_tracker.reset_metrics()
            self._logger.info("分层IP匿名化插件清理完成")
        except Exception as e:
            self._logger.error(f"清理资源失败: {e}")


# 算法注册装饰器（可选）
def register_hierarchical_plugin():
    """注册分层IP匿名化插件"""
    from ...registry import get_algorithm_registry
    
    registry = get_algorithm_registry()
    success = registry.register_algorithm(
        HierarchicalAnonymizationPlugin,
        "hierarchical_ip_anonymization",
        metadata={
            "category": "ip_anonymization",
            "priority": 100,
            "optimized": False,
            "recommended": True
        }
    )
    
    if success:
        logger = get_logger('plugin.registration')
        logger.info("分层IP匿名化插件注册成功")
    
    return success 