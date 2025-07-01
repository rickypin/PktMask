# Enhanced MaskStage API 文档

> 版本：v1.0  
> 更新时间：2025-07-01 13:15  
> 状态：生产就绪 ✅

---

## 📖 概述

Enhanced MaskStage 是 PktMask 架构重构后的核心载荷掩码处理组件，提供智能协议识别和精确载荷掩码功能。它集成了 EnhancedTrimmer 的完整功能，同时提供更好的架构集成和维护性。

### 🎯 核心特性

- **双模式架构**：Enhanced Mode (智能处理) + Basic Mode (兼容降级)
- **多阶段处理**：TShark → PyShark → Scapy 三阶段智能流水线
- **优雅降级**：Enhanced Mode 失败时自动切换到 Basic Mode
- **完整统计**：详细的处理指标和性能监控
- **配置灵活**：支持各阶段独立配置和参数传递

---

## 🏗️ 架构设计

```
Enhanced MaskStage
├── Enhanced Mode (默认)
│   ├── MultiStageExecutor
│   │   ├── TSharkPreprocessor     (TCP流重组、IP碎片重组)
│   │   ├── EnhancedPySharkAnalyzer (协议识别、掩码表生成)
│   │   └── TcpPayloadMaskerAdapter (序列号匹配、精确掩码)
│   └── 完整统计与事件集成
└── Basic Mode (降级备选)
    ├── BlindPacketMasker         (传统配方掩码)
    └── 简化统计
```

---

## 📋 类参考

### `MaskStage`

**继承关系**: `StageBase`  
**模块路径**: `pktmask.core.pipeline.stages.mask_payload.stage`

智能载荷掩码处理阶段，集成 EnhancedTrimmer 的完整功能。

#### 构造函数

```python
def __init__(self, config: Optional[Dict[str, Any]] = None)
```

**参数:**
- `config` (Dict[str, Any], 可选): 配置字典

**配置字段:**
- `mode` (str): 处理模式，"enhanced" (默认) 或 "basic"
- `preserve_ratio` (float): 载荷保留比例 (0.0-1.0)
- `tls_strategy_enabled` (bool): 是否启用TLS策略
- `recipe_path` (str): 掩码配方文件路径 (Basic Mode)
- `tshark_*`: TShark预处理器配置
- `pyshark_*`: PyShark分析器配置
- `scapy_*`: Scapy适配器配置

**配置示例:**
```python
config = {
    "mode": "enhanced",
    "preserve_ratio": 0.3,
    "tls_strategy_enabled": True,
    "enable_tshark_preprocessing": True,
    "tshark_memory_limit": "512M",
    "pyshark_timeout": 300,
    "scapy_batch_size": 1000
}
```

---

### 🔧 核心方法

#### `initialize(config: Optional[Dict[str, Any]] = None) -> None`

初始化 Stage，创建处理器实例。

**参数:**
- `config` (Dict[str, Any], 可选): 运行时配置，会与构造函数配置合并

**行为:**
- Enhanced Mode: 创建并注册 MultiStageExecutor 三个阶段
- Basic Mode: 创建 BlindPacketMasker 实例
- 失败时触发降级到 Basic Mode

**异常:**
- 自动捕获并降级，不会抛出异常

---

#### `process_file(input_path: str | Path, output_path: str | Path) -> StageStats`

处理单个文件，应用载荷掩码。

**参数:**
- `input_path` (str | Path): 输入 PCAP/PCAPNG 文件路径
- `output_path` (str | Path): 输出处理后文件路径

**返回值:**
`StageStats` 对象，包含处理统计信息：
```python
StageStats(
    stage_name="MaskStage",
    packets_processed=1000,
    packets_modified=300,
    duration_ms=1250.5,
    extra_metrics={
        "enhanced_mode": True,
        "stages_count": 3,
        "success_rate": "100%",
        "pipeline_success": True,
        "multi_stage_processing": True,
        "intelligent_protocol_detection": True
    }
)
```

**处理模式:**
- **Enhanced Mode**: 使用 MultiStageExecutor 进行智能多阶段处理
- **Basic Mode**: 使用 BlindPacketMasker 进行传统配方掩码
- **Fallback Mode**: Enhanced Mode 失败时的降级处理

---

### 🔍 内部方法

#### `_initialize_enhanced_mode(config: Dict[str, Any]) -> None`

初始化增强模式组件。

