# PktMask Unified Feature Deployment Checklist

## Overview

This checklist ensures proper deployment and verification of PktMask GUI and CLI unified feature improvements.

## Pre-Deployment Checks

### 1. Code Integrity Check

- [ ] **Service Layer Files**
  - [ ] `src/pktmask/services/config_service.py` - Configuration service
  - [ ] `src/pktmask/services/output_service.py` - Output service
  - [ ] `src/pktmask/services/progress_service.py` - Progress service
  - [ ] `src/pktmask/services/report_service.py` - Report service
  - [ ] `src/pktmask/services/pipeline_service.py` - Pipeline service (updated)

- [ ] **CLI Updates**
  - [ ] `src/pktmask/cli.py` - CLI command updates
  - [ ] Added directory processing support
  - [ ] Added report generation functionality
  - [ ] Added batch processing commands

- [ ] **Test Files**
  - [ ] `tests/integration/test_cli_unified.py` - Integration tests
  - [ ] `tests/unit/services/test_unified_services.py` - Unit tests

- [ ] **文档文件**
  - [ ] `docs/CLI_UNIFIED_GUIDE.md` - CLI 使用指南
  - [ ] `docs/ARCHITECTURE_UNIFIED.md` - 架构文档
  - [ ] `docs/DEPLOYMENT_CHECKLIST.md` - 本检查清单

- [ ] **脚本文件**
  - [ ] `scripts/test_unified_functionality.py` - 功能测试脚本

### 2. 依赖检查

- [ ] **Python 版本**
  - [ ] Python 3.8+ 支持
  - [ ] 虚拟环境配置正确

- [ ] **核心依赖**
  - [ ] `typer` - CLI 框架
  - [ ] `pathlib` - 路径处理
  - [ ] 现有 PktMask 依赖完整

- [ ] **可选依赖**
  - [ ] 测试依赖 (`pytest`, `pytest-mock`)
  - [ ] 开发依赖完整

### 3. 配置检查

- [ ] **应用配置**
  - [ ] TShark 路径配置正确
  - [ ] 默认配置合理
  - [ ] 配置文件格式正确

- [ ] **环境变量**
  - [ ] 必要的环境变量设置
  - [ ] 路径变量正确

## Functional Verification

### 1. Basic Functionality Testing

- [ ] **CLI Command Availability**
  ```bash
  python -m pktmask --help
  python -m pktmask mask --help
  python -m pktmask batch --help
  python -m pktmask info --help
  ```

- [ ] **GUI Startup Normal**
  ```bash
  python -m pktmask  # Should launch GUI
  ```

- [ ] **Configuration Service Normal**
  ```python
  from pktmask.services.config_service import get_config_service
  service = get_config_service()
  # Should not raise exceptions
  ```

### 2. Functional Consistency Testing

- [ ] **Configuration Consistency**
  - [ ] GUI and CLI generate identical configurations
  - [ ] All processing options are available
  - [ ] Parameter validation is correct

- [ ] **Processing Result Consistency**
  - [ ] Same input produces same output
  - [ ] Error handling is consistent
  - [ ] Performance is similar

- [ ] **Output Format Consistency**
  - [ ] Statistics format is consistent
  - [ ] Error message format is consistent
  - [ ] Report content is consistent

### 3. New Feature Verification

- [ ] **Directory Batch Processing**
  ```bash
  # Create test directory and files
  mkdir test_pcaps
  # Add test files
  python -m pktmask batch test_pcaps -o output_dir --verbose
  ```

- [ ] **Report Generation**
  ```bash
  python -m pktmask mask test.pcap -o output.pcap --save-report --report-detailed
  ```

- [ ] **多种输出格式**
  ```bash
  python -m pktmask info test_dir --format json
  python -m pktmask mask test.pcap -o output.pcap --format json
  ```

- [ ] **进度显示**
  ```bash
  python -m pktmask batch test_pcaps -o output_dir --verbose
  python -m pktmask batch test_pcaps -o output_dir --no-progress
  ```

## 性能验证

### 1. 内存使用

- [ ] **单文件处理**
  - [ ] 内存使用合理
  - [ ] 无内存泄漏
  - [ ] 大文件处理稳定

- [ ] **批量处理**
  - [ ] 批量处理内存稳定
  - [ ] 多文件处理无累积内存增长
  - [ ] 错误恢复正常

### 2. 处理速度

- [ ] **基准测试**
  - [ ] CLI 处理速度与 GUI 相当
  - [ ] 批量处理效率合理
  - [ ] 进度显示不影响性能

- [ ] **大规模测试**
  - [ ] 100+ 文件批量处理正常
  - [ ] 大文件（>100MB）处理正常
  - [ ] 长时间运行稳定

## 兼容性验证

### 1. 向后兼容性

