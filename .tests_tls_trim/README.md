# TLS Trim 端到端自动化测试框架

## 1. 概述

本测试框架旨在自动化地验证 `PktMask` 项目核心的TLS载荷裁切功能。

它通过以下方式工作：
1.  **分析原始样本**：使用 `tshark` 精确统计原始 PCAP 文件中 TLS Application Data 的数量。
2.  **执行裁切**：调用项目核心的 `MultiStageExecutor` 对样本文件进行批量裁切处理。
3.  **验证结果**：再次使用 `tshark` 统计裁切后的文件，并结合 `scapy` 进行逐字节的精确验证，确保裁切操作符合预期（即保留5字节头部，其余置零）。
4.  **生成报告**：产出一份清晰的 Markdown 格式的总结报告，直观展示每个样本文件的测试通过情况。

这套框架是保证代码质量、进行回归测试以及定位核心功能BUG的关键工具。

## 2. 目录结构

```
PktMask/
├── src/                          # 项目源代码
├── tests/
│   └── data/
│       └── tls/                  # <-- [输入] 原始PCAP样本文件存放于此
└── .tests_tls_trim/
    ├── README.md                 # <-- [本文档] 测试框架使用说明
    ├── baseline_collector.py     # 脚本: 步骤1 - 收集基线统计
    ├── run_trim_batch.py         # 脚本: 步骤2 - 执行批量裁切
    ├── verification.py           # 脚本: 步骤3 - 验证并生成报告
    └── output/                   # <-- [输出] 所有测试结果均存放于此
        ├── baseline_stats.json   # 机器可读的基线统计结果
        ├── trim_results.json     # 机器可读的裁切执行结果
        ├── verification.json     # 机器可读的最终验证结果
        ├── verification_report.md  # <-- [最终报告] 人类可读的Markdown报告
        └── *.pcap                # 裁切后生成的PCAP文件
```

## 3. 执行测试

### 先决条件
- 系统中必须安装 `Wireshark`，以确保 `tshark` 命令可用。
- 脚本会自动在系统的 `PATH` 和一些常见位置 (`/Applications/Wireshark.app/Contents/MacOS/`) 查找 `tshark`。

### 一键完整测试 (推荐)
在项目根目录下，执行以下链式命令即可完成一次完整的端到端测试：

```bash
python .tests_tls_trim/baseline_collector.py && python .tests_tls_trim/run_trim_batch.py && python .tests_tls_trim/verification.py
```

### 分步执行 (用于调试)
当需要调试特定阶段时，可以按顺序单独运行每个脚本：

1.  **步骤 1: 收集基线**
    ```bash
    python .tests_tls_trim/baseline_collector.py
    ```
    - 此脚本会扫描 `tests/data/tls/` 目录，并生成 `.tests_tls_trim/output/baseline_stats.json` 文件。

2.  **步骤 2: 执行裁切**
    ```bash
    python .tests_tls_trim/run_trim_batch.py
    ```
    - 此脚本会处理所有样本，并将裁切后的文件和 `trim_results.json` 输出到 `.tests_tls_trim/output/` 目录。

3.  **步骤 3: 验证并生成报告**
    ```bash
    python .tests_tls_trim/verification.py
    ```
    - 此脚本会汇总前两步的结果，进行最终验证，并生成 `verification_report.md` 和 `verification.json`。

## 4. 解读结果

测试完成后，最重要的产出是位于以下路径的 **Markdown 报告**:

`./.tests_tls_trim/output/verification_report.md`

打开此文件，您会看到一个总结表格：

- **✅ 通过**: 表示对于该文件，裁切前后的记录数/包数完全一致，并且 Scapy 的逐字节验证也确认了裁切的精确性。这表明核心裁切逻辑对该类文件处理正确。
- **❌ 失败**: 表示验证过程中出现了不一致。这通常指向了核心裁切逻辑中存在的一个BUG。请查看运行 `verification.py` 时的终端日志，其中会包含具体的失败原因（例如"数据未被置零"、"TCP载荷未找到"等），以帮助定位问题。
