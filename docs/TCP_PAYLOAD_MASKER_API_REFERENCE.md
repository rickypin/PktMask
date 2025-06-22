# TCP Payload Masker API 参考文档

版本: 2.0.0  
更新日期: 2025-06-22

## 概述

TCP Payload Masker 是专用于TCP载荷的保留范围掩码处理器。采用隐私优先设计理念：默认掩码所有TCP载荷，只保留指定的协议头部范围。

### 核心理念

- **隐私优先**: 默认掩码所有载荷，最大化隐私保护
- **保留范围**: 记录要保留的字节范围，其余全部掩码为0x00
- **TCP专用**: 只处理TCP协议，提供更高的专业性和性能
- **协议感知**: 支持TLS/HTTP/SSH等协议头部自动保留

## 核心类和接口

### 1. TcpPayloadMasker

主要的TCP载荷掩码处理器类。

```python
from pktmask.core.tcp_payload_masker import TcpPayloadMasker

masker = TcpPayloadMasker(config=None)
```

#### 构造函数

```python
def __init__(self, config: Optional[Dict[str, Any]] = None)
```

**参数:**
- `config` (可选): 配置字典，包含掩码处理的各种设置

**配置选项:**
```python
{
    'mask_byte_value': 0x00,                    # 掩码字节值
    'strict_mode': False,                       # 严格模式
    'performance_optimization_enabled': True,   # 性能优化
    'auto_optimize_keep_range_table': True,    # 自动优化保留范围表
    'enable_batch_processing': True,           # 启用批量处理
    'cache_query_results': True,               # 缓存查询结果
    'optimize_memory_usage': True              # 优化内存使用
}
```

#### 主要方法

##### mask_tcp_payloads_with_keep_ranges()

对PCAP文件应用基于保留范围的TCP载荷掩码。

```python
def mask_tcp_payloads_with_keep_ranges(
    self,
    input_pcap: str,
    keep_range_table: TcpKeepRangeTable,
    output_pcap: str
) -> TcpMaskingResult
```

**参数:**
- `input_pcap`: 输入PCAP文件路径
- `keep_range_table`: TCP保留范围表
- `output_pcap`: 输出PCAP文件路径

**返回:** `TcpMaskingResult` 处理结果对象

**示例:**
```python
from pktmask.core.tcp_payload_masker import (
    TcpPayloadMasker, TcpKeepRangeTable, TcpKeepRangeEntry
)

# 创建掩码器
masker = TcpPayloadMasker()

# 创建保留范围表
table = TcpKeepRangeTable()

# 添加TLS连接的保留范围
tls_entry = TcpKeepRangeEntry(
    stream_id="TCP_192.168.1.10:443_10.0.0.5:12345_forward",
    sequence_start=1000,
    sequence_end=5000,
    keep_ranges=[(0, 5), (22, 47)],  # TLS记录头 + 握手消息
    protocol_hint="TLS"
)
table.add_keep_range_entry(tls_entry)

# 执行掩码处理
result = masker.mask_tcp_payloads_with_keep_ranges(
    "input.pcap", table, "output.pcap"
)

print(f"处理结果: {result.get_summary()}")
```

##### mask_tcp_payloads_batch()

批量处理多个TCP载荷掩码任务。

```python
def mask_tcp_payloads_batch(
    self,
    batch_jobs: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[TcpMaskingResult]
```

**参数:**
- `batch_jobs`: 批量任务列表
- `progress_callback`: 进度回调函数 (当前任务, 总任务, 状态信息)

**批量任务格式:**
```python
batch_jobs = [
    {
        "input_pcap": "input1.pcap",
        "keep_range_table": table1,
        "output_pcap": "output1.pcap"
    },
    {
        "input_pcap": "input2.pcap",
        "keep_range_table": table2,
        "output_pcap": "output2.pcap"
    }
]
```

**示例:**
```python
def progress_callback(current, total, status):
    print(f"进度: {current}/{total} - {status}")

results = masker.mask_tcp_payloads_batch(batch_jobs, progress_callback)
```

##### optimize_keep_range_table()

优化TCP保留范围表以提升处理性能。

