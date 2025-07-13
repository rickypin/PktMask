# PktMask 双模块架构流标识一致性验证报告

## 执行摘要

通过深入检查和验证 PayloadMasker 和 Marker 模块中的流标识构建逻辑，发现了一个**关键的流键格式不一致问题**，这是导致规则匹配失败的根本原因。

## 验证范围

- **测试文件**: `tests/samples/tls-single/tls_sample.pcap`
- **验证模块**: PayloadMasker._process_packet 和 TLSProtocolMarker
- **验证内容**: 流标识构建、流方向识别、流键格式、序列号处理

## 验证结果

### ✅ 流标识 (stream_id) 构建 - 一致

**Masker模块**:
- 使用自增数字ID算法
- 为每个唯一TCP流分配递增的数字标识 (0, 1, 2...)
- 基于五元组标准化: `f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"`

**Marker模块**:
- 使用tshark的tcp.stream字段
- 直接获取tshark分析的流标识

**验证结果**: 对于测试文件，两者生成相同的stream_id = "0"

### ✅ 流方向识别 - 一致

**Masker模块**:
```python
def _determine_flow_direction(self, ip_layer, tcp_layer, stream_id: str) -> str:
    # 第一个包定义为forward方向
    # 后续包根据源端点匹配判断方向
```

**Marker模块**:
```python
def _determine_packet_direction(self, packet, flow_info) -> str:
    # 基于tshark分析的流方向信息
    # 与forward_info匹配判断方向
```

**验证结果**: 两者识别的方向完全一致 (forward/reverse)

### ❌ 流键格式 - 发现关键问题

**Masker模块** (第479行):
```python
flow_key = f"{stream_id}:{direction}"  # 使用冒号分隔符
# 示例: "0:forward", "0:reverse"
```

**Marker模块** (第472行):
```python
flow_key = f"{stream_id}_{direction}"  # 使用下划线分隔符
# 示例: "0_forward", "0_reverse"
```

**问题影响**:
- 规则查找失败
- 掩码操作无法正确应用
- 双模块架构功能失效

### ✅ 序列号处理 - 一致

**两个模块都使用相同的32位序列号回绕处理算法**:
```python
def logical_seq(self, seq32: int, flow_key: str) -> int:
    state = self.seq_state[flow_key]
    if state["last"] is not None and (state["last"] - seq32) > 0x7FFFFFFF:
        state["epoch"] += 1
    state["last"] = seq32
    return (state["epoch"] << 32) | seq32
```

## 问题分析

### 根本原因
两个模块在流键格式上使用了不同的分隔符：
- **Masker**: 冒号 (`:`)
- **Marker**: 下划线 (`_`)

### 影响范围
- **严重程度**: CRITICAL
- **影响功能**: 规则匹配和掩码应用
- **受影响文件**: 所有使用双模块架构的掩码操作

### 技术细节
1. Marker模块生成规则时使用 `"0_forward"` 格式的流键
2. Masker模块查找规则时使用 `"0:forward"` 格式的流键
3. 流键不匹配导致规则查找返回空结果
4. 无规则匹配时，载荷被完全掩码而非按TLS规则保留

## 修复方案

### 推荐方案A: 修改Masker模块使用下划线分隔符

**修改文件**: `src/pktmask/core/pipeline/stages/mask_payload_v2/masker/payload_masker.py`

**修改位置**: 第479行

**修改内容**:
```python
# 修改前
flow_key = f"{stream_id}:{direction}"

# 修改后  
flow_key = f"{stream_id}_{direction}"
```

**优势**:
- 修改点单一，风险较低
- 与Marker模块保持一致
- 不影响tshark的标准输出格式

### 备选方案B: 修改Marker模块使用冒号分隔符

**修改文件**: `src/pktmask/core/pipeline/stages/mask_payload_v2/marker/tls_marker.py`

**修改位置**: 第472行

**修改内容**:
```python
# 修改前
flow_key = f"{stream_id}_{direction}"

# 修改后
flow_key = f"{stream_id}:{direction}"
```

## 验证测试

### 测试步骤
1. 应用修复方案A
2. 运行双模块架构测试
3. 验证规则匹配是否正常工作
4. 检查TLS消息是否按预期保留/掩码

### 预期结果
- 流键格式统一为下划线分隔符
- 规则匹配成功率100%
- TLS消息按类型正确处理

## 风险评估

- **修复风险**: LOW
- **测试要求**: 必须进行完整的功能测试
- **回滚方案**: 简单的代码回退
- **影响范围**: 仅限流键格式，不影响其他逻辑

## 结论

通过深入的流标识一致性验证，确认了双模块架构中的关键问题：

1. **流标识构建逻辑基本一致** - 两个模块能够为相同的TCP流生成相同的stream_id
2. **流方向识别逻辑一致** - 两个模块对数据包方向的判断完全一致  
3. **流键格式存在关键差异** - 这是导致规则匹配失败的根本原因
4. **序列号处理逻辑一致** - 64位逻辑序列号计算算法相同

**立即行动项**: 应用推荐的修复方案A，统一流键格式为下划线分隔符，确保双模块架构的正常运行。

---

**验证执行时间**: 2025-07-13  
**验证工具**: 独立测试脚本 (严格禁止修改主程序代码)  
**验证状态**: 完成 ✅  
**修复状态**: 待实施 ⏳
