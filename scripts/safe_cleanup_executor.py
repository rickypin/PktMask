#!/usr/bin/env python3
"""
安全废弃代码清理执行器
只清理经过验证确认安全的代码

基于REVISED_DEPRECATED_CODE_CLEANUP_ACTION_PLAN.md制定
"""

import os
import shutil
import sys
import re
from pathlib import Path
from datetime import datetime

def create_backup():
    """创建清理前备份"""
    print("📦 创建清理前备份...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(f"backup_before_cleanup_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    
    # 需要备份的文件和目录
    backup_targets = [
        "src/pktmask/adapters/adapter_exceptions.py",
        "src/pktmask/gui/core/app_controller.py",
        "src/pktmask/core/trim/"
    ]
    
    backed_up_files = []
    for target in backup_targets:
        target_path = Path(target)
        if target_path.exists():
            if target_path.is_file():
                backup_file = backup_dir / target_path.name
                shutil.copy2(target_path, backup_file)
                backed_up_files.append(target)
                print(f"✅ 备份文件: {target}")
            elif target_path.is_dir():
                backup_subdir = backup_dir / target_path.name
                shutil.copytree(target_path, backup_subdir)
                backed_up_files.append(target)
                print(f"✅ 备份目录: {target}")
        else:
            print(f"ℹ️ 跳过不存在的目标: {target}")
    
    if backed_up_files:
        print(f"📁 备份已保存到: {backup_dir}")
        return backup_dir
    else:
        print("ℹ️ 没有文件需要备份")
        backup_dir.rmdir()  # 删除空的备份目录
        return None

def cleanup_trim_module():
    """清理trim模块"""
    print("\n🗑️ 清理trim模块...")
    
    trim_dir = Path("src/pktmask/core/trim")
    if not trim_dir.exists():
        print("ℹ️ trim模块目录不存在，跳过")
        return True
    
    try:
        # 统计要删除的内容
        trim_files = list(trim_dir.rglob("*.py"))
        total_lines = 0
        for file_path in trim_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    total_lines += len(f.readlines())
            except Exception:
                pass
        
        print(f"📊 即将删除: {len(trim_files)}个Python文件, 约{total_lines}行代码")
        
        # 确认删除
        response = input("❓ 确认删除trim模块? (y/N): ").strip().lower()
        if response == 'y':
            shutil.rmtree(trim_dir)
            print("✅ trim模块已删除")
            return True
        else:
            print("⏭️ 跳过trim模块删除")
            return False
            
    except Exception as e:
        print(f"❌ 删除trim模块失败: {e}")
        return False

def cleanup_unused_exceptions(unused_exceptions):
    """清理未使用的异常类"""
    if not unused_exceptions:
        print("\nℹ️ 没有未使用的异常类需要清理")
        return True
    
    print(f"\n🗑️ 清理 {len(unused_exceptions)} 个未使用的异常类...")
    print(f"目标异常类: {', '.join(unused_exceptions)}")
    
    exception_file = Path("src/pktmask/adapters/adapter_exceptions.py")
    if not exception_file.exists():
        print("❌ 异常文件不存在")
        return False
    
    try:
        # 读取原文件
        with open(exception_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_lines = len(content.splitlines())
        
        # 为每个未使用的异常类创建删除模式
        for exc_class in unused_exceptions:
            # 匹配异常类定义及其文档字符串
            pattern = rf'class {exc_class}\([^)]*\):.*?(?=\n\nclass|\n\n\n|\Z)'
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        # 清理多余的空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        new_lines = len(content.splitlines())
        lines_removed = original_lines - new_lines
        
        print(f"📊 预计删除 {lines_removed} 行代码")
        
        # 确认修改
        response = input("❓ 确认删除这些异常类? (y/N): ").strip().lower()
        if response == 'y':
            # 写入修改后的内容
            with open(exception_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 已删除 {len(unused_exceptions)} 个异常类")
            return True
        else:
            print("⏭️ 跳过异常类删除")
            return False
            
    except Exception as e:
        print(f"❌ 清理异常类失败: {e}")
        return False

def cleanup_app_controller():
    """清理未使用的AppController"""
    print("\n🗑️ 清理AppController...")
    
    app_controller_file = Path("src/pktmask/gui/core/app_controller.py")
    if not app_controller_file.exists():
        print("ℹ️ AppController文件不存在，跳过")
        return True
    
    try:
        # 统计文件大小
        with open(app_controller_file, 'r', encoding='utf-8') as f:
            lines = len(f.readlines())
        
        print(f"📊 即将删除: {lines}行代码")
        
        # 确认删除
        response = input("❓ 确认删除AppController文件? (y/N): ").strip().lower()
        if response == 'y':
            app_controller_file.unlink()
            print("✅ AppController已删除")
            
            # 检查是否需要删除空的core目录
            core_dir = app_controller_file.parent
            if core_dir.exists() and not any(core_dir.iterdir()):
                core_dir.rmdir()
                print("✅ 已删除空的core目录")
            
            return True
        else:
            print("⏭️ 跳过AppController删除")
            return False
            
    except Exception as e:
        print(f"❌ 删除AppController失败: {e}")
        return False

def verify_cleanup_safety():
    """验证清理操作的安全性"""
    print("🔍 验证清理操作安全性...")
    
    # 检查是否在正确的目录
    if not Path("src/pktmask").exists():
        print("❌ 错误: 请在PktMask项目根目录运行此脚本")
        return False
    
    # 检查是否有未提交的Git更改
    try:
        import subprocess
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            print("⚠️ 警告: 检测到未提交的Git更改")
            print("建议先提交或暂存当前更改")
            response = input("❓ 是否继续? (y/N): ").strip().lower()
            if response != 'y':
                return False
    except FileNotFoundError:
        print("ℹ️ Git未安装，跳过版本控制检查")
    
    return True

def run_post_cleanup_validation():
    """运行清理后验证"""
    print("\n🧪 运行清理后验证...")
    
    try:
        # 测试关键模块导入
        test_modules = [
            'pktmask.core.pipeline.executor',
            'pktmask.core.processors.registry',
            'pktmask.gui.main_window'
        ]
        
        for module in test_modules:
            try:
                __import__(module)
                print(f"✅ {module} 导入成功")
            except ImportError as e:
                print(f"❌ {module} 导入失败: {e}")
                return False
        
        print("✅ 基础验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        return False

def main():
    """主函数"""
    print("🚀 PktMask安全废弃代码清理执行器")
    print("基于修正版清理计划 (REVISED_DEPRECATED_CODE_CLEANUP_ACTION_PLAN.md)")
    print("="*60)
    
    # 安全性验证
    if not verify_cleanup_safety():
        print("❌ 安全性验证失败，退出清理")
        return 1
    
    # 提示用户先运行验证脚本
    print("\n⚠️ 重要提醒:")
    print("请确保已运行 'python scripts/validate_cleanup_targets.py' 验证清理目标")
    response = input("❓ 是否已运行验证脚本? (y/N): ").strip().lower()
    if response != 'y':
        print("💡 请先运行验证脚本: python scripts/validate_cleanup_targets.py")
        return 1
    
    # 创建备份
    backup_dir = create_backup()
    
    # 获取用户确认的清理目标
    print("\n📋 请确认要清理的目标:")
    
    cleanup_trim = input("❓ 清理trim模块? (y/N): ").strip().lower() == 'y'
    
    unused_exceptions_input = input("❓ 输入要删除的异常类名 (用逗号分隔，留空跳过): ").strip()
    unused_exceptions = [exc.strip() for exc in unused_exceptions_input.split(',') if exc.strip()]
    
    cleanup_app_controller_flag = input("❓ 清理AppController? (y/N): ").strip().lower() == 'y'
    
    # 执行清理操作
    cleanup_results = []
    
    if cleanup_trim:
        result = cleanup_trim_module()
        cleanup_results.append(("Trim模块", result))
    
    if unused_exceptions:
        result = cleanup_unused_exceptions(unused_exceptions)
        cleanup_results.append(("异常类", result))
    
    if cleanup_app_controller_flag:
        result = cleanup_app_controller()
        cleanup_results.append(("AppController", result))
    
    # 运行清理后验证
    validation_passed = run_post_cleanup_validation()
    
    # 生成清理报告
    print("\n" + "="*60)
    print("📋 清理操作报告")
    print("="*60)
    
    for operation, success in cleanup_results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{operation}: {status}")
    
    print(f"清理后验证: {'✅ 通过' if validation_passed else '❌ 失败'}")
    
    if backup_dir:
        print(f"备份位置: {backup_dir}")
    
    if all(result for _, result in cleanup_results) and validation_passed:
        print("\n🎉 清理操作成功完成!")
        return 0
    else:
        print("\n⚠️ 清理操作部分失败，请检查错误信息")
        if backup_dir:
            print(f"如需回滚，请使用备份: {backup_dir}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
