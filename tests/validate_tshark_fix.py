#!/usr/bin/env python3
"""
简化的TShark修复验证脚本

此脚本专门验证NoneType错误修复的核心功能，
确保修复后的代码能够正确处理各种None值情况。
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.infrastructure.dependency.checker import DependencyChecker


def test_none_stdout_fix():
    """测试stdout为None的修复"""
    print("Testing None stdout fix...")
    
    checker = DependencyChecker()
    
    with patch('subprocess.run') as mock_run:
        # 模拟subprocess返回stdout=None的情况
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = None
        mock_proc.stderr = "some stderr"
        mock_run.return_value = mock_proc
        
        try:
            result = checker._check_protocol_support("/fake/tshark")
            
            # 验证不会抛出AttributeError
            assert not result['success'], "Should fail when stdout is None"
            assert "stdout is None" in result['error'], f"Expected 'stdout is None' in error, got: {result['error']}"
            print("✅ None stdout handling works correctly")
            return True
            
        except AttributeError as e:
            if "'NoneType' object has no attribute 'lower'" in str(e):
                print("❌ NoneType error still occurs!")
                return False
            else:
                raise


def test_empty_stdout_fix():
    """测试空stdout的修复"""
    print("Testing empty stdout fix...")
    
    checker = DependencyChecker()
    
    with patch('subprocess.run') as mock_run:
        # 模拟subprocess返回空stdout的情况
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc
        
        try:
            result = checker._check_protocol_support("/fake/tshark")
            
            assert not result['success'], "Should fail when stdout is empty"
            assert "empty output" in result['error'], f"Expected 'empty output' in error, got: {result['error']}"
            print("✅ Empty stdout handling works correctly")
            return True
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


def test_version_check_none_fix():
    """测试版本检查中None输出的修复"""
    print("Testing version check None output fix...")
    
    checker = DependencyChecker()
    
    with patch('subprocess.run') as mock_run:
        # 模拟subprocess返回stdout和stderr都为None
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = None
        mock_proc.stderr = None
        mock_run.return_value = mock_proc
        
        try:
            result = checker._check_tshark_version("/fake/tshark")
            
            assert not result['success'], "Should fail when both outputs are None"
            assert "no output" in result['error'], f"Expected 'no output' in error, got: {result['error']}"
            print("✅ Version check None output handling works correctly")
            return True
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


def test_json_check_none_fix():
    """测试JSON检查中None stderr的修复"""
    print("Testing JSON check None stderr fix...")
    
    checker = DependencyChecker()
    
    with patch('subprocess.run') as mock_run:
        # 模拟subprocess返回stderr=None
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = None
        mock_run.return_value = mock_proc
        
        try:
            result = checker._check_json_output("/fake/tshark")
            
            # 应该成功，因为没有错误信息
            assert result['success'], f"Should succeed when stderr is None, got error: {result.get('error')}"
            print("✅ JSON check None stderr handling works correctly")
            return True
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


def test_error_message_formatting():
    """测试错误消息格式化"""
    print("Testing error message formatting...")
    
    from pktmask.infrastructure.dependency.checker import DependencyResult, DependencyStatus
    
    checker = DependencyChecker()
    
    # 测试NoneType错误的特殊处理
    result = DependencyResult(
        name="tshark",
        status=DependencyStatus.EXECUTION_ERROR,
        path="/fake/path",
        version_found="4.2.0",
        error_message="Protocol support check failed: 'NoneType' object has no attribute 'lower'"
    )
    
    formatted = checker._format_error_message(result)
    
    if "Windows compatibility" in formatted and "known issue" in formatted:
        print("✅ Error message formatting works correctly")
        return True
    else:
        print(f"❌ Error message formatting failed: {formatted}")
        return False


def main():
    """运行所有验证测试"""
    print("=" * 60)
    print("PktMask TShark NoneType Error Fix Validation")
    print("=" * 60)
    
    tests = [
        test_none_stdout_fix,
        test_empty_stdout_fix,
        test_version_check_none_fix,
        test_json_check_none_fix,
        test_error_message_formatting
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The NoneType error fix is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
