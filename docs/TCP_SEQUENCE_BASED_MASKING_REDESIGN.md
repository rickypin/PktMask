# TCP Sequence-Based Masking Mechanism Redesign

## 方案概述

本方案旨在重构PktMask的Trim模块，建立基于TCP序列号绝对值范围的通用掩码机制。新机制以TCP连接的单个方向为处理单位，通过tshark重组、PyShark解析生成掩码表，再由scapy进行精确的序列号范围置零操作。

## 核心设计理念

### 1. 通用性原则
- 掩码机制独立于上层协议，适用于任意TCP Payload
- 基于TCP序列号绝对值范围进行字节级精确置零
- 支持多种协议的差异化掩码策略

### 2. 方向性处理
- 以每条TCP连接的单个方向（forward/reverse）为运算单位
- 独立维护每个方向的序列号空间和掩码表
- 避免双向流序列号冲突问题

### 3. 三阶段处理流程
- **阶段1**: TShark预处理（TCP流重组）
- **阶段2**: PyShark分析（协议解析+掩码表生成）
- **阶段3**: Scapy回写（序列号匹配+字节置零）

## 详细技术设计

### 1. TCP连接标识与方向性

```
连接标识格式: TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}
示例:
- TCP_192.168.1.100:12345_10.0.0.1:443_forward
- TCP_192.168.1.100:12345_10.0.0.1:443_reverse
```

### 2. 掩码表数据结构

```python
# 掩码表条目
class MaskEntry:
    tcp_stream_id: str          # TCP流标识（含方向）
    seq_start: int              # 绝对序列号起始位置
    seq_end: int                # 绝对序列号结束位置
    mask_type: str              # 掩码类型（如"tls_application_data"）
    preserve_headers: List[tuple]  # 需要保留的头部范围 [(start, end), ...]

# 掩码表
class SequenceMaskTable:
    entries: Dict[str, List[MaskEntry]]  # 按TCP流ID分组的掩码条目
```

### 3. TLS协议处理示例

对于TLS Application Data (content type = 23)：
- 检测TLS记录边界
- 每个TLS记录保留5字节头部（content type + version + length）
- TLS payload部分添加到掩码表
- 支持单个TCP段包含多个TLS记录的情况

### 4. 序列号匹配算法

```python
def match_sequence_range(packet_seq: int, payload_len: int, mask_entry: MaskEntry) -> tuple:
    """
    匹配数据包序列号范围与掩码条目
    返回: (is_match, mask_start_offset, mask_end_offset)
    """
    packet_start = packet_seq
    packet_end = packet_seq + payload_len - 1
    
    # 计算重叠范围
    overlap_start = max(packet_start, mask_entry.seq_start)
    overlap_end = min(packet_end, mask_entry.seq_end)
    
    if overlap_start <= overlap_end:
        # 转换为数据包内偏移量
        mask_start_offset = overlap_start - packet_start
        mask_end_offset = overlap_end - packet_start
        return (True, mask_start_offset, mask_end_offset)
    
    return (False, 0, 0)
```

## 分阶段重构计划

### Phase 1: 核心数据结构重构 (预计2天)

**目标**: 建立新的掩码表数据结构和TCP流管理机制

**任务清单**:
1. 设计`SequenceMaskTable`类
2. 实现TCP流方向性标识机制
3. 创建`MaskEntry`数据模型
4. 建立序列号范围计算算法

**交付物**:
- `src/pktmask/core/trim/models/sequence_mask_table.py`
- `src/pktmask/core/trim/models/tcp_stream.py`
- 单元测试覆盖

**验证标准**:
- TCP流ID生成正确性测试
- 序列号范围计算精度测试
- 掩码表CRUD操作测试

### Phase 2: PyShark分析器改造 (预计3天)

**目标**: 重构PyShark分析器，生成基于序列号的掩码表

**任务清单**:
1. 修改流ID生成逻辑，支持方向性
2. 重构TLS协议处理逻辑
3. 实现序列号范围计算
4. 建立多协议掩码策略框架

**核心算法**:
```python
def generate_tls_mask_entries(tls_packets: List) -> List[MaskEntry]:
    """为TLS Application Data生成掩码条目"""
    for packet in tls_packets:
        if packet.tls.record.content_type == "23":  # Application Data
            tls_records = parse_tls_records(packet.tls.payload)
            for record in tls_records:
                # 保留5字节TLS头部，payload部分加入掩码表
                mask_start = record.seq_start + 5
                mask_end = record.seq_end
                yield MaskEntry(
                    tcp_stream_id=packet.stream_id,
                    seq_start=mask_start,
                    seq_end=mask_end,
                    mask_type="tls_application_data"
                )
```

**交付物**:
- 增强版`pyshark_analyzer.py`
- TLS协议掩码策略实现
- 序列号映射算法

**验证标准**:
- 使用`tls_sample.pcap`验证TLS处理逻辑
- 确保14、15号包生成正确掩码条目
- 确保4、6、7、9、10、12、16、19号包不生成掩码条目

### Phase 3: Scapy回写器改造 (预计2天)

**目标**: 实现基于序列号匹配的通用置零机制

