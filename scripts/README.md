# Scripts 目录说明

本目录包含项目开发、测试、维护相关的脚本工具。这些脚本主要供开发者使用，而非最终用户。

## 目录结构

### `adhoc/`
临时脚本和一次性工具，包括：
- 备份版本的工具
- 快速验证脚本
- 实验性代码

### `build/`
构建和打包相关脚本：
- `build_app.sh` - 应用构建脚本

### `debug/`
调试和问题诊断工具：
- 组件诊断脚本
- 问题排查工具

### `maintenance/`
系统维护和审计脚本：
- `audit_dependencies.py` - 依赖审计工具

### `migration/`
版本迁移和数据迁移脚本：
- 适配器迁移工具
- 导入路径更新工具
- 架构迁移辅助脚本

### `test/`
测试辅助脚本：
- `adapter_baseline.py` - 适配器基线测试
- `adapter_performance_test.py` - 性能测试
- `verify_adapter_migration.py` - 迁移验证
- `verify_single_entrypoint.py` - 入口点验证

### `validation/`
数据验证和分析脚本：
- TLS 数据包分析工具
- 端到端验证脚本
- 掩码结果验证工具

## 使用说明

### 运行脚本
大部分脚本可以直接运行：
```bash
python scripts/maintenance/audit_dependencies.py
```

### 测试脚本
运行测试相关脚本：
```bash
python scripts/test/adapter_baseline.py
```

### 验证脚本
执行验证任务：
```bash
python scripts/validation/tls23_e2e_validator.py --input samples/tls --output output/validation
```

## 注意事项

1. 这些脚本主要用于开发和维护，不是生产工具
2. 生产级工具请查看 `src/pktmask/tools/` 目录
3. 临时脚本应放在 `adhoc/` 目录，并定期清理
4. 新增脚本请遵循现有的命名规范和目录结构

## 相关链接

- 生产工具: `src/pktmask/tools/`
- 项目文档: `docs/`
- 测试用例: `tests/`
