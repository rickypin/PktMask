"""
独立PCAP掩码处理器配置管理

提供配置参数的定义、验证和管理功能。
"""

from typing import Dict, Any, Optional, List
import logging
from pathlib import Path

from ..exceptions import ConfigurationError


# 默认配置参数
DEFAULT_CONFIG = {
    # 掩码处理参数
    'mask_byte_value': 0x00,                    # 掩码字节值
    'preserve_timestamps': True,                # 保持原始时间戳
    'recalculate_checksums': True,              # 重新计算校验和
    
    # 文件格式参数
    'supported_formats': ['.pcap', '.pcapng'],  # 支持的文件格式
    'strict_consistency_mode': True,            # 严格一致性模式
    'backup_original': False,                   # 是否备份原文件
    
    # 性能参数
    'batch_size': 1000,                         # 批处理大小
    'memory_limit_mb': 512,                     # 内存限制（MB）
    'enable_streaming': True,                   # 启用流式处理
    'max_concurrent_streams': 100,              # 最大并发流数量
    
    # 验证参数
    'verify_tcp_sequences': True,               # 验证TCP序列号连续性
    'strict_stream_matching': True,             # 严格的流ID匹配
    'enable_consistency_check': True,           # 启用一致性检查
    'max_sequence_gap': 65536,                  # 最大序列号间隙
    
    # 协议处理参数
    'disable_protocol_parsing': True,           # 禁用协议解析（关键参数）
    'force_raw_payload': True,                  # 强制Raw载荷模式
    'backup_protocol_bindings': True,           # 备份协议绑定状态
    'verify_raw_layer_rate': 0.95,             # Raw层存在率验证阈值
    
    # 日志参数
    'log_level': 'INFO',                        # 日志级别
    'enable_debug_output': False,               # 启用调试输出
    'log_packet_details': False,                # 记录数据包详细信息
    'performance_logging': True,                # 性能日志记录
    
    # 错误处理参数
    'continue_on_error': False,                 # 遇到错误时继续处理
    'max_errors_before_stop': 10,               # 停止前的最大错误数
    'error_packet_handling': 'skip',            # 错误包处理方式: skip, stop, save
    
    # 输出参数
    'output_format': 'auto',                    # 输出格式: auto, pcap, pcapng
    'compress_output': False,                   # 压缩输出文件
    'include_statistics': True,                 # 包含统计信息
}

# 配置参数验证规则
CONFIG_VALIDATION_RULES = {
    'mask_byte_value': {
        'type': int,
        'min': 0,
        'max': 255,
        'description': '掩码字节值必须在0-255范围内'
    },
    'batch_size': {
        'type': int,
        'min': 1,
        'max': 10000,
        'description': '批处理大小必须在1-10000范围内'
    },
    'memory_limit_mb': {
        'type': int,
        'min': 64,
        'max': 8192,
        'description': '内存限制必须在64MB-8GB范围内'
    },
    'max_concurrent_streams': {
        'type': int,
        'min': 1,
        'max': 1000,
        'description': '最大并发流数量必须在1-1000范围内'
    },
    'verify_raw_layer_rate': {
        'type': float,
        'min': 0.0,
        'max': 1.0,
        'description': 'Raw层存在率阈值必须在0.0-1.0范围内'
    },
    'log_level': {
        'type': str,
        'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        'description': '日志级别必须是有效的logging级别'
    },
    'error_packet_handling': {
        'type': str,
        'choices': ['skip', 'stop', 'save'],
        'description': '错误包处理方式必须是skip、stop或save'
    },
    'output_format': {
        'type': str,
        'choices': ['auto', 'pcap', 'pcapng'],
        'description': '输出格式必须是auto、pcap或pcapng'
    }
}


