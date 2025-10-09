# PktMask 端到端测试 (E2E Tests)

> **目标**: 确保重构、更新后功能一致性  
> **方法**: 黄金文件测试法 (Golden File Testing)

---

## 📖 快速开始

### 🚀 方式一：使用便捷脚本（推荐）

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行所有测试并生成HTML报告（自动在浏览器中打开）
./tests/e2e/run_e2e_tests.sh --all --open

# 只运行核心功能测试
./tests/e2e/run_e2e_tests.sh --core --open

# 只运行协议覆盖测试
./tests/e2e/run_e2e_tests.sh --protocol --open

# 只运行封装类型测试
./tests/e2e/run_e2e_tests.sh --encap --open

# 并行运行测试（需要pytest-xdist）
./tests/e2e/run_e2e_tests.sh --all --parallel --open

# 查看帮助
./tests/e2e/run_e2e_tests.sh --help
```

### 🔧 方式二：使用pytest命令

#### 前置条件

```bash
# 1. 确保测试数据存在
ls tests/data/tls/
ls tests/samples/http-collector/

# 2. 安装测试依赖
pip install pytest pytest-html pytest-xdist pytest-timeout

# 3. 激活Python虚拟环境(如果使用)
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

#### 1. 生成黄金基准（仅一次）

```bash
# 在当前稳定版本运行
cd /path/to/PktMask
python tests/e2e/generate_golden_baseline.py

# 预期输出:
# 🚀 Starting Golden Baseline Generation
# 📁 Golden directory: .../tests/e2e/golden
# 📊 Total test cases: 16
#
# Processing E2E-001: Dedup Only...
#   ✅ Generated baseline
#      Output hash: ...
#      Packets: 150
# ...
# ============================================================
# ✅ Success: 16/16
# ============================================================
```

#### 2. 运行端到端测试

```bash
# 运行所有测试
pytest tests/e2e/test_e2e_golden_validation.py -v

# 并行运行（更快）
pytest tests/e2e/test_e2e_golden_validation.py -n auto

# 运行特定测试组
pytest tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency -v
```

#### 3. 生成HTML测试报告

```bash
# 生成增强的HTML报告
pytest tests/e2e/test_e2e_golden_validation.py -v \
  --html=tests/e2e/report.html \
  --self-contained-html

# 生成报告并自动在浏览器中打开
pytest tests/e2e/test_e2e_golden_validation.py -v \
  --html=tests/e2e/report.html \
  --self-contained-html && open tests/e2e/report.html

# 生成报告 + JUnit XML（用于CI/CD）
pytest tests/e2e/test_e2e_golden_validation.py -v \
  --html=tests/e2e/report.html \
  --self-contained-html \
  --junitxml=tests/e2e/junit.xml
```

#### HTML报告功能特性

报告包含以下信息：

**📊 测试概览**
- 总测试数、通过率、失败率、跳过率
- 总执行时间和平均执行时间
- 测试环境信息（Python版本、平台、依赖版本）

**📈 分类统计**
- 核心功能测试 (E2E-001 ~ E2E-007)
- 协议覆盖测试 (E2E-101 ~ E2E-106)
- 封装类型测试 (E2E-201 ~ E2E-203)
- 每个类别的通过/失败统计

**📝 详细测试结果**
- 测试ID和名称
- 测试类别
- 执行时间
- 测试状态（通过/失败/跳过）
- 失败原因和错误堆栈

**🔍 基线验证详情** ✨新增
- 每个测试的基线比对表格
  - 输出文件哈希(SHA256)
  - 数据包数量
  - 文件大小
  - 处理统计(packets processed/modified)
  - 执行时间(带容差)
  - 阶段数量和详细统计
- 验证检查列表
  - 每个验证步骤的详细说明
  - 通过/失败状态标记
  - 基线值vs当前值对比

**📁 输出文件**
- HTML报告: `tests/e2e/report.html`
- JSON结果: `tests/e2e/test_results.json`
- JUnit XML: `tests/e2e/junit.xml` (可选)

> 💡 **提示**: 查看 [REPORT_GUIDE.md](REPORT_GUIDE.md) 了解如何使用HTML报告

#### 4. 高级测试选项

```bash
# 并行运行测试（需要pytest-xdist）
pytest tests/e2e/test_e2e_golden_validation.py -v -n auto \
  --html=tests/e2e/report.html --self-contained-html

# 只运行失败的测试
pytest tests/e2e/test_e2e_golden_validation.py -v --lf \
  --html=tests/e2e/report.html --self-contained-html

# 运行特定类别的测试
pytest tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency -v \
  --html=tests/e2e/report_core.html --self-contained-html

# 显示详细输出
pytest tests/e2e/test_e2e_golden_validation.py -vv \
  --html=tests/e2e/report.html --self-contained-html

# 查看控制台详细输出
pytest tests/e2e/test_e2e_golden_validation.py -v --tb=long
```

