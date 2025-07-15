# PktMask Keep Rule Set 处理逻辑梳理

## 概述

本文档详细梳理了PktMask项目中maskstage和masker阶段对keep rule set的完整处理逻辑，包括规则生成、传递、预处理、应用和优先级处理等各个环节。

## 1. 整体架构流程

### 1.1 双模块架构
```
MaskPayloadStage (maskstage)
├── Marker模块 (TLSProtocolMarker)
│   └── 生成 KeepRuleSet
└── Masker模块 (PayloadMasker)
    └── 应用 KeepRuleSet
```

### 1.2 处理流程
```
输入PCAP → Marker分析 → KeepRuleSet → Masker应用 → 输出PCAP
```

## 2. Keep Rule Set 数据结构

### 2.1 KeepRule 核心结构
```python
@dataclass
class KeepRule:
    stream_id: str              # TCP流标识
    direction: str              # 流方向 (forward/reverse)
    seq_start: int              # 起始序列号 (包含，左闭)
    seq_end: int                # 结束序列号 (不包含，右开)
    rule_type: str              # 规则类型
    metadata: Dict[str, Any]    # 附加信息
```

**关键特性：**
- 使用绝对TCP序列号
- 采用左闭右开区间 `[seq_start, seq_end)`
- 支持保留策略元数据 (`preserve_strategy`)

### 2.2 KeepRuleSet 集合结构
```python
@dataclass
class KeepRuleSet:
    rules: List[KeepRule]                    # 规则列表
    tcp_flows: Dict[str, FlowInfo]           # TCP流信息
    statistics: Dict[str, Any]               # 统计信息
    metadata: Dict[str, Any]                 # 元数据
```

## 3. Marker阶段：规则生成逻辑

### 3.1 TLS Marker 处理流程
```
1. 扫描TLS消息 (_scan_tls_messages)
2. 分析TCP流 (_analyze_tcp_flows)
3. 生成保留规则 (_generate_keep_rules)
4. 设置元数据
```

### 3.2 规则生成策略

#### 3.2.1 TLS消息类型处理
```python
# TLS-20/21/22/24: 完全保留
preserve_strategy = "full_preserve"

# TLS-23 (ApplicationData): 仅保留头部
preserve_strategy = "header_only"
```

#### 3.2.2 规则创建逻辑
```python
def _create_keep_rule_from_tls_record(self, record):
    if record['content_type'] == 23:  # ApplicationData
        # 创建头部保留规则 (5字节)
        return KeepRule(
            seq_start=tcp_seq,
            seq_end=tcp_seq + 5,  # TLS记录头
            metadata={'preserve_strategy': 'header_only'}
        )
    else:  # 其他TLS类型
        # 创建完全保留规则
        return KeepRule(
            seq_start=tcp_seq,
            seq_end=tcp_seq + record_length,
            metadata={'preserve_strategy': 'full_preserve'}
        )
```

### 3.3 序列号计算
- 使用tshark的绝对TCP序列号 (`tcp.seq_raw`)
- 通过TCP载荷重组获得精确的序列号映射
- 支持跨TCP段的TLS消息处理

## 4. Masker阶段：规则应用逻辑

### 4.1 处理流程概览
```
1. 预处理保留规则 (_preprocess_keep_rules)
2. 逐包处理载荷
3. 应用保留规则 (_apply_keep_rules)
4. 修改数据包载荷
```

### 4.2 规则预处理 (_preprocess_keep_rules)

#### 4.2.1 按策略分组
```python
rule_lookup = {
    stream_id: {
        direction: {
            'header_only': [(seq_start, seq_end), ...],
            'full_preserve': [(seq_start, seq_end), ...]
        }
    }
}
```

#### 4.2.2 策略映射
```python
# 策略名称标准化
if preserve_strategy == 'full_message':
    preserve_strategy = 'full_preserve'
elif preserve_strategy not in ['header_only', 'full_preserve']:
    preserve_strategy = 'full_preserve'  # 默认策略
```

#### 4.2.3 规则优化
- **full_preserve规则**：可以合并重叠区间
- **header_only规则**：保持独立，不合并
- 构建二分查找优化结构（大量规则时）

### 4.3 规则应用 (_apply_keep_rules)

#### 4.3.1 优先级策略
```
1. header_only规则 (最高优先级)
   - 无条件应用
   - 不能被其他规则覆盖

2. full_preserve规则 (次优先级)
   - 不能覆盖已保留的header_only区域
   - 只保留未被占用的部分
```