**创建组件:**
1. MultiStageExecutor 实例
2. TSharkPreprocessor (Stage 0)
3. EnhancedPySharkAnalyzer (Stage 1) 
4. TcpPayloadMaskerAdapter (Stage 2)

**配置传播:**
- `_create_stage_config(stage_type, config)` 为每个阶段生成专用配置

---

#### `_initialize_basic_mode(config: Dict[str, Any]) -> None`

初始化基础模式组件。

**创建组件:**
- BlindPacketMasker 实例 (从配方文件)

---

#### `_process_with_enhanced_mode(input_path: Path, output_path: Path) -> StageStats`

使用 MultiStageExecutor 进行智能处理。

**处理流程:**
1. 调用 `_executor.execute_pipeline()`
2. 收集多阶段统计信息
3. 生成 Enhanced Mode 特有的指标
4. 失败时触发降级处理

---

#### `_process_with_basic_mode(input_path: Path, output_path: Path) -> StageStats`

使用 BlindPacketMasker 进行基础处理。

**处理流程:**
1. 读取数据包 (`rdpcap`)
2. 应用掩码 (`_masker.mask_packets`)
3. 写入结果 (`wrpcap`)
4. 收集统计信息

---

#### `_create_stage_config(stage_type: str, config: Dict[str, Any]) -> Dict[str, Any]`

为指定阶段创建专用配置。

**支持的阶段类型:**
- `"tshark"`: TShark预处理器配置
- `"pyshark"`: PyShark分析器配置  
- `"scapy"`: Scapy适配器配置

**配置映射:**
```python
# TShark 配置
"tshark": {
    "enable_tcp_reassembly": config.get("enable_tshark_preprocessing", True),
    "memory_limit": config.get("tshark_memory_limit", "256M"),
    "timeout": config.get("tshark_timeout", 300)
}

# PyShark 配置
"pyshark": {
    "enable_protocol_detection": config.get("enable_protocol_detection", True),
    "tls_strategy_enabled": config.get("tls_strategy_enabled", True),
    "timeout": config.get("pyshark_timeout", 300)
}

# Scapy 配置
"scapy": {
    "batch_size": config.get("scapy_batch_size", 1000),
    "enable_statistics": config.get("enable_statistics", True)
}
```

---

## 📊 统计指标

### Enhanced Mode 指标

```python
{
    "enhanced_mode": True,
    "stages_count": 3,
    "success_rate": "100%", 
    "pipeline_success": True,
    "multi_stage_processing": True,
    "intelligent_protocol_detection": True
}
```

### Basic Mode 指标

```python
{
    "enhanced_mode": False,
    "mode": "basic_masking",
    "recipe_entries": 15,
    "modified_packets_by_rule": {...}
}
```

### Fallback Mode 指标

```python
{
    "enhanced_mode": False,
    "mode": "fallback",
    "original_mode": "enhanced",
    "fallback_reason": "enhanced_mode_execution_failed",
    "graceful_degradation": True
}
```

---

## 🔧 集成指南

### 1. PipelineExecutor 集成

```python
# 配置 Pipeline
config = {
    "mask": {
        "enabled": True,
        "mode": "enhanced",
        "preserve_ratio": 0.3,
        "tls_strategy_enabled": True
    }
}

# 创建并运行 Pipeline
executor = PipelineExecutor(config)
result = executor.run(input_file, output_file)
```

### 2. 直接使用

```python
from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage

# 创建并配置 Stage
stage = MaskStage({
    "mode": "enhanced",
    "preserve_ratio": 0.3
})

# 初始化
stage.initialize()

# 处理文件
stats = stage.process_file("input.pcap", "output.pcap")
print(f"处理了 {stats.packets_processed} 个包，修改了 {stats.packets_modified} 个包")
```

### 3. 自定义配置

```python
# 高级配置示例
config = {
    "mode": "enhanced",
    "preserve_ratio": 0.2,
    "tls_strategy_enabled": True,
    
    # TShark 配置
    "enable_tshark_preprocessing": True,
    "tshark_memory_limit": "1G",
    "tshark_timeout": 600,
    
    # PyShark 配置  
    "enable_protocol_detection": True,
    "pyshark_timeout": 400,
    
    # Scapy 配置
    "scapy_batch_size": 2000,
    "enable_statistics": True
}

stage = MaskStage(config)
```

---

## ⚠️ 错误处理

### 1. 优雅降级机制

Enhanced MaskStage 实现了完整的优雅降级机制：

