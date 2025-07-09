# PktMask 抽象层次简化重构计划

> **版本**: v2.0
> **创建时间**: 2025-07-09
> **更新时间**: 2025-07-09
> **作者**: AI 架构师
> **目标**: 消除过度复杂的抽象层次，针对桌面应用特点优化架构

---

## 🎯 重构目标

### 核心问题分析
1. **多层适配器嵌套**：`MaskPayloadStage → PipelineProcessorAdapter → MaskPayloadProcessor → TSharkEnhancedMaskProcessor`
   - 4层嵌套调用，每层仅做简单转发
   - 增加调试难度和性能开销

2. **冗余处理器包装**：`MaskPayloadProcessor` 仅是 `TSharkEnhancedMaskProcessor` 的代理
   - 无实际业务价值的包装层
   - 增加维护成本和认知负担

3. **过度设计事件系统**：`EventCoordinator + EventDataAdapter + 13种事件数据模型`
   - Pydantic验证对桌面应用过度
   - 复杂的双向转换机制
   - 启动时间和内存开销

### 桌面应用特点考虑
- **用户体验优先**：启动速度和响应性比复杂验证更重要
- **简单维护**：小团队开发，需要直观易懂的架构
- **稳定性要求**：避免过度工程化，减少故障点

### 预期效果
- **代码复杂度降低 35%**：移除冗余适配器和包装类
- **启动时间改善 20%**：减少初始化开销（桌面应用关键指标）
- **内存使用优化 15%**：移除Pydantic验证和中间对象
- **可维护性提升 40%**：简化调用链和依赖关系

---

## 📋 分阶段实施计划

### 阶段1：处理器层简化（Week 1）
**目标**：彻底移除冗余包装，建立直接集成基础

#### 1.1 完全移除 MaskPayloadProcessor（Day 1-2）
- **任务**：直接删除 `MaskPayloadProcessor` 类，无需合并
- **理由**：该类仅为代理包装，无实际业务价值
- **影响范围**：
  - 删除 `src/pktmask/core/processors/masking_processor.py`
  - 更新所有导入引用
- **验证方式**：运行现有单元测试，确保功能不变

#### 1.2 简化 PipelineProcessorAdapter（Day 3-4）
- **任务**：创建轻量级适配器，专注桌面应用需求
- **优化重点**：
  - 移除复杂的错误转换逻辑
  - 简化统计数据收集
  - 优化内存使用
- **影响范围**：`src/pktmask/adapters/processor_adapter.py`
- **验证方式**：GUI响应性测试 + 集成测试

#### 1.3 更新调用点和性能优化（Day 5）
- **任务**：更新所有调用点，优化桌面应用性能
- **影响范围**：`src/pktmask/core/pipeline/stages/mask_payload/stage.py`
- **性能优化**：
  - 减少对象创建
  - 优化导入时间
  - 简化初始化流程
- **验证方式**：启动时间测试 + 端到端功能测试

### 阶段2：事件系统简化（Week 2）
**目标**：针对桌面应用优化事件系统，提升响应性

#### 2.1 设计桌面应用优化的事件结构（Day 1-2）
- **任务**：用简单 `dataclass` 替代复杂 Pydantic 模型
- **设计原则**：
  - 无运行时验证开销
  - 简单的字典转换
  - 最小内存占用
- **影响范围**：`src/pktmask/domain/models/pipeline_event_data.py`
- **验证方式**：启动时间测试 + 事件传递功能测试

#### 2.2 简化 EventCoordinator（Day 3-4）
- **任务**：移除双向转换机制，统一使用简化格式
- **优化重点**：
  - 移除 Pydantic 验证
  - 简化信号发射逻辑
  - 减少内存分配
- **影响范围**：`src/pktmask/gui/managers/event_coordinator.py`
- **验证方式**：GUI响应性测试 + 内存使用监控

#### 2.3 移除 EventDataAdapter（Day 5）
- **任务**：完全移除适配器，统一事件格式
- **理由**：桌面应用无需复杂的格式转换
- **影响范围**：
  - 删除 `src/pktmask/adapters/event_adapter.py`
  - 更新所有事件发射点
- **验证方式**：GUI管理器通信测试 + 性能基准测试

