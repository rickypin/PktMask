import warnings
from pathlib import Path
from typing import Optional

import typer

from pktmask.core.pipeline.executor import PipelineExecutor

# ---------------------------------------------------------------------------
# Typer 应用初始化
# ---------------------------------------------------------------------------
app = typer.Typer(help="PktMask CLI - 基于 PipelineExecutor 的命令行接口")

# ---------------------------------------------------------------------------
# 公共帮助函数
# ---------------------------------------------------------------------------

def _run_pipeline(
    input_file: Path,
    output_file: Path,
    enable_dedup: bool = False,
    enable_anon: bool = False,
    enable_mask: bool = False,
    recipe_path: Optional[str] = None,
) -> None:
    """构造 Pipeline 配置并执行。"""

    cfg = {
        "dedup": {"enabled": enable_dedup},
        "anon": {"enabled": enable_anon},
        "mask": {
            "enabled": enable_mask,
        },
    }

    if recipe_path:
        cfg["mask"]["recipe_path"] = recipe_path  # type: ignore[index]

    executor = PipelineExecutor(cfg)
    result = executor.run(str(input_file), str(output_file))

    # 简要输出统计信息；详细信息可序列化 result.to_dict()
    typer.echo(
        f"✅ 处理完成! 耗时: {result.duration_ms:.1f} ms | 输出文件: {result.output_file}"
    )


# ---------------------------------------------------------------------------
# 主命令: mask
# ---------------------------------------------------------------------------


@app.command("mask")
def cmd_mask(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="输入 PCAP/PCAPNG 文件"),
    output_path: Path = typer.Option(..., "-o", "--output", help="输出文件路径"),
    dedup: bool = typer.Option(False, "--dedup", help="启用去重阶段"),
    anon: bool = typer.Option(False, "--anon", help="启用 IP 匿名化阶段"),
    recipe_path: Optional[str] = typer.Option(
        None,
        "--recipe-path",
        help="可选的 MaskRecipe JSON 路径 (用于 BlindPacketMasker)",
    ),
):
    """执行载荷掩码 (BlindPacketMasker) Pipeline。"""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_dedup=dedup,
        enable_anon=anon,
        enable_mask=True,
        recipe_path=recipe_path,
    )


# ---------------------------------------------------------------------------
# 兼容别名: trim (Deprecated)
# ---------------------------------------------------------------------------


@app.command("trim")
def cmd_trim(*args, **kwargs):  # type: ignore[override]
    """已废弃的别名，等价于 `mask` 命令。"""

    warnings.warn(
        "`pktmask trim` 已废弃，请使用 `pktmask mask`。", DeprecationWarning, stacklevel=2
    )
    cmd_mask(*args, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# dedup / anon 单独命令 (便于快速处理)
# ---------------------------------------------------------------------------


@app.command("dedup")
def cmd_dedup(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="输入 PCAP/PCAPNG 文件"),
    output_path: Path = typer.Option(..., "-o", "--output", help="输出文件路径"),
):
    """仅执行去重阶段。"""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_dedup=True,
    )


@app.command("anon")
def cmd_anon(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="输入 PCAP/PCAPNG 文件"),
    output_path: Path = typer.Option(..., "-o", "--output", help="输出文件路径"),
):
    """仅执行 IP 匿名化阶段。"""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_anon=True,
    ) 