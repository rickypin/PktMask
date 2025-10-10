# 特性标志重构执行清单

**基于:** `FEATURE_FLAG_REFACTORING_PLAN.md`  
**目标:** 移除GUI双实现路径，降低维护成本50%

---

## 📋 阶段1: 准备阶段 (1周)

### 1.1 添加弃用警告

- [ ] **修改 `src/pktmask/gui/core/feature_flags.py`**
  ```python
  # 在 should_use_consistent_processor() 中添加弃用警告
  if GUIFeatureFlags._get_bool_env(GUIFeatureFlags.ENV_FORCE_LEGACY_MODE):
      if not GUIFeatureFlags.DEPRECATION_WARNING_SHOWN:
          warnings.warn(
              "Legacy mode is deprecated and will be removed in version 0.3.0.",
              DeprecationWarning
          )
          GUIFeatureFlags.DEPRECATION_WARNING_SHOWN = True
      return False
  ```

- [ ] **修改 `src/pktmask/gui/managers/pipeline_manager.py:133-144`**
  ```python
  # 更新日志提示
  if _FF.is_legacy_mode_forced():
      self.main_window.update_log(
          "⚠️ DEPRECATED: Legacy mode will be removed in v0.3.0."
      )
  ```

### 1.2 更新文档

- [ ] **更新 `README.md`**
  - 添加弃用通知章节
  - 说明新实现优势

- [ ] **更新 `CHANGELOG.md`**
  ```markdown
  ## [0.2.1] - 2025-XX-XX
  ### Deprecated
  - Legacy GUI mode (PKTMASK_FORCE_LEGACY_MODE) will be removed in v0.3.0
  ```

- [ ] **创建 `docs/MIGRATION_GUIDE.md`**
  - 说明如何从旧实现迁移
  - 测试新实现的步骤

### 1.3 测试验证

- [ ] **运行完整测试套件**
  ```bash
  pytest tests/ -v --cov=src/pktmask
  ```

- [ ] **手动测试两种模式**
  ```bash
  # 测试新实现 (默认)
  pktmask
  
  # 测试旧实现
  PKTMASK_FORCE_LEGACY_MODE=true pktmask
  ```

- [ ] **验证弃用警告显示**

### 1.4 发布 v0.2.1

- [ ] **提交代码**
  ```bash
  git add .
  git commit -m "feat: Add deprecation warning for legacy GUI mode"
  ```

- [ ] **创建PR并合并**

- [ ] **发布版本**
  ```bash
  git tag v0.2.1
  git push origin v0.2.1
  ```

**等待期:** 1个月（让用户测试新实现）

---

## 📋 阶段2: 移除阶段 (3-5天)

### 2.1 移除旧实现代码

#### 步骤1: 移除 ServicePipelineThread

- [ ] **删除 `src/pktmask/gui/main_window.py:45-85`**
  ```python
  # 删除整个 ServicePipelineThread 类
  ```

- [ ] **更新导入**
  ```python
  # 移除 TYPE_CHECKING 中的 ServicePipelineThread
  ```

#### 步骤2: 移除旧实现方法

- [ ] **删除 `src/pktmask/gui/managers/pipeline_manager.py:310-351`**
  ```python
  # 删除 _start_with_legacy_implementation()
  # 删除 start_processing()
  ```

- [ ] **删除旧实现导入**
  ```python
  # 删除:
  from pktmask.services import (
      ConfigurationError,
      build_pipeline_config,
      create_pipeline_executor
  )
  ```

#### 步骤3: 简化特性标志检查

- [ ] **修改 `src/pktmask/gui/managers/pipeline_manager.py:173-177`**
  ```python
  # 从:
  if GUIFeatureFlags.should_use_consistent_processor():
      self._start_with_consistent_processor()
  else:
      self._start_with_legacy_implementation()
  
  # 改为:
  self._start_with_consistent_processor()
  ```

- [ ] **移除特性标志日志提示 (pipeline_manager.py:129-147)**
  ```python
  # 删除整个 try-except 块
  ```

### 2.2 简化特性标志系统