---

## 📁 目录结构

```
tests/e2e/
├── README.md                         # 本文件
├── generate_golden_baseline.py      # 黄金基准生成器
├── test_e2e_golden_validation.py    # 端到端验证测试
└── golden/                           # 黄金基准数据（Git管理）
    ├── E2E-001_baseline.json         # 测试基准元数据
    ├── E2E-001_output.pcap           # 黄金输出文件
    ├── E2E-002_baseline.json
    ├── E2E-002_output.pcap
    └── ...
```

---

## 🎯 测试覆盖

### 核心功能组合 (7个测试)

- E2E-001: Dedup Only
- E2E-002: Anonymize Only
- E2E-003: Mask Only
- E2E-004: Dedup + Anonymize
- E2E-005: Dedup + Mask
- E2E-006: Anonymize + Mask
- E2E-007: All Features

### 协议覆盖 (6个测试)

- E2E-101: TLS 1.0 Multi-Segment
- E2E-102: TLS 1.2 Standard
- E2E-103: TLS 1.3 with 0-RTT
- E2E-104: SSL 3.0
- E2E-105: HTTP Download
- E2E-106: HTTP 500 Error

### 封装类型 (3个测试)

- E2E-201: Plain IP
- E2E-202: Single VLAN
- E2E-203: Double VLAN

**总计**: 16个端到端测试

---

## ✅ 验证标准

### 完全一致性

- ✅ 输出文件 SHA256 哈希完全匹配
- ✅ 数据包数量精确匹配
- ✅ 文件大小字节级匹配

### 统计信息

- ✅ 处理数据包数精确匹配
- ✅ 修改数据包数精确匹配
- ✅ 处理时间允许 ±10% 误差

---

## 🔄 工作流程

### 重构前

```bash
# 1. 确保当前版本功能正确
pytest tests/integration/ -v

# 2. 生成黄金基准
python tests/e2e/generate_golden_baseline.py

# 3. 提交黄金基准
git add tests/e2e/golden/
git commit -m "Add E2E golden baselines"
```

### 重构中

```bash
# 进行代码重构、优化、更新
# ...
```

### 重构后

```bash
# 1. 运行端到端测试
pytest tests/e2e/test_e2e_golden_validation.py -v

# 2. 如果全部通过 ✅
#    重构成功，功能一致性得到保证

# 3. 如果有失败 ❌
#    分析差异，确认是否为预期变化
#    - 如果是Bug: 修复代码
#    - 如果是预期变化: 重新生成基准
```

---

## 📊 示例输出

### 成功

```
tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-001] PASSED
tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-002] PASSED
...
======================== 16 passed in 45.23s ========================
```

### 失败

```
FAILED tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-003]
AssertionError: Output hash mismatch for E2E-003
Expected: a1b2c3d4e5f6g7h8...
Got:      x9y8z7w6v5u4t3s2...
```

---

## 🛠️ 故障排查

### 问题: 测试数据不存在

```bash
# 检查测试数据
ls tests/data/tls/
ls tests/samples/http-collector/

# 如果缺失，从备份恢复或重新获取
```

### 问题: 哈希不匹配

```bash
# 1. 检查是否为预期变化
git diff tests/e2e/golden/E2E-XXX_baseline.json

# 2. 如果是预期变化，重新生成基准
python tests/e2e/generate_golden_baseline.py

# 3. 如果不是预期变化，修复代码
```

### 问题: 测试超时

```bash
# 增加超时时间
pytest tests/e2e/test_e2e_golden_validation.py --timeout=300
```

---

## 📚 相关文档

- [E2E_TEST_PLAN.md](../../docs/dev/E2E_TEST_PLAN.md) - 完整测试方案
- [E2E_TEST_IMPLEMENTATION_GUIDE.md](../../docs/dev/E2E_TEST_IMPLEMENTATION_GUIDE.md) - 实施指南

---

## ⚠️ 重要提示

1. **黄金基准是版本控制的一部分**
   - 所有 `golden/` 目录下的文件都应该提交到 Git
   - 团队成员使用相同的基准

2. **只在稳定版本生成基准**
   - 确保功能正确后再生成
   - 不要在有已知Bug的版本生成

3. **定期审查测试覆盖**
   - 每月审查测试用例
   - 根据新功能添加测试

4. **CI/CD 集成**
   - 在持续集成中运行核心测试
   - 本地运行完整测试

---

**维护人**: 开发团队  
**最后更新**: 2025-10-09