```
Enhanced Mode 失败
        ↓
自动切换到 Basic Mode 
        ↓
Basic Mode 失败
        ↓  
Fallback Mode (文件复制)
```

### 2. 常见错误场景

| 错误类型 | Enhanced Mode | Basic Mode | Fallback Mode |
|---------|---------------|------------|---------------|
| 模块导入失败 | ❌ → Basic | ✅ 继续 | N/A |
| 配置错误 | ❌ → Basic | ❌ → Fallback | ✅ 复制 |
| 文件读取失败 | ❌ → Basic | ❌ → Fallback | ❌ 抛异常 |
| 处理异常 | ❌ → Basic | ❌ → Fallback | ✅ 复制 |

### 3. 错误监控

通过 `extra_metrics` 监控错误和降级情况：

```python
if stats.extra_metrics.get("mode") == "fallback":
    print(f"降级原因: {stats.extra_metrics.get('fallback_reason')}")
    
if not stats.extra_metrics.get("enhanced_mode", False):
    print("未使用增强模式处理")
```

---

## 🚀 性能特征

### 1. 性能基准

| 指标 | Enhanced Mode | Basic Mode |
|------|---------------|------------|
| 初始化时间 | ~15ms | ~2ms |
| 处理吞吐量 | 4000-8500 pps | 10000+ pps |
| 内存开销 | 2.5MB/实例 | 0.8MB/实例 |
| 功能完整性 | 100% | 60% |

### 2. 扩展性

- **并发安全**: 多个实例可并发运行
- **内存管理**: 自动清理临时资源
- **配置热更新**: 支持运行时配置更新

### 3. 监控指标

```python
# 性能监控
duration = stats.duration_ms
throughput = stats.packets_processed / (duration / 1000)  # pps
efficiency = stats.packets_modified / stats.packets_processed  # 修改率

# 功能监控  
enhanced_mode_usage = stats.extra_metrics.get("enhanced_mode", False)
pipeline_success = stats.extra_metrics.get("pipeline_success", False)
stages_completed = stats.extra_metrics.get("stages_count", 0)
```

---

## 🔄 与 EnhancedTrimmer 对比

| 方面 | Enhanced MaskStage | EnhancedTrimmer |
|------|-------------------|-----------------|
| **架构集成** | ✅ 原生 Pipeline 集成 | ⚠️ 临时适配器 |
| **功能完整性** | ✅ 100% 对等 | ✅ 100% 完整 |
| **测试覆盖** | ✅ 28/28 测试通过 | ⚠️ 部分覆盖 |
| **维护性** | ✅ 标准化接口 | ⚠️ 独立维护 |
| **配置灵活性** | ✅ 分层配置系统 | ⚠️ 单一配置 |
| **错误处理** | ✅ 优雅降级机制 | ⚠️ 异常抛出 |
| **性能监控** | ✅ 详细指标 | ✅ 基础指标 |

**迁移建议**: Enhanced MaskStage 已完全就绪，建议逐步从 EnhancedTrimmer 迁移到 Enhanced MaskStage。

---

## 📚 相关文档

- [MaskStage 功能回归与演进方案](./MASK_STAGE_REINTEGRATION_PLAN.md)
- [Enhanced MaskStage 性能报告](../reports/enhanced_mask_stage_performance_report.json)  
- [PipelineExecutor API 文档](./PIPELINE_EXECUTOR_API.md)
- [多阶段执行器文档](./MULTI_STAGE_EXECUTOR.md)

---

## 🤝 贡献指南

### 1. 扩展支持

要添加新的处理模式：

```python
# 1. 扩展模式枚举
SUPPORTED_MODES = ["enhanced", "basic", "custom"]

# 2. 添加初始化方法
def _initialize_custom_mode(self, config: Dict[str, Any]) -> None:
    # 自定义初始化逻辑
    pass

# 3. 添加处理方法  
def _process_with_custom_mode(self, input_path: Path, output_path: Path) -> StageStats:
    # 自定义处理逻辑
    pass
```

### 2. 测试规范

新功能必须包含：
- 单元测试 (test_enhanced_mask_stage.py)
- 集成测试 (test_enhanced_mask_stage_integration.py)
- 性能基准测试

### 3. 文档更新

- API 变更需更新本文档
- 配置变更需更新示例
- 性能变更需更新基准数据

---

**版权声明**: © 2025 PktMask Core Team. 保留所有权利。 