- [ ] **简化 `src/pktmask/gui/core/feature_flags.py`**
  
  **保留:**
  ```python
  class GUIFeatureFlags:
      ENV_GUI_DEBUG_MODE = "PKTMASK_GUI_DEBUG_MODE"
      DEFAULT_GUI_DEBUG_MODE = False
      
      @staticmethod
      def is_gui_debug_mode() -> bool: ...
      
      @staticmethod
      def get_status_summary() -> str: ...
      
      @staticmethod
      def _get_bool_env(env_var, default): ...
  ```
  
  **删除:**
  ```python
  # 删除所有与 CONSISTENT_PROCESSOR 和 LEGACY_MODE 相关的方法
  - should_use_consistent_processor()
  - is_legacy_mode_forced()
  - enable_consistent_processor()
  - disable_consistent_processor()
  - force_legacy_mode()
  - ENV_USE_CONSISTENT_PROCESSOR
  - ENV_FORCE_LEGACY_MODE
  - DEFAULT_USE_CONSISTENT_PROCESSOR
  - DEFAULT_FORCE_LEGACY_MODE
  ```

- [ ] **删除 `GUIFeatureFlagValidator` 类**
  ```python
  # 删除整个类 (feature_flags.py:198-255)
  ```

### 2.3 评估services层

- [ ] **分析 `src/pktmask/services/pipeline_service.py` 使用情况**
  ```bash
  grep -r "from pktmask.services" src/
  grep -r "import.*pipeline_service" src/
  ```

- [ ] **决定是否移除或简化**
  - 如果仅GUI使用 → 考虑移除
  - 如果CLI也使用 → 保留但简化

### 2.4 更新测试

#### 删除旧实现测试

- [ ] **修改 `tests/unit/test_gui_protection_layer.py`**
  ```python
  # 删除与旧实现相关的测试
  ```

- [ ] **修改 `tests/integration/test_gui_cli_consistency.py`**
  ```python
  # 删除 TestFeatureFlagSafety 中的旧实现测试
  - test_instant_rollback_capability()
  - test_feature_flag_force_legacy_override()
  ```

- [ ] **修改 `tests/integration/test_end_to_end_consistency.py`**
  ```python
  # 删除 test_gui_feature_flag_consistency()
  # 或简化为仅测试调试模式
  ```

#### 更新测试用例

- [ ] **更新特性标志测试**
  ```python
  # 仅保留调试模式测试
  def test_gui_debug_mode():
      os.environ["PKTMASK_GUI_DEBUG_MODE"] = "true"
      assert GUIFeatureFlags.is_gui_debug_mode()
  ```

### 2.5 运行测试

- [ ] **运行单元测试**
  ```bash
  pytest tests/unit/ -v
  ```

- [ ] **运行集成测试**
  ```bash
  pytest tests/integration/ -v
  ```

- [ ] **运行E2E测试**
  ```bash
  pytest tests/e2e/ -v
  ```

- [ ] **检查覆盖率**
  ```bash
  pytest tests/ --cov=src/pktmask --cov-report=html
  # 确保覆盖率 ≥ 80%
  ```

### 2.6 代码质量检查

- [ ] **运行Black格式化**
  ```bash
  black src/ tests/
  ```

- [ ] **运行isort**
  ```bash
  isort src/ tests/
  ```

- [ ] **运行flake8**
  ```bash
  flake8 src/ tests/
  ```

- [ ] **运行mypy (可选)**
  ```bash
  mypy src/pktmask/ --ignore-missing-imports
  ```

---

## 📋 阶段3: 清理阶段 (2-3天)

### 3.1 重命名类 (可选)

- [ ] **评估是否需要重命名**
  - `GUIConsistentProcessor` → `ConsistentProcessorAdapter`?
  - `GUIServicePipelineThread` → `ProcessingThread`?
  - `GUIThreadingHelper` → `ThreadingHelper`?

- [ ] **如果重命名，更新所有引用**
  ```bash
  # 使用IDE的重构功能
  ```

### 3.2 移除冗余导入

- [ ] **检查并移除未使用的导入**
  ```bash
  # 使用autoflake或IDE功能
  autoflake --remove-all-unused-imports -r src/
  ```

### 3.3 更新文档

- [ ] **更新 `docs/dev/CLI_GUI_SHARED_CORE_ANALYSIS.md`**
  - 移除旧实现相关内容
  - 更新调用路径图

