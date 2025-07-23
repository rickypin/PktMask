# PktMask Documentation Management Quick Guide

> **Version**: v1.0.0
> **Created**: 2025-07-22
> **Scope**: PktMask ≥ 4.0.0

---

## 🚀 快速开始

### 1. 创建新文档

```bash
# 创建用户指南
./scripts/docs/manage-docs.sh create user-guide new-feature-guide

# 创建开发者文档
./scripts/docs/manage-docs.sh create dev-guide contribution-workflow

# 创建工具文档
./scripts/docs/manage-docs.sh create tool-guide advanced-analyzer
```

### 2. 运行质量检查

```bash
# 运行所有检查
./scripts/docs/manage-docs.sh check

# 仅检查链接
./scripts/docs/manage-docs.sh check-links

# 仅检查格式
./scripts/docs/manage-docs.sh check-format
```

### 3. 生成统计报告

```bash
# 生成文档统计
./scripts/docs/manage-docs.sh stats
```

---

## 📋 文档创建流程

### 标准流程

1. **确定文档类型和目标受众**
   - 用户文档 (`user-guide`)
   - 开发者文档 (`dev-guide`)
   - API 文档 (`api-doc`)
   - 架构文档 (`arch-doc`)
   - 工具文档 (`tool-guide`)

2. **使用管理工具创建文档**
   ```bash
   ./scripts/docs/manage-docs.sh create <type> <name>
   ```

3. **编辑文档内容**
   - 使用提供的模板
   - 遵循格式规范
   - 添加必要的示例

4. **更新索引**
   ```bash
   ./scripts/docs/manage-docs.sh update-index <directory>
   ```

5. **运行质量检查**
   ```bash
   ./scripts/docs/manage-docs.sh check
   ```

6. **提交变更**
   ```bash
   git add docs/
   git commit -m "docs: add new documentation"
   ```

---

## 🔧 常用命令

### 文档管理

| 命令 | 用途 | 示例 |
|------|------|------|
| `create` | 创建新文档 | `create user-guide installation` |
| `check` | 运行所有检查 | `check` |
| `stats` | 生成统计报告 | `stats` |
| `validate` | 验证目录结构 | `validate` |

### 质量检查

| 命令 | 用途 | 说明 |
|------|------|------|
| `check-links` | 检查链接有效性 | 验证内部链接是否正确 |
| `check-format` | 检查格式规范 | 验证命名和格式标准 |
| `check-freshness` | 检查文档时效性 | 识别需要更新的文档 |

---

## 📝 文档编写规范

### 文件命名

```bash
✅ 正确示例
installation-guide.md
user-manual.md
api-reference.md

❌ 错误示例
Installation Guide.md
User_Manual.md
APIReference.md
```

### 文档头部

```markdown
# 文档标题

> **版本**: v1.0.0  
> **创建日期**: 2025-07-22  
> **最后更新**: 2025-07-22  
> **适用范围**: PktMask ≥ 4.0.0  
> **维护状态**: ✅ 活跃维护  

---
```

### 章节结构

```markdown
## 1. 概述
### 1.1 子章节

## 2. 主要内容
### 2.1 子章节
### 2.2 子章节

---

> 💡 **提示**: 补充说明
```

---

## 🔗 目录结构

```
docs/
├── README.md                    # 📚 文档中心入口
├── user/                        # 👥 用户文档
├── dev/                         # 🛠️ 开发者文档
├── api/                         # 📚 API 文档
├── architecture/                # 🏛️ 架构文档
├── tools/                       # 🔧 工具文档
└── archive/                     # 📦 历史存档
```

---

## ⚡ 快速参考

### 创建文档类型

| 类型 | 目录 | 用途 |
|------|------|------|
| `user-guide` | `docs/user/` | 最终用户使用指南 |
| `dev-guide` | `docs/dev/` | 开发者技术文档 |
| `api-doc` | `docs/api/` | API 接口参考 |
| `arch-doc` | `docs/architecture/` | 架构设计文档 |
| `tool-guide` | `docs/tools/` | 工具使用指南 |

### 质量检查项目

- ✅ 文件命名规范 (kebab-case)
- ✅ 文档头部信息完整
- ✅ 内部链接有效性
- ✅ 章节结构规范
- ✅ 文档时效性

### 维护周期

| 频率 | 任务 |
|------|------|
| 每周 | 链接检查 |
| 每月 | 内容更新 |
| 每季度 | 结构优化 |
| 每年 | 历史存档 |

---

## 🆘 故障排除

### 常见问题

**Q: 创建文档时提示权限错误？**
A: 确保脚本有执行权限：`chmod +x scripts/docs/manage-docs.sh`

**Q: 链接检查失败？**
A: 检查相对路径是否正确，确保目标文件存在

**Q: 格式检查不通过？**
A: 检查文件命名是否使用 kebab-case，文档头部信息是否完整

**Q: 如何批量更新文档？**
A: 使用 `find` 命令结合脚本进行批量操作

### 获取帮助

```bash
# 查看帮助信息
./scripts/docs/manage-docs.sh help

# 查看详细指南
cat docs/DOCS_DIRECTORY_STRUCTURE_GUIDE.md
```

---

## 📞 支持

- **详细指南**: [docs/DOCS_DIRECTORY_STRUCTURE_GUIDE.md](DOCS_DIRECTORY_STRUCTURE_GUIDE.md)
- **GitHub Issues**: 报告问题和建议
- **项目讨论**: 技术交流和问答

---

> 💡 **提示**: 这是一个快速参考指南。完整的文档管理规范请参考 [DOCS_DIRECTORY_STRUCTURE_GUIDE.md](DOCS_DIRECTORY_STRUCTURE_GUIDE.md)。
