# 适配器命名规范

## 1. 总体原则

- **一致性**：所有适配器遵循统一的命名模式
- **描述性**：名称应清晰表达适配器的用途
- **简洁性**：避免过长或冗余的名称

## 2. 文件命名规范

### 2.1 标准适配器
- 格式：`{功能}_adapter.py`
- 示例：
  - `processor_adapter.py` - 处理器适配
  - `event_adapter.py` - 事件数据适配
  - `statistics_adapter.py` - 统计数据适配
  - `encapsulation_adapter.py` - 封装处理适配

### 2.2 兼容性适配器
- 格式：`{功能}_compat.py`
- 示例：
  - `anon_compat.py` - 匿名化兼容
  - `dedup_compat.py` - 去重兼容

## 3. 类命名规范

### 3.1 标准适配器类
- 格式：`{功能}Adapter`
- 示例：
  ```python
  class ProcessorAdapter:
      """处理器适配器"""
      pass
  
  class EventAdapter:
      """事件数据适配器"""
      pass
  ```

### 3.2 兼容性适配器类
- 格式：`{功能}CompatibilityAdapter`
- 示例：
  ```python
  class AnonCompatibilityAdapter:
      """匿名化兼容性适配器"""
      pass
  
  class DedupCompatibilityAdapter:
      """去重兼容性适配器"""
      pass
  ```

## 4. 方法命名规范

### 4.1 适配方法
- 格式：`adapt_{源类型}_to_{目标类型}`
- 示例：
  ```python
  def adapt_processor_to_stage(self, processor):
      """将处理器适配为管道阶段"""
      pass
  
  def adapt_old_event_to_new(self, old_event):
      """将旧版事件格式适配为新版"""
      pass
  ```

### 4.2 转换方法
- 格式：`convert_{内容描述}`
- 示例：
  ```python
  def convert_statistics_format(self, stats):
      """转换统计数据格式"""
      pass
  ```

### 4.3 验证方法
- 格式：`validate_{内容描述}`
- 示例：
  ```python
  def validate_input_format(self, data):
      """验证输入数据格式"""
      pass
  ```

## 5. 变量命名规范

### 5.1 实例变量
- 使用小写字母和下划线
- 示例：
  ```python
  self.source_format = "v1"
  self.target_format = "v2"
  self.conversion_rules = {}
  ```

### 5.2 常量
- 使用大写字母和下划线
- 示例：
  ```python
  DEFAULT_BUFFER_SIZE = 1024
  MAX_RETRY_COUNT = 3
  SUPPORTED_FORMATS = ["json", "yaml", "xml"]
  ```

## 6. 导入规范

### 6.1 模块导入顺序
1. 标准库
2. 第三方库
3. 项目内部模块
4. 相对导入

### 6.2 导入示例
```python
# 标准库
import logging
from typing import Dict, Any

# 第三方库
import pandas as pd

# 项目内部模块
from pktmask.core.base import BaseAdapter
from pktmask.utils.validation import validate_data

# 相对导入（仅在包内部使用）
from .base_adapter import AbstractAdapter
```

## 7. 文档注释规范

### 7.1 模块文档
```python
"""
模块名称适配器

功能描述：
    详细说明适配器的作用和使用场景

使用示例：
    adapter = ExampleAdapter()
    result = adapter.adapt(input_data)
"""
```

### 7.2 类文档
```python
class ExampleAdapter:
    """
    示例适配器
    
    用于将X格式数据适配为Y格式。
    
    Attributes:
        source_format: 源数据格式
        target_format: 目标数据格式
    
    Example:
        >>> adapter = ExampleAdapter()
        >>> result = adapter.adapt(data)
    """
```

### 7.3 方法文档
```python
def adapt_data(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    适配数据格式
    
    Args:
        input_data: 输入数据字典
        
    Returns:
        适配后的数据字典
        
    Raises:
        AdapterError: 当数据格式不支持时
    """
```

## 8. 目录组织规范

```
adapters/
├── __init__.py                 # 统一导出接口
├── base_adapter.py             # 基础适配器类（如需要）
├── processor_adapter.py        # 处理器适配器
├── event_adapter.py            # 事件适配器
├── statistics_adapter.py       # 统计适配器
├── encapsulation_adapter.py    # 封装适配器
└── compatibility/              # 兼容性适配器目录
    ├── __init__.py
    ├── anon_compat.py          # 匿名化兼容
    └── dedup_compat.py         # 去重兼容
```

## 9. 迁移指南

### 9.1 旧名称到新名称映射
| 原名称 | 新名称 | 说明 |
|--------|--------|------|
| `adapter.py` | `encapsulation_adapter.py` | 避免通用名称 |
| `ProcessorAdapterStage` | `ProcessorAdapter` | 简化类名 |

### 9.2 废弃警告示例
```python
# 在旧位置创建的代理文件
import warnings
from pktmask.adapters.processor_adapter import ProcessorAdapter

warnings.warn(
    "导入路径 'pktmask.core.adapters' 已废弃，"
    "请使用 'pktmask.adapters' 替代。"
    "此兼容性支持将在 v2.0 中移除。",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['ProcessorAdapter']
```
