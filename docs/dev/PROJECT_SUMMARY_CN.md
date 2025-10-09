# PktMask 项目解读总结

> **文档日期**: 2025-10-09  
> **项目版本**: v3.1+  
> **分析范围**: 完整代码库架构与数据流

---

## 📌 项目概览

**PktMask** 是一个专业的网络数据包安全处理工具，用于在保留分析价值的同时移除敏感信息，使网络专业人员能够安全地共享 PCAP/PCAPNG 文件。

### 核心价值主张

```
原始网络捕获 → [PktMask处理] → 安全可共享的数据
  ↓                              ↓
包含敏感信息                    移除敏感信息
- 真实IP地址                    - 匿名IP地址
- 明文载荷数据                  - 掩码载荷数据
- 重复数据包                    - 去重优化
```

---

## 🎯 三大核心功能

### 1. 🔄 Remove Dupes（数据包去重）

**技术实现**:
- 算法: SHA256 哈希字节级去重
- 实现类: `DeduplicationStage`
- 位置: `src/pktmask/core/pipeline/stages/deduplication_stage.py`

**处理逻辑**:
```python
for packet in pcap_file:
    hash_value = sha256(packet.raw_bytes)
    if hash_value not in seen_hashes:
        seen_hashes.add(hash_value)
        write_to_output(packet)
    else:
        skip_packet()  # 重复包
```

**效果**: 典型场景减少 30-50% 文件大小

---

### 2. 🎭 Anonymize IPs（IP地址匿名化）

**技术实现**:
- 策略: 层次化匿名化（HierarchicalAnonymizationStrategy）
- 实现类: `AnonymizationStage`
- 位置: `src/pktmask/core/pipeline/stages/anonymization_stage.py`

**处理逻辑**:
```python
for packet in pcap_file:
    if has_ip_layer(packet):
        src_ip = extract_source_ip(packet)
        dst_ip = extract_destination_ip(packet)
        
        # 应用匿名化策略（保留子网结构）
        anon_src = anonymize_strategy.anonymize(src_ip)
        anon_dst = anonymize_strategy.anonymize(dst_ip)
        
        # 重写IP字段
        packet.src = anon_src
        packet.dst = anon_dst
        recalculate_checksums(packet)
        write_to_output(packet)
```

**特点**:
- 保留子网结构（便于分析）
- 一致性映射（同一IP总是映射到同一匿名IP）
- 支持 IPv4 和 IPv6

---

### 3. 🛡️ Mask Payloads（载荷掩码）

**技术实现**: 双模块架构
- 实现类: `MaskingStage`
- 位置: `src/pktmask/core/pipeline/stages/masking_stage/`

#### 双模块架构详解

```
┌─────────────────────────────────────────────────────────┐
│                    MaskingStage                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────┐    ┌────────────────────┐   │
│  │  Marker 模块         │    │  Masker 模块       │   │
│  │  (协议分析器)        │    │  (载荷处理器)      │   │
│  ├──────────────────────┤    ├────────────────────┤   │
│  │ 工具: TShark         │    │ 工具: Scapy        │   │
│  │ 职责:                │    │ 职责:              │   │
│  │ - 解析协议结构       │    │ - 读取数据包       │   │
│  │ - 识别保留部分       │    │ - 应用保留规则     │   │
│  │ - 生成规则集         │    │ - 掩码敏感载荷     │   │
│  └──────────┬───────────┘    └────────┬───────────┘   │
│             │                         │               │
│             └──── KeepRuleSet ────────┘               │
│                  (TCP序列号规则)                       │
└─────────────────────────────────────────────────────────┘
```

**处理流程**:

```
Phase 1: Marker 分析
  Input PCAP → TShark 解析 → 识别协议字段 → 生成 KeepRuleSet
  
  KeepRuleSet 示例:
  {
    tcp_seq_12345: "keep",    # 保留（握手包）
    tcp_seq_12346: "mask",    # 掩码（应用数据）
    tcp_seq_12347: "keep",    # 保留（Alert包）
  }

Phase 2: Masker 应用
  Input PCAP → Scapy 读取 → 查询规则集 → 应用掩码 → Output PCAP
  
  for packet in pcap:
      tcp_seq = packet[TCP].seq
      action = keep_rules.get(tcp_seq)
      if action == "mask":
          packet.payload = b'\x00' * len(packet.payload)
      write_to_output(packet)
```

**支持协议**:
- TLS/SSL (默认)
- HTTP
- Auto-detect (自动检测)

