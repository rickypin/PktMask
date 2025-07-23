# PktMask 工具函数模块

本模块提供了一套统一的工具函数，用于简化常见的编程任务，提高代码复用性和一致性。

## 模块结构

```
utils/
├── __init__.py          # 统一导出接口
├── time.py              # 时间处理工具
├── file_ops.py          # 文件操作工具
├── math_ops.py          # 数值计算工具
├── string_ops.py        # 字符串格式化工具
├── path.py              # 路径处理工具
├── file_selector.py     # 文件选择工具
└── reporting.py         # 报告生成工具
```

## 使用方式

### 统一导入
```python
from pktmask.utils import (
    current_timestamp, calculate_percentage, 
    format_ip_mapping, ensure_directory
)
```

### 分模块导入
```python
from pktmask.utils.time import current_timestamp, format_duration
from pktmask.utils.math_ops import calculate_percentage, format_number
```

## 主要功能

### 1. 时间处理 (time.py)

#### 时间格式化
```python
# 获取当前时间字符串
current_time()  # "2025-06-08 17:15:01"
current_time("%Y%m%d")  # "20250608"

# 获取时间戳（用于文件命名）
current_timestamp()  # "20250608_171501"

# 格式化持续时间
format_duration(start_time, end_time)  # "1h 23m 45s"
format_duration_seconds(3665)  # "1h 1m 5s"

# 格式化毫秒为时间显示
format_milliseconds_to_time(125000)  # "02:05.00"
```

#### 性能指标计算
```python
metrics = get_performance_metrics(start_time, end_time, item_count=1000)
# 返回: {
#   'duration_seconds': 10.5,
#   'duration_formatted': '10s',
#   'items_per_second': 95.2,
#   'items_processed': 1000
# }
```

### 2. 文件操作 (file_ops.py)

#### 目录管理
```python
# 确保目录存在
ensure_directory("/path/to/dir")

# 安全路径拼接
safe_join("path", "to", "file.txt")  # "path/to/file.txt"

# 在系统文件管理器中打开目录
open_directory_in_system("/path/to/dir")
```

#### 文件信息
```python
# 获取文件信息
get_file_extension("file.pcap")  # ".pcap"
get_file_base_name("file.pcap")  # "file"
get_file_size("file.pcap")  # 1024000

# 验证文件
validate_file_size("file.pcap")  # True/False
is_supported_file("file.pcap")  # True
```

#### File Search
```python
# Find PCAP files
pcap_files = find_pcap_files("/path/to/dir")

# Find files by extension
files = find_files_by_extension("/path", [".txt", ".log"])
```

#### File Operations
```python
# Safe file copy
copy_file_safely("src.txt", "dst.txt", overwrite=True)

# Safe file deletion
delete_file_safely("temp.txt")

# Generate output filename
output_file = generate_output_filename("input.pcap", "-processed")
# "input-processed.pcap"

# Clean temporary files
cleaned_count = cleanup_temp_files("/path/to/dir", "*.tmp")
```

### 3. Numerical Calculations (math_ops.py)

#### Percentages and Ratios
```python
# Calculate percentage
percentage = calculate_percentage(75, 100)  # 75.0
rate = calculate_rate(processed=80, total=100)  # 80.0

# Calculate processing speed
speed = calculate_speed(1000, 10.5)  # 95.2 items/second
```

#### 数字格式化
```python
# 格式化数字
format_number(1234567)  # "1,234,567"
format_number(123.456, decimal_places=2)  # "123.46"

# 格式化文件大小
format_size_bytes(1024000)  # "1000.00 KB"
format_size_bytes(1073741824)  # "1.00 GB"
```

#### 统计计算
```python
# 计算基本统计
stats = calculate_statistics([1, 2, 3, 4, 5])
# 返回: {
#   'count': 5, 'sum': 15, 'mean': 3.0,
#   'min': 1, 'max': 5, 'median': 3.0
# }

# 格式化处理摘要
summary = format_processing_summary(1000, 850, "IP Masking", "packets")
# "IP Masking: 850 / 1,000 packets (85.0%)"
```

