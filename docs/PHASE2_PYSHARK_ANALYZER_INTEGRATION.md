# Phase 2: PyShark分析器集成改造方案

## 概述

第二阶段的目标是改造 `pyshark_analyzer` 和相关前序环节，使其能够生成符合Phase 1 API要求的**包级掩码指令**，并通过调用Phase 1的API完成整个掩码流程。

## 核心设计理念

### 当前架构
- `tshark_preprocessor` → `pyshark_analyzer` → `scapy_rewriter`
- 基于TCP序列号的 `SequenceMaskTable` 作为中间数据结构
- 各Stage通过 `StageContext` 传递掩码表

### 目标架构  
- `tshark_preprocessor` → `enhanced_pyshark_analyzer` → `tcp_payload_masker_adapter`
- 包级的 `MaskingRecipe` 作为最终数据结构
- 前序环节专注于智能分析，后序环节专注于精确执行

## 改造策略

### 整体改造思路
采用**"渐进式改造"**策略，最大限度复用现有代码：

1. **保留现有分析逻辑**: 继续使用成熟的协议分析和掩码策略生成代码
2. **增加翻译层**: 在现有逻辑基础上，增加"序列号掩码表 → 包级指令"的翻译功能
3. **API适配器**: 创建新的Stage来调用Phase 1的独立API
4. **向后兼容**: 确保改造过程中系统始终可用

## 详细改造方案

### 1. Enhanced PyShark Analyzer

#### 核心改动
在 `src/pktmask/core/trim/stages/pyshark_analyzer.py` 中增加新的方法：

```python
class PysharkAnalyzer(BaseStage):
    
    def execute(self, context: StageContext) -> StageResult:
        """改造后的主执行方法"""
        
        # 第1步: 生成逻辑掩码表 (保持现有逻辑)
        self._analyze_with_tshark_flow(context)
        logical_mask_table = self.mask_table  # 现有的SequenceMaskTable
        
        # 第2步: 翻译为包级指令 (新增核心功能)
        masking_recipe = self._translate_to_packet_instructions(
            logical_mask_table, 
            context.input_file
        )
        
        # 第3步: 输出到上下文
        context.masking_recipe = masking_recipe
        context.mask_table = logical_mask_table  # 临时保留，用于兼容性验证
        
        return StageResult(
            success=True,
            message=f"Generated {len(masking_recipe.instructions)} packet-level instructions",
            data={"recipe_size": len(masking_recipe.instructions)}
        )
```

#### 核心翻译逻辑

```python
def _translate_to_packet_instructions(
    self, 
    mask_table: SequenceMaskTable, 
    input_file: str
) -> MaskingRecipe:
    """
    将逻辑掩码表翻译为包级指令
    
    核心思路:
    1. 遍历原始PCAP文件
    2. 对每个包，检查其是否属于需要掩码的流
    3. 如果属于，计算该包内需要掩码的具体位置
    4. 生成精确的包级指令
    """
    
    # 1. 预处理掩码表，按流ID组织
    stream_masks = self._organize_masks_by_stream(mask_table)
    
    # 2. 为每个流维护处理状态
    stream_states = {
        stream_id: StreamProcessingState(masks)
        for stream_id, masks in stream_masks.items()
    }
    
    # 3. 遍历原始包，生成指令
    instructions = {}
    
    # 使用新的FileCapture实例处理原始文件
    with FileCapture(input_file, keep_packets=False) as cap:
        for packet_index, packet in enumerate(cap):
            
            if not self._is_tcp_packet(packet):
                continue
                
            # 生成流ID
            stream_id = self._generate_stream_id(packet)
            
            if stream_id not in stream_states:
                continue  # 该流不需要掩码
                
            # 提取包信息
            packet_info = self._extract_packet_info(packet, packet_index)
            
            # 计算该包的掩码指令
            instruction = self._calculate_packet_instruction(
                packet_info, 
                stream_states[stream_id]
            )
            
            if instruction:
                key = (packet_info.index, packet_info.timestamp)
                instructions[key] = instruction
    
    return MaskingRecipe(
        instructions=instructions,
        total_packets=packet_index + 1,
        metadata={
            "stream_count": len(stream_states),
            "analysis_timestamp": time.time()
        }
    )
```

#### 关键辅助方法

