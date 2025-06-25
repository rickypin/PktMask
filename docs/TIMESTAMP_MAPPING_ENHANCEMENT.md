# 时间戳映射算法增强方案（Phase 2 修订）

> 目标：彻底消除 *同一时间戳不同协议* 造成的包映射冲突，确保重组文件中的 TLS 分析结果能够 **唯一定向** 回原始 PCAP 中的正确数据包。

---

## 1 现状与痛点

| 项目 | 现行实现 |
| --- | --- |
| 映射键 | 仅使用 `sniff_timestamp`（微秒级浮点数） |
| 校验 | 无其它确认；一旦时间戳相同即建立映射 |
| 风险 | ① 不同协议/方向包落在相同微秒→误映射<br/>② VLAN/隧道环境中相对时间对齐更密集，冲突概率 ↑<br/>③ 误映射后深度分析会为错误的数据包生成掩码指令，验证阶段报"无 TCP 载荷"错误 |

案例：`tls_1_2_single_vlan.pcap` 中 3 个 ICMP 包与 TLS Application-Data 记录时间戳相同 → 被误识别为 `content-type = 23`，导致第 807 帧验证失败。

---

## 2 改进思路

```
时间戳 (primary key)
└── 五元组 + 协议号 (second check)
    └── 载荷长度 / 序列号补充验证 (optional)
```

1. **时间戳预过滤** ：维持 O(1) 查找。
2. **协议一致性** ：
   * IP `proto` == 6 ( TCP )
   * 存在 `tcp.payload`（长度>0）
3. **五元组比对** ：`src_ip dst_ip src_port dst_port` 必须完全一致。
4. **载荷长度 & TCP flags（可选）** ：长度≥ 5 且非 SYN/ACK 纯握手包。
5. **Fail-over 策略** ：如多封包均符合，则按以下优先级选择：
   1. 载荷长度最大者
   2. 帧号最小者
6. **统计告警** ：若发生冲突（同一时间戳映射至 >1 原始包）写入日志，方便排查。

---

## 3 数据结构调整

```python
# 伪码
orig_key = (
    packet.sniff_timestamp,
    ip.src, ip.dst,
    tcp.srcport, tcp.dstport
)
orig_map[orig_key] = orig_index

# 查找
key = (ts, ip.src, ip.dst, tcp.srcport, tcp.dstport)
orig_idx = orig_map.get(key)
```

* 以 **复合键** 替代单时间戳。
* 键长约 4 字节 × 4 + 时间戳(8) ≈ 24 B，可接受。

---

## 4 实现步骤

1. **创建辅助函数** `_build_orig_key(pkt) -> Tuple`，封装键提取逻辑。
2. 修改 `_build_timestamp_mapping`：
   * 首轮遍历原始 PCAP 构建 `orig_map: Dict[Tuple, int]`。
   * 第二轮遍历重组文件根据同样键查找。
3. 回溯兼容：若键缺失（例如 UDP 流）回退到旧时间戳逻辑。
4. 单元测试
   * 构造"同时间戳不同协议"人造 PCAP → 期待仅 TCP 匹配。
   * 真实样本 `tls_1_2_single_vlan.pcap` → 验证 807 帧不再被映射。
5. 性能评估 ：对 10 万包 PCAP 进行基准；预期时间增加 <5%。

---

## 5 回归风险与缓解

| 风险 | 缓解措施 |
| --- | --- |
| 键过度严格 → 部分合法包无法映射 | 日志警告 + 回退到时间戳匹配（带 *协议校验*） |
| 内存占用增加 | 使用 `dict` + `__slots__` 简单对象或纯元组；删除 PyShark 对象后立即 `gc.collect()` |
| 多协议场景 (UDP/DNS) | 流保持原逻辑；仅对 TCP 激活复合键 |

---

## 6 预计收益

* **误映射率 → 0**（在测试样本中）
* 修复 `tls_1_2_single_vlan` 验证失败；所有 TLS Trim 用例预期全绿。
* 为 Multi-protocol 扩展奠定健壮的映射基础。

---

## 7 时间线

| 任务 | 预估 | 负责人 |
| --- | --- | --- |
| 代码重构 & 基本测试 | 1 h | \- |
| 人造 PCAP 单元测试 | 30 m | \- |
| 真实样本回归 | 20 m | \- |
| 性能基准 & 文档 | 20 m | \- |

**总计：≈ 2 小时完成**

---

> 作者：AI 助手 – 2025-06-26 