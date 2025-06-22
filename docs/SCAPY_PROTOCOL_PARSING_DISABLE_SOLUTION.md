# Scapy独立掩码处理器技术文档

## 1. 模块独立化设计目标

### 1.1 独立模块设计理念

将Scapy掩码功能重构为**完全独立的处理器**，可以脱离PktMask主程序单独运行：

```
标准化API接口
     ↓
独立输入: PCAP文件 + 序列号掩码表
     ↓
独立处理: 禁用协议解析 + 字节级掩码
     ↓
独立输出: 掩码后的PCAP文件
```

**独立性原则**：
- **零架构依赖**: 不依赖BaseStage、StageContext、事件系统
- **API驱动**: 提供标准化的函数调用接口
- **功能单一**: 纯粹的序列号匹配和字节级掩码
- **完全测试**: 可独立进行单元测试和集成测试
- **后续集成**: 通过适配器模式集成到主程序

### 1.2 模块优势

**开发优势**：
- ✅ 独立开发和调试
- ✅ 快速迭代和测试  
- ✅ 清晰的责任边界
- ✅ 高复用性

**维护优势**：
- ✅ 模块化的bug修复
- ✅ 独立的性能优化
- ✅ 简单的版本管理
- ✅ 明确的API契约

## 2. 核心技术挑战分析

### 2.1 Scapy协议自动解析问题

**问题根源**：Scapy默认行为与我们的需求冲突

**期望的数据流**：
```
PCAP读取 → TCP/Raw包结构 → 字节级掩码 → 输出PCAP
```

**实际的数据流**：
```
PCAP读取 → TCP/TLS包结构 → 无Raw层 → 掩码失败
         ↑
    Scapy自动协议解析
```

**具体症状**：
- `packet[Raw]` 抛出 `LayerNotFound` 异常
- TCP载荷被解析为TLS/HTTP等协议对象
- 无法进行直接的字节级掩码操作

### 2.2 Scapy内置绑定机制

**自动绑定规则**：
```python
# Scapy库内置绑定（不是我们的代码）
TCP端口443 → 自动解析为TLS协议
TCP端口80  → 自动解析为HTTP协议  
UDP端口53  → 自动解析为DNS协议
```

**绑定存储位置**：
```python
# 绑定信息存储在协议类中
TCP.payload_guess    # TCP协议的载荷猜测规则
UDP.payload_guess    # UDP协议的载荷猜测规则
TLS._overload_fields # TLS协议的字段重载
```

## 3. 独立API接口设计

### 3.1 核心API定义

