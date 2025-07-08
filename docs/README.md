# PktMask 文档导航

欢迎查阅 PktMask 项目文档。本目录包含了项目的所有文档资料。

## 📚 文档结构

### 🔄 current/ - 当前版本文档
这些是与当前代码版本同步的文档，是您应该优先参考的资料。

- **[架构文档](current/architecture/)** - 系统架构和设计
  - [MaskPayloadStage 架构](current/architecture/mask_payload_stage.md) - 核心掩码处理阶段

- **[用户指南](current/user/)** - 使用说明和教程
  - [适配器使用指南](current/user/adapters_usage_guide.md) - 适配器模块使用方法

- **[开发文档](current/development/)** - 开发者参考
  - [重构文档](current/development/refactoring/) - 最新的重构记录

- **[API 参考](current/api/)** - API 接口文档（待完善）

### 📦 archive/ - 历史文档存档
包含历史版本、废弃功能和过时设计的文档，仅供参考。

- **[design/](archive/design/)** - 历史设计文档
- **[plans/](archive/plans/)** - 历史计划文档
- **[deprecated/](archive/deprecated/)** - 废弃功能文档

### 📋 其他重要文档

- **[文档状态清单](DOCUMENT_STATUS.md)** - 所有文档的状态跟踪
- **[TLS 工具文档](TLS23_*.md)** - TLS 相关工具的使用说明
- **[管道执行指南](UNIFIED_PIPELINE_EXECUTION_GUIDE.md)** - 管道系统使用指南

## 🔍 快速查找

### 对于用户
1. 如何使用适配器？→ [适配器使用指南](current/user/adapters_usage_guide.md)
2. 如何使用 TLS 工具？→ [TLS23 标记工具](TLS23_MARKER_USAGE.md)
3. 如何运行管道？→ [管道执行指南](UNIFIED_PIPELINE_EXECUTION_GUIDE.md)

### 对于开发者
1. 系统架构是怎样的？→ [架构文档](current/architecture/)
2. 最近的更改是什么？→ [重构记录](current/development/refactoring/)
3. 如何贡献代码？→ [开发指南](development/)

## 📝 文档维护

### 报告问题
如果您发现文档有误或过时，请：
1. 查看[文档状态清单](DOCUMENT_STATUS.md)确认是否已知
2. 提交 Issue 或 Pull Request

### 贡献文档
1. 新文档添加到 `current/` 相应目录
2. 更新[文档状态清单](DOCUMENT_STATUS.md)
3. 遵循现有的文档格式和命名规范

## 🏷️ 文档版本

- **当前版本**: v3.1
- **最后更新**: 2025年1月9日
- **维护团队**: PktMask 开发团队

---

> 💡 **提示**: 使用 `Ctrl+F` 或 `Cmd+F` 在页面中搜索关键词快速定位所需内容。
