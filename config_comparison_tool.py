#!/usr/bin/env python3
"""
配置对比验证工具
用于对比 GUI 和脚本调用 maskstage 时的配置差异
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

# 添加src目录到Python路径
script_dir = Path(__file__).parent.absolute()
src_path = script_dir / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ConfigDifference:
    """配置差异记录"""
    path: str
    gui_value: Any
    script_value: Any
    impact: str
    severity: str  # 'critical', 'warning', 'info'

class ConfigComparator:
    """配置对比器"""
    
    def __init__(self):
        self.differences: List[ConfigDifference] = []
    
    def get_gui_config(self) -> Dict[str, Any]:
        """获取 GUI 配置"""
        try:
            from pktmask.services.pipeline_service import build_pipeline_config
            config = build_pipeline_config(
                enable_anon=False,
                enable_dedup=False,
                enable_mask=True
            )
            return config.get('mask', {})
        except Exception as e:
            logger.error(f"获取 GUI 配置失败: {e}")
            return {}
    
    def get_script_pipeline_config(self) -> Dict[str, Any]:
        """获取脚本 Pipeline 模式配置"""
        return {
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
    
    def get_script_direct_config(self) -> Dict[str, Any]:
        """获取脚本 Direct 模式配置"""
        return {
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
    
    def compare_configs(self) -> List[ConfigDifference]:
        """对比所有配置"""
        gui_config = self.get_gui_config()
        script_pipeline_config = self.get_script_pipeline_config()
        script_direct_config = self.get_script_direct_config()
        
        logger.info("=== 配置对比分析 ===")
        logger.info(f"GUI 配置: {json.dumps(gui_config, indent=2, ensure_ascii=False)}")
        logger.info(f"脚本 Pipeline 配置: {json.dumps(script_pipeline_config, indent=2, ensure_ascii=False)}")
        logger.info(f"脚本 Direct 配置: {json.dumps(script_direct_config, indent=2, ensure_ascii=False)}")
        
        # 对比 GUI vs 脚本 Pipeline
        self._compare_two_configs("GUI", gui_config, "Script-Pipeline", script_pipeline_config)
        
        # 对比 GUI vs 脚本 Direct
        self._compare_two_configs("GUI", gui_config, "Script-Direct", script_direct_config)
        
        return self.differences
    
    def _compare_two_configs(self, name1: str, config1: Dict, name2: str, config2: Dict, path: str = ""):
        """递归对比两个配置"""
        all_keys = set(config1.keys()) | set(config2.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            
            if key not in config1:
                self.differences.append(ConfigDifference(
                    path=current_path,
                    gui_value=None,
                    script_value=config2[key],
                    impact=f"{name1} 缺少配置项",
                    severity="warning"
                ))
            elif key not in config2:
                self.differences.append(ConfigDifference(
                    path=current_path,
                    gui_value=config1[key],
                    script_value=None,
                    impact=f"{name2} 缺少配置项",
                    severity="warning"
                ))
            elif isinstance(config1[key], dict) and isinstance(config2[key], dict):
                # 递归对比嵌套字典
                self._compare_two_configs(name1, config1[key], name2, config2[key], current_path)
            elif config1[key] != config2[key]:
                # 判断影响严重程度
                severity = self._assess_severity(current_path, config1[key], config2[key])
                impact = self._assess_impact(current_path, config1[key], config2[key])
                
                self.differences.append(ConfigDifference(
                    path=current_path,
                    gui_value=config1[key],
                    script_value=config2[key],
                    impact=impact,
                    severity=severity
                ))
    
    def _assess_severity(self, path: str, value1: Any, value2: Any) -> str:
        """评估配置差异的严重程度"""
        # TLS-23 相关配置是关键配置
        if "application_data" in path.lower():
            return "critical"
        elif "marker_config" in path:
            return "critical"
        elif "preserve" in path:
            return "critical"
        else:
            return "warning"
    
    def _assess_impact(self, path: str, value1: Any, value2: Any) -> str:
        """评估配置差异的影响"""
        if "application_data" in path.lower():
            return "直接影响 TLS-23 消息体的掩码行为"
        elif "marker_config" in path:
            return "影响 Marker 模块的规则生成"
        elif "preserve" in path:
            return "影响消息保留策略"
        else:
            return "一般配置差异"
    
    def generate_report(self) -> str:
        """生成对比报告"""
        differences = self.compare_configs()
        
        report = ["# 配置对比分析报告\n"]
        
        # 按严重程度分组
        critical_diffs = [d for d in differences if d.severity == "critical"]
        warning_diffs = [d for d in differences if d.severity == "warning"]
        
        if critical_diffs:
            report.append("## 🚨 关键配置差异\n")
            for diff in critical_diffs:
                report.append(f"**路径**: `{diff.path}`")
                report.append(f"- GUI 值: `{diff.gui_value}`")
                report.append(f"- 脚本值: `{diff.script_value}`")
                report.append(f"- 影响: {diff.impact}")
                report.append("")
        
        if warning_diffs:
            report.append("## ⚠️ 一般配置差异\n")
            for diff in warning_diffs:
                report.append(f"**路径**: `{diff.path}`")
                report.append(f"- GUI 值: `{diff.gui_value}`")
                report.append(f"- 脚本值: `{diff.script_value}`")
                report.append(f"- 影响: {diff.impact}")
                report.append("")
        
        if not differences:
            report.append("## ✅ 配置完全一致\n")
        
        return "\n".join(report)

def main():
    """主函数"""
    comparator = ConfigComparator()
    report = comparator.generate_report()
    
    # 输出到控制台
    print(report)
    
    # 保存到文件
    output_file = Path("config_comparison_report.md")
    output_file.write_text(report, encoding='utf-8')
    logger.info(f"报告已保存到: {output_file}")

class MiddlewareCheckpoint:
    """中间结果检查点"""

    def __init__(self, test_file: Path):
        self.test_file = test_file
        self.checkpoints = {}

    def check_stage_creation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查点1: Stage 创建和配置传递"""
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
            stage = NewMaskPayloadStage(config)

            result = {
                "success": True,
                "stage_protocol": stage.protocol,
                "stage_mode": stage.mode,
                "marker_config": stage.marker_config,
                "masker_config": stage.masker_config
            }

            self.checkpoints["stage_creation"] = result
            return result

        except Exception as e:
            result = {"success": False, "error": str(e)}
            self.checkpoints["stage_creation"] = result
            return result

    def check_marker_initialization(self, stage) -> Dict[str, Any]:
        """检查点2: Marker 初始化和配置解析"""
        try:
            stage.initialize()
            marker = stage.marker

            result = {
                "success": True,
                "marker_type": type(marker).__name__,
                "preserve_config": getattr(marker, 'preserve_config', {}),
                "tshark_path": getattr(marker, 'tshark_path', None)
            }

            self.checkpoints["marker_initialization"] = result
            return result

        except Exception as e:
            result = {"success": False, "error": str(e)}
            self.checkpoints["marker_initialization"] = result
            return result

    def check_rule_generation(self, stage) -> Dict[str, Any]:
        """检查点3: 规则生成过程"""
        try:
            # 模拟规则生成（不实际处理文件）
            marker = stage.marker

            # 检查关键配置
            preserve_config = getattr(marker, 'preserve_config', {})
            application_data_config = preserve_config.get('application_data', None)

            result = {
                "success": True,
                "preserve_config": preserve_config,
                "application_data_setting": application_data_config,
                "will_mask_tls23": not application_data_config if application_data_config is not None else "unknown"
            }

            self.checkpoints["rule_generation"] = result
            return result

        except Exception as e:
            result = {"success": False, "error": str(e)}
            self.checkpoints["rule_generation"] = result
            return result

    def run_all_checkpoints(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行所有检查点"""
        logger.info(f"=== 开始中间结果检查 ===")

        # 检查点1: Stage 创建
        stage_result = self.check_stage_creation(config)
        if not stage_result["success"]:
            return self.checkpoints

        # 重新创建 Stage 实例用于后续检查
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        stage = NewMaskPayloadStage(config)

        # 检查点2: Marker 初始化
        marker_result = self.check_marker_initialization(stage)
        if not marker_result["success"]:
            return self.checkpoints

        # 检查点3: 规则生成配置
        rule_result = self.check_rule_generation(stage)

        return self.checkpoints

if __name__ == "__main__":
    main()
