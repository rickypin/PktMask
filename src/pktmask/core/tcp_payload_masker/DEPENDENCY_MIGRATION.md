# TCP Payload Masker 依赖管理迁移说明

## 变更说明

为了统一项目依赖管理，我们已将此模块的依赖声明迁移到项目根目录的 `pyproject.toml`。

### 已移除的文件
- `requirements.txt` → `requirements.txt.bak`（备份）
- `setup.py` → `setup.py.bak`（备份）

### 依赖管理方式
所有依赖现在由顶层 `pyproject.toml` 统一管理：
- **核心依赖**：`scapy`、`typing-extensions` 等已合并到主项目依赖
- **开发依赖**：测试和开发工具已合并到 `[project.optional-dependencies]` 的 `dev` 组
- **性能依赖**：`psutil`、`memory-profiler` 已添加到新的 `performance` 组

### 安装方式

```bash
# 安装核心依赖（从项目根目录）
pip install -e .

# 安装开发依赖
pip install -e ".[dev]"

# 安装性能监控依赖
pip install -e ".[performance]"

# 安装所有依赖
pip install -e ".[dev,performance]"
```

### 导入方式
模块导入方式保持不变：
```python
from pktmask.core.tcp_payload_masker import TCPPayloadMasker
from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe
```

### 注意事项
1. 此模块不再支持独立安装
2. 不再维护独立的版本号
3. 所有依赖更新需通过顶层 `pyproject.toml` 进行

### 备份文件
备份文件（`.bak`）将保留 30 天，之后会被永久删除。

---
*迁移日期：2025-01-08*
