# 独立PCAP掩码处理器API参考文档

## 概述

独立PCAP掩码处理器是一个完全独立的模块，用于对PCAP文件进行基于TCP序列号的精确字节级掩码处理。该模块不依赖PktMask主程序，可独立运行，提供高性能的掩码处理功能。

### 核心特性

- **完全独立**: 不依赖PktMask主程序架构
- **高性能**: 处理速度可达2000-5000 pps
- **严格一致性**: 除掩码字节外，输出文件与原文件完全一致
- **三种掩码类型**: 支持 mask_after、mask_range、keep_all
- **协议解析控制**: 可禁用Scapy协议解析以保持Raw层
- **格式支持**: 完整支持PCAP和PCAPNG格式

## 快速开始

```python
from pktmask.core.independent_pcap_masker import (
    IndependentPcapMasker, 
    SequenceMaskTable, 
    MaskEntry, 
    MaskingResult
)

# 创建处理器实例
masker = IndependentPcapMasker()

# 创建掩码表
mask_table = SequenceMaskTable()

# 添加掩码条目（TLS应用数据掩码示例）
mask_entry = MaskEntry(
    stream_id="TCP_192.168.1.1:443_10.0.0.1:1234_forward",
    sequence_start=1000,
    sequence_end=2000,
    mask_type="mask_after",
    mask_params={"keep_bytes": 5}  # 保留TLS头部5字节
)
mask_table.add_entry(mask_entry)

# 执行掩码处理
result = masker.mask_pcap_with_sequences(
    input_pcap="input.pcap",
    mask_table=mask_table,
    output_pcap="output.pcap"
)

# 检查结果
if result.success:
    print(f"成功处理 {result.total_packets} 个数据包")
    print(f"修改了 {result.modified_packets} 个数据包")
    print(f"掩码了 {result.bytes_masked} 个字节")
else:
    print(f"处理失败: {result.error_message}")
```

## API参考

### IndependentPcapMasker类

主要的PCAP掩码处理器类，提供核心的掩码处理功能。

#### 构造函数

```python
def __init__(self, config: Optional[Dict] = None)
```

**参数**:
- `config` (Optional[Dict]): 可选配置参数，会与默认配置合并

**默认配置**:
```python
{
    'mask_byte_value': 0x00,           # 掩码字节值
    'preserve_timestamps': True,       # 保持时间戳
    'recalculate_checksums': True,     # 重新计算校验和
    'supported_formats': ['.pcap', '.pcapng'],  # 支持的格式
    'strict_consistency_mode': True,   # 严格一致性模式
    'log_level': 'INFO',              # 日志级别
    'disable_protocol_parsing': True,  # 禁用协议解析
    'performance_mode': True,         # 性能模式
    'batch_size': 1000,               # 批处理大小
    'memory_limit_mb': 512,           # 内存限制
    'enable_raw_layer_validation': True,  # 启用Raw层验证
    'enable_consistency_check': True,     # 启用一致性检查
    'enable_detailed_logging': False,    # 启用详细日志
    'enable_progress_reporting': False,  # 启用进度报告
    'enable_statistics_collection': True,  # 启用统计收集
    'enable_memory_monitoring': True,     # 启用内存监控
    'enable_performance_profiling': False,  # 启用性能分析
    'enable_error_recovery': True,        # 启用错误恢复
    'enable_backup_creation': False,      # 启用备份创建
    'enable_multithread_processing': False,  # 启用多线程处理
    'thread_pool_size': 4,                # 线程池大小
    'chunk_size': 10000,                  # 块大小
    'compression_level': 6,               # 压缩级别
    'temp_dir': None,                     # 临时目录
    'cleanup_temp_files': True,           # 清理临时文件
    'verify_output_integrity': True       # 验证输出完整性
}
```

#### 主要方法

##### mask_pcap_with_sequences()

```python
def mask_pcap_with_sequences(
    self,
    input_pcap: str,
    mask_table: SequenceMaskTable,
    output_pcap: str
) -> MaskingResult:
```