```python
def optimize_keep_range_table(self, keep_range_table: TcpKeepRangeTable) -> TcpKeepRangeTable
```

执行以下优化：
1. 合并重叠的保留范围
2. 排序条目以提升查找效率
3. 预计算常用查询结果
4. 优化内存布局

##### estimate_processing_time()

估算处理时间（用于批量处理规划）。

```python
def estimate_processing_time(
    self,
    input_pcap: str,
    keep_range_table: TcpKeepRangeTable
) -> Dict[str, float]
```

**返回:**
```python
{
    'estimated_time': 1.5,      # 预估处理时间（秒）
    'confidence': 0.8,          # 估算置信度（0-1）
    'file_size_mb': 5.2,        # 文件大小（MB）
    'complexity_score': 2.1     # 复杂度评分
}
```

##### get_performance_metrics()

获取详细性能指标。

```python
def get_performance_metrics(self) -> Dict[str, Any]
```

**返回:**
```python
{
    'processing_speed': {
        'packets_per_second': 1500.0,
        'files_per_hour': 120.0
    },
    'throughput': {
        'mbps': 25.6,
        'estimated_data_processed_mb': 128.0
    },
    'efficiency_metrics': {
        'modification_rate_percent': 75.0,
        'avg_streams_per_file': 8.5,
        'avg_processing_time_per_file': 2.3
    },
    'resource_usage': {
        'total_files_processed': 50,
        'total_processing_time': 115.0,
        'avg_bytes_masked_per_stream': 5120,
        'avg_bytes_kept_per_stream': 512
    }
}
```

##### enable_performance_optimization()

启用/禁用性能优化模式。

```python
def enable_performance_optimization(self, enable: bool = True) -> None
```

##### cleanup_resources()

清理资源和临时缓存。

```python
def cleanup_resources(self) -> None
```

### 2. TcpKeepRangeEntry

TCP保留范围条目，定义对特定TCP流的特定序列号范围内需要保留的字节范围。

```python
from pktmask.core.tcp_payload_masker import TcpKeepRangeEntry

entry = TcpKeepRangeEntry(
    stream_id="TCP_src:port_dst:port_direction",
    sequence_start=1000,
    sequence_end=2000,
    keep_ranges=[(0, 5), (10, 15)],
    protocol_hint="TLS"
)
```

#### 属性

- `stream_id` (str): TCP流ID，格式为 "TCP_src:port_dst:port_direction"
- `sequence_start` (int): 序列号起始位置（包含）
- `sequence_end` (int): 序列号结束位置（不包含）
- `keep_ranges` (List[Tuple[int, int]]): 需要保留的字节范围列表
- `protocol_hint` (Optional[str]): 协议提示，如 "TLS", "HTTP", "SSH"

#### 方法

##### covers_sequence()

检查该条目是否覆盖指定序列号。

```python
def covers_sequence(self, sequence: int) -> bool
```

##### get_keep_ranges_for_offset()

获取相对于指定偏移量的保留范围。

```python
def get_keep_ranges_for_offset(self, offset: int) -> List[Tuple[int, int]]
```

##### get_total_keep_bytes()

计算总保留字节数。

```python
def get_total_keep_bytes(self) -> int
```

##### validate()

验证条目的有效性。

```python
def validate(self) -> bool
```

##### merge_keep_ranges()

合并重叠的保留范围，返回新的条目。

```python
def merge_keep_ranges(self) -> 'TcpKeepRangeEntry'
```

##### get_keep_range_summary()

获取保留范围摘要信息。

```python
def get_keep_range_summary(self) -> Dict[str, Any]
```

**返回:**
```python
{
    'stream_id': 'TCP_1.2.3.4:443_5.6.7.8:1234_forward',
    'sequence_range': (1000, 2000),
    'sequence_length': 1000,
    'keep_ranges': [(0, 5), (10, 15)],
    'range_count': 2,
    'total_keep_bytes': 10,
    'keep_density': 0.01,    # 保留字节数 / 序列号范围长度
    'protocol_hint': 'TLS',
    'is_valid': True
}
```

### 3. TcpKeepRangeTable

