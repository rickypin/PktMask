# Phase 2：PyShark → Blind TCP Payload Masker 集成实施方案

## 一、项目目标

### 1.1 核心目标
**数据流重构**：实现从基于TCP序列号的掩码表到基于包索引的指令集的完整转换
```
旧数据流: PyShark分析 → SequenceMaskTable → ScapyRewriter
新数据流: PyShark分析 → MaskingRecipe → BlindPacketMasker
```

### 1.2 关键要求
1. **文件一致性**：输出文件与原始文件在包数、时间戳、顺序方面100%一致（除掩码字节外）
2. **GUI零变化**：用户界面、交互方式、功能100%保持不变
3. **双文件映射**：利用重组文件进行协议分析，但确保输出基于原始文件
4. **Plain IP + VLAN支持**：专注这两种封装类型，确保处理正确性
5. **保持下游模块独立性**: 调用现有的 BlindPacketMasker API，保持其代码和内部实现完全不变

### 1.3 测试样本定义

#### **测试样本1：Plain IP + TLS** (`tests/data/tls/tls_plainip.pcap`)
- TLS Handshake/Alert报文：完全保留
- TLS Application Data报文：保留5字节TLS header，置零Application Data内容

#### **测试样本2：VLAN + TLS** (`tests/data/tls/tls_vlan.pcap`) 
- VLAN标签：正确识别和保留
- TLS处理：与Plain IP样本相同逻辑
- 偏移量计算：VLAN封装下的精确计算

---

## 二、技术方案

### 2.1 EnhancedPySharkAnalyzer核心设计
**核心策略**：单一处理器集成双文件映射和协议分析

**架构方案**：
```
原始文件 + 重组文件 → EnhancedPySharkAnalyzer → MaskingRecipe → TcpPayloadMaskerAdapter → 输出文件
```

**核心实现**：
```python
class EnhancedPySharkAnalyzer(BaseStage):
    """集成双文件处理的增强分析器，替换现有PySharkAnalyzer"""
    
    def execute(self, context: StageContext) -> StageResult:
        # 1. 双文件映射：建立原始文件与重组文件的包对应关系
        mapping = self._build_timestamp_mapping(context.input_file, context.tshark_output)
        
        # 2. 协议分析：基于重组文件进行深度TLS/HTTP协议识别
        protocol_strategies = self._analyze_protocols(context.tshark_output)
        
        # 3. 指令生成：将协议策略映射回原始文件生成MaskingRecipe
        recipe = self._generate_masking_recipe(protocol_strategies, mapping, context.input_file)
        
        # 4. 输出：更新context供后续TcpPayloadMaskerAdapter使用
        context.masking_recipe = recipe
        return self._create_result_with_simple_stats()
```

**关键保证**：
- **文件一致性**：输出基于原始文件，包数、时间戳、顺序100%一致
- **协议完整性**：利用重组文件分析跨包TLS消息、完整HTTP事务
- **精确映射**：协议策略准确映射到原始文件的具体包和偏移位置

### 2.2 核心技术实现

#### 偏移量计算
- **Plain IP**：标准IP+TCP头部长度计算
- **VLAN**：增加4字节VLAN标签检测和处理
- **一致性验证**：确保PyShark和Scapy计算结果一致

#### 双文件映射算法
- **时间戳匹配**：基于包时间戳建立原始文件与重组文件的对应关系
- **协议特征验证**：五元组、载荷长度等辅助验证
- **错误处理**：映射失败时使用保守掩码策略

#### 协议分析策略
- **TLS处理**：Handshake/Alert完全保留，Application Data保留5字节header
- **HTTP处理**：头部保留，载荷按策略处理
- **通用TCP**：回退策略，适用于未识别协议

---

## 三、实施计划

### 3.1 Phase 2-A：核心处理器实现（2天）
**目标**：创建EnhancedPySharkAnalyzer，集成双文件处理逻辑

**关键任务**：
1. **EnhancedPySharkAnalyzer实现**（1.5天）
   - 替换现有PySharkAnalyzer，保持BaseStage接口
   - 实现双文件映射：`_build_timestamp_mapping()`
   - 协议分析：`_analyze_protocols()` 支持TLS/HTTP识别
   - 指令生成：`_generate_masking_recipe()` 输出MaskingRecipe
   - 偏移量计算：支持Plain IP和VLAN封装

