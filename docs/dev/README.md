# 开发者文档

欢迎参与 PktMask 项目开发！本目录包含开发者和贡献者所需的技术文档。

## 📖 文档列表

### 🚀 开始开发
- **[贡献指南](contributing.md)** - 如何参与项目开发
- **[开发环境设置](development-setup.md)** - 开发环境配置和工具安装
- **[编码规范](coding-standards.md)** - 代码风格、命名规范和最佳实践

### 🧪 测试和质量
- **[测试指南](testing-guide.md)** - 单元测试、集成测试和测试策略

## 🎯 开发流程

### 新贡献者推荐路径
1. **了解项目** → [系统概览](../architecture/system-overview.md)
2. **设置环境** → [开发环境设置](development-setup.md)
3. **学习规范** → [编码规范](coding-standards.md)
4. **开始贡献** → [贡献指南](contributing.md)

### 开发工作流
1. **Fork 项目** 并创建功能分支
2. **遵循编码规范** 进行开发
3. **编写测试** 确保代码质量
4. **提交 Pull Request** 进行代码审查

## 🏗️ 架构理解

### 核心概念
- **[系统概览](../architecture/system-overview.md)** - 整体架构和设计理念
- **[管道架构](../architecture/pipeline-architecture.md)** - 处理管道的设计模式
- **[GUI 架构](../architecture/gui-architecture.md)** - 图形界面架构

### API 参考
- **[核心 API](../api/core-api.md)** - 核心功能接口
- **[管道 API](../api/pipeline-api.md)** - 处理管道接口
- **[工具 API](../api/tools-api.md)** - 工具和实用程序接口

## 🔧 开发工具

### 推荐工具
- **IDE**: PyCharm, VSCode
- **版本控制**: Git
- **测试**: pytest
- **代码质量**: black, flake8, mypy

### 项目结构
```
src/pktmask/
├── core/           # 核心功能模块
├── gui/            # 图形界面
├── adapters/       # 适配器模块
└── utils/          # 工具和实用程序
```

## 📝 贡献类型

### 代码贡献
- 新功能开发
- Bug 修复
- 性能优化
- 代码重构

### 文档贡献
- 用户文档改进
- API 文档完善
- 示例代码添加
- 翻译工作

### 测试贡献
- 单元测试编写
- 集成测试改进
- 性能测试添加
- 测试覆盖率提升

## 🔗 相关资源

- **[架构文档](../architecture/)** - 深入了解系统设计
- **[API 文档](../api/)** - 编程接口详细说明
- **[工具文档](../tools/)** - 开发和调试工具
- **[历史存档](../archive/)** - 项目历史和设计决策

## 📞 联系方式

- **GitHub Issues** - 报告 Bug 和功能请求
- **Pull Requests** - 代码贡献和改进
- **Discussions** - 技术讨论和问题咨询

---

> 💡 **提示**: 开始贡献前，建议先阅读 [贡献指南](contributing.md) 了解项目的开发流程和规范。