TCP保留范围掩码表，高效管理和查询基于TCP序列号的保留范围条目。

```python
from pktmask.core.tcp_payload_masker import TcpKeepRangeTable

table = TcpKeepRangeTable()
```

#### 主要方法

##### add_keep_range_entry()

添加TCP保留范围条目。

```python
def add_keep_range_entry(self, entry: TcpKeepRangeEntry) -> None
```

##### find_keep_ranges_for_sequence()

查找指定TCP序列号位置的保留范围。

```python
def find_keep_ranges_for_sequence(self, stream_id: str, sequence: int) -> List[Tuple[int, int]]
```

##### find_entries_for_stream()

查找指定TCP流的所有保留范围条目。

```python
def find_entries_for_stream(self, stream_id: str) -> List[TcpKeepRangeEntry]
```

##### find_entries_for_sequence_range()

查找与指定序列号范围有重叠的保留范围条目。

```python
def find_entries_for_sequence_range(
    self, stream_id: str, start_seq: int, end_seq: int
) -> List[TcpKeepRangeEntry]
```

##### get_total_entries()

获取总条目数。

```python
def get_total_entries(self) -> int
```

##### get_streams_count()

获取TCP流的数量。

```python
def get_streams_count(self) -> int
```

##### get_all_stream_ids()

获取所有TCP流ID。

```python
def get_all_stream_ids(self) -> List[str]
```

##### validate_consistency()

验证保留范围表的一致性。

```python
def validate_consistency(self) -> List[str]
```

返回发现的问题列表，空列表表示无问题。

##### get_statistics()

获取保留范围表统计信息。

```python
def get_statistics(self) -> Dict[str, Any]
```

**返回:**
```python
{
    "total_entries": 25,
    "tcp_streams_count": 8,
    "entries_per_stream": {...},
    "keep_ranges_per_stream": {...},
    "sequence_range_coverage": {...},
    "protocol_hint_distribution": {
        "TLS": 15,
        "HTTP": 8,
        "SSH": 2
    }
}
```

##### export_to_dict() / import_from_dict()

导出/导入保留范围表为字典格式。

```python
def export_to_dict(self) -> Dict[str, Any]
def import_from_dict(self, data: Dict[str, Any]) -> None
```

**导出格式:**
```python
{
    'version': '2.0.0',
    'type': 'TcpKeepRangeTable',
    'entries': [...],
    'statistics': {...}
}
```

##### clear()

清空所有保留范围条目。

```python
def clear(self) -> None
```

##### remove_stream()

移除指定TCP流的所有保留范围条目。

```python
def remove_stream(self, stream_id: str) -> int
```

返回移除的条目数量。

### 4. TcpMaskingResult

TCP掩码处理结果，包含TCP载荷掩码处理过程的详细统计信息和结果。

```python
from pktmask.core.tcp_payload_masker import TcpMaskingResult

result = TcpMaskingResult(
    success=True,
    total_packets=1000,
    modified_packets=750,
    bytes_masked=50000,
    bytes_kept=10000,
    tcp_streams_processed=25,
    processing_time=5.5
)
```

#### 属性

- `success` (bool): 处理是否成功
- `total_packets` (int): 总数据包数
- `modified_packets` (int): 修改的数据包数
- `bytes_masked` (int): 掩码的字节数
- `bytes_kept` (int): 保留的字节数
- `tcp_streams_processed` (int): 处理的TCP流数量
- `processing_time` (float): 处理时间（秒）
- `error_message` (Optional[str]): 错误信息（失败时）
- `keep_range_statistics` (Dict[str, int]): 保留范围统计

#### 方法

##### get_modification_rate()

获取数据包修改率。

```python
def get_modification_rate(self) -> float
```

##### get_processing_speed()

获取处理速度（包/秒）。

```python
def get_processing_speed(self) -> float
```

##### get_masking_rate()

获取掩码字节比例。

```python
def get_masking_rate(self) -> float
```

##### get_keep_rate()

获取保留字节比例。

```python
def get_keep_rate(self) -> float
```

##### add_keep_range_statistic()

添加保留范围统计信息。

```python
def add_keep_range_statistic(self, key: str, value: int) -> None
```

