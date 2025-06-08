# PktMask 配置管理系统

## 概述

PktMask 配置管理系统提供了统一的配置管理功能，支持用户自定义设置、处理参数调优和配置持久化。系统采用 Pydantic 进行类型安全的配置验证，支持 YAML 和 JSON 格式的配置文件。

## 核心特性

- **类型安全**: 使用 Pydantic 模型确保配置值的类型正确性
- **配置验证**: 自动验证配置值的有效性和一致性
- **多格式支持**: 支持 YAML 和 JSON 配置文件格式
- **热重载**: 支持配置文件的动态加载和更新
- **回调机制**: 配置变更时自动通知相关组件
- **默认值管理**: 提供合理的默认配置值
- **配置备份**: 支持配置文件的备份和恢复

## 配置结构

### 主配置模型 (PktMaskConfig)

```python
from pktmask.config import get_config_manager

# 获取配置管理器
config_manager = get_config_manager()
config = config_manager.config

# 访问各个配置段
ui_config = config.ui
processing_config = config.processing
performance_config = config.performance
file_config = config.file
logging_config = config.logging
```

### 1. UI配置 (UIConfig)

控制用户界面的外观和行为：

```yaml
ui:
  # 窗口设置
  window_width: 1200          # 窗口宽度 (800-2560)
  window_height: 800          # 窗口高度 (600-1440)
  window_min_width: 800       # 最小窗口宽度 (≥600)
  window_min_height: 600      # 最小窗口高度 (≥400)
  
  # 主题和外观
  theme: "auto"               # 主题模式: auto, light, dark
  language: "zh_CN"           # 界面语言: zh_CN, en_US
  font_size: 12               # 字体大小 (8-24)
  
  # 默认选项
  default_dedup: true         # 默认启用去重
  default_mask_ip: true       # 默认启用IP匿名化
  default_trim: false         # 默认启用载荷裁切
  
  # 界面行为
  remember_last_dir: true     # 记住上次使用的目录
  auto_open_output: false     # 处理完成后自动打开输出目录
  show_progress_details: true # 显示详细进度信息
```

### 2. 处理配置 (ProcessingConfig)

控制数据处理算法和参数：

```yaml
processing:
  # 算法参数
  chunk_size: 10              # 数据包处理块大小 (1-1000)
  max_retry_attempts: 3       # 最大重试次数 (1-10)
  timeout_seconds: 300        # 处理超时时间(秒) (60-3600)
  
  # IP匿名化设置
  anonymization_strategy: "hierarchical"  # 匿名化策略
  preserve_subnet_structure: true         # 保持子网结构
  consistent_mapping: true                # 保持一致性映射
  
  # 去重设置
  dedup_algorithm: "hash_based"           # 去重算法
  dedup_threshold: 0.95                   # 去重相似度阈值 (0.0-1.0)
  
  # 裁切设置
  preserve_tls_handshake: true            # 保留TLS握手数据
  trim_application_data: true             # 裁切应用数据
  max_payload_size: 1024                  # 最大载荷大小 (0-65535)
```

### 3. 性能配置 (PerformanceConfig)

控制系统性能和资源使用：

```yaml
performance:
  # 并发设置
  max_workers: 4              # 最大工作线程数 (1-16)
  use_multiprocessing: false  # 使用多进程处理
  memory_limit_mb: 1024       # 内存限制(MB) (256-8192)
  
  # 缓存设置
  enable_caching: true        # 启用缓存
  cache_size_mb: 256          # 缓存大小(MB) (64-2048)
  cache_cleanup_interval: 300 # 缓存清理间隔(秒) (60-3600)
  
  # 进度报告
  progress_update_interval: 100  # 进度更新间隔(包数) (10-10000)
  enable_detailed_stats: true    # 启用详细统计
```

### 4. 文件配置 (FileConfig)

控制文件处理和输出设置：

```yaml
file:
  # 目录设置
  default_input_dir: null     # 默认输入目录
  default_output_dir: null    # 默认输出目录
  output_dir_pattern: "pktmask_output_{timestamp}"  # 输出目录命名模式
  
  # 文件大小限制
  max_file_size_gb: 2.0       # 最大文件大小(GB) (0.1-100.0)
  min_file_size_bytes: 24     # 最小文件大小(字节) (1-1024)
  
  # 支持的文件类型
  supported_extensions:       # 支持的文件扩展名
    - ".pcap"
    - ".pcapng"
  
  # 输出设置
  preserve_timestamps: true   # 保留文件时间戳
  create_backup: false        # 创建原文件备份
  cleanup_temp_files: true    # 自动清理临时文件
  
  # 报告设置
  generate_html_report: true  # 生成HTML报告
  generate_json_report: true  # 生成JSON报告
  include_detailed_stats: true # 包含详细统计信息
```

### 5. 日志配置 (LoggingConfig)

控制日志记录行为：

```yaml
logging:
  # 日志级别
  console_level: "INFO"       # 控制台日志级别
  file_level: "DEBUG"         # 文件日志级别
  
  # 日志文件设置
  log_file_path: null         # 日志文件路径
  max_log_size_mb: 10         # 最大日志文件大小(MB) (1-100)
  log_backup_count: 5         # 日志备份文件数量 (1-20)
  
  # 日志格式
  include_timestamp: true     # 包含时间戳
  include_module_name: true   # 包含模块名
  include_line_number: false  # 包含行号
```

