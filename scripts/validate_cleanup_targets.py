#!/usr/bin/env python3
"""
废弃代码清理目标验证脚本
验证哪些代码真正未被使用，可以安全清理

基于REVISED_DEPRECATED_CODE_CLEANUP_ACTION_PLAN.md制定
"""

import os
import re
import subprocess
import sys
from pathlib import Path

def run_grep_search(pattern, directory, exclude_dirs=None, include_pattern="*.py"):
    """运行grep搜索并返回结果"""
    cmd = ['grep', '-r', '--include=' + include_pattern, pattern, directory]
    
    if exclude_dirs:
        for exclude_dir in exclude_dirs:
            cmd.extend(['--exclude-dir', exclude_dir])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError:
        print("❌ grep命令未找到，请确保系统已安装grep")
        return False, "", "grep not found"

def check_trim_module_usage():
    """检查trim模块的使用情况"""
    print("🔍 检查trim模块使用情况...")
    
    # 检查trim模块是否存在
    trim_dir = Path("src/pktmask/core/trim")
    if not trim_dir.exists():
        print("ℹ️ trim模块目录不存在")
        return True, "不存在"
    
    # 搜索trim模块的导入
    patterns_to_check = [
        r'from.*\.trim',
        r'import.*trim',
        r'pktmask\.core\.trim'
    ]
    
    usage_found = False
    for pattern in patterns_to_check:
        found, stdout, stderr = run_grep_search(pattern, 'src/', exclude_dirs=['trim'])
        if found:
            print(f"❌ 发现trim模块使用 (模式: {pattern}):")
            print(stdout[:500] + ("..." if len(stdout) > 500 else ""))
            usage_found = True
    
    if not usage_found:
        print("✅ trim模块未被使用，可以安全删除")
        
        # 额外检查：统计trim模块的代码量
        trim_files = list(trim_dir.rglob("*.py"))
        total_lines = 0
        for file_path in trim_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    total_lines += len(f.readlines())
            except Exception:
                pass
        
        print(f"📊 trim模块统计: {len(trim_files)}个文件, 约{total_lines}行代码")
        return True, f"{len(trim_files)}个文件, {total_lines}行"
    
    return False, "被使用"