##### get_summary()

获取结果摘要。

```python
def get_summary(self) -> str
```

**示例输出:**
```
TCP载荷掩码处理成功: 750/1000 个数据包被修改, 掩码字节: 50000, 保留字节: 10000 (总计 60000 字节), TCP流: 25, 处理时间: 5.50秒, 处理速度: 181.8 pps
```

## 异常类

### TcpPayloadMaskerError

TCP载荷掩码处理器基础异常类。

```python
from pktmask.core.tcp_payload_masker import TcpPayloadMaskerError
```

### ProtocolBindingError

协议绑定控制相关错误。

### FileConsistencyError

文件一致性验证错误。

### TcpKeepRangeApplicationError

TCP保留范围应用错误。

### ValidationError

输入验证错误。

### ConfigurationError

配置错误。

## 使用模式和最佳实践

### 1. 基本使用模式

```python
from pktmask.core.tcp_payload_masker import (
    TcpPayloadMasker, TcpKeepRangeTable, TcpKeepRangeEntry
)

# 1. 创建掩码器
masker = TcpPayloadMasker()

# 2. 创建保留范围表
table = TcpKeepRangeTable()

# 3. 添加保留范围条目
entry = TcpKeepRangeEntry(
    stream_id="TCP_192.168.1.10:443_10.0.0.5:12345_forward",
    sequence_start=1000,
    sequence_end=5000,
    keep_ranges=[(0, 5), (22, 47)],
    protocol_hint="TLS"
)
table.add_keep_range_entry(entry)

# 4. 执行掩码处理
result = masker.mask_tcp_payloads_with_keep_ranges(
    "input.pcap", table, "output.pcap"
)

# 5. 检查结果
if result.success:
    print(f"处理成功: {result.get_summary()}")
else:
    print(f"处理失败: {result.error_message}")
```

### 2. 批量处理模式

```python
# 准备批量任务
batch_jobs = []
for i in range(10):
    table = create_keep_range_table_for_file(f"input_{i}.pcap")
    batch_jobs.append({
        "input_pcap": f"input_{i}.pcap",
        "keep_range_table": table,
        "output_pcap": f"output_{i}.pcap"
    })

# 定义进度回调
def progress_callback(current, total, status):
    print(f"进度: {current}/{total} - {status}")

# 执行批量处理
results = masker.mask_tcp_payloads_batch(batch_jobs, progress_callback)

# 分析结果
successful = [r for r in results if r.success]
print(f"成功处理: {len(successful)}/{len(results)} 个文件")
```

### 3. 性能优化模式

```python
# 启用性能优化
masker.enable_performance_optimization(True)

# 优化保留范围表
optimized_table = masker.optimize_keep_range_table(table)

# 估算处理时间
estimation = masker.estimate_processing_time("large_file.pcap", optimized_table)
print(f"预估处理时间: {estimation['estimated_time']:.2f}秒")

# 执行处理
result = masker.mask_tcp_payloads_with_keep_ranges(
    "large_file.pcap", optimized_table, "output.pcap"
)

# 获取性能指标
metrics = masker.get_performance_metrics()
print(f"处理速度: {metrics['processing_speed']['packets_per_second']:.0f} pps")

# 清理资源
masker.cleanup_resources()
```

### 4. 协议特定配置

#### TLS协议保留范围

```python
def create_tls_keep_ranges():
    """创建TLS协议的标准保留范围"""
    return [
        (0, 5),    # TLS记录头部 (Type + Version + Length)
        (5, 9),    # 握手消息头部  
        (9, 13),   # 握手消息长度
        (13, 45),  # Client Hello 固定部分
        (45, 77),  # Random 字段
        (77, 78),  # Session ID 长度
        # 根据需要添加更多范围...
    ]

tls_entry = TcpKeepRangeEntry(
    stream_id="TCP_192.168.1.10:443_10.0.0.5:12345_forward",
    sequence_start=1000,
    sequence_end=5000,
    keep_ranges=create_tls_keep_ranges(),
    protocol_hint="TLS"
)
```

#### HTTP协议保留范围

