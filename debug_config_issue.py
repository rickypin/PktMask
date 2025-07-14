#!/usr/bin/env python3
"""
调试GUI配置传递问题的脚本
"""

import json
import sys
from pathlib import Path

def test_gui_config_chain():
    """测试GUI配置传递链条"""
    print("=== GUI配置传递链条测试 ===")
    
    # 步骤1: 模拟GUI的build_pipeline_config
    from pktmask.services.pipeline_service import build_pipeline_config
    
    gui_pipeline_config = build_pipeline_config(
        enable_anon=False,
        enable_dedup=False,
        enable_mask=True
    )
    
    print("1. GUI Pipeline配置:")
    print(json.dumps(gui_pipeline_config, indent=2))
    
    # 步骤2: 提取mask配置
    mask_config = gui_pipeline_config.get("mask", {})
    marker_config = mask_config.get("marker_config", {})
    
    print("\n2. Marker配置:")
    print(json.dumps(marker_config, indent=2))
    
    # 步骤3: 测试TLS标记器如何解析这个配置
    from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
    
    print("\n3. 创建TLS标记器并检查preserve_config:")
    try:
        tls_marker = TLSProtocolMarker(marker_config)
        print(f"TLS标记器的preserve_config: {tls_marker.preserve_config}")
        
        # 关键检查：application_data是否为False
        app_data_preserve = tls_marker.preserve_config.get('application_data', True)
        print(f"application_data保留设置: {app_data_preserve}")
        print(f"预期行为: TLS-23应该被{'保留' if app_data_preserve else '掩码'}")
        
        if app_data_preserve:
            print("❌ 错误：TLS-23会被完全保留，而不是掩码！")
            return False
        else:
            print("✅ 正确：TLS-23会被掩码")
            return True
            
    except Exception as e:
        print(f"❌ 创建TLS标记器失败: {e}")
        return False

def test_script_config_chain():
    """测试脚本配置传递链条"""
    print("\n=== 脚本配置传递链条测试 ===")
    
    # 模拟脚本的配置
    script_config = {
        "protocol": "tls",
        "mode": "enhanced",
        "marker_config": {
            "tls": {
                "preserve_handshake": True,
                "preserve_application_data": False
            }
        },
        "masker_config": {
            "preserve_ratio": 0.3
        }
    }
    
    print("1. 脚本配置:")
    print(json.dumps(script_config, indent=2))
    
    # 测试TLS标记器如何解析这个配置
    from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
    
    marker_config = script_config.get("marker_config", {})
    print("\n2. Marker配置:")
    print(json.dumps(marker_config, indent=2))
    
    print("\n3. 创建TLS标记器并检查preserve_config:")
    try:
        tls_marker = TLSProtocolMarker(marker_config)
        print(f"TLS标记器的preserve_config: {tls_marker.preserve_config}")
        
        # 关键检查：application_data是否为False
        app_data_preserve = tls_marker.preserve_config.get('application_data', True)
        print(f"application_data保留设置: {app_data_preserve}")
        print(f"预期行为: TLS-23应该被{'保留' if app_data_preserve else '掩码'}")
        
        if app_data_preserve:
            print("❌ 错误：TLS-23会被完全保留，而不是掩码！")
            return False
        else:
            print("✅ 正确：TLS-23会被掩码")
            return True
            
    except Exception as e:
        print(f"❌ 创建TLS标记器失败: {e}")
        return False

def main():
    """主函数"""
    print("调试GUI与脚本配置传递差异\n")
    
    gui_ok = test_gui_config_chain()
    script_ok = test_script_config_chain()
    
    print(f"\n=== 总结 ===")
    print(f"GUI配置: {'✅ 正确' if gui_ok else '❌ 错误'}")
    print(f"脚本配置: {'✅ 正确' if script_ok else '❌ 错误'}")
    
    if not gui_ok:
        print("\n🔧 需要修复GUI配置传递逻辑")
        print("问题：GUI的marker_config结构与TLS标记器期望的不匹配")
        print("解决方案：修改build_pipeline_config函数中的marker_config结构")
    
    return gui_ok and script_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