```python
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging

@dataclass
class MaskEntry:
    """掩码条目定义"""
    stream_id: str                                  # TCP流ID (如: "TCP_1.2.3.4:443_5.6.7.8:1234_forward")
    sequence_start: int                             # 序列号起始位置
    sequence_end: int                               # 序列号结束位置
    mask_type: str                                  # 掩码类型: "mask_after", "mask_range", "keep_all"
    mask_params: Dict                               # 掩码参数 (如: {"keep_bytes": 5})
    preserve_headers: Optional[List[Tuple[int, int]]] = None  # 头部保留范围

@dataclass
class MaskingResult:
    """掩码处理结果"""
    success: bool                                   # 处理是否成功
    total_packets: int                              # 总数据包数
    modified_packets: int                           # 修改的数据包数
    bytes_masked: int                               # 掩码的字节数
    processing_time: float                          # 处理时间（秒）
    streams_processed: int                          # 处理的流数量
    error_message: Optional[str] = None             # 错误信息
    statistics: Optional[Dict] = None               # 详细统计信息

class SequenceMaskTable:
    """序列号掩码表"""
    
    def __init__(self):
        self.entries: List[MaskEntry] = []
    
    def add_entry(self, entry: MaskEntry) -> None:
        """添加掩码条目"""
        self.entries.append(entry)
    
    def find_matches(self, stream_id: str, sequence: int) -> List[MaskEntry]:
        """查找匹配指定流ID和序列号的掩码条目"""
        return [
            entry for entry in self.entries
            if entry.stream_id == stream_id 
            and entry.sequence_start <= sequence < entry.sequence_end
        ]
    
    def get_total_entries(self) -> int:
        """获取总条目数"""
        return len(self.entries)

class IndependentPcapMasker:
    """独立的PCAP掩码处理器
    
    这是一个完全独立的模块，可以脱离PktMask主程序运行。
    只需要提供PCAP文件和掩码表即可完成处理。
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化掩码处理器
        
        Args:
            config: 可选配置参数
        """
        self.config = self._merge_config(config or {})
        self.logger = self._setup_logger()
        self._original_bindings = {}
    
    def mask_pcap_with_sequences(
        self,
        input_pcap: str,
        mask_table: SequenceMaskTable,
        output_pcap: str
    ) -> MaskingResult:
        """主要API接口：对PCAP文件应用基于序列号的掩码
        
        这是模块的主要入口点，可以完全独立调用。
        
        Args:
            input_pcap: 输入PCAP文件路径（任意来源）
            mask_table: 序列号掩码表
            output_pcap: 输出PCAP文件路径
            
        Returns:
            MaskingResult: 处理结果和详细统计信息
            
        Example:
            >>> masker = IndependentPcapMasker()
            >>> mask_table = SequenceMaskTable()
            >>> mask_table.add_entry(MaskEntry(
            ...     stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            ...     sequence_start=1000,
            ...     sequence_end=2000,
            ...     mask_type="mask_after",
            ...     mask_params={"keep_bytes": 5}
            ... ))
            >>> result = masker.mask_pcap_with_sequences(
            ...     "input.pcap", mask_table, "output.pcap"
            ... )
            >>> print(f"成功处理 {result.modified_packets} 个数据包")
        """
```

### 3.2 配置参数定义

```python
DEFAULT_CONFIG = {
    # 掩码处理参数
    'mask_byte_value': 0x00,            # 掩码字节值
    'preserve_timestamps': True,         # 保持原始时间戳
    'recalculate_checksums': True,       # 重新计算校验和
    
    # 性能参数
    'batch_size': 1000,                 # 批处理大小
    'memory_limit_mb': 512,             # 内存限制（MB）
    
    # 验证参数
    'verify_tcp_sequences': True,        # 验证TCP序列号连续性
    'strict_stream_matching': True,      # 严格的流ID匹配
    
    # 日志参数
    'log_level': 'INFO',                # 日志级别
    'enable_debug_output': False,        # 启用调试输出
    
    # 协议处理参数
    'disable_protocol_parsing': True,    # 禁用协议解析（关键参数）
    'force_raw_payload': True           # 强制Raw载荷模式
}
```

### 3.3 使用示例

```python
# 完全独立使用示例
from pcap_masker import IndependentPcapMasker, SequenceMaskTable, MaskEntry

# 1. 创建掩码处理器
masker = IndependentPcapMasker(config={
    'mask_byte_value': 0x00,
    'log_level': 'DEBUG'
})

# 2. 构建掩码表
mask_table = SequenceMaskTable()

# 添加TLS流的掩码条目
mask_table.add_entry(MaskEntry(
    stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
    sequence_start=1000,
    sequence_end=5000,
    mask_type="mask_after",
    mask_params={"keep_bytes": 5}  # 保留前5字节（TLS头部）
))

# 添加HTTP流的掩码条目  
mask_table.add_entry(MaskEntry(
    stream_id="TCP_192.168.1.100:80_10.0.0.1:54322_forward",
    sequence_start=500,
    sequence_end=2500,
    mask_type="mask_range",
    mask_params={"ranges": [(100, 2000)]}  # 掩码特定范围
))

# 3. 执行掩码处理
result = masker.mask_pcap_with_sequences(
    input_pcap="/path/to/input.pcap",
    mask_table=mask_table,
    output_pcap="/path/to/output.pcap"
)

# 4. 检查结果
if result.success:
    print(f"✅ 处理成功:")
    print(f"   总数据包: {result.total_packets}")
    print(f"   修改数据包: {result.modified_packets}")
    print(f"   掩码字节数: {result.bytes_masked}")
    print(f"   处理时间: {result.processing_time:.2f}秒")
else:
    print(f"❌ 处理失败: {result.error_message}")
```

