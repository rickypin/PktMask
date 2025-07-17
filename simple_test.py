#!/usr/bin/env python3
"""简单测试脚本"""

import sys
import os
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_basic():
    """基本测试"""
    print("Python version:", sys.version)
    print("Current directory:", os.getcwd())
    
    # 测试 TShark 路径
    tshark_paths = [
        r'C:\Program Files\Wireshark\tshark.exe',
        r'C:\Program Files (x86)\Wireshark\tshark.exe',
    ]
    
    for path in tshark_paths:
        exists = Path(path).exists()
        print(f"TShark path {path}: {'EXISTS' if exists else 'NOT FOUND'}")
    
    # 测试导入
    try:
        from pktmask.config.settings import get_app_config
        print("✅ Config import successful")
        
        config = get_app_config()
        print(f"✅ Config loaded: {type(config)}")
        
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_basic()
