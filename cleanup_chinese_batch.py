#!/usr/bin/env python3
"""
批量清理PktMask项目中剩余的中文内容
"""

import os
import re
import sys
from pathlib import Path

# 中文到英文的翻译映射
TRANSLATIONS = {
    # 通用术语
    "进度服务接口": "Progress service interface",
    "提供统一的进度显示和回调管理服务": "Provides unified progress display and callback management services",
    "进度显示样式": "Progress display style",
    "进度状态": "Progress status",
    "统一进度服务": "Unified progress service",
    "添加进度回调": "Add progress callback",
    "移除进度回调": "Remove progress callback",
    "开始处理": "Start processing",
    "开始处理文件": "Start processing file",
    "更新阶段进度": "Update stage progress",
    "更新包统计": "Update packet statistics",
    "显示阶段进度": "Display stage progress",
    "完成文件处理": "Complete file processing",
    "完成所有处理": "Complete all processing",
    "显示总耗时": "Display total duration",
    "报告错误": "Report error",
    "发送事件到所有回调": "Send event to all callbacks",
    "更新进度行": "Update progress line",
    "覆盖式显示": "overwrite display",
    "计算进度百分比": "Calculate progress percentage",
    "清除之前的行": "Clear previous line",
    "写入新消息": "Write new message",
    "清除进度行": "Clear progress line",
    "创建进度条": "Create progress bar",
    "打印消息": "Print message",
    "便捷函数": "Convenience functions",
    "创建进度服务实例": "Create progress service instance",
    "创建CLI专用的进度回调函数": "Create CLI-specific progress callback function",
    "进度回调实现": "Progress callback implementation",
    
    # 报告服务
    "报告生成服务": "Report generation service",
    "提供统一的处理报告生成和格式化服务": "Provides unified processing report generation and formatting services",
    "处理报告数据结构": "Processing report data structure",
    "统一报告生成服务": "Unified report generation service",
    "开始新的报告": "Start new report",
    "添加阶段统计": "Add stage statistics",
    "添加错误信息": "Add error information",
    "添加警告信息": "Add warning information",
    "完成报告生成": "Complete report generation",
    "生成文本格式报告": "Generate text format report",
    "标题": "Title",
    "基本信息": "Basic information",
    "文件统计": "File statistics",
    "包统计": "Packet statistics",
    "阶段统计": "Stage statistics",
    "警告信息": "Warning information",
    "错误信息": "Error information",
    "结尾": "End",
    "生成JSON格式报告": "Generate JSON format report",
    "保存报告到文件": "Save report to file",
    "生成文件名": "Generate filename",
    "确保目录存在": "Ensure directory exists",
    "写入文件": "Write file",
    "格式化持续时间": "Format duration",
    "全局报告服务实例": "Global report service instance",
    "获取报告服务实例": "Get report service instance",
    "单例模式": "singleton pattern",
    
    # 输出服务
    "输出服务接口": "Output service interface",
    "提供统一的输出格式化和显示服务": "Provides unified output formatting and display services",
    "输出格式枚举": "Output format enumeration",
    "输出详细程度枚举": "Output verbosity enumeration",
    "统一输出服务": "Unified output service",
    "打印处理开始信息": "Print processing start information",
    "打印文件处理进度": "Print file processing progress",
    "打印阶段处理进度": "Print stage processing progress",
    "打印文件处理完成信息": "Print file processing completion information",
    "打印处理摘要": "Print processing summary",
    "打印错误信息": "Print error information",
    "打印警告信息": "Print warning information",
    "打印文本格式摘要": "Print text format summary",
    "时间信息": "Time information",
    "输出文件信息": "Output file information",
    "详细统计": "Detailed statistics",
    "模式": "mode",
    "只显示前": "Only show first",
    "个错误": "errors",
    "打印详细统计信息": "Print detailed statistics",
    "打印JSON格式摘要": "Print JSON format summary",
    "添加时间戳": "Add timestamp",
    "统一打印方法": "Unified print method",
    "创建输出服务实例": "Create output service instance",
    
    # 数据模型
    "数据模型模块": "Data model module",
    "包含所有核心数据传输对象和业务模型": "Contains all core data transfer objects and business models",
    "文件处理数据": "File processing data",
    "统计数据": "Statistics data",
    "管道事件数据": "Pipeline event data",
    "步骤结果数据": "Step result data",
    "报告数据": "Report data",
    
    # 日志系统
    "统一的日志管理系统": "Unified logging management system",
    "日志系统": "Logging system",
    "提供统一的日志管理功能": "Provides unified logging management functionality",
    "应用程序日志管理器": "Application log manager",
    "设置根日志记录器": "Setup root logger",
    "避免重复添加": "Avoid duplicate addition",
    "尝试从配置获取日志级别": "Try to get log level from configuration",
    "默认级别": "Default level",
    "如果配置获取失败": "If configuration retrieval fails",
    "使用默认级别": "Use default level",
    "控制台处理器": "Console handler",
    "文件处理器": "File handler",
    "如果文件日志设置失败": "If file logging setup fails",
    "至少保证控制台日志可用": "At least ensure console logging is available",
    "获取指定名称的日志记录器": "Get logger with specified name",
    "设置日志级别": "Set log level",
    "根据配置重新配置日志系统": "Reconfigure logging system based on configuration",
    "获取配置的日志级别": "Get configured log level",
    "更新所有现有处理器的级别": "Update level of all existing handlers",
    "这是控制台处理器": "This is console handler",
    "如果重新配置失败": "If reconfiguration fails",
    "记录警告但不中断程序": "Log warning but don't interrupt program",
    "记录异常信息": "Log exception information",
    "记录性能信息": "Log performance information",
    "全局日志管理器实例": "Global log manager instance",
    "获取日志记录器的便利函数": "Convenience function to get logger",
    "设置全局日志级别的便利函数": "Convenience function to set global log level",
    "根据当前配置重新配置日志系统的便利函数": "Convenience function to reconfigure logging system based on current configuration",
    "记录异常的便利函数": "Convenience function to log exceptions",
    "记录性能的便利函数": "Convenience function to log performance",
    "装饰器": "Decorator",
    "自动记录函数执行时间": "Automatically log function execution time",

    # 数据模型相关
    "统计数据模型": "Statistics data model",
    "定义处理过程中的各种统计数据结构": "Defines various statistical data structures during processing",
    "数据包统计信息": "Packet statistics information",
    "总包数": "Total packets",
    "已处理包数": "Processed packets",
    "过滤的包数": "Filtered packets",
    "丢弃的包数": "Dropped packets",
    "错误包数": "Error packets",
    "获取成功处理率": "Get success processing rate",
    "获取过滤率": "Get filter rate",
    "处理指标数据": "Processing metrics data",
    "已处理文件数": "Processed files",
    "总文件数": "Total files",
    "不能超过总文件数": "Cannot exceed total files",
    "获取完成率": "Get completion rate",
    "时间统计数据": "Time statistics data",
    "开始时间": "Start time",
    "处理耗时": "Processing duration",
    "毫秒": "milliseconds",
    "获取格式化的耗时字符串": "Get formatted duration string",
    "获取处理速度": "Get processing speed",
    "包": "packets",
    "秒": "seconds",
    "文件处理结果数据": "File processing result data",
    "文件名": "Filename",
    "步骤处理结果": "Step processing results",
    "处理时间戳": "Processing timestamp",
    "处理状态": "Processing status",
    "无效的状态值": "Invalid status value",
    "有效值": "Valid values",
    "映射数据": "Mapping data",
    "全局": "Global",
    "映射": "mapping",
    "按子目录的报告": "Reports by subdirectory",
    "获取映射数量": "Get mapping count",
    "添加新的映射": "Add new mapping",
    "获取指定子目录的报告": "Get report for specified subdirectory",
    "处理状态数据": "Processing status data",
    "当前处理文件": "Current processing file",
    "已计数文件的子目录": "Subdirectories with counted files",
    "已计数包的子目录": "Subdirectories with counted packets",
    "已打印摘要头的集合": "Set of printed summary headers",
    "完整的统计数据模型": "Complete statistics data model",
    "处理指标": "Processing metrics",
    "时间统计": "Time statistics",
    "文件结果": "File results",
    "步骤结果": "Step results",
    "获取仪表盘摘要数据": "Get dashboard summary data",
    "获取完整的处理摘要": "Get complete processing summary",
    "重置所有统计数据": "Reset all statistics data",
    "检查处理是否完成": "Check if processing is complete",

    # 报告数据模型
    "报告数据模型": "Report data model",
    "定义各种报告的数据结构": "Defines data structures for various reports",
    "报告类型": "Report type",
    "摘要报告": "Summary report",
    "详细报告": "Detailed report",
    "进度报告": "Progress report",
    "错误报告": "Error report",
    "性能报告": "Performance report",
    "报告格式": "Report format",
    "报告段落": "Report section",
    "段落标题": "Section title",
    "段落内容": "Section content",
    "标题级别": "Title level",
    "段落元数据": "Section metadata",
    "处理摘要数据": "Processing summary data",
    "已完成文件数": "Completed files",
    "失败文件数": "Failed files",
    "跳过文件数": "Skipped files",
    "总处理包数": "Total processed packets",
    "成功率": "Success rate",
    "步骤统计信息": "Step statistics information",
    "步骤名称": "Step name",
    "总执行次数": "Total executions",
    "成功执行次数": "Successful executions",
    "失败执行次数": "Failed executions",
    "平均执行时间": "Average execution time",
    "获取成功率": "Get success rate",
    "错误摘要": "Error summary",
    "总错误数": "Total errors",
    "错误类型统计": "Error type statistics",
    "严重错误数": "Critical errors",
    "可恢复错误数": "Recoverable errors",
    "最常见错误": "Most common error",
    "添加错误统计": "Add error statistics",
    "更新最常见错误": "Update most common error",
    "性能指标": "Performance metrics",
    "每分钟处理文件数": "Files per minute",
    "每秒处理包数": "Packets per second",
    "吞吐量": "Throughput",
    "平均文件大小": "Average file size",
    "峰值内存使用": "Peak memory usage",
    "使用率": "Usage rate",
    "计算性能指标": "Calculate performance metrics",
    "报告元数据": "Report metadata",
    "生成时间": "Generation time",
    "生成者": "Generator",
    "报告版本": "Report version",
    "报告": "Report",
    "报告标签": "Report tags",
    "自定义字段": "Custom fields",
    "完整报告数据模型": "Complete report data model",
    "报告元数据": "Report metadata",
    "核心数据": "Core data",
    "处理摘要": "Processing summary",
    "详细数据": "Detailed data",
    "文件结果详情": "File result details",
    "配置和上下文": "Configuration and context",
    "处理配置": "Processing configuration",
    "环境信息": "Environment information",
    "添加报告段落": "Add report section",
    "添加步骤统计": "Add step statistics",
    "添加文件结果": "Add file result",
    "获取格式化的报告内容": "Get formatted report content",
    "格式化为文本": "Format as text",
    "格式化为": "Format as",
    "格式化为Markdown": "Format as Markdown",
    "项目": "Item",
    "数值": "Value",
    "处理报告": "Processing report",
    "从统计数据创建报告": "Create report from statistics data",
    "需要从文件结果中计算": "Need to calculate from file results",
}

