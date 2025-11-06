# GUI单文件输入功能 - 实施检查清单

**版本：** v1.0  
**日期：** 2025-01-06  
**用途：** 实施过程中的逐步检查清单

---

## 使用说明

- ✅ 表示已完成
- ⏳ 表示进行中
- ❌ 表示未开始
- ⚠️ 表示需要注意

---

## Phase 0: 准备工作（预计5-10分钟）

### 代码备份
- [ ] 备份 `src/pktmask/config/settings.py`
- [ ] 备份 `src/pktmask/gui/main_window.py`
- [ ] 创建 Git 分支（建议：`feature/gui-single-file-input`）

### 环境准备
- [ ] 确认开发环境正常
- [ ] 确认测试数据准备完毕（单个 PCAP 文件 + 目录）
- [ ] 确认依赖包已安装

---

## Phase 1: 配置层修改（预计5分钟）

### 文件：`src/pktmask/config/settings.py`

- [ ] **步骤 1.1** 找到 `UISettings` 类定义（约第18行）
- [ ] **步骤 1.2** 在 `last_output_dir` 后添加新字段：
  ```python
  last_input_mode: str = "file"  # "file" | "directory"
  ```
- [ ] **步骤 1.3** 保存文件
- [ ] **步骤 1.4** 运行快速测试：
  ```bash
  python3 -c "from pktmask.config.settings import get_app_config; c = get_app_config(); print(c.ui.last_input_mode)"
  ```
  预期输出：`file`

---

## Phase 2: UI 层修改（预计2.5-3小时）

### 文件：`src/pktmask/gui/main_window.py`

#### 2.1 修改 `__init__` 方法（约10分钟）

- [ ] **步骤 2.1.1** 找到 `__init__` 方法中的属性定义（约第93-96行）
- [ ] **步骤 2.1.2** 在 `self.base_dir` 后添加新属性：
  ```python
  self.input_path: Optional[str] = None
  self.input_type: str = "none"  # "file" | "directory" | "none"
  ```
- [ ] **步骤 2.1.3** 在 `self.allowed_root` 后添加：
  ```python
  self.last_input_mode = self.config.ui.last_input_mode or "file"
  ```
- [ ] **步骤 2.1.4** 保存并检查语法错误

#### 2.2 创建新的 UI 组件（约30分钟）

- [ ] **步骤 2.2.1** 找到 `_create_directory_selection_ui` 方法（约第235行）
- [ ] **步骤 2.2.2** 重命名为 `_create_input_selection_ui`
- [ ] **步骤 2.2.3** 替换为新的实现（参考文档第484-527行）
  - [ ] 添加 ComboBox
  - [ ] 添加 "Select Input..." 按钮
  - [ ] 添加显示标签
- [ ] **步骤 2.2.4** 更新调用处（在 `_setup_main_layout` 中）

⚠️ **注意：** 考虑移除 emoji 图标，使用纯文本：
```python
self.input_mode_combo.addItem("File", "file")
self.input_mode_combo.addItem("Directory", "directory")
```

#### 2.3 添加新方法（约1小时）

- [ ] **步骤 2.3.1** 添加 `_on_input_mode_changed` 方法
- [ ] **步骤 2.3.2** 添加 `_update_input_button_tooltip` 方法
- [ ] **步骤 2.3.3** 添加 `choose_input` 方法
- [ ] **步骤 2.3.4** 添加 `choose_input_file` 方法
- [ ] **步骤 2.3.5** 添加 `choose_input_directory` 方法（重构自 `choose_input_folder`）
- [ ] **步骤 2.3.6** 添加 `_save_input_mode` 方法
- [ ] **步骤 2.3.7** 添加 `_count_pcap_files` 方法
- [ ] **步骤 2.3.8** 添加 `_get_directory_size` 方法
- [ ] **步骤 2.3.9** 添加 `_format_file_size` 方法

⚠️ **注意：** 在 `choose_input_file` 和 `choose_input_directory` 中同步 `base_dir`：
```python
self.base_dir = file_path  # 向后兼容
```

#### 2.4 修改输出路径生成（约30分钟）

