# PktMask 统一架构文档

## 概述

本文档描述了 PktMask 项目在实现 GUI 与 CLI 功能统一后的完整架构设计。通过统一的服务层和配置系统，两种界面现在共享相同的核心处理逻辑，确保功能一致性和代码复用。

## 架构层次

```
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层                                │
├─────────────────────────┬───────────────────────────────────┤
│         GUI             │            CLI                    │
│   (main_window.py)      │        (cli.py)                   │
│   - 图形化交互          │   - 命令行交互                    │
│   - 实时进度显示        │   - 批量处理                      │
│   - 可视化报告          │   - 脚本化操作                    │
└─────────────────────────┴───────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│                    统一服务层                                │
├─────────────────────────────────────────────────────────────┤
│  ConfigService     │  OutputService    │  ProgressService   │
│  - 配置构建        │  - 输出格式化     │  - 进度管理        │
│  - 参数验证        │  - 多格式支持     │  - 回调协调        │
│  - GUI/CLI适配     │  - 统计显示       │  - 状态跟踪        │
├─────────────────────────────────────────────────────────────┤
│  PipelineService   │  ReportService    │                    │
│  - 执行器管理      │  - 报告生成       │                    │
│  - 文件/目录处理   │  - 多格式导出     │                    │
│  - 错误处理        │  - 详细统计       │                    │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│                    核心处理层                                │
├─────────────────────────────────────────────────────────────┤
│                 PipelineExecutor                            │
│                 - 统一执行引擎                              │
│                 - Stage 调度                               │
│                 - 结果聚合                                 │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────────┐
│                   StageBase 架构                            │
├─────────────────────────────────────────────────────────────┤
│  UnifiedIPAnonymizationStage  │  UnifiedDeduplicationStage  │
│  NewMaskPayloadStage          │  其他处理阶段               │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件详解

### 1. 统一服务层

#### ConfigService - 配置服务
**职责**：
- 统一的配置构建和验证
- GUI 和 CLI 参数的标准化转换
- 配置完整性检查

**关键接口**：
```python
class ConfigService:
    def build_pipeline_config(self, options: ProcessingOptions) -> Dict[str, Any]
    def create_options_from_cli_args(self, **kwargs) -> ProcessingOptions
    def create_options_from_gui(self, dedup: bool, anon: bool, mask: bool) -> ProcessingOptions
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]
```

#### PipelineService - 管道服务
**职责**：
- 执行器创建和管理
- 单文件和目录处理的统一接口
- 进度回调协调

**关键接口**：
```python
def process_single_file(executor, input_file, output_file, progress_callback, verbose) -> Dict
def process_directory_cli(executor, input_dir, output_dir, progress_callback, verbose) -> Dict
```

#### OutputService - 输出服务
**职责**：
- 统一的输出格式化
- 多级别详细程度控制
- 文本和 JSON 格式支持

**输出级别**：
- `MINIMAL`: 最少输出
- `NORMAL`: 标准输出
- `VERBOSE`: 详细输出
- `DEBUG`: 调试输出

#### ProgressService - 进度服务
**职责**：
- 统一的进度显示管理
- 多样式进度展示
- 回调事件协调

**进度样式**：
- `NONE`: 无进度显示
- `SIMPLE`: 简单进度
- `DETAILED`: 详细进度
- `RICH`: 丰富进度显示

#### ReportService - 报告服务
**职责**：
- 详细处理报告生成
- 多格式报告导出
- 统计数据聚合

**报告格式**：
- 文本格式：人类可读的详细报告
- JSON 格式：机器可读的结构化数据

### 2. 配置统一机制

#### 配置流程
```
GUI 状态 ──┐
           ├──→ ProcessingOptions ──→ PipelineConfig ──→ PipelineExecutor
CLI 参数 ──┘
```

#### 配置映射
| GUI 选项 | CLI 参数 | 配置键 | 说明 |
|---------|---------|--------|------|
| Remove Dupes 复选框 | `--dedup` | `remove_dupes.enabled` | 去重处理 |
| Anonymize IPs 复选框 | `--anon` | `anonymize_ips.enabled` | IP 匿名化 |
| Mask Payloads 复选框 | `--mask` | `mask_payloads.enabled` | 载荷掩码 |
| 掩码模式选择 | `--mode` | `mask_payloads.mode` | enhanced/basic |
| 协议类型 | `--protocol` | `mask_payloads.protocol` | tls/http |

### 3. 处理流程统一

#### 单文件处理流程
```
输入文件 → 配置验证 → 执行器创建 → Stage 执行 → 结果输出 → 报告生成
```

#### 目录批量处理流程
```
输入目录 → 文件扫描 → 配置验证 → 执行器创建 → 
循环处理 → 进度更新 → 结果聚合 → 报告生成
```

### 4. 错误处理统一

#### 错误层次
1. **配置错误**：参数验证失败
2. **文件错误**：文件访问权限问题
3. **处理错误**：Stage 执行异常
4. **系统错误**：内存不足等系统级问题

#### 错误处理策略
- **GUI**：图形化错误对话框 + 日志记录
- **CLI**：命令行错误输出 + 退出码 + 可选报告

### 5. 性能优化

#### 内存管理
- 统一的内存池管理
- 大文件流式处理
- 及时资源释放

#### 并发处理
- Stage 内部并发优化
- 批量处理时的文件级并发（实验性）
- 进度回调的异步处理

## 扩展性设计

### 1. 新界面支持
架构支持轻松添加新的用户界面：
```python
# 新界面只需实现统一的服务层接口
new_interface = NewInterface()
config = build_config_from_new_interface(new_interface.get_options())
executor = create_pipeline_executor(config)
result = process_with_unified_service(executor, input_path, output_path)
```

### 2. 新处理阶段
添加新的处理阶段：
```python
class NewProcessingStage(StageBase):
    def process_packet(self, packet):
        # 实现新的处理逻辑
        pass

# 在配置服务中注册
config_service.register_stage("new_processing", NewProcessingStage)
```

### 3. 新输出格式
添加新的输出格式：
```python
class NewOutputFormatter:
    def format_result(self, result):
        # 实现新的格式化逻辑
        pass

output_service.register_formatter("new_format", NewOutputFormatter)
```

## 测试策略

### 1. 单元测试
- 每个服务组件的独立测试
- 配置转换逻辑测试
- 错误处理路径测试

### 2. 集成测试
- GUI 与 CLI 功能一致性测试
- 端到端处理流程测试
- 性能基准测试

### 3. 兼容性测试
- 向后兼容性验证
- 不同平台兼容性测试
- 大规模数据处理测试

## 部署考虑

### 1. 依赖管理
- 统一的依赖声明
- 可选依赖的条件加载
- 版本兼容性管理

### 2. 配置管理
- 默认配置的合理性
- 用户配置的持久化
- 配置迁移策略

### 3. 监控和日志
- 统一的日志格式
- 性能指标收集
- 错误追踪和报告

## 未来发展

### 1. 短期目标
- 完善批量处理的并发支持
- 增强报告系统的可视化能力
- 优化大文件处理性能

### 2. 长期目标
- 支持更多协议类型
- 实现插件化架构
- 提供 Web 界面支持

## 总结

通过统一的服务层架构，PktMask 实现了 GUI 与 CLI 的完全功能一致性，同时保持了良好的代码复用性和扩展性。这种设计不仅解决了当前的功能差异问题，还为未来的功能扩展和新界面支持奠定了坚实的基础。
