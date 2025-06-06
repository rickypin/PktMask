import json
import os
from datetime import datetime
from typing import Dict, List, Any
from jinja2 import Template

from pktmask.utils.path import resource_path

# 自动加载HTML模板
try:
    TEMPLATE_PATH = resource_path('log_template.html')
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        LOG_HTML = f.read()
    HTML_TEMPLATE = Template(LOG_HTML)
except Exception as e:
    HTML_TEMPLATE = None
    print(f"Warning: Could not load HTML template. HTML reports will be disabled. Error: {e}")

def current_time() -> str:
    """获取当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def generate_report(
    subdir_path: str,
    rel_subdir: str,
    processed_file_count: int,
    final_mapping: Dict[str, str],
    elapsed_time: float,
    file_ip_counts: Dict[str, int],
    file_mappings: Dict[str, Dict[str, str]],
    error_log: List[str]
):
    """
    生成处理结果的 JSON 和 HTML 报告。

    Args:
        subdir_path (str): 报告要保存到的目录。
        rel_subdir (str): 相对子目录路径，用于报告显示。
        processed_file_count (int): 已处理的文件总数。
        final_mapping (Dict[str, str]): 最终使用的总 IP 映射。
        elapsed_time (float): 总处理耗时（秒）。
        file_ip_counts (Dict[str, int]): 每个文件中的唯一IP数。
        file_mappings (Dict[str, Dict[str, str]]): 每个文件的IP映射详情。
        error_log (List[str]): 错误日志。
    """
    stats = {
        "processed_file_count": processed_file_count,
        "total_unique_ips": len(final_mapping),
        "total_time_seconds": round(elapsed_time, 2),
        "file_ip_counts": file_ip_counts
    }
    
    report_data = {
        "stats": stats,
        "file_mappings": file_mappings,
        "total_mapping": final_mapping,
        "error_log": error_log
    }
    
    # 保存JSON报告
    report_path = os.path.join(subdir_path, "replacement.log")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        error_log.append(f"{current_time()} - Error saving JSON report: {str(e)}")
        print(f"[{current_time()}] Error saving JSON report: {str(e)}")

    # 生成HTML报告
    if HTML_TEMPLATE:
        try:
            html_path = os.path.join(subdir_path, "replacement.html")
            html_content = HTML_TEMPLATE.render(
                subdir=rel_subdir,
                now=current_time(),
                stats=stats,
                file_mappings=file_mappings,
                total_mapping=final_mapping
            )
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
        except Exception as e:
            error_log.append(f"{current_time()} - Error generating HTML report: {str(e)}")
            print(f"[{current_time()}] Error generating HTML report: {str(e)}") 