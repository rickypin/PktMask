# GitHub PR 创建指导

## 快速创建 PR

1. **访问 GitHub 仓库**
   ```
   https://github.com/rickypin/PktMask
   ```

2. **创建 Pull Request**
   - 点击 "Pull requests" 标签
   - 点击 "New pull request" 按钮
   - 选择分支: `629-new-arch` → `main`

3. **填写 PR 信息**
   
   **标题**:
   ```
   🚀 Release v0.2.0: 架构重构与向后兼容性改进
   ```
   
   **描述**: 复制 `PR_TEMPLATE_v0.2.0.md` 的内容，或使用以下简化版本：

   ```markdown
   ## 📋 PR 概要
   
   **版本**: v0.2.0  
   **类型**: 🚀 Major Release  
   
   ## 🎯 主要变更
   
   ### 🏗️ 架构重构
   - 移除 BlindPacketMasker 中间层，直接使用 MaskingRecipe
   - 简化 MaskStage Basic 模式，减少 30-40% 代码量
   - 引入 ProcessorStageAdapter 统一处理器接口
   - 重构 Pipeline 执行器，提升模块化程度
   
   ### 🔄 向后兼容性改进
   - 废弃 recipe_dict 和 recipe_path 配置项（保持兼容，发出警告）
   - 引入 processor_adapter 智能模式作为推荐配置
   - 保持所有公共 API 签名不变
   - 新增完整的向后兼容性文档
   
   ### 🧪 测试与验证增强
   - 完善跨数据包 TLS 记录处理
   - 新增 E2E 端到端测试套件
   - 实施回归测试机制
   
   ### 📋 文档完善
   - 创建根级 CHANGELOG.md
   - 新增架构设计决策文档
   - 更新版本号到 v0.2.0
   
   ## ⚠️ 破坏性变更
   
   以下配置项已废弃，将在 v1.0.0 版本中移除：
   - `recipe_dict` → 使用 `processor_adapter` 模式
   - `recipe_path` → 使用 `processor_adapter` 模式
   
   ## 📚 相关文档
   
   - [CHANGELOG.md](CHANGELOG.md)
   - [向后兼容性说明](docs/development/BACKWARD_COMPATIBILITY.md)
   - [设计决策文档](docs/development/MASK_STAGE_SIMPLIFICATION.md)
   
   ## 🔍 审查要点
   
   - [ ] 架构变更的合理性和完整性
   - [ ] 向后兼容性机制的有效性
   - [ ] 文档和迁移指南的清晰度
   - [ ] 测试覆盖的充分性
   
   **审查完成后，请合并到 main 分支并创建 v0.2.0 release。**
   ```

4. **添加审查者**
   - 添加项目维护者作为审查者
   - 设置适当的标签（如 `enhancement`, `major release`, `breaking change`）

5. **创建 PR**
   - 点击 "Create pull request"

## 后续步骤

PR 创建后：
1. 等待代码审查
2. 根据反馈进行必要的修改
3. 审查通过后合并到 main 分支
4. 创建 v0.2.0 release tag
5. 发布 release notes

## 重要文件

本次提交包含的重要文件：
- `CHANGELOG.md` - 根级变更日志
- `pyproject.toml` - 版本号更新到 v0.2.0
- `docs/development/BACKWARD_COMPATIBILITY.md` - 向后兼容性文档
- `docs/development/MASK_STAGE_SIMPLIFICATION.md` - 架构设计决策
- `PR_TEMPLATE_v0.2.0.md` - 详细的 PR 模板
