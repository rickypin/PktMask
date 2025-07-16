# PktMask 依赖状态显示设计方案

> **文档版本**: v1.0  
> **创建日期**: 2025-07-16  
> **适用版本**: PktMask v3.1+  
> **作者**: AI 设计助手

本文档设计了一个合理实用的PktMask依赖状态显示解决方案，避免过度工程化，专注于核心问题解决。

---

## 1. 问题分析

### 1.1 核心问题
GUI当前缺乏tshark依赖状态可见性，用户无法了解依赖是否满足。

### 1.2 现状分析
- **分散的检查逻辑**: tshark检查分布在多个模块中
- **缺乏统一接口**: 没有中央化的依赖管理器
- **GUI无状态显示**: 依赖问题时用户无法获得反馈
- **启动时无检查**: 应用启动时不进行依赖验证

### 1.3 设计约束
- 保持GUI结构100%兼容
- 避免复杂UI组件
- 专注Log模块作为状态显示位置
- 保持轻量级和可维护性

---

## 2. 解决方案架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    PktMask Application                      │
├─────────────────────────────────────────────────────────────┤
│  Startup Flow                                               │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────┐ │
│  │ App Launch  │───▶│ Dependency Check │───▶│ GUI Init    │ │
│  └─────────────┘    └──────────────────┘    └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Core Components                                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │           DependencyChecker (New)                      │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │ │
│  │  │ TShark      │  │ Future      │  │ Status          │ │ │
│  │  │ Validator   │  │ Deps        │  │ Reporter        │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  GUI Integration                                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 Log Module                              │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │ Conditional Display:                                │ │ │
│  │  │ • Dependencies OK: Clean interface                 │ │ │
│  │  │ • Dependencies FAIL: Status messages              │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件设计

#### 2.2.1 DependencyChecker (新增)
- **位置**: `src/pktmask/infrastructure/dependency/checker.py`
- **职责**: 统一的依赖检查接口
- **功能**: 
  - 整合现有分散的tshark检查逻辑
  - 提供标准化的检查结果格式
  - 支持未来扩展其他依赖

#### 2.2.2 GUI集成点
- **位置**: GUI初始化流程中
- **集成点**: `MainWindow.__init__()` 或 `UIBuilder.setup_ui()`
- **显示位置**: 现有Log模块 (`log_text` QTextEdit)

---

## 3. 实现方案

### 3.1 DependencyChecker实现

```python
# src/pktmask/infrastructure/dependency/checker.py

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

class DependencyStatus(Enum):
    SATISFIED = "satisfied"
    MISSING = "missing"
    VERSION_MISMATCH = "version_mismatch"
    PERMISSION_ERROR = "permission_error"

@dataclass
class DependencyResult:
    name: str
    status: DependencyStatus
    version_found: Optional[str] = None
    version_required: Optional[str] = None
    path: Optional[str] = None
    error_message: Optional[str] = None

class DependencyChecker:
    """统一的依赖检查器"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def check_all_dependencies(self) -> Dict[str, DependencyResult]:
        """检查所有依赖"""
        results = {}
        results['tshark'] = self.check_tshark()
        # 未来可扩展其他依赖
        return results
    
    def check_tshark(self) -> DependencyResult:
        """检查tshark依赖 - 整合现有逻辑"""
        # 复用scripts/check_tshark_dependencies.py中的逻辑
        pass
    
    def are_dependencies_satisfied(self) -> bool:
        """检查所有依赖是否满足"""
        results = self.check_all_dependencies()
        return all(
            result.status == DependencyStatus.SATISFIED 
            for result in results.values()
        )
    
    def get_status_messages(self) -> List[str]:
        """获取状态消息用于GUI显示"""
        results = self.check_all_dependencies()
        messages = []
        
        for name, result in results.items():
            if result.status != DependencyStatus.SATISFIED:
                messages.append(self._format_error_message(result))
        
        return messages
```

### 3.2 GUI集成实现