```python
@dataclass
class PacketInfo:
    """单个数据包的信息"""
    index: int
    timestamp: str  
    stream_id: str
    seq_number: int
    payload_length: int
    payload_offset: int  # TCP载荷的绝对字节偏移量

class StreamProcessingState:
    """流处理状态，用于维护各个流的掩码应用进度"""
    
    def __init__(self, mask_entries: List[MaskEntry]):
        self.mask_entries = sorted(mask_entries, key=lambda x: x.start_seq)
        self.total_bytes_processed = 0
        self.current_mask_index = 0
        
    def calculate_mask_for_packet(self, packet_seq: int, packet_len: int) -> Optional[MaskSpec]:
        """为给定的包计算掩码规范"""
        # 实现逻辑: 检查包的序列号范围与掩码条目的交集
        # 返回该包需要应用的具体掩码规范
        pass

def _extract_packet_info(self, packet, packet_index: int) -> PacketInfo:
    """从PyShark包对象中提取关键信息"""
    
    # 获取基本信息
    timestamp = str(packet.sniff_timestamp)
    stream_id = self._generate_stream_id(packet)
    seq_number = int(packet.tcp.seq) if hasattr(packet, 'tcp') else 0
    
    # 计算载荷长度
    if hasattr(packet.tcp, 'payload'):
        payload_length = len(packet.tcp.payload.binary_value)
    else:
        payload_length = 0
    
    # 关键: 获取TCP载荷的绝对偏移量
    payload_offset = self._get_tcp_payload_offset(packet)
    
    return PacketInfo(
        index=packet_index,
        timestamp=timestamp,
        stream_id=stream_id, 
        seq_number=seq_number,
        payload_length=payload_length,
        payload_offset=payload_offset
    )

def _get_tcp_payload_offset(self, packet) -> int:
    """
    获取TCP载荷在数据包字节流中的绝对偏移量
    
    这是关键方法，需要利用PyShark/TShark的能力来准确计算
    即使面对复杂的多层封装也能给出正确结果
    """
    
    # 方法1: 尝试直接从PyShark获取偏移信息
    if hasattr(packet.tcp, '_ws_expert_layer_offset'):
        return int(packet.tcp._ws_expert_layer_offset)
    
    # 方法2: 计算所有头部长度的总和
    offset = 0
    
    # Ethernet头
    if hasattr(packet, 'eth'):
        offset += 14
        
    # VLAN标签 (可能多层)
    if hasattr(packet, 'vlan'):
        # 计算VLAN标签数量和总长度
        offset += self._calculate_vlan_header_length(packet)
        
    # MPLS标签
    if hasattr(packet, 'mpls'):
        offset += self._calculate_mpls_header_length(packet)
        
    # IP头
    if hasattr(packet, 'ip'):
        offset += int(packet.ip.hdr_len) * 4
    elif hasattr(packet, 'ipv6'):
        offset += 40  # IPv6固定头长度
        
    # TCP头  
    if hasattr(packet, 'tcp'):
        offset += int(packet.tcp.hdr_len) * 4
        
    return offset
```

### 2. TCP Payload Masker Adapter

创建新的Stage来调用Phase 1的API：

```python
# src/pktmask/core/trim/stages/tcp_payload_masker_adapter.py

from ...tcp_payload_masker import (
    mask_pcap_with_instructions,
    MaskingRecipe
)

class TcpPayloadMaskerAdapter(BaseStage):
    """TCP载荷掩码器适配器"""
    
    def __init__(self):
        super().__init__()
        self.stage_name = "TCP Payload Masker"
        
    def execute(self, context: StageContext) -> StageResult:
        """执行包级掩码操作"""
        
        # 从上下文获取掩码配方
        masking_recipe = context.masking_recipe
        if not masking_recipe:
            return StageResult(
                success=False,
                message="No masking recipe found in context"
            )
        
        # 准备输出文件路径
        output_file = self._prepare_output_file(context.input_file)
        
        # 调用Phase 1的独立API
        result = mask_pcap_with_instructions(
            input_file=context.input_file,
            output_file=output_file,
            masking_recipe=masking_recipe,
            verify_consistency=True
        )
        
        # 处理结果
        if result.success:
            context.output_file = output_file
            context.masking_statistics = result.statistics
            
            return StageResult(
                success=True,
                message=f"Successfully masked {result.modified_packets}/{result.processed_packets} packets",
                data={
                    "processed_packets": result.processed_packets,
                    "modified_packets": result.modified_packets,
                    "output_file": output_file
                }
            )
        else:
            return StageResult(
                success=False,
                message=f"Masking failed: {'; '.join(result.errors)}",
                data={"errors": result.errors}
            )
            
    def _prepare_output_file(self, input_file: str) -> str:
        """准备输出文件路径"""
        base_name = os.path.splitext(input_file)[0]
        return f"{base_name}_masked.pcap"
```

