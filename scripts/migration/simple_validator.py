#!/usr/bin/env python3
"""
PktMask目录结构迁移简化验证脚本

用法: python3 scripts/migration/simple_validator.py
"""

import os
import sys
from pathlib import Path

def main():
    project_root = Path(__file__).parent.parent.parent
    print(f"🔍 验证PktMask目录结构迁移...")
    print(f"📁 项目根目录: {project_root}")
    
    # 检查必需目录
    required_dirs = [
        "config/default", "config/samples", "config/production", "config/test",
        "scripts/build", "scripts/test", "scripts/validation", "scripts/migration",
        "docs/reports", "output/reports"
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if not (project_root / dir_path).exists():
            missing_dirs.append(dir_path)
    
    # 检查关键文件是否迁移
    expected_files = {
        "config/default/mask_config.yaml": "mask_config.yaml",
        "config/samples/demo_recipe.json": "demo_recipe.json",
        "scripts/test/manual_tcp_masker_test.py": "manual_tcp_masker_test.py",
        "scripts/build/build_app.sh": "build_app.sh"
    }
    
    missing_files = []
    for new_path, old_name in expected_files.items():
        if not (project_root / new_path).exists():
            missing_files.append(f"{old_name} -> {new_path}")
    
    # 输出结果
    if not missing_dirs and not missing_files:
        print("✅ 迁移验证通过！")
        return True
    else:
        print("❌ 发现问题:")
        if missing_dirs:
            print(f"  缺失目录: {missing_dirs}")
        if missing_files:
            print(f"  未迁移文件: {missing_files}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 