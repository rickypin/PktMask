#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试清单验证问题
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def debug_manifest_validation():
    """调试清单验证问题"""
    try:
        from src.pktmask.algorithms.registry.plugin_marketplace import (
            PluginManifest, PluginValidator, PluginCategory, PluginLicense
        )
        
        print("🔍 调试清单验证问题")
        print("=" * 50)
        
        # 创建验证器
        validator = PluginValidator()
        
        # 有效清单
        valid_manifest = PluginManifest(
            name="valid_plugin",
            version="1.0.0",
            description="有效插件",
            author="Valid Author",
            author_email="valid@example.com"
        )
        
        print("验证有效清单:")
        print(f"  名称: {valid_manifest.name}")
        print(f"  版本: {valid_manifest.version}")
        print(f"  描述: {valid_manifest.description}")
        print(f"  作者: {valid_manifest.author}")
        print(f"  邮箱: {valid_manifest.author_email}")
        
        errors = validator.validate_manifest(valid_manifest)
        print(f"\n验证结果:")
        print(f"  错误数量: {len(errors)}")
        if errors:
            print(f"  错误列表:")
            for i, error in enumerate(errors, 1):
                print(f"    {i}. {error}")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_manifest_validation() 