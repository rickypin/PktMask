"""
新一代 MaskPayload 阶段主类

实现基于双模块架构的新一代掩码处理阶段，集成 Marker 和 Masker 模块。
支持完全向后兼容的配置格式转换。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Union, Optional

from pktmask.core.pipeline.processor_stage import ProcessorStage
from pktmask.core.pipeline.models import StageStats


class NewMaskPayloadStage(ProcessorStage):
    """新一代掩码处理阶段
    
    基于双模块分离设计：
    - Marker模块: 协议分析和规则生成
    - Masker模块: 通用载荷掩码应用
    
    保持与现有 MaskPayloadStage 完全兼容的接口。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化新一代掩码处理阶段

        Args:
            config: 配置字典，支持以下参数：
                新格式:
                - protocol: 协议类型 ("tls", "http", "auto")
                - marker_config: Marker模块配置
                - masker_config: Masker模块配置
                - mode: 处理模式 ("enhanced", "basic")

                向后兼容格式:
                - recipe: MaskingRecipe 实例
                - recipe_dict: 配方字典
                - mode: "enhanced" 或 "basic"
        """
        super().__init__(config)
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        # 配置转换和标准化
        self.normalized_config = self._normalize_legacy_config(config)

        # 配置解析
        self.protocol = self.normalized_config.get('protocol', 'tls')
        self.mode = self.normalized_config.get('mode', 'enhanced')
        self.marker_config = self.normalized_config.get('marker_config', {})
        self.masker_config = self.normalized_config.get('masker_config', {})

        # 向后兼容性支持
        self.legacy_recipe = config.get('recipe')
        self.legacy_recipe_dict = config.get('recipe_dict')

        # 只有在没有新格式配置时才使用旧版模式
        has_new_format = 'protocol' in config or 'marker_config' in config or 'masker_config' in config
        has_recipe = self.legacy_recipe is not None or self.legacy_recipe_dict is not None
        self.use_legacy_mode = has_recipe and not has_new_format

        # 模块实例（延迟初始化）
        self.marker = None
        self.masker = None

        # 配置验证器（可选）
        self.config_validator = None

        self.logger.info(f"NewMaskPayloadStage 创建: protocol={self.protocol}, mode={self.mode}, "
                        f"legacy_mode={self.use_legacy_mode}")

    def _normalize_legacy_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """将旧版配置格式转换为新格式

        Args:
            config: 原始配置字典

        Returns:
            标准化的新格式配置
        """
        normalized = config.copy()

        # 检测各种配置格式
        has_recipe = 'recipe' in config or 'recipe_dict' in config or 'recipe_path' in config
        has_new_format = 'protocol' in config or 'marker_config' in config or 'masker_config' in config
        has_tls_config = any(key.startswith('tls_') for key in config.keys())
        has_gui_config = any(key in config for key in ['enable_anon', 'enable_dedup', 'enable_mask'])

        # 处理 recipe_path（已废弃但可能存在遗留配置）
        if 'recipe_path' in config:
            self.logger.warning("检测到已废弃的 recipe_path 配置，将忽略并使用智能协议分析")
            normalized.pop('recipe_path', None)

        if has_recipe and not has_new_format:
            # 纯旧版配置，转换为新格式
            self.logger.info("检测到旧版配置格式，正在转换为新格式")
            normalized = self._convert_legacy_recipe_config(normalized)

        elif has_tls_config and not has_new_format:
            # TLS 特定配置格式（来自 YAML 配置文件）
            self.logger.info("检测到 TLS 配置格式，正在转换为新格式")
            normalized = self._convert_tls_config(normalized)

        elif has_gui_config and not has_new_format:
            # GUI 配置格式
            self.logger.info("检测到 GUI 配置格式，正在转换为新格式")
            normalized = self._convert_gui_config(normalized)

        elif not has_recipe and not has_new_format and not has_tls_config and not has_gui_config:
            # 空配置或基础配置，设置默认值
            normalized = self._set_default_config(normalized)

        # 确保 mode 参数的兼容性
        normalized = self._normalize_mode_parameter(normalized)

        # 处理其他兼容性参数
        normalized = self._handle_compatibility_parameters(normalized)

        # 处理 TLS 配置的合并（即使在新格式中也要处理 TLS 特定参数）
        normalized = self._merge_tls_specific_params(normalized, config)

        return normalized

    def _convert_legacy_recipe_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """转换旧版配方配置"""
        normalized = config.copy()

        # 设置默认协议为 TLS（旧版主要处理 TLS）
        normalized.setdefault('protocol', 'tls')

        # 设置默认 marker 配置
        normalized.setdefault('marker_config', {
            'tls': {
                'preserve_handshake': True,
                'preserve_application_data': False,
                'preserve_alert': True,
                'preserve_change_cipher_spec': True
            }
        })

        # 设置默认 masker 配置
        normalized.setdefault('masker_config', {
            'chunk_size': 1000,
            'verify_checksums': True,
            'enable_performance_monitoring': True
        })

        return normalized

    def _convert_tls_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """转换 TLS 特定配置格式（来自 YAML 配置文件）"""
        normalized = config.copy()

        # 设置协议
        normalized.setdefault('protocol', 'tls')

        # 转换 TLS 策略配置
        marker_config = {'tls': {}}

        # 映射 TLS 策略到 marker 配置
        tls_strategy_mapping = {
            'tls_20_strategy': ('preserve_change_cipher_spec', 'keep_all'),
            'tls_21_strategy': ('preserve_alert', 'keep_all'),
            'tls_22_strategy': ('preserve_handshake', 'keep_all'),
            'tls_23_strategy': ('preserve_application_data', 'mask_payload'),
            'tls_24_strategy': ('preserve_heartbeat', 'keep_all'),
        }

        for config_key, (marker_key, strategy) in tls_strategy_mapping.items():
            if config_key in config:
                marker_config['tls'][marker_key] = (config[config_key] == 'keep_all')

        # 处理 TLS 23 头部保留字节数
        if 'tls_23_header_preserve_bytes' in config:
            marker_config['tls']['application_data_header_bytes'] = config['tls_23_header_preserve_bytes']

        # 处理非 TLS TCP 策略
        if 'non_tls_tcp_strategy' in config:
            marker_config['tcp'] = {
                'mask_non_tls_payload': (config['non_tls_tcp_strategy'] == 'mask_all_payload')
            }

        normalized['marker_config'] = marker_config

        # 设置 masker 配置
        masker_config = {
            'chunk_size': config.get('chunk_size', 1000),
            'verify_checksums': config.get('verify_checksums', True),
            'enable_performance_monitoring': config.get('enable_performance_monitoring', True),
            'keep_intermediate_files': config.get('keep_intermediate_files', False)
        }

        if 'temp_dir' in config:
            masker_config['temp_dir'] = config['temp_dir']

        normalized['masker_config'] = masker_config

        return normalized

    def _convert_gui_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """转换 GUI 配置格式"""
        normalized = config.copy()

        # GUI 配置主要影响是否启用掩码功能
        enable_mask = config.get('enable_mask', True)

        if enable_mask:
            # 启用掩码时使用默认 TLS 配置
            normalized.setdefault('protocol', 'tls')
            normalized.setdefault('mode', 'enhanced')
            normalized.setdefault('marker_config', {
                'tls': {
                    'preserve_handshake': True,
                    'preserve_application_data': False,
                    'preserve_alert': True,
                    'preserve_change_cipher_spec': True
                }
            })
            normalized.setdefault('masker_config', {
                'chunk_size': 1000,
                'verify_checksums': True
            })
        else:
            # 禁用掩码时使用基础模式
            normalized['mode'] = 'basic'
            normalized.setdefault('protocol', 'tls')
            normalized.setdefault('marker_config', {})
            normalized.setdefault('masker_config', {})

        return normalized

    def _set_default_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """设置默认配置"""
        normalized = config.copy()

        normalized.setdefault('protocol', 'tls')
        normalized.setdefault('mode', 'enhanced')
        normalized.setdefault('marker_config', {
            'tls': {
                'preserve_handshake': True,
                'preserve_application_data': False,
                'preserve_alert': True,
                'preserve_change_cipher_spec': True
            }
        })
        normalized.setdefault('masker_config', {
            'chunk_size': 1000,
            'verify_checksums': True,
            'enable_performance_monitoring': True
        })

        return normalized

    def _normalize_mode_parameter(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化 mode 参数"""
        normalized = config.copy()

        mode = normalized.get('mode', 'enhanced')
        if mode == 'processor_adapter':
            # 旧版的 processor_adapter 模式对应新版的 enhanced 模式
            normalized['mode'] = 'enhanced'
            self.logger.debug("将 processor_adapter 模式转换为 enhanced 模式")
        elif mode not in ['enhanced', 'basic', 'debug']:
            # 未知模式，降级到 enhanced
            self.logger.warning(f"未知模式 '{mode}'，降级到 enhanced 模式")
            normalized['mode'] = 'enhanced'

        return normalized

    def _handle_compatibility_parameters(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """处理其他兼容性参数"""
        normalized = config.copy()

        # 处理旧版参数映射
        legacy_param_mapping = {
            'preserve_ratio': ('masker_config', 'preserve_ratio'),
            'min_preserve_bytes': ('masker_config', 'min_preserve_bytes'),
            'enable_tls_processing': ('marker_config', 'enable_tls_processing'),
            'fallback_config': ('masker_config', 'fallback_config'),
        }

        for old_key, (section, new_key) in legacy_param_mapping.items():
            if old_key in config:
                if section not in normalized:
                    normalized[section] = {}
                normalized[section][new_key] = config[old_key]
                self.logger.debug(f"映射旧版参数 {old_key} 到 {section}.{new_key}")

        return normalized

    def _merge_tls_specific_params(self, normalized: Dict[str, Any], original_config: Dict[str, Any]) -> Dict[str, Any]:
        """合并 TLS 特定参数到现有配置中"""
        # 检查是否有 TLS 特定参数需要合并
        tls_params = {
            'tls_23_header_preserve_bytes': 'application_data_header_bytes',
        }

        for original_key, target_key in tls_params.items():
            if original_key in original_config:
                # 确保 marker_config.tls 存在
                if 'marker_config' not in normalized:
                    normalized['marker_config'] = {}
                if 'tls' not in normalized['marker_config']:
                    normalized['marker_config']['tls'] = {}

                # 合并参数
                normalized['marker_config']['tls'][target_key] = original_config[original_key]
                self.logger.debug(f"合并 TLS 参数 {original_key} 到 marker_config.tls.{target_key}")

        return normalized

    def initialize(self) -> bool:
        """初始化阶段

        Returns:
            初始化是否成功
        """
        if self._initialized:
            return True

        try:
            self.logger.info("开始初始化 NewMaskPayloadStage")

            # 配置验证（可选）
            if self._should_validate_config():
                validation_result = self._validate_config()
                if not validation_result.is_valid:
                    self.logger.error(f"配置验证失败: {validation_result.errors}")
                    return False
                if validation_result.warnings:
                    for warning in validation_result.warnings:
                        self.logger.warning(f"配置警告: {warning}")

            # 创建 Marker 模块
            self.marker = self._create_marker(self.normalized_config)
            if not self.marker.initialize():
                raise RuntimeError("Marker模块初始化失败")

            # 创建 Masker 模块
            self.masker = self._create_masker(self.normalized_config)

            self._initialized = True
            self.logger.info("NewMaskPayloadStage 初始化成功")
            return True

        except Exception as e:
            self.logger.error(f"NewMaskPayloadStage 初始化失败: {e}")
            return False
    
    def process_file(self, input_path: Union[str, Path],
                    output_path: Union[str, Path]) -> StageStats:
        """处理文件 - 与现有接口完全兼容

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径

        Returns:
            StageStats: 处理统计信息
        """
        if not self._initialized and not self.initialize():
            raise RuntimeError("NewMaskPayloadStage 未初始化")

        self.validate_inputs(input_path, output_path)

        input_path = Path(input_path)
        output_path = Path(output_path)

        self.logger.info(f"开始处理文件: {input_path} -> {output_path}")

        start_time = time.time()

        try:
            # 检查是否为 basic 模式（降级处理）
            if self.mode == 'basic':
                return self._process_with_basic_mode(input_path, output_path, start_time)

            # 检查是否使用旧版配方模式
            if self.use_legacy_mode:
                return self._process_with_legacy_mode(input_path, output_path, start_time)

            # 新版双模块处理模式
            return self._process_with_dual_module_mode(input_path, output_path, start_time)

        except Exception as e:
            self.logger.error(f"文件处理失败: {e}")
            raise

    def _process_with_dual_module_mode(self, input_path: Path, output_path: Path, start_time: float) -> StageStats:
        """使用新版双模块架构处理文件"""
        self.logger.debug("使用双模块架构处理模式")

        # 阶段1: 调用Marker模块生成KeepRuleSet
        self.logger.debug("阶段1: 生成保留规则")
        keep_rules = self.marker.analyze_file(str(input_path), self.normalized_config)

        # 阶段2: 调用Masker模块应用规则
        self.logger.debug("阶段2: 应用掩码规则")
        masking_stats = self.masker.apply_masking(str(input_path), str(output_path), keep_rules)

        # 阶段3: 转换统计信息
        stage_stats = self._convert_to_stage_stats(masking_stats)

        self.logger.info(f"双模块处理完成: 处理包数={stage_stats.packets_processed}, "
                        f"修改包数={stage_stats.packets_modified}")

        return stage_stats

    def _process_with_legacy_mode(self, input_path: Path, output_path: Path, start_time: float) -> StageStats:
        """使用旧版配方模式处理文件（向后兼容）"""
        self.logger.debug("使用旧版配方兼容模式")

        try:
            # 导入旧版处理器
            from pktmask.core.tcp_payload_masker.utils.helpers import create_masking_recipe_from_dict
            from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe

            # 获取配方
            recipe = None
            if self.legacy_recipe:
                recipe = self.legacy_recipe
            elif self.legacy_recipe_dict:
                recipe = create_masking_recipe_from_dict(self.legacy_recipe_dict)

            if recipe is None:
                raise RuntimeError("旧版模式下未找到有效的配方")

            # 使用旧版处理逻辑（简化实现）
            # 这里应该调用旧版的处理器，但为了保持架构一致性，
            # 我们将配方转换为新版的保留规则
            keep_rules = self._convert_recipe_to_keep_rules(recipe, str(input_path))

            # 使用新版 Masker 应用规则
            masking_stats = self.masker.apply_masking(str(input_path), str(output_path), keep_rules)

            # 转换统计信息
            stage_stats = self._convert_to_stage_stats(masking_stats)

            self.logger.info(f"旧版兼容处理完成: 处理包数={stage_stats.packets_processed}, "
                            f"修改包数={stage_stats.packets_modified}")

            return stage_stats

        except ImportError as e:
            self.logger.warning(f"无法导入旧版处理器，降级到基础模式: {e}")
            return self._process_with_basic_mode(input_path, output_path, start_time)

    def _process_with_basic_mode(self, input_path: Path, output_path: Path, start_time: float) -> StageStats:
        """基础模式处理（透传复制）"""
        self.logger.debug("使用基础模式（透传复制）")

        import shutil

        # 验证输入文件
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"输入路径不是文件: {input_path}")

        # 简单复制文件
        shutil.copy2(str(input_path), str(output_path))

        duration_ms = (time.time() - start_time) * 1000

        # 创建基础统计信息
        stage_stats = StageStats(
            stage_name=self.get_display_name(),
            packets_processed=0,  # 基础模式不统计包数
            packets_modified=0,
            duration_ms=duration_ms,
            extra_metrics={
                'mode': 'basic',
                'operation': 'passthrough_copy',
                'success': True,
                'file_size': input_path.stat().st_size
            }
        )

        self.logger.info(f"基础模式处理完成: 文件大小={stage_stats.extra_metrics['file_size']} 字节")

        return stage_stats

    def _create_marker(self, config: Dict[str, Any]):
        """创建 Marker 模块实例
        
        Args:
            config: 配置字典
            
        Returns:
            ProtocolMarker 实例
        """
        protocol = config.get('protocol', 'tls')
        
        if protocol == 'tls':
            from .marker.tls_marker import TLSProtocolMarker
            return TLSProtocolMarker(config.get('marker_config', {}))
        else:
            raise ValueError(f"不支持的协议: {protocol}")
    
    def _create_masker(self, config: Dict[str, Any]):
        """创建 Masker 模块实例
        
        Args:
            config: 配置字典
            
        Returns:
            PayloadMasker 实例
        """
        from .masker.payload_masker import PayloadMasker
        return PayloadMasker(config.get('masker_config', {}))
    
    def _convert_to_stage_stats(self, masking_stats) -> StageStats:
        """转换掩码统计信息为阶段统计信息
        
        Args:
            masking_stats: MaskingStats 实例
            
        Returns:
            StageStats 实例
        """
        return StageStats(
            stage_name=self.get_display_name(),
            packets_processed=masking_stats.processed_packets,
            packets_modified=masking_stats.modified_packets,
            duration_ms=masking_stats.execution_time * 1000,
            extra_metrics={
                'masked_bytes': masking_stats.masked_bytes,
                'preserved_bytes': masking_stats.preserved_bytes,
                'masking_ratio': masking_stats.masking_ratio,
                'preservation_ratio': masking_stats.preservation_ratio,
                'processing_speed_mbps': masking_stats.processing_speed_mbps,
                'protocol': self.protocol,
                'mode': self.mode,
                'success': masking_stats.success,
                'errors': masking_stats.errors,
                'warnings': masking_stats.warnings
            }
        )
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        return "Mask Payloads (v2)"
    
    def get_description(self) -> str:
        """获取描述信息"""
        return (
            f"新一代载荷掩码处理器 (协议: {self.protocol}, 模式: {self.mode})。"
            "基于双模块架构，支持协议分析与掩码应用分离。"
        )
    
    def get_required_tools(self) -> list[str]:
        """获取所需工具列表"""
        tools = ['scapy']
        if self.protocol == 'tls':
            tools.append('tshark')
        return tools
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.marker:
            self.marker.cleanup()
        if self.masker:
            # Masker 模块暂时没有清理方法
            pass
        self._initialized = False
        self.logger.debug("NewMaskPayloadStage 资源清理完成")

    def _should_validate_config(self) -> bool:
        """判断是否需要进行配置验证"""
        # 在调试模式或明确要求时进行配置验证
        return (
            self.normalized_config.get('validate_config', False) or
            self.normalized_config.get('mode') == 'debug'
            # 注意：不使用 logger.isEnabledFor(logging.DEBUG) 因为它在测试中总是返回 True
        )

    def _validate_config(self):
        """验证配置参数"""
        try:
            # 延迟导入配置验证器
            from .config_validator import ConfigValidator, ValidationResult

            if self.config_validator is None:
                self.config_validator = ConfigValidator()

            return self.config_validator.validate_config(self.normalized_config)

        except ImportError:
            # 如果配置验证器不可用，返回成功结果
            self.logger.debug("配置验证器不可用，跳过验证")
            from dataclasses import dataclass
            from typing import List

            @dataclass
            class ValidationResult:
                is_valid: bool = True
                errors: List[str] = None
                warnings: List[str] = None
                normalized_config: Dict[str, Any] = None

                def __post_init__(self):
                    if self.errors is None:
                        self.errors = []
                    if self.warnings is None:
                        self.warnings = []
                    if self.normalized_config is None:
                        self.normalized_config = {}

            return ValidationResult()

    def _convert_recipe_to_keep_rules(self, recipe, pcap_path: str):
        """将旧版配方转换为新版保留规则（简化实现）"""
        from .marker.types import KeepRuleSet, KeepRule, FlowInfo

        # 这是一个简化的转换实现
        # 实际应用中可能需要更复杂的逻辑来正确转换配方

        self.logger.warning("配方转换为保留规则的功能尚未完全实现，使用默认 TLS 分析")

        # 降级到使用 TLS 分析器
        if self.marker:
            return self.marker.analyze_file(pcap_path, self.normalized_config)
        else:
            # 返回空规则集
            return KeepRuleSet(
                rules=[],
                tcp_flows={},
                statistics={'converted_from_recipe': True, 'recipe_instructions': recipe.get_instruction_count()}
            )
