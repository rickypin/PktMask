#!/usr/bin/env python3
"""
调试NewMaskPayloadStage配置传递问题的脚本
"""

import json
import sys
from pathlib import Path

def test_stage_config_passing():
    """测试Stage配置传递问题"""
    print("=== NewMaskPayloadStage配置传递测试 ===")
    
    # 模拟GUI的完整配置
    gui_mask_config = {
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
    
    print("1. GUI Mask配置:")
    print(json.dumps(gui_mask_config, indent=2))
    
    # 创建NewMaskPayloadStage
    from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
    
    stage = NewMaskPayloadStage(gui_mask_config)
    
    print(f"\n2. Stage属性:")
    print(f"   self.config: {stage.config}")
    print(f"   self.marker_config: {stage.marker_config}")
    print(f"   self.masker_config: {stage.masker_config}")
    
    # 初始化stage
    if not stage.initialize():
        print("❌ Stage初始化失败")
        return False
    
    print(f"\n3. 初始化后的marker配置:")
    print(f"   marker类型: {type(stage.marker)}")
    print(f"   marker.preserve_config: {stage.marker.preserve_config}")
    
    # 检查关键配置
    app_data_preserve = stage.marker.preserve_config.get('application_data', True)
    print(f"\n4. 关键检查:")
    print(f"   application_data保留: {app_data_preserve}")
    print(f"   预期行为: TLS-23应该被{'保留' if app_data_preserve else '掩码'}")
    
    if app_data_preserve:
        print("❌ 错误：TLS-23会被完全保留，而不是掩码！")
        return False
    else:
        print("✅ 正确：TLS-23会被掩码")
        return True

def test_analyze_file_config_passing():
    """测试analyze_file方法的配置传递"""
    print("\n=== analyze_file配置传递测试 ===")
    
    # 模拟GUI的完整配置
    gui_mask_config = {
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
    
    from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
    
    stage = NewMaskPayloadStage(gui_mask_config)
    stage.initialize()
    
    print("1. 当前代码中analyze_file接收的配置:")
    print("   传递给analyze_file的是: self.config")
    print(f"   self.config内容: {stage.config}")
    
    print("\n2. 应该传递的配置:")
    print("   应该传递给analyze_file的是: self.marker_config")
    print(f"   self.marker_config内容: {stage.marker_config}")
    
    # 测试两种配置对TLS标记器的影响
    from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
    
    print("\n3. 使用self.config创建TLS标记器:")
    try:
        marker_with_full_config = TLSProtocolMarker(stage.config)
        print(f"   preserve_config: {marker_with_full_config.preserve_config}")
        app_data_1 = marker_with_full_config.preserve_config.get('application_data', True)
        print(f"   application_data保留: {app_data_1}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        app_data_1 = True
    
    print("\n4. 使用self.marker_config创建TLS标记器:")
    try:
        marker_with_marker_config = TLSProtocolMarker(stage.marker_config)
        print(f"   preserve_config: {marker_with_marker_config.preserve_config}")
        app_data_2 = marker_with_marker_config.preserve_config.get('application_data', True)
        print(f"   application_data保留: {app_data_2}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        app_data_2 = True
    
    print(f"\n5. 结论:")
    if app_data_1 != app_data_2:
        print("❌ 配置传递错误！两种配置产生不同的结果")
        print(f"   self.config -> application_data={app_data_1}")
        print(f"   self.marker_config -> application_data={app_data_2}")
        return False
    else:
        print("✅ 配置传递正确，两种配置产生相同结果")
        return True

def main():
    """主函数"""
    print("调试NewMaskPayloadStage配置传递问题\n")
    
    test1_ok = test_stage_config_passing()
    test2_ok = test_analyze_file_config_passing()
    
    print(f"\n=== 总结 ===")
    print(f"Stage配置测试: {'✅ 正确' if test1_ok else '❌ 错误'}")
    print(f"analyze_file配置测试: {'✅ 正确' if test2_ok else '❌ 错误'}")
    
    if not test2_ok:
        print("\n🔧 需要修复analyze_file配置传递")
        print("问题：第130行传递self.config而不是self.marker_config")
        print("解决方案：修改为keep_rules = self.marker.analyze_file(str(input_path), self.marker_config)")
    
    return test1_ok and test2_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