#### 4.3.2 应用算法
```python
def _apply_keep_rules_simple(self, payload, seg_start, seg_end, rule_data):
    # 创建全零缓冲区
    buf = bytearray(len(payload))
    preserved_map = [False] * len(payload)
    
    # 第一阶段：应用header_only规则（最高优先级）
    for range_info in header_range_infos:
        buf[offset_left:offset_right] = payload[offset_left:offset_right]
        preserved_map[offset_left:offset_right] = True
    
    # 第二阶段：应用full_preserve规则（不覆盖已保留区域）
    for range_info in full_range_infos:
        for i in range(offset_left, offset_right):
            if not preserved_map[i]:  # 只保留未被占用的字节
                buf[i] = payload[i]
                preserved_map[i] = True
    
    return bytes(buf)
```

### 4.4 性能优化

#### 4.4.1 算法选择
```python
if rule_data['range_count'] > 10:
    # 大量规则：使用二分查找优化
    return self._apply_keep_rules_optimized(...)
else:
    # 少量规则：使用简单遍历
    return self._apply_keep_rules_simple(...)
```

#### 4.4.2 内存优化
- 批处理缓冲区 (chunk_size)
- 流式处理避免全量加载
- 性能监控和内存跟踪

## 5. 关键设计特性

### 5.1 优先级处理
- **TLS-23头部保留规则**具有最高优先级
- 避免跨包TLS消息规则覆盖精确的TLS-23头部规则
- 保证关键协议信息的精确保留

### 5.2 序列号处理
- 使用绝对TCP序列号，避免32位回绕问题
- 左闭右开区间 `[seq_start, seq_end)` 语义
- 支持多层封装剥离

### 5.3 错误处理
- 规则验证和合理性检查
- 跨段消息规则验证
- 降级处理和错误恢复

### 5.4 统计信息
```python
MaskingStats:
    - total_packets: 总包数
    - masked_packets: 修改包数
    - preserved_bytes: 保留字节数
    - masked_bytes: 掩码字节数
    - processing_time: 处理时间
```

## 6. 配置和扩展性

### 6.1 保留策略配置
```python
preserve_config = {
    'tls_20': 'full_preserve',      # ChangeCipherSpec
    'tls_21': 'full_preserve',      # Alert
    'tls_22': 'full_preserve',      # Handshake
    'tls_23': 'header_only',        # ApplicationData
    'tls_24': 'full_preserve',      # Heartbeat
    'non_tls': 'full_mask'          # 非TLS载荷
}
```

### 6.2 扩展点
- 支持新的协议标记器
- 可配置的保留策略
- 插件化的规则优化算法
- 自定义的掩码应用策略

## 7. 总结

当前的keep rule set处理逻辑具有以下特点：

**优势：**
- 精确的序列号计算和区间处理
- 清晰的优先级策略
- 高效的规则预处理和应用算法
- 良好的性能优化和错误处理

**关键机制：**
- 双模块架构分离关注点
- 基于保留策略的规则分类
- 优先级驱动的规则应用
- 左闭右开区间语义

这套机制确保了TLS协议的精确掩码处理，特别是对TLS-23 ApplicationData的头部保留和载荷掩码的精确控制。

## 8. 代码示例

### 8.1 规则生成示例
```python
# TLS Marker生成规则
def _create_keep_rule_from_tls_record(self, record):
    if record['content_type'] == 23:  # ApplicationData
        # 仅保留5字节TLS记录头
        rule = KeepRule(
            stream_id="192.168.1.1:443-192.168.1.2:12345",
            direction="forward",
            seq_start=1000,
            seq_end=1005,  # 5字节头部
            rule_type="tls_applicationdata_header",
            metadata={
                'preserve_strategy': 'header_only',
                'tls_content_type': 23,
                'frame_number': 150
            }
        )
    else:  # 其他TLS类型
        # 完全保留整个TLS记录
        rule = KeepRule(
            stream_id="192.168.1.1:443-192.168.1.2:12345",
            direction="forward",
            seq_start=1000,
            seq_end=1000 + record_length,
            rule_type="tls_handshake",
            metadata={
                'preserve_strategy': 'full_preserve',
                'tls_content_type': 22
            }
        )
    return rule
```

### 8.2 规则预处理示例
```python
# Masker预处理规则
def _preprocess_keep_rules(self, keep_rules):
    rule_lookup = defaultdict(lambda: defaultdict(
        lambda: {'header_only': [], 'full_preserve': []}
    ))

    for rule in keep_rules.rules:
        strategy = rule.metadata.get('preserve_strategy', 'full_preserve')

        # 策略标准化
        if strategy == 'full_message':
            strategy = 'full_preserve'

        # 按流、方向、策略分组
        rule_lookup[rule.stream_id][rule.direction][strategy].append(
            (rule.seq_start, rule.seq_end)
        )

    # 优化full_preserve规则（合并重叠区间）
    for stream_id, directions in rule_lookup.items():
        for direction, strategies in directions.items():
            if strategies['full_preserve']:
                strategies['full_preserve'] = self._merge_overlapping_ranges(
                    strategies['full_preserve']
                )

    return rule_lookup
```

