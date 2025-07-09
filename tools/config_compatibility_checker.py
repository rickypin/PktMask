#!/usr/bin/env python3
"""
用户配置兼容性检查工具
确保现有用户配置能够平滑迁移
"""

import json
import yaml
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class ConfigCompatibilityResult:
    status: str  # 'no_config', 'compatible', 'needs_migration', 'error'
    migration_needed: bool
    changes: List[Dict[str, Any]]
    backup_recommended: bool
    error_message: Optional[str] = None

class ConfigCompatibilityChecker:
    def __init__(self):
        self.compatibility_map = {
            # 旧配置键 -> 新配置键的映射
            "processing.dedup_enabled": "processing.stages.dedup.enabled",
            "processing.anon_enabled": "processing.stages.anon.enabled", 
            "processing.mask_enabled": "processing.stages.mask.enabled",
            "processing.trim_enabled": "processing.stages.trim.enabled",
            "ui.stage_options": "ui.pipeline_options",
            "ui.show_stage_details": "ui.show_pipeline_details",
            
            # 处理器特定配置
            "dedup.algorithm": "processing.stages.dedup.algorithm",
            "anon.preserve_subnet": "processing.stages.anon.preserve_subnet_structure",
            "mask.preserve_tls": "processing.stages.mask.preserve_tls_handshake",
            "trim.threshold": "processing.stages.trim.trim_threshold",
            
            # 工具路径配置
            "tools.tshark_path": "tools.executable_paths.tshark",
            "tools.editcap_path": "tools.executable_paths.editcap",
        }
        
        # 值转换规则
        self.value_transformations = {
            "processing.dedup_algorithm": {
                "old_values": ["md5", "sha1", "sha256"],
                "new_key": "processing.stages.dedup.algorithm",
                "default": "sha256"
            },
            "processing.anon_method": {
                "old_values": ["hash", "random", "hierarchical"],
                "new_key": "processing.stages.anon.anonymization_method", 
                "default": "hierarchical"
            }
        }

    def check_user_configs(self, project_root: str) -> Dict[str, ConfigCompatibilityResult]:
        """检查项目中所有用户配置的兼容性"""
        project_path = Path(project_root)
        results = {}
        
        # 查找可能的配置文件
        config_patterns = [
            "config.json",
            "config.yaml", 
            "config.yml",
            "settings.json",
            "settings.yaml",
            "pktmask.json",
            "pktmask.yaml",
            ".pktmask.json",
            ".pktmask.yaml"
        ]
        
        # 检查项目根目录
        for pattern in config_patterns:
            config_path = project_path / pattern
            if config_path.exists():
                result = self.check_single_config(config_path)
                results[str(config_path)] = result
        
        # 检查用户配置目录
        user_config_dirs = [
            project_path / "config",
            project_path / ".config",
            Path.home() / ".config" / "pktmask",
            Path.home() / ".pktmask"
        ]
        
        for config_dir in user_config_dirs:
            if config_dir.exists():
                for config_file in config_dir.glob("*.{json,yaml,yml}"):
                    result = self.check_single_config(config_file)
                    results[str(config_file)] = result
        
        return results

    def check_single_config(self, config_path: Path) -> ConfigCompatibilityResult:
        """检查单个配置文件的兼容性"""
        if not config_path.exists():
            return ConfigCompatibilityResult(
                status="no_config",
                migration_needed=False,
                changes=[],
                backup_recommended=False
            )

        try:
            # 加载配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)

            if not isinstance(config, dict):
                return ConfigCompatibilityResult(
                    status="error",
                    migration_needed=False,
                    changes=[],
                    backup_recommended=False,
                    error_message="配置文件格式无效"
                )

            return self._analyze_config(config)
            
        except Exception as e:
            return ConfigCompatibilityResult(
                status="error",
                migration_needed=False,
                changes=[],
                backup_recommended=False,
                error_message=str(e)
            )

    def _analyze_config(self, config: Dict) -> ConfigCompatibilityResult:
        """分析配置内容"""
        migration_needed = False
        changes = []

        # 检查需要重命名的键
        for old_key, new_key in self.compatibility_map.items():
            if self._has_nested_key(config, old_key):
                migration_needed = True
                old_value = self._get_nested_value(config, old_key)
                changes.append({
                    "type": "rename_key",
                    "old_key": old_key,
                    "new_key": new_key,
                    "value": old_value,
                    "description": f"重命名配置键: {old_key} -> {new_key}"
                })

        # 检查需要值转换的配置
        for old_key, transform_rule in self.value_transformations.items():
            if self._has_nested_key(config, old_key):
                old_value = self._get_nested_value(config, old_key)
                if old_value in transform_rule["old_values"]:
                    migration_needed = True
                    changes.append({
                        "type": "transform_value",
                        "old_key": old_key,
                        "new_key": transform_rule["new_key"],
                        "old_value": old_value,
                        "new_value": old_value,  # 值保持不变，只是位置改变
                        "description": f"迁移配置值: {old_key} -> {transform_rule['new_key']}"
                    })

        # 检查废弃的配置项
        deprecated_keys = [
            "legacy.enable_old_pipeline",
            "experimental.use_beta_features",
            "debug.enable_step_debugging"
        ]
        
        for deprecated_key in deprecated_keys:
            if self._has_nested_key(config, deprecated_key):
                migration_needed = True
                changes.append({
                    "type": "remove_deprecated",
                    "old_key": deprecated_key,
                    "description": f"移除废弃配置: {deprecated_key}"
                })

        # 检查是否需要添加新的默认配置
        new_defaults_needed = self._check_new_defaults_needed(config)
        if new_defaults_needed:
            migration_needed = True
            for default_config in new_defaults_needed:
                changes.append({
                    "type": "add_default",
                    "new_key": default_config["key"],
                    "new_value": default_config["value"],
                    "description": f"添加新默认配置: {default_config['key']}"
                })

        # 确定状态
        if migration_needed:
            status = "needs_migration"
        else:
            status = "compatible"

        return ConfigCompatibilityResult(
            status=status,
            migration_needed=migration_needed,
            changes=changes,
            backup_recommended=migration_needed
        )

    def _has_nested_key(self, d: Dict, key: str) -> bool:
        """检查嵌套键是否存在"""
        keys = key.split('.')
        current = d
        for k in keys:
            if not isinstance(current, dict) or k not in current:
                return False
            current = current[k]
        return True

    def _get_nested_value(self, d: Dict, key: str) -> Any:
        """获取嵌套键的值"""
        keys = key.split('.')
        current = d
        for k in keys:
            current = current[k]
        return current

    def _check_new_defaults_needed(self, config: Dict) -> List[Dict[str, Any]]:
        """检查是否需要添加新的默认配置"""
        new_defaults = []
        
        # 检查新的处理阶段配置结构
        if not self._has_nested_key(config, "processing.stages"):
            new_defaults.append({
                "key": "processing.stages.dedup.enabled",
                "value": True
            })
            new_defaults.append({
                "key": "processing.stages.anon.enabled", 
                "value": True
            })
            new_defaults.append({
                "key": "processing.stages.mask.enabled",
                "value": False
            })
        
        # 检查新的UI配置
        if not self._has_nested_key(config, "ui.pipeline_options"):
            new_defaults.append({
                "key": "ui.pipeline_options.show_progress_details",
                "value": True
            })
        
        return new_defaults

    def generate_migration_report(self, results: Dict[str, ConfigCompatibilityResult]) -> Dict[str, Any]:
        """生成迁移报告"""
        total_configs = len(results)
        needs_migration = sum(1 for r in results.values() if r.migration_needed)
        compatible = sum(1 for r in results.values() if r.status == "compatible")
        errors = sum(1 for r in results.values() if r.status == "error")
        
        migration_summary = {
            "total_configs_found": total_configs,
            "compatible_configs": compatible,
            "configs_needing_migration": needs_migration,
            "config_errors": errors,
            "migration_complexity": "low" if needs_migration <= 2 else "medium" if needs_migration <= 5 else "high"
        }
        
        detailed_results = {}
        for config_path, result in results.items():
            detailed_results[config_path] = asdict(result)
        
        return {
            "summary": migration_summary,
            "detailed_results": detailed_results,
            "recommendations": self._generate_recommendations(migration_summary, results)
        }

    def _generate_recommendations(self, summary: Dict, results: Dict[str, ConfigCompatibilityResult]) -> List[str]:
        """生成迁移建议"""
        recommendations = []
        
        if summary["configs_needing_migration"] == 0:
            recommendations.append("✅ 所有配置文件都兼容新架构，无需迁移")
        else:
            recommendations.append(f"📋 发现 {summary['configs_needing_migration']} 个配置文件需要迁移")
            recommendations.append("🔄 建议使用自动迁移工具进行配置更新")
            
        if summary["config_errors"] > 0:
            recommendations.append(f"⚠️  发现 {summary['config_errors']} 个配置文件有错误，需要手动检查")
            
        if summary["migration_complexity"] == "high":
            recommendations.append("🚨 迁移复杂度较高，建议分阶段进行")
        else:
            recommendations.append("✨ 迁移复杂度较低，可以一次性完成")
            
        recommendations.append("💾 迁移前请备份所有配置文件")
        
        return recommendations

# 使用示例
if __name__ == "__main__":
    import sys
    
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    checker = ConfigCompatibilityChecker()
    
    print("🔍 检查用户配置兼容性...")
    results = checker.check_user_configs(project_root)
    
    print(f"📊 发现 {len(results)} 个配置文件")
    
    # 生成报告
    report = checker.generate_migration_report(results)
    
    print(f"\n📋 兼容性检查结果:")
    print(f"  - 兼容配置: {report['summary']['compatible_configs']}")
    print(f"  - 需要迁移: {report['summary']['configs_needing_migration']}")
    print(f"  - 配置错误: {report['summary']['config_errors']}")
    print(f"  - 迁移复杂度: {report['summary']['migration_complexity']}")
    
    print(f"\n💡 建议:")
    for rec in report["recommendations"]:
        print(f"  {rec}")
    
    # 保存报告
    output_file = "reports/config_compatibility_report.json"
    os.makedirs("reports", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 兼容性报告已保存到: {output_file}")
