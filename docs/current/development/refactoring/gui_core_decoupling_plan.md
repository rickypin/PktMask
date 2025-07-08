# GUI 与核心层解耦重构计划

## 1. 问题概述

### 1.1 当前问题
- `src/pktmask/gui/managers/pipeline_manager.py` 和 `src/pktmask/gui/main_window.py` 直接导入并使用 `pktmask.core.pipeline` 的内部实现类
- GUI 层直接创建和操作 `PipelineExecutor` 对象，违反了分层架构原则
- 紧密耦合导致核心逻辑变更时必须同步修改 GUI 代码

### 1.2 影响范围
- pipeline_manager.py: 第14行导入，第113-114行直接创建 PipelineExecutor
- main_window.py: 第25行导入 Pipeline
- NewPipelineThread 类直接持有和操作 executor 对象

## 2. 重构目标

### 2.1 核心目标
- **解耦 GUI 和核心逻辑**：GUI 只通过服务接口与核心交互
- **保持简洁**：避免过度工程化，适合桌面应用的轻量级架构
- **最小化改动**：保持现有功能不变，重点在接口抽象

### 2.2 设计原则
- 使用简单的服务函数而非复杂的类层次
- 保持 Qt 信号/槽机制的使用方式不变
- 复用现有的事件系统（PipelineEvents）

## 3. 具体重构方案

### 3.1 新增服务层

在 `src/pktmask/services/pipeline_service.py` 创建服务接口：

```python
"""
Pipeline 服务接口
提供 GUI 与核心管道的解耦接口
"""
from typing import Dict, Callable, Optional
from pktmask.core.events import PipelineEvents

def create_pipeline_executor(config: Dict) -> object:
    """
    创建管道执行器
    
    Args:
        config: 管道配置字典，包含各阶段的启用状态和参数
        
    Returns:
        执行器对象（对 GUI 不透明）
    """
    from pktmask.core.pipeline.executor import PipelineExecutor
    return PipelineExecutor(config)

def process_directory(
    executor: object,
    input_dir: str,
    output_dir: str,
    progress_callback: Callable[[PipelineEvents, Dict], None],
    is_running_check: Callable[[], bool]
) -> None:
    """
    处理目录中的所有 PCAP 文件
    
    Args:
        executor: 执行器对象
        input_dir: 输入目录路径
        output_dir: 输出目录路径
        progress_callback: 进度回调函数
        is_running_check: 检查是否继续运行的函数
    """
    # 实现目录遍历和文件处理逻辑
    # 从 NewPipelineThread._run_directory_processing 迁移过来

def stop_pipeline(executor: object) -> None:
    """停止管道执行"""
    # 如果 executor 有 stop 方法，调用它
    pass
```

### 3.2 重构 PipelineManager

修改 `pipeline_manager.py`：

```python
# 移除直接导入
# from pktmask.core.pipeline import Pipeline
# from pktmask.core.pipeline.executor import PipelineExecutor

# 改为导入服务
from pktmask.services import pipeline_service

# 在 start_pipeline_processing 方法中：
# 原代码：
# executor = PipelineExecutor(config)
# 改为：
executor = pipeline_service.create_pipeline_executor(config)
```

### 3.3 重构线程类

创建新的线程类 `ServicePipelineThread`，不直接依赖核心类：

```python
class ServicePipelineThread(QThread):
    """使用服务接口的处理线程"""
    progress_signal = pyqtSignal(PipelineEvents, dict)
    
    def __init__(self, executor: object, base_dir: str, output_dir: str):
        super().__init__()
        self._executor = executor  # 不需要知道具体类型
        self._base_dir = base_dir
        self._output_dir = output_dir
        self.is_running = True
    
    def run(self):
        try:
            pipeline_service.process_directory(
                self._executor,
                self._base_dir,
                self._output_dir,
                self._emit_progress,
                lambda: self.is_running
            )
        except Exception as e:
            self.progress_signal.emit(PipelineEvents.ERROR, {'message': str(e)})
    
    def _emit_progress(self, event_type: PipelineEvents, data: dict):
        self.progress_signal.emit(event_type, data)
    
    def stop(self):
        self.is_running = False
        pipeline_service.stop_pipeline(self._executor)
```

### 3.4 配置构建器

可选：为了进一步解耦，可以将配置构建逻辑也移到服务层：

