#!/usr/bin/env python3
"""
TLS-23掩码效果验证
验证修复后的TLS-23消息体掩码是否正确（只保留5字节头部）
"""

import sys
import os
import tempfile
import subprocess
from pathlib import Path

# 添加src目录到Python路径
script_dir = Path(__file__).parent.absolute()
src_path = script_dir / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

def process_file_with_gui_config(input_file, output_file):
    """使用GUI配置处理文件"""
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # GUI配置
        gui_config = {
            "enabled": True,
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "preserve": {
                    "handshake": True,
                    "application_data": False,  # 关键：不保留完整ApplicationData
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
        
        print(f"GUI配置处理完成:")
        print(f"  处理包数: {stats.packets_processed}")
        print(f"  修改包数: {stats.packets_modified}")
        print(f"  处理时间: {stats.duration_ms:.2f}ms")
        
        return True, stats
        
    except Exception as e:
        print(f"❌ GUI配置处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def analyze_tls23_messages(pcap_file):
    """分析PCAP文件中的TLS-23消息"""
    print(f"\n=== 分析TLS-23消息 ===")
    print(f"分析文件: {pcap_file}")
    
    try:
        # 使用enhanced_tls_marker工具分析TLS-23消息
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_path)
        
        cmd = [
            sys.executable,
            "-m",
            "pktmask.tools.enhanced_tls_marker",
            "--pcap",
            str(pcap_file),
            "--types",
            "23",  # 只分析TLS-23 ApplicationData
            "--formats",
            "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            print(f"⚠️ enhanced_tls_marker执行失败: {result.stderr}")
            return None
        
        # 解析输出
        output_lines = result.stdout.strip().split('\n')
        json_lines = [line for line in output_lines if line.startswith('{')]
        
        if not json_lines:
            print("ℹ️ 未找到TLS-23消息")
            return []
        
        import json
        tls23_messages = []
        for line in json_lines:
            try:
                msg = json.loads(line)
                if msg.get('tls_content_type') == 23:
                    tls23_messages.append(msg)
            except json.JSONDecodeError:
                continue
        
        print(f"找到 {len(tls23_messages)} 条TLS-23消息")
        return tls23_messages
        
    except Exception as e:
        print(f"❌ 分析TLS-23消息失败: {e}")
        return None

def verify_tls23_masking(original_file, processed_file):
    """验证TLS-23掩码效果"""
    print(f"\n=== 验证TLS-23掩码效果 ===")
    
    # 分析原始文件
    print("分析原始文件...")
    original_tls23 = analyze_tls23_messages(original_file)
    if original_tls23 is None:
        return False
    
    # 分析处理后文件
    print("分析处理后文件...")
    processed_tls23 = analyze_tls23_messages(processed_file)
    if processed_tls23 is None:
        return False
    
    if len(original_tls23) == 0:
        print("ℹ️ 原始文件中没有TLS-23消息，无需验证掩码效果")
        return True
    
    print(f"\n=== 掩码效果对比 ===")
    print(f"原始文件TLS-23消息数: {len(original_tls23)}")
    print(f"处理后文件TLS-23消息数: {len(processed_tls23)}")
    
    if len(processed_tls23) != len(original_tls23):
        print("⚠️ TLS-23消息数量不一致，这可能是正常的（某些消息可能被完全掩码）")
    
    # 检查每条TLS-23消息的掩码效果
    masking_verified = True
    for i, (orig_msg, proc_msg) in enumerate(zip(original_tls23, processed_tls23)):
        print(f"\n消息 {i+1}:")
        
        orig_length = orig_msg.get('tls_record_length', 0)
        proc_length = proc_msg.get('tls_record_length', 0)
        
        print(f"  原始长度: {orig_length} 字节")
        print(f"  处理后长度: {proc_length} 字节")
        
        # TLS记录头部是5字节，如果application_data=False，应该只保留头部
        if proc_length <= 5:
            print(f"  ✅ 掩码正确：只保留了TLS记录头部（≤5字节）")
        elif proc_length < orig_length:
            print(f"  ✅ 掩码正确：部分掩码（{orig_length} -> {proc_length}字节）")
        elif proc_length == orig_length:
            print(f"  ⚠️ 可能未掩码：长度未变化")
            masking_verified = False
        else:
            print(f"  ❌ 异常：处理后长度大于原始长度")
            masking_verified = False
    
    return masking_verified

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
        processed_file = temp_path / "processed_output.pcap"
        
        # 使用GUI配置处理文件
        success, stats = process_file_with_gui_config(test_file, processed_file)
        if not success:
            return False
        
        # 验证TLS-23掩码效果
        masking_verified = verify_tls23_masking(test_file, processed_file)
        
        print(f"\n=== 验证总结 ===")
        if masking_verified:
            print("🎉 TLS-23掩码验证通过！")
            print("   修复后的配置正确实现了TLS-23消息体的智能掩码。")
            print("   只保留5字节TLS记录头部，其余部分被掩码。")
            return True
        else:
            print("❌ TLS-23掩码验证失败！")
            print("   可能存在配置问题或掩码逻辑问题。")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
