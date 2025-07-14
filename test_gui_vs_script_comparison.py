#!/usr/bin/env python3
"""
GUI vs 脚本对比测试
真正验证GUI界面操作和脚本执行结果的一致性
"""

import sys
import os
import tempfile
import hashlib
import subprocess
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

def run_script_processing(input_file, output_file):
    """运行脚本处理（使用实际的验证脚本）"""
    print(f"=== 运行脚本处理 ===")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    try:
        # 创建输出目录
        output_dir = output_file.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_path)
        
        # 运行验证脚本处理单个文件
        cmd = [
            sys.executable,
            "scripts/validation/tls23_maskstage_e2e_validator.py",
            "--input-dir", str(input_file.parent),
            "--output-dir", str(output_dir),
            "--file-pattern", input_file.name,
            "--mode", "pipeline",
            "--verbose"
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=script_dir)
        
        if result.returncode != 0:
            print(f"❌ 脚本执行失败:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False, None
        
        # 查找生成的输出文件
        masked_dir = output_dir / "masked_pcaps"
        expected_output = masked_dir / f"{input_file.stem}_masked.pcap"
        
        if expected_output.exists():
            # 复制到指定位置
            import shutil
            shutil.copy2(expected_output, output_file)
            print(f"✅ 脚本处理成功，输出文件: {output_file}")
            return True, expected_output
        else:
            print(f"❌ 未找到预期的输出文件: {expected_output}")
            return False, None
            
    except Exception as e:
        print(f"❌ 脚本处理异常: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def simulate_gui_processing(input_file, output_file):
    """模拟GUI处理（使用实际的GUI配置和pipeline服务）"""
    print(f"\n=== 模拟GUI处理 ===")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    try:
        # 导入GUI相关模块
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        # 使用GUI的实际配置构建方式
        gui_config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False,
            enable_mask=True
        )
        
        print(f"GUI配置: {gui_config}")
        
        # 创建pipeline执行器
        executor = create_pipeline_executor(gui_config)
        
        # 处理文件
        result = executor.run(str(input_file), str(output_file))
        
        print(f"✅ GUI处理成功:")
        print(f"  处理统计: {result}")
        
        return True, result
        
    except Exception as e:
        print(f"❌ GUI处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def analyze_tls23_in_file(pcap_file, label):
    """分析文件中的TLS-23消息"""
    print(f"\n=== 分析{label}中的TLS-23消息 ===")
    
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_path)
        
        cmd = [
            sys.executable,
            "-m",
            "pktmask.tools.tls23_marker",
            "--pcap", str(pcap_file),
            "--formats", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            print(f"⚠️ TLS-23分析失败: {result.stderr}")
            return None
        
        # 解析JSON输出
        import json
        tls23_messages = []
        for line in result.stdout.strip().split('\n'):
            if line.startswith('{'):
                try:
                    msg = json.loads(line)
                    if msg.get('tls_content_type') == 23:
                        tls23_messages.append(msg)
                except json.JSONDecodeError:
                    continue
        
        print(f"找到 {len(tls23_messages)} 条TLS-23消息")
        
        # 分析掩码状态
        masked_count = 0
        unmasked_count = 0
        
        for msg in tls23_messages:
            length = msg.get('tls_record_length', 0)
            if length <= 5:  # 只保留头部
                masked_count += 1
            else:
                unmasked_count += 1
        
        print(f"  已掩码消息: {masked_count}")
        print(f"  未掩码消息: {unmasked_count}")
        
        return {
            'total': len(tls23_messages),
            'masked': masked_count,
            'unmasked': unmasked_count,
            'messages': tls23_messages
        }
        
    except Exception as e:
        print(f"❌ 分析TLS-23消息失败: {e}")
        return None

def main():
    """主函数"""
    # 选择一个包含TLS-23消息的测试文件
    test_files = [
        "tests/data/tls/https-justlaunchpage.pcap",
        "tests/data/tls/ssl_3.pcap",
        "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap"
    ]
    
    test_file = None
    for file_path in test_files:
        if Path(file_path).exists():
            test_file = Path(file_path)
            break
    
    if not test_file:
        print("❌ 未找到合适的测试文件")
        return False
    
    print(f"使用测试文件: {test_file}")
    
    # 创建临时输出目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        script_output = temp_path / "script_output.pcap"
        gui_output = temp_path / "gui_output.pcap"
        
        # 分析原始文件
        original_analysis = analyze_tls23_in_file(test_file, "原始文件")
        if not original_analysis or original_analysis['total'] == 0:
            print("⚠️ 原始文件中没有TLS-23消息，选择其他文件测试")
            return False
        
        # 运行脚本处理
        script_success, script_result = run_script_processing(test_file, script_output)
        if not script_success:
            print("❌ 脚本处理失败，无法进行对比")
            return False
        
        # 运行GUI处理
        gui_success, gui_result = simulate_gui_processing(test_file, gui_output)
        if not gui_success:
            print("❌ GUI处理失败，无法进行对比")
            return False
        
        # 分析处理后的文件
        script_analysis = analyze_tls23_in_file(script_output, "脚本处理后文件")
        gui_analysis = analyze_tls23_in_file(gui_output, "GUI处理后文件")
        
        # 对比结果
        print(f"\n=== 处理结果对比 ===")
        print(f"原始文件TLS-23消息: {original_analysis['total']}")
        print(f"脚本处理后:")
        print(f"  已掩码: {script_analysis['masked'] if script_analysis else 'N/A'}")
        print(f"  未掩码: {script_analysis['unmasked'] if script_analysis else 'N/A'}")
        print(f"GUI处理后:")
        print(f"  已掩码: {gui_analysis['masked'] if gui_analysis else 'N/A'}")
        print(f"  未掩码: {gui_analysis['unmasked'] if gui_analysis else 'N/A'}")
        
        # 文件级对比
        script_hash = calculate_file_hash(script_output)
        gui_hash = calculate_file_hash(gui_output)
        
        print(f"\n=== 文件哈希对比 ===")
        print(f"脚本输出哈希: {script_hash}")
        print(f"GUI输出哈希: {gui_hash}")
        
        # 最终判断
        files_identical = (script_hash == gui_hash)
        masking_consistent = (
            script_analysis and gui_analysis and
            script_analysis['masked'] == gui_analysis['masked'] and
            script_analysis['unmasked'] == gui_analysis['unmasked']
        )
        
        print(f"\n=== 验证结果 ===")
        if files_identical:
            print("🎉 文件完全一致！GUI和脚本产生相同的输出。")
        else:
            print("❌ 文件不一致！GUI和脚本产生不同的输出。")
        
        if masking_consistent:
            print("✅ TLS-23掩码行为一致！")
        else:
            print("❌ TLS-23掩码行为不一致！")
        
        overall_success = files_identical and masking_consistent
        
        if overall_success:
            print("\n🎉 修复验证成功！GUI界面现在与脚本产生一致的TLS-23掩码结果。")
        else:
            print("\n❌ 修复验证失败！GUI界面仍与脚本产生不一致的结果。")
        
        return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