### 3. 多阶段执行器集成

更新执行器配置以使用新的Stage：

```python
# 在适当的配置文件中
def create_enhanced_trimmer_executor() -> MultiStageExecutor:
    """创建增强版裁切器执行器"""
    
    executor = MultiStageExecutor("Enhanced TCP Payload Trimmer")
    
    # Stage 1: TShark预处理 (保持不变)
    executor.register_stage(TsharkPreprocessor())
    
    # Stage 2: 增强版PyShark分析器
    executor.register_stage(PysharkAnalyzer())  # 内部已增强
    
    # Stage 3: TCP载荷掩码器适配器 (新)
    executor.register_stage(TcpPayloadMaskerAdapter())
    
    return executor
```

## 兼容性和验证策略

### 1. 双轨验证
在改造初期，同时生成新旧两种数据格式，进行对比验证：

```python
# 在PysharkAnalyzer中临时增加
def execute(self, context: StageContext) -> StageResult:
    # ... 现有逻辑生成 mask_table ...
    
    # 新逻辑生成 masking_recipe  
    masking_recipe = self._translate_to_packet_instructions(mask_table, context.input_file)
    
    # 双轨输出，便于验证
    context.mask_table = mask_table  # 旧格式
    context.masking_recipe = masking_recipe  # 新格式
    
    # 可选: 进行一致性验证
    if self.enable_consistency_check:
        self._verify_translation_consistency(mask_table, masking_recipe)
```

### 2. 渐进式迁移
1. **第一步**: 实现新的翻译逻辑，但继续使用旧的 `scapy_rewriter`
2. **第二步**: 引入 `TcpPayloadMaskerAdapter`，与旧Stage并行运行，对比结果
3. **第三步**: 完全切换到新架构，移除旧代码

### 3. 回滚方案
保留旧代码作为fallback机制，通过配置开关控制使用新旧方案。

## 测试验证

### 集成测试策略
1. **端到端测试**: 使用完整的多阶段流程，验证从TShark分析到最终掩码的整个链路
2. **对比测试**: 新旧方案在相同输入下的输出对比
3. **性能测试**: 验证新架构的性能表现
4. **真实样本测试**: 使用项目中的各种真实PCAP样本

### 验证数据集
- Plain IP samples
- VLAN/Double VLAN samples  
- TLS encrypted samples
- Large file samples (>100MB)
- Multi-protocol samples

## 实施计划

### Phase 2.1: 翻译逻辑开发 (5天)
1. 实现 `_translate_to_packet_instructions` 核心方法
2. 实现 `_get_tcp_payload_offset` 偏移量计算
3. 单元测试验证翻译逻辑正确性

### Phase 2.2: 适配器开发 (2天)  
1. 实现 `TcpPayloadMaskerAdapter`
2. 集成到多阶段执行器中
3. 基础集成测试

### Phase 2.3: 端到端验证 (3天)
1. 使用真实样本进行完整流程测试
2. 性能基准测试和优化
3. 与Phase 1结果的一致性验证

### Phase 2.4: 生产化 (2天)
1. 完善错误处理和日志记录
2. 更新配置和文档
3. 最终的回归测试

## 成功标准

1. **功能一致性**: 新架构产生的掩码结果与现有方案100%一致
2. **性能要求**: 端到端处理时间不超过现有方案的120%
3. **可靠性**: 在各种复杂封装场景下稳定工作
4. **可维护性**: 代码结构清晰，易于理解和扩展

## 风险缓解

### 主要风险点
1. **PyShark偏移量计算准确性**: 多层封装场景下的偏移量计算
2. **包匹配一致性**: 新旧机制在包识别上的一致性
3. **性能影响**: 二次文件遍历的性能开销

### 缓解措施
1. **充分测试**: 针对各种封装类型进行专项测试
2. **渐进部署**: 通过配置开关控制，支持快速回滚
3. **性能监控**: 实时监控关键性能指标，及时发现问题

## 与Phase 1的接口

Phase 2将调用Phase 1提供的标准API：

```python
from pktmask.core.tcp_payload_masker import mask_pcap_with_instructions

# 在TcpPayloadMaskerAdapter中调用
result = mask_pcap_with_instructions(
    input_file=context.input_file,
    output_file=output_file, 
    masking_recipe=context.masking_recipe,
    verify_consistency=True
)
```

这确保了两个阶段的清晰解耦和标准化接口。 