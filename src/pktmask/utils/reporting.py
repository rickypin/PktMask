import json
import os
from datetime import datetime
from typing import Dict, List, Any
from jinja2 import Template
from abc import ABC, abstractmethod

from pktmask.utils.path import resource_path

class Reporter(ABC):
    """报告生成器的抽象基类。"""
    @abstractmethod
    def generate(self, subdir_path: str, report_data: Dict[str, Any]):
        """生成报告的接口方法。"""
        pass

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

class FileReporter(Reporter):
    """将报告写入JSON和HTML文件的具体实现。"""
    def generate(self, subdir_path: str, report_data: Dict[str, Any]):
        rel_subdir = report_data.get("rel_subdir", os.path.basename(subdir_path))
        stats = report_data.get("stats", {})
        file_mappings = report_data.get("file_mappings", {})
        total_mapping = report_data.get("total_mapping", {})
        error_log = report_data.get("error_log", [])

        # 准备用于渲染的数据
        render_data = {
            "subdir": rel_subdir,
            "now": current_time(),
            "stats": stats,
            "file_mappings": file_mappings,
            "total_mapping": total_mapping
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
                html_content = HTML_TEMPLATE.render(**render_data)
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
            except Exception as e:
                error_log.append(f"{current_time()} - Error generating HTML report: {str(e)}")
                print(f"[{current_time()}] Error generating HTML report: {str(e)}")

# 旧的 generate_report 函数已被废弃，其逻辑已移入 FileReporter 类。
# 为了保持向后兼容性（以防万一），可以保留一个包装器，但最好是直接移除。
# 我们选择直接移除。 