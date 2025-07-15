# PayloadMasker默认全掩码处理策略修改

## 📋 修改概述

本次修改实现了PayloadMasker模块的默认全掩码处理策略，确保所有TCP载荷都经过掩码处理，提高数据安全性。

## 🎯 核心需求

### 修改前的问题
- **无匹配规则时原样返回**：非TLS协议的TCP载荷完全保持原始状态
- **敏感信息泄露风险**：HTTP、SSH、FTP等明文协议的敏感数据暴露
- **不一致的安全策略**：只有TLS流量被处理，其他协议被忽略

### 修改后的策略
- **默认全掩码**：所有TCP载荷都先创建全零缓冲区
- **选择性保留**：仅根据KeepRuleSet中的规则进行保留
- **一致的安全策略**：拒绝保留，除非明确允许

## 🔧 具体修改内容

### 1. _process_packet方法修改

#### 修改前逻辑
```python
# 检查是否有匹配的规则
if stream_id not in rule_lookup or direction not in rule_lookup[stream_id]:
    # 没有匹配的规则，记录调试信息
    self.logger.debug(f"无匹配规则: stream_id={stream_id}, direction={direction}")
    return packet, False  # ❌ 原样返回，不做任何修改

# 检查载荷是否发生变化
if new_payload == payload:
    # 没有修改，原样返回
    return packet, False  # ❌ 当规则为空时，载荷保持原样
```

#### 修改后逻辑
```python
# 获取匹配的规则数据，如果没有匹配规则则使用空规则数据
if stream_id in rule_lookup and direction in rule_lookup[stream_id]:
    rule_data = rule_lookup[stream_id][direction]
    self.logger.debug(f"找到匹配规则: stream_id={stream_id}, direction={direction}")
else:
    # 没有匹配的规则，使用空规则数据（将导致全掩码处理）
    rule_data = {'header_only_ranges': [], 'full_preserve_ranges': []}
    self.logger.debug(f"无匹配规则，执行全掩码: stream_id={stream_id}, direction={direction}")

# 应用保留规则（对于无规则的情况，将执行全掩码）
new_payload = self._apply_keep_rules(payload, seq_start, seq_end, rule_data)

# 检查载荷是否发生变化
if new_payload is None or new_payload == payload:
    # 如果_apply_keep_rules返回None或未修改，但我们需要确保全掩码处理
    if rule_data['header_only_ranges'] == [] and rule_data['full_preserve_ranges'] == []:
        # 无任何保留规则，执行全掩码
        new_payload = b'\x00' * len(payload)
        self.logger.debug(f"执行全掩码处理: {len(payload)}字节")
    else:
        # 有规则但未修改，原样返回
        return packet, False
```

### 2. _apply_keep_rules方法修改

#### 返回类型修改
```python
# 修改前
def _apply_keep_rules(self, payload: bytes, seg_start: int, seg_end: int,
                     rule_data: Dict) -> Optional[bytes]:  # ❌ 可能返回None

# 修改后  
def _apply_keep_rules(self, payload: bytes, seg_start: int, seg_end: int,
                     rule_data: Dict) -> bytes:  # ✅ 总是返回处理后的载荷
```

#### 文档更新
```python
"""应用保留规则到载荷

修改说明：现在总是返回处理后的载荷，实现默认全掩码策略。
- 如果有保留规则，则根据规则选择性保留
- 如果无保留规则，则返回全零载荷
- 不再返回None，确保所有TCP载荷都被处理
"""
```

### 3. 相关方法签名更新

同步更新了以下方法的返回类型：
- `_apply_keep_rules_simple` 
- `_apply_keep_rules_optimized`

## 📊 验证结果

### 测试场景
1. **HTTP数据包**（非TLS，无规则）→ ✅ 完全掩码
2. **SSH数据包**（非TLS，无规则）→ ✅ 完全掩码  
3. **TLS数据包**（有保留规则）→ ✅ 选择性保留

### 处理统计
- **处理包数**: 3
- **修改包数**: 3 (100%修改率)
- **保留字节数**: 21
- **掩码字节数**: 50

### 载荷分析示例
```
HTTP载荷: "GET /secret.html HTTP/1.1\r\n" 
→ 处理后: 27个零字节 ✅

SSH载荷: "SSH-2.0-OpenSSH_8.0\r\n"
→ 处理后: 21个零字节 ✅

TLS载荷: "\x16\x03\x03\x00\x10TLS_HANDSHAKE_DATA"
→ 处理后: 部分保留，部分掩码 ✅
```

## 🔒 安全性提升

### 修改前的风险
- **HTTP明文协议**：用户名、密码、API密钥等完全暴露
- **SSH协议**：版本信息、配置信息等可能泄露
- **数据库协议**：SQL查询、数据内容等敏感信息暴露
- **内部协议**：业务逻辑、配置信息等可能暴露

### 修改后的保护
- **默认安全**：所有TCP载荷默认被掩码
- **明确保留**：只有在KeepRuleSet中明确指定的数据才被保留
- **一致策略**：所有协议使用相同的安全处理逻辑
- **零信任原则**：拒绝保留，除非明确允许

## 📈 性能影响

### 处理开销
- **增加的操作**：为无规则流量创建全零缓冲区
- **减少的操作**：移除了规则匹配失败时的早期返回
- **整体影响**：轻微增加，但安全性显著提升

### 统计信息
- **修改包数**：现在正确反映所有被处理的包
- **掩码字节数**：准确统计被掩码的字节数
- **保留字节数**：准确统计被保留的字节数

## 🎯 实现效果

### ✅ 已实现的目标
1. 移除了"无匹配规则时原样返回"的逻辑
2. 对所有包含TCP载荷的数据包都执行掩码处理
3. 无规则时创建全零缓冲区
4. 有规则时根据规则选择性保留
5. 保持现有的优先级处理逻辑（header_only > full_preserve）
6. 保持左闭右开区间[seq_start, seq_end)的语义
7. 确保载荷长度不变，只改变内容
8. 更新统计信息以正确反映掩码字节数

### 🔄 兼容性保证
- **现有TLS处理逻辑**：完全保持不变
- **规则优先级策略**：完全保持不变
- **接口签名**：保持向后兼容
- **配置选项**：无需修改现有配置

## 📝 总结

本次修改成功实现了PayloadMasker的默认全掩码处理策略，显著提升了数据安全性：

- **非TLS协议**：从完全暴露改为完全掩码
- **TLS协议**：保持现有的精确控制逻辑
- **统计信息**：更准确地反映处理结果
- **安全策略**：从"默认允许"改为"默认拒绝"

这一修改确保了PktMask在处理混合协议流量时的一致性和安全性，特别是对包含敏感信息的非TLS协议提供了有效保护。
