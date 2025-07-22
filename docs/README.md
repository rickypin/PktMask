# PktMask 文档中心

欢迎来到 PktMask 项目文档中心！这里包含了使用和开发 PktMask 所需的所有文档资料。

## 📚 文档导航

### 👥 [用户文档](user/)
面向最终用户的使用指南和教程
- **[安装指南](user/installation-guide.md)** - 系统要求和安装步骤
- **[MaskStage 用户指南](user/maskstage-guide.md)** - 掩码处理功能使用说明

### 🛠️ [开发者文档](dev/)
面向开发者和贡献者的技术文档
- **[贡献指南](dev/contributing.md)** - 如何参与项目开发
- **[开发环境设置](dev/development-setup.md)** - 开发环境配置
- **[编码规范](dev/coding-standards.md)** - 代码风格和规范

### 📚 [API 文档](api/)
API 接口参考和使用说明
- **[核心 API](api/core-api.md)** - 核心功能 API
- **[管道 API](api/pipeline-api.md)** - 处理管道 API
- **[工具 API](api/tools-api.md)** - 工具和实用程序 API

### 🏛️ [架构文档](architecture/)
系统架构和设计文档
- **[系统概览](architecture/system-overview.md)** - 整体架构介绍
- **[管道架构](architecture/pipeline-architecture.md)** - 处理管道设计
- **[GUI 架构](architecture/gui-architecture.md)** - 图形界面架构

### 🔧 [工具文档](tools/)
专用工具的使用指南
- **[TLS 流量分析工具](tools/tls-flow-analyzer.md)** - TLS 协议分析
- **[TLS23 标记工具](tools/tls23-marker.md)** - TLS23 帧标记
- **[TLS23 验证工具](tools/tls23-validator.md)** - TLS23 端到端验证
- **[MaskStage 验证工具](tools/maskstage-validator.md)** - MaskStage 功能验证

### 📦 [历史存档](archive/)
历史文档和已完成项目的记录
- **[已完成项目](archive/completed-projects/)** - 历史项目文档
- **[废弃功能](archive/deprecated-features/)** - 不再支持的功能
- **[遗留文档](archive/legacy-docs/)** - 历史版本文档

## 🚀 快速开始

### 新用户
1. **安装 PktMask** → [安装指南](user/installation-guide.md)
2. **了解基本功能** → [MaskStage 用户指南](user/maskstage-guide.md)
3. **使用专用工具** → [工具文档](tools/)

### 开发者
1. **设置开发环境** → [开发环境设置](dev/development-setup.md)
2. **了解系统架构** → [系统概览](architecture/system-overview.md)
3. **查看 API 文档** → [API 文档](api/)
4. **参与贡献** → [贡献指南](dev/contributing.md)

### 高级用户
1. **深入了解架构** → [架构文档](architecture/)
2. **使用高级工具** → [工具文档](tools/)
3. **查看历史记录** → [历史存档](archive/)

## 📝 文档维护

### 文档状态
- **版本**: v4.0.0
- **最后更新**: 2025-07-22
- **维护状态**: ✅ 活跃维护

### 📋 文档管理体系
- **[文档结构使用说明](DOCS_DIRECTORY_STRUCTURE_GUIDE.md)** - 完整的文档管理规范和操作指导
- **[快速管理指南](QUICK_DOCS_MANAGEMENT_GUIDE.md)** - 日常文档操作的快速参考

### 🛠️ 文档管理工具
```bash
# 创建新文档
./scripts/docs/manage-docs.sh create user-guide new-feature

# 运行质量检查
./scripts/docs/manage-docs.sh check

# 生成统计报告
./scripts/docs/manage-docs.sh stats
```

### 贡献文档
1. 使用文档管理工具创建新文档
2. 遵循 [编码规范](dev/coding-standards.md) 中的文档规范
3. 运行质量检查确保规范性
4. 更新相关的 README.md 索引
5. 提交 Pull Request

### 报告问题
如果发现文档问题，请：
1. 检查是否为已知问题
2. 在 GitHub 提交 Issue
3. 或直接提交 Pull Request 修复

---

> 💡 **提示**: 每个目录都有详细的 README.md 索引，点击上方链接可快速导航到相关内容。
