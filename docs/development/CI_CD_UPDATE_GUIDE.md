# CI/CD 配置更新指南

## 需要更新的文件

### 1. `.github/workflows/build.yml`

**当前问题**：
- 第29-32行：尝试从 pyproject.toml 生成 requirements.txt
- 这是不必要的，因为我们已经在 pyproject.toml 中定义了所有依赖

**建议修改**：
```yaml
# 替换第28-32行
- name: Install dependencies
  run: |
    pip install --upgrade pip
    pip install -e .
    pip install pyinstaller
```

### 2. `.github/workflows/test.yml`

**当前问题**：
- 多处引用 requirements.txt 作为缓存键的一部分
- 可以简化为仅使用 pyproject.toml

**建议修改**：

1. 更新缓存键（第40, 94, 103行）：
```yaml
key: ${{ runner.os }}-pip-${{ env.CACHE_VERSION }}-${{ hashFiles('**/pyproject.toml') }}
```

2. 确保安装命令正确（已经正确使用 `pip install -e ".[dev]"`）

## 临时解决方案

如果不想立即修改 CI/CD 配置，可以生成一个 requirements.txt 文件：

```bash
# 使用 pip-tools 生成 requirements.txt
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt

# 或者使用 pip freeze（不推荐，会包含所有已安装的包）
pip freeze > requirements.txt
```

## 长期建议

1. **统一依赖管理**：
   - 仅使用 pyproject.toml 作为依赖声明的唯一来源
   - CI/CD 中直接使用 `pip install -e .` 或 `pip install -e ".[dev]"`

2. **更新缓存策略**：
   - 使用 pyproject.toml 的哈希值作为缓存键
   - 考虑添加 Python 版本到缓存键中

3. **简化构建流程**：
   - 移除不必要的 pip-compile 步骤
   - 直接从 pyproject.toml 安装依赖

## 示例：更新后的 build.yml 片段

```yaml
- name: Set up Python ${{ matrix.python-version }}
  uses: actions/setup-python@v4
  with:
    python-version: ${{ matrix.python-version }}

- name: Cache pip packages
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('pyproject.toml') }}
    restore-keys: |
      ${{ runner.os }}-pip-

- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -e .
    pip install pyinstaller

- name: Build package
  run: python -m build
```

## 注意事项

1. 更新 CI/CD 配置前，确保在本地测试构建流程
2. 考虑在 PR 中逐步更新，避免一次性改动过多
3. 保留旧的工作流程文件作为备份，直到新配置稳定运行
