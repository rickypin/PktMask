#!/usr/bin/env python3
"""
用户配置自动迁移工具
确保现有用户配置平滑过渡到新架构
"""

import json
import yaml
import shutil
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class MigrationResult:
    status: str  # 'success', 'error', 'no_config', 'skipped'
    config_path: str
    backup_path: Optional[str] = None
    changes_made: List[str] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.changes_made is None:
            self.changes_made = []

class ConfigMigrator:
    def __init__(self):
        self.migration_rules = {
            # 配置键映射规则
            "processing.dedup_enabled": "processing.stages.dedup.enabled",
            "processing.anon_enabled": "processing.stages.anon.enabled",
            "processing.mask_enabled": "processing.stages.mask.enabled",
            "processing.trim_enabled": "processing.stages.trim.enabled",
            "ui.stage_options": "ui.pipeline_options",

            # 值转换规则
            "processing.dedup_algorithm": {
                "old_values": ["md5", "sha1", "sha256"],
                "new_key": "processing.stages.dedup.algorithm",
                "default": "sha256"
            },
            
            # 工具路径迁移
            "tools.tshark_path": "tools.executable_paths.tshark",
            "tools.editcap_path": "tools.executable_paths.editcap",
        }

        self.backup_suffix = f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def migrate_all_configs(self, project_root: str) -> Dict[str, MigrationResult]:
        """迁移项目中所有用户配置文件"""
        project_path = Path(project_root)
        results = {}
        
        print("🔄 开始配置迁移...")
        
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
                result = self.migrate_single_config(config_path)
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
                    result = self.migrate_single_config(config_file)
                    results[str(config_file)] = result
        
        return results

    def migrate_single_config(self, config_path: Path) -> MigrationResult:
        """迁移单个配置文件"""
        if not config_path.exists():
            return MigrationResult(
                status="no_config",
                config_path=str(config_path)
            )

        print(f"📝 迁移配置文件: {config_path}")

        # 备份原配置
        backup_path = config_path.with_suffix(config_path.suffix + self.backup_suffix)
        try:
            shutil.copy2(config_path, backup_path)
        except Exception as e:
            return MigrationResult(
                status="error",
                config_path=str(config_path),
                error_message=f"备份失败: {e}"
            )

        try:
            # 加载原配置
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)

            if not isinstance(config, dict):
                return MigrationResult(
                    status="error",
                    config_path=str(config_path),
                    backup_path=str(backup_path),
                    error_message="配置文件格式无效"
                )

            # 执行迁移
            migrated_config, changes = self._migrate_config_dict(config)

            # 如果没有变更，跳过保存
            if not changes:
                # 删除不必要的备份
                backup_path.unlink()
                return MigrationResult(
                    status="skipped",
                    config_path=str(config_path),
                    changes_made=["配置已是最新格式，无需迁移"]
                )

            # 保存新配置
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    json.dump(migrated_config, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(migrated_config, f, default_flow_style=False,
                             allow_unicode=True, indent=2)

            return MigrationResult(
                status="success",
                config_path=str(config_path),
                backup_path=str(backup_path),
                changes_made=changes
            )

        except Exception as e:
            # 恢复备份
            try:
                shutil.copy2(backup_path, config_path)
            except:
                pass
            
            return MigrationResult(
                status="error",
                config_path=str(config_path),
                backup_path=str(backup_path),
                error_message=str(e)
            )

    def _migrate_config_dict(self, config: Dict) -> tuple[Dict, List[str]]:
        """迁移配置字典"""
        migrated = config.copy()
        changes = []

        # 应用简单的键重命名
        for old_key, new_key in self.migration_rules.items():
            if isinstance(new_key, str) and self._has_nested_key(config, old_key):
                value = self._get_nested_value(config, old_key)
                self._set_nested_value(migrated, new_key, value)
                self._delete_nested_key(migrated, old_key)
                changes.append(f"重命名配置键: {old_key} -> {new_key}")

        # 应用值转换规则
        for old_key, rule in self.migration_rules.items():
            if isinstance(rule, dict) and "old_values" in rule:
                if self._has_nested_key(config, old_key):
                    old_value = self._get_nested_value(config, old_key)
                    if old_value in rule["old_values"]:
                        new_key = rule["new_key"]
                        self._set_nested_value(migrated, new_key, old_value)
                        self._delete_nested_key(migrated, old_key)
                        changes.append(f"迁移配置值: {old_key} -> {new_key}")

        # 添加新的默认配置
        new_defaults = self._add_new_defaults(migrated)
        changes.extend(new_defaults)

        # 移除废弃的配置
        deprecated_removals = self._remove_deprecated_configs(migrated)
        changes.extend(deprecated_removals)

        return migrated, changes

    def _add_new_defaults(self, config: Dict) -> List[str]:
        """添加新架构的默认配置"""
        changes = []
        
        # 确保新的配置结构存在
        if 'processing' not in config:
            config['processing'] = {}

        if 'stages' not in config['processing']:
            config['processing']['stages'] = {
                'dedup': {'enabled': True, 'algorithm': 'sha256'},
                'anon': {'enabled': True, 'preserve_subnet_structure': True},
                'mask': {'enabled': False, 'preserve_tls_handshake': True}
            }
            changes.append("添加新的处理阶段配置结构")

        # 确保UI配置存在
        if 'ui' not in config:
            config['ui'] = {}
            
        if 'pipeline_options' not in config['ui']:
            config['ui']['pipeline_options'] = {
                'show_progress_details': True,
                'show_statistics': True
            }
            changes.append("添加新的UI管道选项配置")

        # 添加工具路径配置
        if 'tools' not in config:
            config['tools'] = {}
            
        if 'executable_paths' not in config['tools']:
            config['tools']['executable_paths'] = {
                'tshark': 'tshark',
                'editcap': 'editcap'
            }
            changes.append("添加工具可执行文件路径配置")

        return changes

    def _remove_deprecated_configs(self, config: Dict) -> List[str]:
        """移除废弃的配置项"""
        changes = []
        
        deprecated_keys = [
            "legacy.enable_old_pipeline",
            "experimental.use_beta_features", 
            "debug.enable_step_debugging",
            "processing.use_old_stages"
        ]
        
        for deprecated_key in deprecated_keys:
            if self._has_nested_key(config, deprecated_key):
                self._delete_nested_key(config, deprecated_key)
                changes.append(f"移除废弃配置: {deprecated_key}")
        
        return changes

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

    def _set_nested_value(self, d: Dict, key: str, value: Any) -> None:
        """设置嵌套键的值"""
        keys = key.split('.')
        current = d
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def _delete_nested_key(self, d: Dict, key: str) -> None:
        """删除嵌套键"""
        keys = key.split('.')
        current = d
        for k in keys[:-1]:
            if k not in current:
                return
            current = current[k]
        if keys[-1] in current:
            del current[keys[-1]]

    def generate_migration_summary(self, results: Dict[str, MigrationResult]) -> Dict[str, Any]:
        """生成迁移总结报告"""
        total = len(results)
        successful = sum(1 for r in results.values() if r.status == "success")
        skipped = sum(1 for r in results.values() if r.status == "skipped")
        errors = sum(1 for r in results.values() if r.status == "error")
        no_config = sum(1 for r in results.values() if r.status == "no_config")

        summary = {
            "total_configs_processed": total,
            "successful_migrations": successful,
            "skipped_migrations": skipped,
            "migration_errors": errors,
            "no_config_found": no_config,
            "migration_timestamp": datetime.now().isoformat()
        }

        detailed_results = {}
        for config_path, result in results.items():
            detailed_results[config_path] = asdict(result)

        recommendations = []
        if successful > 0:
            recommendations.append(f"✅ 成功迁移 {successful} 个配置文件")
        if skipped > 0:
            recommendations.append(f"⏭️  跳过 {skipped} 个已是最新格式的配置文件")
        if errors > 0:
            recommendations.append(f"❌ {errors} 个配置文件迁移失败，需要手动检查")
        if no_config == total:
            recommendations.append("📝 未发现配置文件，这是正常的（使用默认配置）")

        return {
            "summary": summary,
            "detailed_results": detailed_results,
            "recommendations": recommendations
        }

# 使用示例
if __name__ == "__main__":
    import sys
    
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    migrator = ConfigMigrator()
    
    # 执行迁移
    results = migrator.migrate_all_configs(project_root)
    
    # 生成报告
    report = migrator.generate_migration_summary(results)
    
    print(f"\n📊 迁移结果:")
    print(f"  - 处理配置文件: {report['summary']['total_configs_processed']}")
    print(f"  - 成功迁移: {report['summary']['successful_migrations']}")
    print(f"  - 跳过迁移: {report['summary']['skipped_migrations']}")
    print(f"  - 迁移错误: {report['summary']['migration_errors']}")
    
    print(f"\n💡 建议:")
    for rec in report["recommendations"]:
        print(f"  {rec}")
    
    # 保存报告
    output_file = "reports/config_migration_report.json"
    os.makedirs("reports", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 迁移报告已保存到: {output_file}")
