"""
默认协议裁切策略

这个模块实现了默认的协议裁切策略，为所有不被特定策略支持的协议
提供通用的裁切方案。默认策略采用简单但有效的载荷处理逻辑。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

from typing import Dict, Any, List
import logging

from .base_strategy import BaseStrategy, ProtocolInfo, TrimContext, TrimResult
from ..models.mask_spec import MaskAfter, MaskRange, KeepAll


class DefaultStrategy(BaseStrategy):
    """
    默认协议裁切策略
    
    提供通用的载荷裁切功能，适用于所有未被特定策略支持的协议。
    采用配置驱动的简单裁切逻辑。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化默认策略
        
        Args:
            config: 策略配置字典
        """
        super().__init__(config)
        
        # 默认配置值
        self._default_config = {
            'default_preserve_bytes': 64,      # 默认保留字节数
            'min_preserve_bytes': 20,          # 最小保留字节数
            'max_preserve_bytes': 1024,        # 最大保留字节数
            'preserve_ratio': 0.1,             # 保留比例 (0.0-1.0)
            'trim_strategy': 'mask_after',     # 裁切策略: mask_after, mask_range, keep_all
            'enable_adaptive': True,           # 是否启用自适应裁切
            'confidence_threshold': 0.7        # 置信度阈值
        }
        
        # 合并用户配置和默认配置
        for key, default_value in self._default_config.items():
            if key not in self.config:
                self.config[key] = default_value
                
    @property
    def supported_protocols(self) -> List[str]:
        """返回支持的协议列表"""
        # 默认策略支持所有协议作为后备方案
        return ['*']  # 通配符表示支持所有协议
        
    @property
    def strategy_name(self) -> str:
        """返回策略名称"""
        return 'default'
        
    @property
    def priority(self) -> int:
        """返回策略优先级"""
        # 默认策略优先级最低，只在没有其他策略时使用
        return 0
        
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        """
        判断是否可以处理指定的协议和上下文
        
        默认策略可以处理任何协议，但优先级最低
        """
        return True
        
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo, 
                       context: TrimContext) -> Dict[str, Any]:
        """
        分析载荷结构
        
        默认策略进行基础的载荷分析，识别常见的结构模式
        """
        payload_size = len(payload)
        
        analysis = {
            'payload_size': payload_size,
            'has_header': False,
            'header_size': 0,
            'has_structured_data': False,
            'null_bytes_count': payload.count(b'\x00'),
            'printable_ratio': 0.0,
            'entropy': 0.0,
            'patterns': []
        }
        
        # 分析可打印字符比例
        if payload_size > 0:
            printable_count = sum(1 for b in payload if 32 <= b <= 126)
            analysis['printable_ratio'] = printable_count / payload_size
            
        # 简单的熵计算
        if payload_size > 0:
            byte_counts = [payload.count(bytes([i])) for i in range(256)]
            total = sum(byte_counts)
            if total > 0:
                import math
                entropy = -sum((count/total) * math.log2(count/total) 
                             for count in byte_counts if count > 0)
                analysis['entropy'] = entropy / 8.0  # 归一化到0-1
                
        # 检测可能的头部结构
        if payload_size >= 4:
            # 检查前几个字节是否像长度字段
            header_candidates = [
                payload[:2],  # 2字节头
                payload[:4],  # 4字节头
                payload[:8]   # 8字节头
            ]
            
            for i, candidate in enumerate(header_candidates):
                if self._looks_like_length_field(candidate, payload_size):
                    analysis['has_header'] = True
                    analysis['header_size'] = len(candidate)
                    break
                    
        # 检测结构化数据
        analysis['has_structured_data'] = (
            analysis['printable_ratio'] > 0.5 or  # 大量可打印字符
            analysis['null_bytes_count'] > payload_size * 0.1 or  # 较多空字节
            analysis['entropy'] < 0.3  # 低熵值表示有模式
        )
        
        self.logger.debug(f"载荷分析完成: 大小={payload_size}, "
                         f"可打印比例={analysis['printable_ratio']:.2f}, "
                         f"熵值={analysis['entropy']:.2f}")
        
        return analysis
        
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        """
        生成掩码规范
        
        根据配置和载荷分析结果生成合适的掩码规范
        """
        payload_size = analysis['payload_size']
        
        # 确定保留字节数
        preserve_bytes = self._calculate_preserve_bytes(payload_size, analysis)
        
        # 生成掩码规范
        mask_spec = self._create_mask_spec(preserve_bytes, payload_size)
        
        # 计算置信度
        confidence = self._calculate_confidence(analysis, preserve_bytes, payload_size)
        
        # 生成结果
        trimmed_bytes = max(0, payload_size - preserve_bytes)
        
        result = TrimResult(
            success=True,
            mask_spec=mask_spec,
            preserved_bytes=preserve_bytes,
            trimmed_bytes=trimmed_bytes,
            confidence=confidence,
            reason=f"默认策略应用: 保留 {preserve_bytes} 字节",
            warnings=self._generate_warnings(analysis, preserve_bytes, payload_size),
            metadata={
                'strategy': 'default',
                'analysis': analysis,
                'preserve_ratio': preserve_bytes / payload_size if payload_size > 0 else 0
            }
        )
        
        return result
        
    def _calculate_preserve_bytes(self, payload_size: int, analysis: Dict[str, Any]) -> int:
        """计算应该保留的字节数"""
        
        # 获取配置值
        default_preserve = self.get_config_value('default_preserve_bytes', 64)
        min_preserve = self.get_config_value('min_preserve_bytes', 20)
        max_preserve = self.get_config_value('max_preserve_bytes', 1024)
        preserve_ratio = self.get_config_value('preserve_ratio', 0.1)
        enable_adaptive = self.get_config_value('enable_adaptive', True)
        
        if not enable_adaptive:
            # 非自适应模式：使用固定值
            preserve_bytes = min(default_preserve, payload_size)
        else:
            # 自适应模式：根据载荷特征调整
            if analysis.get('has_header', False):
                # 有头部结构：保留头部 + 一些载荷
                header_size = analysis.get('header_size', 0)
                preserve_bytes = header_size + min(default_preserve, payload_size - header_size)
            elif analysis.get('has_structured_data', False):
                # 结构化数据：保留更多内容
                preserve_bytes = min(int(payload_size * preserve_ratio * 2), payload_size)
            else:
                # 普通载荷：使用比例保留
                preserve_bytes = min(int(payload_size * preserve_ratio), default_preserve)
                
        # 应用限制
        preserve_bytes = max(min_preserve, min(preserve_bytes, max_preserve, payload_size))
        
        return preserve_bytes
        
    def _create_mask_spec(self, preserve_bytes: int, payload_size: int):
        """创建掩码规范"""
        trim_strategy = self.get_config_value('trim_strategy', 'mask_after')
        
        if trim_strategy == 'keep_all' or preserve_bytes >= payload_size:
            return KeepAll()
        elif trim_strategy == 'mask_range':
            # 保留前部分，掩码后部分
            if preserve_bytes < payload_size:
                # MaskRange需要一个区间列表：[(start, end)]
                mask_ranges = [(preserve_bytes, payload_size)]
                return MaskRange(mask_ranges)
            else:
                return KeepAll()
        else:  # mask_after
            return MaskAfter(preserve_bytes)
            
    def _calculate_confidence(self, analysis: Dict[str, Any], 
                            preserve_bytes: int, payload_size: int) -> float:
        """计算裁切置信度"""
        base_confidence = 0.6  # 默认策略基础置信度
        
        # 根据载荷特征调整置信度
        if analysis.get('has_header', False):
            base_confidence += 0.1  # 有头部结构，置信度稍高
            
        if analysis.get('has_structured_data', False):
            base_confidence += 0.1  # 结构化数据，置信度稍高
            
        # 根据保留比例调整
        preserve_ratio = preserve_bytes / payload_size if payload_size > 0 else 0
        if 0.05 <= preserve_ratio <= 0.3:
            base_confidence += 0.1  # 合理的保留比例
        elif preserve_ratio > 0.5:
            base_confidence -= 0.2  # 保留过多，降低置信度
            
        return min(1.0, max(0.0, base_confidence))
        
    def _generate_warnings(self, analysis: Dict[str, Any], 
                          preserve_bytes: int, payload_size: int) -> List[str]:
        """生成警告信息"""
        warnings = []
        
        # 检查保留比例
        preserve_ratio = preserve_bytes / payload_size if payload_size > 0 else 0
        if preserve_ratio > 0.5:
            warnings.append(f"保留比例较高 ({preserve_ratio:.1%})，可能保留了过多数据")
            
        if preserve_ratio < 0.05:
            warnings.append(f"保留比例较低 ({preserve_ratio:.1%})，可能丢失重要信息")
            
        # 检查载荷特征
        if analysis.get('entropy', 0) > 0.8:
            warnings.append("载荷熵值较高，可能包含加密或压缩数据")
            
        if analysis.get('printable_ratio', 0) > 0.8:
            warnings.append("载荷包含大量可打印字符，可能是文本协议")
            
        return warnings
        
    def _looks_like_length_field(self, data: bytes, total_size: int) -> bool:
        """判断数据是否像长度字段"""
        if len(data) < 2:
            return False
            
        # 尝试解析为不同字节序的整数
        try:
            # 大端序
            value_be = int.from_bytes(data, 'big')
            # 小端序
            value_le = int.from_bytes(data, 'little')
            
            # 检查是否在合理范围内
            reasonable_range = total_size * 2  # 允许一些误差
            
            return (0 < value_be <= reasonable_range or 
                   0 < value_le <= reasonable_range)
        except Exception:
            return False
            
    def _validate_config(self) -> None:
        """验证配置参数"""
        super()._validate_config()
        
        # 验证数值范围
        preserve_bytes = self.get_config_value('default_preserve_bytes', 64)
        if not isinstance(preserve_bytes, int) or preserve_bytes < 0:
            raise ValueError("default_preserve_bytes 必须是非负整数")
            
        preserve_ratio = self.get_config_value('preserve_ratio', 0.1)
        if not isinstance(preserve_ratio, (int, float)) or not 0 <= preserve_ratio <= 1:
            raise ValueError("preserve_ratio 必须在 0.0-1.0 范围内")
            
        trim_strategy = self.get_config_value('trim_strategy', 'mask_after')
        valid_strategies = ['mask_after', 'mask_range', 'keep_all']
        if trim_strategy not in valid_strategies:
            raise ValueError(f"trim_strategy 必须是: {valid_strategies}") 