#### 数值处理
```python
# 安全除法
result = safe_divide(10, 0, default=0)  # 0.0

# 数值限制
clamped = clamp(150, 0, 100)  # 100

# 数值标准化
normalized = normalize_value(75, 0, 100)  # 0.75
```

### 4. 字符串格式化 (string_ops.py)

#### 分隔符和格式化
```python
# 创建分隔符
separator = create_separator(50, "=")  # "=" * 50

# 格式化IP映射
ip_mapping = format_ip_mapping("192.168.1.1", "10.0.0.1")
# "192.168.1.1      → 10.0.0.1"
```

#### 步骤摘要格式化
```python
# IP匿名化摘要
summary = format_step_summary("IP Masking", 1000, 850, 85.0, "🛡️")
# "  🛡️ IP Masking        | Original: 1000 | Processed:  850 | Rate:  85.0%"

# 去重摘要
dedup_summary = format_deduplication_summary("Deduplication", 800, 200, 20.0)
# "  🔄 Deduplication     | Unique Pkts:  800 | Removed Pkts:  200 | Rate:  20.0%"

# 裁切摘要
trim_summary = format_trimming_summary("Payload Trim", 1000, 300, 30.0)
# "  ✂️  Payload Trim      | Full Pkts:  1000 | Trimmed Pkts:  300 | Rate:  30.0%"
```

#### 章节和列表格式化
```python
# 格式化章节标题
header = format_section_header("PROCESSING RESULTS", "📊")

# 格式化IP映射列表
ip_mappings = {"192.168.1.1": "10.0.0.1", "192.168.1.2": "10.0.0.2"}
mapping_list = format_ip_mapping_list(ip_mappings, max_display=5)

# 格式化文件状态
status = format_file_status("file.pcap", "✅", ["Processed successfully", "Output: file-processed.pcap"])
```

#### 字符串处理
```python
# 截断字符串
truncated = truncate_string("Very long text here", 10)  # "Very lo..."

# 填充字符串
padded = pad_string("Text", 10, align=">")  # "      Text"

# 连接字符串列表
joined = join_with_separator(["Step1", "Step2", "Step3"])  # "Step1, Step2, Step3"

# 清理文件名
clean_name = clean_filename("file<name>.txt")  # "file_name_.txt"
```

## 设计原则

1. **统一性**: 所有工具函数遵循相同的命名和参数约定
2. **安全性**: 包含错误处理和边界情况处理
3. **可配置性**: 提供合理的默认值，同时允许自定义
4. **性能**: 优化常用操作的性能
5. **可测试性**: 函数设计便于单元测试

## 常量集成

工具函数与常量系统紧密集成：

```python
from pktmask.common.constants import FormatConstants, SystemConstants

# 使用预定义的格式常量
format_ip_mapping(ip1, ip2, FormatConstants.IP_DISPLAY_WIDTH)

# 使用系统常量
format_duration_seconds(duration, SystemConstants.SECONDS_PER_MINUTE)
```

## 错误处理

所有工具函数都包含适当的错误处理：

```python
try:
    ensure_directory("/invalid/path")
except FileError as e:
    logger.error(f"Directory creation failed: {e}")

# 或使用安全函数
success = delete_file_safely("/path/to/file")  # 返回 True/False
```

## 性能考虑

- 文件操作使用 `pathlib.Path` 提高性能和跨平台兼容性
- 数值计算避免重复计算
- 字符串格式化使用高效的格式化方法
- 大文件操作包含进度回调支持

## 扩展指南

添加新工具函数时：

1. 选择合适的模块或创建新模块
2. 遵循现有的命名约定
3. 添加完整的类型注解和文档字符串
4. 包含错误处理
5. 更新 `__init__.py` 的导出列表
6. 添加使用示例到此文档 