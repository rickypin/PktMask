from __future__ import annotations

"""`python -m pktmask.adapters.mcp` 启动 Uvicorn 开发服务器。"""

import argparse
import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start PktMask MCP FastAPI server.")
    parser.add_argument("--host", default="127.0.0.1", help="绑定主机 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认 8000)")
    parser.add_argument("--reload", action="store_true", help="启用自动重载 (开发模式)")
    args = parser.parse_args()

    uvicorn.run(
        "pktmask.adapters.mcp:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main() 