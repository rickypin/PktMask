#!/usr/bin/env python3
"""
GUI运行时诊断工具

用于诊断PktMask GUI实际运行时显示"masked 0 pkts"的问题。
严格禁止修改主程序代码，仅用于验证分析。

Author: PktMask Core Team
Version: v1.0 (GUI运行时诊断专用)
"""

import sys
import logging
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List
import subprocess

# Add src directory to Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 配置日志
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("gui_runtime_diagnosis")

def simulate_gui_pipeline_execution(test_file: Path, output_file: Path) -> Dict[str, Any]:
    """模拟GUI管道执行过程"""
    logger.info(f"模拟GUI管道执行: {test_file} -> {output_file}")
    
    try:
        # 步骤1: 模拟GUI的配置构建过程
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        logger.debug("步骤1: 构建GUI配置")
        gui_config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False,
            enable_mask=True
        )
        logger.debug(f"GUI配置: {json.dumps(gui_config, indent=2)}")
        
        # 步骤2: 创建执行器
        logger.debug("步骤2: 创建PipelineExecutor")
        executor = create_pipeline_executor(gui_config)
        logger.debug(f"执行器创建成功，包含stages: {[stage.name for stage in executor.stages]}")
        
        # 步骤3: 执行处理
        logger.debug("步骤3: 执行文件处理")
        result = executor.run(str(test_file), str(output_file))
        
        # 步骤4: 分析结果
        logger.debug("步骤4: 分析处理结果")
        analysis = {
            "success": result.success,
            "errors": result.errors,
            "stage_stats": [],
            "total_duration_ms": result.duration_ms
        }
        
        for stats in result.stage_stats:
            stage_info = {
                "stage_name": stats.stage_name,
                "packets_processed": stats.packets_processed,
                "packets_modified": stats.packets_modified,
                "duration_ms": stats.duration_ms,
                "extra_metrics": stats.extra_metrics
            }
            analysis["stage_stats"].append(stage_info)
            logger.info(f"Stage {stats.stage_name}: processed={stats.packets_processed}, modified={stats.packets_modified}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"GUI管道执行失败: {e}")
        return {"error": str(e)}

def run_direct_maskstage_test(test_file: Path, output_file: Path) -> Dict[str, Any]:
    """直接运行MaskStage测试（对比基准）"""
    logger.info(f"直接MaskStage测试: {test_file} -> {output_file}")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 使用与GUI相同的配置
        config = {
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
        
        logger.debug(f"直接测试配置: {json.dumps(config, indent=2)}")
        
        # 创建和初始化Stage
        stage = NewMaskPayloadStage(config)
        if not stage.initialize():
            return {"error": "Stage初始化失败"}
        
        # 执行处理
        stats = stage.process_file(str(test_file), str(output_file))
        
        return {
            "success": True,
            "stage_name": stats.stage_name,
            "packets_processed": stats.packets_processed,
            "packets_modified": stats.packets_modified,
            "duration_ms": stats.duration_ms,
            "extra_metrics": stats.extra_metrics
        }
        
    except Exception as e:
        logger.error(f"直接MaskStage测试失败: {e}")
        return {"error": str(e)}

def analyze_tls_content(pcap_file: Path) -> Dict[str, Any]:
    """分析PCAP文件的TLS内容"""
    logger.info(f"分析TLS内容: {pcap_file}")
    
    try:
        # 使用tshark分析TLS内容
        cmd = [
            "tshark", "-r", str(pcap_file),
            "-Y", "tls",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "tls.record.content_type",
            "-e", "tls.record.length",
            "-E", "header=y",
            "-E", "separator=,"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # 跳过header
                tls_records = []
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 3:
                            frame_num = parts[0]
                            content_type = parts[1]
                            length = parts[2]
                            tls_records.append({
                                "frame": frame_num,
                                "type": content_type,
                                "length": length
                            })
                
                # 统计TLS消息类型
                type_counts = {}
                for record in tls_records:
                    tls_type = record["type"]
                    if tls_type:
                        type_counts[tls_type] = type_counts.get(tls_type, 0) + 1
                
                return {
                    "total_tls_records": len(tls_records),
                    "type_counts": type_counts,
                    "records": tls_records[:10]  # 只返回前10条记录
                }
        
        return {"error": f"tshark分析失败: {result.stderr}"}
        
    except Exception as e:
        logger.error(f"TLS内容分析失败: {e}")
        return {"error": str(e)}

def compare_results(gui_result: Dict[str, Any], direct_result: Dict[str, Any], file_name: str) -> None:
    """对比GUI和直接测试的结果"""
    print(f"\n{'='*80}")
    print(f"文件: {file_name}")
    print(f"{'='*80}")
    
    # GUI结果
    print(f"\n📱 GUI管道执行结果:")
    if "error" in gui_result:
        print(f"   ❌ 错误: {gui_result['error']}")
    else:
        print(f"   成功: {gui_result.get('success', False)}")
        for stage_info in gui_result.get('stage_stats', []):
            print(f"   Stage {stage_info['stage_name']}: processed={stage_info['packets_processed']}, modified={stage_info['packets_modified']}")
    
    # 直接测试结果
    print(f"\n🔧 直接MaskStage测试结果:")
    if "error" in direct_result:
        print(f"   ❌ 错误: {direct_result['error']}")
    else:
        print(f"   成功: {direct_result.get('success', False)}")
        print(f"   Stage {direct_result.get('stage_name', 'Unknown')}: processed={direct_result.get('packets_processed', 0)}, modified={direct_result.get('packets_modified', 0)}")
    
    # 对比分析
    print(f"\n🔍 对比分析:")
    if "error" in gui_result or "error" in direct_result:
        print(f"   ⚠️  存在错误，无法进行有效对比")
    else:
        gui_modified = 0
        for stage_info in gui_result.get('stage_stats', []):
            if 'Mask Payloads' in stage_info['stage_name']:
                gui_modified = stage_info['packets_modified']
                break
        
        direct_modified = direct_result.get('packets_modified', 0)
        
        if gui_modified == direct_modified:
            print(f"   ✅ 掩码包数一致: {gui_modified}")
        else:
            print(f"   ❌ 掩码包数不一致: GUI={gui_modified}, 直接测试={direct_modified}")

def main():
    """主函数"""
    logger.info("开始GUI运行时诊断")
    
    # 测试文件列表（选择几个代表性文件）
    test_files = [
        "tls_1_2-2.pcap",
        "tls_1_2_plainip.pcap", 
        "tls_1_3_0-RTT-2_22_23_mix.pcap",
        "ssl_3.pcap"
    ]
    
    test_dir = project_root / "tests" / "data" / "tls"
    
    for file_name in test_files:
        test_file = test_dir / file_name
        if not test_file.exists():
            logger.warning(f"测试文件不存在: {test_file}")
            continue
        
        with tempfile.TemporaryDirectory(prefix="gui_diagnosis_") as temp_dir:
            temp_path = Path(temp_dir)
            
            # 输出文件
            gui_output = temp_path / f"{test_file.stem}_gui.pcap"
            direct_output = temp_path / f"{test_file.stem}_direct.pcap"
            
            # 分析TLS内容
            tls_analysis = analyze_tls_content(test_file)
            
            # 运行GUI模拟测试
            gui_result = simulate_gui_pipeline_execution(test_file, gui_output)
            
            # 运行直接测试
            direct_result = run_direct_maskstage_test(test_file, direct_output)
            
            # 对比结果
            compare_results(gui_result, direct_result, file_name)
            
            # 显示TLS分析
            print(f"\n📊 TLS内容分析:")
            if "error" in tls_analysis:
                print(f"   ❌ 分析失败: {tls_analysis['error']}")
            else:
                print(f"   TLS记录总数: {tls_analysis.get('total_tls_records', 0)}")
                print(f"   类型统计: {tls_analysis.get('type_counts', {})}")
    
    print(f"\n{'='*80}")
    print("诊断完成")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