## 使用方法

### 基本使用

```python
from pktmask.config import get_config_manager

# 获取配置管理器
config_manager = get_config_manager()

# 获取当前配置
config = config_manager.config

# 访问配置值
window_width = config.ui.window_width
chunk_size = config.processing.chunk_size
max_workers = config.performance.max_workers
```

### 更新配置

```python
# 更新单个配置段
success = config_manager.update_ui_config(
    theme='dark',
    font_size=14,
    auto_open_output=True
)

# 更新多个配置段
success = config_manager.update_config({
    'ui': {
        'theme': 'dark',
        'font_size': 14
    },
    'performance': {
        'max_workers': 8
    }
})
```

### 配置验证

```python
# 验证当前配置
validation_result = config_manager.validate_config()

if validation_result['valid']:
    print("配置有效")
else:
    print("配置错误:")
    for error in validation_result['errors']:
        print(f"  - {error}")

if validation_result['warnings']:
    print("配置警告:")
    for warning in validation_result['warnings']:
        print(f"  - {warning}")
```

### 配置文件操作

```python
# 导出配置到文件
config_manager.export_config('my_config.yaml', 'yaml')
config_manager.export_config('my_config.json', 'json')

# 从文件导入配置
success = config_manager.import_config('my_config.yaml')

# 备份当前配置
success = config_manager.backup_config()

# 重置为默认配置
success = config_manager.reset_to_defaults()  # 重置全部
success = config_manager.reset_to_defaults('ui')  # 重置UI配置
```

### 配置变更回调

```python
def on_config_changed(new_config):
    print(f"配置已更新: {new_config.config_version}")
    # 重新应用设置...

# 注册回调
config_manager.register_change_callback(on_config_changed)

# 取消注册回调
config_manager.unregister_change_callback(on_config_changed)
```

## 配置文件位置

### 默认配置文件路径

- **Windows**: `%APPDATA%\PktMask\config.yaml`
- **macOS/Linux**: `~/.config/pktmask/config.yaml`

### 自定义配置文件

```python
# 使用自定义配置文件
config_manager = ConfigManager('/path/to/custom/config.yaml')
```

## 配置模板

系统提供了完整的配置模板文件：

```python
from pktmask.config.loader import ConfigLoader

loader = ConfigLoader()
loader.export_config_template('config_template.yaml')
```

## 最佳实践

### 1. 配置验证

始终在更新配置后进行验证：

```python
if config_manager.update_config(updates):
    validation = config_manager.validate_config()
    if not validation['valid']:
        print("配置更新后验证失败，请检查配置值")
```

### 2. 错误处理

```python
try:
    config_manager.update_ui_config(window_width=500)  # 可能失败
except Exception as e:
    print(f"配置更新失败: {e}")
```

### 3. 性能优化

```python
# 批量更新配置，避免多次保存
updates = {
    'ui': {'theme': 'dark', 'font_size': 14},
    'performance': {'max_workers': 8}
}
config_manager.update_config(updates)
```

### 4. 配置备份

在重要操作前备份配置：

```python
# 备份当前配置
config_manager.backup_config()

# 进行配置更改
config_manager.update_config(risky_updates)
```

## 扩展配置

### 添加新的配置字段

1. 在相应的配置模型中添加字段：

```python
class UIConfig(BaseModel):
    # 现有字段...
    new_feature_enabled: bool = Field(default=False, description="启用新功能")
```

2. 更新配置模板文件
3. 添加相应的验证逻辑

### 添加新的配置段

1. 创建新的配置模型：

```python
class PluginConfig(BaseModel):
    enabled_plugins: List[str] = Field(default=[], description="启用的插件列表")
    plugin_timeout: int = Field(default=30, ge=1, le=300, description="插件超时时间")
```

2. 在主配置模型中添加：

```python
class PktMaskConfig(BaseModel):
    # 现有字段...
    plugin: PluginConfig = Field(default_factory=PluginConfig, description="插件配置")
```

## 故障排除

### 常见问题

1. **配置文件损坏**
   - 系统会自动使用默认配置
   - 检查日志获取详细错误信息

2. **配置验证失败**
   - 检查配置值是否在有效范围内
   - 查看验证错误信息进行修正

3. **配置更新不生效**
   - 确认配置更新返回 True
   - 检查是否注册了配置变更回调

### 调试配置

```python
# 获取配置信息
config_info = config_manager.get_config_info()
print(f"配置文件: {config_info['config_file']}")
print(f"配置版本: {config_info['config_version']}")
print(f"配置有效: {config_info['valid']}")

# 重新加载配置
config_manager.reload_config()
```

## API 参考

详细的 API 文档请参考各模块的 docstring：

- `pktmask.config.models` - 配置数据模型
- `pktmask.config.manager` - 配置管理器
- `pktmask.config.loader` - 配置加载器
- `pktmask.config.validators` - 配置验证器 