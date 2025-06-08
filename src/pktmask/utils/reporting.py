import json
import os
from datetime import datetime
from typing import Dict, List, Any
from jinja2 import Template
from abc import ABC, abstractmethod

from pktmask.utils.path import resource_path
from pktmask.utils.time import current_time
from pktmask.infrastructure.logging import get_logger
from pktmask.common.exceptions import FileError, create_error_from_exception

class Reporter(ABC):
    """报告生成器的抽象基类。"""
    @abstractmethod
    def generate(self, report_name: str, report_data: Dict[str, Any]):
        """生成报告的接口方法。"""
        pass

    @abstractmethod
    def finalize_report_for_directory(self, subdir_name: str, stats: Dict[str, Any], final_mapping: Dict[str, str]):
        """在目录处理完成后生成最终报告。"""
        pass

    def set_output_directory(self, path: str):
        """设置报告输出目录的可选方法。"""
        pass

# 自动加载HTML模板
logger = get_logger('reporting')

try:
    TEMPLATE_PATH = resource_path('log_template.html')
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        LOG_HTML = f.read()
    HTML_TEMPLATE = Template(LOG_HTML)
    logger.info("HTML template loaded successfully")
except Exception as e:
    HTML_TEMPLATE = None
    logger.warning(f"Could not load HTML template. HTML reports will be disabled. Error: {e}")

class FileReporter(Reporter):
    """将报告写入JSON和HTML文件的具体实现。"""
    def __init__(self):
        self._output_dir = os.getcwd() # 默认为当前工作目录
        self._logger = get_logger('file_reporter')

    def set_output_directory(self, path: str):
        """设置报告的输出目录。"""
        try:
            if not os.path.isdir(path):
                os.makedirs(path, exist_ok=True)
                self._logger.info(f"Created output directory: {path}")
            self._output_dir = path
            self._logger.debug(f"Report output directory set to: {path}")
        except Exception as e:
            error = create_error_from_exception(e, {'path': path})
            self._logger.error(f"Failed to set output directory: {error}")
            raise error

    def generate(self, report_name: str, report_data: Dict[str, Any]):
        """为单个操作生成并保存JSON报告。"""
        report_path = os.path.join(self._output_dir, f"{report_name}.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            self._logger.info(f"Generated JSON report: {report_path}")
        except Exception as e:
            error = FileError(
                f"Error saving JSON report for {report_name}",
                file_path=report_path,
                operation="write"
            )
            self._logger.error(f"Failed to generate JSON report: {error}")
            # 不抛出异常，因为报告生成失败不应该中断主流程

    def finalize_report_for_directory(self, subdir_name: str, stats: Dict[str, Any], final_mapping: Dict[str, str]):
        """为整个目录生成并保存一个最终的JSON和HTML报告。"""
        
        report_name = f"final_report_for_{subdir_name.replace('/', '_')}"
        
        # 构造用于JSON和HTML的数据
        report_data = {
            "path": subdir_name,
            "stats": stats,
            "data": { "total_mapping": final_mapping },
            "generated_at": current_time()
        }

        # 保存JSON报告
        self.generate(report_name, report_data)

        # 生成HTML报告
        if HTML_TEMPLATE:
            render_data = {
                "subdir": subdir_name,
                "now": current_time(),
                "stats": stats,
                "total_mapping": final_mapping,
                "file_mappings": {} # 在总报告中不提供单文件映射
            }
            try:
                html_path = os.path.join(self._output_dir, f"{report_name}.html")
                html_content = HTML_TEMPLATE.render(**render_data)
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                self._logger.info(f"Generated HTML report: {html_path}")
            except Exception as e:
                error = FileError(
                    f"Error generating final HTML report for {subdir_name}",
                    file_path=html_path,
                    operation="write"
                )
                self._logger.error(f"Failed to generate HTML report: {error}")
        else:
            self._logger.debug("HTML template not available, skipping HTML report generation")
        
        return report_data

# 旧的 generate_report 函数已被废弃，其逻辑已移入 FileReporter 类。
# 为了保持向后兼容性（以防万一），可以保留一个包装器，但最好是直接移除。
# 我们选择直接移除。 