2. **集成测试**（0.5天）
   - TcpPayloadMaskerAdapter集成验证
   - 双TLS样本功能验证
   - 包映射关系准确性测试

### 3.2 Phase 2-B：系统集成和验证（1天）
**目标**：完整集成并确保GUI完全不变

**关键任务**：
1. **系统集成**（0.5天）
   - 注册EnhancedPySharkAnalyzer替换旧PySharkAnalyzer
   - 验证事件系统和进度报告接口一致性
   - 确保现有配置和参数正确传递

2. **验收测试**（0.3天）
   - GUI功能完整性验证
   - 双TLS样本端到端测试
   - 文件一致性验证

3. **代码归档**（0.2天）
   - 旧代码标记为归档状态
   - 文档更新和发布准备

### 3.3 进度追踪 (2025-06-25)

- [x] Phase 2-A 核心处理器实现（EnhancedPySharkAnalyzer 已实现并提交，初步单元测试与代码审查通过）
- [x] Phase 2-B 系统集成和验证（已完成，代码已集成并通过初步测试）
- [x] Phase 2-C 核心功能与TLS样本验收（所有验收测试通过，文档和测试用例已合并）

---

## 四、关键风险与缓解

| 风险类别 | 风险描述 | 缓解措施 |
|----------|----------|----------|
| **文件一致性** | 输出文件与原始文件不一致 | 时间戳映射+严格验证+双TLS样本测试 |
| **包映射准确性** | 原始文件与重组文件映射错误 | 时间戳匹配+协议特征验证+降级策略 |
| **GUI兼容性** | 新系统影响现有GUI功能 | 保持BaseStage接口+事件系统一致性 |
| **偏移量一致性** | PyShark和Scapy偏移量不一致 | 统一计算方法+强制一致性测试 |

---

## 五、验收标准

### 5.1 核心功能验收
- [x] 输出文件与原始文件完全一致（包数、时间戳、顺序、非掩码字节）
- [x] Plain IP和VLAN封装类型处理正确
- [x] 包映射关系满足质量要求
- [x] GUI界面、交互、功能100%保持不变

### 5.2 TLS样本专项验收
**Plain IP + TLS样本** (`tests/data/tls/tls_plainip.pcap`)：
- [x] TLS Handshake/Alert报文完全保留
- [x] TLS Application Data：保留5字节header，置零Application Data
- [x] 文件整体一致性验证通过

**VLAN + TLS样本** (`tests/data/tls/tls_vlan.pcap`)：
- [x] VLAN标签正确识别和保留
- [x] VLAN封装下偏移量计算准确
- [x] TLS处理逻辑与Plain IP样本一致
- [x] 文件整体一致性验证通过

### 5.3 系统集成验收
- [x] EnhancedPySharkAnalyzer完全替换旧PySharkAnalyzer
- [x] TcpPayloadMaskerAdapter正常处理新生成的MaskingRecipe
- [x] 现有事件系统和统计报告兼容
- [x] 所有现有功能保持不变

---

## 六、里程碑时间线

| 里程碑 | 时间 | 关键交付物 | 验收条件 |
|--------|------|-----------|----------|
| **M1: 核心处理器完成** | Day 2 | EnhancedPySharkAnalyzer实现，双文件处理逻辑 | 偏移量计算一致，包映射质量达标，MaskingRecipe正确生成 |
| **M2: 系统集成完成** | Day 3 | MultiStageExecutor集成、GUI兼容性验证、代码归档 | 新系统完整工作，GUI完全不变，双TLS样本测试通过 |

**总工期**：3天

**关键成功因素**：
- 文件一致性是核心要求
- GUI零变化是用户体验保证
- 专注Plain IP+VLAN，避免过度复杂化
- 双文件映射确保输出准确性

---

## 项目总结

**实施目标**：通过EnhancedPySharkAnalyzer实现从SequenceMaskTable到MaskingRecipe的数据流重构，确保文件一致性和GUI零变化。

**技术亮点**：
- 双文件映射机制解决协议分析与输出一致性矛盾
- 单一处理器设计，降低系统复杂度
- 专注Plain IP和VLAN封装，避免过度工程化
- 完全保持现有GUI和用户体验

**预期收益**：
- 数据流从序列号模式升级到包索引模式
- 提高协议识别和掩码处理准确性
- 为后续扩展更多封装类型建立基础架构
- 用户体验完全透明化升级 