对PCAP文件应用基于TCP序列号的掩码处理。

**参数**:
- `input_pcap` (str): 输入PCAP/PCAPNG文件路径
- `mask_table` (SequenceMaskTable): 包含掩码条目的序列号掩码表
- `output_pcap` (str): 输出PCAP/PCAPNG文件路径

**返回值**:
- `MaskingResult`: 详细的处理结果，包含成功状态、统计信息和错误信息

**异常**:
- `ValueError`: 输入参数无效
- `FileNotFoundError`: 输入文件不存在
- `PermissionError`: 文件权限不足
- `RuntimeError`: 处理过程中发生错误
- `MemoryError`: 内存不足
- `TimeoutError`: 处理超时

**示例**:
```python
masker = IndependentPcapMasker({
    'log_level': 'DEBUG',
    'enable_detailed_logging': True
})

result = masker.mask_pcap_with_sequences(
    input_pcap="/path/to/input.pcap",
    mask_table=mask_table,
    output_pcap="/path/to/output.pcap"
)
```

### SequenceMaskTable类

管理TCP序列号掩码表的数据结构，提供高效的序列号匹配功能。

#### 构造函数

```python
def __init__(self)
```

创建一个空的序列号掩码表。

#### 主要方法

##### add_entry()

```python
def add_entry(self, entry: MaskEntry) -> None
```

向掩码表添加一个掩码条目。

**参数**:
- `entry` (MaskEntry): 要添加的掩码条目

**异常**:
- `ValueError`: 掩码条目无效
- `TypeError`: 参数类型错误

##### find_matches()

```python
def find_matches(self, stream_id: str, sequence: int) -> List[MaskEntry]
```

查找与指定流ID和序列号匹配的掩码条目。

**参数**:
- `stream_id` (str): TCP流ID
- `sequence` (int): TCP序列号

**返回值**:
- `List[MaskEntry]`: 匹配的掩码条目列表

##### get_total_entries()

```python
def get_total_entries(self) -> int
```

获取掩码表中的总条目数。

**返回值**:
- `int`: 总条目数

##### clear()

```python
def clear(self) -> None
```

清空掩码表中的所有条目。

##### get_statistics()

```python
def get_statistics(self) -> Dict[str, Any]
```

获取掩码表的统计信息。

**返回值**:
- `Dict[str, Any]`: 包含统计信息的字典

## 数据结构

### MaskEntry

表示一个掩码条目的数据结构。

```python
@dataclass
class MaskEntry:
    stream_id: str                    # TCP流ID
    sequence_start: int               # 序列号起始位置（包含）
    sequence_end: int                 # 序列号结束位置（不包含）
    mask_type: str                    # 掩码类型
    mask_params: Dict[str, Any]       # 掩码参数
    preserve_headers: Optional[List[Tuple[int, int]]] = None  # 头部保留范围
```

**字段说明**:
- `stream_id`: TCP流标识符，格式为 "TCP_src_ip:port_dst_ip:port_direction"
- `sequence_start`: 掩码应用的起始序列号（包含）
- `sequence_end`: 掩码应用的结束序列号（不包含）
- `mask_type`: 掩码类型，支持 "mask_after"、"mask_range"、"keep_all"
- `mask_params`: 掩码参数字典，根据掩码类型不同而不同
- `preserve_headers`: 可选的头部保留范围列表

### MaskingResult

表示掩码处理结果的数据结构。

```python
@dataclass
class MaskingResult:
    success: bool                         # 处理是否成功
    total_packets: int                    # 总数据包数
    modified_packets: int                 # 修改的数据包数
    bytes_masked: int                     # 掩码的字节数
    processing_time: float                # 处理时间（秒）
    streams_processed: int                # 处理的TCP流数量
    error_message: Optional[str] = None   # 错误信息（失败时）
    statistics: Optional[Dict[str, Any]] = None  # 详细统计信息
```

