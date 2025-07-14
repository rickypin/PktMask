#!/usr/bin/env python3
"""
GUI主程序与验证脚本配置对比分析工具

用于诊断PktMask GUI主程序与独立验证脚本在处理相同测试数据时产生不一致掩码结果的问题。
严格禁止修改主程序代码，仅用于验证分析。

Author: PktMask Core Team
Version: v1.0 (配置对比分析专用)
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any
import json

# Add src directory to Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 配置日志
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("gui_vs_validator_config_comparison")

def get_gui_config() -> Dict[str, Any]:
    """获取GUI主程序使用的配置"""
    logger.info("分析GUI主程序配置...")
    
    try:
        # 导入GUI服务层配置构建函数
        from pktmask.services.pipeline_service import build_pipeline_config
        
        # 模拟GUI中mask_payload_cb.isChecked()=True的情况
        gui_config = build_pipeline_config(
            enable_anon=False,
            enable_dedup=False, 
            enable_mask=True
        )
        
        logger.info("✅ GUI配置获取成功")
        return gui_config
        
    except Exception as e:
        logger.error(f"❌ GUI配置获取失败: {e}")
        return {}

def get_validator_config() -> Dict[str, Any]:
    """获取验证脚本使用的配置"""
    logger.info("分析验证脚本配置...")
    
    try:
        # 验证脚本中的配置（来自run_maskstage_internal函数）
        validator_config = {
            "dedup": {"enabled": False},
            "anon": {"enabled": False},
            "mask": {
                "enabled": True,
                "protocol": "tls",  # 协议类型
                "mode": "enhanced",  # 使用增强模式
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
        
        logger.info("✅ 验证脚本配置获取成功")
        return validator_config
        
    except Exception as e:
        logger.error(f"❌ 验证脚本配置获取失败: {e}")
        return {}

def compare_configs(gui_config: Dict[str, Any], validator_config: Dict[str, Any]) -> None:
    """对比两个配置的差异"""
    logger.info("开始配置对比分析...")
    
    print("\n" + "="*60)
    print("配置对比分析结果")
    print("="*60)
    
    print("\n1. GUI主程序配置:")
    print(json.dumps(gui_config, indent=2, ensure_ascii=False))
    
    print("\n2. 验证脚本配置:")
    print(json.dumps(validator_config, indent=2, ensure_ascii=False))
    
    print("\n3. 关键差异分析:")
    
    # 检查mask配置差异
    gui_mask = gui_config.get("mask", {})
    validator_mask = validator_config.get("mask", {})
    
    differences = []
    
    # 检查protocol字段
    gui_protocol = gui_mask.get("protocol")
    validator_protocol = validator_mask.get("protocol")
    if gui_protocol != validator_protocol:
        differences.append(f"   - protocol: GUI='{gui_protocol}' vs 验证脚本='{validator_protocol}'")
    
    # 检查marker_config字段
    gui_marker = gui_mask.get("marker_config")
    validator_marker = validator_mask.get("marker_config")
    if gui_marker != validator_marker:
        differences.append(f"   - marker_config: GUI={gui_marker} vs 验证脚本={validator_marker}")
    
    # 检查masker_config字段
    gui_masker = gui_mask.get("masker_config")
    validator_masker = validator_mask.get("masker_config")
    if gui_masker != validator_masker:
        differences.append(f"   - masker_config: GUI={gui_masker} vs 验证脚本={validator_masker}")
    
    if differences:
        print("   ❌ 发现配置差异:")
        for diff in differences:
            print(diff)
    else:
        print("   ✅ 配置完全一致")
    
    print("\n4. 潜在问题分析:")
    
    # 分析GUI配置缺失的字段
    missing_in_gui = []
    if not gui_mask.get("protocol"):
        missing_in_gui.append("protocol")
    if not gui_mask.get("marker_config"):
        missing_in_gui.append("marker_config")
    if not gui_mask.get("masker_config"):
        missing_in_gui.append("masker_config")
    
    if missing_in_gui:
        print(f"   ⚠️  GUI配置缺失字段: {missing_in_gui}")
        print("   这可能导致NewMaskPayloadStage使用默认配置，与验证脚本的显式配置不同")
    else:
        print("   ✅ GUI配置字段完整")

def test_stage_creation() -> None:
    """测试Stage创建过程的差异"""
    logger.info("测试Stage创建过程...")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        # 测试GUI配置创建Stage
        gui_config = get_gui_config()
        gui_mask_config = gui_config.get("mask", {})
        
        print(f"\n5. Stage创建测试:")
        print(f"   GUI mask配置: {gui_mask_config}")
        
        gui_stage = NewMaskPayloadStage(gui_mask_config)
        print(f"   GUI Stage创建成功:")
        print(f"     - protocol: {gui_stage.protocol}")
        print(f"     - mode: {gui_stage.mode}")
        print(f"     - marker_config: {gui_stage.marker_config}")
        print(f"     - masker_config: {gui_stage.masker_config}")
        
        # 测试验证脚本配置创建Stage
        validator_config = get_validator_config()
        validator_mask_config = validator_config.get("mask", {})
        
        validator_stage = NewMaskPayloadStage(validator_mask_config)
        print(f"   验证脚本 Stage创建成功:")
        print(f"     - protocol: {validator_stage.protocol}")
        print(f"     - mode: {validator_stage.mode}")
        print(f"     - marker_config: {validator_stage.marker_config}")
        print(f"     - masker_config: {validator_stage.masker_config}")
        
        # 对比Stage属性
        stage_differences = []
        if gui_stage.protocol != validator_stage.protocol:
            stage_differences.append(f"protocol: {gui_stage.protocol} vs {validator_stage.protocol}")
        if gui_stage.mode != validator_stage.mode:
            stage_differences.append(f"mode: {gui_stage.mode} vs {validator_stage.mode}")
        if gui_stage.marker_config != validator_stage.marker_config:
            stage_differences.append(f"marker_config: {gui_stage.marker_config} vs {validator_stage.marker_config}")
        if gui_stage.masker_config != validator_stage.masker_config:
            stage_differences.append(f"masker_config: {gui_stage.masker_config} vs {validator_stage.masker_config}")
        
        if stage_differences:
            print(f"   ❌ Stage属性差异:")
            for diff in stage_differences:
                print(f"     - {diff}")
        else:
            print(f"   ✅ Stage属性完全一致")
            
    except Exception as e:
        logger.error(f"❌ Stage创建测试失败: {e}")

def main():
    """主函数"""
    logger.info("开始GUI主程序与验证脚本配置对比分析")
    
    # 获取配置
    gui_config = get_gui_config()
    validator_config = get_validator_config()
    
    if not gui_config or not validator_config:
        logger.error("配置获取失败，无法进行对比")
        return
    
    # 对比配置
    compare_configs(gui_config, validator_config)
    
    # 测试Stage创建
    test_stage_creation()
    
    print("\n" + "="*60)
    print("分析完成")
    print("="*60)

if __name__ == "__main__":
    main()
