#!/usr/bin/env python3
"""
快速修复TCP载荷掩码器中的统计属性名问题
"""

import os
import re

def fix_stats_attributes():
    """修复统计属性名问题"""
    
    target_file = "src/pktmask/core/tcp_payload_masker/api/masker.py"
    
    if not os.path.exists(target_file):
        print(f"❌ 文件不存在: {target_file}")
        return False
    
    print(f"🔧 修复文件: {target_file}")
    
    # 读取文件
    with open(target_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 进行替换
    replacements = [
        ('masker.stats.processed_count', 'masker.stats.processed_packets'),
        ('masker.stats.modified_count', 'masker.stats.modified_packets'),
    ]
    
    modified = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f"  ✅ 替换: {old} -> {new}")
            modified = True
    
    if modified:
        # 写回文件
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  📄 文件已更新")
        return True
    else:
        print(f"  ⚠️ 无需修改")
        return False

def main():
    """主函数"""
    print("🚀 TCP载荷掩码器统计属性修复")
    print("=" * 40)
    
    success = fix_stats_attributes()
    
    if success:
        print("\n✅ 修复完成！现在可以重新测试API")
    else:
        print("\n⚠️ 修复完成或无需修改")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main()) 