## 4. 协议解析禁用技术方案

### 4.1 核心实现策略

**技术路径**：临时禁用Scapy的协议绑定，强制所有TCP/UDP载荷保持为Raw格式

```python
class IndependentPcapMasker:
    
    def _disable_protocol_parsing(self) -> None:
        """禁用Scapy协议解析，保存原始绑定状态"""
        
        # 1. 保存原始TCP绑定状态
        if hasattr(TCP, 'payload_guess'):
            self._original_bindings['TCP'] = TCP.payload_guess.copy()
            
            # 移除常见端口的协议绑定
            TCP.payload_guess = [
                guess for guess in TCP.payload_guess
                if not self._is_application_protocol_binding(guess)
            ]
        
        # 2. 保存原始UDP绑定状态
        if hasattr(UDP, 'payload_guess'):
            self._original_bindings['UDP'] = UDP.payload_guess.copy()
            
            # 移除DNS等协议绑定
            UDP.payload_guess = [
                guess for guess in UDP.payload_guess
                if not self._is_application_protocol_binding(guess)
            ]
        
        # 3. 禁用特定协议的字段重载
        self._disable_protocol_overloads()
        
        self.logger.info("✅ 已禁用Scapy协议解析，所有载荷将保持为Raw格式")
    
    def _is_application_protocol_binding(self, guess) -> bool:
        """判断是否为应用层协议绑定"""
        try:
            # 检查常见的应用层端口
            if hasattr(guess, 'fld'):
                port = getattr(guess.fld, 'dport', None) or getattr(guess.fld, 'sport', None)
                if port in [80, 443, 53, 22, 21, 25, 110, 143, 993, 995, 8080, 8443]:
                    return True
            return False
        except:
            return False
    
    def _disable_protocol_overloads(self) -> None:
        """禁用协议字段重载"""
        try:
            # TLS协议重载禁用
            from scapy.layers.tls import TLS
            if hasattr(TLS, '_overload_fields'):
                self._original_bindings['TLS_overload'] = TLS._overload_fields.copy()
                TLS._overload_fields.clear()
            
            # HTTP协议重载禁用
            from scapy.layers.http import HTTP
            if hasattr(HTTP, '_overload_fields'):
                self._original_bindings['HTTP_overload'] = HTTP._overload_fields.copy()
                HTTP._overload_fields.clear()
                
        except ImportError:
            # 协议模块未安装，跳过
            pass
    
    def _restore_protocol_parsing(self) -> None:
        """恢复Scapy协议解析到原始状态"""
        
        try:
            # 恢复TCP绑定
            if 'TCP' in self._original_bindings:
                TCP.payload_guess = self._original_bindings['TCP']
            
            # 恢复UDP绑定
            if 'UDP' in self._original_bindings:
                UDP.payload_guess = self._original_bindings['UDP']
            
            # 恢复协议重载
            if 'TLS_overload' in self._original_bindings:
                from scapy.layers.tls import TLS
                TLS._overload_fields = self._original_bindings['TLS_overload']
            
            if 'HTTP_overload' in self._original_bindings:
                from scapy.layers.http import HTTP
                HTTP._overload_fields = self._original_bindings['HTTP_overload']
            
            self.logger.info("✅ 已恢复Scapy协议解析到原始状态")
            
        except Exception as e:
            self.logger.error(f"恢复协议绑定时发生错误: {e}")
        finally:
            self._original_bindings.clear()
```

### 4.2 安全的处理流程

