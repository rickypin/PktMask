#!/usr/bin/env python3
"""
调试多文件处理问题的脚本
"""

import json
import sys
import tempfile
from pathlib import Path

def test_gui_multifile_simulation():
    """模拟GUI多文件处理流程"""
    print("=== GUI多文件处理模拟 ===")
    
    # 测试文件列表
    test_files = [
        "tests/data/tls/tls_1_2-2.pcap",
        "tests/data/tls/ssl_3.pcap",
        "tests/data/tls/tls_1_2_double_vlan.pcap"
    ]
    
    # 过滤存在的文件
    existing_files = [f for f in test_files if Path(f).exists()]
    if not existing_files:
        print("❌ 没有找到测试文件")
        return False
    
    print(f"找到 {len(existing_files)} 个测试文件")
    
    # 创建GUI配置
    from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
    
    config = build_pipeline_config(
        enable_anon=False,
        enable_dedup=False,
        enable_mask=True
    )
    
    print("1. 创建PipelineExecutor（模拟GUI）")
    executor = create_pipeline_executor(config)
    
    # 模拟多文件处理
    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for i, input_file in enumerate(existing_files):
            print(f"\n2.{i+1} 处理文件: {Path(input_file).name}")
            
            output_file = temp_path / f"output_{i}.pcap"
            
            try:
                # 使用同一个executor处理多个文件（模拟GUI行为）
                result = executor.run(input_file, str(output_file))
                
                print(f"   成功: {result.success}")
                if result.stage_stats:
                    for stage_stat in result.stage_stats:
                        print(f"   {stage_stat.stage_name}: 处理包数={stage_stat.packets_processed}, 修改包数={stage_stat.packets_modified}")
                        results.append({
                            'file': Path(input_file).name,
                            'stage': stage_stat.stage_name,
                            'processed': stage_stat.packets_processed,
                            'modified': stage_stat.packets_modified,
                            'success': result.success
                        })
                
            except Exception as e:
                print(f"   ❌ 失败: {e}")
                results.append({
                    'file': Path(input_file).name,
                    'stage': 'unknown',
                    'processed': 0,
                    'modified': 0,
                    'success': False,
                    'error': str(e)
                })
    
    # 分析结果
    print(f"\n3. 结果分析:")
    mask_results = [r for r in results if 'Mask' in r.get('stage', '')]
    
    if not mask_results:
        print("❌ 没有找到掩码处理结果")
        return False
    
    successful_masks = [r for r in mask_results if r['success'] and r['modified'] > 0]
    failed_masks = [r for r in mask_results if not r['success'] or r['modified'] == 0]
    
    print(f"   成功掩码的文件: {len(successful_masks)}")
    for r in successful_masks:
        print(f"     - {r['file']}: 修改了 {r['modified']} 个包")
    
    print(f"   掩码失败的文件: {len(failed_masks)}")
    for r in failed_masks:
        print(f"     - {r['file']}: 修改了 {r['modified']} 个包 {'(错误: ' + r.get('error', 'unknown') + ')' if 'error' in r else ''}")
    
    # 判断是否存在问题
    if len(failed_masks) > 0:
        print("❌ 检测到多文件处理问题：部分文件掩码失败")
        return False
    else:
        print("✅ 多文件处理正常")
        return True

def test_script_multifile_simulation():
    """模拟脚本多文件处理流程"""
    print("\n=== 脚本多文件处理模拟 ===")
    
    # 测试文件列表
    test_files = [
        "tests/data/tls/tls_1_2-2.pcap",
        "tests/data/tls/ssl_3.pcap",
        "tests/data/tls/tls_1_2_double_vlan.pcap"
    ]
    
    # 过滤存在的文件
    existing_files = [f for f in test_files if Path(f).exists()]
    if not existing_files:
        print("❌ 没有找到测试文件")
        return False
    
    print(f"找到 {len(existing_files)} 个测试文件")
    
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
    
    print("1. 每个文件创建新的NewMaskPayloadStage（模拟脚本）")
    
    # 模拟多文件处理
    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for i, input_file in enumerate(existing_files):
            print(f"\n2.{i+1} 处理文件: {Path(input_file).name}")
            
            output_file = temp_path / f"output_{i}.pcap"
            
            try:
                # 每个文件创建新的stage（模拟脚本行为）
                from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
                
                stage = NewMaskPayloadStage(script_config)
                stage.initialize()
                
                result = stage.process_file(input_file, str(output_file))
                
                print(f"   成功: True")
                print(f"   {result.stage_name}: 处理包数={result.packets_processed}, 修改包数={result.packets_modified}")
                
                results.append({
                    'file': Path(input_file).name,
                    'stage': result.stage_name,
                    'processed': result.packets_processed,
                    'modified': result.packets_modified,
                    'success': True
                })
                
            except Exception as e:
                print(f"   ❌ 失败: {e}")
                results.append({
                    'file': Path(input_file).name,
                    'stage': 'unknown',
                    'processed': 0,
                    'modified': 0,
                    'success': False,
                    'error': str(e)
                })
    
    # 分析结果
    print(f"\n3. 结果分析:")
    successful_masks = [r for r in results if r['success'] and r['modified'] > 0]
    failed_masks = [r for r in results if not r['success'] or r['modified'] == 0]
    
    print(f"   成功掩码的文件: {len(successful_masks)}")
    for r in successful_masks:
        print(f"     - {r['file']}: 修改了 {r['modified']} 个包")
    
    print(f"   掩码失败的文件: {len(failed_masks)}")
    for r in failed_masks:
        print(f"     - {r['file']}: 修改了 {r['modified']} 个包 {'(错误: ' + r.get('error', 'unknown') + ')' if 'error' in r else ''}")
    
    # 判断是否存在问题
    if len(failed_masks) > 0:
        print("❌ 检测到多文件处理问题：部分文件掩码失败")
        return False
    else:
        print("✅ 多文件处理正常")
        return True

def main():
    """主函数"""
    print("调试多文件处理差异\n")
    
    gui_ok = test_gui_multifile_simulation()
    script_ok = test_script_multifile_simulation()
    
    print(f"\n=== 总结 ===")
    print(f"GUI多文件处理: {'✅ 正常' if gui_ok else '❌ 异常'}")
    print(f"脚本多文件处理: {'✅ 正常' if script_ok else '❌ 异常'}")
    
    if not gui_ok and script_ok:
        print("\n🔧 确认GUI多文件处理存在问题")
        print("可能原因：PipelineExecutor重用导致状态污染")
    elif gui_ok and not script_ok:
        print("\n🔧 脚本处理也存在问题")
    elif not gui_ok and not script_ok:
        print("\n🔧 两种方式都存在问题，可能是测试环境问题")
    else:
        print("\n✅ 两种方式都正常，问题可能在其他地方")
    
    return gui_ok and script_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
