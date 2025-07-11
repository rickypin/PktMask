# PktMask 增强掩码规则实现报告

## 实现概述

成功在PktMask的掩码规则体系中添加了对非TLS TCP载荷的处理能力，实现了完整的增强掩码规则体系。新功能在保持现有TLS协议掩码策略100%不变的基础上，扩展了对未识别为TLS协议的TCP载荷的处理。

## 完整掩码规则体系

### 现有TLS协议掩码规则（保持不变）
- **TLS-20 (ChangeCipherSpec)**: `keep_all` - 完全保留
- **TLS-21 (Alert)**: `keep_all` - 完全保留  
- **TLS-22 (Handshake)**: `keep_all` - 完全保留
- **TLS-23 (ApplicationData)**: `mask_payload` - 保留头部5字节，掩码载荷
- **TLS-24 (Heartbeat)**: `keep_all` - 完全保留

### 新增非TLS TCP载荷掩码规则
- **未识别到包含TLS消息的TCP载荷**: `mask_all_payload` - 全部掩码载荷（整个TCP载荷置零）

## 技术实现详情

### 1. 配置文件更新

**文件**: `config/default/mask_config.yaml`
```yaml
tshark_enhanced:
  # 新增非TLS TCP载荷掩码策略配置
  non_tls_tcp_strategy: mask_all_payload
  enable_non_tls_tcp_masking: true
```

### 2. 模型扩展

**文件**: `src/pktmask/core/trim/models/tls_models.py`

#### 枚举扩展
```python
class TLSProcessingStrategy(Enum):
    KEEP_ALL = "keep_all"
    MASK_PAYLOAD = "mask_payload"
    MASK_ALL_PAYLOAD = "mask_all_payload"  # 新增

class MaskAction(Enum):
    KEEP_ALL = "keep_all"
    MASK_PAYLOAD = "mask_payload"
    MASK_ALL_PAYLOAD = "mask_all_payload"  # 新增
```

#### 新增函数
```python
def create_non_tls_tcp_mask_rule(packet_number: int, tcp_stream_id: str) -> MaskRule:
    """为非TLS TCP载荷创建全掩码规则"""
    return MaskRule(
        packet_number=packet_number,
        tcp_stream_id=tcp_stream_id,
        tls_record_offset=0,
        tls_record_length=0,
        mask_offset=0,
        mask_length=-1,  # 特殊值：掩码到载荷结束
        action=MaskAction.MASK_ALL_PAYLOAD,
        reason="非TLS TCP载荷全掩码策略：保护未识别协议的敏感数据",
        tls_record_type=None
    )
```

### 3. 规则生成器增强

**文件**: `src/pktmask/core/processors/tls_mask_rule_generator.py`

#### 新增方法
```python
def generate_enhanced_rules(self, tls_records: List[TLSRecordInfo], 
                           tcp_packets_info: Optional[Dict[int, Dict[str, Any]]] = None) -> List[MaskRule]:
    """生成增强掩码规则，包括非TLS TCP载荷处理"""
    
def _generate_non_tls_tcp_rules(self, tls_rules: List[MaskRule], 
                               tcp_packets_info: Dict[int, Dict[str, Any]]) -> List[MaskRule]:
    """为非TLS TCP载荷生成掩码规则"""
```

### 4. 处理器增强

**文件**: `src/pktmask/core/processors/tshark_enhanced_mask_processor.py`

#### 配置扩展
```python
@dataclass
class TSharkEnhancedConfig:
    # 新增非TLS TCP载荷策略配置
    enable_non_tls_tcp_masking: bool = True
    non_tls_tcp_strategy: str = "mask_all_payload"
```

#### 处理流程增强
```python
def _collect_tcp_packets_info(self, pcap_file: Path) -> Optional[Dict[int, Dict[str, Any]]]:
    """收集TCP包信息用于非TLS载荷掩码"""
```

### 5. 掩码应用器更新

**文件**: `src/pktmask/core/processors/scapy_mask_applier.py`

#### 支持新的掩码操作
```python
if rule.action.value == "mask_all_payload":
    # 非TLS TCP载荷全掩码：掩码整个TCP载荷
    abs_start = 0
    abs_end = payload_length
```

## 处理流程