- [ ] **步骤 2.4.1** 找到 `generate_actual_output_path` 方法（约第2540行）
- [ ] **步骤 2.4.2** 替换为新实现（参考文档第1312-1348行）
- [ ] **步骤 2.4.3** 特别注意父目录选择逻辑：
  ```python
  if self.input_type == "file":
      parent_dir = os.path.dirname(self.input_path)
  else:
      parent_dir = os.path.dirname(self.input_path)
  ```

#### 2.5 添加验证方法（约20分钟）

- [ ] **步骤 2.5.1** 添加 `validate_input_file` 方法
- [ ] **步骤 2.5.2** 添加 `validate_input_path` 方法
- [ ] **步骤 2.5.3** 确保验证逻辑完整（存在性、类型、扩展名）

#### 2.6 修改处理启动逻辑（约10分钟）

- [ ] **步骤 2.6.1** 找到 `start_pipeline_processing` 方法（约第2691行）
- [ ] **步骤 2.6.2** 修改输入检查：
  ```python
  if not self.input_path:
      # 提示改为 "Please choose an input file or folder to process."
  ```
- [ ] **步骤 2.6.3** 添加同步逻辑：
  ```python
  self.base_dir = self.input_path  # 向后兼容
  ```

#### 2.7 更新信号连接（约10分钟）

- [ ] **步骤 2.7.1** 找到 `_connect_ui_signals` 方法（约第424行）
- [ ] **步骤 2.7.2** 更新按钮连接：
  ```python
  self.select_input_btn.clicked.connect(self.choose_input)
  self.input_mode_combo.currentIndexChanged.connect(self._on_input_mode_changed)
  ```

---

## Phase 3: 测试（预计1.5-2小时）

### 3.1 单元测试（约30分钟）

- [ ] **测试 3.1.1** 配置保存和加载
  ```python
  # 测试代码
  config = get_app_config()
  config.ui.last_input_mode = "directory"
  config.save()
  # 重新加载
  config2 = get_app_config()
  assert config2.ui.last_input_mode == "directory"
  ```

- [ ] **测试 3.1.2** 文件大小格式化
  ```python
  # 测试不同大小
  assert _format_file_size(500) == "500.0 B"
  assert _format_file_size(1024) == "1.0 KB"
  assert _format_file_size(1024*1024) == "1.0 MB"
  ```

- [ ] **测试 3.1.3** 输出路径生成
  ```python
  # 单文件
  self.input_path = "/home/user/test.pcap"
  self.input_type = "file"
  path = self.generate_actual_output_path()
  assert "/home/user/test-Masked-" in path
  
  # 目录
  self.input_path = "/home/user/pcaps"
  self.input_type = "directory"
  path = self.generate_actual_output_path()
  assert "/home/user/pcaps-Masked-" in path
  ```

### 3.2 功能测试（约40分钟）

- [ ] **测试 3.2.1** 单文件选择和处理
  - [ ] 启动 GUI
  - [ ] ComboBox 选择 "File"
  - [ ] 点击 "Select Input..." 选择单个 PCAP 文件
  - [ ] 验证文件信息显示正确（文件名、大小）
  - [ ] 验证输出预览正确
  - [ ] 勾选处理选项
  - [ ] 点击 "Start" 开始处理
  - [ ] 验证输出目录位置正确
  - [ ] 验证输出文件正确

- [ ] **测试 3.2.2** 目录选择和处理（回归测试）
  - [ ] ComboBox 选择 "Directory"
  - [ ] 选择目录
  - [ ] 验证目录信息显示正确（文件数、总大小）
  - [ ] 验证处理流程正常
  - [ ] 验证输出位置正确

- [ ] **测试 3.2.3** 模式记忆功能
  - [ ] 选择 "File" 模式并处理
  - [ ] 关闭并重启 GUI
  - [ ] 验证 ComboBox 默认为 "File"
  - [ ] 切换到 "Directory" 并处理
  - [ ] 重启 GUI
  - [ ] 验证 ComboBox 默认为 "Directory"

- [ ] **测试 3.2.4** 自定义输出目录
  - [ ] 选择单文件
  - [ ] 点击 Output 按钮选择自定义目录
  - [ ] 验证输出在自定义目录下创建

### 3.3 边界测试（约20分钟）

- [ ] **测试 3.3.1** 无效文件
  - [ ] 选择非 PCAP 文件（如 .txt）
  - [ ] 验证错误提示

