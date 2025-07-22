# TLS23 E2E Validator 使用指南

> 版本：v1.1 · 适用工具：scripts/validation/tls23_e2e_validator.py · 作者：AI 设计助手

---

## 1. 前置条件

1. 已正确安装 **PktMask ≥ 3.0** 及其所有依赖（参考 `README.md`）。  
2. 环境中可执行 `python3`（遵循项目规则，所有命令均用 `python3` 调用）。  
3. `tshark` 与 `PyShark` 已配置完成（脚本依赖这两个工具进行 TLS23 帧扫描）。  
4. 已确保 `scripts/validation/tls23_e2e_validator.py` 可被 `PYTHONPATH` 找到，或当前目录位于项目根目录。

---

## 2. 脚本定位

```bash
PktMask/scripts/validation/tls23_e2e_validator.py
```

如需在任何位置调用，可使用以下两种方式之一：

1. **绝对路径**
   ```bash
   python3 /abs/path/to/PktMask/scripts/validation/tls23_e2e_validator.py [...options]
   ```
2. **模块路径（推荐）**
   在项目根执行：
   ```bash
   python3 -m scripts.validation.tls23_e2e_validator [...options]
   ```

---

## 3. CLI 语法

```bash
python3 scripts/validation/tls23_e2e_validator.py \
  --input-dir <pcap_dir> \
  --output-dir <output_dir> \
  --pktmask-mode trim \
  [--glob "**/*.pcap"] \
  [--verbose]
```

| 参数            | 必/选 | 默认值                     | 说明                                                    |
|-----------------|-------|---------------------------|---------------------------------------------------------|
| `--input-dir`   | 必填  | —                         | 递归扫描的 PCAP/PCAPNG 输入目录                         |
| `--output-dir`  | 可选  | `output/tls23_e2e`        | 结果与报告输出目录                                      |
| `--pktmask-mode`| 可选  | `trim`                    | 调用 PktMask 主体程序的处理模式（未来可扩展）           |
| `--glob`        | 可选  | `**/*.{pcap,pcapng}`      | 自定义文件匹配表达式（glob 语法）                       |
| `--verbose`     | 可选  | 关闭                      | 打印调试信息                                            |

### 退出码说明

| 退出码 | 含义                                                         |
|--------|-------------------------------------------------------------|
| 0      | 所有文件全部验证通过                                        |
| 1      | 至少 1 个文件验证失败                                       |
| 2      | 输入目录下未发现匹配文件                                    |
| 3      | 运行时异常（参数错误、外部工具不可用等）                    |

---

## 4. 使用示例

以下示例在 PktMask 项目根目录执行：

```bash
python3 -m scripts.validation.tls23_e2e_validator \
  --input-dir tests/data/tls \
  --output-dir output/tls23_e2e \
  --pktmask-mode trim \
  --verbose
```

脚本将在 `output/tls23_e2e/` 生成：

```
<file>_orig_tls23.json        # 掩码前 TLS23 扫描结果
<file>_masked_tls23.json      # 掩码后 TLS23 扫描结果
masked_pcaps/                 # 统一存放所有 *_masked.pcap(ng) 文件
validation_summary.json       # 机器可读的汇总报告（JSON）
validation_summary.html       # 人类可读的可视化 HTML 报告
```

控制台示例输出：

```
🔍 发现 4 个 PCAP 文件，开始验证...
✅ sample1_tls.pcapng - 通过 (12/12 帧已全部掩码)
✅ sample2_tls.pcap   - 通过 (8/8 帧已全部掩码)
❌ sample3_tls.pcap   - 失败 (2 帧未被成功置零)
📊 Overall Pass Rate: 66.7% (退出码 1)
```

---

## 5. 报告文件说明

`validation_summary.json` 示例结构（v1.1 起字段更丰富）：

```jsonc
{
  "overall_pass_rate": 66.7,
  "files": [
    {
      "file": "sample1_tls.pcapng",
      "status": "pass",
      "records_before": 12,
      "records_after": 12,
      "total_records": 12,
      "masked_records": 12,
      "unmasked_records": 0,
      "masked_ok_frames": [1,2,3,4,5,6,7,8,9,10,11,12],
      "failed_frames": [],
      "failed_frame_details": []
    },
    {
      "file": "sample3_tls.pcap",
      "status": "fail",
      "records_before": 11,
      "records_after": 11,
      "total_records": 11,
      "masked_records": 9,
      "unmasked_records": 2,
      "masked_ok_frames": [1,2,3,4,5,6,7,8,9],
      "failed_frames": [10,11],
      "failed_frame_details": [
        {"frame": 10, "path": "eth:...:tls", "lengths": [69], "zero_bytes": 0, "payload_preview": "160301..."},
        {"frame": 11, "path": "eth:...:tls", "lengths": [69], "zero_bytes": 0, "payload_preview": "160301..."}
      ]
    }
  ]
}
```

* `overall_pass_rate`：百分比格式，全部通过为 `100.0`。  
* `files`：各文件验证结果列表。
  - `total_records`：TLS23 消息总数。
  - `masked_records`：已完全置零的消息数。
  - `unmasked_records`：仍含明文字节的消息数。
  - `failed_frame_details`：若 `unmasked_records`>0，列出失败帧的关键字段，便于定位问题。

此外，将同时生成 `validation_summary.html`，在浏览器打开即可查看图表化结果：

* 绿色行表示文件通过，红色行表示失败。  
* 点击失败行中的【失败帧详情】可展开查看具体帧号、路径、payload 预览等信息。

---

## 6. 常见问题 (FAQ)

### Q1: 运行时报错 `tshark: Command not found`？
请安装 Wireshark 并确认 `tshark` 可在 PATH 中被找到。

### Q2: 执行很慢怎么办？
1. 使用 `--glob` 缩小文件范围；  
2. 未来版本将支持 `--parallel N` 参数进行并行处理。

### Q3: 结果显示 TLS23 帧计数不一致？
确认使用的 PCAP 文件未被其他工具修改；同时检查第一轮与第二轮扫描是否指向同一个输入文件（掩码前/掩码后文件名应不同）。

---

## 7. 贡献与反馈

如发现脚本问题或有功能改进建议，请在 GitHub 提交 Issue 或 Pull Request，或直接联系维护者。

---

> 版权声明 © 2025 PktMask Contributors 