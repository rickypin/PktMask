from pathlib import Path
from typing import Optional, Union, Dict, Any
import warnings
import os
import sys
from datetime import datetime

import typer

from pktmask.services.pipeline_service import (
    create_pipeline_executor,
    process_single_file,
    process_directory_cli,
    PipelineServiceError,
    create_gui_compatible_report_data,
    generate_gui_style_report
)
from pktmask.services.config_service import build_config_from_cli_args, validate_pipeline_config
from pktmask.services.output_service import create_output_service, OutputFormat, OutputLevel
from pktmask.services.progress_service import create_cli_progress_callback
from pktmask.services.report_service import get_report_service

# ---------------------------------------------------------------------------
# Typer Application Initialization
# ---------------------------------------------------------------------------
app = typer.Typer(help="PktMask CLI - Unified command line interface with directory support")

# ---------------------------------------------------------------------------
# Common Helper Functions
# ---------------------------------------------------------------------------

def _run_unified_pipeline(
    input_path: Union[Path, str],
    output_path: Union[Path, str],
    enable_dedup: bool = False,
    enable_anon: bool = False,
    enable_mask: bool = False,
    mask_mode: Optional[str] = None,
    mask_protocol: str = "tls",
    verbose: bool = False,
    output_format: str = "text",
    show_progress: bool = True,
    file_pattern: str = "*.pcap,*.pcapng",
    save_report: bool = False,
    report_format: str = "text",
    report_detailed: bool = False
) -> None:
    """Unified pipeline execution for both files and directories."""

    # 初始化报告服务
    report_service = get_report_service() if save_report else None

    try:
        # 构建配置
        config = build_config_from_cli_args(
            enable_dedup=enable_dedup,
            enable_anon=enable_anon,
            enable_mask=enable_mask,
            mask_mode=mask_mode or "enhanced",
            mask_protocol=mask_protocol
        )

        # 验证配置
        is_valid, error_msg = validate_pipeline_config(config)
        if not is_valid:
            typer.echo(f"❌ Configuration error: {error_msg}", err=True)
            raise typer.Exit(1)

        # 创建执行器
        executor = create_pipeline_executor(config)

        # 创建输出服务
        output_service = create_output_service(
            format_str=output_format,
            level_str="verbose" if verbose else "normal"
        )

        # 开始报告
        if report_service:
            report_service.start_report(str(input_path), str(output_path))

        # 创建进度回调（包含报告回调）
        progress_callback = None
        if show_progress or report_service:
            progress_callback = _create_enhanced_progress_callback(
                verbose=verbose,
                show_stages=verbose,
                report_service=report_service
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
                verbose=verbose
            )
        elif input_path_obj.is_dir():
            # 目录处理
            output_service.print_processing_start(str(input_path))
            result = process_directory_cli(
                executor=executor,
                input_dir=str(input_path),
                output_dir=str(output_path),
                progress_callback=progress_callback,
                verbose=verbose,
                file_pattern=file_pattern
            )
        else:
            typer.echo(f"❌ Input path does not exist: {input_path}", err=True)
            raise typer.Exit(1)

        # 完成报告
        if report_service:
            total_packets = sum(
                stats.get('packets_processed', 0)
                for stats in result.get('stage_stats', [])
                if isinstance(stats, dict)
            )
            modified_packets = sum(
                stats.get('packets_modified', 0)
                for stats in result.get('stage_stats', [])
                if isinstance(stats, dict)
            )

            # 使用GUI兼容的报告数据格式
            gui_compatible_data = create_gui_compatible_report_data(result)

            report = report_service.finalize_report(
                success=result['success'],
                total_files=result.get('total_files', 1),
                processed_files=result.get('processed_files', 1 if result['success'] else 0),
                total_packets=total_packets,
                modified_packets=modified_packets
            )

            # 保存报告到文件
            try:
                if report_format.lower() == "gui":
                    # 生成GUI风格的报告
                    gui_report_content = generate_gui_style_report(result)

                    # 手动保存GUI风格报告
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"pktmask_gui_style_report_{timestamp}.txt"
                    output_dir = str(output_path) if Path(output_path).is_dir() else str(Path(output_path).parent)
                    report_path = Path(output_dir) / filename

                    with open(report_path, 'w', encoding='utf-8') as f:
                        f.write(gui_report_content)

                    typer.echo(f"📄 GUI-style report saved: {report_path}")
                else:
                    # 使用标准报告服务
                    report_path = report_service.save_report_to_file(
                        report=report,
                        output_path=str(output_path) if Path(output_path).is_dir() else str(Path(output_path).parent),
                        format_type=report_format,
                        detailed=report_detailed
                    )
                    typer.echo(f"📄 Report saved: {report_path}")
            except Exception as e:
                typer.echo(f"⚠️  Failed to save report: {e}", err=True)

        # 显示处理结果
        output_service.print_processing_summary(result)

        # 根据结果设置退出码
        if not result['success']:
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