```python
def create_http_keep_ranges():
    """创建HTTP协议的标准保留范围"""
    return [
        (0, 50),   # HTTP请求行和主要头部
        (50, 100), # 其他头部字段
        # Cookie和认证信息通常不保留
    ]

http_entry = TcpKeepRangeEntry(
    stream_id="TCP_192.168.1.10:80_10.0.0.5:12345_forward",
    sequence_start=2000,
    sequence_end=4000,
    keep_ranges=create_http_keep_ranges(),
    protocol_hint="HTTP"
)
```

### 5. 错误处理最佳实践

```python
from pktmask.core.tcp_payload_masker import (
    TcpPayloadMaskerError, ValidationError, FileConsistencyError
)

try:
    # 验证输入
    if not table.get_total_entries():
        raise ValidationError("保留范围表为空")
    
    # 检查一致性
    issues = table.validate_consistency()
    if issues:
        logger.warning(f"保留范围表一致性问题: {issues}")
    
    # 执行处理
    result = masker.mask_tcp_payloads_with_keep_ranges(
        input_pcap, table, output_pcap
    )
    
    if not result.success:
        raise TcpPayloadMaskerError(result.error_message)

except ValidationError as e:
    logger.error(f"输入验证失败: {e}")
except FileConsistencyError as e:
    logger.error(f"文件一致性错误: {e}")
except TcpPayloadMaskerError as e:
    logger.error(f"掩码处理失败: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}")
```

## 迁移指南

### 从Independent PCAP Masker迁移

#### 类名映射

| 旧类名 | 新类名 |
|--------|--------|
| `IndependentPcapMasker` | `TcpPayloadMasker` |
| `MaskEntry` | `TcpKeepRangeEntry` |
| `MaskingResult` | `TcpMaskingResult` |
| `SequenceMaskTable` | `TcpKeepRangeTable` |
| `IndependentMaskerError` | `TcpPayloadMaskerError` |

#### 方法名映射

| 旧方法名 | 新方法名 |
|----------|----------|
| `mask_pcap_with_sequences()` | `mask_tcp_payloads_with_keep_ranges()` |
| `add_mask_entry()` | `add_keep_range_entry()` |

#### 参数名映射

| 旧参数名 | 新参数名 |
|----------|----------|
| `mask_table` | `keep_range_table` |
| `mask_entry` | `keep_range_entry` |
| `mask_type` | `protocol_hint` |
| `mask_params` | `keep_ranges` |

#### 概念转换

1. **从掩码类型到协议提示**:
   - `"mask_after"` → `"TLS"`
   - `"mask_range"` → `"HTTP"` 
   - `"keep_all"` → `"UNKNOWN"`

2. **从掩码参数到保留范围**:
   - 旧: `mask_params=[100, 200]` (掩码从位置100到200)
   - 新: `keep_ranges=[(0, 100), (200, 300)]` (保留0-100和200-300，掩码100-200)

3. **隐私优先理念**:
   - 旧: 默认保留所有，指定要掩码的部分
   - 新: 默认掩码所有，指定要保留的部分

### 使用迁移工具

```bash
# 自动迁移整个项目
python scripts/migrate_to_tcp_payload_masker.py --directory /path/to/project --recursive

# 预览迁移效果（不实际修改文件）
python scripts/migrate_to_tcp_payload_masker.py --directory /path/to/project --dry-run

# 生成迁移报告
python scripts/migrate_to_tcp_payload_masker.py --directory /path/to/project --report migration_report.md

# 创建兼容性包装器（临时解决方案）
python scripts/migrate_to_tcp_payload_masker.py --create-wrapper compatibility_wrapper.py
```

## 性能调优

### 1. 保留范围表优化

```python
# 优化前
original_count = table.get_total_entries()

# 执行优化
optimized_table = masker.optimize_keep_range_table(table)

# 查看优化效果
optimized_count = optimized_table.get_total_entries()
reduction = (original_count - optimized_count) / original_count * 100
print(f"条目减少: {reduction:.1f}%")
```

### 2. 批量处理优化

