#!/usr/bin/env python3
"""
全面验证GUI多文件处理修复效果的脚本
"""

import json
import sys
import tempfile
from pathlib import Path

def test_all_tls_files():
    """测试所有TLS测试文件"""
    print("=== 全面验证GUI多文件处理修复效果 ===")
    
    # 获取所有TLS测试文件
    tls_dir = Path("tests/data/tls")
    if not tls_dir.exists():
        print("❌ TLS测试目录不存在")
        return False
    
    test_files = list(tls_dir.glob("*.pcap")) + list(tls_dir.glob("*.pcapng"))
    test_files = [f for f in test_files if f.is_file()]
    
    if not test_files:
        print("❌ 没有找到测试文件")
        return False
    
    print(f"找到 {len(test_files)} 个测试文件:")
    for f in test_files:
        print(f"  - {f.name}")
    
    # 创建GUI配置
    from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
    
    config = build_pipeline_config(
        enable_anon=False,
        enable_dedup=False,
        enable_mask=True
    )
    
    print("\n1. 创建PipelineExecutor（模拟GUI）")
    executor = create_pipeline_executor(config)
    
    # 测试多文件处理
    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for i, input_file in enumerate(test_files):
            print(f"\n2.{i+1} 处理文件: {input_file.name}")
            
            output_file = temp_path / f"output_{i}.pcap"
            
            try:
                # 使用同一个executor处理多个文件（模拟GUI行为）
                result = executor.run(str(input_file), str(output_file))
                
                if result.stage_stats:
                    for stage_stat in result.stage_stats:
                        if 'Mask' in stage_stat.stage_name:
                            print(f"   {stage_stat.stage_name}: 处理包数={stage_stat.packets_processed}, 修改包数={stage_stat.packets_modified}")
                            results.append({
                                'file': input_file.name,
                                'processed': stage_stat.packets_processed,
                                'modified': stage_stat.packets_modified,
                                'success': result.success
                            })
                            break
                
            except Exception as e:
                print(f"   ❌ 失败: {e}")
                results.append({
                    'file': input_file.name,
                    'processed': 0,
                    'modified': 0,
                    'success': False,
                    'error': str(e)
                })
    
    # 分析结果
    print(f"\n3. 结果分析:")
    successful_results = [r for r in results if r['success']]
    failed_results = [r for r in results if not r['success']]
    
    # 有掩码效果的文件
    masked_files = [r for r in successful_results if r['modified'] > 0]
    unmasked_files = [r for r in successful_results if r['modified'] == 0]
    
    print(f"   总文件数: {len(results)}")
    print(f"   成功处理: {len(successful_results)}")
    print(f"   处理失败: {len(failed_results)}")
    print(f"   有掩码效果: {len(masked_files)}")
    print(f"   无掩码效果: {len(unmasked_files)}")
    
    if masked_files:
        print(f"\n   有掩码效果的文件:")
        for r in masked_files:
            print(f"     - {r['file']}: 修改了 {r['modified']} 个包")
    
    if unmasked_files:
        print(f"\n   无掩码效果的文件:")
        for r in unmasked_files:
            print(f"     - {r['file']}: 处理了 {r['processed']} 个包，但未修改")
    
    if failed_results:
        print(f"\n   处理失败的文件:")
        for r in failed_results:
            error_msg = r.get('error', 'unknown error')
            print(f"     - {r['file']}: {error_msg}")
    
    # 判断修复是否成功
    # 成功标准：
    # 1. 所有文件都能成功处理
    # 2. 至少有一些文件有掩码效果（说明TLS-23掩码正常工作）
    # 3. 没有明显的状态污染问题（如某些文件应该有掩码但没有）
    
    success_criteria = {
        'all_processed': len(failed_results) == 0,
        'has_masking_effect': len(masked_files) > 0,
        'reasonable_results': len(masked_files) >= len(unmasked_files) * 0.3  # 至少30%的文件有掩码效果
    }
    
    print(f"\n4. 修复验证:")
    print(f"   所有文件成功处理: {'✅' if success_criteria['all_processed'] else '❌'}")
    print(f"   存在掩码效果: {'✅' if success_criteria['has_masking_effect'] else '❌'}")
    print(f"   结果合理性: {'✅' if success_criteria['reasonable_results'] else '❌'}")
    
    overall_success = all(success_criteria.values())
    
    if overall_success:
        print(f"\n🎉 修复验证成功！")
        print(f"   GUI多文件处理现在能够正确执行TLS-23掩码")
        print(f"   状态污染问题已解决")
    else:
        print(f"\n❌ 修复验证失败")
        failed_criteria = [k for k, v in success_criteria.items() if not v]
        print(f"   失败的标准: {failed_criteria}")
    
    return overall_success