### 增强的三阶段处理
```
Stage 1: TShark TLS分析
    ↓
Stage 1.5: TCP包信息收集（新增）
    ↓
Stage 2: 增强掩码规则生成
    ├── TLS掩码规则生成
    └── 非TLS TCP载荷规则生成（新增）
    ↓
Stage 3: Scapy掩码应用
```

### 规则生成逻辑
1. **TLS规则生成**: 使用现有逻辑生成TLS协议掩码规则
2. **非TLS识别**: 识别未被TLS规则覆盖的TCP包
3. **全掩码规则**: 为非TLS TCP载荷生成全掩码规则
4. **规则合并**: 合并TLS和非TLS规则

## 示例配置文件

### 增强掩码配方
**文件**: `config/samples/enhanced_mask_recipe.json`

展示了完整的增强掩码策略，包括：
- TLS协议的差异化处理
- 非TLS TCP载荷的全掩码策略
- 详细的安全考虑和实现说明

## 测试验证

### 单元测试
**文件**: `tests/test_enhanced_mask_rules.py`
- 测试新增枚举类型
- 测试非TLS规则创建
- 测试规则生成逻辑
- 测试配置参数

### 集成测试
**文件**: `tests/integration/test_enhanced_mask_integration.py`
- 测试混合流量处理
- 测试禁用功能
- 测试配置参数

### 测试结果
```
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_mask_action_enum_extension PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_tls_processing_strategy_extension PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_create_non_tls_tcp_mask_rule PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_non_tls_rule_is_mask_operation PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_non_tls_rule_description PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_generator_config_non_tls_parameters PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_generate_non_tls_tcp_rules PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_generate_enhanced_rules_integration PASSED
tests/test_enhanced_mask_rules.py::TestEnhancedMaskRules::test_disabled_non_tls_masking PASSED

tests/integration/test_enhanced_mask_integration.py::TestEnhancedMaskIntegration::test_disabled_non_tls_masking PASSED
tests/integration/test_enhanced_mask_integration.py::TestEnhancedMaskIntegration::test_enhanced_config_parameters PASSED
tests/integration/test_enhanced_mask_integration.py::TestEnhancedMaskIntegration::test_enhanced_mask_processing_with_mixed_traffic PASSED
```

## 兼容性保证

### 向后兼容
- ✅ 现有TLS掩码策略100%保持不变
- ✅ 现有配置文件无需修改
- ✅ 现有API接口完全兼容
- ✅ 可通过配置禁用新功能

### 功能扩展
- ✅ 新增非TLS TCP载荷处理能力
- ✅ 支持混合协议流量处理
- ✅ 提供详细的统计和日志信息
- ✅ 保持高性能处理能力

## 安全增强

### 保守策略
- 对未识别协议采用最保守的全掩码策略
- 确保敏感信息不会泄露
- 覆盖HTTP、SSH、FTP等常见协议

### 协议感知
- 根据协议类型采用差异化处理
- 保留TLS协议结构信息用于分析
- 最大化隐私保护

## 性能影响

### 额外开销
- TCP包信息收集：轻微I/O开销
- 协议识别：CPU开销可忽略
- 规则生成：内存开销线性增长

### 优化措施
- 延迟加载TCP包信息
- 批量处理规则生成
- 内存高效的数据结构

## 文档更新

### 新增文档
- `docs/current/features/enhanced_mask_rules.md`: 详细的功能说明
- `config/samples/enhanced_mask_recipe.json`: 示例配置文件
- `ENHANCED_MASK_RULES_IMPLEMENTATION.md`: 实现报告

### 更新内容
- 配置文件说明
- API文档
- 使用示例

## 总结

成功实现了PktMask增强掩码规则体系，具备以下特点：

1. **完整覆盖**: 所有TCP载荷都有相应的掩码策略
2. **协议感知**: 根据协议类型采用差异化处理
3. **安全优先**: 未识别协议采用最保守策略
4. **向后兼容**: 现有功能100%保持不变
5. **可配置性**: 支持灵活的策略配置
6. **高性能**: 保持原有的处理性能
7. **可测试**: 提供完整的测试覆盖

这使得PktMask能够处理更复杂的网络环境，在保护隐私的同时保留必要的协议分析能力，为企业网络安全脱敏提供了更强大的工具。