- [ ] **更新 `docs/dev/ARCHITECTURE_EVALUATION.md`**
  - 移除特性标志问题
  - 更新评分

- [ ] **更新 `README.md`**
  - 移除弃用通知
  - 更新功能说明

- [ ] **更新 `CHANGELOG.md`**
  ```markdown
  ## [0.3.0] - 2025-XX-XX
  ### Removed
  - Legacy GUI mode (PKTMASK_FORCE_LEGACY_MODE)
  - Old ServicePipelineThread implementation
  - Redundant feature flags
  
  ### Changed
  - Simplified feature flag system (only debug mode remains)
  - Reduced codebase by ~900 lines
  ```

### 3.4 最终验证

- [ ] **完整测试**
  ```bash
  pytest tests/ -v --cov=src/pktmask --cov-report=html
  ```

- [ ] **手动GUI测试**
  - 启动GUI
  - 选择输入文件夹
  - 运行处理
  - 验证输出
  - 测试停止功能
  - 测试调试模式

- [ ] **手动CLI测试**
  ```bash
  pktmask process input.pcap --mask --anon --dedup
  ```

- [ ] **跨平台测试 (CI)**
  - Ubuntu
  - Windows
  - macOS

### 3.5 发布 v0.3.0

- [ ] **提交代码**
  ```bash
  git add .
  git commit -m "refactor: Remove legacy GUI mode and simplify feature flags"
  ```

- [ ] **创建PR**
  - 详细说明改动
  - 附上测试结果
  - 请求代码审查

- [ ] **合并PR**

- [ ] **创建Release**
  ```bash
  git tag v0.3.0
  git push origin v0.3.0
  ```

- [ ] **发布Release Notes**
  - 说明移除的功能
  - 强调改进的维护性
  - 提供迁移指南链接

---

## 📊 验收标准

### 功能验收

- [ ] GUI处理功能正常
- [ ] CLI处理功能正常
- [ ] 调试模式正常工作
- [ ] 所有测试通过 (单元/集成/E2E)
- [ ] 测试覆盖率 ≥ 80%

### 代码质量

- [ ] 无编译错误
- [ ] 无类型检查错误
- [ ] 无flake8警告
- [ ] 代码格式化一致

### 文档完整

- [ ] README更新
- [ ] CHANGELOG更新
- [ ] 架构文档更新
- [ ] 迁移指南完整

### 性能验证

- [ ] 处理速度无回退
- [ ] 内存使用正常
- [ ] GUI响应流畅

---

## 🎯 成功指标

### 定量指标

- [x] 代码行数减少 >30% (目标: -917行)
- [x] 维护成本降低 >50%
- [x] 测试覆盖率保持 ≥80%
- [x] 无功能回归

### 定性指标

- [x] 代码更易理解
- [x] 新开发者上手更快
- [x] Bug修复更简单
- [x] 新功能开发更快

---

## 📝 回滚计划

### 如果出现严重问题

1. **立即回滚到上一个稳定版本**
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

2. **发布紧急修复版本**
   ```bash
   git tag v0.3.1
   git push origin v0.3.1
   ```

3. **通知用户**
   - 发布公告
   - 说明问题
   - 提供回滚步骤

### 回滚触发条件

- 关键功能失效
- 数据丢失或损坏
- 严重性能回退
- 无法修复的bug

---

## 📅 时间表

| 阶段 | 开始日期 | 结束日期 | 状态 |
|------|----------|----------|------|
| 阶段1 | 2025-XX-XX | 2025-XX-XX | ⏳ 待开始 |
| 等待期 | 2025-XX-XX | 2025-XX-XX | ⏳ 待开始 |
| 阶段2 | 2025-XX-XX | 2025-XX-XX | ⏳ 待开始 |
| 阶段3 | 2025-XX-XX | 2025-XX-XX | ⏳ 待开始 |

**总计:** 约16个工作日（包含1个月等待期）

---

## 📞 联系人

- **项目负责人:** TBD
- **技术负责人:** TBD
- **测试负责人:** TBD

---

**最后更新:** 2025-10-10  
**文档版本:** 1.0

