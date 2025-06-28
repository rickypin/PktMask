from __future__ import annotations

"""MCP (Microservice Control Plane) FastAPI 适配层。

该模块提供一个极简的 FastAPI 应用，包装 `PipelineExecutor`，方便通过
HTTP POST /process 触发完整的去重→匿名化→掩码流程。

设计目标：
1. **20 行 Demo**：实现最小可用 API；供内部自动化或 PoC 使用。
2. **无额外依赖**：仅依赖 `fastapi`/`uvicorn`，已在 `pyproject.toml` 加入主依赖。
3. **零业务逻辑**：所有核心处理仍在 `PipelineExecutor` 中完成。

示例启动：
```bash
python -m pktmask.adapters.mcp --host 0.0.0.0 --port 8000
```
"""

from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pktmask.core.pipeline.executor import PipelineExecutor

app = FastAPI(title="PktMask MCP API", version="0.1.0")


class ProcessRequest(BaseModel):
    """请求模型，对应 REFACTOR_PLAN.md §7.2。"""

    input_path: str
    output_path: str
    steps: Dict[str, Any] = {}


@app.post("/process")
async def process_pcap(req: ProcessRequest):  # type: ignore[valid-type]
    """处理单个 PCAP/PCAPNG 文件。"""

    try:
        executor = PipelineExecutor(config=req.steps)
        result = executor.run(req.input_path, req.output_path)
        return result.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) 