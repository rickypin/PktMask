#!/usr/bin/env python3
"""
GUI真实环境测试脚本

模拟GUI的真实运行环境，包括完整的三阶段管道（Dedup + Anon + Mask）
用于诊断为什么GUI实际运行时显示"masked 0 pkts"

Author: PktMask Core Team
Version: v1.0 (GUI真实环境测试专用)
"""

import sys
import logging
import tempfile
import os
from pathlib import Path
from typing import Dict, Any

# Add src directory to Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 配置日志
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("gui_real_environment_test")

def simulate_gui_real_execution(test_file: Path, output_file: Path) -> Dict[str, Any]:
    """完全模拟GUI的真实执行环境"""
    logger.info(f"模拟GUI真实执行: {test_file} -> {output_file}")
    
    try:
        # 步骤1: 使用GUI完全相同的配置构建方式
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        logger.debug("步骤1: 构建GUI真实配置（包含所有三个stage）")
        # 模拟GUI中所有复选框都选中的情况
        gui_config = build_pipeline_config(
            enable_anon=True,   # 对应 mask_ip_cb.isChecked()
            enable_dedup=True,  # 对应 dedup_packet_cb.isChecked()
            enable_mask=True    # 对应 mask_payload_cb.isChecked()
        )
        logger.debug(f"GUI真实配置: {gui_config}")
        
        # 步骤2: 使用GUI完全相同的执行器创建方式
        logger.debug("步骤2: 创建GUI真实PipelineExecutor")
        executor = create_pipeline_executor(gui_config)
        logger.debug(f"执行器创建成功，包含stages: {[stage.name for stage in executor.stages]}")
        
        # 步骤3: 使用GUI完全相同的执行方式
        logger.debug("步骤3: 执行GUI真实文件处理")
        
        # 模拟GUI中的进度回调函数
        def progress_callback(event_type, data):
            logger.debug(f"进度回调: {event_type} - {data}")
        
        # 使用与GUI完全相同的调用方式
        result = executor.run(str(test_file), str(output_file), progress_cb=lambda stage, stats: progress_callback('stage_progress', {'stage': stage, 'stats': stats}))
        
        # 步骤4: 分析结果
        logger.debug("步骤4: 分析GUI真实处理结果")
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
        logger.error(f"GUI真实执行失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {"error": str(e)}

def analyze_stage_execution_order(test_file: Path, output_file: Path) -> None:
    """分析stage执行顺序对掩码结果的影响"""
    logger.info(f"分析stage执行顺序影响: {test_file}")
    
    with tempfile.TemporaryDirectory(prefix="stage_order_test_") as temp_dir:
        temp_path = Path(temp_dir)
        
        # 测试1: 只运行MaskStage
        logger.info("测试1: 只运行MaskStage")
        mask_only_output = temp_path / f"{test_file.stem}_mask_only.pcap"
        try:
            from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
            
            mask_only_config = build_pipeline_config(
                enable_anon=False,
                enable_dedup=False,
                enable_mask=True
            )
            
            mask_only_executor = create_pipeline_executor(mask_only_config)
            mask_only_result = mask_only_executor.run(str(test_file), str(mask_only_output))
            
            mask_only_stats = mask_only_result.stage_stats[0] if mask_only_result.stage_stats else None
            if mask_only_stats:
                logger.info(f"只运行MaskStage: processed={mask_only_stats.packets_processed}, modified={mask_only_stats.packets_modified}")
            
        except Exception as e:
            logger.error(f"只运行MaskStage失败: {e}")
        
        # 测试2: 运行Dedup + Mask
        logger.info("测试2: 运行Dedup + Mask")
        dedup_mask_output = temp_path / f"{test_file.stem}_dedup_mask.pcap"
        try:
            dedup_mask_config = build_pipeline_config(
                enable_anon=False,
                enable_dedup=True,
                enable_mask=True
            )
            
            dedup_mask_executor = create_pipeline_executor(dedup_mask_config)
            dedup_mask_result = dedup_mask_executor.run(str(test_file), str(dedup_mask_output))
            
            for stats in dedup_mask_result.stage_stats:
                logger.info(f"Dedup+Mask - {stats.stage_name}: processed={stats.packets_processed}, modified={stats.packets_modified}")
            
        except Exception as e:
            logger.error(f"运行Dedup+Mask失败: {e}")
        
        # 测试3: 运行Anon + Mask
        logger.info("测试3: 运行Anon + Mask")
        anon_mask_output = temp_path / f"{test_file.stem}_anon_mask.pcap"
        try:
            anon_mask_config = build_pipeline_config(
                enable_anon=True,
                enable_dedup=False,
                enable_mask=True
            )
            
            anon_mask_executor = create_pipeline_executor(anon_mask_config)
            anon_mask_result = anon_mask_executor.run(str(test_file), str(anon_mask_output))
            
            for stats in anon_mask_result.stage_stats:
                logger.info(f"Anon+Mask - {stats.stage_name}: processed={stats.packets_processed}, modified={stats.packets_modified}")
            
        except Exception as e:
            logger.error(f"运行Anon+Mask失败: {e}")
        
        # 测试4: 运行完整管道（Dedup + Anon + Mask）
        logger.info("测试4: 运行完整管道（Dedup + Anon + Mask）")
        full_pipeline_output = temp_path / f"{test_file.stem}_full_pipeline.pcap"
        try:
            full_config = build_pipeline_config(
                enable_anon=True,
                enable_dedup=True,
                enable_mask=True
            )
            
            full_executor = create_pipeline_executor(full_config)
            full_result = full_executor.run(str(test_file), str(full_pipeline_output))
            
            for stats in full_result.stage_stats:
                logger.info(f"完整管道 - {stats.stage_name}: processed={stats.packets_processed}, modified={stats.packets_modified}")
            
        except Exception as e:
            logger.error(f"运行完整管道失败: {e}")

def check_file_integrity_after_stages(test_file: Path) -> None:
    """检查文件在各个stage处理后的完整性"""
    logger.info(f"检查文件完整性: {test_file}")
    
    try:
        # 使用tshark检查原始文件
        import subprocess
        
        cmd = ["tshark", "-r", str(test_file), "-T", "fields", "-e", "frame.number", "-e", "tcp.len", "-e", "tls.record.content_type"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            tcp_packets = [line for line in lines if line.strip() and '\t' in line]
            tls_packets = [line for line in tcp_packets if line.split('\t')[2]]  # 有TLS内容类型的包
            
            logger.info(f"原始文件分析:")
            logger.info(f"  总包数: {len(lines)}")
            logger.info(f"  TCP包数: {len(tcp_packets)}")
            logger.info(f"  TLS包数: {len(tls_packets)}")
            
            # 显示前几个TLS包的详细信息
            for i, line in enumerate(tls_packets[:5]):
                parts = line.split('\t')
                if len(parts) >= 3:
                    frame_num, tcp_len, tls_type = parts[0], parts[1], parts[2]
                    logger.info(f"  TLS包 {i+1}: Frame={frame_num}, TCP_len={tcp_len}, TLS_type={tls_type}")
        
    except Exception as e:
        logger.error(f"文件完整性检查失败: {e}")

def main():
    """主函数"""
    logger.info("开始GUI真实环境测试")
    
    # 测试文件列表（选择几个有代表性的文件）
    test_files = [
        "tls_1_2-2.pcap",
        "tls_1_2_plainip.pcap",
        "ssl_3.pcap"
    ]
    
    test_dir = project_root / "tests" / "data" / "tls"
    
    for file_name in test_files:
        test_file = test_dir / file_name
        if not test_file.exists():
            logger.warning(f"测试文件不存在: {test_file}")
            continue
        
        print(f"\n{'='*80}")
        print(f"测试文件: {file_name}")
        print(f"{'='*80}")
        
        # 检查文件完整性
        check_file_integrity_after_stages(test_file)
        
        with tempfile.TemporaryDirectory(prefix="gui_real_test_") as temp_dir:
            temp_path = Path(temp_dir)
            
            # GUI真实环境测试
            gui_output = temp_path / f"{test_file.stem}_gui_real.pcap"
            gui_result = simulate_gui_real_execution(test_file, gui_output)
            
            print(f"\n📱 GUI真实环境执行结果:")
            if "error" in gui_result:
                print(f"   ❌ 错误: {gui_result['error']}")
            else:
                print(f"   成功: {gui_result.get('success', False)}")
                for stage_info in gui_result.get('stage_stats', []):
                    print(f"   Stage {stage_info['stage_name']}: processed={stage_info['packets_processed']}, modified={stage_info['packets_modified']}")
            
            # Stage执行顺序分析
            print(f"\n🔍 Stage执行顺序影响分析:")
            analyze_stage_execution_order(test_file, temp_path / f"{test_file.stem}_order_test.pcap")
    
    print(f"\n{'='*80}")
    print("GUI真实环境测试完成")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
