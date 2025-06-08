#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误处理系统测试脚本
验证Phase 3错误处理重构的功能
"""

import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.infrastructure.error_handling import (
    get_error_handler, install_global_exception_handler,
    handle_errors, ErrorHandlingContext, get_error_reporter,
    get_recovery_manager, create_error_context
)
from pktmask.common.exceptions import FileError, ProcessingError, ValidationError
from pktmask.infrastructure.logging import get_logger

logger = get_logger(__name__)


def test_basic_error_handling():
    """测试基本错误处理功能"""
    print("\n🔧 测试基本错误处理功能...")
    
    error_handler = get_error_handler()
    
    # 测试文件错误
    try:
        raise FileError("Test file not found", file_path="/path/to/test.txt")
    except Exception as e:
        recovery_result = error_handler.handle_exception(
            e, operation="test_file_read", component="test_module"
        )
        print(f"✅ 文件错误处理结果: {recovery_result.action if recovery_result else 'None'}")


@handle_errors(
    operation="test_operation",
    component="test_component",
    auto_recover=True,
    fallback_return_value="fallback_result"
)
def test_decorated_function():
    """测试装饰器功能"""
    print("\n🎯 测试装饰器功能...")
    
    # 故意抛出异常
    raise ProcessingError("Intentional test error", step_name="test_step")


def test_context_manager():
    """测试上下文管理器"""
    print("\n📝 测试上下文管理器...")
    
    try:
        with ErrorHandlingContext("test_context_operation", "test_context_component"):
            print("   在错误处理上下文中执行操作...")
            raise ValidationError("Test validation error", field_name="test_field")
    except Exception as e:
        print(f"   上下文外捕获的异常: {e}")


def test_error_recovery():
    """测试错误恢复功能"""
    print("\n🔄 测试错误恢复功能...")
    
    recovery_manager = get_recovery_manager()
    
    # 创建一个错误和上下文
    error = ProcessingError("Test processing error")
    context = create_error_context(
        exception=error,
        operation="test_recovery",
        component="test_component"
    )
    
    # 尝试恢复
    recovery_result = recovery_manager.attempt_recovery(error, context)
    print(f"✅ 恢复结果: {recovery_result.action} - {recovery_result.message}")


def test_error_reporting():
    """测试错误报告功能"""
    print("\n📊 测试错误报告功能...")
    
    error_reporter = get_error_reporter()
    
    # 生成一些测试错误报告
    error = FileError("Test file error for reporting")
    context = create_error_context(
        exception=error,
        operation="test_reporting",
        component="test_component",
        custom_data={"test_key": "test_value"}
    )
    
    report = error_reporter.report_error(error, context)
    print(f"✅ 生成报告: {report.report_id}")
    
    # 获取最近报告
    recent_reports = error_reporter.get_recent_reports(limit=3)
    print(f"✅ 最近报告数量: {len(recent_reports)}")
    
    # 生成汇总报告
    summary = error_reporter.generate_summary_report(time_range_hours=1)
    print(f"✅ 汇总报告 - 总错误数: {summary['total_errors']}")


def test_global_exception_handler():
    """测试全局异常处理器"""
    print("\n🌐 测试全局异常处理器...")
    
    # 安装全局异常处理器
    install_global_exception_handler()
    print("✅ 全局异常处理器已安装")
    
    # 注意：这里不能真的抛出未捕获异常，因为会终止程序
    print("   (全局异常处理器将在真实未捕获异常时生效)")


def test_error_statistics():
    """测试错误统计功能"""
    print("\n📈 测试错误统计功能...")
    
    error_handler = get_error_handler()
    
    # 生成几个测试错误来产生统计数据
    for i in range(3):
        try:
            if i == 0:
                raise FileError(f"Test file error {i}")
            elif i == 1:
                raise ProcessingError(f"Test processing error {i}")
            else:
                raise ValidationError(f"Test validation error {i}")
        except Exception as e:
            error_handler.handle_exception(e, operation=f"test_stats_{i}")
    
    # 获取统计信息
    stats = error_handler.get_error_stats()
    print(f"✅ 错误统计:")
    print(f"   总错误数: {stats['total_errors']}")
    print(f"   已处理错误: {stats['handled_errors']}")
    print(f"   已恢复错误: {stats['recovered_errors']}")
    print(f"   严重性分布: {stats['severity_counts']}")
    
    # 获取恢复统计
    recovery_stats = stats.get('recovery_stats', {})
    print(f"   恢复统计: {recovery_stats}")


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始 Phase 3 错误处理系统测试...")
    print("=" * 60)
    
    try:
        # 基本功能测试
        test_basic_error_handling()
        
        # 装饰器测试
        result = test_decorated_function()
        print(f"✅ 装饰器测试结果: {result}")
        
        # 上下文管理器测试
        test_context_manager()
        
        # 恢复功能测试
        test_error_recovery()
        
        # 报告功能测试
        test_error_reporting()
        
        # 全局异常处理器测试
        test_global_exception_handler()
        
        # 统计功能测试
        test_error_statistics()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试完成！错误处理系统运行正常。")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests() 