### 阶段3：适配器层消除（Week 3）
**目标**：实现 Stage 与 Processor 的直接集成

#### 3.1 设计统一接口（Day 1-2）
- **任务**：定义 `ProcessorStage` 基类，统一 Stage 和 Processor 接口
- **影响范围**：新建 `src/pktmask/core/pipeline/processor_stage.py`
- **验证方式**：接口兼容性测试

#### 3.2 重构 MaskPayloadStage（Day 3-4）
- **任务**：让 `MaskPayloadStage` 直接继承 `ProcessorStage`
- **影响范围**：`src/pktmask/core/pipeline/stages/mask_payload/stage.py`
- **验证方式**：掩码功能完整性测试

#### 3.3 移除 PipelineProcessorAdapter（Day 5）
- **任务**：完全移除适配器，使用直接集成
- **影响范围**：`src/pktmask/adapters/processor_adapter.py`
- **验证方式**：完整管道执行测试

### 阶段4：清理和优化（Week 4）
**目标**：清理遗留代码，优化性能

#### 4.1 代码清理（Day 1-2）
- **任务**：移除废弃的文件和导入
- **影响范围**：全项目清理
- **验证方式**：静态代码分析

#### 4.2 性能优化（Day 3-4）
- **任务**：优化数据流转，减少不必要的对象创建
- **影响范围**：核心处理流程
- **验证方式**：性能基准测试

#### 4.3 文档更新（Day 5）
- **任务**：更新架构文档和使用指南
- **影响范围**：`docs/` 目录
- **验证方式**：文档审查

---

## 🔧 技术实施细节

### 统一接口设计

```python
class ProcessorStage(ABC):
    """统一的处理器阶段基类"""
    
    @abstractmethod
    def process_file(self, input_path: str, output_path: str) -> ProcessResult:
        """处理文件的核心方法"""
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化处理器"""
        pass
    
    def get_required_tools(self) -> List[str]:
        """获取所需工具列表"""
        return []
```

### 桌面应用优化的事件数据结构

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

