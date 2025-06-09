# PktMask 自动化测试指南

本文档描述了 PktMask 项目的自动化测试系统，包括如何使用单一命令运行完整的测试套件并生成汇总报告。

## 📋 目录

- [快速开始](#快速开始)
- [测试命令](#测试命令)
- [测试类型](#测试类型)
- [报告输出](#报告输出)
- [CI/CD集成](#cicd集成)
- [配置自定义](#配置自定义)
- [故障排除](#故障排除)

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 建议使用虚拟环境
- 至少 1GB 内存
- 500MB 磁盘空间

### 安装依赖

```bash
# 安装开发依赖
pip install -e ".[dev]"
```

### 运行所有测试

```bash
# 使用 Python 脚本 (推荐)
python test_suite.py

# 使用 Shell 脚本 (Linux/macOS)
./run_tests.sh

# 使用批处理脚本 (Windows)
run_tests.bat
```

## 🛠️ 测试命令

### Python 脚本命令

```bash
# 基本用法
python test_suite.py                 # 运行所有测试
python test_suite.py --quick         # 快速测试(跳过性能测试)
python test_suite.py --unit          # 仅单元测试
python test_suite.py --integration   # 仅集成测试
python test_suite.py --performance   # 仅性能测试
python test_suite.py --output reports # 指定输出目录
```

### Shell 脚本命令 (Linux/macOS)

```bash
# 基本用法
./run_tests.sh                       # 运行所有测试
./run_tests.sh --quick               # 快速测试
./run_tests.sh --unit                # 仅单元测试
./run_tests.sh --integration         # 仅集成测试
./run_tests.sh --performance         # 仅性能测试
./run_tests.sh --clean               # 清理报告目录
./run_tests.sh --output reports      # 指定输出目录
./run_tests.sh --no-deps             # 跳过依赖检查
./run_tests.sh --help                # 显示帮助
```

### 批处理脚本命令 (Windows)

```cmd
rem 基本用法
run_tests.bat                        :: 运行所有测试
run_tests.bat /quick                 :: 快速测试
run_tests.bat /unit                  :: 仅单元测试
run_tests.bat /integration           :: 仅集成测试
run_tests.bat /performance           :: 仅性能测试
run_tests.bat /clean                 :: 清理报告目录
run_tests.bat /output reports        :: 指定输出目录
run_tests.bat /help                  :: 显示帮助
```

## 🧪 测试类型

### 1. 单元测试 (Unit Tests)

**目的**: 验证各个组件的独立功能

**包含文件**:
- `tests/test_basic_phase_7.py` - Phase 7基础功能测试
- `tests/test_config_system.py` - 配置系统测试
- `tests/test_algorithm_plugins.py` - 算法插件测试
- `tests/test_managers.py` - GUI管理器测试
- `tests/test_pktmask.py` - 核心应用测试
- `tests/test_gui.py` - GUI组件测试
- `tests/test_core_ip_processor_unit.py` - IP处理器单元测试

**运行时间**: 通常 5-10 分钟

### 2. 集成测试 (Integration Tests)

**目的**: 验证组件间协作功能

**包含文件**:
- `tests/test_integration_phase_7.py` - Phase 7集成测试
- `test_phase_6_4_basic.py` - Phase 6.4基础集成测试
- `test_plugin_system.py` - 插件系统集成测试
- `test_enhanced_plugin_system.py` - 增强插件系统测试

**运行时间**: 通常 10-15 分钟

### 3. 性能测试 (Performance Tests)

**目的**: 验证系统性能和优化效果

**包含文件**:
- `tests/performance/test_runner.py` - 性能测试运行器
- `tests/performance/benchmark_suite.py` - 基准测试套件
- `tests/performance/run_optimization_test.py` - 优化测试

**性能基准**:
- IP匿名化: ≥1000 packets/sec
- 去重处理: ≥500 packets/sec  
- 数据包处理: ≥2000 packets/sec

**运行时间**: 通常 15-25 分钟

### 4. 阶段特定测试 (Phase-Specific Tests)

**目的**: 验证各个重构阶段的特定功能

**包含文件**:
- `test_phase_6_2_optimized_plugins.py` - Phase 6.2优化插件测试
- `test_phase_6_2_enhanced_plugins.py` - Phase 6.2增强插件测试
- `test_phase_6_3_algorithm_configs.py` - Phase 6.3算法配置测试
- `test_phase_6_4_dynamic_loading.py` - Phase 6.4动态加载测试

**运行时间**: 通常 10-20 分钟

## 📊 报告输出

### 报告文件结构

```
test_reports/
├── test_summary_YYYYMMDD_HHMMSS.html     # 主要HTML报告
├── test_summary_YYYYMMDD_HHMMSS.json     # JSON格式报告
├── unit_results.xml                       # 单元测试JUnit报告
├── integration_results.xml               # 集成测试JUnit报告
├── coverage.json                          # 覆盖率JSON报告
├── htmlcov/                              # 覆盖率HTML报告
│   └── index.html                        # 覆盖率主页
└── test_suite.log                        # 测试日志文件
```

### HTML报告功能

✅ **总体状态** - 显示测试通过/失败状态  
📊 **测试统计** - 总数、通过、失败、错误、跳过  
⏱️ **执行时间** - 各测试套件的耗时统计  
📈 **覆盖率** - 代码覆盖率百分比和详细信息  
🔧 **环境信息** - Python版本、平台、系统信息  
📋 **详细结果** - 每个测试套件的详细执行结果  

### 自动报告打开

- **macOS**: HTML报告会在默认浏览器中自动打开
- **Windows**: 批处理脚本会自动启动HTML报告
- **Linux**: 需要手动打开HTML报告文件

## 🔄 CI/CD集成

### GitHub Actions

项目包含完整的 GitHub Actions 工作流 (`.github/workflows/test.yml`):

**触发条件**:
- 推送到 `main` 或 `develop` 分支
- 创建 Pull Request
- 手动触发
- 每日定时执行 (凌晨2点)

**测试矩阵**:
- 操作系统: Ubuntu, Windows, macOS
- Python版本: 3.8, 3.9, 3.10, 3.11

**工作流步骤**:
1. 代码质量检查 (Lint)
2. 跨平台测试
3. 代码覆盖率测试
4. 性能测试 (仅主分支)
5. 安全扫描
6. 发布就绪检查 (仅标签)
7. 报告汇总

### 本地CI模拟

```bash
# 模拟CI环境测试
QT_QPA_PLATFORM=offscreen python test_suite.py --quick

# 运行安全扫描
pip install bandit safety
bandit -r src/
safety check
```

## ⚙️ 配置自定义

### 测试配置文件

编辑 `test_config.yaml` 来自定义测试行为:

```yaml
# 启用/禁用测试套件
test_suites:
  unit:
    enabled: true
    timeout: 300
  
# 覆盖率要求
coverage:
  min_coverage: 80
  
# 性能基准
performance_benchmarks:
  ip_anonymization:
    min_throughput: 1000
```

### pytest配置

编辑 `pyproject.toml` 中的 pytest 配置:

```toml
[tool.pytest.ini_options]
addopts = "--cov=pktmask --cov-report=html --cov-fail-under=80"
testpaths = ["tests"]
```

## 🔧 故障排除

### 常见问题

**1. 依赖安装失败**

```bash
# 清理pip缓存
pip cache purge

# 重新安装依赖
pip install --force-reinstall -e ".[dev]"
```

**2. GUI测试在无头环境失败**

```bash
# 设置环境变量
export QT_QPA_PLATFORM=offscreen

# 或在Linux上安装xvfb
sudo apt-get install xvfb
xvfb-run python test_suite.py
```

**3. 权限问题 (Linux/macOS)**

```bash
# 给脚本执行权限
chmod +x run_tests.sh

# 检查Python权限
ls -la $(which python3)
```

**4. 内存不足**

```bash
# 运行快速测试
python test_suite.py --quick

# 仅运行单元测试
python test_suite.py --unit
```

**5. 网络问题**

```bash
# 跳过依赖检查
./run_tests.sh --no-deps

# 离线模式
pip install --no-index --find-links ./wheels -e ".[dev]"
```

### 调试模式

```bash
# 启用详细输出
python test_suite.py --output debug_reports -v

# 查看测试日志
tail -f test_reports/test_suite.log

# 单独运行失败的测试
python -m pytest tests/test_failing_module.py -v --tb=long
```

### 性能调优

```bash
# 跳过性能测试以节省时间
python test_suite.py --quick

# 并行执行 (实验性)
python -m pytest -n auto tests/

# 仅运行特定标记的测试
python -m pytest -m "not slow" tests/
```

## 📞 支持

如果遇到测试相关问题:

1. 检查 `test_reports/test_suite.log` 日志文件
2. 运行 `python test_suite.py --help` 查看所有选项
3. 使用 `./run_tests.sh --help` 查看shell脚本帮助
4. 参考 GitHub Actions 工作流作为最佳实践参考

## 📚 相关文档

- [项目重构档案](PKTMASK_REFACTORING_ARCHIVE.md)
- [Phase 7测试摘要](PHASE_7_TEST_SUMMARY.md)
- [打包指南](PACKAGING_GUIDE.md)
- [README](README.md)

---

**最后更新**: 2025年1月  
**测试框架版本**: v1.0.0  
**支持的Python版本**: 3.8 - 3.11 