# 增强掩码规则 - 非TLS TCP载荷处理

## 概述

PktMask 2.0 引入了增强掩码规则体系，在原有TLS协议掩码策略基础上，新增了对非TLS TCP载荷的处理能力。这确保了所有TCP载荷都能得到适当的掩码处理，对于无法识别为TLS协议的TCP载荷采用最保守的全掩码策略。

## 完整掩码规则体系

### TLS协议掩码规则（现有）

| TLS类型 | 协议名称 | 处理策略 | 说明 |
|---------|----------|----------|------|
| TLS-20 | ChangeCipherSpec | `keep_all` | 完全保留协议状态变更信息 |
| TLS-21 | Alert | `keep_all` | 完全保留错误和警告信息 |
| TLS-22 | Handshake | `keep_all` | 完全保留握手过程信息 |
| TLS-23 | ApplicationData | `mask_payload` | 保留头部5字节，掩码载荷 |
| TLS-24 | Heartbeat | `keep_all` | 完全保留心跳消息 |

### 非TLS TCP载荷掩码规则（新增）

| 载荷类型 | 处理策略 | 说明 |
|----------|----------|------|
| 未识别到包含TLS消息的TCP载荷 | `mask_all_payload` | 全部掩码载荷（整个TCP载荷置零） |

## 技术实现

### 1. 配置参数

在 `config/default/mask_config.yaml` 中新增配置项：

```yaml
tshark_enhanced:
  # 非TLS TCP载荷掩码策略配置
  non_tls_tcp_strategy: mask_all_payload
  enable_non_tls_tcp_masking: true
```

### 2. 掩码操作类型扩展

```python
class MaskAction(Enum):
    """掩码操作类型"""
    KEEP_ALL = "keep_all"
    MASK_PAYLOAD = "mask_payload"
    MASK_ALL_PAYLOAD = "mask_all_payload"  # 新增：全载荷掩码
```

### 3. 处理策略扩展

```python
class TLSProcessingStrategy(Enum):
    """TLS处理策略枚举"""
    KEEP_ALL = "keep_all"
    MASK_PAYLOAD = "mask_payload"
    MASK_ALL_PAYLOAD = "mask_all_payload"  # 新增：全载荷掩码
```

### 4. 增强规则生成

新增 `generate_enhanced_rules` 方法，支持：
- TLS记录掩码规则生成
- TCP包信息收集
- 非TLS TCP载荷识别
- 全掩码规则生成

## 处理流程

### 1. 三阶段增强处理

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

### 2. 规则生成逻辑

```python
def generate_enhanced_rules(tls_records, tcp_packets_info):
    # 1. 生成TLS掩码规则
    tls_rules = generate_rules(tls_records)
    
    # 2. 识别未被TLS规则覆盖的TCP包
    tls_covered_packets = {rule.packet_number for rule in tls_rules}
    
    # 3. 为非TLS TCP载荷生成全掩码规则
    non_tls_rules = []
    for packet_number, packet_info in tcp_packets_info.items():
        if packet_number not in tls_covered_packets and packet_info['has_payload']:
            rule = create_non_tls_tcp_mask_rule(packet_number, packet_info['tcp_stream_id'])
            non_tls_rules.append(rule)
    
    return tls_rules + non_tls_rules
```

## 安全考虑

### 1. 保守策略

对于无法识别为TLS协议的TCP载荷，采用最保守的全掩码策略：
- 整个TCP载荷置零
- 不保留任何载荷内容
- 确保敏感信息不会泄露

### 2. 协议覆盖

新规则覆盖的协议类型：
- HTTP明文传输
- SSH加密协议
- FTP文件传输
- SMTP邮件传输
- 其他未识别的TCP协议

### 3. 隐私保护

- **最大化隐私保护**：未识别协议全部掩码
- **保留协议可分析性**：TLS协议保留结构信息
- **差异化处理**：根据协议类型采用不同策略

## 使用示例

### 1. 基本配置

```python
from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor

# 创建处理器（启用非TLS TCP载荷掩码）
processor = TSharkEnhancedMaskProcessor({
    'enable_non_tls_tcp_masking': True,
    'non_tls_tcp_strategy': 'mask_all_payload'
})

# 处理文件
result = processor.process_file('input.pcap', 'output.pcap')
```

### 2. 配置文件示例

参见 `config/samples/enhanced_mask_recipe.json`，展示了完整的增强掩码策略。

## 性能影响

### 1. 额外开销

- TCP包信息收集：轻微I/O开销
- 协议识别：CPU开销可忽略
- 规则生成：内存开销线性增长

### 2. 优化措施

- 延迟加载TCP包信息
- 批量处理规则生成
- 内存高效的数据结构

## 兼容性

### 1. 向后兼容

- 现有TLS掩码策略100%保持不变
- 现有配置文件无需修改
- 现有API接口完全兼容

### 2. 可选功能

- 可通过配置禁用非TLS TCP载荷掩码
- 禁用时行为与原版本完全一致
- 渐进式启用新功能

## 监控和调试

### 1. 日志输出

```
🚀 [Enhanced Masking] Collecting TCP packet information for non-TLS masking
TCP info collection completed: Found 150 TCP packets, took 0.05 seconds
🚀 [Enhanced Masking] Starting Stage 2: Enhanced Mask Rule Generation
🚀 [Enhanced Masking Statistics] Mask rule generation results:
🚀   Total mask rules: 45
🚀   TLS-23 rules: 12
🚀   TLS mask payload rules: 12
🚀   Non-TLS mask all payload rules: 25
🚀   Non-TLS TCP rules: 25
```

### 2. 统计信息

处理结果包含详细统计：
- TLS规则数量
- 非TLS规则数量
- 处理包数量
- 性能指标

## 总结

增强掩码规则体系通过添加非TLS TCP载荷处理能力，实现了：

1. **完整覆盖**：所有TCP载荷都有相应的掩码策略
2. **协议感知**：根据协议类型采用差异化处理
3. **安全优先**：未识别协议采用最保守策略
4. **向后兼容**：现有功能100%保持不变
5. **可配置性**：支持灵活的策略配置

这使得PktMask能够处理更复杂的网络环境，在保护隐私的同时保留必要的协议分析能力。
