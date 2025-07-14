#!/usr/bin/env python3
"""
调试日志增强工具
为 maskstage 调用流程添加详细的调试日志
"""

import logging
import json
import functools
from typing import Any, Dict, Callable
from pathlib import Path

class MaskStageDebugLogger:
    """MaskStage 调试日志增强器"""
    
    def __init__(self, log_file: Path = None):
        self.log_file = log_file or Path("maskstage_debug.log")
        self.setup_logging()
    
    def setup_logging(self):
        """设置详细的调试日志"""
        # 创建专用的调试日志器
        self.logger = logging.getLogger("MaskStageDebug")
        self.logger.setLevel(logging.DEBUG)
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 文件处理器
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 详细格式
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        
        file_handler.setFormatter(detailed_formatter)
        console_handler.setFormatter(detailed_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_config_analysis(self, config: Dict[str, Any], source: str):
        """记录配置分析"""
        self.logger.info(f"=== {source} 配置分析 ===")
        self.logger.info(f"完整配置: {json.dumps(config, indent=2, ensure_ascii=False)}")
        
        # 重点分析 marker_config
        marker_config = config.get('marker_config', {})
        self.logger.info(f"Marker 配置: {json.dumps(marker_config, indent=2, ensure_ascii=False)}")
        
        # 分析配置结构
        if 'preserve' in marker_config:
            self.logger.warning(f"发现 'preserve' 键在 marker_config 中: {marker_config['preserve']}")
        if 'tls' in marker_config:
            self.logger.info(f"发现 'tls' 键在 marker_config 中: {marker_config['tls']}")
            tls_config = marker_config['tls']
            if 'preserve_application_data' in tls_config:
                self.logger.critical(f"TLS-23 关键配置 preserve_application_data: {tls_config['preserve_application_data']}")
    
    def log_stage_creation(self, stage_class, config: Dict[str, Any]):
        """记录 Stage 创建过程"""
        self.logger.info(f"=== Stage 创建过程 ===")
        self.logger.info(f"Stage 类: {stage_class.__name__}")
        self.logger.info(f"传入配置: {json.dumps(config, indent=2, ensure_ascii=False)}")
    
    def log_marker_creation(self, marker_class, marker_config: Dict[str, Any]):
        """记录 Marker 创建过程"""
        self.logger.info(f"=== Marker 创建过程 ===")
        self.logger.info(f"Marker 类: {marker_class.__name__}")
        self.logger.info(f"传入 Marker 的配置: {json.dumps(marker_config, indent=2, ensure_ascii=False)}")
    
    def log_marker_initialization(self, marker, preserve_config: Dict[str, Any]):
        """记录 Marker 初始化过程"""
        self.logger.info(f"=== Marker 初始化过程 ===")
        self.logger.info(f"Marker 实例: {type(marker).__name__}")
        self.logger.info(f"解析后的 preserve_config: {json.dumps(preserve_config, indent=2, ensure_ascii=False)}")
        
        # 重点检查 TLS-23 相关配置
        application_data_setting = preserve_config.get('application_data', 'NOT_FOUND')
        self.logger.critical(f"🎯 TLS-23 关键配置 application_data: {application_data_setting}")
        
        if application_data_setting == 'NOT_FOUND':
            self.logger.error("❌ 未找到 application_data 配置，将使用默认值 False")
        elif application_data_setting is False:
            self.logger.info("✅ application_data=False，将对 TLS-23 进行智能掩码（保留5字节头部）")
        elif application_data_setting is True:
            self.logger.warning("⚠️ application_data=True，将完全保留 TLS-23 消息体")
    
    def log_rule_generation(self, tls_type: int, preserve_decision: bool, rule_details: Dict[str, Any]):
        """记录规则生成过程"""
        if tls_type == 23:  # 只记录 TLS-23 相关的规则
            self.logger.info(f"=== TLS-23 规则生成 ===")
            self.logger.info(f"TLS 类型: {tls_type} (ApplicationData)")
            self.logger.critical(f"保留决策: {preserve_decision}")
            self.logger.info(f"规则详情: {json.dumps(rule_details, indent=2, ensure_ascii=False)}")
    
    def create_debug_wrapper(self, original_func: Callable, func_name: str) -> Callable:
        """创建调试包装器"""
        @functools.wraps(original_func)
        def wrapper(*args, **kwargs):
            self.logger.debug(f"=== 调用 {func_name} ===")
            self.logger.debug(f"参数: args={args}, kwargs={kwargs}")
            
            try:
                result = original_func(*args, **kwargs)
                self.logger.debug(f"{func_name} 执行成功")
                return result
            except Exception as e:
                self.logger.error(f"{func_name} 执行失败: {e}")
                raise
        
        return wrapper

def patch_tls_marker_for_debug(debug_logger: MaskStageDebugLogger):
    """为 TLSProtocolMarker 添加调试补丁"""
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        # 保存原始方法
        original_init = TLSProtocolMarker.__init__
        original_create_keep_rule = TLSProtocolMarker._create_keep_rule
        
        def debug_init(self, config):
            debug_logger.log_marker_creation(TLSProtocolMarker, config)
            result = original_init(self, config)
            debug_logger.log_marker_initialization(self, self.preserve_config)
            return result
        
        def debug_create_keep_rule(self, stream_id, direction, tls_type, tcp_seq, frame_number):
            rule_details = {
                "stream_id": stream_id,
                "direction": direction,
                "tls_type": tls_type,
                "tcp_seq": tcp_seq,
                "frame_number": frame_number
            }
            
            # 检查保留决策
            preserve_decision = self.preserve_config.get('application_data', False) if tls_type == 23 else True
            debug_logger.log_rule_generation(tls_type, preserve_decision, rule_details)
            
            return original_create_keep_rule(self, stream_id, direction, tls_type, tcp_seq, frame_number)
        
        # 应用补丁
        TLSProtocolMarker.__init__ = debug_init
        TLSProtocolMarker._create_keep_rule = debug_create_keep_rule
        
        debug_logger.logger.info("✅ TLSProtocolMarker 调试补丁已应用")
        
    except ImportError as e:
        debug_logger.logger.error(f"❌ 无法导入 TLSProtocolMarker: {e}")

def patch_stage_for_debug(debug_logger: MaskStageDebugLogger):
    """为 NewMaskPayloadStage 添加调试补丁"""
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 保存原始方法
        original_init = NewMaskPayloadStage.__init__
        original_create_marker = NewMaskPayloadStage._create_marker
        
        def debug_init(self, config):
            debug_logger.log_config_analysis(config, "NewMaskPayloadStage")
            debug_logger.log_stage_creation(NewMaskPayloadStage, config)
            return original_init(self, config)
        
        def debug_create_marker(self):
            debug_logger.logger.info(f"=== 创建 Marker，传递配置: {self.marker_config} ===")
            return original_create_marker(self)
        
        # 应用补丁
        NewMaskPayloadStage.__init__ = debug_init
        NewMaskPayloadStage._create_marker = debug_create_marker
        
        debug_logger.logger.info("✅ NewMaskPayloadStage 调试补丁已应用")
        
    except ImportError as e:
        debug_logger.logger.error(f"❌ 无法导入 NewMaskPayloadStage: {e}")

def enable_debug_logging(log_file: Path = None) -> MaskStageDebugLogger:
    """启用调试日志"""
    debug_logger = MaskStageDebugLogger(log_file)
    
    # 应用调试补丁
    patch_stage_for_debug(debug_logger)
    patch_tls_marker_for_debug(debug_logger)
    
    debug_logger.logger.info("🚀 MaskStage 调试日志已启用")
    return debug_logger

if __name__ == "__main__":
    # 示例用法
    debug_logger = enable_debug_logging(Path("test_debug.log"))
    print(f"调试日志已启用，日志文件: {debug_logger.log_file}")
