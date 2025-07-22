# API 文档

PktMask 提供了丰富的 API 接口，支持编程方式使用所有核心功能。本目录包含完整的 API 参考文档。

## 📚 API 分类

### 🔧 [核心 API](core-api.md)
核心功能和基础组件的编程接口
- 数据包处理核心
- 配置管理
- 事件系统
- 异常处理

### 🔄 [管道 API](pipeline-api.md)
处理管道和阶段管理的编程接口
- 管道构建和执行
- 阶段注册和配置
- 数据流控制
- 并行处理

### 🛠️ [工具 API](tools-api.md)
专用工具和实用程序的编程接口
- TLS 分析工具
- 验证工具
- 文件处理工具
- 报告生成

## 🎯 使用场景

### 自动化脚本
```python
from pktmask.core import PktMaskProcessor
from pktmask.pipeline import Pipeline

# 创建处理器
processor = PktMaskProcessor()

# 配置管道
pipeline = Pipeline()
pipeline.add_stage('dedup')
pipeline.add_stage('anonymize')
pipeline.add_stage('mask')

# 执行处理
result = processor.process_file('input.pcap', pipeline)
```

### 批量处理
```python
from pktmask.core import BatchProcessor

# 批量处理多个文件
processor = BatchProcessor()
results = processor.process_directory('/path/to/pcap/files')
```

### 自定义工具开发
```python
from pktmask.tools import TLSAnalyzer
from pktmask.utils import ReportGenerator

# 使用 TLS 分析工具
analyzer = TLSAnalyzer()
analysis = analyzer.analyze_file('tls_traffic.pcap')

# 生成报告
generator = ReportGenerator()
report = generator.create_html_report(analysis)
```

## 📖 API 设计原则

### 一致性
- 统一的命名规范
- 一致的参数传递方式
- 标准化的返回值格式

### 易用性
- 简洁的接口设计
- 合理的默认参数
- 清晰的错误信息

### 扩展性
- 插件化架构
- 可配置的处理阶段
- 灵活的事件系统

## 🔧 快速开始

### 安装和导入
```python
# 安装 PktMask
pip install pktmask

# 导入核心模块
from pktmask import PktMask
from pktmask.core import Processor
from pktmask.pipeline import Pipeline
```

### 基本使用
```python
# 创建 PktMask 实例
pktmask = PktMask()

# 处理单个文件
result = pktmask.process_file(
    input_file='input.pcap',
    output_file='output.pcap',
    operations=['dedup', 'anonymize', 'mask']
)

# 检查结果
if result.success:
    print(f"处理完成: {result.statistics}")
else:
    print(f"处理失败: {result.error}")
```

### 高级配置
```python
from pktmask.config import Config

# 自定义配置
config = Config()
config.set('anonymization.method', 'prefix_preserving')
config.set('masking.strategy', 'tls_aware')

# 使用配置
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