```python
def mask_pcap_with_sequences(self, input_pcap: str, mask_table: SequenceMaskTable, output_pcap: str) -> MaskingResult:
    """安全的掩码处理流程，确保协议绑定状态的正确恢复"""
    
    start_time = time.time()
    result = MaskingResult(
        success=False,
        total_packets=0,
        modified_packets=0,
        bytes_masked=0,
        processing_time=0.0,
        streams_processed=0
    )
    
    # 线程安全锁
    with self._binding_lock:
        try:
            # 阶段1: 禁用协议解析
            self._disable_protocol_parsing()
            
            # 阶段2: 验证输入
            self._validate_inputs(input_pcap, mask_table, output_pcap)
            
            # 阶段3: 处理PCAP文件
            packets = self._read_pcap_safe(input_pcap)
            result.total_packets = len(packets)
            
            # 阶段4: 验证Raw层存在率
            raw_success_rate = self._verify_raw_layer_presence(packets)
            if raw_success_rate < 0.95:
                raise RuntimeError(f"协议解析禁用不完全，Raw层存在率仅{raw_success_rate:.1%}")
            
            # 阶段5: 应用掩码
            modified_packets, stats = self._apply_masks_to_packets(packets, mask_table)
            result.modified_packets = stats['modified_packets']
            result.bytes_masked = stats['bytes_masked']
            result.streams_processed = stats['streams_processed']
            
            # 阶段6: 写入输出文件
            self._write_pcap_safe(modified_packets, output_pcap)
            
            # 成功完成
            result.success = True
            result.processing_time = time.time() - start_time
            
        except Exception as e:
            result.error_message = str(e)
            self.logger.error(f"掩码处理失败: {e}")
            
        finally:
            # 阶段7: 确保协议解析状态恢复
            self._restore_protocol_parsing()
    
    return result
```

## 5. 简化的载荷处理逻辑

### 5.1 Raw层载荷提取

协议解析禁用后，载荷提取逻辑大幅简化：

```python
def _extract_tcp_payload(self, packet) -> bytes:
    """简化的TCP载荷提取（协议解析已禁用）"""
    if packet.haslayer(Raw):
        payload = bytes(packet[Raw].load)
        return payload
    else:
        # 协议解析禁用失败的指示
        self.logger.warning("⚠️ TCP数据包无Raw层，协议解析可能未完全禁用")
        return b''

def _extract_udp_payload(self, packet) -> bytes:
    """简化的UDP载荷提取（协议解析已禁用）"""
    if packet.haslayer(Raw):
        payload = bytes(packet[Raw].load)
        return payload
    else:
        self.logger.warning("⚠️ UDP数据包无Raw层，协议解析可能未完全禁用")
        return b''
```

### 5.2 核心掩码处理

```python
def _apply_masks_to_packets(self, packets: List, mask_table: SequenceMaskTable) -> Tuple[List, Dict]:
    """核心掩码应用逻辑"""
    
    modified_packets = []
    stats = {
        'modified_packets': 0,
        'bytes_masked': 0,
        'streams_processed': set(),
        'sequence_matches': 0
    }
    
    for i, packet in enumerate(packets, 1):
        try:
            # 提取流信息和序列号
            stream_info = self._extract_stream_info(packet)
            if not stream_info:
                modified_packets.append(packet)
                continue
            
            stream_id, sequence, payload = stream_info
            
            # 查找掩码条目
            mask_entries = mask_table.find_matches(stream_id, sequence)
            if not mask_entries:
                modified_packets.append(packet)
                continue
            
            # 应用掩码
            modified_payload = self._apply_sequence_masks(payload, mask_entries, sequence)
            if modified_payload != payload:
                # 更新数据包载荷
                self._update_packet_payload(packet, modified_payload)
                stats['modified_packets'] += 1
                stats['bytes_masked'] += len(payload) - len(modified_payload.replace(b'\x00', b''))
                stats['streams_processed'].add(stream_id)
            
            stats['sequence_matches'] += len(mask_entries)
            modified_packets.append(packet)
            
        except Exception as e:
            self.logger.error(f"处理数据包{i}时发生错误: {e}")
            modified_packets.append(packet)  # 保持原包
    
    stats['streams_processed'] = len(stats['streams_processed'])
    return modified_packets, stats
```

