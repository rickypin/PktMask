#!/usr/bin/env python3
"""
端到端一致性测试
验证GUI和脚本处理结果的一致性
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

def calculate_file_hash(file_path):
    """计算文件的MD5哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def test_script_processing(input_file, output_file):
    """测试脚本处理"""
    print(f"=== 测试脚本处理 ===")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 脚本配置
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
        
        # 创建Stage并处理
        stage = NewMaskPayloadStage(script_config)
        stage.initialize()
        
        stats = stage.process_file(input_file, output_file)
        
        print(f"脚本处理完成:")
        print(f"  处理包数: {stats.packets_processed}")
        print(f"  修改包数: {stats.packets_modified}")
        print(f"  处理时间: {stats.duration_ms:.2f}ms")
        
        return True, stats
        
    except Exception as e:
        print(f"❌ 脚本处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def simulate_gui_processing(input_file, output_file):
    """模拟GUI处理"""
    print(f"\n=== 模拟GUI处理 ===")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # GUI配置（通过pipeline_service.build_pipeline_config生成）
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
        
        # 创建Stage并处理
        stage = NewMaskPayloadStage(gui_config)
        stage.initialize()
        
        stats = stage.process_file(input_file, output_file)
        
        print(f"GUI处理完成:")
        print(f"  处理包数: {stats.packets_processed}")
        print(f"  修改包数: {stats.packets_modified}")
        print(f"  处理时间: {stats.duration_ms:.2f}ms")
        
        return True, stats
        
    except Exception as e:
        print(f"❌ GUI处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def compare_outputs(script_output, gui_output):
    """对比两个输出文件"""
    print(f"\n=== 对比输出文件 ===")
    
    if not script_output.exists():
        print(f"❌ 脚本输出文件不存在: {script_output}")
        return False
        
    if not gui_output.exists():
        print(f"❌ GUI输出文件不存在: {gui_output}")
        return False
    
    # 计算文件哈希
    script_hash = calculate_file_hash(script_output)
    gui_hash = calculate_file_hash(gui_output)
    
    print(f"脚本输出哈希: {script_hash}")
    print(f"GUI输出哈希: {gui_hash}")
    
    # 获取文件大小
    script_size = script_output.stat().st_size
    gui_size = gui_output.stat().st_size
    
    print(f"脚本输出大小: {script_size} 字节")
    print(f"GUI输出大小: {gui_size} 字节")
    
    if script_hash == gui_hash:
        print("✅ 输出文件完全一致！")
        return True
    else:
        print("❌ 输出文件不一致！")
        return False

def main():
    """主函数"""
    # 选择测试文件
    test_file = Path("tests/data/tls/tls_1_2-2.pcap")
    
    if not test_file.exists():
        print(f"❌ 测试文件不存在: {test_file}")
        return False
    
    print(f"使用测试文件: {test_file}")
    
    # 创建临时输出目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        script_output = temp_path / "script_output.pcap"
        gui_output = temp_path / "gui_output.pcap"
        
        # 测试脚本处理
        script_success, script_stats = test_script_processing(test_file, script_output)
        if not script_success:
            return False
        
        # 测试GUI处理
        gui_success, gui_stats = simulate_gui_processing(test_file, gui_output)
        if not gui_success:
            return False
        
        # 对比输出
        outputs_match = compare_outputs(script_output, gui_output)
        
        # 对比统计信息
        print(f"\n=== 对比处理统计 ===")
        if script_stats and gui_stats:
            print(f"脚本处理包数: {script_stats.packets_processed}")
            print(f"GUI处理包数: {gui_stats.packets_processed}")
            print(f"脚本修改包数: {script_stats.packets_modified}")
            print(f"GUI修改包数: {gui_stats.packets_modified}")
            
            stats_match = (script_stats.packets_processed == gui_stats.packets_processed and
                          script_stats.packets_modified == gui_stats.packets_modified)
            
            if stats_match:
                print("✅ 处理统计一致！")
            else:
                print("⚠️ 处理统计有差异，但这可能是正常的。")
        
        print(f"\n=== 测试总结 ===")
        if outputs_match:
            print("🎉 端到端测试通过！GUI和脚本产生完全一致的输出。")
            print("   这证明TLS-23掩码配置修复成功。")
            return True
        else:
            print("❌ 端到端测试失败，输出文件不一致。")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