class ConfigManager:
    """配置管理器
    
    负责配置参数的加载、验证、合并和访问。
    """
    
    def __init__(self, user_config: Optional[Dict[str, Any]] = None):
        """初始化配置管理器
        
        Args:
            user_config: 用户提供的配置参数
        """
        self.logger = logging.getLogger(__name__)
        self._config = self._merge_config(user_config or {})
        self._setup_logging()
    
    def _merge_config(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """合并用户配置和默认配置
        
        Args:
            user_config: 用户配置参数
            
        Returns:
            合并后的完整配置
        """
        # 复制默认配置
        merged_config = DEFAULT_CONFIG.copy()
        
        # 验证并合并用户配置
        for key, value in user_config.items():
            if key in DEFAULT_CONFIG:
                # 验证参数值
                self._validate_config_value(key, value)
                merged_config[key] = value
            else:
                self.logger.warning(f"未知配置参数: {key}")
        
        return merged_config
    
    def _validate_config_value(self, key: str, value: Any) -> None:
        """验证配置参数值
        
        Args:
            key: 配置参数名
            value: 配置参数值
            
        Raises:
            ConfigurationError: 参数值无效时
        """
        if key not in CONFIG_VALIDATION_RULES:
            return  # 没有验证规则，跳过
        
        rule = CONFIG_VALIDATION_RULES[key]
        
        # 类型检查
        if 'type' in rule and not isinstance(value, rule['type']):
            raise ConfigurationError(
                f"配置参数 {key} 类型错误: 期望 {rule['type'].__name__}, 实际 {type(value).__name__}"
            )
        
        # 数值范围检查
        if 'min' in rule and value < rule['min']:
            raise ConfigurationError(
                f"配置参数 {key} 值过小: {value} < {rule['min']} - {rule['description']}"
            )
        
        if 'max' in rule and value > rule['max']:
            raise ConfigurationError(
                f"配置参数 {key} 值过大: {value} > {rule['max']} - {rule['description']}"
            )
        
        # 选择项检查
        if 'choices' in rule and value not in rule['choices']:
            raise ConfigurationError(
                f"配置参数 {key} 值无效: {value} 不在允许值 {rule['choices']} 中 - {rule['description']}"
            )
    
    def _setup_logging(self) -> None:
        """根据配置设置日志"""
        log_level = getattr(logging, self._config['log_level'].upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置参数值
        
        Args:
            key: 配置参数名
            default: 默认值
            
        Returns:
            配置参数值
        """
        return self._config.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置参数"""
        return self._config.copy()
    
    def update(self, updates: Dict[str, Any]) -> None:
        """更新配置参数
        
        Args:
            updates: 要更新的配置参数
        """
        for key, value in updates.items():
            if key in DEFAULT_CONFIG:
                self._validate_config_value(key, value)
                self._config[key] = value
                self.logger.debug(f"更新配置参数: {key} = {value}")
            else:
                self.logger.warning(f"忽略未知配置参数: {key}")
    
    def validate_file_format(self, file_path: str) -> bool:
        """验证文件格式是否支持
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持该文件格式
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        supported_formats = self._config['supported_formats']
        
        return suffix in supported_formats
    
    def get_memory_limit_bytes(self) -> int:
        """获取内存限制（字节）"""
        return self._config['memory_limit_mb'] * 1024 * 1024
    
    def is_strict_mode(self) -> bool:
        """是否启用严格模式"""
        return self._config['strict_consistency_mode']
    
    def should_preserve_timestamps(self) -> bool:
        """是否保持时间戳"""
        return self._config['preserve_timestamps']
    
    def should_recalculate_checksums(self) -> bool:
        """是否重新计算校验和"""
        return self._config['recalculate_checksums']
    
    def get_batch_size(self) -> int:
        """获取批处理大小"""
        return self._config['batch_size']
    
    def get_mask_byte_value(self) -> int:
        """获取掩码字节值"""
        return self._config['mask_byte_value']
    
    def should_disable_protocol_parsing(self) -> bool:
        """是否禁用协议解析"""
        return self._config['disable_protocol_parsing']
    
    def get_raw_layer_threshold(self) -> float:
        """获取Raw层存在率阈值"""
        return self._config['verify_raw_layer_rate']
    
    def should_continue_on_error(self) -> bool:
        """遇到错误时是否继续处理"""
        return self._config['continue_on_error']
    
    def get_max_errors(self) -> int:
        """获取停止前的最大错误数"""
        return self._config['max_errors_before_stop']
    
    def export_summary(self) -> Dict[str, Any]:
        """导出配置摘要
        
        Returns:
            配置摘要字典
        """
        return {
            'mask_settings': {
                'mask_byte_value': self._config['mask_byte_value'],
                'preserve_timestamps': self._config['preserve_timestamps'],
                'recalculate_checksums': self._config['recalculate_checksums']
            },
            'performance_settings': {
                'batch_size': self._config['batch_size'],
                'memory_limit_mb': self._config['memory_limit_mb'],
                'enable_streaming': self._config['enable_streaming']
            },
            'protocol_settings': {
                'disable_protocol_parsing': self._config['disable_protocol_parsing'],
                'force_raw_payload': self._config['force_raw_payload'],
                'verify_raw_layer_rate': self._config['verify_raw_layer_rate']
            },
            'validation_settings': {
                'strict_consistency_mode': self._config['strict_consistency_mode'],
                'verify_tcp_sequences': self._config['verify_tcp_sequences'],
                'enable_consistency_check': self._config['enable_consistency_check']
            }
        }


def create_config_manager(user_config: Optional[Dict[str, Any]] = None) -> ConfigManager:
    """创建配置管理器的便捷函数
    
    Args:
        user_config: 用户配置参数
        
    Returns:
        配置管理器实例
    """
    return ConfigManager(user_config)


def get_default_config() -> Dict[str, Any]:
    """获取默认配置的副本
    
    Returns:
        默认配置字典
    """
    return DEFAULT_CONFIG.copy()


def validate_config(config: Dict[str, Any]) -> List[str]:
    """验证配置参数
    
    Args:
        config: 要验证的配置
        
    Returns:
        验证错误列表，空列表表示无错误
    """
    errors = []
    
    for key, value in config.items():
        if key not in DEFAULT_CONFIG:
            errors.append(f"未知配置参数: {key}")
            continue
        
        try:
            # 使用临时配置管理器验证参数
            temp_manager = ConfigManager()
            temp_manager._validate_config_value(key, value)
        except ConfigurationError as e:
            errors.append(str(e))
    
    return errors 