```python
# 在 pipeline_service.py 中添加
 def build_pipeline_config(
    enable_anon: bool,
    enable_dedup: bool, 
    enable_mask: bool
) -> Dict:
    """根据功能开关构建管道配置"""
    config: Dict[str, Dict] = {}
    if enable_anon:
        config["anon"] = {"enabled": True}
    if enable_dedup:
        config["dedup"] = {"enabled": True}
    if enable_mask:
        config["mask"] = {
            "enabled": True,
            "mode": "processor_adapter"
        }
    return config
```

### 3.5 服务接口补充
为了让 GUI 获得更多运行时信息，服务层还应提供：

```python
from typing import Any, Dict, Tuple, Optional

class PipelineServiceError(Exception):
    """服务层基础异常"""
    pass

class ConfigurationError(PipelineServiceError):
    """配置无效或缺失时抛出"""
    pass

# ---- 新接口 ----

def get_pipeline_status(executor: object) -> Dict[str, Any]:
    """返回当前执行器的统计信息，例如已处理文件数等"""
    ...

def validate_config(config: Dict) -> Tuple[bool, Optional[str]]:
    """在真正创建执行器前验证配置"""
    ...
```

### 3.6 异常与日志策略
1. 所有服务层函数捕获核心层异常后统一包装为 `PipelineServiceError` 子类再向外抛出。
2. 统一使用 `infrastructure.logging` 提供的 logger，日志前缀增加 `[Service]` 方便区分。

### 3.7 向后兼容与迁移路径
| 版本 | 措施 |
|------|------|
| v0.2.x | 新旧接口并存，旧接口使用 `warnings.warn("deprecated", DeprecationWarning)` 提示 |
| v0.3.0 | 移除旧线程类及直接导入，GUI 强制使用服务层 |

对应提交计划：在 PR 描述中注明 "BREAKING CHANGE: remove legacy pipeline thread"。

### 3.8 性能与基准
- 在 `tests/benchmarks/` 目录中添加简单基准脚本，比较重构前后单文件处理时长。
- CI 阶段记录并输出基准结果，不做硬性阈值限制，仅用于观察。

## 4. 实施步骤

### 第一阶段：创建服务层（低风险）
1. 创建 `pipeline_service.py` 文件
2. 实现基本的服务函数
3. 编写单元测试验证服务函数

### 第二阶段：重构线程类（中等风险）
1. 创建 `ServicePipelineThread` 类
2. 将目录处理逻辑从线程类迁移到服务函数
3. 在开发分支测试新线程类

### 第三阶段：更新 GUI 代码（较高风险）
1. 修改 `pipeline_manager.py` 使用服务接口
2. 更新 `main_window.py` 移除不必要的导入
3. 全面测试 GUI 功能

### 第四阶段：清理和优化
1. 移除旧的 `PipelineThread` 和 `NewPipelineThread` 类
2. 更新相关文档和注释
3. 性能测试和优化

## 5. 测试计划

### 5.1 单元测试
- 测试 `pipeline_service` 的每个函数
- 模拟不同的配置和错误情况

### 5.2 集成测试
- 测试 GUI 启动和停止处理流程
- 验证进度更新和事件处理
- 测试错误处理和异常情况

### 5.3 性能与回归测试
- 回归：确保所有现有功能正常工作
- 性能：对比重构前后同一数据集处理时间，波动不超过 ±5% 视为通过
- 稳定性：长时间运行（≥30 min）无内存泄漏或崩溃
- 确保所有现有功能正常工作
- 性能不应有明显下降

## 6. 风险评估

### 6.1 低风险
- 服务层是新增代码，不影响现有功能
- 可以渐进式实施，每步都可验证

### 6.2 需要注意
- Qt 信号/槽机制的正确连接
- 线程安全性
- 错误处理的完整性

## 7. 后续优化建议

### 7.1 短期
- 考虑添加更多的服务函数，如获取处理状态、暂停/恢复等
- 改进错误消息的传递机制

### 7.2 长期
- 可以考虑使用依赖注入模式进一步解耦
- 添加插件系统支持自定义处理步骤

## 8. 评估标准

重构成功的标准：
1. GUI 代码中不再有 `from pktmask.core` 的导入
2. 所有功能测试通过
3. 代码可读性和可维护性提高
4. 未来修改核心逻辑时不需要改动 GUI 代码

---

本方案遵循"适度工程化"原则，在解决耦合问题的同时保持代码的简洁性，适合桌面应用程序的架构需求。
