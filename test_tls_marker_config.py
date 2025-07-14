#!/usr/bin/env python3
"""
直接测试TLSProtocolMarker的配置解析
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
script_dir = Path(__file__).parent.absolute()
src_path = script_dir / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

def test_tls_marker_config_parsing():
    """测试TLSProtocolMarker的配置解析"""
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        print("=== 测试TLSProtocolMarker配置解析 ===")
        
        # 测试GUI格式配置
        print("\n1. 测试GUI格式配置 (preserve结构)")
        gui_config = {
            "preserve": {
                "handshake": True,
                "application_data": False,
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True
            }
        }
        
        gui_marker = TLSProtocolMarker(gui_config)
        print(f"GUI配置解析结果: {gui_marker.preserve_config}")
        gui_app_data = gui_marker.preserve_config.get('application_data')
        print(f"GUI application_data设置: {gui_app_data}")
        
        # 测试脚本格式配置
        print("\n2. 测试脚本格式配置 (tls结构)")
        script_config = {
            "tls": {
                "preserve_handshake": True,
                "preserve_application_data": False
            }
        }
        
        script_marker = TLSProtocolMarker(script_config)
        print(f"脚本配置解析结果: {script_marker.preserve_config}")
        script_app_data = script_marker.preserve_config.get('application_data')
        print(f"脚本 application_data设置: {script_app_data}")
        
        # 对比结果
        print("\n3. 配置对比结果")
        print(f"GUI application_data: {gui_app_data}")
        print(f"脚本 application_data: {script_app_data}")
        
        if gui_app_data == script_app_data:
            print("✅ TLS-23配置一致！修复成功。")
            return True
        else:
            print("❌ TLS-23配置不一致！修复失败。")
            return False
            
    except ImportError as e:
        print(f"❌ 导入TLSProtocolMarker失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_default_config():
    """测试默认配置"""
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        print("\n=== 测试默认配置 ===")
        
        # 测试空配置
        empty_config = {}
        default_marker = TLSProtocolMarker(empty_config)
        print(f"默认配置: {default_marker.preserve_config}")
        default_app_data = default_marker.preserve_config.get('application_data')
        print(f"默认 application_data设置: {default_app_data}")
        
        return default_app_data == False  # 默认应该是False
        
    except Exception as e:
        print(f"❌ 测试默认配置失败: {e}")
        return False

def main():
    """主函数"""
    print("开始测试TLSProtocolMarker配置解析...")
    
    # 测试配置解析
    config_test_passed = test_tls_marker_config_parsing()
    
    # 测试默认配置
    default_test_passed = test_default_config()
    
    print(f"\n=== 测试总结 ===")
    print(f"配置解析测试: {'✅ 通过' if config_test_passed else '❌ 失败'}")
    print(f"默认配置测试: {'✅ 通过' if default_test_passed else '❌ 失败'}")
    
    overall_success = config_test_passed and default_test_passed
    
    if overall_success:
        print("\n🎉 所有测试通过！TLSProtocolMarker现在可以正确解析GUI和脚本的配置格式。")
        print("   这意味着GUI和脚本应该产生一致的TLS-23掩码行为。")
    else:
        print("\n❌ 测试失败，需要进一步调试。")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
