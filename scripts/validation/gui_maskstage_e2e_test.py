#!/usr/bin/env python3
"""
GUI MaskStage 端到端测试脚本

用于验证修复后的GUI主程序与验证脚本是否产生一致的掩码结果。
严格禁止修改主程序代码，仅用于验证分析。

Author: PktMask Core Team
Version: v1.0 (GUI修复验证专用)
"""

import sys
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple
import subprocess

# Add src directory to Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 配置日志
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("gui_maskstage_e2e_test")

def run_gui_maskstage(input_file: Path, output_file: Path) -> bool:
    """使用GUI主程序的配置运行maskstage"""
    logger.info(f"使用GUI配置处理: {input_file} -> {output_file}")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        # 使用GUI的配置构建方式
        config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False,
            enable_mask=True
        )
        
        # 创建执行器
        executor = create_pipeline_executor(config)
        
        # 执行处理
        result = executor.run(str(input_file), str(output_file))
        
        if result.success:
            logger.info("✅ GUI配置处理成功")
            return True
        else:
            logger.error(f"❌ GUI配置处理失败: {result.errors}")
            return False
            
    except Exception as e:
        logger.error(f"❌ GUI配置处理异常: {e}")
        return False

def run_validator_maskstage(input_file: Path, output_file: Path) -> bool:
    """使用验证脚本的配置运行maskstage"""
    logger.info(f"使用验证脚本配置处理: {input_file} -> {output_file}")
    
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage as MaskStage
        
        # 使用验证脚本的配置
        config = {
            "dedup": {"enabled": False},
            "anon": {"enabled": False},
            "mask": {
                "enabled": True,
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
        }
        
        # 创建执行器
        executor = PipelineExecutor(config)
        
        # 执行处理
        result = executor.run(str(input_file), str(output_file))
        
        if result.success:
            logger.info("✅ 验证脚本配置处理成功")
            return True
        else:
            logger.error(f"❌ 验证脚本配置处理失败: {result.errors}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 验证脚本配置处理异常: {e}")
        return False

def compare_files(file1: Path, file2: Path) -> Tuple[bool, str]:
    """比较两个文件是否相同"""
    try:
        # 使用文件大小快速检查
        if file1.stat().st_size != file2.stat().st_size:
            return False, f"文件大小不同: {file1.stat().st_size} vs {file2.stat().st_size}"
        
        # 逐字节比较
        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            chunk_size = 8192
            while True:
                chunk1 = f1.read(chunk_size)
                chunk2 = f2.read(chunk_size)
                
                if chunk1 != chunk2:
                    return False, "文件内容不同"
                
                if not chunk1:  # 到达文件末尾
                    break
        
        return True, "文件完全相同"
        
    except Exception as e:
        return False, f"比较失败: {e}"

def run_tls23_marker_analysis(input_file: Path, output_file: Path) -> Dict[str, Any]:
    """运行tls23_marker分析获取详细信息"""
    try:
        # 运行tls23_marker
        cmd = [
            sys.executable, 
            str(project_root / "tools" / "tls23_marker.py"),
            str(input_file),
            "--output-format", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            import json
            return json.loads(result.stdout)
        else:
            logger.warning(f"tls23_marker分析失败: {result.stderr}")
            return {}
            
    except Exception as e:
        logger.warning(f"tls23_marker分析异常: {e}")
        return {}

def test_single_file(test_file: Path) -> Dict[str, Any]:
    """测试单个文件的处理一致性"""
    logger.info(f"测试文件: {test_file}")
    
    with tempfile.TemporaryDirectory(prefix="gui_maskstage_test_") as temp_dir:
        temp_path = Path(temp_dir)
        
        # 输出文件路径
        gui_output = temp_path / f"{test_file.stem}_gui_processed.pcap"
        validator_output = temp_path / f"{test_file.stem}_validator_processed.pcap"
        
        # 运行GUI配置处理
        gui_success = run_gui_maskstage(test_file, gui_output)
        
        # 运行验证脚本配置处理
        validator_success = run_validator_maskstage(test_file, validator_output)
        
        result = {
            "file": str(test_file),
            "gui_success": gui_success,
            "validator_success": validator_success,
            "files_identical": False,
            "comparison_message": "",
            "original_analysis": {},
            "gui_analysis": {},
            "validator_analysis": {}
        }
        
        # 如果两个都成功，比较输出文件
        if gui_success and validator_success:
            files_identical, comparison_message = compare_files(gui_output, validator_output)
            result["files_identical"] = files_identical
            result["comparison_message"] = comparison_message
            
            # 获取详细分析
            result["original_analysis"] = run_tls23_marker_analysis(test_file, None)
            result["gui_analysis"] = run_tls23_marker_analysis(gui_output, None)
            result["validator_analysis"] = run_tls23_marker_analysis(validator_output, None)
        
        return result

def main():
    """主函数"""
    logger.info("开始GUI MaskStage端到端测试")
    
    # 测试文件列表
    test_files = [
        project_root / "tests" / "data" / "tls" / "tls_1_2-2.pcap",
        project_root / "tests" / "data" / "tls" / "google-https-cachedlink_plus_sitelink.pcap"
    ]
    
    # 过滤存在的文件
    existing_files = [f for f in test_files if f.exists()]
    
    if not existing_files:
        logger.error("未找到测试文件")
        return
    
    logger.info(f"找到 {len(existing_files)} 个测试文件")
    
    # 测试结果
    results = []
    
    for test_file in existing_files:
        try:
            result = test_single_file(test_file)
            results.append(result)
        except Exception as e:
            logger.error(f"测试文件 {test_file} 失败: {e}")
            results.append({
                "file": str(test_file),
                "error": str(e)
            })
    
    # 输出测试结果
    print("\n" + "="*80)
    print("GUI MaskStage 端到端测试结果")
    print("="*80)
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. 文件: {Path(result['file']).name}")
        
        if "error" in result:
            print(f"   ❌ 测试失败: {result['error']}")
            continue
        
        print(f"   GUI处理: {'✅ 成功' if result['gui_success'] else '❌ 失败'}")
        print(f"   验证脚本处理: {'✅ 成功' if result['validator_success'] else '❌ 失败'}")
        
        if result['gui_success'] and result['validator_success']:
            if result['files_identical']:
                print(f"   🎉 输出文件完全一致: {result['comparison_message']}")
            else:
                print(f"   ⚠️  输出文件不一致: {result['comparison_message']}")
        
        # 显示TLS分析统计
        original = result.get('original_analysis', {})
        gui = result.get('gui_analysis', {})
        validator = result.get('validator_analysis', {})
        
        if original:
            print(f"   原始文件TLS-23消息: {len(original.get('flows', {}).get('tls_records', []))}")
        if gui:
            print(f"   GUI处理后TLS-23消息: {len(gui.get('flows', {}).get('tls_records', []))}")
        if validator:
            print(f"   验证脚本处理后TLS-23消息: {len(validator.get('flows', {}).get('tls_records', []))}")
    
    # 总结
    successful_tests = sum(1 for r in results if r.get('gui_success') and r.get('validator_success'))
    identical_outputs = sum(1 for r in results if r.get('files_identical'))
    
    print(f"\n总结:")
    print(f"  测试文件数: {len(results)}")
    print(f"  成功处理数: {successful_tests}")
    print(f"  输出一致数: {identical_outputs}")
    
    if identical_outputs == successful_tests and successful_tests > 0:
        print(f"  🎉 所有测试通过！GUI主程序与验证脚本产生一致结果")
    else:
        print(f"  ⚠️  存在不一致，需要进一步调查")
    
    print("="*80)

if __name__ == "__main__":
    main()
