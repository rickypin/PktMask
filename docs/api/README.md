# API Documentation

PktMask provides rich API interfaces that support programmatic use of all core functionality.

> **Note**: Detailed API documentation is currently under development. For now, please refer to the source code and existing documentation.

## 📚 Available API Information

### 🔧 Core Components
For core API usage, see the source code documentation:
- **Pipeline Stages**: `src/pktmask/core/pipeline/stages/`
- **Configuration**: `src/pktmask/config/`
- **Services**: `src/pktmask/services/`

### 🔄 Architecture Reference
- **[Unified Architecture](../ARCHITECTURE_UNIFIED.md)** - System architecture overview
- **[Developer Documentation](../dev/README.md)** - Technical implementation details

### 📖 Usage Examples
- **[CLI Guide](../CLI_UNIFIED_GUIDE.md)** - Command-line usage examples
- **[Tools Documentation](../tools/README.md)** - Tool-specific APIs

### 🛠️ [Tools API](tools-api.md)
Programming interfaces for specialized tools and utilities
- TLS analysis tools
- Validation tools
- File processing tools
- Report generation

## 🎯 Usage Scenarios

### Automation Scripts
```python
from pktmask.core import PktMaskProcessor
from pktmask.pipeline import Pipeline

# Create processor
processor = PktMaskProcessor()

# Configure pipeline
pipeline = Pipeline()
pipeline.add_stage('dedup')
pipeline.add_stage('anonymize')
pipeline.add_stage('mask')

# Execute processing
result = processor.process_file('input.pcap', pipeline)
```

### Batch Processing
```python
from pktmask.core import BatchProcessor

# Batch process multiple files
processor = BatchProcessor()
results = processor.process_directory('/path/to/pcap/files')
```

### Custom Tool Development
```python
from pktmask.tools import TLSAnalyzer
from pktmask.utils import ReportGenerator

# Use TLS analysis tool
analyzer = TLSAnalyzer()
analysis = analyzer.analyze_file('tls_traffic.pcap')

# Generate report
generator = ReportGenerator()
report = generator.create_html_report(analysis)
```

## 📖 API Design Principles

### Consistency
- Unified naming conventions
- Consistent parameter passing methods
- Standardized return value formats

### Usability
- Simple interface design
- Reasonable default parameters
- Clear error messages

### Extensibility
- Plugin-based architecture
- Configurable processing stages
- Flexible event system

## 🔧 Quick Start

### Installation and Import
```python
# Install PktMask
pip install pktmask

# Import core modules
from pktmask import PktMask
from pktmask.core import Processor
from pktmask.pipeline import Pipeline
```

### Basic Usage
```python
# Create PktMask instance
pktmask = PktMask()

# Process single file
result = pktmask.process_file(
    input_file='input.pcap',
    output_file='output.pcap',
    operations=['dedup', 'anonymize', 'mask']
)

# Check results
if result.success:
    print(f"Processing completed: {result.statistics}")
else:
    print(f"Processing failed: {result.error}")
```

### Advanced Configuration
```python
from pktmask.config import Config

# Custom configuration
config = Config()
config.set('anonymization.method', 'prefix_preserving')
config.set('masking.strategy', 'tls_aware')

# Use configuration
pktmask = PktMask(config=config)
```

## 📋 API 参考

### 核心类和方法

#### PktMask 主类
- `process_file()` - 处理单个文件
- `process_directory()` - 批量处理目录
- `get_statistics()` - 获取处理统计
- `configure()` - 配置处理参数

#### Pipeline 管道类
- `add_stage()` - 添加处理阶段
- `remove_stage()` - 移除处理阶段
- `execute()` - 执行管道
- `get_stages()` - 获取阶段列表

#### Processor 处理器类
- `register_stage()` - 注册自定义阶段
- `set_config()` - 设置配置
- `process()` - 执行处理
- `get_result()` - 获取处理结果

## 🔗 相关资源

### 示例代码
- **[用户指南](../user/)** - 基础使用示例
- **[工具文档](../tools/)** - 工具 API 使用示例
- **[GitHub 仓库](https://github.com/pktmask/pktmask)** - 完整示例代码

### 开发资源
- **[开发者文档](../dev/)** - 开发指南和规范
- **[架构文档](../architecture/)** - 系统设计和原理
- **[测试指南](../dev/testing-guide.md)** - API 测试方法

## 📝 版本兼容性

### 当前版本
- **API 版本**: v4.0
- **Python 支持**: 3.8+
- **向后兼容**: 支持 v3.x API

### 版本变更
- **v4.0** - 新增工具 API，重构管道 API
- **v3.x** - 稳定的核心 API
- **v2.x** - 遗留版本（不推荐）

## 🐛 错误处理

### 异常类型
```python
from pktmask.exceptions import (
    PktMaskError,          # 基础异常
    ProcessingError,       # 处理错误
    ConfigurationError,    # 配置错误
    FileFormatError        # 文件格式错误
)

try:
    result = pktmask.process_file('input.pcap')
except ProcessingError as e:
    print(f"处理错误: {e}")
except FileFormatError as e:
    print(f"文件格式错误: {e}")
```

### 错误码
- `E001` - 文件不存在
- `E002` - 格式不支持
- `E003` - 权限不足
- `E004` - 内存不足

---

> 💡 **提示**: API 文档包含详细的参数说明、返回值格式和使用示例，建议结合具体的 API 文档使用。