- [ ] **测试 3.3.2** 空目录
  - [ ] 选择不含 PCAP 文件的目录
  - [ ] 验证警告提示

- [ ] **测试 3.3.3** 特殊字符文件名
  - [ ] 测试包含空格、中文、特殊符号的文件名

- [ ] **测试 3.3.4** 大文件
  - [ ] 测试 >100MB 的 PCAP 文件

### 3.4 兼容性测试（约20分钟）

- [ ] **测试 3.4.1** 向后兼容
  - [ ] 验证 `base_dir` 属性仍然可用
  - [ ] 验证现有代码路径正常工作

- [ ] **测试 3.4.2** UI 显示
  - [ ] 测试不同分辨率（1920x1080, 1366x768）
  - [ ] 测试窗口缩放
  - [ ] 验证 emoji 显示（如果使用）

---

## Phase 4: 文档和清理（预计30分钟）

### 4.1 代码清理

- [ ] **步骤 4.1.1** 移除未使用的导入
- [ ] **步骤 4.1.2** 检查代码格式（运行 black/autopep8）
- [ ] **步骤 4.1.3** 检查类型提示
- [ ] **步骤 4.1.4** 添加必要的注释

### 4.2 文档更新

- [ ] **步骤 4.2.1** 更新 CHANGELOG.md
- [ ] **步骤 4.2.2** 更新用户文档（如果有）
- [ ] **步骤 4.2.3** 更新 README（如果需要）

### 4.3 提交代码

- [ ] **步骤 4.3.1** 检查 Git 状态
- [ ] **步骤 4.3.2** 提交配置文件修改
  ```bash
  git add src/pktmask/config/settings.py
  git commit -m "feat(config): add last_input_mode field to UISettings"
  ```
- [ ] **步骤 4.3.3** 提交 GUI 修改
  ```bash
  git add src/pktmask/gui/main_window.py
  git commit -m "feat(gui): add single file input support"
  ```
- [ ] **步骤 4.3.4** 推送到远程（如果需要）

---

## 验收标准

### 功能验收

- [ ] ✅ 可以选择单个 PCAP 文件
- [ ] ✅ 可以选择目录（现有功能不受影响）
- [ ] ✅ ComboBox 记住上次选择的模式
- [ ] ✅ 单文件输出目录位置正确
- [ ] ✅ 目录输出位置正确（与之前一致）
- [ ] ✅ 文件大小显示正确
- [ ] ✅ 目录统计显示正确
- [ ] ✅ 自定义输出目录功能正常

### 质量验收

- [ ] ✅ 无语法错误
- [ ] ✅ 无运行时错误
- [ ] ✅ 配置正常保存和加载
- [ ] ✅ 日志输出正常
- [ ] ✅ 错误处理完善
- [ ] ✅ 代码格式规范

### 性能验收

- [ ] ✅ UI 响应流畅
- [ ] ✅ 文件选择对话框正常
- [ ] ✅ 处理速度与之前一致

---

## 常见问题排查

### 问题 1：配置保存失败

**症状：** `AttributeError: 'UISettings' object has no attribute 'last_input_mode'`

**解决：**
- 检查 `settings.py` 中是否添加了字段
- 删除旧的配置文件重新生成

### 问题 2：输出目录位置错误

**症状：** 输出目录在错误的位置

**解决：**
- 检查 `generate_actual_output_path` 中的父目录选择逻辑
- 验证 `input_type` 是否正确设置

### 问题 3：ComboBox 不记住选择

**症状：** 重启后总是默认 "File"

**解决：**
- 检查 `_save_input_mode` 是否被调用
- 检查配置是否正常保存

### 问题 4：单文件处理失败

**症状：** 选择文件后无法处理

**解决：**
- 检查 `base_dir` 是否正确同步
- 检查 `GUIConsistentProcessor` 是否正确接收文件路径

---

## 完成确认

- [ ] 所有 Phase 0-4 的任务已完成
- [ ] 所有测试已通过
- [ ] 所有验收标准已满足
- [ ] 代码已提交
- [ ] 文档已更新

**实施完成日期：** _______________  
**实施人员：** _______________  
**审核人员：** _______________

---

**祝实施顺利！** 🎉