### 8.3 规则应用示例
```python
# Masker应用规则到载荷
def _apply_keep_rules_simple(self, payload, seg_start, seg_end, rule_data):
    # 创建全零缓冲区
    buf = bytearray(len(payload))
    preserved_map = [False] * len(payload)

    # 获取重叠的规则区间
    header_ranges = self._find_overlapping_ranges(
        rule_data['header_only_ranges'], seg_start, seg_end
    )
    full_ranges = self._find_overlapping_ranges(
        rule_data['full_preserve_ranges'], seg_start, seg_end
    )

    # 第一阶段：应用header_only规则（最高优先级）
    for range_info in header_ranges:
        offset_left = range_info["offset_left"]
        offset_right = range_info["offset_right"]

        # 无条件保留头部数据
        buf[offset_left:offset_right] = payload[offset_left:offset_right]
        for i in range(offset_left, offset_right):
            preserved_map[i] = True

    # 第二阶段：应用full_preserve规则（不覆盖已保留区域）
    for range_info in full_ranges:
        offset_left = range_info["offset_left"]
        offset_right = range_info["offset_right"]

        # 只保留未被header_only规则占用的字节
        for i in range(offset_left, offset_right):
            if not preserved_map[i]:
                buf[i] = payload[i]
                preserved_map[i] = True

    return bytes(buf)
```

### 8.4 实际处理场景示例
```python
# 场景：TCP载荷包含TLS-23消息
# 原始载荷: [TLS头5字节][应用数据1000字节]
# 规则1: header_only, seq_start=1000, seq_end=1005
# 规则2: full_preserve, seq_start=1000, seq_end=1100 (跨包消息)

# 处理结果:
# - 字节0-4: 保留TLS头部 (header_only优先级)
# - 字节5-99: 保留部分应用数据 (full_preserve，未与header冲突)
# - 字节100-1004: 置零 (无规则覆盖)

payload_before = b'\x17\x03\x03\x03\xe8' + b'A' * 1000  # TLS-23头 + 数据
payload_after  = b'\x17\x03\x03\x03\xe8' + b'A' * 95 + b'\x00' * 905
```

## 9. 性能特性

### 9.1 时间复杂度
- **规则预处理**: O(n log n) - 排序和合并
- **规则查找**: O(log n) - 二分查找（大量规则时）
- **规则应用**: O(m) - m为重叠规则数量

### 9.2 空间复杂度
- **规则存储**: O(n) - n为规则数量
- **查找结构**: O(n) - 预处理后的优化结构
- **载荷处理**: O(p) - p为载荷大小

### 9.3 优化策略
- 规则合并减少重叠处理
- 二分查找加速规则匹配
- 批处理减少I/O开销
- 内存池避免频繁分配

## 10. 规则类型对比表

| 规则类型 | 保留策略 | 优先级 | 合并策略 | 应用场景 | 示例 |
|---------|---------|--------|----------|----------|------|
| `tls_applicationdata_header` | `header_only` | 最高 | 不合并 | TLS-23头部 | 5字节TLS记录头 |
| `tls_handshake` | `full_preserve` | 次高 | 可合并 | TLS-22握手 | 完整握手消息 |
| `tls_changecipherspec` | `full_preserve` | 次高 | 可合并 | TLS-20状态 | 完整状态消息 |
| `tls_alert` | `full_preserve` | 次高 | 可合并 | TLS-21警告 | 完整警告消息 |
| `tls_heartbeat` | `full_preserve` | 次高 | 可合并 | TLS-24心跳 | 完整心跳消息 |
| `non_tls_tcp` | `full_mask` | 最低 | N/A | 非TLS载荷 | 完全掩码 |

## 11. 关键设计决策

### 11.1 为什么使用左闭右开区间？
- **一致性**: 与编程语言切片语义一致
- **边界清晰**: 避免off-by-one错误
- **合并简单**: 相邻区间合并逻辑简洁

### 11.2 为什么TLS-23头部规则优先级最高？
- **协议完整性**: 保证TLS记录结构可解析
- **精确控制**: 避免被跨包消息规则意外覆盖
- **安全考虑**: 确保关键协议信息不被掩码

### 11.3 为什么分离header_only和full_preserve？
- **策略隔离**: 不同保留需求独立处理
- **优先级控制**: 精确的规则应用顺序
- **扩展性**: 便于添加新的保留策略

## 12. 故障排查指南

### 12.1 常见问题
1. **TLS-23载荷未被掩码**: 检查header_only规则是否正确生成
2. **规则重叠冲突**: 验证优先级处理逻辑
3. **序列号计算错误**: 确认使用绝对序列号
4. **跨包消息处理**: 检查TCP载荷重组逻辑

### 12.2 调试方法
- 启用详细日志记录规则生成和应用过程
- 使用统计信息验证处理结果
- 对比输入输出文件的字节级差异
- 分析规则覆盖范围和重叠情况
