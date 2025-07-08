#!/usr/bin/env python3
"""
适配器自动迁移脚本

自动化执行适配器迁移任务，包括：
1. 移动文件到新位置
2. 更新导入路径
3. 重命名类（如需要）
4. 创建向后兼容的代理文件
"""

import os
import shutil
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

# 适配器迁移映射
ADAPTER_MIGRATIONS = [
    # (原文件路径, 新文件路径, 是否需要重命名)
    ("src/pktmask/core/adapters/processor_adapter.py", 
     "src/pktmask/adapters/processor_adapter.py", False),
    
    ("src/pktmask/core/encapsulation/adapter.py", 
     "src/pktmask/adapters/encapsulation_adapter.py", True),
    
    ("src/pktmask/domain/adapters/event_adapter.py", 
     "src/pktmask/adapters/event_adapter.py", False),
    
    ("src/pktmask/domain/adapters/statistics_adapter.py", 
     "src/pktmask/adapters/statistics_adapter.py", False),
    
    ("src/pktmask/stages/adapters/anon_compat.py", 
     "src/pktmask/adapters/compatibility/anon_compat.py", False),
    
    ("src/pktmask/stages/adapters/dedup_compat.py", 
     "src/pktmask/adapters/compatibility/dedup_compat.py", False),
]

# 导入路径映射
IMPORT_MAPPINGS = {
    "pktmask.core.adapters.processor_adapter": "pktmask.adapters.processor_adapter",
    "pktmask.core.encapsulation.adapter": "pktmask.adapters.encapsulation_adapter",
    "pktmask.domain.adapters.event_adapter": "pktmask.adapters.event_adapter",
    "pktmask.domain.adapters.statistics_adapter": "pktmask.adapters.statistics_adapter",
    "pktmask.stages.adapters.anon_compat": "pktmask.adapters.compatibility.anon_compat",
    "pktmask.stages.adapters.dedup_compat": "pktmask.adapters.compatibility.dedup_compat",
}

# 类名映射
CLASS_MAPPINGS = {
    "ProcessorAdapter": "ProcessorAdapter",
}


def create_proxy_file(old_path: Path, new_module: str) -> None:
    """创建向后兼容的代理文件"""
    module_parts = new_module.split('.')
    class_imports = []
    
    # 根据文件名推测可能的类名
    file_name = old_path.stem
    if file_name.endswith('_adapter'):
        class_name = ''.join(word.capitalize() for word in file_name.split('_'))
        class_imports.append(class_name)
    elif file_name.endswith('_compat'):
        class_name = ''.join(word.capitalize() for word in file_name.split('_'))
        class_imports.append(class_name)
    
    proxy_content = f'''"""
向后兼容代理文件

此文件用于保持向后兼容性。
请使用新的导入路径：{new_module}
"""

import warnings
from {new_module} import *

warnings.warn(
    f"导入路径 '{{__name__}}' 已废弃，"
    f"请使用 '{new_module}' 替代。"
    f"此兼容性支持将在 v2.0 中移除。",
    DeprecationWarning,
    stacklevel=2
)
'''
    
    old_path.write_text(proxy_content, encoding='utf-8')
    print(f"  创建代理文件: {old_path}")


def move_adapter_file(root_dir: Path, old_path: str, new_path: str, needs_rename: bool) -> bool:
    """移动适配器文件到新位置"""
    src = root_dir / old_path
    dst = root_dir / new_path
    
    if not src.exists():
        print(f"  ⚠️  源文件不存在: {src}")
        return False
    
    # 确保目标目录存在
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    # 复制文件到新位置
    shutil.copy2(src, dst)
    print(f"  ✅ 复制文件: {old_path} -> {new_path}")
    
    # 创建代理文件
    old_module = old_path.replace('src/', '').replace('.py', '').replace('/', '.')
    new_module = new_path.replace('src/', '').replace('.py', '').replace('/', '.')
    create_proxy_file(src, new_module)
    
    return True


def update_imports_in_file(file_path: Path, dry_run: bool = False) -> int:
    """更新文件中的导入路径"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = 0
        
        # 更新导入路径
        for old_import, new_import in IMPORT_MAPPINGS.items():
            # 匹配 from ... import 语句
            pattern1 = re.compile(rf'from\s+{re.escape(old_import)}\s+import')
            if pattern1.search(content):
                content = pattern1.sub(f'from {new_import} import', content)
                changes += 1
            
            # 匹配 import ... 语句
            pattern2 = re.compile(rf'import\s+{re.escape(old_import)}')
            if pattern2.search(content):
                content = pattern2.sub(f'import {new_import}', content)
                changes += 1
        
        # 更新类名（如果需要）
        for old_class, new_class in CLASS_MAPPINGS.items():
            if old_class in content:
                content = content.replace(old_class, new_class)
                changes += 1
        
        # 写回文件
        if changes > 0 and not dry_run:
            file_path.write_text(content, encoding='utf-8')
            print(f"  ✅ 更新 {file_path}: {changes} 处变更")
        elif changes > 0:
            print(f"  🔍 发现 {file_path}: {changes} 处需要变更")
        
        return changes
        
    except Exception as e:
        print(f"  ❌ 处理文件失败 {file_path}: {e}")
        return 0


def find_affected_files(root_dir: Path) -> List[Path]:
    """查找所有需要更新导入的文件"""
    affected_files = []
    
    for root, dirs, files in os.walk(root_dir):
        # 跳过不需要的目录
        dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', '.git', 'output'}]
        
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                # 快速检查文件是否包含需要更新的导入
                try:
                    content = file_path.read_text(encoding='utf-8')
                    for old_import in IMPORT_MAPPINGS:
                        if old_import in content:
                            affected_files.append(file_path)
                            break
                except:
                    pass
    
    return affected_files


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='适配器迁移脚本')
    parser.add_argument('--dry-run', action='store_true', help='仅显示将要执行的操作，不实际执行')
    parser.add_argument('--step', choices=['move', 'update', 'all'], default='all', 
                        help='执行的步骤：move-移动文件，update-更新导入，all-全部')
    args = parser.parse_args()
    
    root_dir = Path(__file__).parent.parent.parent
    
    print(f"{'🔍 模拟运行模式' if args.dry_run else '🚀 执行迁移'}")
    print("=" * 60)
    
    # 步骤1：移动适配器文件
    if args.step in ['move', 'all']:
        print("\n📁 步骤1：移动适配器文件")
        print("-" * 40)
        for old_path, new_path, needs_rename in ADAPTER_MIGRATIONS:
            if not args.dry_run:
                move_adapter_file(root_dir, old_path, new_path, needs_rename)
            else:
                print(f"  将移动: {old_path} -> {new_path}")
    
    # 步骤2：更新导入路径
    if args.step in ['update', 'all']:
        print("\n📝 步骤2：更新导入路径")
        print("-" * 40)
        
        # 查找受影响的文件
        print("查找需要更新的文件...")
        affected_files = find_affected_files(root_dir)
        print(f"找到 {len(affected_files)} 个文件需要更新")
        
        total_changes = 0
        for file_path in affected_files:
            changes = update_imports_in_file(file_path, dry_run=args.dry_run)
            total_changes += changes
        
        print(f"\n总计需要更新 {total_changes} 处导入")
    
    print("\n✅ 迁移准备完成！")
    
    if args.dry_run:
        print("\n💡 这是模拟运行，实际文件未被修改。")
        print("   要执行实际迁移，请运行不带 --dry-run 参数的命令。")


if __name__ == "__main__":
    main()