---

## 🏗️ 架构设计

### 分层架构

PktMask 采用经典的分层架构，从上到下分为 5 层：

```
┌─────────────────────────────────────────────────────────┐
│ 1. 用户界面层 (UI Layer)                                 │
│    - GUI (PyQt6): 图形化界面，实时进度，可视化报告       │
│    - CLI (Typer): 命令行界面，批处理，脚本集成           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. 统一服务层 (Service Layer)                           │
│    - ConfigService: 配置构建与验证                       │
│    - PipelineService: 执行器管理                         │
│    - ProgressService: 进度管理                           │
│    - OutputService: 输出格式化                           │
│    - ReportService: 报告生成                             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. 核心处理层 (Core Layer)                              │
│    - PipelineExecutor: 统一执行引擎，阶段调度            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 4. 处理阶段层 (Stage Layer)                             │
│    - DeduplicationStage: SHA256 去重                    │
│    - AnonymizationStage: IP 匿名化                      │
│    - MaskingStage: 载荷掩码（双模块）                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 5. 基础设施层 (Infrastructure Layer)                    │
│    - Logging: 统一日志系统                               │
│    - Error Handling: 异常处理与恢复                      │
│    - Resource Management: 资源管理与清理                 │
└─────────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **统一接口**: GUI 和 CLI 共享相同的核心处理逻辑
2. **职责分离**: 每层专注特定功能，降低耦合
3. **可扩展性**: 易于添加新的处理阶段和协议
4. **类型安全**: 完整的类型注解，减少运行时错误
5. **错误恢复**: 完善的异常处理和资源清理

---

## 🔄 数据处理流程

### 单文件处理流程（简化版）

```
用户输入
  ↓
验证输入 → 构建配置 → 创建执行器
  ↓
检查输入文件 → 创建临时目录
  ↓
┌─────────────────────────────────────┐
│ Stage 1: DeduplicationStage         │
│ Input → 计算哈希 → 过滤重复 → Temp1 │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ Stage 2: AnonymizationStage         │
│ Temp1 → 提取IP → 匿名化 → Temp2     │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ Stage 3: MaskingStage               │
│ Temp2 → Marker分析 → Masker处理     │
│      → Output                       │
└─────────────────────────────────────┘
  ↓
收集统计 → 清理临时文件 → 生成报告
  ↓
输出结果
```

### 配置数据流转

```
GUI 复选框 ──┐
            ├──→ ProcessingOptions ──→ PipelineConfig ──→ PipelineExecutor
CLI 参数 ────┘

示例:
GUI: [✓] Remove Dupes, [✓] Anonymize IPs, [✓] Mask Payloads
  ↓
ProcessingOptions {
  enable_remove_dupes: true,
  enable_anonymize_ips: true,
  enable_mask_payloads: true,
  mask_protocol: "tls"
}
  ↓
PipelineConfig {
  "remove_dupes": {"enabled": true},
  "anonymize_ips": {"enabled": true},
  "mask_payloads": {
    "enabled": true,
    "protocol": "tls",
    "marker_config": {...},
    "masker_config": {...}
  }
}
  ↓
PipelineExecutor 创建 3 个 Stage 实例并顺序执行
```

---

## 🔑 关键类与接口

### 1. PipelineExecutor（核心执行器）

**位置**: `src/pktmask/core/pipeline/executor.py`

**核心方法**:
```python
class PipelineExecutor:
    def __init__(self, config: Dict):
        """根据配置动态装配 Stage 列表"""
        self.stages = self._build_pipeline(config)
    
    def run(self, input_path, output_path, progress_cb) -> ProcessResult:
        """执行完整处理管道"""
        # 1. 验证输入
        # 2. 创建临时目录
        # 3. 顺序执行各 Stage
        # 4. 聚合统计信息
        # 5. 清理资源
        # 6. 返回结果
```

### 2. StageBase（阶段基类）

**位置**: `src/pktmask/core/pipeline/base_stage.py`

**核心接口**:
```python
class StageBase(ABC):
    name: str  # 阶段名称
    
    @abstractmethod
    def initialize(self, config) -> bool:
        """初始化阶段"""
    
    @abstractmethod
    def process_file(self, input_path, output_path) -> StageStats:
        """处理单个文件（核心方法）"""
    
    # 可选的目录级方法
    def prepare_for_directory(self, directory, all_files):
        """目录级预处理"""
    
    def finalize_directory_processing(self):
        """目录级后处理"""