**字段说明**:
- `success`: 布尔值，表示处理是否成功
- `total_packets`: 输入文件中的总数据包数
- `modified_packets`: 被修改的数据包数量
- `bytes_masked`: 被掩码的总字节数
- `processing_time`: 处理耗时（秒）
- `streams_processed`: 处理的TCP流数量
- `error_message`: 失败时的错误信息
- `statistics**: 详细统计信息字典

## 掩码类型详解

### 1. mask_after - 保留前N字节

保留载荷前N个字节，将其余字节置零。常用于保留协议头部。

**参数**:
- `keep_bytes` (int): 要保留的字节数

**示例**:
```python
# TLS应用数据掩码 - 保留TLS头部5字节
MaskEntry(
    stream_id="TCP_192.168.1.1:443_10.0.0.1:1234_forward",
    sequence_start=1000,
    sequence_end=2000,
    mask_type="mask_after",
    mask_params={"keep_bytes": 5}
)
```

**行为**:
- 原始载荷: `[0x17, 0x03, 0x03, 0x00, 0x20, 0x41, 0x42, 0x43, ...]`
- 掩码后载荷: `[0x17, 0x03, 0x03, 0x00, 0x20, 0x00, 0x00, 0x00, ...]`

### 2. mask_range - 掩码指定范围

掩码指定的字节范围，可以指定多个不连续的范围。

**参数**:
- `ranges` (List[Tuple[int, int]]): 要掩码的字节范围列表，每个元组表示(起始位置, 结束位置)

**示例**:
```python
# HTTP POST数据掩码 - 掩码敏感数据字段
MaskEntry(
    stream_id="TCP_192.168.1.1:80_10.0.0.1:1234_forward",
    sequence_start=500,
    sequence_end=1500,
    mask_type="mask_range",
    mask_params={"ranges": [(100, 200), (300, 400)]}
)
```

**行为**:
- 保留0-99字节和200-299字节
- 掩码100-199字节和300-399字节
- 保留400字节之后的内容

### 3. keep_all - 保留所有字节

保留所有字节，不进行掩码处理。主要用于调试和测试。

**参数**:
- 无参数

**示例**:
```python
# 调试用 - 保留所有数据
MaskEntry(
    stream_id="TCP_192.168.1.1:22_10.0.0.1:1234_forward",
    sequence_start=0,
    sequence_end=10000,
    mask_type="keep_all",
    mask_params={}
)
```

## 使用场景示例

### 场景1: TLS流量掩码

```python
# 处理TLS流量，保留TLS头部，掩码应用数据
def mask_tls_application_data(input_pcap: str, output_pcap: str):
    masker = IndependentPcapMasker()
    mask_table = SequenceMaskTable()
    
    # 添加TLS Application Data掩码条目
    tls_entry = MaskEntry(
        stream_id="TCP_192.168.1.1:443_10.0.0.1:1234_forward",
        sequence_start=1000,
        sequence_end=2000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 5}  # 保留TLS头部
    )
    mask_table.add_entry(tls_entry)
    
    result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
    return result
```

### 场景2: HTTP POST数据掩码

```python
# 处理HTTP流量，掩码POST数据中的敏感信息
def mask_http_post_data(input_pcap: str, output_pcap: str):
    masker = IndependentPcapMasker()
    mask_table = SequenceMaskTable()
    
    # 添加HTTP POST数据掩码条目
    http_entry = MaskEntry(
        stream_id="TCP_192.168.1.1:80_10.0.0.1:1234_forward",
        sequence_start=500,
        sequence_end=1500,
        mask_type="mask_range",
        mask_params={"ranges": [(200, 800)]}  # 掩码POST数据部分
    )
    mask_table.add_entry(http_entry)
    
    result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
    return result