- [ ] **现有 CLI 命令**
  ```bash
  python -m pktmask mask input.pcap -o output.pcap --dedup --anon
  python -m pktmask dedup input.pcap -o output.pcap
  python -m pktmask anon input.pcap -o output.pcap
  ```

- [ ] **现有 GUI 功能**
  - [ ] 所有 GUI 功能正常
  - [ ] 配置保存/加载正常
  - [ ] 处理结果一致

### 2. 平台兼容性

- [ ] **Windows**
  - [ ] CLI 命令正常
  - [ ] 路径处理正确
  - [ ] 文件权限正常

- [ ] **macOS**
  - [ ] CLI 命令正常
  - [ ] 路径处理正确
  - [ ] 权限处理正常

- [ ] **Linux**
  - [ ] CLI 命令正常
  - [ ] 路径处理正确
  - [ ] 权限处理正常

## 错误处理验证

### 1. 输入验证

- [ ] **无效文件**
  ```bash
  python -m pktmask mask nonexistent.pcap -o output.pcap
  # 应返回错误码和清晰错误信息
  ```

- [ ] **权限问题**
  ```bash
  python -m pktmask mask readonly.pcap -o /readonly/output.pcap
  # 应正确处理权限错误
  ```

- [ ] **无效参数**
  ```bash
  python -m pktmask mask input.pcap -o output.pcap --mode invalid
  # 应提供有用的错误信息
  ```

### 2. 异常恢复

- [ ] **处理中断**
  - [ ] Ctrl+C 正确处理
  - [ ] 临时文件清理
  - [ ] 状态恢复正常

- [ ] **资源不足**
  - [ ] 内存不足时的优雅降级
  - [ ] 磁盘空间不足的处理
  - [ ] 网络问题的处理（如适用）

## 自动化测试

### 1. 运行测试套件

- [ ] **单元测试**
  ```bash
  python -m pytest tests/unit/services/test_unified_services.py -v
  ```

- [ ] **集成测试**
  ```bash
  python -m pytest tests/integration/test_cli_unified.py -v
  ```

- [ ] **功能测试**
  ```bash
  python scripts/test_unified_functionality.py
  ```

### 2. 测试覆盖率

- [ ] **代码覆盖率**
  ```bash
  python -m pytest --cov=pktmask.services tests/ --cov-report=html
  ```

- [ ] **功能覆盖率**
  - [ ] 所有新功能都有测试
  - [ ] 所有错误路径都有测试
  - [ ] 边界条件都有测试

## 文档验证

### 1. 用户文档

- [ ] **CLI 指南**
  - [ ] 所有示例都可运行
  - [ ] 参数说明准确
  - [ ] 使用场景清晰

- [ ] **架构文档**
  - [ ] 架构图准确
  - [ ] 组件说明完整
  - [ ] 接口文档正确

### 2. 开发文档

- [ ] **API 文档**
  - [ ] 服务接口文档完整
  - [ ] 参数类型正确
  - [ ] 返回值说明清晰

- [ ] **部署文档**
  - [ ] 安装步骤正确
  - [ ] 配置说明完整
  - [ ] 故障排除有用

## 部署后验证

### 1. 生产环境测试

- [ ] **基本功能**
  - [ ] CLI 和 GUI 都能正常启动
  - [ ] 基本处理功能正常
  - [ ] 配置加载正确

- [ ] **性能监控**
  - [ ] 内存使用正常
  - [ ] CPU 使用合理
  - [ ] 处理速度符合预期

### 2. 用户反馈

- [ ] **易用性**
  - [ ] CLI 命令直观
  - [ ] 错误信息有用
  - [ ] 帮助信息完整

- [ ] **功能完整性**
  - [ ] 所有承诺功能都可用
  - [ ] 性能符合预期
  - [ ] 稳定性良好

## 发布准备

### 1. 版本管理

- [ ] **版本号更新**
  - [ ] 主版本号反映重大改进
  - [ ] 变更日志完整
  - [ ] 标签创建正确

- [ ] **发布说明**
  - [ ] 新功能说明
  - [ ] 改进点列表
  - [ ] 兼容性说明
  - [ ] 迁移指南

### 2. 分发准备

- [ ] **打包**
  - [ ] 所有文件包含在分发包中
  - [ ] 依赖声明正确
  - [ ] 安装脚本正常

- [ ] **文档**
  - [ ] README 更新
  - [ ] 安装指南更新
  - [ ] 快速开始指南更新

## 签署确认

- [ ] **开发团队确认**
  - 开发负责人：_________________ 日期：_________
  - 测试负责人：_________________ 日期：_________

- [ ] **质量保证确认**
  - QA 负责人：__________________ 日期：_________

- [ ] **产品负责人确认**
  - 产品负责人：_________________ 日期：_________

---

**注意**：所有检查项目都必须完成并确认通过后，才能进行正式部署。如有任何项目未通过，需要修复后重新验证。
