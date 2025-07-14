#!/usr/bin/env python3
"""
GUI vs 独立调用对比分析工具

专门用于对比GUI调用maskstage与独立调用maskstage的差异，
找出为什么GUI环境下TLS-23掩码失效的真正原因。

使用方法：
    python scripts/debug/gui_vs_standalone_comparison.py <test_pcap_file>
"""

import sys
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def simulate_gui_call(input_file: str, output_file: str) -> Dict[str, Any]:
    """模拟GUI调用maskstage的完整流程"""
    print("🖥️ 模拟GUI调用流程...")
    
    try:
        # 1. 模拟GUI配置生成
        from pktmask.services.pipeline_service import build_pipeline_config
        
        # 模拟GUI复选框状态
        gui_config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False, 
            enable_mask=True
        )
        
        print(f"📋 GUI生成的配置:")
        print(json.dumps(gui_config, indent=2))
        
        # 2. 模拟PipelineExecutor调用
        from pktmask.core.pipeline.executor import PipelineExecutor
        
        executor = PipelineExecutor(gui_config)
        stats = executor.run(input_file, output_file)
        
        return {
            "success": True,
            "config": gui_config,
            "stats": {
                "stage_name": stats.stage_name if hasattr(stats, 'stage_name') else "unknown",
                "packets_processed": stats.packets_processed if hasattr(stats, 'packets_processed') else 0,
                "packets_modified": stats.packets_modified if hasattr(stats, 'packets_modified') else 0,
                "duration_ms": stats.duration_ms if hasattr(stats, 'duration_ms') else 0,
                "stage_stats": [
                    {
                        "stage_name": s.stage_name,
                        "packets_processed": s.packets_processed,
                        "packets_modified": s.packets_modified,
                        "extra_metrics": s.extra_metrics
                    } for s in (stats.stage_stats if hasattr(stats, 'stage_stats') else [])
                ]
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def simulate_standalone_call(input_file: str, output_file: str) -> Dict[str, Any]:
    """模拟独立调用maskstage（类似验证器）"""
    print("🔧 模拟独立调用流程...")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 使用验证器的配置格式（已知工作正常）
        standalone_config = {
            "protocol": "tls",
            "mode": "enhanced", 
            "marker_config": {
                "tls": {  # 验证器使用的格式
                    "preserve_handshake": True,
                    "preserve_application_data": False
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
        
        print(f"📋 独立调用配置:")
        print(json.dumps(standalone_config, indent=2))
        
        stage = NewMaskPayloadStage(standalone_config)
        stage.initialize()
        stats = stage.process_file(input_file, output_file)
        
        return {
            "success": True,
            "config": standalone_config,
            "stats": {
                "stage_name": stats.stage_name,
                "packets_processed": stats.packets_processed,
                "packets_modified": stats.packets_modified,
                "duration_ms": stats.duration_ms,
                "extra_metrics": stats.extra_metrics
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def verify_tls23_masking(pcap_file: str) -> Dict[str, Any]:
    """验证TLS-23掩码效果"""
    try:
        # 使用tls23_marker工具分析
        result = subprocess.run([
            sys.executable, "-m", "pktmask.tools.tls23_marker",
            "--pcap", pcap_file,
            "--no-annotate", "--formats", "json"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)
        
        if result.returncode != 0:
            return {"error": f"tls23_marker failed: {result.stderr}"}
        
        # 解析输出
        output_lines = result.stdout.strip().split('\n')
        json_line = None
        for line in output_lines:
            if line.startswith('{') and 'frames' in line:
                json_line = line
                break
        
        if not json_line:
            return {"error": "No JSON output found"}
        
        data = json.loads(json_line)
        frames = data.get('frames', [])
        
        total_tls23 = len(frames)
        masked_tls23 = 0
        
        for frame in frames:
            # 检查是否被掩码（全零）
            if frame.get('zero_bytes', 0) > 0:
                masked_tls23 += 1
        
        success_rate = masked_tls23 / total_tls23 if total_tls23 > 0 else 0.0
        
        return {
            "total_tls23": total_tls23,
            "masked_tls23": masked_tls23,
            "success_rate": success_rate,
            "frames_sample": frames[:3]  # 前3个样本
        }
        
    except Exception as e:
        return {"error": str(e)}

def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("使用方法: python scripts/debug/gui_vs_standalone_comparison.py <test_pcap_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    if not Path(input_file).exists():
        print(f"❌ 测试文件不存在: {input_file}")
        sys.exit(1)
    
    print("🔍 GUI vs 独立调用对比分析")
    print("="*60)
    print(f"📁 测试文件: {input_file}")
    
    # 创建临时输出目录
    with tempfile.TemporaryDirectory(prefix="gui_vs_standalone_") as temp_dir:
        temp_path = Path(temp_dir)
        
        gui_output = temp_path / "gui_output.pcap"
        standalone_output = temp_path / "standalone_output.pcap"
        
        # 1. GUI调用测试
        print(f"\n📋 步骤1: GUI调用测试")
        gui_result = simulate_gui_call(input_file, str(gui_output))
        
        if gui_result["success"]:
            print("✅ GUI调用成功")
            gui_verification = verify_tls23_masking(str(gui_output))
            print(f"📊 GUI TLS-23掩码效果: {gui_verification.get('success_rate', 0):.2%}")
        else:
            print(f"❌ GUI调用失败: {gui_result['error']}")
            gui_verification = {"error": "GUI调用失败"}
        
        # 2. 独立调用测试
        print(f"\n📋 步骤2: 独立调用测试")
        standalone_result = simulate_standalone_call(input_file, str(standalone_output))
        
        if standalone_result["success"]:
            print("✅ 独立调用成功")
            standalone_verification = verify_tls23_masking(str(standalone_output))
            print(f"📊 独立调用TLS-23掩码效果: {standalone_verification.get('success_rate', 0):.2%}")
        else:
            print(f"❌ 独立调用失败: {standalone_result['error']}")
            standalone_verification = {"error": "独立调用失败"}
        
        # 3. 对比分析
        print(f"\n📊 步骤3: 对比分析")
        print("="*60)
        
        # 配置对比
        print("🔧 配置对比:")
        if gui_result["success"] and standalone_result["success"]:
            gui_mask_config = gui_result["config"].get("mask", {})
            standalone_mask_config = standalone_result["config"]
            
            print("GUI配置:")
            print(json.dumps(gui_mask_config, indent=2))
            print("\n独立调用配置:")
            print(json.dumps(standalone_mask_config, indent=2))
        
        # 处理统计对比
        print(f"\n📈 处理统计对比:")
        if gui_result["success"]:
            gui_stats = gui_result["stats"]
            print(f"GUI: 处理包={gui_stats.get('packets_processed', 0)}, 修改包={gui_stats.get('packets_modified', 0)}")
        
        if standalone_result["success"]:
            standalone_stats = standalone_result["stats"]
            print(f"独立: 处理包={standalone_stats.get('packets_processed', 0)}, 修改包={standalone_stats.get('packets_modified', 0)}")
        
        # TLS-23掩码效果对比
        print(f"\n🎯 TLS-23掩码效果对比:")
        gui_rate = gui_verification.get('success_rate', 0) if 'error' not in gui_verification else 0
        standalone_rate = standalone_verification.get('success_rate', 0) if 'error' not in standalone_verification else 0
        
        print(f"GUI掩码成功率: {gui_rate:.2%}")
        print(f"独立调用掩码成功率: {standalone_rate:.2%}")
        
        # 结论
        print(f"\n💡 分析结论:")
        if abs(gui_rate - standalone_rate) < 0.1:
            print("✅ GUI和独立调用的掩码效果基本一致")
            print("💭 问题可能不在maskstage本身，而在其他环节")
        else:
            print("❌ GUI和独立调用的掩码效果存在显著差异")
            if gui_rate < standalone_rate:
                print("🔍 GUI环境下掩码效果更差，需要深入调查GUI特有的处理流程")
            else:
                print("🔍 独立调用掩码效果更差，需要检查配置差异")
        
        # 保存详细结果
        comparison_result = {
            "input_file": input_file,
            "gui_result": gui_result,
            "standalone_result": standalone_result,
            "gui_verification": gui_verification,
            "standalone_verification": standalone_verification,
            "analysis": {
                "gui_success_rate": gui_rate,
                "standalone_success_rate": standalone_rate,
                "rate_difference": abs(gui_rate - standalone_rate),
                "conclusion": "consistent" if abs(gui_rate - standalone_rate) < 0.1 else "different"
            }
        }
        
        result_file = temp_path / "comparison_result.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(comparison_result, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细结果已保存: {result_file}")
        
        # 复制结果文件到当前目录
        import shutil
        final_result_file = Path("gui_vs_standalone_comparison_result.json")
        shutil.copy2(result_file, final_result_file)
        print(f"📄 结果副本: {final_result_file}")

if __name__ == "__main__":
    main()