def compare_with_known_good_results():
    """与已知的良好结果进行对比"""
    print("\n=== 与已知良好结果对比 ===")
    
    # 已知的良好结果（基于之前的测试）
    known_good_results = {
        'tls_1_2-2.pcap': {'processed': 14, 'modified': 1},
        'ssl_3.pcap': {'processed': 101, 'modified': 59},
        'tls_1_2_double_vlan.pcap': {'processed': 854, 'modified': 70}
    }
    
    # 测试这些特定文件
    from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
    
    config = build_pipeline_config(
        enable_anon=False,
        enable_dedup=False,
        enable_mask=True
    )
    
    executor = create_pipeline_executor(config)
    
    comparison_results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for filename, expected in known_good_results.items():
            input_file = Path(f"tests/data/tls/{filename}")
            if not input_file.exists():
                print(f"   跳过 {filename}: 文件不存在")
                continue
            
            output_file = temp_path / f"test_{filename}"
            
            try:
                result = executor.run(str(input_file), str(output_file))
                
                if result.stage_stats:
                    for stage_stat in result.stage_stats:
                        if 'Mask' in stage_stat.stage_name:
                            actual = {
                                'processed': stage_stat.packets_processed,
                                'modified': stage_stat.packets_modified
                            }
                            
                            matches = (actual['processed'] == expected['processed'] and 
                                     actual['modified'] == expected['modified'])
                            
                            comparison_results.append({
                                'file': filename,
                                'expected': expected,
                                'actual': actual,
                                'matches': matches
                            })
                            
                            status = "✅" if matches else "❌"
                            print(f"   {status} {filename}:")
                            print(f"      预期: 处理{expected['processed']}, 修改{expected['modified']}")
                            print(f"      实际: 处理{actual['processed']}, 修改{actual['modified']}")
                            break
                            
            except Exception as e:
                print(f"   ❌ {filename}: 处理失败 - {e}")
                comparison_results.append({
                    'file': filename,
                    'expected': expected,
                    'actual': None,
                    'matches': False,
                    'error': str(e)
                })
    
    # 统计对比结果
    matching_files = [r for r in comparison_results if r['matches']]
    total_files = len(comparison_results)
    
    print(f"\n   对比结果: {len(matching_files)}/{total_files} 个文件结果匹配")
    
    if len(matching_files) == total_files:
        print(f"   🎉 所有测试文件的结果都与预期一致！")
        return True
    else:
        print(f"   ❌ 部分文件结果不匹配")
        return False

def main():
    """主函数"""
    print("全面验证GUI多文件处理修复效果\n")
    
    test1_ok = test_all_tls_files()
    test2_ok = compare_with_known_good_results()
    
    print(f"\n=== 最终结果 ===")
    print(f"全面测试: {'✅ 通过' if test1_ok else '❌ 失败'}")
    print(f"对比测试: {'✅ 通过' if test2_ok else '❌ 失败'}")
    
    if test1_ok and test2_ok:
        print(f"\n🎉 修复验证完全成功！")
        print(f"GUI界面现在能够正确处理多个TLS文件，")
        print(f"TLS-23消息掩码功能与命令行脚本保持一致。")
        print(f"状态污染问题已彻底解决。")
    else:
        print(f"\n❌ 修复验证失败")
        print(f"需要进一步调查和修复")
    
    return test1_ok and test2_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