@dataclass
class SimpleEvent:
    """桌面应用优化的事件数据结构

    设计原则：
    - 无运行时验证开销
    - 最小内存占用
    - 简单的序列化/反序列化
    """
    type: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "info"

    def to_dict(self) -> dict:
        """转换为字典，用于GUI显示"""
        return {
            'type': self.type,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SimpleEvent':
        """从字典创建事件"""
        return cls(
            type=data['type'],
            message=data['message'],
            data=data.get('data', {}),
            severity=data.get('severity', 'info')
        )
```

### 桌面应用优化的直接集成示例

```python
class MaskPayloadStage(ProcessorStage):
    """桌面应用优化的掩码处理阶段

    特点：
    - 直接集成，无中间包装
    - 延迟初始化，提升启动速度
    - 简化错误处理
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._processor: Optional[TSharkEnhancedMaskProcessor] = None
        self._initialized = False

    def initialize(self) -> bool:
        """延迟初始化，优化启动时间"""
        if self._initialized:
            return True

        try:
            self._processor = TSharkEnhancedMaskProcessor(self.config)
            self._initialized = self._processor.initialize()
            return self._initialized
        except Exception as e:
            logger.error(f"MaskPayloadStage initialization failed: {e}")
            return False

    def process_file(self, input_path: str, output_path: str) -> ProcessResult:
        """直接处理，无适配器开销"""
        if not self._initialized and not self.initialize():
            return ProcessResult(success=False, error="Initialization failed")

        return self._processor.process_file(input_path, output_path)

    def get_required_tools(self) -> List[str]:
        """获取所需工具"""
        return ['tshark', 'scapy']
```

---

## ✅ 验证策略

### 桌面应用专项测试

#### 自动化测试
- **单元测试**：每个阶段完成后运行相关单元测试
- **集成测试**：验证组件间的正确集成
- **端到端测试**：确保完整功能链路正常
- **GUI响应性测试**：验证界面操作的流畅性

#### 桌面应用性能基准
- **启动时间**：应用冷启动到界面可用的时间（关键指标）
- **内存使用**：
  - 启动时内存占用
  - 处理过程中内存峰值
  - 内存泄漏检测
- **处理速度**：使用标准测试文件测量处理时间
- **GUI响应性**：界面操作响应时间

#### 功能验证
- **GUI功能**：
  - 所有界面元素正常显示
  - 用户交互响应及时
  - 进度显示准确
- **CLI功能**：验证命令行接口正常
- **错误处理**：
  - 用户友好的错误提示
  - 优雅的降级处理
  - 系统稳定性保证

#### 用户体验验证
- **操作流畅性**：拖拽、点击等操作的响应速度
- **资源占用**：CPU和内存使用的合理性
- **稳定性**：长时间运行的稳定性测试

---

## 🚨 风险控制

### 回滚策略
- **分支管理**：每个阶段在独立分支进行
- **备份机制**：重要文件变更前创建备份
- **渐进合并**：逐步合并到主分支

### 兼容性保证
- **接口保持**：保持公共API不变
- **配置兼容**：确保现有配置文件仍可用
- **数据格式**：保持输入输出格式不变

### 质量保证
- **代码审查**：每个阶段完成后进行代码审查
- **测试覆盖**：确保测试覆盖率不降低
- **文档同步**：及时更新相关文档

---

## 📊 成功指标

### 量化指标（桌面应用优化）
- **代码行数减少**：目标 35%（更激进的简化）
- **文件数量减少**：目标 30%
- **依赖关系简化**：目标 40%
- **启动时间改善**：目标 20%（桌面应用关键指标）
- **内存使用优化**：目标 15%
- **处理性能提升**：目标 10-15%

### 质量指标
- **测试通过率**：100%
- **代码覆盖率**：≥80%
- **静态分析**：0 严重问题
- **文档完整性**：100%

### 桌面应用专项指标
- **GUI响应时间**：所有操作 < 100ms
- **内存稳定性**：长时间运行无内存泄漏
- **错误恢复**：所有错误都有用户友好提示
- **资源占用**：空闲时 CPU < 1%

---

## 📅 时间表

| 阶段 | 时间 | 里程碑 | 负责人 |
|------|------|--------|--------|
| 阶段1 | Week 1 | 处理器层简化完成 | 开发团队 |
| 阶段2 | Week 2 | 事件系统简化完成 | 开发团队 |
| 阶段3 | Week 3 | 适配器层消除完成 | 开发团队 |
| 阶段4 | Week 4 | 清理优化完成 | 开发团队 |

**总计**：4周完成整体重构

---

## 📝 后续计划

### 短期目标（1-2个月）
- 监控重构后的系统稳定性
- 收集用户反馈
- 进行必要的微调

### 长期目标（3-6个月）
- 基于简化架构开发新功能
- 进一步优化性能
- 扩展协议支持能力

---

## 🛠️ 详细实施指南

### 阶段1详细步骤

#### 1.1 完全移除 MaskPayloadProcessor 包装

**步骤1：分析依赖关系和性能影响**
```bash
# 查找所有使用 MaskPayloadProcessor 的地方
grep -r "MaskPayloadProcessor" src/ --include="*.py"
grep -r "masking_processor" src/ --include="*.py"

# 分析启动时间影响
python -c "
import time
start = time.time()
from pktmask.core.processors.masking_processor import MaskPayloadProcessor
print(f'Import time: {(time.time() - start) * 1000:.2f}ms')
"
```

**步骤2：创建自动化迁移脚本**
```python
# scripts/migration/remove_masking_processor_wrapper.py
import os
import re
from pathlib import Path

def migrate_masking_processor_usage():
    """自动化迁移 MaskPayloadProcessor 到 TSharkEnhancedMaskProcessor"""

    # 查找所有Python文件
    for py_file in Path('src').rglob('*.py'):
        content = py_file.read_text()

        # 替换导入语句
        content = re.sub(
            r'from pktmask\.core\.processors\.masking_processor import MaskPayloadProcessor',
            'from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor',
            content
        )

        # 替换类名使用
        content = re.sub(r'\bMaskPayloadProcessor\b', 'TSharkEnhancedMaskProcessor', content)

        py_file.write_text(content)
        print(f"Migrated: {py_file}")

if __name__ == "__main__":
    migrate_masking_processor_usage()
```

**步骤3：验证迁移效果**
```bash
# 验证没有遗留引用
grep -r "MaskPayloadProcessor" src/ --include="*.py" || echo "Migration complete"

# 测试启动时间改善
python scripts/performance/measure_startup_time.py
```

#### 1.2 简化 PipelineProcessorAdapter

**目标架构**：
```python
class SimplifiedProcessorAdapter(StageBase):
    """简化的处理器适配器 - 仅处理必要的接口转换"""

    def __init__(self, processor_class: Type[BaseProcessor], config: Dict[str, Any]):
        self._processor = processor_class(config)
        self._config = config

    def process_file(self, input_path: str, output_path: str) -> StageStats:
        # 直接调用处理器，最小化转换逻辑
        result = self._processor.process_file(input_path, output_path)
        return self._convert_result(result)

    def _convert_result(self, result: ProcessorResult) -> StageStats:
        """最小化的结果转换"""
        return StageStats(
            stage_name=self._processor.__class__.__name__,
            packets_processed=result.stats.get('packets_processed', 0),
            packets_modified=result.stats.get('packets_modified', 0),
            duration_ms=result.stats.get('duration_ms', 0.0)
        )
```

### 阶段2详细步骤

#### 2.1 统一事件数据结构

**桌面应用优化的事件系统设计**：
```python
# src/pktmask/core/events/desktop_events.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

@dataclass
class DesktopEvent:
    """桌面应用优化的事件数据结构

    设计原则：
    - 最小内存占用
    - 快速创建和访问
    - 无运行时验证开销
    - 简单的序列化
    """
    type: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "info"

    def to_dict(self) -> dict:
        """快速转换为字典，用于GUI显示"""
        return {
            'type': self.type,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity
        }

    @classmethod
    def create_fast(cls, event_type: str, message: str, **data) -> 'DesktopEvent':
        """快速创建事件，优化桌面应用性能"""
        return cls(
            type=event_type,
            message=message,
            data=data
        )

    def is_error(self) -> bool:
        """快速错误检查"""
        return self.severity in ('error', 'critical')

    def get_display_text(self) -> str:
        """获取用户友好的显示文本"""
        timestamp_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{timestamp_str}] {self.message}"

# 常用事件类型常量（避免字符串拼写错误）
class EventTypes:
    PIPELINE_START = "pipeline_start"
    PIPELINE_END = "pipeline_end"
    FILE_START = "file_start"
    FILE_END = "file_end"
    STEP_START = "step_start"
    STEP_END = "step_end"
    ERROR = "error"
    LOG = "log"
    GUI_UPDATE = "gui_update"
    PROGRESS_UPDATE = "progress_update"
```

#### 2.2 简化 EventCoordinator

**桌面应用优化的事件协调器**：
```python
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, List, Callable, Set
from collections import defaultdict
import logging

class DesktopEventCoordinator(QObject):
    """桌面应用优化的事件协调器

    优化特点：
    - 最小化信号开销
    - 快速事件分发
    - 内存友好的订阅管理
    - 异常隔离
    """

    # 优化的信号定义
    event_emitted = pyqtSignal(object)  # DesktopEvent
    error_occurred = pyqtSignal(str)    # 错误事件专用信号
    progress_updated = pyqtSignal(int)  # 进度更新专用信号

    def __init__(self):
        super().__init__()
        self._subscribers: Dict[str, Set[Callable]] = defaultdict(set)
        self._logger = logging.getLogger(__name__)

        # 性能优化：预分配常用事件类型
        for event_type in [EventTypes.PIPELINE_START, EventTypes.FILE_START,
                          EventTypes.STEP_START, EventTypes.ERROR]:
            self._subscribers[event_type] = set()

    def subscribe(self, event_type: str, callback: Callable):
        """订阅事件（使用set避免重复订阅）"""
        self._subscribers[event_type].add(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """取消订阅"""
        self._subscribers[event_type].discard(callback)

    def emit_event(self, event: DesktopEvent):
        """高性能事件发布"""
        # 快速路径：错误事件
        if event.is_error():
            self.error_occurred.emit(event.message)

        # 快速路径：进度事件
        if event.type == EventTypes.PROGRESS_UPDATE:
            progress = event.data.get('progress', 0)
            self.progress_updated.emit(progress)

        # 调用订阅者（异常隔离）
        for callback in self._subscribers[event.type]:
            try:
                callback(event)
            except Exception as e:
                self._logger.error(f"Event callback error: {e}")

        # 发出通用信号
        self.event_emitted.emit(event)

    def emit_fast(self, event_type: str, message: str, **data):
        """快速事件发射（减少对象创建）"""
        event = DesktopEvent.create_fast(event_type, message, **data)
        self.emit_event(event)

    def clear_subscribers(self):
        """清理所有订阅者（内存管理）"""
        self._subscribers.clear()
```

### 阶段3详细步骤

#### 3.1 统一接口设计

**ProcessorStage 基类**：
```python
# src/pktmask/core/pipeline/processor_stage.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pathlib import Path

class ProcessorStage(ABC):
    """统一的处理器阶段基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._initialized = False

    @abstractmethod
    def process_file(self, input_path: str, output_path: str) -> 'ProcessResult':
        """处理文件的核心方法"""
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """初始化处理器"""
        pass

    def get_required_tools(self) -> List[str]:
        """获取所需工具列表"""
        return []

    @property
    def name(self) -> str:
        """获取处理器名称"""
        return self.__class__.__name__

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
```

#### 3.2 重构 MaskPayloadStage

**新的 MaskPayloadStage**：
```python
class MaskPayloadStage(ProcessorStage):
    """直接集成的掩码处理阶段"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._tshark_processor = None

    def initialize(self) -> bool:
        """初始化TShark处理器"""
        try:
            from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
            self._tshark_processor = TSharkEnhancedMaskProcessor(self.config)
            self._initialized = self._tshark_processor.initialize()
            return self._initialized
        except Exception as e:
            logger.error(f"Failed to initialize MaskPayloadStage: {e}")
            return False

    def process_file(self, input_path: str, output_path: str) -> ProcessResult:
        """直接调用TShark处理器"""
        if not self._initialized:
            raise RuntimeError("MaskPayloadStage not initialized")

        return self._tshark_processor.process_file(input_path, output_path)

    def get_required_tools(self) -> List[str]:
        """获取所需工具"""
        return ['tshark', 'scapy']
```

---

## 🧪 测试策略详细说明

### 单元测试更新

**测试文件结构**：
```
tests/
├── unit/
│   ├── test_simplified_processor_adapter.py
│   ├── test_simple_event_coordinator.py
│   ├── test_processor_stage.py
│   └── test_mask_payload_stage_direct.py
├── integration/
│   ├── test_pipeline_without_adapters.py
│   └── test_event_system_simplified.py
└── e2e/
    ├── test_complete_workflow_simplified.py
    └── test_performance_comparison.py
```

**关键测试用例**：
```python
# tests/unit/test_mask_payload_stage_direct.py
class TestMaskPayloadStageDirect:
    """测试直接集成的掩码处理阶段"""

    def test_direct_processing(self):
        """测试直接处理功能"""
        config = {"mode": "processor_adapter"}
        stage = MaskPayloadStage(config)
        assert stage.initialize()

        result = stage.process_file("input.pcap", "output.pcap")
        assert result.success

    def test_no_adapter_overhead(self):
        """测试没有适配器开销"""
        # 性能对比测试
        pass
```

### 性能基准测试

**桌面应用性能基准测试脚本**：
```python
# scripts/performance/desktop_app_benchmark.py
import time
import psutil
import gc
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    startup_time: float
    memory_usage: int
    processing_time: float
    gui_response_time: float
    cpu_usage: float

class DesktopAppBenchmark:
    """桌面应用性能基准测试"""

    def __init__(self):
        self.process = psutil.Process()
        self.baseline_metrics: Dict[str, PerformanceMetrics] = {}

    @contextmanager
    def measure_time(self):
        """时间测量上下文管理器"""
        start = time.perf_counter()
        yield
        end = time.perf_counter()
        return end - start

    def measure_startup_time(self) -> float:
        """测量应用启动时间"""
        start_time = time.perf_counter()

        # 模拟应用启动过程
        import pktmask
        from pktmask.gui.main_window import MainWindow
        from PyQt6.QtWidgets import QApplication

        app = QApplication([])
        window = MainWindow()
        window.show()

        startup_time = time.perf_counter() - start_time

        # 清理
        window.close()
        app.quit()

        return startup_time

    def measure_memory_usage(self) -> int:
        """测量内存使用"""
        gc.collect()  # 强制垃圾回收
        return self.process.memory_info().rss

    def measure_gui_responsiveness(self) -> float:
        """测量GUI响应性"""
        from PyQt6.QtWidgets import QApplication, QPushButton
        from PyQt6.QtCore import QTimer

        app = QApplication([])
        button = QPushButton("Test")

        response_times = []

        def on_click():
            end_time = time.perf_counter()
            response_times.append(end_time - click_start_time)

        button.clicked.connect(on_click)

        # 模拟多次点击
        for _ in range(10):
            click_start_time = time.perf_counter()
            button.click()

        app.quit()
        return sum(response_times) / len(response_times) if response_times else 0

    def run_comprehensive_benchmark(self, label: str) -> PerformanceMetrics:
        """运行综合性能基准测试"""
        print(f"Running benchmark: {label}")

        # 启动时间测试
        startup_time = self.measure_startup_time()
        print(f"  Startup time: {startup_time:.3f}s")

        # 内存使用测试
        memory_usage = self.measure_memory_usage()
        print(f"  Memory usage: {memory_usage / 1024 / 1024:.1f}MB")

        # GUI响应性测试
        gui_response = self.measure_gui_responsiveness()
        print(f"  GUI response: {gui_response * 1000:.1f}ms")

        # CPU使用率测试
        cpu_usage = self.process.cpu_percent(interval=1)
        print(f"  CPU usage: {cpu_usage:.1f}%")

        metrics = PerformanceMetrics(
            startup_time=startup_time,
            memory_usage=memory_usage,
            processing_time=0,  # 待实现
            gui_response_time=gui_response,
            cpu_usage=cpu_usage
        )

        self.baseline_metrics[label] = metrics
        return metrics

    def compare_metrics(self, before_label: str, after_label: str):
        """对比性能指标"""
        before = self.baseline_metrics[before_label]
        after = self.baseline_metrics[after_label]

        print(f"\n=== Performance Comparison: {before_label} vs {after_label} ===")

        # 启动时间对比
        startup_improvement = (before.startup_time - after.startup_time) / before.startup_time * 100
        print(f"Startup time: {before.startup_time:.3f}s -> {after.startup_time:.3f}s ({startup_improvement:+.1f}%)")

        # 内存使用对比
        memory_improvement = (before.memory_usage - after.memory_usage) / before.memory_usage * 100
        print(f"Memory usage: {before.memory_usage/1024/1024:.1f}MB -> {after.memory_usage/1024/1024:.1f}MB ({memory_improvement:+.1f}%)")

        # GUI响应性对比
        gui_improvement = (before.gui_response_time - after.gui_response_time) / before.gui_response_time * 100
        print(f"GUI response: {before.gui_response_time*1000:.1f}ms -> {after.gui_response_time*1000:.1f}ms ({gui_improvement:+.1f}%)")

if __name__ == "__main__":
    benchmark = DesktopAppBenchmark()

    # 运行基准测试
    benchmark.run_comprehensive_benchmark("before_refactor")
    # ... 执行重构 ...
    benchmark.run_comprehensive_benchmark("after_refactor")

    # 对比结果
    benchmark.compare_metrics("before_refactor", "after_refactor")
```

---

## 📋 检查清单

### 阶段1完成检查
- [ ] MaskPayloadProcessor 所有引用已更新
- [ ] PipelineProcessorAdapter 已简化
- [ ] 单元测试全部通过
- [ ] 集成测试验证正常
- [ ] 性能无明显下降

### 阶段2完成检查
- [ ] 新的 SimpleEvent 系统已实现
- [ ] EventCoordinator 已简化
- [ ] EventDataAdapter 已移除
- [ ] GUI事件响应正常
- [ ] 事件传递功能完整

### 阶段3完成检查
- [ ] ProcessorStage 基类已实现
- [ ] MaskPayloadStage 已重构
- [ ] 适配器层已移除
- [ ] 端到端测试通过
- [ ] 所有功能正常工作

### 阶段4完成检查
- [ ] 废弃代码已清理
- [ ] 性能已优化
- [ ] 文档已更新
- [ ] 代码质量检查通过
- [ ] 最终验证完成

---

*本文档将随着重构进展持续更新*
