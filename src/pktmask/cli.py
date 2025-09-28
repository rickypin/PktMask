from pathlib import Path
from typing import Any, Dict, Optional, Union

import typer

from pktmask.services.config_service import build_config_from_unified_args, validate_pipeline_config
from pktmask.services.output_service import create_output_service
from pktmask.services.pipeline_service import (
    PipelineServiceError,
    create_gui_compatible_report_data,
    create_pipeline_executor,
    process_directory_cli,
    process_single_file,
)
from pktmask.services.report_service import get_report_service

# ---------------------------------------------------------------------------
# Typer Application Initialization
# ---------------------------------------------------------------------------
app = typer.Typer(help="PktMask CLI - Unified command line interface with directory support")

# ---------------------------------------------------------------------------
# Common Helper Functions
# ---------------------------------------------------------------------------


def _validate_process_parameters(dedup: bool, anon: bool, mask: bool) -> tuple[bool, str | None]:
    """Validate that at least one operation is selected for process command"""
    if not any([dedup, anon, mask]):
        return (
            False,
            "At least one operation must be specified: --dedup, --anon, or --mask",
        )

    return True, None


def _detect_input_type(input_path: Path) -> tuple[str, str | None]:
    """
    Detect input type and validate appropriateness.

    Returns:
        tuple: (input_type, error_message)
        input_type: 'file', 'directory', or 'invalid'
        error_message: None if valid, error string if invalid
    """
    if not input_path.exists():
        return "invalid", f"Input path does not exist: {input_path}"

    if input_path.is_file():
        # Check if it's a PCAP file
        if input_path.suffix.lower() in [".pcap", ".pcapng"]:
            return "file", None
        else:
            return (
                "invalid",
                f"Input file must be a PCAP or PCAPNG file (got: {input_path.suffix})",
            )

    elif input_path.is_dir():
        # Check if directory contains PCAP files
        pcap_files = list(input_path.glob("*.pcap")) + list(input_path.glob("*.pcapng"))
        if pcap_files:
            return "directory", None
        else:
            return "invalid", f"Directory contains no PCAP/PCAPNG files: {input_path}"

    else:
        return "invalid", f"Input path is neither a file nor a directory: {input_path}"


def _generate_smart_output_path(input_path: Path, input_type: str) -> Path:
    """
    Generate smart output path when none is specified.

    Args:
        input_path: Input file or directory path
        input_type: 'file' or 'directory'

    Returns:
        Generated output path
    """
    if input_type == "file":
        # For files: same directory with _processed suffix
        parent = input_path.parent
        stem = input_path.stem
        suffix = input_path.suffix
        return parent / f"{stem}_processed{suffix}"

    elif input_type == "directory":
        # For directories: create sibling directory with _processed suffix
        parent = input_path.parent
        name = input_path.name
        return parent / f"{name}_processed"

    else:
        raise ValueError(f"Invalid input type: {input_type}")


def _build_config_from_unified_args(
    dedup: bool = False,
    anon: bool = False,
    mask: bool = False,
) -> Dict[str, Any]:
    """Build configuration from unified CLI arguments with TLS protocol"""
    return build_config_from_unified_args(dedup=dedup, anon=anon, mask=mask, protocol="tls")  # Always use TLS protocol


