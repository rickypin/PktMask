# PktMask 项目代码逻辑与架构分析

## 📋 目录
- [项目概述](#项目概述)
- [核心功能](#核心功能)
- [架构设计](#架构设计)
- [数据处理流程](#数据处理流程)
- [关键模块解析](#关键模块解析)
- [技术栈](#技术栈)

---

## 项目概述

**PktMask** 是一个专业的网络数据包处理工具，用于安全地共享和分析网络数据包捕获文件（PCAP/PCAPNG）。它通过去除敏感信息，同时保留分析价值，使网络专业人员能够安全地共享网络数据。

### 应用场景
- 🔒 **安全事件响应** - 与外部团队共享攻击证据
- 🔧 **网络故障排查** - 向供应商发送网络捕获数据
- 📚 **培训与研究** - 创建真实但匿名的数据集
- ✅ **合规审计** - 满足数据保护法规要求

---

## 核心功能

PktMask 提供三大核心处理功能：

### 1. 🔄 Remove Dupes（去重）
- **功能**：消除重复数据包，减少文件大小
- **算法**：基于 SHA256/MD5 哈希的字节级去重
- **效果**：典型场景下可减少 30-50% 文件大小
- **实现**：`DeduplicationStage`

### 2. 🎭 Anonymize IPs（IP匿名化）
- **功能**：将真实IP地址替换为一致的虚假地址
- **策略**：层次化匿名化，保留子网结构
- **支持**：IPv4 和 IPv6
- **实现**：`AnonymizationStage`

### 3. 🛡️ Mask Payloads（载荷掩码）
- **功能**：移除敏感数据，保留协议结构
- **协议**：TLS/SSL、HTTP（自动检测）
- **模式**：双模块架构（Marker + Masker）
- **实现**：`MaskingStage`

---

## 架构设计

### 整体架构层次

```
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层 (UI Layer)                     │
├─────────────────────────┬───────────────────────────────────┤
│         GUI             │            CLI                    │
│   (PyQt6 桌面应用)       │      (Typer 命令行)               │
│   - 图形化交互           │   - 批处理操作                     │
│   - 实时进度显示         │   - 脚本化处理                     │
│   - 可视化报告           │   - 自动化集成                     │
└─────────────────────────┴───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  统一服务层 (Service Layer)                  │
├─────────────────────────────────────────────────────────────┤
│  ConfigService     │  PipelineService  │  ProgressService   │
│  - 配置构建         │  - 执行器管理      │  - 进度管理        │
│  - 参数验证         │  - 文件/目录处理   │  - 回调协调        │
│  - GUI/CLI适配     │  - 错误处理        │  - 状态跟踪        │
├─────────────────────────────────────────────────────────────┤
│  OutputService     │  ReportService    │                    │
│  - 输出格式化       │  - 报告生成        │                    │
│  - 多级详细度       │  - 多格式导出      │                    │
│  - 文本/JSON       │  - 统计聚合        │                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                 核心处理层 (Core Layer)                      │
├─────────────────────────────────────────────────────────────┤
│                   PipelineExecutor                          │
│                   - 统一执行引擎                             │
│                   - 阶段调度                                 │
│                   - 结果聚合                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                 处理阶段层 (Stage Layer)                     │
├─────────────────────────────────────────────────────────────┤
│  DeduplicationStage │ AnonymizationStage │ MaskingStage     │
│  - SHA256哈希去重   │ - 层次化IP匿名化   │ - 双模块掩码      │
│  - 字节级比较       │ - 子网结构保留     │ - 协议智能分析    │
│  - 空间节省统计     │ - IPv4/IPv6支持   │ - 规则化处理      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              基础设施层 (Infrastructure Layer)               │
├─────────────────────────────────────────────────────────────┤
│  Logging           │  Error Handling   │  Resource Mgmt    │
│  - 统一日志系统     │  - 异常处理        │  - 内存管理        │
│  - 多级日志         │  - 错误恢复        │  - 临时文件清理    │
│  - 文件/控制台输出  │  - 上下文追踪      │  - 资源池管理      │
└─────────────────────────────────────────────────────────────┘
```

### 设计原则

1. **分层架构** - 清晰的职责分离，每层专注特定功能
2. **统一接口** - GUI 和 CLI 共享相同的核心处理逻辑
3. **可扩展性** - 易于添加新的处理阶段和协议支持
4. **类型安全** - 强类型注解，减少运行时错误
5. **错误恢复** - 完善的异常处理和资源清理机制

---

## 数据处理流程

### 单文件处理流程

```
┌─────────────┐
│  用户输入    │
│  - 输入文件  │
│  - 输出路径  │
│  - 处理选项  │
└──────┬──────┘
       ↓
┌─────────────────────────────────────────┐
│  1. 配置构建 (ConfigService)             │
│  - 验证输入参数                          │
│  - 构建 ProcessingOptions               │
│  - 生成 PipelineConfig                  │
└──────┬──────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  2. 执行器创建 (PipelineExecutor)        │
│  - 解析配置                              │
│  - 动态装配 Stage 列表                   │
│  - 初始化资源管理器                      │
└──────┬──────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  3. 阶段执行 (Stage Pipeline)            │
│  ┌─────────────────────────────────┐   │
│  │ Stage 1: DeduplicationStage     │   │
│  │ - 读取数据包                     │   │
│  │ - 计算哈希值                     │   │
│  │ - 过滤重复包                     │   │
│  │ - 写入临时文件                   │   │
│  └────────┬────────────────────────┘   │
│           ↓                             │
│  ┌─────────────────────────────────┐   │
│  │ Stage 2: AnonymizationStage     │   │
│  │ - 读取数据包                     │   │
│  │ - 提取IP地址                     │   │
│  │ - 应用匿名化策略                 │   │
│  │ - 重写IP字段                     │   │
│  │ - 写入临时文件                   │   │
│  └────────┬────────────────────────┘   │
│           ↓                             │
│  ┌─────────────────────────────────┐   │
│  │ Stage 3: MaskingStage           │   │
│  │ ┌─────────────────────────────┐ │   │
│  │ │ Marker 模块 (协议分析)       │ │   │
│  │ │ - TShark 协议解析            │ │   │
│  │ │ - 生成保留规则集             │ │   │
│  │ │ - TCP序列号映射              │ │   │
│  │ └────────┬────────────────────┘ │   │
│  │          ↓                       │   │
│  │ ┌─────────────────────────────┐ │   │
│  │ │ Masker 模块 (载荷处理)       │ │   │
│  │ │ - Scapy 数据包读取           │ │   │
│  │ │ - 应用保留规则               │ │   │
│  │ │ - 掩码敏感载荷               │ │   │
│  │ │ - 写入最终文件               │ │   │
│  │ └─────────────────────────────┘ │   │
│  └─────────────────────────────────┘   │
└──────┬──────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  4. 结果聚合与报告                       │
│  - 收集各阶段统计信息                    │
│  - 计算总处理时间                        │
│  - 生成处理报告                          │
│  - 返回 ProcessResult                   │
└──────┬──────────────────────────────────┘
       ↓
┌─────────────┐
│  输出结果    │
│  - 处理文件  │
│  - 统计报告  │
│  - 日志信息  │
└─────────────┘
```

### 批量处理流程

```
┌─────────────┐
│  输入目录    │
└──────┬──────┘
       ↓
┌─────────────────────────────────────────┐
│  1. 文件扫描                             │
│  - 递归查找 .pcap/.pcapng 文件           │
│  - 过滤隐藏文件                          │
│  - 构建文件列表                          │
└──────┬──────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  2. 批量处理循环                         │
│  ┌─────────────────────────────────┐   │
│  │  For each file:                 │   │
│  │  ├─ 检查中断标志                 │   │
│  │  ├─ 发送 FILE_START 事件        │   │
│  │  ├─ 执行单文件处理流程           │   │
│  │  ├─ 收集处理结果                 │   │
│  │  ├─ 更新进度回调                 │   │
│  │  └─ 发送 FILE_END 事件          │   │
│  └─────────────────────────────────┘   │
└──────┬──────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  3. 结果汇总                             │
│  - 成功文件数                            │
│  - 失败文件数                            │
│  - 总处理时间                            │
│  - 聚合统计信息                          │
└──────┬──────────────────────────────────┘
       ↓
┌─────────────┐
│  批量报告    │
└─────────────┘
```

---

## 关键模块解析

### 1. PipelineExecutor（管道执行器）

**位置**: `src/pktmask/core/pipeline/executor.py`

**职责**:
- 根据配置动态装配处理阶段
- 管理临时文件和资源
- 协调阶段间的数据流转
- 收集和聚合统计信息

**核心方法**:
```python
def run(input_path, output_path, progress_cb) -> ProcessResult:
    """执行完整处理管道"""
    # 1. 验证输入文件
    # 2. 创建临时目录
    # 3. 顺序执行各阶段
    # 4. 清理临时文件
    # 5. 返回处理结果
```

**配置格式**:
```python
config = {
    "remove_dupes": {"enabled": True},
    "anonymize_ips": {"enabled": True},
    "mask_payloads": {
        "enabled": True,
        "protocol": "tls",
        "mode": "enhanced"
    }
}
```

### 2. StageBase（阶段基类）

**位置**: `src/pktmask/core/pipeline/base_stage.py`

**设计模式**: 模板方法模式

**核心接口**:
```python
class StageBase(ABC):
    @abstractmethod
    def initialize(config) -> bool:
        """初始化阶段"""
    
    @abstractmethod
    def process_file(input_path, output_path) -> StageStats:
        """处理单个文件"""
    
    def prepare_for_directory(directory, all_files):
        """目录级预处理（可选）"""
    
    def finalize_directory_processing():
        """目录级后处理（可选）"""
```

**资源管理**:
- 统一的临时文件管理
- 自动资源清理
- 异常恢复机制

### 3. MaskingStage（掩码阶段）

**位置**: `src/pktmask/core/pipeline/stages/masking_stage/`

**双模块架构**:

#### Marker 模块（协议分析器）
- **工具**: TShark（Wireshark命令行工具）
- **功能**: 
  - 解析协议结构
  - 识别需要保留的数据包部分
  - 生成 TCP 序列号保留规则
- **支持协议**: TLS, HTTP, Auto-detect

#### Masker 模块（载荷处理器）
- **工具**: Scapy（Python数据包处理库）
- **功能**:
  - 读取数据包
  - 应用保留规则
  - 掩码敏感载荷
  - 写入处理后的数据包

**处理流程**:
```
Input PCAP
    ↓
[Marker] TShark 分析 → KeepRuleSet (TCP seq保留规则)
    ↓
[Masker] Scapy 应用规则 → 掩码载荷
    ↓
Output PCAP
```

### 4. ConfigService（配置服务）

**位置**: `src/pktmask/services/config_service.py`

**职责**:
- 统一配置构建
- GUI/CLI 参数适配
- 配置验证

**数据模型**:
```python
@dataclass
class ProcessingOptions:
    enable_remove_dupes: bool = False
    enable_anonymize_ips: bool = False
    enable_mask_payloads: bool = False
    mask_protocol: str = "tls"
    preserve_handshake: bool = True
    preserve_alert: bool = True
    # ... 更多配置项
```

**配置转换**:
```
GUI Checkboxes → ProcessingOptions → PipelineConfig
CLI Arguments  → ProcessingOptions → PipelineConfig
```

### 5. GUI 管理器架构

**位置**: `src/pktmask/gui/managers/`

**管理器职责分离**:

| 管理器 | 职责 |
|--------|------|
| **UIManager** | UI组件创建、布局管理、样式应用 |
| **FileManager** | 文件选择、目录扫描、路径验证 |
| **PipelineManager** | 执行器创建、线程管理、进度跟踪 |
| **ReportManager** | 报告生成、统计展示、结果导出 |
| **DialogManager** | 对话框管理、用户交互、消息提示 |
| **EventCoordinator** | 事件分发、管理器间通信 |

**事件驱动模型**:
```python
class PipelineEvents(Enum):
    PIPELINE_START = "pipeline_start"
    FILE_START = "file_start"
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    FILE_END = "file_end"
    PIPELINE_END = "pipeline_end"
    ERROR = "error"
    LOG = "log"
```

---

## 技术栈

### 核心依赖

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.8+ | 主要编程语言 |
| **Scapy** | Latest | 数据包读写和处理 |
| **PyQt6** | Latest | GUI 框架 |
| **Typer** | Latest | CLI 框架 |
| **TShark** | Latest | 协议分析（外部工具） |

### 开发工具

| 工具 | 用途 |
|------|------|
| **pytest** | 单元测试和集成测试 |
| **flake8** | 代码风格检查 |
| **black** | 代码格式化 |
| **mypy** | 类型检查 |
| **PyInstaller** | 可执行文件打包 |

### 项目结构

```
PktMask/
├── src/pktmask/              # 源代码
│   ├── __main__.py           # 入口点
│   ├── cli/                  # CLI 模块
│   │   ├── commands.py       # CLI 命令
│   │   └── formatters.py     # 输出格式化
│   ├── gui/                  # GUI 模块
│   │   ├── main_window.py    # 主窗口
│   │   └── managers/         # 管理器
│   ├── core/                 # 核心处理
│   │   ├── pipeline/         # 管道系统
│   │   │   ├── executor.py   # 执行器
│   │   │   ├── base_stage.py # 阶段基类
│   │   │   └── stages/       # 处理阶段
│   │   ├── strategy.py       # 匿名化策略
│   │   └── consistency.py    # 一致性处理器
│   ├── services/             # 服务层
│   │   ├── config_service.py # 配置服务
│   │   ├── pipeline_service.py # 管道服务
│   │   ├── progress_service.py # 进度服务
│   │   └── report_service.py # 报告服务
│   ├── domain/               # 领域模型
│   │   └── models/           # 数据模型
│   ├── infrastructure/       # 基础设施
│   │   ├── logging/          # 日志系统
│   │   ├── error_handling/   # 错误处理
│   │   └── dependency/       # 依赖管理
│   ├── common/               # 公共模块
│   │   ├── constants.py      # 常量定义
│   │   ├── enums.py          # 枚举类型
│   │   └── exceptions.py     # 异常类
│   ├── config/               # 配置模块
│   │   ├── settings.py       # 应用配置
│   │   └── defaults.py       # 默认值
│   └── utils/                # 工具函数
│       ├── file_ops.py       # 文件操作
│       ├── reporting.py      # 报告工具
│       └── subprocess_utils.py # 子进程工具
├── tests/                    # 测试代码
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   └── e2e/                  # 端到端测试
├── docs/                     # 文档
│   ├── user/                 # 用户文档
│   ├── dev/                  # 开发文档
│   └── api/                  # API 文档
├── config/                   # 配置文件
│   ├── app/                  # 应用配置
│   └── templates/            # 配置模板
├── scripts/                  # 脚本工具
│   ├── build/                # 构建脚本
│   ├── test/                 # 测试脚本
│   └── validation/           # 验证脚本
└── output/                   # 输出目录
```

---

## 数据流详解

### 配置数据流

```
┌──────────────┐
│  用户输入     │
│  GUI/CLI     │
└──────┬───────┘
       ↓
┌──────────────────────────────┐
│  ProcessingOptions           │
│  - enable_remove_dupes       │
│  - enable_anonymize_ips      │
│  - enable_mask_payloads      │
│  - mask_protocol             │
│  - preserve_* options        │
└──────┬───────────────────────┘
       ↓
┌──────────────────────────────┐
│  PipelineConfig (Dict)       │
│  {                           │
│    "remove_dupes": {...},    │
│    "anonymize_ips": {...},   │
│    "mask_payloads": {        │
│      "protocol": "tls",      │
│      "marker_config": {...}, │
│      "masker_config": {...}  │
│    }                         │
│  }                           │
└──────┬───────────────────────┘
       ↓
┌──────────────────────────────┐
│  PipelineExecutor            │
│  - 解析配置                   │
│  - 创建 Stage 实例            │
│  - 初始化资源                 │
└──────────────────────────────┘
```

### 数据包处理流

```
┌──────────────┐
│  Input PCAP  │
│  (原始文件)   │
└──────┬───────┘
       ↓
┌─────────────────────────────────────┐
│  Stage 1: Deduplication             │
│  ┌───────────────────────────────┐  │
│  │ For each packet:              │  │
│  │ 1. 读取数据包                  │  │
│  │ 2. 计算 SHA256 哈希            │  │
│  │ 3. 检查哈希集合                │  │
│  │ 4. 如果新包，添加到输出        │  │
│  │ 5. 如果重复，跳过              │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────────────────┘
       ↓
┌──────────────┐
│  Temp File 1 │
│  (去重后)     │
└──────┬───────┘
       ↓
┌─────────────────────────────────────┐
│  Stage 2: Anonymization             │
│  ┌───────────────────────────────┐  │
│  │ For each packet:              │  │
│  │ 1. 读取数据包                  │  │
│  │ 2. 提取 IP 层                  │  │
│  │ 3. 提取源/目标 IP              │  │
│  │ 4. 应用匿名化策略              │  │
│  │ 5. 重写 IP 字段                │  │
│  │ 6. 重新计算校验和              │  │
│  │ 7. 写入输出                    │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────────────────┘
       ↓
┌──────────────┐
│  Temp File 2 │
│  (IP匿名化)   │
└──────┬───────┘
       ↓
┌─────────────────────────────────────┐
│  Stage 3: Masking                   │
│  ┌───────────────────────────────┐  │
│  │ Phase 1: Marker (TShark)      │  │
│  │ 1. 运行 TShark 分析            │  │
│  │ 2. 解析协议字段                │  │
│  │ 3. 识别保留部分                │  │
│  │ 4. 生成 KeepRuleSet            │  │
│  │    - TCP seq → keep/mask      │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Phase 2: Masker (Scapy)       │  │
│  │ For each packet:              │  │
│  │ 1. 读取数据包                  │  │
│  │ 2. 提取 TCP 层                 │  │
│  │ 3. 获取 TCP seq                │  │
│  │ 4. 查询 KeepRuleSet            │  │
│  │ 5. 如果需要掩码：              │  │
│  │    - 清零载荷数据              │  │
│  │    - 保留协议头                │  │
│  │ 6. 如果需要保留：              │  │
│  │    - 保持原始载荷              │  │
│  │ 7. 写入输出                    │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────────────────┘
       ↓
┌──────────────┐
│ Output PCAP  │
│ (最终文件)    │
└──────────────┘
```

### 统计信息流

```
┌──────────────┐
│  Stage Stats │ (每个阶段)
└──────┬───────┘
       ↓
┌─────────────────────────────────┐
│  StageStats                     │
│  - stage_name: str              │
│  - packets_processed: int       │
│  - packets_modified: int        │
│  - duration_ms: float           │
│  - extra_metrics: Dict          │
└──────┬──────────────────────────┘
       ↓
┌─────────────────────────────────┐
│  ProcessResult                  │
│  - success: bool                │
│  - input_file: str              │
│  - output_file: str             │
│  - duration_ms: float           │
│  - stage_stats: List[StageStats]│
│  - errors: List[str]            │
└──────┬──────────────────────────┘
       ↓
┌─────────────────────────────────┐
│  Report Generation              │
│  - 文本格式报告                  │
│  - JSON 格式报告                 │
│  - 统计图表（GUI）               │
└─────────────────────────────────┘
```

---

## 关键设计模式

### 1. 策略模式（Strategy Pattern）

**应用**: IP 匿名化策略

```python
class HierarchicalAnonymizationStrategy:
    """层次化匿名化策略"""
    def anonymize_ip(self, ip_address):
        # 保留子网结构的匿名化
        pass
```

### 2. 模板方法模式（Template Method Pattern）

**应用**: StageBase 基类

```python
class StageBase(ABC):
    def process_file(self, input_path, output_path):
        # 模板方法定义处理流程
        self.initialize()
        result = self._do_process()
        self.cleanup()
        return result

    @abstractmethod
    def _do_process(self):
        # 子类实现具体处理逻辑
        pass
```

### 3. 观察者模式（Observer Pattern）

**应用**: 进度回调系统

```python
# 发布者
executor.run(input_path, output_path, progress_callback)

# 订阅者
def on_progress(event, data):
    if event == PipelineEvents.STAGE_END:
        update_progress_bar(data)
```

### 4. 工厂模式（Factory Pattern）

**应用**: Stage 创建

```python
def _build_pipeline(self, config):
    stages = []
    if config.get("remove_dupes", {}).get("enabled"):
        stages.append(DeduplicationStage(config["remove_dupes"]))
    if config.get("anonymize_ips", {}).get("enabled"):
        stages.append(AnonymizationStage(config["anonymize_ips"]))
    # ...
    return stages
```

### 5. 适配器模式（Adapter Pattern）

**应用**: GUI/CLI 配置适配

```python
class ConfigService:
    def create_options_from_gui(self, checkboxes):
        # GUI → ProcessingOptions
        pass

    def create_options_from_cli(self, args):
        # CLI → ProcessingOptions
        pass
```

---

## 错误处理机制

### 异常层次结构

```
Exception
└── PktMaskException (基础异常)
    ├── ConfigurationError (配置错误)
    ├── FileError (文件错误)
    │   ├── FileNotFoundError
    │   └── FilePermissionError
    ├── ProcessingError (处理错误)
    │   ├── StageError
    │   └── ValidationError
    └── ResourceError (资源错误)
        ├── MemoryError
        └── DiskSpaceError
```

### 错误恢复策略

```python
class StageBase:
    def process_file(self, input_path, output_path):
        retry_count = 0
        while retry_count < self.max_retry_attempts:
            try:
                return self._do_process(input_path, output_path)
            except RecoverableError as e:
                retry_count += 1
                self.logger.warning(f"Retry {retry_count}/{self.max_retry_attempts}")
                time.sleep(self.retry_delay_seconds)
            except FatalError as e:
                self.logger.error(f"Fatal error: {e}")
                raise
```

### 资源清理

```python
def run(self, input_path, output_path):
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 处理逻辑
            result = self._process_pipeline(input_path, output_path, temp_dir)
        except Exception as e:
            # 错误处理
            log_exception(e)
            raise
        finally:
            # 自动清理临时目录
            pass
    return result
```

---

## 性能优化

### 1. 内存管理

- **流式处理**: 逐包读取，避免一次性加载整个文件
- **临时文件**: 使用磁盘临时文件存储中间结果
- **资源池**: 复用对象，减少内存分配

### 2. 并发处理

- **阶段内并发**: 某些阶段支持多线程处理
- **文件级并发**: 批量处理时可并行处理多个文件（实验性）

### 3. 缓存策略

- **哈希缓存**: 去重阶段缓存已见过的哈希值
- **IP映射缓存**: 匿名化阶段缓存IP映射关系

---

## 测试策略

### 测试金字塔

```
        ┌─────────┐
        │  E2E    │  端到端测试
        │  Tests  │  - GUI 工作流
        └─────────┘  - CLI 命令
       ┌───────────┐
       │Integration│ 集成测试
       │   Tests   │ - 管道执行
       └───────────┘ - 服务交互
      ┌─────────────┐
      │    Unit     │ 单元测试
      │    Tests    │ - 单个函数
      └─────────────┘ - 类方法
```

### 测试覆盖

| 模块 | 测试类型 | 覆盖率目标 |
|------|---------|-----------|
| Core Pipeline | Unit + Integration | 90%+ |
| Stages | Unit + Integration | 85%+ |
| Services | Unit | 80%+ |
| GUI | Integration + E2E | 70%+ |
| CLI | Integration + E2E | 85%+ |

---

## 部署与打包

### 打包流程

```
Source Code
    ↓
[PyInstaller]
    ↓
├─ Windows (.exe)
├─ macOS (.app)
└─ Linux (binary)
```

### 配置文件

```
PktMask.spec (PyInstaller配置)
├─ 入口点: pktmask_launcher.py
├─ 隐藏导入: PyQt6, scapy
├─ 数据文件: config/, assets/
└─ 图标: assets/PktMask.ico
```

---

## 总结

PktMask 是一个设计良好、架构清晰的网络数据包处理工具，具有以下特点：

### ✅ 优势

1. **统一架构** - GUI 和 CLI 共享核心逻辑，确保一致性
2. **模块化设计** - 清晰的职责分离，易于维护和扩展
3. **类型安全** - 完整的类型注解，减少运行时错误
4. **错误恢复** - 完善的异常处理和资源管理
5. **可扩展性** - 易于添加新的处理阶段和协议支持
6. **双模块掩码** - Marker + Masker 架构，协议分析与处理分离

### 🎯 核心价值

- **安全性**: 有效移除敏感信息，保护隐私
- **可用性**: 保留分析价值，支持故障排查
- **易用性**: 图形界面友好，命令行灵活
- **可靠性**: 完善的测试和错误处理

### 🚀 未来方向

1. 支持更多协议（DNS, SMTP, etc.）
2. 插件化架构
3. Web 界面支持
4. 性能优化（大文件处理）
5. 云端处理支持


