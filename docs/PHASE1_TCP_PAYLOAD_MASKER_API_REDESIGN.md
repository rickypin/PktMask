# Phase 1: TCP载荷掩码器API重设计方案

## 概述

第一阶段的目标是将 `tcp_payload_masker` 模块改造为一个**完全独立**的、基于**包级指令**的掩码执行引擎。它将脱离当前基于TCP序列号的复杂匹配机制，转而接收精确的、以数据包为单位的掩码指令。

## 核心设计理念

### 当前问题
- `scapy_rewriter` 承担了太多协议解析责任
- 基于TCP序列号的匹配机制复杂且脆弱
- 多层封装支持困难，需要复杂的头部长度计算
- 与PyShark分析结果的对应关系容易出错

### 目标架构
- **职责单一**: 纯粹的字节级掩码执行器
- **输入简化**: 接收包级的、基于字节偏移的精确指令
- **协议无关**: 完全不解析协议，只进行字节操作
- **API优先**: 提供标准化的函数调用接口

## API接口设计

### 核心数据结构

```python
@dataclass
class PacketMaskInstruction:
    """单个数据包的掩码指令"""
    packet_index: int          # 包在PCAP中的索引（从0开始）
    packet_timestamp: str      # 纳秒级时间戳字符串
    payload_offset: int        # TCP载荷在包字节流中的绝对偏移量
    mask_spec: MaskSpec       # 掩码规范（复用现有类型）

@dataclass 
class MaskingRecipe:
    """完整的掩码配方"""
    instructions: Dict[Tuple[int, str], PacketMaskInstruction]
    total_packets: int
    metadata: Dict[str, Any] = field(default_factory=dict)

class PacketMaskingResult:
    """掩码执行结果"""
    success: bool
    processed_packets: int
    modified_packets: int
    output_file: str
    errors: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
```

### 主要API函数

```python
def mask_pcap_with_instructions(
    input_file: str,
    output_file: str, 
    masking_recipe: MaskingRecipe,
    verify_consistency: bool = True
) -> PacketMaskingResult:
    """
    使用包级指令对PCAP文件进行掩码处理
    
    Args:
        input_file: 输入PCAP文件路径
        output_file: 输出PCAP文件路径  
        masking_recipe: 包含所有掩码指令的配方
        verify_consistency: 是否验证输入输出一致性
        
    Returns:
        处理结果，包含统计信息和错误信息
    """

def validate_masking_recipe(
    recipe: MaskingRecipe, 
    input_file: str
) -> List[str]:
    """
    验证掩码配方的有效性
    
    Returns:
        错误信息列表，空列表表示验证通过
    """

def create_masking_recipe_from_dict(
    instructions_dict: Dict[str, Dict]
) -> MaskingRecipe:
    """从字典格式创建掩码配方"""
```

## 核心实现逻辑

### 1. 盲操作执行引擎

```python
class BlindPacketMasker:
    """盲操作数据包掩码器"""
    
    def __init__(self, masking_recipe: MaskingRecipe):
        self.recipe = masking_recipe
        self.stats = MaskingStatistics()
    
    def process_packet(self, packet_index: int, packet) -> Optional[bytes]:
        """
        处理单个数据包
        
        核心逻辑:
        1. 根据(index, timestamp)查找指令
        2. 如果无指令，直接返回原包
        3. 如果有指令，执行字节级掩码操作
        4. 返回修改后的字节流
        """
        # 获取包的时间戳
        timestamp = str(packet.time)
        key = (packet_index, timestamp)
        
        # 查找指令
        instruction = self.recipe.instructions.get(key)
        if not instruction:
            return raw(packet)  # 无需修改
            
        # 执行盲操作
        raw_bytes = bytearray(raw(packet))
        self._apply_mask_instruction(raw_bytes, instruction)
        return bytes(raw_bytes)
    
    def _apply_mask_instruction(
        self, 
        raw_bytes: bytearray, 
        instruction: PacketMaskInstruction
    ):
        """在字节数组上应用掩码指令"""
        offset = instruction.payload_offset
        mask_spec = instruction.mask_spec
        
        # 根据mask_spec类型执行不同的掩码操作
        if isinstance(mask_spec, MaskAfter):
            start_pos = offset + mask_spec.keep_bytes
            # 从start_pos开始置零到包末尾
            if start_pos < len(raw_bytes):
                raw_bytes[start_pos:] = b'\x00' * (len(raw_bytes) - start_pos)
                
        elif isinstance(mask_spec, MaskRange):
            for range_spec in mask_spec.ranges:
                start_pos = offset + range_spec.start
                end_pos = start_pos + range_spec.length
                if start_pos < len(raw_bytes):
                    end_pos = min(end_pos, len(raw_bytes))
                    raw_bytes[start_pos:end_pos] = b'\x00' * (end_pos - start_pos)
        
        # KeepAll类型不做任何操作
```

### 2. 文件处理流程