```

### 3. ConfigService（配置服务）

**位置**: `src/pktmask/services/config_service.py`

**核心方法**:
```python
class ConfigService:
    def create_options_from_gui(self, checkboxes) -> ProcessingOptions:
        """从 GUI 状态创建配置"""
    
    def create_options_from_cli(self, args) -> ProcessingOptions:
        """从 CLI 参数创建配置"""
    
    def build_pipeline_config(self, options) -> Dict:
        """构建管道配置字典"""
```

---

## 📊 数据模型

### ProcessingOptions（处理选项）

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

### StageStats（阶段统计）

```python
@dataclass
class StageStats:
    stage_name: str              # 阶段名称
    packets_processed: int       # 处理的数据包数
    packets_modified: int        # 修改的数据包数
    duration_ms: float           # 处理耗时（毫秒）
    extra_metrics: Dict          # 额外指标
```

### ProcessResult（处理结果）

```python
@dataclass
class ProcessResult:
    success: bool                # 是否成功
    input_file: str              # 输入文件路径
    output_file: Optional[str]   # 输出文件路径
    duration_ms: float           # 总耗时
    stage_stats: List[StageStats] # 各阶段统计
    errors: List[str]            # 错误列表
```

---

## 🛠️ 技术栈

| 技术 | 用途 |
|------|------|
| **Python 3.8+** | 主要编程语言 |
| **Scapy** | 数据包读写和处理 |
| **PyQt6** | GUI 框架 |
| **Typer** | CLI 框架 |
| **TShark** | 协议分析（外部工具） |
| **pytest** | 测试框架 |

---

## 📁 项目结构（简化版）

```
PktMask/
├── src/pktmask/              # 源代码
│   ├── __main__.py           # 入口点
│   ├── cli/                  # CLI 模块
│   ├── gui/                  # GUI 模块
│   ├── core/                 # 核心处理
│   │   └── pipeline/         # 管道系统
│   │       ├── executor.py   # 执行器
│   │       ├── base_stage.py # 阶段基类
│   │       └── stages/       # 处理阶段
│   ├── services/             # 服务层
│   ├── domain/               # 领域模型
│   ├── infrastructure/       # 基础设施
│   └── utils/                # 工具函数
├── tests/                    # 测试代码
├── docs/                     # 文档
└── config/                   # 配置文件
```

---

## ✨ 设计亮点

### 1. 统一的 GUI/CLI 接口

通过服务层抽象，GUI 和 CLI 共享相同的核心处理逻辑，确保功能一致性：

```
GUI → ConfigService → PipelineExecutor → Stages
CLI → ConfigService → PipelineExecutor → Stages
                ↑
            相同的核心逻辑
```

### 2. 双模块掩码架构

Marker 和 Masker 分离设计，实现关注点分离：
- **Marker**: 专注协议分析（TShark）
- **Masker**: 专注载荷处理（Scapy）
- **优势**: 易于扩展新协议，独立测试

### 3. 资源管理

使用 Python 上下文管理器自动清理临时文件：

```python
with tempfile.TemporaryDirectory() as temp_dir:
    # 处理逻辑
    process_pipeline(input, output, temp_dir)
    # 自动清理临时目录
```

### 4. 事件驱动的进度报告

通过回调机制实现解耦的进度报告：

```python
def on_progress(event, data):
    if event == PipelineEvents.STAGE_END:
        update_ui(data)

executor.run(input, output, progress_callback=on_progress)
```

---

## 🎓 总结

PktMask 是一个架构清晰、设计优良的专业工具，具有以下特点：

### 核心优势
- ✅ **统一架构**: GUI/CLI 共享核心逻辑
- ✅ **模块化设计**: 清晰的职责分离
- ✅ **类型安全**: 完整的类型注解
- ✅ **可扩展性**: 易于添加新功能
- ✅ **错误恢复**: 完善的异常处理

### 技术特色
- 🔧 双模块掩码架构（Marker + Masker）
- 🔧 层次化 IP 匿名化策略
- 🔧 SHA256 字节级去重
- 🔧 事件驱动的进度报告
- 🔧 自动资源管理

### 应用价值
- 🎯 安全共享网络数据
- 🎯 保护隐私和敏感信息
- 🎯 满足合规要求
- 🎯 支持故障排查和分析

---

**文档生成**: 基于完整代码库分析  
**可视化图表**: 参见 Mermaid 流程图（已生成）  
**详细文档**: `docs/dev/PROJECT_ANALYSIS_AND_FLOW.md`