def check_exception_usage():
    """检查异常类的使用情况"""
    print("\n🔍 检查异常类使用情况...")
    
    # 首先检查异常文件是否存在
    exception_file = Path("src/pktmask/adapters/adapter_exceptions.py")
    if not exception_file.exists():
        print("ℹ️ adapter_exceptions.py文件不存在")
        return []
    
    # 读取异常文件内容，提取所有异常类名
    try:
        with open(exception_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式提取异常类定义
        exception_classes = re.findall(r'class\s+(\w+Error?)\s*\(', content)
        print(f"📋 发现异常类: {exception_classes}")
        
    except Exception as e:
        print(f"❌ 读取异常文件失败: {e}")
        return []
    
    unused_exceptions = []
    for exc_class in exception_classes:
        # 跳过基础异常类
        if exc_class in ['AdapterError']:
            continue
            
        found, stdout, stderr = run_grep_search(exc_class, 'src/', exclude_dirs=['adapters'])
        
        if not found:
            unused_exceptions.append(exc_class)
            print(f"✅ {exc_class} 未被使用")
        else:
            print(f"❌ {exc_class} 被使用:")
            # 只显示前几行结果
            lines = stdout.strip().split('\n')[:3]
            for line in lines:
                print(f"   {line}")
            if len(stdout.strip().split('\n')) > 3:
                print("   ...")
    
    print(f"📊 未使用异常类总数: {len(unused_exceptions)}")
    return unused_exceptions

def check_app_controller_usage():
    """检查AppController的使用情况"""
    print("\n🔍 检查AppController使用情况...")
    
    # 检查AppController文件是否存在
    app_controller_file = Path("src/pktmask/gui/core/app_controller.py")
    if not app_controller_file.exists():
        print("ℹ️ AppController文件不存在")
        return True, "不存在"
    
    # 搜索AppController的使用
    patterns_to_check = [
        'AppController',
        'app_controller',
        'from.*app_controller',
        'import.*AppController'
    ]
    
    usage_found = False
    for pattern in patterns_to_check:
        found, stdout, stderr = run_grep_search(pattern, 'src/', exclude_dirs=['core'])
        if found:
            print(f"❌ 发现AppController使用 (模式: {pattern}):")
            lines = stdout.strip().split('\n')[:5]
            for line in lines:
                print(f"   {line}")
            if len(stdout.strip().split('\n')) > 5:
                print("   ...")
            usage_found = True
    
    if not usage_found:
        print("✅ AppController未被主程序使用")
        
        # 统计AppController代码量
        try:
            with open(app_controller_file, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
            print(f"📊 AppController统计: {lines}行代码")
            return True, f"{lines}行"
        except Exception:
            return True, "未知大小"
    
    return False, "被使用"

def check_simplified_main_window():
    """检查SimplifiedMainWindow是否存在"""
    print("\n🔍 检查SimplifiedMainWindow...")
    
    simplified_window_file = Path("src/pktmask/gui/simplified_main_window.py")
    if simplified_window_file.exists():
        print("❌ SimplifiedMainWindow文件存在，需要评估")
        return False, "存在"
    else:
        print("✅ SimplifiedMainWindow文件不存在")
        return True, "不存在"

def generate_cleanup_report(results):
    """生成清理报告"""
    print("\n" + "="*60)
    print("📋 废弃代码清理目标验证报告")
    print("="*60)
    
    total_cleanable_items = 0
    estimated_lines_saved = 0
    
    print("\n🎯 清理目标状态:")
    
    # Trim模块
    trim_safe, trim_info = results['trim']
    if trim_safe:
        print(f"✅ Trim模块: 可安全删除 ({trim_info})")
        total_cleanable_items += 1
        if "行" in trim_info:
            try:
                lines = int(re.search(r'(\d+)行', trim_info).group(1))
                estimated_lines_saved += lines
            except:
                pass
    else:
        print(f"❌ Trim模块: 不可删除 ({trim_info})")
    
    # 异常类
    unused_exceptions = results['exceptions']
    if unused_exceptions:
        print(f"✅ 未使用异常类: {len(unused_exceptions)}个可删除")
        print(f"   {', '.join(unused_exceptions)}")
        total_cleanable_items += len(unused_exceptions)
        estimated_lines_saved += len(unused_exceptions) * 5  # 估算每个异常类5行
    else:
        print("❌ 异常类: 全部被使用，不可删除")
    
    # AppController
    app_controller_safe, app_controller_info = results['app_controller']
    if app_controller_safe:
        print(f"✅ AppController: 可安全删除 ({app_controller_info})")
        total_cleanable_items += 1
        if "行" in app_controller_info:
            try:
                lines = int(re.search(r'(\d+)行', app_controller_info).group(1))
                estimated_lines_saved += lines
            except:
                pass
    else:
        print(f"❌ AppController: 不可删除 ({app_controller_info})")
    
    # SimplifiedMainWindow
    simplified_safe, simplified_info = results['simplified']
    if not simplified_safe:
        print(f"⚠️ SimplifiedMainWindow: 需要评估 ({simplified_info})")
    else:
        print(f"✅ SimplifiedMainWindow: 已不存在")
    
    print(f"\n📊 清理潜力:")
    print(f"- 可清理项目: {total_cleanable_items}个")
    print(f"- 预估节省代码行数: {estimated_lines_saved}行")
    print(f"- 风险等级: {'低风险' if total_cleanable_items > 0 else '无需清理'}")
    
    return total_cleanable_items > 0

def main():
    """主函数"""
    print("🚀 PktMask废弃代码清理目标验证")
    print("基于修正版清理计划 (REVISED_DEPRECATED_CODE_CLEANUP_ACTION_PLAN.md)")
    print("="*60)
    
    # 检查当前工作目录
    if not Path("src/pktmask").exists():
        print("❌ 错误: 请在PktMask项目根目录运行此脚本")
        sys.exit(1)
    
    # 执行各项检查
    results = {}
    
    try:
        results['trim'] = check_trim_module_usage()
        results['exceptions'] = check_exception_usage()
        results['app_controller'] = check_app_controller_usage()
        results['simplified'] = check_simplified_main_window()
        
        # 生成报告
        has_cleanup_targets = generate_cleanup_report(results)
        
        if has_cleanup_targets:
            print("\n✅ 验证完成: 发现可安全清理的废弃代码")
            print("💡 建议: 可以继续执行清理操作")
        else:
            print("\n✅ 验证完成: 未发现需要清理的废弃代码")
            print("💡 建议: 当前代码库状态良好，无需清理")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