def clean_chinese_content(file_path):
    """清理文件中的中文内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 应用翻译映射
        for chinese, english in TRANSLATIONS.items():
            content = content.replace(chinese, english)
        
        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated: {file_path}")
            return True
        else:
            print(f"⏭️  No changes: {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def main():
    """主函数"""
    # 需要处理的文件列表
    files_to_process = [
        # 服务层文件
        "src/pktmask/services/progress_service.py",
        "src/pktmask/services/report_service.py",
        "src/pktmask/services/output_service.py",

        # 数据模型文件
        "src/pktmask/domain/models/__init__.py",
        "src/pktmask/domain/models/statistics_data.py",
        "src/pktmask/domain/models/report_data.py",
        "src/pktmask/domain/models/step_result_data.py",
        "src/pktmask/domain/models/file_processing_data.py",
        "src/pktmask/domain/__init__.py",

        # 基础设施文件
        "src/pktmask/infrastructure/logging/__init__.py",
        "src/pktmask/infrastructure/logging/logger.py",

        # 配置文件
        "config/__init__.py",
        "config/naming_aliases.yaml",
        "config/app/__init__.py",

        # 脚本文件
        "run_tests.py",
        "test_suite.py",
        "pktmask_launcher.py",
        "PktMask-Windows.spec",
        "pyproject.toml",
    ]
    
    updated_count = 0
    total_count = len(files_to_process)
    
    print("🚀 开始批量清理中文内容...")
    print("=" * 60)
    
    for file_path in files_to_process:
        if os.path.exists(file_path):
            if clean_chinese_content(file_path):
                updated_count += 1
        else:
            print(f"⚠️  File not found: {file_path}")
    
    print("=" * 60)
    print(f"📊 处理完成: {updated_count}/{total_count} 个文件已更新")

if __name__ == "__main__":
    main()