def _run_unified_pipeline(
    input_path: Union[Path, str],
    output_path: Union[Path, str],
    enable_dedup: bool = False,
    enable_anon: bool = False,
    enable_mask: bool = False,
    verbose: bool = False,
    save_report: bool = False,
) -> None:
    """Unified pipeline execution for both files and directories with smart defaults."""

    # 初始化报告服务
    report_service = get_report_service() if save_report else None

    try:
        # 构建配置
        config = build_config_from_unified_args(
            dedup=enable_dedup,
            anon=enable_anon,
            mask=enable_mask,
            protocol="tls",  # Always use TLS protocol
        )

        # 验证配置
        is_valid, error_msg = validate_pipeline_config(config)
        if not is_valid:
            typer.echo(f"❌ Configuration error: {error_msg}", err=True)
            raise typer.Exit(1)

        # 创建执行器
        executor = create_pipeline_executor(config)

        # 创建输出服务 (smart defaults: text format, auto-detect verbosity level)
        output_service = create_output_service(format_str="text", level_str="verbose" if verbose else "normal")

        # 开始报告
        if report_service:
            report_service.start_report(str(input_path), str(output_path))

        # 创建进度回调（包含报告回调）- always show progress for better UX
        progress_callback = None
        if True or report_service:  # Always show progress
            progress_callback = _create_enhanced_progress_callback(
                verbose=verbose, show_stages=verbose, report_service=report_service
            )

        # 判断输入类型并处理
        input_path_obj = Path(input_path)

        if input_path_obj.is_file():
            # 单文件处理
            output_service.print_processing_start(str(input_path), 1)
            result = process_single_file(
                executor=executor,
                input_file=str(input_path),
                output_file=str(output_path),
                progress_callback=progress_callback,
                verbose=verbose,
            )
        elif input_path_obj.is_dir():
            # 目录处理 (smart default: auto-detect PCAP files)
            output_service.print_processing_start(str(input_path))
            result = process_directory_cli(
                executor=executor,
                input_dir=str(input_path),
                output_dir=str(output_path),
                progress_callback=progress_callback,
                verbose=verbose,
                file_pattern="*.pcap,*.pcapng",  # Smart default
            )
        else:
            typer.echo(f"❌ Input path does not exist: {input_path}", err=True)
            raise typer.Exit(1)

        # 完成报告
        if report_service:
            total_packets = sum(
                stats.get("packets_processed", 0) for stats in result.get("stage_stats", []) if isinstance(stats, dict)
            )
            modified_packets = sum(
                stats.get("packets_modified", 0) for stats in result.get("stage_stats", []) if isinstance(stats, dict)
            )

            # 使用GUI兼容的报告数据格式
            create_gui_compatible_report_data(result)

            report = report_service.finalize_report(
                success=result["success"],
                total_files=result.get("total_files", 1),
                processed_files=result.get("processed_files", 1 if result["success"] else 0),
                total_packets=total_packets,
                modified_packets=modified_packets,
            )

            # 保存报告到文件 (smart default: text format)
            try:
                # 使用标准报告服务 (simplified - no format options)
                report_path = report_service.save_report_to_file(
                    report=report,
                    output_path=(str(output_path) if Path(output_path).is_dir() else str(Path(output_path).parent)),
                    format_type="text",  # Smart default
                    detailed=verbose,  # Use verbose flag for detail level
                )
                typer.echo(f"📄 Report saved: {report_path}")
            except Exception as e:
                typer.echo(f"⚠️  Failed to save report: {e}", err=True)

        # 显示处理结果
        output_service.print_processing_summary(result)

        # 根据结果设置退出码
        if not result["success"]:
            raise typer.Exit(1)

    except PipelineServiceError as e:
        if report_service:
            report_service.add_error(str(e))
        typer.echo(f"❌ Pipeline error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        if report_service:
            report_service.add_error(str(e))
        typer.echo(f"❌ Unexpected error: {e}", err=True)
        raise typer.Exit(1)


def _create_enhanced_progress_callback(verbose: bool = False, show_stages: bool = False, report_service=None):
    """创建增强的进度回调函数 - 使用简化的进度报告系统"""
    from pktmask.core.progress.simple_progress import create_simple_progress_callback

    # 使用简化的进度报告系统
    return create_simple_progress_callback(verbose=verbose, show_stages=show_stages, report_service=report_service)


# ---------------------------------------------------------------------------
# Unified Processing Command (Recommended)
# ---------------------------------------------------------------------------


@app.command("process")
def cmd_process(
    input_path: Path = typer.Argument(..., help="Input PCAP/PCAPNG file or directory"),
    output_path: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output file/directory path (auto-generated if not specified)",
    ),
    dedup: bool = typer.Option(False, "--dedup", help="Enable Remove Dupes processing"),
    anon: bool = typer.Option(False, "--anon", help="Enable Anonymize IPs processing"),
    mask: bool = typer.Option(False, "--mask", help="Enable Mask Payloads processing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
    save_report: bool = typer.Option(False, "--save-report", help="Save detailed processing report"),
):
    """Unified processing command with intelligent operation defaults.

    Automatically detects input type and applies smart defaults:
    - Directory input with no flags: auto-enables all operations (--dedup --anon --mask)
    - File input with no flags: requires explicit operation specification
    - Output path is auto-generated if not specified

    Examples:
        # Single file processing (requires explicit operations)
        pktmask process input.pcap --dedup
        pktmask process input.pcap --anon --mask

        # Directory processing (auto-enables all operations)
        pktmask process /data/pcaps                    # Auto: --dedup --anon --mask
        pktmask process /data/pcaps --dedup --anon     # Explicit: only dedup + anon

        # Custom output paths
        pktmask process input.pcap -o custom_output.pcap --dedup
        pktmask process /data/pcaps -o /custom/output --anon --mask
    """

    # Detect and validate input type first
    input_type, input_error = _detect_input_type(input_path)
    if input_error:
        typer.echo(f"❌ {input_error}", err=True)
        raise typer.Exit(1)

    # Implement intelligent defaults based on input type

    if not any([dedup, anon, mask]):
        if input_type == "directory":
            # Directory processing: auto-enable all operations
            dedup = anon = mask = True
            typer.echo("🔄 Directory processing detected: auto-enabled all operations (--dedup --anon --mask)")
            typer.echo("   Use explicit flags to override this behavior (e.g., --dedup --anon)")
        else:
            # File processing: require explicit operation specification
            typer.echo(
                "❌ At least one operation must be specified: --dedup, --anon, or --mask",
                err=True,
            )
            raise typer.Exit(1)

    # Generate output path if not specified
    if output_path is None:
        output_path = _generate_smart_output_path(input_path, input_type)
        typer.echo(f"📁 Auto-generated output path: {output_path}")

    # Build configuration using unified arguments
    try:
        config = _build_config_from_unified_args(
            dedup=dedup,
            anon=anon,
            mask=mask,
        )

        # Validate configuration
        is_valid, error_msg = validate_pipeline_config(config)
        if not is_valid:
            typer.echo(f"❌ Configuration error: {error_msg}", err=True)
            raise typer.Exit(1)

        # Execute using simplified unified pipeline
        _run_unified_pipeline(
            input_path=input_path,
            output_path=output_path,
            enable_dedup=dedup,
            enable_anon=anon,
            enable_mask=mask,
            verbose=verbose,
            save_report=save_report,
        )

    except Exception as e:
        typer.echo(f"❌ Processing failed: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Information commands
# ---------------------------------------------------------------------------


@app.command("info")
def cmd_info(
    input_path: Path = typer.Argument(..., exists=True, help="Input file or directory to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    output_format: str = typer.Option("text", "--format", help="Output format: text|json"),
):
    """Display information about PCAP files or directories.

    This command analyzes the input without processing, showing file counts,
    sizes, and basic statistics.

    Examples:
        # Analyze single file
        pktmask info input.pcap

        # Analyze directory
        pktmask info /path/to/pcaps --verbose

        # Get JSON output
        pktmask info /path/to/pcaps --format json
    """

    try:
        import glob
        import os
        from datetime import datetime

        input_path_obj = Path(input_path)

        if input_path_obj.is_file():
            # 单文件信息
            file_size = input_path_obj.stat().st_size
            file_mtime = datetime.fromtimestamp(input_path_obj.stat().st_mtime)

            info = {
                "type": "file",
                "path": str(input_path_obj),
                "size_bytes": file_size,
                "size_human": _format_bytes(file_size),
                "modified": file_mtime.isoformat(),
                "extension": input_path_obj.suffix,
            }

        elif input_path_obj.is_dir():
            # 目录信息
            pcap_files = []
            patterns = ["*.pcap", "*.pcapng", "*.cap"]

            for pattern in patterns:
                files = glob.glob(os.path.join(str(input_path_obj), pattern))
                pcap_files.extend(files)

            total_size = sum(os.path.getsize(f) for f in pcap_files)

            info = {
                "type": "directory",
                "path": str(input_path_obj),
                "total_files": len(pcap_files),
                "total_size_bytes": total_size,
                "total_size_human": _format_bytes(total_size),
                "file_extensions": list(set(Path(f).suffix for f in pcap_files)),
            }

            if verbose:
                info["files"] = [
                    {
                        "name": os.path.basename(f),
                        "size_bytes": os.path.getsize(f),
                        "size_human": _format_bytes(os.path.getsize(f)),
                    }
                    for f in pcap_files
                ]
        else:
            typer.echo(f"❌ Path does not exist: {input_path}", err=True)
            raise typer.Exit(1)

        # 输出信息
        if output_format == "json":
            import json

            typer.echo(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            _print_info_text(info, verbose)

    except Exception as e:
        typer.echo(f"❌ Error analyzing path: {e}", err=True)
        raise typer.Exit(1)


def _format_bytes(bytes_count: int) -> str:
    """Format bytes in human readable format"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"


def _print_info_text(info: dict, verbose: bool):
    """Print info in text format"""
    if info["type"] == "file":
        typer.echo(f"📄 File: {info['path']}")
        typer.echo(f"   Size: {info['size_human']} ({info['size_bytes']:,} bytes)")
        typer.echo(f"   Modified: {info['modified']}")
        typer.echo(f"   Extension: {info['extension']}")
    else:
        typer.echo(f"📁 Directory: {info['path']}")
        typer.echo(f"   Files: {info['total_files']}")
        typer.echo(f"   Total size: {info['total_size_human']} ({info['total_size_bytes']:,} bytes)")
        typer.echo(f"   Extensions: {', '.join(info['file_extensions'])}")

        if verbose and "files" in info:
            typer.echo("\n   File details:")
            for file_info in info["files"]:
                typer.echo(f"     • {file_info['name']}: {file_info['size_human']}")


# CLI commands are managed uniformly by __main__.py
# Direct execution of this file is no longer supported
