#!/usr/bin/env python3
"""
测试中间结果检查点
验证 Stage 和 Marker 的创建过程
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
script_dir = Path(__file__).parent.absolute()
src_path = script_dir / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from config_comparison_tool import MiddlewareCheckpoint

def test_gui_config():
    """测试GUI配置"""
    print("=== 测试GUI配置 ===")
    
    gui_config = {
        "enabled": True,
        "protocol": "tls",
        "mode": "enhanced",
        "marker_config": {
            "preserve": {
                "handshake": True,
                "application_data": False,
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True
            }
        },
        "masker_config": {
            "preserve_ratio": 0.3
        }
    }
    
    # 使用一个测试文件路径
    test_file = Path("tests/data/tls/tls_1_2-2.pcap")
    checkpoint = MiddlewareCheckpoint(test_file)
    
    results = checkpoint.run_all_checkpoints(gui_config)
    
    print("GUI配置检查点结果:")
    for checkpoint_name, result in results.items():
        print(f"  {checkpoint_name}: {result}")
    
    return results

def test_script_config():
    """测试脚本配置"""
    print("\n=== 测试脚本配置 ===")
    
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
    
    # 使用一个测试文件路径
    test_file = Path("tests/data/tls/tls_1_2-2.pcap")
    checkpoint = MiddlewareCheckpoint(test_file)
    
    results = checkpoint.run_all_checkpoints(script_config)
    
    print("脚本配置检查点结果:")
    for checkpoint_name, result in results.items():
        print(f"  {checkpoint_name}: {result}")
    
    return results

def compare_preserve_configs(gui_results, script_results):
    """对比两种配置的preserve_config解析结果"""
    print("\n=== 对比preserve_config解析结果 ===")
    
    gui_marker_result = gui_results.get('marker_initialization', {})
    script_marker_result = script_results.get('marker_initialization', {})
    
    if gui_marker_result.get('success') and script_marker_result.get('success'):
        gui_preserve = gui_marker_result.get('preserve_config', {})
        script_preserve = script_marker_result.get('preserve_config', {})
        
        print(f"GUI preserve_config: {gui_preserve}")
        print(f"脚本 preserve_config: {script_preserve}")
        
        # 检查关键配置是否一致
        gui_app_data = gui_preserve.get('application_data')
        script_app_data = script_preserve.get('application_data')
        
        print(f"\n关键配置对比:")
        print(f"  GUI application_data: {gui_app_data}")
        print(f"  脚本 application_data: {script_app_data}")
        
        if gui_app_data == script_app_data:
            print("  ✅ TLS-23配置一致！")
            return True
        else:
            print("  ❌ TLS-23配置不一致！")
            return False
    else:
        print("❌ Marker初始化失败，无法对比配置")
        return False

def main():
    """主函数"""
    try:
        # 测试两种配置
        gui_results = test_gui_config()
        script_results = test_script_config()
        
        # 对比结果
        config_consistent = compare_preserve_configs(gui_results, script_results)
        
        print(f"\n=== 总结 ===")
        if config_consistent:
            print("🎉 配置修复成功！GUI和脚本的TLS-23配置现在一致了。")
        else:
            print("❌ 配置修复失败，仍存在差异。")
            
        return config_consistent
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