```

### 场景3: 批量处理

```python
# 批量处理多个PCAP文件
def batch_mask_pcap_files(input_files: List[str], mask_table: SequenceMaskTable, output_dir: str):
    masker = IndependentPcapMasker({
        'enable_progress_reporting': True,
        'log_level': 'INFO'
    })
    
    results = []
    for input_file in input_files:
        output_file = os.path.join(output_dir, f"masked_{os.path.basename(input_file)}")
        result = masker.mask_pcap_with_sequences(input_file, mask_table, output_file)
        results.append((input_file, result))
    
    return results
```

## 错误处理

### 异常类型

#### ValueError
参数验证失败时抛出。

**常见原因**:
- 文件路径为空或无效
- 掩码表为空
- 掩码条目参数无效

**处理建议**:
```python
try:
    result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
except ValueError as e:
    print(f"参数错误: {e}")
    # 检查输入参数是否正确
```

#### FileNotFoundError
输入文件不存在时抛出。

**处理建议**:
```python
try:
    result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
except FileNotFoundError as e:
    print(f"文件不存在: {e}")
    # 检查文件路径是否正确
```

#### PermissionError
文件权限不足时抛出。

**处理建议**:
```python
try:
    result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
except PermissionError as e:
    print(f"权限不足: {e}")
    # 检查文件权限或运行权限
```

#### RuntimeError
处理过程中发生错误时抛出。

**处理建议**:
```python
try:
    result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
except RuntimeError as e:
    print(f"处理错误: {e}")
    # 检查文件格式或内容是否正确
```

### 错误恢复

```python
def robust_mask_processing(input_pcap: str, mask_table: SequenceMaskTable, output_pcap: str, max_retries: int = 3):
    masker = IndependentPcapMasker({'enable_error_recovery': True})
    
    for attempt in range(max_retries):
        try:
            result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
            if result.success:
                return result
            else:
                print(f"处理失败 (尝试 {attempt + 1}): {result.error_message}")
        except Exception as e:
            print(f"异常发生 (尝试 {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise
    
    return None
```

## 性能优化

### 配置优化

```python
# 高性能配置
high_performance_config = {
    'performance_mode': True,
    'batch_size': 2000,
    'disable_protocol_parsing': True,
    'enable_detailed_logging': False,
    'enable_consistency_check': False,
    'enable_memory_monitoring': False
}

masker = IndependentPcapMasker(high_performance_config)
```

### 内存优化

```python
# 内存优化配置
memory_optimized_config = {
    'memory_limit_mb': 256,
    'batch_size': 500,
    'cleanup_temp_files': True,
    'enable_memory_monitoring': True
}

masker = IndependentPcapMasker(memory_optimized_config)
```

### 并发处理

```python
# 并发处理配置
concurrent_config = {
    'enable_multithread_processing': True,
    'thread_pool_size': 8,
    'chunk_size': 5000
}

masker = IndependentPcapMasker(concurrent_config)
```

## 性能指标

### 处理速度

- **小文件** (< 1MB): 2000-3000 pps
- **中等文件** (1-10MB): 3000-5000 pps  
- **大文件** (> 10MB): 1000-2000 pps

### 内存使用

- **基础内存**: 10-20MB
- **处理期间**: 通常 < 文件大小 × 1.5
- **峰值内存**: 可通过配置限制

### 性能监控

```python
# 启用性能监控
performance_config = {
    'enable_performance_profiling': True,
    'enable_statistics_collection': True,
    'enable_progress_reporting': True
}

masker = IndependentPcapMasker(performance_config)
result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)

# 查看性能统计
if result.statistics:
    print(f"处理速度: {result.statistics.get('packets_per_second', 0):.2f} pps")
    print(f"内存使用: {result.statistics.get('peak_memory_mb', 0):.2f} MB")
