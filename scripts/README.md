# Scripts Directory Description

This directory contains script tools related to project development, testing, and maintenance. These scripts are primarily for developers, not end users.

## Directory Structure

### `adhoc/`
Temporary scripts and one-time tools, including:
- Backup version tools
- Quick verification scripts
- Experimental code

### `build/`
Build and packaging related scripts:
- `build_app.sh` - Application build script

### `debug/`
Debugging and problem diagnosis tools:
- Component diagnostic scripts
- Troubleshooting tools

### `maintenance/`
System maintenance and audit scripts:
- `audit_dependencies.py` - Dependency audit tool

### `migration/`
Version migration and data migration scripts:
- Adapter migration tools
- Import path update tools
- Architecture migration assistance scripts

### `test/`
Testing assistance scripts:
- `adapter_baseline.py` - Adapter baseline testing
- `adapter_performance_test.py` - Performance testing
- `verify_adapter_migration.py` - Migration verification
- `verify_single_entrypoint.py` - Entry point verification

### `validation/`
Data validation and analysis scripts:
- TLS packet analysis tools
- End-to-end verification scripts
- Masking result validation tools

## Usage Instructions

### Running Scripts
Most scripts can be run directly:
```bash
python scripts/maintenance/audit_dependencies.py
```

### Test Scripts
Run test-related scripts:
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
