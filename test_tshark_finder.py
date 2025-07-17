#!/usr/bin/env python3
"""测试 TShark 查找功能"""

import sys
import os

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_tshark_finder():
    """测试 TShark 查找功能"""
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        # 创建一个简单的配置
        config = {
            'preserve': {
                'handshake': True,
                'application_data': False,
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
        # 创建 TLS marker 实例
        marker = TLSProtocolMarker(config)
        
        # 测试 TShark 查找
        print("Testing TShark finder...")
        tshark_path = marker._find_tshark_executable()
        print(f"Found TShark at: {tshark_path}")
        
        # 测试版本检查
        print("Testing TShark version check...")
        verified_path = marker._check_tshark_version(None)
        print(f"Verified TShark at: {verified_path}")
        
        print("✅ TShark finder test passed!")
        return True
        
    except Exception as e:
        print(f"❌ TShark finder test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_tshark_finder()
    sys.exit(0 if success else 1)