**任务清单**:
1. 重构序列号提取和计算逻辑
2. 实现掩码表查询和匹配算法
3. 建立字节级精确置零机制
4. 优化处理性能

**核心处理流程**:
```python
def apply_sequence_based_masks(packet, mask_table: SequenceMaskTable):
    """应用基于序列号的掩码"""
    # 1. 提取TCP序列号和payload
    tcp_seq = packet[TCP].seq
    payload = bytes(packet[TCP].payload)
    
    # 2. 查询掩码表
    stream_id = generate_stream_id(packet)
    mask_entries = mask_table.get_entries(stream_id)
    
    # 3. 序列号匹配和置零
    modified_payload = bytearray(payload)
    for entry in mask_entries:
        is_match, start_offset, end_offset = match_sequence_range(
            tcp_seq, len(payload), entry
        )
        if is_match:
            # 应用头部保留规则
            apply_preserve_headers(modified_payload, entry.preserve_headers)
            # 置零指定范围
            modified_payload[start_offset:end_offset+1] = b'\x00' * (end_offset - start_offset + 1)
    
    # 4. 更新数据包
    packet[TCP].payload = bytes(modified_payload)
```

**交付物**:
- 重构版`scapy_rewriter.py`
- 序列号匹配优化算法
- 通用置零处理器

**验证标准**:
- 序列号匹配精度≥99%
- 字节置零位置准确性验证
- 处理性能≥500 pps

### Phase 4: 协议策略扩展 (预计2天)

**目标**: 建立可扩展的协议掩码策略框架

**任务清单**:
1. 抽象协议掩码策略接口
2. 实现HTTP协议掩码策略
3. 建立策略注册和动态加载机制
4. 支持混合协议场景

**策略框架设计**:
```python
class ProtocolMaskStrategy(ABC):
    @abstractmethod
    def detect_protocol(self, packet) -> bool:
        """检测是否为该协议"""
        pass
    
    @abstractmethod
    def generate_mask_entries(self, packets: List) -> List[MaskEntry]:
        """生成掩码条目"""
        pass

class TLSMaskStrategy(ProtocolMaskStrategy):
    def detect_protocol(self, packet) -> bool:
        return hasattr(packet, 'tls')
    
    def generate_mask_entries(self, packets: List) -> List[MaskEntry]:
        # TLS特定的掩码生成逻辑
        pass
```

**交付物**:
- 协议策略抽象基类
- TLS/HTTP掩码策略实现
- 策略工厂和注册机制

**验证标准**:
- 支持至少3种协议策略
- 策略切换和组合测试
- 混合协议文件处理验证

### Phase 5: 集成测试与性能优化 (预计2天)

**目标**: 端到端验证和性能调优

**任务清单**:
1. 建立完整的集成测试框架
2. 使用真实数据进行端到端验证
3. 性能分析和优化
4. 错误处理和边界条件测试

**测试用例设计**:
```python
class TestSequenceMasking:
    def test_tls_sample_processing(self):
        """使用tls_sample.pcap进行完整流程测试"""
        # 预期结果:
        # - 包14,15: TLS Application Data被置零（保留5字节头）
        # - 包4,6,7,9,10,12,16,19: 保持不变
        pass
    
    def test_multi_tls_records_in_single_tcp(self):
        """测试单个TCP段包含多个TLS记录的情况"""
        pass
    
    def test_cross_packet_tls_records(self):
        """测试跨数据包的TLS记录处理"""
        pass
```

**性能目标**:
- 处理速度≥1000 pps
- 内存使用<100MB/1000包
- 序列号匹配查询时间<1ms

**交付物**:
- 完整集成测试套件
- 性能基准测试
- 错误处理机制
- 详细文档和使用指南

## 验证计划

### 1. 单元测试验证
每个Phase完成后进行对应模块的单元测试，确保功能正确性。

### 2. 集成测试验证
- **基础验证**: 使用`tls_sample.pcap`验证TLS处理逻辑
- **扩展验证**: 使用`tests/samples/`下的多种协议文件
- **性能验证**: 大文件处理和并发测试

### 3. 回归测试验证
确保新机制不影响现有功能：
- 对比重构前后的处理结果
- 验证GUI界面功能保持不变
- 确认配置系统兼容性

### 4. 真实数据验证
- 使用生产环境的PCAP文件进行测试
- 验证多种网络协议和封装格式
- 确认掩码效果符合预期

## 关键技术考量

### 1. 序列号空间管理
- 处理TCP序列号回绕（wrap-around）情况
- 支持大文件和长连接的序列号范围
- 优化序列号查询和匹配性能

### 2. 内存优化
- 按需加载掩码表条目
- 实现流式处理避免全量加载
- 及时释放已处理流的掩码数据

### 3. 容错机制
- 处理损坏或不完整的TCP流
- 支持部分重组的TCP段
- 优雅处理协议解析失败情况

### 4. 扩展性设计
- 预留新协议策略接入点
- 支持自定义掩码规则
- 提供插件机制用于特殊需求

## 预期收益

### 1. 功能改进
- 更精确的字节级掩码控制
- 支持复杂协议场景处理
- 提高掩码操作的准确性

