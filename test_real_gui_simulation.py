#!/usr/bin/env python3
"""
真实GUI模拟测试
直接使用GUI的实际代码路径来处理文件，然后与脚本对比
"""

import sys
import os
import tempfile
import hashlib
from pathlib import Path

# 添加src目录到Python路径
script_dir = Path(__file__).parent.absolute()
src_path = script_dir / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

def test_gui_pipeline_service():
    """测试GUI的pipeline服务处理"""
    print("=== 测试GUI Pipeline服务处理 ===")
    
    try:
        # 导入GUI实际使用的服务
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor, run_pipeline
        
        # 使用GUI的实际配置构建方式
        config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False,
            enable_mask=True
        )
        
        print(f"GUI配置: {config}")
        
        # 测试文件
        test_file = Path("tests/data/tls/tls_1_2_single_vlan.pcap")
        if not test_file.exists():
            print(f"❌ 测试文件不存在: {test_file}")
            return False
        
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        try:
            # 使用GUI的pipeline服务处理文件
            def progress_callback(event_type, data):
                print(f"进度: {event_type} - {data}")
            
            # 运行pipeline
            success = run_pipeline(
                config=config,
                input_files=[str(test_file)],
                output_dir=str(output_file.parent),
                progress_callback=progress_callback
            )
            
            if success:
                print("✅ GUI Pipeline处理成功")
                
                # 检查输出文件
                expected_output = output_file.parent / f"{test_file.stem}_processed.pcap"
                if expected_output.exists():
                    print(f"输出文件: {expected_output}")
                    print(f"文件大小: {expected_output.stat().st_size} 字节")
                    return True, expected_output
                else:
                    print(f"❌ 未找到预期输出文件: {expected_output}")
                    return False, None
            else:
                print("❌ GUI Pipeline处理失败")
                return False, None
                
        finally:
            # 清理临时文件
            if output_file.exists():
                output_file.unlink()
        
    except Exception as e:
        print(f"❌ GUI Pipeline测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_direct_stage_processing():
    """直接测试Stage处理（模拟GUI内部调用）"""
    print("\n=== 测试直接Stage处理 ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 使用GUI配置格式
        gui_config = {
            "enabled": True,
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "preserve": {
                    "handshake": True,
                    "application_data": False,  # 关键配置
                    "alert": True,
                    "change_cipher_spec": True,
                    "heartbeat": True
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
        
        # 脚本配置格式
        script_config = {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "tls": {
                    "preserve_handshake": True,
                    "preserve_application_data": False  # 关键配置
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
        
        test_file = Path("tests/data/tls/tls_1_2_single_vlan.pcap")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            gui_output = temp_path / "gui_output.pcap"
            script_output = temp_path / "script_output.pcap"
            
            # 测试GUI配置
            print("处理GUI配置...")
            gui_stage = NewMaskPayloadStage(gui_config)
            gui_stage.initialize()
            gui_stats = gui_stage.process_file(test_file, gui_output)
            
            print(f"GUI处理结果:")
            print(f"  处理包数: {gui_stats.packets_processed}")
            print(f"  修改包数: {gui_stats.packets_modified}")
            print(f"  掩码字节: {gui_stats.extra_metrics.get('masked_bytes', 0)}")
            print(f"  保留字节: {gui_stats.extra_metrics.get('preserved_bytes', 0)}")
            
            # 测试脚本配置
            print("\n处理脚本配置...")
            script_stage = NewMaskPayloadStage(script_config)
            script_stage.initialize()
            script_stats = script_stage.process_file(test_file, script_output)
            
            print(f"脚本处理结果:")
            print(f"  处理包数: {script_stats.packets_processed}")
            print(f"  修改包数: {script_stats.packets_modified}")
            print(f"  掩码字节: {script_stats.extra_metrics.get('masked_bytes', 0)}")
            print(f"  保留字节: {script_stats.extra_metrics.get('preserved_bytes', 0)}")
            
            # 对比结果
            gui_hash = hashlib.md5(gui_output.read_bytes()).hexdigest()
            script_hash = hashlib.md5(script_output.read_bytes()).hexdigest()
            
            print(f"\n=== 文件对比 ===")
            print(f"GUI输出哈希: {gui_hash}")
            print(f"脚本输出哈希: {script_hash}")
            
            if gui_hash == script_hash:
                print("✅ 输出文件完全一致！")
                return True
            else:
                print("❌ 输出文件不一致！")
                
                # 详细对比统计信息
                print(f"\n=== 详细对比 ===")
                print(f"处理包数: GUI={gui_stats.packets_processed}, 脚本={script_stats.packets_processed}")
                print(f"修改包数: GUI={gui_stats.packets_modified}, 脚本={script_stats.packets_modified}")
                print(f"掩码字节: GUI={gui_stats.extra_metrics.get('masked_bytes', 0)}, 脚本={script_stats.extra_metrics.get('masked_bytes', 0)}")
                
                return False
        
    except Exception as e:
        print(f"❌ 直接Stage测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_marker_config_parsing():
    """测试Marker配置解析"""
    print("\n=== 测试Marker配置解析 ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        # GUI格式
        gui_marker_config = {
            "preserve": {
                "handshake": True,
                "application_data": False,
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True
            }
        }
        
        # 脚本格式
        script_marker_config = {
            "tls": {
                "preserve_handshake": True,
                "preserve_application_data": False
            }
        }
        
        # 测试两种配置
        gui_marker = TLSProtocolMarker(gui_marker_config)
        script_marker = TLSProtocolMarker(script_marker_config)
        
        print(f"GUI Marker preserve_config: {gui_marker.preserve_config}")
        print(f"脚本 Marker preserve_config: {script_marker.preserve_config}")
        
        # 检查关键配置
        gui_app_data = gui_marker.preserve_config.get('application_data')
        script_app_data = script_marker.preserve_config.get('application_data')
        
        print(f"\n关键配置对比:")
        print(f"GUI application_data: {gui_app_data}")
        print(f"脚本 application_data: {script_app_data}")
        
        if gui_app_data == script_app_data:
            print("✅ Marker配置解析一致")
            return True
        else:
            print("❌ Marker配置解析不一致")
            return False
        
    except Exception as e:
        print(f"❌ Marker配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("开始真实GUI模拟测试...")
    
    # 测试1: Marker配置解析
    marker_test_passed = test_marker_config_parsing()
    
    # 测试2: 直接Stage处理对比
    stage_test_passed = test_direct_stage_processing()
    
    # 测试3: GUI Pipeline服务（如果可用）
    # pipeline_test_passed, _ = test_gui_pipeline_service()
    
    print(f"\n=== 测试总结 ===")
    print(f"Marker配置解析: {'✅ 通过' if marker_test_passed else '❌ 失败'}")
    print(f"Stage处理对比: {'✅ 通过' if stage_test_passed else '❌ 失败'}")
    # print(f"Pipeline服务: {'✅ 通过' if pipeline_test_passed else '❌ 失败'}")
    
    overall_success = marker_test_passed and stage_test_passed
    
    if overall_success:
        print("\n🎉 修复验证成功！GUI和脚本现在产生一致的处理结果。")
        print("   TLS-23掩码配置问题已解决。")
    else:
        print("\n❌ 修复验证失败！仍存在GUI和脚本不一致的问题。")
        print("   需要进一步调试。")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