```

## 最佳实践

### 1. 掩码表设计

```python
# 合理设计掩码表，避免重叠条目
def create_optimized_mask_table():
    mask_table = SequenceMaskTable()
    
    # 按流ID分组管理
    tls_streams = ["TCP_192.168.1.1:443_10.0.0.1:1234_forward"]
    http_streams = ["TCP_192.168.1.1:80_10.0.0.1:1234_forward"]
    
    # TLS流掩码
    for stream_id in tls_streams:
        mask_table.add_entry(MaskEntry(
            stream_id=stream_id,
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        ))
    
    return mask_table
```

### 2. 配置管理

```python
# 根据使用场景选择合适的配置
def get_config_for_scenario(scenario: str) -> Dict:
    configs = {
        'development': {
            'log_level': 'DEBUG',
            'enable_detailed_logging': True,
            'enable_consistency_check': True
        },
        'production': {
            'log_level': 'INFO',
            'performance_mode': True,
            'enable_detailed_logging': False
        },
        'testing': {
            'log_level': 'WARNING',
            'enable_error_recovery': True,
            'enable_consistency_check': True
        }
    }
    return configs.get(scenario, {})
```

### 3. 错误处理

```python
# 完整的错误处理流程
def safe_mask_processing(input_pcap: str, mask_table: SequenceMaskTable, output_pcap: str):
    try:
        # 预验证
        if not os.path.exists(input_pcap):
            raise FileNotFoundError(f"输入文件不存在: {input_pcap}")
        
        if mask_table.get_total_entries() == 0:
            raise ValueError("掩码表为空")
        
        # 执行处理
        masker = IndependentPcapMasker()
        result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
        
        # 结果验证
        if not result.success:
            raise RuntimeError(f"处理失败: {result.error_message}")
        
        return result
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        # 清理临时文件
        if os.path.exists(output_pcap):
            os.remove(output_pcap)
        raise
```

## 故障排查

### 常见问题

#### 1. 处理速度慢

**可能原因**:
- 启用了详细日志
- 启用了一致性检查
- 批处理大小过小

**解决方案**:
```python
# 优化配置
optimized_config = {
    'performance_mode': True,
    'batch_size': 2000,
    'enable_detailed_logging': False,
    'enable_consistency_check': False
}
```

#### 2. 内存使用过高

**可能原因**:
- 文件过大
- 批处理大小过大
- 内存泄漏

**解决方案**:
```python
# 内存优化配置
memory_config = {
    'memory_limit_mb': 512,
    'batch_size': 500,
    'cleanup_temp_files': True
}
```

#### 3. 掩码不生效

**可能原因**:
- 流ID不匹配
- 序列号范围错误
- 掩码类型参数错误

**解决方案**:
```python
# 启用详细日志进行调试
debug_config = {
    'log_level': 'DEBUG',
    'enable_detailed_logging': True
}
```

### 调试工具

```python
# 调试模式处理
def debug_mask_processing(input_pcap: str, mask_table: SequenceMaskTable, output_pcap: str):
    debug_config = {
        'log_level': 'DEBUG',
        'enable_detailed_logging': True,
        'enable_consistency_check': True,
        'enable_statistics_collection': True
    }
    
    masker = IndependentPcapMasker(debug_config)
    result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
    
    # 输出详细信息
    print(f"处理结果: {result.success}")
    print(f"总数据包: {result.total_packets}")
    print(f"修改数据包: {result.modified_packets}")
    print(f"掩码字节数: {result.bytes_masked}")
    print(f"处理时间: {result.processing_time:.3f}s")
    
    if result.statistics:
        print("详细统计:")
        for key, value in result.statistics.items():
            print(f"  {key}: {value}")
    
    return result
```

## 版本信息

- **当前版本**: 1.0.0
- **Python兼容性**: 3.8+
- **依赖库**: scapy >= 2.4.0
- **支持平台**: Windows, macOS, Linux

## 支持和联系

如有问题或建议，请通过以下方式联系:

- **项目仓库**: [GitHub链接]
- **问题报告**: [Issue链接]
- **技术文档**: [文档链接]
- **社区讨论**: [社区链接]

---

*本文档最后更新: 2025-06-22* 