```python
# 启用批量处理优化
masker.enable_performance_optimization(True)

# 按文件大小分组处理
small_files = [job for job in batch_jobs if get_file_size(job['input_pcap']) < 10*1024*1024]
large_files = [job for job in batch_jobs if get_file_size(job['input_pcap']) >= 10*1024*1024]

# 分别处理不同大小的文件
small_results = masker.mask_tcp_payloads_batch(small_files)
large_results = masker.mask_tcp_payloads_batch(large_files)
```

### 3. 内存管理

```python
# 长时间运行时定期清理资源
for i, batch in enumerate(file_batches):
    results = masker.mask_tcp_payloads_batch(batch)
    
    # 每处理10个批次清理一次资源
    if (i + 1) % 10 == 0:
        masker.cleanup_resources()
```

### 4. 性能监控

```python
# 定期获取性能指标
def monitor_performance():
    metrics = masker.get_performance_metrics()
    
    # 检查处理速度
    pps = metrics['processing_speed']['packets_per_second']
    if pps < 1000:  # 阈值
        logger.warning(f"处理速度较慢: {pps} pps")
    
    # 检查资源使用
    total_time = metrics['resource_usage']['total_processing_time']
    if total_time > 3600:  # 1小时
        logger.info("建议清理资源")
        masker.cleanup_resources()

# 在批量处理中监控
for batch in file_batches:
    results = masker.mask_tcp_payloads_batch(batch)
    monitor_performance()
```

## 故障排除

### 常见问题和解决方案

#### 1. 保留范围表为空

**错误**: `ValidationError: TCP保留范围表为空，没有需要处理的条目`

**解决方案**:
```python
# 检查表是否为空
if table.get_total_entries() == 0:
    logger.error("保留范围表为空，请添加条目")
    
# 添加默认条目
default_entry = TcpKeepRangeEntry(
    stream_id="TCP_0.0.0.0:0_0.0.0.0:0_default",
    sequence_start=0,
    sequence_end=1000000,
    keep_ranges=[(0, 5)],  # 保留头部5字节
    protocol_hint="UNKNOWN"
)
table.add_keep_range_entry(default_entry)
```

#### 2. 序列号范围无效

**错误**: `ValueError: 序列号范围无效: start=2000 >= end=1000`

**解决方案**:
```python
# 验证序列号范围
if sequence_start >= sequence_end:
    logger.error(f"序列号范围无效: {sequence_start} >= {sequence_end}")
    sequence_start, sequence_end = sequence_end, sequence_start  # 交换
```

#### 3. 保留范围重叠

**警告**: TCP流存在序列号重叠

**解决方案**:
```python
# 检查一致性问题
issues = table.validate_consistency()
for issue in issues:
    if "重叠" in issue:
        logger.warning(f"检测到重叠: {issue}")

# 使用优化功能自动合并重叠范围
optimized_table = masker.optimize_keep_range_table(table)
```

#### 4. 文件不存在

**错误**: `FileNotFoundError`

**解决方案**:
```python
import os

# 检查输入文件
if not os.path.exists(input_pcap):
    raise FileNotFoundError(f"输入文件不存在: {input_pcap}")

# 检查输出目录
output_dir = os.path.dirname(output_pcap)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)
```

#### 5. 性能问题

**问题**: 处理速度慢

**排查步骤**:
```python
# 1. 获取性能指标
metrics = masker.get_performance_metrics()
pps = metrics['processing_speed']['packets_per_second']

# 2. 检查保留范围表大小
total_entries = table.get_total_entries()
streams_count = table.get_streams_count()

# 3. 优化建议
if total_entries > 10000:
    logger.info("建议优化保留范围表")
    optimized_table = masker.optimize_keep_range_table(table)

if pps < 500:
    logger.info("建议启用性能优化")
    masker.enable_performance_optimization(True)
```

### 调试模式

启用详细日志以进行问题诊断:

```python
import logging

# 设置调试级别
logging.getLogger('pktmask.core.tcp_payload_masker').setLevel(logging.DEBUG)

# 创建详细的处理器
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)
```

---

**版权信息**: TCP Payload Masker API 参考文档  
**维护者**: PktMask 开发团队  
**许可证**: 请参考项目LICENSE文件