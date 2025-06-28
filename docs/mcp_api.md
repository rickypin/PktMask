# PktMask MCP HTTP API

> 版本：v0.1   撰写日期：2025-07-02

本文件描述 PktMask **微服务控制平面（MCP）** 的 HTTP API 设计。目标是提供一个简洁的 REST 接口，用于在无 GUI 场景（CI/CD、云函数、容器等）中触发 PktMask 处理流程。

## 1. 端点
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /process | 处理单个 PCAP/PCAPNG 文件 |

### 1.1 请求体 `POST /process`
```jsonc
{
  "input_path": "samples/tls_sample.pcapng",
  "output_path": "output/tls_sample_processed.pcapng",
  "steps": {
    "dedup": {"enabled": true},
    "anon": {"enabled": true, "strategy": "hierarchical"},
    "mask": {"enabled": true, "recipe_path": "config/samples/simple_mask_recipe.json"}
  }
}
```

* `input_path`：待处理文件路径，可为绝对或相对路径。
* `output_path`：输出文件路径，父目录须已存在并具有写权限。
* `steps`：Pipeline 配置，键与 `REFACTOR_PLAN.md §3` 中定义保持一致。

### 1.2 响应体
成功时返回 `200 OK`，JSON 结构与 `ProcessResult` 模型一致：
```jsonc
{
  "success": true,
  "input_file": "samples/tls_sample.pcapng",
  "output_file": "output/tls_sample_processed.pcapng",
  "duration_ms": 1234.56,
  "stage_stats": [
    {
      "stage_name": "DedupStage",
      "packets_processed": 100,
      "packets_modified": 0,
      "duration_ms": 10.5,
      "extra_metrics": {}
    }
  ],
  "errors": []
}
```

错误时返回：
* `404`：输入文件不存在
* `500`：内部错误，`detail` 字段包含错误信息

## 2. 快速启动
```bash
# 安装依赖（若未安装）
pip install fastapi uvicorn

# 启动开发服务器
env PYTHONPATH=. python -m pktmask.adapters.mcp --host 0.0.0.0 --port 8000 --reload
```

## 3. 示例调用（cURL）
```bash
curl -X POST http://localhost:8000/process \
     -H "Content-Type: application/json" \
     -d '{"input_path": "samples/tls_sample.pcapng", "output_path": "out.pcapng", "steps": {"dedup": {"enabled": true}}}'
```

---

> 提示：本接口设计为演示和内部自动化使用，不建议直接暴露到公网。如需部署到生产环境，请务必加上鉴权、限流、错误监控等安全措施。 