def _create_enhanced_progress_callback(
    verbose: bool = False,
    show_stages: bool = False,
    report_service = None
):
    """创建增强的进度回调函数"""
    from pktmask.core.events import PipelineEvents

    # 创建基础进度回调
    base_callback = create_cli_progress_callback(verbose, show_stages)

    def enhanced_callback(event_type: PipelineEvents, data: Dict[str, Any]):
        # 调用基础回调
        base_callback(event_type, data)

        # 添加报告服务回调
        if report_service:
            if event_type == PipelineEvents.STEP_SUMMARY:
                stage_name = data.get('step_name', 'Unknown')
                report_service.add_stage_stats(stage_name, data)
            elif event_type == PipelineEvents.ERROR:
                error_message = data.get('message', 'Unknown error')
                report_service.add_error(error_message)

    return enhanced_callback


# ---------------------------------------------------------------------------
# Main Command: mask
# ---------------------------------------------------------------------------


@app.command("mask")
def cmd_mask(
    input_path: Path = typer.Argument(..., exists=True, help="Input PCAP/PCAPNG file or directory"),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file/directory path"),
    dedup: bool = typer.Option(False, "--dedup", help="Enable Remove Dupes processing"),
    anon: bool = typer.Option(False, "--anon", help="Enable Anonymize IPs processing"),
    mode: str = typer.Option("enhanced", "--mode", help="Mask Payloads mode: enhanced|basic"),
    protocol: str = typer.Option("tls", "--protocol", help="Protocol type: tls|http"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
    output_format: str = typer.Option("text", "--format", help="Output format: text|json"),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress display"),
    file_pattern: str = typer.Option("*.pcap,*.pcapng", "--pattern", help="File pattern for directory processing"),
    save_report: bool = typer.Option(False, "--save-report", help="Save detailed processing report"),
    report_format: str = typer.Option("text", "--report-format", help="Report format: text|json|gui"),
    report_detailed: bool = typer.Option(False, "--report-detailed", help="Include detailed stage statistics in report"),
):
    """Execute Mask Payloads pipeline with optional Remove Dupes and Anonymize IPs processing.

    Supports both single file and directory batch processing.

    Examples:
        # Process single file
        pktmask mask input.pcap -o output.pcap --dedup --anon

        # Process directory
        pktmask mask /path/to/pcaps -o /path/to/output --dedup --anon --verbose

        # Custom file pattern
        pktmask mask /path/to/pcaps -o /path/to/output --pattern "*.pcap,*.cap"
    """

    _run_unified_pipeline(
        input_path=input_path,
        output_path=output_path,
        enable_dedup=dedup,
        enable_anon=anon,
        enable_mask=True,
        mask_mode=mode,
        mask_protocol=protocol,
        verbose=verbose,
        output_format=output_format,
        show_progress=not no_progress,
        file_pattern=file_pattern,
        save_report=save_report,
        report_format=report_format,
        report_detailed=report_detailed
    )


# ---------------------------------------------------------------------------
# Standalone dedup/anon commands (for quick processing)
# ---------------------------------------------------------------------------


@app.command("dedup")
def cmd_dedup(
    input_path: Path = typer.Argument(..., exists=True, help="Input PCAP/PCAPNG file or directory"),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file/directory path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
    output_format: str = typer.Option("text", "--format", help="Output format: text|json"),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress display"),
    file_pattern: str = typer.Option("*.pcap,*.pcapng", "--pattern", help="File pattern for directory processing"),
):
    """Execute Remove Dupes processing only.

    Supports both single file and directory batch processing.

    Examples:
        # Process single file
        pktmask dedup input.pcap -o output.pcap

        # Process directory
        pktmask dedup /path/to/pcaps -o /path/to/output --verbose
    """

    _run_unified_pipeline(
        input_path=input_path,
        output_path=output_path,
        enable_dedup=True,
        verbose=verbose,
        output_format=output_format,
        show_progress=not no_progress,
        file_pattern=file_pattern
    )


@app.command("anon")
def cmd_anon(
    input_path: Path = typer.Argument(..., exists=True, help="Input PCAP/PCAPNG file or directory"),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file/directory path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
    output_format: str = typer.Option("text", "--format", help="Output format: text|json"),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress display"),
    file_pattern: str = typer.Option("*.pcap,*.pcapng", "--pattern", help="File pattern for directory processing"),
):
    """Execute Anonymize IPs processing only.

    Supports both single file and directory batch processing.

    Examples:
        # Process single file
        pktmask anon input.pcap -o output.pcap

        # Process directory
        pktmask anon /path/to/pcaps -o /path/to/output --verbose
    """

    _run_unified_pipeline(
        input_path=input_path,
        output_path=output_path,
        enable_anon=True,
        verbose=verbose,
        output_format=output_format,
        show_progress=not no_progress,
        file_pattern=file_pattern
    )


# ---------------------------------------------------------------------------
# Batch processing commands
# ---------------------------------------------------------------------------


@app.command("batch")
def cmd_batch(
    input_dir: Path = typer.Argument(..., exists=True, help="Input directory containing PCAP files"),
    output_dir: Path = typer.Option(..., "-o", "--output", help="Output directory path"),
    dedup: bool = typer.Option(True, "--dedup/--no-dedup", help="Enable/disable Remove Dupes processing"),
    anon: bool = typer.Option(True, "--anon/--no-anon", help="Enable/disable Anonymize IPs processing"),
    mask: bool = typer.Option(True, "--mask/--no-mask", help="Enable/disable Mask Payloads processing"),
    mode: str = typer.Option("enhanced", "--mode", help="Mask Payloads mode: enhanced|basic"),
    protocol: str = typer.Option("tls", "--protocol", help="Protocol type: tls|http"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
    output_format: str = typer.Option("text", "--format", help="Output format: text|json"),
    file_pattern: str = typer.Option("*.pcap,*.pcapng", "--pattern", help="File pattern to match"),
    parallel: bool = typer.Option(False, "--parallel", help="Enable parallel processing (experimental)"),
):
    """Batch process all PCAP files in a directory with full pipeline.

    This command is optimized for processing large numbers of files with
    all processing stages enabled by default.

    Examples:
        # Process all files with default settings
        pktmask batch /path/to/pcaps -o /path/to/output

        # Process with custom settings
        pktmask batch /path/to/pcaps -o /path/to/output --no-dedup --mode basic

        # Process with verbose output and JSON format
        pktmask batch /path/to/pcaps -o /path/to/output --verbose --format json
    """

    if not input_dir.is_dir():
        typer.echo(f"❌ Input path is not a directory: {input_dir}", err=True)
        raise typer.Exit(1)

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    if parallel:
        typer.echo("⚠️  Parallel processing is experimental and may not be stable", err=True)

    _run_unified_pipeline(
        input_path=input_dir,
        output_path=output_dir,
        enable_dedup=dedup,
        enable_anon=anon,
        enable_mask=mask,
        mask_mode=mode,
        mask_protocol=protocol,
        verbose=verbose,
        output_format=output_format,
        show_progress=True,
        file_pattern=file_pattern
    )


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
                'type': 'file',
                'path': str(input_path_obj),
                'size_bytes': file_size,
                'size_human': _format_bytes(file_size),
                'modified': file_mtime.isoformat(),
                'extension': input_path_obj.suffix
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
                'type': 'directory',
                'path': str(input_path_obj),
                'total_files': len(pcap_files),
                'total_size_bytes': total_size,
                'total_size_human': _format_bytes(total_size),
                'file_extensions': list(set(Path(f).suffix for f in pcap_files))
            }

            if verbose:
                info['files'] = [
                    {
                        'name': os.path.basename(f),
                        'size_bytes': os.path.getsize(f),
                        'size_human': _format_bytes(os.path.getsize(f))
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
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"


def _print_info_text(info: dict, verbose: bool):
    """Print info in text format"""
    if info['type'] == 'file':
        typer.echo(f"📄 File: {info['path']}")
        typer.echo(f"   Size: {info['size_human']} ({info['size_bytes']:,} bytes)")
        typer.echo(f"   Modified: {info['modified']}")
        typer.echo(f"   Extension: {info['extension']}")
    else:
        typer.echo(f"📁 Directory: {info['path']}")
        typer.echo(f"   Files: {info['total_files']}")
        typer.echo(f"   Total size: {info['total_size_human']} ({info['total_size_bytes']:,} bytes)")
        typer.echo(f"   Extensions: {', '.join(info['file_extensions'])}")

        if verbose and 'files' in info:
            typer.echo("\n   File details:")
            for file_info in info['files']:
                typer.echo(f"     • {file_info['name']}: {file_info['size_human']}")


# CLI commands are managed uniformly by __main__.py
# Direct execution of this file is no longer supported