```python
def mask_pcap_with_instructions(
    input_file: str,
    output_file: str,
    masking_recipe: MaskingRecipe,
    verify_consistency: bool = True
) -> PacketMaskingResult:
    
    # 验证输入
    errors = validate_masking_recipe(masking_recipe, input_file)
    if errors:
        return PacketMaskingResult(
            success=False, 
            processed_packets=0,
            modified_packets=0,
            output_file="",
            errors=errors
        )
    
    # 创建掩码器
    masker = BlindPacketMasker(masking_recipe)
    modified_packets = []
    
    # 处理每个包
    for index, packet in enumerate(PcapReader(input_file)):
        processed_bytes = masker.process_packet(index, packet)
        
        if processed_bytes != raw(packet):
            # 包被修改了，需要重新构造
            modified_packet = Ether(processed_bytes)
            modified_packets.append(modified_packet)
            masker.stats.modified_count += 1
        else:
            # 包未修改
            modified_packets.append(packet)
        
        masker.stats.processed_count += 1
    
    # 写入输出文件
    wrpcap(output_file, modified_packets)
    
    # 一致性验证（如果启用）
    if verify_consistency:
        consistency_errors = _verify_consistency(input_file, output_file, masking_recipe)
        errors.extend(consistency_errors)
    
    return PacketMaskingResult(
        success=len(errors) == 0,
        processed_packets=masker.stats.processed_count,
        modified_packets=masker.stats.modified_count,
        output_file=output_file,
        errors=errors,
        statistics=masker.stats.to_dict()
    )
```

## 模块结构调整

### 文件组织
```
src/pktmask/core/tcp_payload_masker/
├── __init__.py                    # 导出主要API
├── api/
│   ├── __init__.py
│   ├── types.py                   # 数据类型定义
│   ├── masker.py                  # 主要API实现
│   └── validator.py               # 验证功能
├── core/
│   ├── __init__.py  
│   ├── blind_masker.py            # 盲操作核心引擎
│   ├── packet_processor.py       # 包处理逻辑
│   └── consistency.py             # 一致性验证
└── utils/
    ├── __init__.py
    ├── stats.py                   # 统计信息
    └── helpers.py                 # 辅助函数
```

### 主要导出接口
```python
# src/pktmask/core/tcp_payload_masker/__init__.py
from .api.masker import (
    mask_pcap_with_instructions,
    validate_masking_recipe,
    create_masking_recipe_from_dict
)
from .api.types import (
    PacketMaskInstruction,
    MaskingRecipe, 
    PacketMaskingResult
)

__all__ = [
    "mask_pcap_with_instructions",
    "validate_masking_recipe", 
    "create_masking_recipe_from_dict",
    "PacketMaskInstruction",
    "MaskingRecipe",
    "PacketMaskingResult"
]
```

## 测试策略

### 1. 单元测试
- `BlindPacketMasker` 的核心逻辑测试
- 各种 `MaskSpec` 类型的处理测试
- 边界条件和错误处理测试

### 2. 集成测试  
- 使用真实PCAP样本的端到端测试
- 不同封装类型的处理验证
- 大文件性能测试

### 3. 兼容性测试
- 与现有掩码结果的对比验证
- 校验和自动修复验证
- 文件格式一致性验证

## 验证计划

### 阶段1: 基础功能验证（3天）
1. **简单场景测试**: 使用Plain IP包，验证基本掩码功能
2. **封装场景测试**: 使用VLAN、双层VLAN包验证封装处理
3. **掩码类型测试**: 验证MaskAfter、MaskRange、KeepAll各种类型

### 阶段2: 真实样本验证（2天） 
1. **TLS样本测试**: 使用`tests/data/tls-single/tls_sample.pcap`
2. **复杂场景测试**: 使用项目中的各种真实网络流量样本
3. **性能基准测试**: 与当前方案进行性能对比

### 阶段3: 兼容性验证（1天）
1. **结果一致性**: 确保新API产生的掩码结果与期望完全一致
2. **统计信息验证**: 验证处理统计的准确性
3. **错误处理测试**: 验证各种异常情况的处理

## 成功标准

1. **功能完整性**: 支持所有现有的掩码类型和场景
2. **性能要求**: 处理速度不低于当前方案的80%
3. **准确性**: 掩码位置和长度100%精确
4. **独立性**: 模块可以完全脱离PktMask主程序独立运行
5. **API稳定性**: 接口设计清晰，向后兼容性良好

## 风险评估

### 主要风险
1. **Scapy校验和处理**: 确保字节流重构后校验和正确更新
2. **包匹配准确性**: 时间戳+索引的匹配机制可靠性
3. **内存使用**: 大文件处理时的内存控制

### 缓解措施  
1. **充分测试**: 使用多种真实样本进行全面测试
2. **渐进式开发**: 先支持简单场景，逐步增加复杂度
3. **性能监控**: 在测试过程中持续监控性能指标

## 下一阶段接口

为Phase 2准备的标准接口：

```python
# Phase 2将调用的主要接口
result = mask_pcap_with_instructions(
    input_file="input.pcap",
    output_file="output.pcap", 
    masking_recipe=recipe_from_pyshark_analyzer
)
```

这个接口设计确保了两个阶段之间的清晰解耦，Phase 2只需要生成符合 `MaskingRecipe` 格式的指令即可。 