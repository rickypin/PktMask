# 子包依赖管理分散问题分析与解决方案

## 1. 问题分析

### 1.1 当前状况
在 `src/pktmask/core/tcp_payload_masker/` 目录下发现：
- `requirements.txt` - 声明了 scapy 等依赖
- `setup.py` - 完整的包配置，包含入口点和依赖声明

而项目根目录已使用 `pyproject.toml` 进行统一依赖管理。

### 1.2 问题影响

#### 依赖版本冲突风险
- **子包**: `scapy>=2.4.0,<3.0.0` (requirements.txt)
- **主项目**: `scapy>=2.5.0` (pyproject.toml)
- **风险**: 版本约束不一致可能导致安装问题

#### 管理复杂度增加
1. 开发者需要在多处更新依赖版本
2. CI/CD 需要处理多个依赖文件
3. 依赖审计和安全扫描变得复杂

#### 潜在的命名冲突
- `setup.py` 定义了独立包名 `tcp-payload-masker`
- 包含独立的 console_scripts 入口点
- 可能与主项目产生命名空间冲突

### 1.3 根因分析
该子包可能原本设计为独立模块，后来被整合到主项目中，但未完全清理独立包的配置文件。

## 2. 解决方案

### 2.1 短期方案：依赖合并

#### 步骤 1：审查依赖差异
```bash
# 比较依赖版本
diff <(grep -E "^[a-zA-Z]" src/pktmask/core/tcp_payload_masker/requirements.txt | sort) \
     <(grep -E "^\s*\"[a-zA-Z]" pyproject.toml | grep -v "#" | sort)
```

#### 步骤 2：合并到 pyproject.toml
1. 将子包特有的依赖添加到主项目（如有）
2. 统一版本约束，使用更严格的版本范围
3. 保留性能监控等可选依赖到 `[project.optional-dependencies]`

#### 步骤 3：清理冗余文件
```bash
# 备份后删除
mv src/pktmask/core/tcp_payload_masker/requirements.txt \
   src/pktmask/core/tcp_payload_masker/requirements.txt.bak
   
mv src/pktmask/core/tcp_payload_masker/setup.py \
   src/pktmask/core/tcp_payload_masker/setup.py.bak
```

### 2.2 长期方案：模块化重构

#### 选项 A：完全整合
将 tcp_payload_masker 作为内部模块：
1. 移除所有独立包配置
2. 依赖完全由顶层 pyproject.toml 管理
3. 不再支持独立安装

#### 选项 B：插件化架构
如果需要保持模块独立性：
1. 将其移到独立仓库
2. 主项目通过依赖引用
3. 使用 namespace packages 避免冲突

## 3. 实施计划

### 3.1 第一阶段：依赖审计（Day 1）

创建依赖对比报告：

```python
# scripts/audit_dependencies.py
import toml
import configparser

def audit_dependencies():
    # 读取主项目依赖
    with open('pyproject.toml', 'r') as f:
        main_deps = toml.load(f)['project']['dependencies']
    
    # 读取子包依赖
    sub_deps = []
    with open('src/pktmask/core/tcp_payload_masker/requirements.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                sub_deps.append(line)
    
    # 分析差异
    print("=== 依赖对比分析 ===")
    print(f"主项目依赖数: {len(main_deps)}")
    print(f"子包依赖数: {len(sub_deps)}")
    
    # 版本冲突检查
    conflicts = check_version_conflicts(main_deps, sub_deps)
    if conflicts:
        print("\n⚠️  发现版本冲突:")
        for pkg, versions in conflicts.items():
            print(f"  {pkg}: 主项目={versions['main']}, 子包={versions['sub']}")
    
    return main_deps, sub_deps, conflicts

if __name__ == "__main__":
    audit_dependencies()
```

### 3.2 第二阶段：合并实施（Day 2）

更新 pyproject.toml：

```toml
[project]
dependencies = [
    "scapy>=2.5.0",  # 统一使用主项目版本
    # ... 其他依赖
    "typing-extensions>=4.0.0;python_version<'3.8'",  # 从子包合并
]

[project.optional-dependencies]
# 新增性能监控组
performance = [
    "psutil>=5.9.0",
    "memory-profiler>=0.60.0"
]
```

### 3.3 第三阶段：验证测试（Day 3）

1. **安装测试**
   ```bash
   # 清理环境
   pip uninstall -y pktmask tcp-payload-masker
   
   # 重新安装
   pip install -e .
   pip install -e ".[dev,performance]"
   ```

2. **功能测试**
   ```bash
   # 测试 tcp_payload_masker 模块
   python -m pytest tests/unit/test_tcp_payload_masker.py
   ```

3. **导入测试**
   ```python
   # 确保模块可正常导入
   from pktmask.core.tcp_payload_masker import TCPPayloadMasker
   ```

## 4. 迁移检查清单

- [ ] 审计所有依赖版本差异
- [ ] 更新 pyproject.toml 合并依赖
- [ ] 备份并删除子包的 requirements.txt
- [ ] 备份并删除子包的 setup.py
- [ ] 更新文档说明依赖管理变更
- [ ] 运行完整测试套件
- [ ] 更新 CI/CD 配置（如有引用子包依赖文件）
- [ ] 通知团队成员更新开发环境

## 5. 风险与缓解

### 5.1 风险评估
- **低风险**: 依赖版本统一可能影响特定功能
- **中风险**: 移除独立安装能力可能影响某些用户
- **低风险**: CI/CD 脚本可能需要更新

### 5.2 缓解措施
1. 保留备份文件 `.bak` 30天
2. 在 CHANGELOG 中详细记录变更
3. 提供迁移脚本帮助用户更新

## 6. 长期建议

1. **建立依赖管理规范**
   - 所有 Python 依赖必须在顶层 pyproject.toml 声明
   - 子模块不应包含独立的依赖配置文件
   - 使用 dependabot 或 renovate 自动更新依赖

2. **模块边界清晰化**
   - 明确哪些模块是内部使用
   - 哪些模块可能独立发布
   - 为可能独立的模块预留接口

3. **持续集成改进**
   - 添加依赖冲突检查到 CI
   - 定期运行依赖审计
   - 自动化安全漏洞扫描
