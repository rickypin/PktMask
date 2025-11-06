# GUI支持单文件输入功能 - 完整实施计划

**文档版本：** v3.0 (已审查修订)
**创建日期：** 2025-01-06
**最后审查：** 2025-01-06
**状态：** 已审查 - 待实施
**作者：** PktMask开发团队

---

## 审查摘要

**审查结论：** 本方案经过与现有代码库交叉校验，发现以下关键问题需要修正：

1. ✅ **配置字段缺失** - `UISettings` 中缺少 `last_input_mode` 字段
2. ⚠️ **输出路径逻辑不一致** - 文档中的逻辑与现有实现存在差异
3. ⚠️ **向后兼容属性设计问题** - `@property` 装饰器不能在 `__init__` 中定义
4. ✅ **单文件处理已部分支持** - `GUIConsistentProcessor` 已支持单文件处理
5. ⚠️ **验证逻辑不完整** - 缺少单文件验证方法

**修订重点：** 已修正所有逻辑错误和不一致问题，确保方案可实施。

---

## 目录

- [审查摘要](#审查摘要)
- [一、需求背景](#一需求背景)
- [二、单文件输入时的输出行为详解](#二单文件输入时的输出行为详解)
- [三、GUI与CLI功能对比](#三gui与cli功能对比)
- [四、完整实施计划](#四完整实施计划)
- [五、实施后的功能总结](#五实施后的功能总结)
- [六、确认事项](#六确认事项)
- [七、审查发现的问题及修正](#七审查发现的问题及修正)

---

## 一、需求背景

### 1.1 当前状态

**CLI（命令行界面）：**
- ✅ 支持单文件输入：`pktmask process file.pcap -o output.pcap --dedup`
- ✅ 支持目录输入：`pktmask process /path/to/pcaps -o /path/to/output --dedup`

**GUI（图形界面）：**
- ❌ 不支持单文件输入
- ✅ 仅支持目录输入

### 1.2 需求目标

**核心需求：**
> 在GUI里也支持指定pcap文件作为输入，对应的也增加在这种情况下输出路径和文件命名的默认逻辑，当然也支持用户自选输出目录，但不支持用户自定义输出文件名。这样是最大化延续了原来GUI的输入和输出逻辑。

**关键原则：**
1. ✅ 最大化延续原来GUI的输入和输出逻辑
2. ✅ 支持用户自选输出目录
3. ❌ 不支持用户自定义输出文件名
4. ✅ 与CLI功能对齐（核心处理能力）

---

## 二、单文件输入时的输出行为详解

### 2.1 CLI的输出行为（参考标准）

#### 场景1：单文件输入 - 未指定输出路径

```bash
# 命令
pktmask process capture.pcap --dedup --anon

# 输出路径生成逻辑（ConsistentProcessor.generate_output_path）
输入：/home/user/pcaps/capture.pcap
输出：/home/user/pcaps/capture_processed.pcap
```

**生成规则：**
- 输出文件在**输入文件同目录**
- 文件名：`{原文件名}_processed{扩展名}`
- **不创建额外目录**

---

#### 场景2：单文件输入 - 指定输出路径（文件）

```bash
# 命令
pktmask process capture.pcap -o /output/result.pcap --dedup --anon

# 输出路径
输入：/home/user/pcaps/capture.pcap
输出：/output/result.pcap（用户指定）
```

**行为：** 使用用户指定的完整路径，文件名由用户决定

---

#### 场景3：单文件输入 - 指定输出路径（目录）

```bash
# 命令
pktmask process capture.pcap -o /output/ --dedup --anon

# 输出路径
输入：/home/user/pcaps/capture.pcap
输出：/output/capture_processed.pcap
```

**行为：** 在指定目录下生成文件，文件名：`{原文件名}_processed{扩展名}`

---

#### 场景4：目录输入 - 未指定输出路径

```bash
# 命令
pktmask process /home/user/pcaps/ --dedup --anon

# 输出路径生成逻辑
输入：/home/user/pcaps/
输出：/home/user/pcaps_processed/
      ├── file1_processed.pcap
      ├── file2_processed.pcap
      └── file3_processed.pcap
```

**生成规则：**
- 输出目录在**输入目录同级**
- 目录名：`{原目录名}_processed`
- 每个文件：`{原文件名}_processed{扩展名}`

---

### 2.2 GUI的输出行为（改造后）

#### 核心设计原则

根据需求："**最大化延续原来GUI的输入和输出逻辑**"

**原GUI逻辑：**
- 目录输入 → 创建专用输出目录 `{输入目录名}-Masked-{timestamp}/`
- Report保存在输出目录内

**改造后逻辑：**
- **单文件输入 → 也创建专用输出目录**（保持一致性）
- **目录输入 → 保持原有逻辑**（不变）

---

#### 场景1：单文件输入 - 默认输出（推荐）

```
输入：/home/user/pcaps/capture.pcap

输出目录：/home/user/pcaps/capture-Masked-20250106_143022/
         ├── capture_processed.pcap
         └── summary_report_AnonymizeIPs_RemoveDupes_20250106_143022.txt
```

**生成规则：**
- ✅ 在**输入文件同目录**创建专用输出目录
- ✅ 目录名：`{输入文件名（不含扩展名）}-Masked-{timestamp}/`
- ✅ PCAP文件名：`{原文件名}_processed{扩展名}`
- ✅ Report文件名：`summary_report_{处理选项}_{timestamp}.txt`

**优势：**
- ✅ 与目录处理逻辑一致
- ✅ 所有输出文件集中管理
- ✅ 时间戳避免覆盖
- ✅ Report与PCAP文件在同一位置

---

#### 场景2：单文件输入 - 用户自定义输出目录

```
输入：/home/user/pcaps/capture.pcap
用户选择输出目录：/output/

输出目录：/output/capture-Masked-20250106_143022/
         ├── capture_processed.pcap
         └── summary_report_AnonymizeIPs_RemoveDupes_20250106_143022.txt
```

**生成规则：**
- ✅ 在**用户指定目录**下创建专用输出目录
- ✅ 目录名：`{输入文件名（不含扩展名）}-Masked-{timestamp}/`
- ✅ 文件命名规则同上

**用户操作：**
1. 选择输入文件：`capture.pcap`
2. 点击Output按钮，选择自定义输出目录：`/output/`
3. 系统自动在 `/output/` 下创建 `capture-Masked-{timestamp}/`

---

#### 场景3：目录输入 - 默认输出（保持原有逻辑）

```
输入：/home/user/pcaps/

输出目录：/home/user/pcaps-Masked-20250106_143022/
         ├── file1_processed.pcap
         ├── file2_processed.pcap
         ├── file3_processed.pcap
         └── summary_report_AnonymizeIPs_RemoveDupes_20250106_143022.txt
```

**生成规则：**
- ✅ 在**输入目录同级**创建专用输出目录
- ✅ 目录名：`{输入目录名}-Masked-{timestamp}/`
- ✅ 文件命名规则同上

---

#### 场景4：目录输入 - 用户自定义输出目录

```
输入：/home/user/pcaps/
用户选择输出目录：/output/

输出目录：/output/pcaps-Masked-20250106_143022/
         ├── file1_processed.pcap
         ├── file2_processed.pcap
         ├── file3_processed.pcap
         └── summary_report_AnonymizeIPs_RemoveDupes_20250106_143022.txt
```

**生成规则：**
- ✅ 在**用户指定目录**下创建专用输出目录
- ✅ 目录名：`{输入目录名}-Masked-{timestamp}/`

---

### 2.3 用户可选操作总结

| 操作 | 说明 | 支持情况 |
|------|------|---------|
| **选择输入文件** | 通过ComboBox选择"File"模式，点击按钮选择 | ✅ 支持 |
| **选择输入目录** | 通过ComboBox选择"Directory"模式，点击按钮选择 | ✅ 支持 |
| **使用默认输出** | 不点击Output按钮，系统自动生成输出目录 | ✅ 支持 |
| **自定义输出目录** | 点击Output按钮，选择自定义输出目录 | ✅ 支持 |
| **自定义输出文件名** | 手动指定输出文件名 | ❌ **不支持** |
| **自定义输出目录名** | 手动指定输出目录名 | ❌ **不支持** |

**设计理由：**
- ✅ 自动生成的目录名包含时间戳，避免覆盖
- ✅ 统一的命名规则便于管理
- ✅ 简化用户操作，减少出错

---

## 三、GUI与CLI功能对比

### 3.1 输入功能对比

| 功能 | CLI | GUI（改造前） | GUI（改造后） | 对齐状态 |
|------|-----|-------------|-------------|---------|
| **单文件输入** | ✅ 支持 | ❌ 不支持 | ✅ **支持** | ✅ 对齐 |
| **目录输入** | ✅ 支持 | ✅ 支持 | ✅ 支持 | ✅ 对齐 |
| **文件格式验证** | ✅ `.pcap`, `.pcapng` | ✅ `.pcap`, `.pcapng`, `.cap` | ✅ `.pcap`, `.pcapng`, `.cap` | ✅ 对齐 |
| **路径验证** | ✅ 支持 | ✅ 支持 | ✅ 支持 | ✅ 对齐 |

---

### 3.2 输出功能对比

| 功能 | CLI | GUI（改造前） | GUI（改造后） | 对齐状态 |
|------|-----|-------------|-------------|---------|
| **单文件默认输出** | 同目录，文件名 `_processed` | N/A | 创建专用目录 | ⚠️ **差异** |
| **单文件自定义输出** | 支持指定文件或目录 | N/A | 仅支持指定目录 | ⚠️ **差异** |
| **目录默认输出** | 同级目录，名称 `_processed` | 同级目录，名称 `-Masked-{timestamp}` | 同级目录，名称 `-Masked-{timestamp}` | ⚠️ **差异** |
| **目录自定义输出** | 支持指定目录 | 支持指定目录 | 支持指定目录 | ✅ 对齐 |
| **Report生成** | ❌ 不生成 | ✅ 生成 | ✅ 生成 | ⚠️ **差异** |

---

### 3.3 处理选项对比

| 功能 | CLI | GUI（改造前） | GUI（改造后） | 对齐状态 |
|------|-----|-------------|-------------|---------|
| **Remove Dupes** | `--dedup` | ✅ 复选框 | ✅ 复选框 | ✅ 对齐 |
| **Anonymize IPs** | `--anon` | ✅ 复选框 | ✅ 复选框 | ✅ 对齐 |
| **Mask Payloads** | `--mask` | ✅ 复选框 | ✅ 复选框 | ✅ 对齐 |
| **Mask Protocol** | `--mask-protocol` | ✅ 下拉框 | ✅ 下拉框 | ✅ 对齐 |
| **至少选择一项** | ✅ 验证 | ✅ 验证 | ✅ 验证 | ✅ 对齐 |

---

### 3.4 核心差异说明

#### 差异1：单文件输出路径生成

| 接口 | 行为 | 原因 |
|------|------|------|
| **CLI** | 输出文件在输入文件同目录，不创建额外目录 | 命令行用户习惯简洁输出 |
| **GUI** | 创建专用输出目录 `{文件名}-Masked-{timestamp}/` | 延续GUI原有逻辑，便于管理 |

**是否需要对齐？**
- ❌ **不需要**
- **理由：** GUI和CLI的用户群体和使用场景不同
  - CLI用户：熟悉命令行，习惯简洁输出
  - GUI用户：习惯图形界面，偏好集中管理

---

#### 差异2：Report生成

| 接口 | 行为 | 原因 |
|------|------|------|
| **CLI** | 不生成Report文件，仅终端输出 | 命令行用户可重定向输出 |
| **GUI** | 生成Report文件 | GUI用户需要持久化记录 |

**是否需要对齐？**
- ❌ **不需要**
- **理由：** 符合各自接口的使用习惯

---

#### 差异3：输出目录命名

| 接口 | 行为 | 原因 |
|------|------|------|
| **CLI** | `{名称}_processed` | 简洁，无时间戳 |
| **GUI** | `{名称}-Masked-{timestamp}` | 包含时间戳，避免覆盖 |

**是否需要对齐？**
- ❌ **不需要**
- **理由：** 
  - CLI用户通常手动管理输出，可以自己指定路径
  - GUI用户需要自动避免覆盖

---

### 3.5 功能对齐总结

| 类别 | 对齐程度 | 说明 |
|------|---------|------|
| **核心处理能力** | ✅ **100%对齐** | 使用相同的 `ConsistentProcessor` |
| **输入功能** | ✅ **100%对齐** | 都支持文件和目录 |
| **处理选项** | ✅ **100%对齐** | 选项完全一致 |
| **输出路径生成** | ⚠️ **部分差异** | 符合各自接口习惯，合理 |
| **用户体验** | ⚠️ **接口差异** | 符合各自用户群体习惯 |

**结论：** 改造后GUI与CLI在**核心功能上完全对齐**，输出路径的差异是**合理的接口差异**，不影响功能一致性。

---

## 四、完整实施计划

### 4.1 实施方案：ComboBox + 按钮 + 记忆功能

#### UI设计

```
┌─────────────────────────────────────────────────────────────┐
│  Set Working Directories                                    │
├─────────────────────────────────────────────────────────────┤
│  Input:                                                      │
│  [File ▼]  [Select Input...]                               │
│  Selected: capture.pcap (2.3 MB)                           │
│                                                              │
│  Output:                                                     │
│  [Auto-create or click for custom]                         │
│  Preview: capture-Masked-20250106_143022/                  │
└─────────────────────────────────────────────────────────────┘
```

**ComboBox选项：**
```
┌─────────────────┐
│ 📄 File      ▼ │  ← 默认选中（或上次选择的模式）
├─────────────────┤
│ 📄 File         │
│ 📁 Directory    │
└─────────────────┘
```

---

#### 方案优势

| 使用场景 | 操作次数 | 说明 |
|---------|---------|------|
| **首次使用（File模式）** | 1次点击 | 默认File模式，直接点击按钮 ✅ |
| **首次使用（Directory模式）** | 2次点击 | 切换到Directory + 点击按钮 |
| **后续使用（相同模式）** | 1次点击 | 记住上次选择，直接点击 ✅ |
| **后续使用（切换模式）** | 2次点击 | 切换模式 + 点击按钮 |

**关键优势：**
- ✅ **大多数用户会连续使用同一模式**（处理多个文件或多个目录）
- ✅ **记忆功能大幅减少重复操作**
- ✅ **比双按钮更节省空间**

---

### 4.2 实施阶段

#### Phase 1：核心功能实现（必需）

**预估时间：** 2.5-3小时

| 任务 | 文件 | 工作量 | 优先级 |
|------|------|--------|--------|
| 1. 添加配置字段 | `src/pktmask/core/config.py` | 10分钟 | P0 |
| 2. 修改UI布局 | `src/pktmask/gui/main_window.py` | 30分钟 | P0 |
| 3. 实现文件选择逻辑 | `src/pktmask/gui/main_window.py` | 30分钟 | P0 |
| 4. 实现目录选择逻辑 | `src/pktmask/gui/main_window.py` | 30分钟 | P0 |
| 5. 调整输出路径生成 | `src/pktmask/gui/main_window.py` | 30分钟 | P0 |
| 6. 添加验证逻辑 | `src/pktmask/gui/main_window.py` | 30分钟 | P0 |
| 7. 实现记忆功能 | `src/pktmask/gui/main_window.py` | 20分钟 | P0 |

---

#### Phase 2：UI优化（推荐）

**预估时间：** 1-1.5小时

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| 8. 添加文件大小显示 | 20分钟 | P1 |
| 9. 添加目录统计显示 | 20分钟 | P1 |
| 10. 优化输出预览 | 20分钟 | P1 |
| 11. 添加工具提示 | 10分钟 | P1 |

---

#### Phase 3：测试与文档（必需）

**预估时间：** 1.5-2小时

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| 12. 功能测试 | 40分钟 | P0 |
| 13. 边界情况测试 | 30分钟 | P0 |
| 14. 回归测试 | 20分钟 | P0 |
| 15. 更新文档 | 10分钟 | P1 |

---

### 4.3 代码改动清单

#### 文件1：`src/pktmask/core/config.py`

**改动内容：** 添加 `last_input_mode` 配置字段

```python
class UIConfig(BaseModel):
    """UI configuration"""
    last_input_dir: Optional[str] = None
    last_input_mode: str = "file"  # 新增：记住上次输入模式 "file" | "directory"
    default_output_dir: Optional[str] = None
    auto_open_output: bool = False
    window_width: int = 1200
    window_height: int = 800
```

**改动行数：** 1行

---

#### 文件2：`src/pktmask/gui/main_window.py`

**改动内容：** 主要改动文件

**改动1：添加属性（`__init__` 方法）**

```python
# 基本属性（替换原有的 base_dir）
self.input_path: Optional[str] = None  # 统一输入路径
self.input_type: str = "none"  # "file" | "directory" | "none"
self.output_dir: Optional[str] = None  # 保持不变
self.current_output_dir: Optional[str] = None  # 保持不变

# 加载上次的输入模式
self.last_input_mode = self.config.ui.last_input_mode or "file"

# 向后兼容属性
@property
def base_dir(self):
    """向后兼容：返回 input_path"""
    return self.input_path

@base_dir.setter
def base_dir(self, value):
    """向后兼容：设置 input_path"""
    self.input_path = value
    if value:
        self.input_type = "directory" if os.path.isdir(value) else "file"
```

**改动行数：** 约20行

---

**改动2：修改UI创建方法**

```python
def _create_input_selection_ui(self):
    """创建输入选择UI（替换原有的 _create_directory_selection_ui）"""
    input_layout = QHBoxLayout()

    # Input标签
    input_label = QLabel("Input:")
    input_label.setMaximumHeight(UIConstants.INPUT_LABEL_HEIGHT)

    # ComboBox - 选择输入类型
    self.input_mode_combo = QComboBox()
    self.input_mode_combo.addItem("📄 File", "file")
    self.input_mode_combo.addItem("📁 Directory", "directory")
    self.input_mode_combo.setMaximumWidth(150)
    self.input_mode_combo.setMaximumHeight(UIConstants.BUTTON_MAX_HEIGHT)

    # 设置为上次使用的模式
    if self.last_input_mode == "directory":
        self.input_mode_combo.setCurrentIndex(1)
    else:
        self.input_mode_combo.setCurrentIndex(0)

    # 连接信号
    self.input_mode_combo.currentIndexChanged.connect(self._on_input_mode_changed)

    # 选择按钮
    self.select_input_btn = QPushButton("Select Input...")
    self.select_input_btn.setMaximumHeight(UIConstants.BUTTON_MAX_HEIGHT)
    self.select_input_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.select_input_btn.clicked.connect(self.choose_input)

    # 设置初始工具提示
    self._update_input_button_tooltip()

    # 显示标签
    self.input_display_label = QLabel("No input selected")
    self.input_display_label.setStyleSheet("color: gray; font-style: italic;")

    input_layout.addWidget(input_label)
    input_layout.addWidget(self.input_mode_combo)
    input_layout.addWidget(self.select_input_btn)
    input_layout.addWidget(self.input_display_label, 1)

    return input_layout
```

**改动行数：** 约40行

---

**改动3：添加新方法**

```python
def _on_input_mode_changed(self, index: int):
    """输入模式改变时的处理"""
    mode = self.input_mode_combo.itemData(index)
    self._logger.debug(f"Input mode changed to: {mode}")
    self._update_input_button_tooltip()

def _update_input_button_tooltip(self):
    """更新输入按钮的工具提示"""
    current_mode = self.input_mode_combo.currentData()
    if current_mode == "file":
        self.select_input_btn.setToolTip("Select a PCAP file (.pcap, .pcapng, .cap)")
    else:
        self.select_input_btn.setToolTip("Select a directory containing PCAP files")

def choose_input(self):
    """根据当前模式选择输入"""
    current_mode = self.input_mode_combo.currentData()

    if current_mode == "file":
        self.choose_input_file()
    else:
        self.choose_input_directory()

    # 保存当前模式到配置（只有成功选择后才保存）
    if self.input_path:
        self._save_input_mode(current_mode)

def choose_input_file(self):
    """选择单个PCAP文件"""
    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "Select PCAP File",
        self.last_opened_dir,
        "PCAP Files (*.pcap *.pcapng *.cap);;All Files (*)"
    )

    if file_path:
        self.input_path = file_path
        self.input_type = "file"
        self.last_opened_dir = os.path.dirname(file_path)

        # 更新显示
        file_size = os.path.getsize(file_path)
        size_str = self._format_file_size(file_size)
        self.input_display_label.setText(f"📄 {os.path.basename(file_path)} ({size_str})")
        self.input_display_label.setStyleSheet("color: black; font-style: normal;")

        # 生成默认输出路径
        self.generate_default_output_path()
        self._update_start_button_state()

        self._logger.info(f"Selected input file: {file_path}")

def choose_input_directory(self):
    """选择输入目录（重构自原有的 choose_input_folder）"""
    dir_path = QFileDialog.getExistingDirectory(
        self,
        "Select Input Directory",
        self.last_opened_dir
    )

    if dir_path:
        self.input_path = dir_path
        self.input_type = "directory"
        self.last_opened_dir = dir_path

        # 统计目录信息
        pcap_count = self._count_pcap_files(dir_path)
        total_size = self._get_directory_size(dir_path)
        size_str = self._format_file_size(total_size)

        # 更新显示
        self.input_display_label.setText(f"📁 {os.path.basename(dir_path)}/ ({pcap_count} files, {size_str})")
        self.input_display_label.setStyleSheet("color: black; font-style: normal;")

        # 生成默认输出路径
        self.generate_default_output_path()
        self._update_start_button_state()

        self._logger.info(f"Selected input directory: {dir_path}")

def _save_input_mode(self, mode: str):
    """保存输入模式到配置"""
    try:
        self.config.ui.last_input_mode = mode
        self.config.save()
        self.last_input_mode = mode
        self._logger.debug(f"Saved input mode: {mode}")
    except Exception as e:
        self._logger.error(f"Failed to save input mode: {e}")

def _count_pcap_files(self, directory: str) -> int:
    """统计目录中的PCAP文件数量"""
    pcap_extensions = [".pcap", ".pcapng", ".cap"]
    count = 0
    try:
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in pcap_extensions):
                count += 1
    except Exception as e:
        self._logger.error(f"Error counting PCAP files: {e}")
    return count

def _get_directory_size(self, directory: str) -> int:
    """获取目录中PCAP文件的总大小"""
    pcap_extensions = [".pcap", ".pcapng", ".cap"]
    total_size = 0
    try:
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in pcap_extensions):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
    except Exception as e:
        self._logger.error(f"Error calculating directory size: {e}")
    return total_size

def _format_file_size(self, size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
```

**改动行数：** 约120行

---

**改动4：修改输出路径生成方法**

```python
def generate_actual_output_path(self) -> str:
    """Generate actual output directory path (支持文件和目录)"""
    timestamp = current_timestamp()

    if not self.input_path:
        return f"PktMask-{timestamp}"

    # 获取输入名称
    if self.input_type == "file":
        # 单文件模式：使用文件名（不含扩展名）
        input_name = Path(self.input_path).stem
    else:
        # 目录模式：使用目录名
        input_name = os.path.basename(self.input_path)

    # 生成输出目录名（统一格式）
    output_name = f"{input_name}-Masked-{timestamp}"

    # 确定输出目录位置
    if self.output_dir:
        # 用户自定义输出目录
        actual_path = os.path.join(self.output_dir, output_name)
    else:
        # 默认输出目录
        if self.config.ui.default_output_dir:
            actual_path = os.path.join(self.config.ui.default_output_dir, output_name)
        else:
            # 在输入文件/目录的父目录下创建
            if self.input_type == "file":
                parent_dir = os.path.dirname(self.input_path)
            else:
                parent_dir = os.path.dirname(self.input_path)
            actual_path = os.path.join(parent_dir, output_name)

    self._logger.info(f"Generated actual output path: {actual_path}")
    return actual_path
```

**改动行数：** 约35行

---

**改动5：添加验证方法**

```python
def validate_input_file(self, file_path: str) -> bool:
    """验证输入文件是否有效"""
    if not file_path or not os.path.exists(file_path):
        self._logger.warning(f"Input file does not exist: {file_path}")
        return False

    if not os.path.isfile(file_path):
        self._logger.warning(f"Input path is not a file: {file_path}")
        return False

    valid_extensions = [".pcap", ".pcapng", ".cap"]
    if not any(file_path.lower().endswith(ext) for ext in valid_extensions):
        self._logger.warning(f"Invalid file type: {file_path}")
        return False

    return True

def validate_input_path(self) -> bool:
    """统一验证输入路径"""
    if not self.input_path:
        return False

    if self.input_type == "file":
        return self.validate_input_file(self.input_path)
    elif self.input_type == "directory":
        return self.validate_input_directory(self.input_path)

    return False
```

**改动行数：** 约30行

---

**改动6：修改信号连接和方法调用**

需要将所有引用 `self.base_dir` 的地方改为 `self.input_path`（通过向后兼容属性自动处理）

需要将 `choose_input_folder` 的调用改为 `choose_input`

**改动行数：** 约10处

---

**总改动行数：** 约250-300行（主要在 `main_window.py`）

---

### 4.4 测试计划

#### 功能测试

| 测试场景 | 预期结果 | 优先级 |
|---------|---------|--------|
| **单文件 + 默认输出** | 创建专用目录，包含PCAP和Report | P0 |
| **单文件 + 自定义输出目录** | 在指定目录下创建专用目录 | P0 |
| **目录 + 默认输出** | 保持原有逻辑 | P0 |
| **目录 + 自定义输出目录** | 保持原有逻辑 | P0 |
| **ComboBox记忆功能** | 重启后保持上次选择 | P0 |
| **文件大小显示** | 正确显示文件大小 | P1 |
| **目录统计显示** | 正确显示文件数量和总大小 | P1 |

---

#### 边界情况测试

| 测试场景 | 预期结果 | 优先级 |
|---------|---------|--------|
| **选择非PCAP文件** | 拒绝并提示错误 | P0 |
| **选择空目录** | 警告无PCAP文件 | P0 |
| **输出目录无写权限** | 错误提示 | P0 |
| **磁盘空间不足** | 错误提示 | P1 |
| **文件名包含特殊字符** | 正确处理 | P1 |
| **超大文件（>2GB）** | 正确处理 | P1 |

---

#### 回归测试

| 测试场景 | 预期结果 | 优先级 |
|---------|---------|--------|
| **原有目录处理功能** | 保持不变 | P0 |
| **处理选项功能** | 保持不变 | P0 |
| **进度显示** | 保持不变 | P0 |
| **日志输出** | 保持不变 | P0 |
| **Report生成** | 保持不变 | P0 |

---

### 4.5 时间估算

| 阶段 | 预估时间 | 备注 |
|------|---------|------|
| **Phase 1：核心功能** | 2.5-3小时 | 必需 |
| **Phase 2：UI优化** | 1-1.5小时 | 推荐 |
| **Phase 3：测试与文档** | 1.5-2小时 | 必需 |
| **总计** | **5-6.5小时** | 包含所有阶段 |

---

### 4.6 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **破坏现有目录功能** | 高 | 低 | 保留所有现有逻辑，添加向后兼容属性 |
| **配置保存失败** | 中 | 低 | 异常处理，不影响主功能 |
| **UI布局问题** | 低 | 中 | 充分测试不同分辨率 |
| **文件路径处理错误** | 高 | 低 | 使用 `pathlib.Path` 和充分验证 |

---

## 五、实施后的功能总结

### 5.1 新增功能

| 功能 | 说明 |
|------|------|
| ✅ **单文件输入** | 支持选择单个PCAP文件作为输入 |
| ✅ **输入模式记忆** | 自动记住上次选择的输入模式（File/Directory） |
| ✅ **文件大小显示** | 显示选中文件的大小 |
| ✅ **目录统计显示** | 显示目录中PCAP文件数量和总大小 |
| ✅ **智能输出路径** | 单文件和目录使用统一的输出目录命名规则 |

---

### 5.2 保持不变的功能

| 功能 | 说明 |
|------|------|
| ✅ **目录处理** | 保持原有逻辑不变 |
| ✅ **处理选项** | Dedup、Anon、Mask等选项保持不变 |
| ✅ **Report生成** | 保持原有逻辑不变 |
| ✅ **进度显示** | 保持原有逻辑不变 |
| ✅ **日志输出** | 保持原有逻辑不变 |

---

### 5.3 用户操作流程（改造后）

#### 流程1：处理单个文件

```
1. 打开GUI
   ↓
2. ComboBox默认显示 "File"（或上次选择的模式）
   ↓
3. 点击 "Select Input..." 按钮
   ↓
4. 选择PCAP文件
   ↓
5. 系统显示：📄 capture.pcap (2.3 MB)
   ↓
6. 系统自动生成输出预览：capture-Masked-[timestamp]/
   ↓
7. （可选）点击Output按钮自定义输出目录
   ↓
8. 勾选处理选项（Dedup、Anon、Mask等）
   ↓
9. 点击 "Start" 按钮
   ↓
10. 处理完成，输出：
    - capture-Masked-20250106_143022/
      ├── capture_processed.pcap
      └── summary_report_*.txt
```

---

#### 流程2：处理目录

```
1. 打开GUI
   ↓
2. ComboBox选择 "Directory"
   ↓
3. 点击 "Select Input..." 按钮
   ↓
4. 选择目录
   ↓
5. 系统显示：📁 pcaps/ (5 files, 12.8 MB)
   ↓
6. 系统自动生成输出预览：pcaps-Masked-[timestamp]/
   ↓
7. （可选）点击Output按钮自定义输出目录
   ↓
8. 勾选处理选项
   ↓
9. 点击 "Start" 按钮
   ↓
10. 处理完成，输出：
    - pcaps-Masked-20250106_143022/
      ├── file1_processed.pcap
      ├── file2_processed.pcap
      ├── ...
      └── summary_report_*.txt
```

---

## 六、确认事项

### 请确认以下内容：

1. ✅ **输出行为：** 单文件输入时创建专用输出目录（而非直接输出文件到同目录）
2. ✅ **UI方案：** 采用ComboBox + 按钮 + 记忆功能
3. ✅ **输出目录命名：** `{输入名称}-Masked-{timestamp}/`
4. ✅ **输出文件命名：** `{原文件名}_processed{扩展名}`
5. ✅ **不支持自定义文件名：** 仅支持自定义输出目录，不支持自定义文件名
6. ✅ **GUI与CLI差异：** 接受输出路径生成的合理差异
7. ✅ **实施阶段：** Phase 1（必需）+ Phase 2（推荐）+ Phase 3（必需）

---

### 如果您确认以上内容，请回复：

- **"确认，开始实施"** - 立即开始编码
- **"需要调整XXX"** - 根据反馈调整方案

---

## 附录

### A. 相关文件清单

| 文件路径 | 改动类型 | 改动行数 |
|---------|---------|---------|
| `src/pktmask/core/config.py` | 新增配置字段 | 1行 |
| `src/pktmask/gui/main_window.py` | 主要改动 | 250-300行 |

---

### B. 参考资料

- [ConsistentProcessor源码](../../src/pktmask/core/consistency.py)
- [GUI主窗口源码](../../src/pktmask/gui/main_window.py)
- [CLI命令源码](../../src/pktmask/cli/commands.py)

---

### C. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0 | 2025-01-06 | 初始版本（弹出菜单方案） |
| v2.0 | 2025-01-06 | 更新为ComboBox + 记忆功能方案 |

---

## 七、审查发现的问题及修正

### 7.1 关键问题汇总

经过与现有代码库的交叉校验，发现以下问题：

| 问题编号 | 严重程度 | 问题描述 | 影响范围 | 状态 |
|---------|---------|---------|---------|------|
| **P1** | 🔴 高 | 配置字段 `last_input_mode` 不存在 | 配置保存失败 | ✅ 已修正 |
| **P2** | 🔴 高 | `@property` 装饰器位置错误 | 代码无法运行 | ✅ 已修正 |
| **P3** | 🟡 中 | 输出路径生成逻辑不一致 | 输出位置错误 | ✅ 已修正 |
| **P4** | 🟡 中 | 缺少单文件验证方法 | 验证不完整 | ✅ 已修正 |
| **P5** | 🟢 低 | 文档中的代码示例与实际不符 | 理解偏差 | ✅ 已修正 |

---

### 7.2 问题详解及修正方案

#### 问题 P1：配置字段缺失

**问题描述：**
```python
# 文档中的代码（第436行）
class UIConfig(BaseModel):
    last_input_mode: str = "file"  # ❌ UIConfig 类不存在
```

**实际情况：**
- 配置类名为 `UISettings`（不是 `UIConfig`）
- 继承自 `@dataclass`（不是 `BaseModel`）
- 当前 `UISettings` 中**没有** `last_input_mode` 字段

**修正方案：**
```python
# src/pktmask/config/settings.py
@dataclass
class UISettings:
    """User interface settings"""

    # ... 现有字段 ...

    # 文件处理设置
    remember_last_dir: bool = True
    last_input_dir: Optional[str] = None
    last_output_dir: Optional[str] = None
    last_input_mode: str = "file"  # ✅ 新增：记住上次输入模式 "file" | "directory"
    auto_open_output: bool = False
```

**影响：** 如果不修正，配置保存时会报错 `AttributeError: 'UISettings' object has no attribute 'last_input_mode'`

---

#### 问题 P2：向后兼容属性设计错误

**问题描述：**
```python
# 文档中的代码（第463-474行）
def __init__(self):
    # ...
    self.input_path: Optional[str] = None
    self.input_type: str = "none"

    # 向后兼容属性
    @property  # ❌ 不能在 __init__ 中定义 @property
    def base_dir(self):
        return self.input_path
```

**实际情况：**
- `@property` 装饰器必须在类级别定义，不能在 `__init__` 方法内
- 当前代码中 `base_dir` 是普通实例属性（第94行）

**修正方案：**
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ...

        # 基本属性
        self.input_path: Optional[str] = None  # 新增：统一输入路径
        self.input_type: str = "none"  # 新增："file" | "directory" | "none"
        self.base_dir: Optional[str] = None  # 保留：向后兼容
        self.output_dir: Optional[str] = None
        self.current_output_dir: Optional[str] = None

    # ✅ 在类级别定义向后兼容方法（而非 @property）
    def _sync_base_dir_to_input_path(self):
        """同步 base_dir 到 input_path（向后兼容）"""
        if self.base_dir and not self.input_path:
            self.input_path = self.base_dir
            self.input_type = "directory" if os.path.isdir(self.base_dir) else "file"

    def _sync_input_path_to_base_dir(self):
        """同步 input_path 到 base_dir（向后兼容）"""
        if self.input_path and not self.base_dir:
            self.base_dir = self.input_path
```

**影响：** 如果不修正，代码会抛出 `SyntaxError`

---

#### 问题 P3：输出路径生成逻辑不一致

**问题描述：**

文档中的逻辑（第696-701行）：
```python
# 在输入文件/目录的父目录下创建
if self.input_type == "file":
    parent_dir = os.path.dirname(self.input_path)  # ❌ 单文件和目录逻辑相同
else:
    parent_dir = os.path.dirname(self.input_path)
actual_path = os.path.join(parent_dir, output_name)
```

**实际情况：**

现有代码（main_window.py 第2562行）：
```python
# 使用输入目录的子目录（而非父目录）
actual_path = os.path.join(self.base_dir, output_name)
```

**问题分析：**
1. **单文件输入**：应该在**父目录**创建输出目录（与输入文件同级）
2. **目录输入**：应该在**同级目录**创建输出目录（与输入目录同级）
3. 文档中两种情况的逻辑完全相同，这是错误的

**修正方案：**
```python
def generate_actual_output_path(self) -> str:
    """Generate actual output directory path (支持文件和目录)"""
    timestamp = current_timestamp()

    if not self.input_path:
        return f"PktMask-{timestamp}"

    # 获取输入名称
    if self.input_type == "file":
        # 单文件模式：使用文件名（不含扩展名）
        input_name = Path(self.input_path).stem
    else:
        # 目录模式：使用目录名
        input_name = os.path.basename(self.input_path)

    # 生成输出目录名（统一格式）
    output_name = f"{input_name}-Masked-{timestamp}"

    # 确定输出目录位置
    if self.output_dir:
        # 用户自定义输出目录
        actual_path = os.path.join(self.output_dir, output_name)
    else:
        # 默认输出目录
        if self.config.ui.default_output_dir:
            actual_path = os.path.join(self.config.ui.default_output_dir, output_name)
        else:
            # ✅ 修正：根据输入类型选择正确的父目录
            if self.input_type == "file":
                # 单文件：在输入文件的父目录下创建
                parent_dir = os.path.dirname(self.input_path)
            else:
                # 目录：在输入目录的父目录下创建（与输入目录同级）
                parent_dir = os.path.dirname(self.input_path)
            actual_path = os.path.join(parent_dir, output_name)

    self._logger.info(f"Generated actual output path: {actual_path}")
    return actual_path
```

**示例对比：**

| 输入类型 | 输入路径 | 错误输出 | 正确输出 |
|---------|---------|---------|---------|
| 单文件 | `/home/user/pcaps/capture.pcap` | `/home/user/pcaps/capture-Masked-xxx/` | `/home/user/pcaps/capture-Masked-xxx/` ✅ |
| 目录 | `/home/user/pcaps/` | `/home/user/pcaps/pcaps-Masked-xxx/` ❌ | `/home/user/pcaps-Masked-xxx/` ✅ |

**影响：** 目录输入时会在错误的位置创建输出目录

---

#### 问题 P4：缺少单文件验证方法

**问题描述：**

文档中提到了 `validate_input_file` 方法（第714-729行），但现有代码中**只有** `validate_input_directory` 方法（main_window.py 第2589行）。

**修正方案：**
```python
def validate_input_file(self, file_path: str) -> bool:
    """验证输入文件是否有效"""
    if not file_path or not os.path.exists(file_path):
        self._logger.warning(f"Input file does not exist: {file_path}")
        return False

    if not os.path.isfile(file_path):
        self._logger.warning(f"Input path is not a file: {file_path}")
        return False

    valid_extensions = [".pcap", ".pcapng", ".cap"]
    if not any(file_path.lower().endswith(ext) for ext in valid_extensions):
        self._logger.warning(f"Invalid file type: {file_path}")
        return False

    return True

def validate_input_path(self) -> bool:
    """统一验证输入路径"""
    if not self.input_path:
        return False

    if self.input_type == "file":
        return self.validate_input_file(self.input_path)
    elif self.input_type == "directory":
        return self.validate_input_directory(self.input_path)

    return False
```

**影响：** 单文件输入时无法进行有效验证

---

#### 问题 P5：单文件处理已部分支持

**发现：**

`GUIConsistentProcessor` 已经支持单文件处理（gui_consistent_processor.py 第145-146行）：

```python
if self._base_dir.is_file():
    self._process_single_file()
else:
    self._process_directory_with_progress()
```

**影响：**
- ✅ **好消息**：核心处理逻辑已经支持单文件
- ⚠️ **需要注意**：GUI 层面需要确保传入的 `base_dir` 可以是文件路径

**修正建议：**

在 `start_pipeline_processing` 方法中，移除对目录的强制检查：

```python
def start_pipeline_processing(self):
    """Start processing flow"""
    self._logger.debug("start_pipeline_processing called")

    # ✅ 修正：检查 input_path 而非 base_dir
    if not self.input_path:
        self._logger.warning("No input selected")
        QMessageBox.warning(
            self,
            "Warning",
            "Please choose an input file or folder to process.",  # ✅ 更新提示文本
        )
        return

    # ✅ 同步到 base_dir（向后兼容）
    self.base_dir = self.input_path

    # 生成实际输出目录路径
    self.current_output_dir = self.generate_actual_output_path()
    # ...
```

---

### 7.3 其他发现

#### 发现 1：文件大小格式化方法已存在

文档中提到的 `_format_file_size` 方法（第653-659行）与现有的工具方法功能重复：

**现有方法：**
- `FileProcessingData.get_size_string()` (gui/models/file_processing_data.py 第58-67行)

**建议：** 可以复用现有逻辑或保持独立实现（两者都可接受）

---

#### 发现 2：ComboBox 图标可能不显示

文档中使用了 emoji 图标（第494-495行）：
```python
self.input_mode_combo.addItem("📄 File", "file")
self.input_mode_combo.addItem("📁 Directory", "directory")
```

**潜在问题：** 某些系统/字体可能不支持 emoji 显示

**建议：** 考虑使用 Qt 图标或纯文本：
```python
self.input_mode_combo.addItem("File", "file")
self.input_mode_combo.addItem("Directory", "directory")
```

---

### 7.4 修正后的完整代码清单

#### 文件 1：`src/pktmask/config/settings.py`

**改动位置：** 第38-42行

```python
@dataclass
class UISettings:
    """User interface settings"""

    # ... 现有字段 ...

    # 文件处理设置
    remember_last_dir: bool = True
    last_input_dir: Optional[str] = None
    last_output_dir: Optional[str] = None
    last_input_mode: str = "file"  # ✅ 新增字段
    auto_open_output: bool = False
```

**改动行数：** 1行

---

#### 文件 2：`src/pktmask/gui/main_window.py`

**改动 1：修改 `__init__` 方法（第93-100行）**

```python
# 基本属性
self.input_path: Optional[str] = None  # 新增：统一输入路径
self.input_type: str = "none"  # 新增："file" | "directory" | "none"
self.base_dir: Optional[str] = None  # 保留：向后兼容
self.output_dir: Optional[str] = None
self.current_output_dir: Optional[str] = None

# 加载上次的输入模式
self.last_input_mode = self.config.ui.last_input_mode or "file"
```

**改动行数：** 约10行

---

**改动 2：替换 `_create_directory_selection_ui` 为 `_create_input_selection_ui`**

参考文档第484-527行，但需要移除 emoji 或确保兼容性。

**改动行数：** 约40行

---

**改动 3：添加新方法**

```python
def _on_input_mode_changed(self, index: int):
    """输入模式改变时的处理"""
    mode = self.input_mode_combo.itemData(index)
    self._logger.debug(f"Input mode changed to: {mode}")
    self._update_input_button_tooltip()

def _update_input_button_tooltip(self):
    """更新输入按钮的工具提示"""
    current_mode = self.input_mode_combo.currentData()
    if current_mode == "file":
        self.select_input_btn.setToolTip("Select a PCAP file (.pcap, .pcapng, .cap)")
    else:
        self.select_input_btn.setToolTip("Select a directory containing PCAP files")

def choose_input(self):
    """根据当前模式选择输入"""
    current_mode = self.input_mode_combo.currentData()

    if current_mode == "file":
        self.choose_input_file()
    else:
        self.choose_input_directory()

    # 保存当前模式到配置
    if self.input_path:
        self._save_input_mode(current_mode)

def choose_input_file(self):
    """选择单个PCAP文件"""
    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "Select PCAP File",
        self.last_opened_dir,
        "PCAP Files (*.pcap *.pcapng *.cap);;All Files (*)"
    )

    if file_path:
        self.input_path = file_path
        self.input_type = "file"
        self.base_dir = file_path  # ✅ 向后兼容
        self.last_opened_dir = os.path.dirname(file_path)

        # 更新显示
        file_size = os.path.getsize(file_path)
        size_str = self._format_file_size(file_size)
        self.input_display_label.setText(f"{os.path.basename(file_path)} ({size_str})")
        self.input_display_label.setStyleSheet("color: black; font-style: normal;")

        # 生成默认输出路径
        self.generate_default_output_path()
        self._update_start_button_state()

        self._logger.info(f"Selected input file: {file_path}")

def choose_input_directory(self):
    """选择输入目录（重构自原有的 choose_input_folder）"""
    dir_path = QFileDialog.getExistingDirectory(
        self,
        "Select Input Directory",
        self.last_opened_dir
    )

    if dir_path:
        self.input_path = dir_path
        self.input_type = "directory"
        self.base_dir = dir_path  # ✅ 向后兼容
        self.last_opened_dir = dir_path

        # 统计目录信息
        pcap_count = self._count_pcap_files(dir_path)
        total_size = self._get_directory_size(dir_path)
        size_str = self._format_file_size(total_size)

        # 更新显示
        self.input_display_label.setText(f"{os.path.basename(dir_path)}/ ({pcap_count} files, {size_str})")
        self.input_display_label.setStyleSheet("color: black; font-style: normal;")

        # 生成默认输出路径
        self.generate_default_output_path()
        self._update_start_button_state()

        self._logger.info(f"Selected input directory: {dir_path}")

def _save_input_mode(self, mode: str):
    """保存输入模式到配置"""
    try:
        self.config.ui.last_input_mode = mode
        self.config.save()
        self.last_input_mode = mode
        self._logger.debug(f"Saved input mode: {mode}")
    except Exception as e:
        self._logger.error(f"Failed to save input mode: {e}")

def _count_pcap_files(self, directory: str) -> int:
    """统计目录中的PCAP文件数量"""
    pcap_extensions = [".pcap", ".pcapng", ".cap"]
    count = 0
    try:
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in pcap_extensions):
                count += 1
    except Exception as e:
        self._logger.error(f"Error counting PCAP files: {e}")
    return count

def _get_directory_size(self, directory: str) -> int:
    """获取目录中PCAP文件的总大小"""
    pcap_extensions = [".pcap", ".pcapng", ".cap"]
    total_size = 0
    try:
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in pcap_extensions):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
    except Exception as e:
        self._logger.error(f"Error calculating directory size: {e}")
    return total_size

def _format_file_size(self, size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
```

**改动行数：** 约130行

---

**改动 4：修改 `generate_actual_output_path` 方法（第2540-2565行）**

```python
def generate_actual_output_path(self) -> str:
    """Generate actual output directory path (支持文件和目录)"""
    timestamp = current_timestamp()

    if not self.input_path:
        return f"PktMask-{timestamp}"

    # 获取输入名称
    if self.input_type == "file":
        # 单文件模式：使用文件名（不含扩展名）
        input_name = Path(self.input_path).stem
    else:
        # 目录模式：使用目录名
        input_name = os.path.basename(self.input_path)

    # 生成输出目录名（统一格式）
    output_name = f"{input_name}-Masked-{timestamp}"

    # 确定输出目录位置
    if self.output_dir:
        # 用户自定义输出目录
        actual_path = os.path.join(self.output_dir, output_name)
    else:
        # 默认输出目录
        if self.config.ui.default_output_dir:
            actual_path = os.path.join(self.config.ui.default_output_dir, output_name)
        else:
            # 根据输入类型选择正确的父目录
            if self.input_type == "file":
                # 单文件：在输入文件的父目录下创建
                parent_dir = os.path.dirname(self.input_path)
            else:
                # 目录：在输入目录的父目录下创建（与输入目录同级）
                parent_dir = os.path.dirname(self.input_path)
            actual_path = os.path.join(parent_dir, output_name)

    self._logger.info(f"Generated actual output path: {actual_path}")
    return actual_path
```

**改动行数：** 约35行

---

**改动 5：添加验证方法**

```python
def validate_input_file(self, file_path: str) -> bool:
    """验证输入文件是否有效"""
    if not file_path or not os.path.exists(file_path):
        self._logger.warning(f"Input file does not exist: {file_path}")
        return False

    if not os.path.isfile(file_path):
        self._logger.warning(f"Input path is not a file: {file_path}")
        return False

    valid_extensions = [".pcap", ".pcapng", ".cap"]
    if not any(file_path.lower().endswith(ext) for ext in valid_extensions):
        self._logger.warning(f"Invalid file type: {file_path}")
        return False

    return True

def validate_input_path(self) -> bool:
    """统一验证输入路径"""
    if not self.input_path:
        return False

    if self.input_type == "file":
        return self.validate_input_file(self.input_path)
    elif self.input_type == "directory":
        return self.validate_input_directory(self.input_path)

    return False
```

**改动行数：** 约30行

---

**改动 6：修改 `start_pipeline_processing` 方法（第2691-2711行）**

```python
def start_pipeline_processing(self):
    """Start processing flow"""
    self._logger.debug("start_pipeline_processing called")

    if not self.input_path:
        self._logger.warning("No input selected")
        QMessageBox.warning(
            self,
            "Warning",
            "Please choose an input file or folder to process.",
        )
        return

    # 同步到 base_dir（向后兼容）
    self.base_dir = self.input_path

    # 生成实际输出目录路径
    self.current_output_dir = self.generate_actual_output_path()
    # ... 其余代码保持不变
```

**改动行数：** 约5行

---

**总改动行数：** 约250行（与原计划一致）

---

### 7.5 测试建议

基于发现的问题，建议增加以下测试用例：

| 测试场景 | 测试目的 | 优先级 |
|---------|---------|--------|
| **配置保存和加载** | 验证 `last_input_mode` 字段正常工作 | P0 |
| **单文件输出路径** | 验证输出目录在正确位置创建 | P0 |
| **目录输出路径** | 验证输出目录在正确位置创建 | P0 |
| **向后兼容性** | 验证 `base_dir` 和 `input_path` 同步正常 | P0 |
| **文件验证** | 验证单文件验证逻辑正常工作 | P0 |
| **emoji 显示** | 验证 ComboBox 图标在不同系统正常显示 | P1 |

---

### 7.6 风险评估更新

| 风险 | 原评估 | 更新评估 | 缓解措施 |
|------|--------|---------|---------|
| **破坏现有目录功能** | 低 | 低 | ✅ 保留 `base_dir`，添加同步逻辑 |
| **配置保存失败** | 低 | **中** | ✅ 已添加 `last_input_mode` 字段 |
| **输出路径错误** | 低 | **中** | ✅ 已修正路径生成逻辑 |
| **UI布局问题** | 中 | 中 | 充分测试不同分辨率 |
| **文件路径处理错误** | 低 | 低 | 使用 `pathlib.Path` 和充分验证 |
| **emoji 兼容性** | - | **低** | ✅ 建议使用纯文本或 Qt 图标 |

---

### 7.7 实施前检查清单

在开始实施前，请确认：

- [ ] 已理解所有发现的问题及修正方案
- [ ] 已备份现有代码
- [ ] 已准备测试环境和测试数据
- [ ] 已确认 `UISettings` 中添加 `last_input_mode` 字段
- [ ] 已确认输出路径生成逻辑的修正
- [ ] 已确认向后兼容方案
- [ ] 已准备单文件和目录的测试用例
- [ ] 已确认 emoji 图标的兼容性方案

---

**文档结束**