### 2. 性能提升
- 减少不必要的协议解析开销
- 优化序列号匹配算法
- 提高大文件处理效率

### 3. 可维护性
- 模块化设计便于功能扩展
- 清晰的接口定义降低维护成本
- 完整的测试覆盖保证代码质量

### 4. 通用性
- 独立于协议的掩码机制
- 支持未来新协议的快速接入
- 灵活的策略配置能力

## 风险评估与缓解

### 1. 技术风险
- **序列号计算复杂性**: 建立完整的单元测试覆盖，使用已知数据验证算法正确性
- **性能回归风险**: 建立性能基准测试，确保重构后性能不低于现有水平
- **兼容性风险**: 保持现有API接口不变，确保GUI和配置系统无感知升级

### 2. 进度风险
- **复杂度低估**: 预留20%缓冲时间，分阶段交付降低风险
- **测试验证时间**: 并行进行开发和测试，尽早发现问题

### 3. 缓解措施
- 建立回滚机制，保留旧版本备份
- 分阶段验收，确保每个阶段质量达标
- 持续集成，及时发现和修复问题

## 实施时间表

| 阶段 | 任务 | 预计工期 | 开始时间 | 完成时间 | 负责人 | 验收标准 |
|------|------|----------|----------|----------|---------|----------|
| Phase 1 | 核心数据结构重构 | 2天 | Day 1 | Day 2 | 开发者 | 所有单元测试通过，API文档完成 |
| Phase 2 | PyShark分析器改造 | 3天 | Day 3 | Day 5 | 开发者 | TLS样本测试通过，掩码表生成正确 |
| Phase 3 | Scapy回写器改造 | 2天 | Day 6 | Day 7 | 开发者 | 序列号匹配≥99%，置零位置准确 |
| Phase 4 | 协议策略扩展 | 2天 | Day 8 | Day 9 | 开发者 | 支持3种协议，策略切换正常 |
| Phase 5 | 集成测试与优化 | 2天 | Day 10 | Day 11 | 开发者+测试 | 端到端测试通过，性能达标 |

**总工期**: 11个工作日  
**关键里程碑**: 
- Day 5: PyShark分析器完成，可生成正确掩码表
- Day 7: Scapy回写器完成，基础置零功能可用  
- Day 11: 完整系统集成，生产环境就绪

## 与现有系统的兼容性

### 1. 保持现有接口
- **MultiStageExecutor**: 保持现有的executor接口不变
- **BaseStage**: 继承现有的基类，保证接口一致性
- **配置系统**: 复用现有的配置管理机制

### 2. 渐进式迁移
- **并行运行**: 新旧系统可并行运行，便于对比验证
- **配置开关**: 提供配置选项在新旧机制间切换
- **回滚机制**: 遇到问题可快速回滚到旧版本

### 3. GUI集成
- **透明升级**: GUI界面无需修改，用户体验保持一致
- **进度报告**: 利用现有的事件系统报告处理进度
- **错误处理**: 集成到现有的错误处理和报告机制

## 质量保证措施

### 1. 代码质量
- **代码审查**: 每个阶段完成后进行代码审查
- **静态分析**: 使用pylint、mypy等工具进行静态检查
- **文档同步**: 代码和文档同步更新

### 2. 测试策略
- **单元测试**: 每个模块≥80%代码覆盖率
- **集成测试**: 端到端流程测试，覆盖主要使用场景
- **性能测试**: 建立性能基准，确保无回归
- **回归测试**: 使用现有测试样本验证兼容性

### 3. 文档完善
- **API文档**: 详细的接口文档和使用示例
- **开发者指南**: 针对后续维护和扩展的技术指南
- **用户手册**: 新功能的使用说明和配置指导

## 部署策略

### 1. 灰度发布
- **内部测试**: 先在开发环境完整验证
- **Beta测试**: 选择少量用户进行Beta测试
- **正式发布**: 逐步扩大用户范围

### 2. 监控和反馈
- **性能监控**: 实时监控处理性能和错误率
- **用户反馈**: 建立反馈收集机制
- **快速响应**: 建立问题快速响应和修复流程

## 长期维护计划

### 1. 功能扩展
- **新协议支持**: 预留扩展接口，便于添加新协议支持
- **性能优化**: 持续优化算法和数据结构
- **功能增强**: 根据用户需求增加新功能

### 2. 技术债务管理
- **定期重构**: 定期检查和重构代码，保持代码质量
- **依赖更新**: 及时更新第三方依赖，保证安全性
- **技术栈升级**: 根据技术发展适时升级技术栈

## 总结

本重构方案基于TCP序列号绝对值范围的通用掩码机制，具有高度的通用性和扩展性。通过三阶段处理流程和方向性TCP连接管理，能够精确处理各种协议的掩码需求。分阶段的重构计划确保了项目的可控性和质量保证，预期将显著提升PktMask Trim模块的功能性和性能表现。

该方案不仅解决了当前掩码机制的复杂性问题，还为未来的功能扩展奠定了坚实基础。通过严格的质量保证措施和完善的部署策略，确保重构过程的顺利进行和最终系统的稳定可靠。 