## 6. 后续集成方案

### 6.1 适配器模式集成

设计适配器将独立模块集成到PktMask主程序：

```python
class ScapyMaskerAdapter(BaseStage):
    """Scapy掩码处理器适配器
    
    将独立的IndependentPcapMasker集成到PktMask的Stage架构中
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("Scapy掩码处理器", config)
        self._masker = IndependentPcapMasker(self._convert_config(config))
    
    def execute(self, context: StageContext) -> ProcessorResult:
        """执行掩码处理（适配器模式）"""
        
        # 转换输入参数
        input_pcap = str(context.tshark_output)
        mask_table = context.mask_table
        output_pcap = str(context.output_file)
        
        # 调用独立模块
        masking_result = self._masker.mask_pcap_with_sequences(
            input_pcap, mask_table, output_pcap
        )
        
        # 转换输出结果
        return self._convert_result(masking_result, context)
    
    def _convert_config(self, stage_config: Dict) -> Dict:
        """将Stage配置转换为独立模块配置"""
        return {
            'mask_byte_value': stage_config.get('mask_byte_value', 0x00),
            'batch_size': stage_config.get('batch_size', 1000),
            'log_level': stage_config.get('log_level', 'INFO')
        }
    
    def _convert_result(self, masking_result: MaskingResult, context: StageContext) -> ProcessorResult:
        """将独立模块结果转换为Stage结果"""
        return ProcessorResult(
            success=masking_result.success,
            message=f"掩码处理完成：{masking_result.modified_packets}/{masking_result.total_packets} 个数据包被修改",
            data={
                'total_packets': masking_result.total_packets,
                'modified_packets': masking_result.modified_packets,
                'bytes_masked': masking_result.bytes_masked,
                'processing_time': masking_result.processing_time
            },
            error=masking_result.error_message
        )
```

### 6.2 渐进式集成策略

```python
# Phase 1: 独立开发和测试
# - 完全独立的IndependentPcapMasker
# - 独立的单元测试和集成测试
# - 性能基准测试

# Phase 2: 适配器集成
# - 创建ScapyMaskerAdapter
# - 保持现有Stage接口
# - 逐步替换原有实现

# Phase 3: 完全替换
# - 移除旧的ScapyRewriter
# - 更新所有相关测试
# - 更新文档和配置
```

## 7. 技术优势总结

### 7.1 独立性优势

**完全独立**：
- ✅ 零架构依赖：不依赖BaseStage、StageContext等
- ✅ API驱动：标准化的函数调用接口
- ✅ 独立测试：可单独进行完整测试
- ✅ 高复用性：其他项目可直接使用

**开发效率**：
- ✅ 快速迭代：独立开发和调试
- ✅ 清晰边界：明确的输入输出定义
- ✅ 简化调试：问题定位更容易
- ✅ 并行开发：可与其他模块并行开发

### 7.2 技术优势

**架构优化**：
- ✅ 单一职责：只负责序列号掩码处理
- ✅ 协议无关：基于序列号的通用机制
- ✅ 性能可控：无复杂的协议解析开销
- ✅ 可预测性：输入输出关系明确

**维护优势**：
- ✅ 模块化修复：问题影响范围有限
- ✅ 独立优化：性能调优不影响其他模块
- ✅ 版本管理：清晰的API版本控制
- ✅ 文档完整：API契约明确定义

### 7.3 预期效果

**问题解决**：
- ✅ TLS/HTTP载荷提取失败问题完全解决
- ✅ "修改了0个数据包"问题彻底消除
- ✅ 序列号匹配机制正常工作
- ✅ 字节级掩码精确执行

**质量提升**：
- ✅ 代码复杂度大幅降低
- ✅ 测试覆盖率显著提高
- ✅ 错误定位更加精确
- ✅ 性能监控更加准确

这个独立模块设计完全符合优秀软件工程的模块化原则，为PktMask项目提供了一个可靠、高效、易维护的掩码处理解决方案。 