#### 3.2.1 启动时检查
```python
# src/pktmask/gui/main_window.py 或 simplified_main_window.py

class MainWindow(QMainWindow):
    def __init__(self):
        # ... 现有初始化代码 ...
        
        # 在UI初始化后进行依赖检查
        self._check_and_display_dependencies()
    
    def _check_and_display_dependencies(self):
        """检查依赖并在GUI中显示状态"""
        from pktmask.infrastructure.dependency.checker import DependencyChecker
        
        checker = DependencyChecker()
        
        if not checker.are_dependencies_satisfied():
            # 依赖不满足时显示状态信息
            status_messages = checker.get_status_messages()
            self._display_dependency_status(status_messages)
        # 依赖满足时不显示任何额外信息（保持界面清洁）
    
    def _display_dependency_status(self, messages: List[str]):
        """在Log模块中显示依赖状态"""
        if hasattr(self, 'log_text'):
            # 添加依赖状态标题
            self.log_text.append("⚠️  Dependency Status Check:")
            self.log_text.append("-" * 40)
            
            # 添加具体状态信息
            for message in messages:
                self.log_text.append(f"❌ {message}")
            
            # 添加解决建议
            self.log_text.append("")
            self.log_text.append("💡 Installation Guide:")
            self.log_text.append("   • Install Wireshark (includes tshark)")
            self.log_text.append("   • Ensure tshark is in system PATH")
            self.log_text.append("   • Minimum version required: 4.2.0")
            self.log_text.append("-" * 40)
```

#### 3.2.2 条件显示逻辑
- **依赖满足**: 正常显示欢迎信息，无额外状态信息
- **依赖不满足**: 在Log模块顶部显示依赖状态信息

---

## 4. 技术实现细节

### 4.1 代码复用策略
- 复用 `scripts/check_tshark_dependencies.py` 中的检查逻辑
- 整合现有模块中的版本验证代码
- 保持与现有错误处理系统的兼容性

### 4.2 性能考虑
- 依赖检查仅在启动时执行一次
- 检查结果可缓存避免重复执行
- 异步检查避免阻塞GUI初始化

### 4.3 扩展性设计
- DependencyChecker支持添加新的依赖类型
- 状态消息格式标准化
- 支持不同严重级别的依赖问题

---

## 5. 用户体验设计

### 5.1 正常场景（依赖满足）
```
🚀 Welcome to PktMask!

┌─ Quick Start Guide ──────────┐
│ 1. Select pcap directory     │
│ 2. Configure actions         │
│ 3. Start processing          │
└──────────────────────────────┘

💡 Remove Dupes & Anonymize IPs enabled by default

Processing logs will appear here...
```

### 5.2 异常场景（依赖不满足）
```
⚠️  Dependency Status Check:
----------------------------------------
❌ TShark not found in system PATH
❌ Required version: ≥4.2.0, found: 3.6.2

💡 Installation Guide:
   • Install Wireshark (includes tshark)
   • Ensure tshark is in system PATH  
   • Minimum version required: 4.2.0
----------------------------------------

🚀 Welcome to PktMask!
...
```

### 5.3 消息设计原则
- 使用emoji增强可读性
- 提供具体的错误信息
- 包含明确的解决建议
- 保持消息简洁但信息完整

---

## 6. 实现优先级

### Phase 1: 核心功能 (高优先级)
- [ ] 创建DependencyChecker类
- [ ] 整合tshark检查逻辑
- [ ] GUI启动时依赖检查
- [ ] Log模块状态显示

### Phase 2: 增强功能 (中优先级)  
- [ ] 异步依赖检查
- [ ] 检查结果缓存
- [ ] 详细错误报告

### Phase 3: 扩展功能 (低优先级)
- [ ] 支持其他依赖类型
- [ ] 依赖自动安装建议
- [ ] 配置文件集成

---

## 7. 测试策略

### 7.1 单元测试
- DependencyChecker各方法的功能测试
- 不同依赖状态的结果验证
- 错误处理逻辑测试

### 7.2 集成测试
- GUI启动流程中的依赖检查
- Log模块显示效果验证
- 用户交互场景测试

### 7.3 场景测试
- tshark已安装且版本满足
- tshark未安装
- tshark版本过低
- tshark权限问题

---

## 8. 风险评估

### 8.1 技术风险
- **低风险**: 基于现有代码重构，技术成熟
- **缓解措施**: 充分的单元测试和集成测试

### 8.2 兼容性风险
- **低风险**: 不修改现有GUI结构
- **缓解措施**: 保持现有接口不变

### 8.3 用户体验风险
- **中风险**: 依赖问题时的信息过载
- **缓解措施**: 精心设计消息格式和内容

---

## 9. 总结

本设计方案提供了一个轻量级、实用的依赖状态显示解决方案：

### 9.1 核心优势
- **统一管理**: 中央化的依赖检查器
- **条件显示**: 仅在需要时显示状态信息
- **用户友好**: 清晰的错误信息和解决建议
- **易于扩展**: 支持未来添加新依赖

### 9.2 实现简单
- 复用现有检查逻辑
- 最小化GUI修改
- 保持架构清洁

### 9.3 维护性强
- 代码集中管理
- 标准化接口
- 良好的测试覆盖

这个方案避免了过度工程化，专注于解决核心问题，为PktMask提供了实用的依赖状态可见性。
