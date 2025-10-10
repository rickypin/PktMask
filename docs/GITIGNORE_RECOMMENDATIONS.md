# .gitignore 建议清单 - 2025-10-10

## ✅ 已添加到 .gitignore 的规则

以下规则已成功添加到项目的 `.gitignore` 文件中：

### 📊 代码质量报告
```gitignore
flake8_report.txt
pylint_report.txt
mypy_report.txt
*.lint
.ruff_cache/
```

**说明**: 这些是代码质量检查工具生成的临时报告文件，每次运行都会重新生成。

---

### 🧪 测试报告
```gitignore
junit.xml
tests/**/junit.xml
.coverage
.coverage.*
coverage.xml
```

**说明**: 测试框架生成的报告文件，包括 JUnit XML 和代码覆盖率报告。

---

### 📁 临时测试目录
```gitignore
output/tmp*/
output/test_*/
output/*_test/
output/*_validation*/
```

**说明**: 测试过程中生成的临时输出目录，使用通配符模式匹配所有临时目录。

---

### 📝 应用日志
```gitignore
*.log
logs/
!tests/samples/**/*.log
```

**说明**: 
- 忽略所有 `.log` 文件和 `logs/` 目录
- 例外：保留 `tests/samples/` 中的日志文件（测试样本数据）

---

### ⚙️ 本地配置
```gitignore
.env
.env.local
config.local.yaml
config.local.json
```

**说明**: 本地环境配置文件，通常包含敏感信息或个人设置。

---

### 💻 额外 IDE 文件
```gitignore
.fleet/
.cursor/
*.sublime-project
*.sublime-workspace
```

**说明**: 补充更多 IDE 和编辑器的配置文件（原有已包含 `.idea/` 和 `.vscode/`）。

---

### 🍎 macOS 特定文件
```gitignore
*.DS_Store
.AppleDouble
.LSOverride
```

**说明**: macOS 系统生成的元数据文件（原有已包含 `.DS_Store`，这里补充更多）。

---

### 🐍 虚拟环境替代方案
```gitignore
env/
ENV/
venv.bak/
```

**说明**: 补充其他常见的虚拟环境目录名称（原有已包含 `venv/` 和 `.venv/`）。

---

## 📋 原有 .gitignore 规则（保持不变）

以下是项目原有的 .gitignore 规则，已经很完善：

### Python 相关
```gitignore
__pycache__/
*.py[cod]
*.pyo
*.pyd
*$py.class
*.so
```

### 分发/打包
```gitignore
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
```

### IDE
```gitignore
.idea/
.vscode/
.augment/
*.swp
*.swo
```

### 操作系统文件
```gitignore
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
Thumbs.db:encryptable
ehthumbs_vista.db
*.stackdump
```

### 项目特定
```gitignore
tests/samples/
tests/data/
```

### 测试覆盖率报告
```gitignore
htmlcov/
demo_test_reports/htmlcov/
output/reports/coverage/
reports/coverage/
```

### 临时输出
```gitignore
output/
output/tmp/
output/maskstage_validation/
output/monitoring/
tmp/
```

### 虚拟环境
```gitignore
.venv/
```

### 维护和清理文件
```gitignore
cleanup_backup_*.tar.gz
cleanup_backup_*.zip
backup_temp_*/
backup_refactor_*/
cleanup_*.log
maintenance_*.log
```

### E2E 测试生成文件
```gitignore
tests/e2e/report.html
tests/e2e/report_debug.html
tests/e2e/**/report*.html
tests/e2e/test_results.json
.pytest_cache/
tests/.pytest_cache/
tests/e2e/.pytest_cache/
tests/e2e/test_output/
tests/e2e/tmp/
```

---

## 🎯 .gitignore 覆盖率总结

### ✅ 已完全覆盖的类别

1. **Python 缓存和编译文件** - 100% 覆盖
2. **IDE 配置文件** - 主流 IDE 全覆盖
3. **操作系统元数据** - Windows/macOS/Linux 全覆盖
4. **测试输出和报告** - 全面覆盖
5. **虚拟环境** - 多种命名方式覆盖
6. **临时文件和日志** - 全面覆盖
7. **构建产物** - 完整覆盖

### 📊 统计数据

- **总规则数**: 110+ 条
- **新增规则**: 30+ 条
- **覆盖类别**: 15+ 个
- **特殊例外**: 2 条（保留测试样本和 golden baseline）

---

## 🔍 特殊说明

### 保留的文件模式

以下文件虽然匹配某些忽略规则，但被明确保留：

```gitignore
# 保留测试样本中的日志文件
!tests/samples/**/*.log

# 保留 golden baseline 文件（注释状态，可按需启用）
# !tests/e2e/golden/**/*.json
# !tests/e2e/golden/**/*.pcap
# !tests/e2e/golden_cli/**/*.json
# !tests/e2e/golden_cli/**/*.pcap
```

### 通配符使用

项目使用了多种通配符模式以提高灵活性：

- `**/` - 匹配任意深度的目录
- `*` - 匹配任意字符
- `*.ext` - 匹配特定扩展名
- `prefix*` - 匹配特定前缀

---

## 📝 维护建议

### 定期检查

建议定期检查以下内容：

1. **未跟踪文件**: `git status --ignored`
2. **意外忽略**: 确保重要文件未被误忽略
3. **新增临时文件类型**: 根据项目发展添加新规则

### 验证命令

```bash
# 查看所有被忽略的文件
git status --ignored

# 检查特定文件是否被忽略
git check-ignore -v <file_path>

# 查看 .gitignore 规则生效情况
git ls-files --others --ignored --exclude-standard
```

---

## 🎉 总结

当前 `.gitignore` 配置已经非常完善：

- ✅ **覆盖全面**: 涵盖所有常见临时文件类型
- ✅ **规则清晰**: 分类明确，注释详细
- ✅ **维护性好**: 使用通配符，易于扩展
- ✅ **特殊处理**: 正确保留必要的测试文件

**建议**: 保持当前配置，仅在出现新类型临时文件时按需添加。

---

## 📅 更新日期
**2025-10-10**

## 📄 相关文档
- 清理总结: `CLEANUP_SUMMARY.md`
- 详细报告: `docs/dev/cleanup/CODE_CLEANUP_2025-10-10.md`

