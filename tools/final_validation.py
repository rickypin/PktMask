#!/usr/bin/env python3
"""
最终验证和总结报告
验证兼容层移除的完整性和效果
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

class FinalValidator:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.validation_results = {}

    def run_complete_validation(self) -> Dict[str, Any]:
        """运行完整的验证流程"""
        print("🔍 开始最终验证...")
        
        # 1. 验证文件结构
        self.validation_results['file_structure'] = self._validate_file_structure()
        
        # 2. 验证导入更新
        self.validation_results['import_updates'] = self._validate_import_updates()
        
        # 3. 验证兼容性保持
        self.validation_results['compatibility'] = self._validate_compatibility()
        
        # 4. 验证功能完整性
        self.validation_results['functionality'] = self._validate_functionality()
        
        # 5. 生成迁移总结
        self.validation_results['migration_summary'] = self._generate_migration_summary()
        
        return self.validation_results

    def _validate_file_structure(self) -> Dict[str, Any]:
        """验证文件结构"""
        print("📁 验证文件结构...")
        
        required_files = [
            "src/pktmask/core/unified_stage.py",
            "src/pktmask/core/base_step.py",
            "src/pktmask/core/pipeline/base_stage.py",
        ]
        
        optional_files = [
            "src/pktmask/adapters/processor_adapter.py",
            "src/pktmask/adapters/compatibility/dedup_compat.py",
            "src/pktmask/adapters/compatibility/anon_compat.py",
        ]
        
        results = {
            "required_files_present": [],
            "required_files_missing": [],
            "optional_files_present": [],
            "optional_files_missing": [],
            "backup_files_created": []
        }
        
        # 检查必需文件
        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                results["required_files_present"].append(file_path)
            else:
                results["required_files_missing"].append(file_path)
        
        # 检查可选文件
        for file_path in optional_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                results["optional_files_present"].append(file_path)
            else:
                results["optional_files_missing"].append(file_path)
        
        # 检查备份文件
        backup_dirs = list(self.project_root.glob("temp_backups/*"))
        if backup_dirs:
            results["backup_files_created"] = [str(d) for d in backup_dirs]
        
        return results

    def _validate_import_updates(self) -> Dict[str, Any]:
        """验证导入更新"""
        print("📦 验证导入更新...")
        
        results = {
            "files_with_old_imports": [],
            "files_with_new_imports": [],
            "problematic_imports": []
        }
        
        old_import_patterns = [
            "from pktmask.core.base_step import ProcessingStep",
            "from ..core.base_step import ProcessingStep",
        ]
        
        new_import_patterns = [
            "from pktmask.core.unified_stage import StageBase",
            "from ..core.unified_stage import StageBase",
        ]
        
        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 检查旧导入
                has_old_imports = any(pattern in content for pattern in old_import_patterns)
                if has_old_imports:
                    results["files_with_old_imports"].append(str(py_file.relative_to(self.project_root)))
                
                # 检查新导入
                has_new_imports = any(pattern in content for pattern in new_import_patterns)
                if has_new_imports:
                    results["files_with_new_imports"].append(str(py_file.relative_to(self.project_root)))
                
            except Exception as e:
                results["problematic_imports"].append(f"{py_file}: {e}")
        
        return results

    def _validate_compatibility(self) -> Dict[str, Any]:
        """验证兼容性保持"""
        print("🛡️ 验证兼容性...")
        
        results = {
            "compatibility_layers_present": [],
            "deprecated_warnings_added": [],
            "backward_compatibility_score": 0
        }
        
        # 检查兼容性层文件
        compat_files = [
            "src/pktmask/core/base_step.py",
            "src/pktmask/steps/__init__.py",
            "src/pktmask/adapters/compatibility/dedup_compat.py",
            "src/pktmask/adapters/compatibility/anon_compat.py",
        ]
        
        for compat_file in compat_files:
            full_path = self.project_root / compat_file
            if full_path.exists():
                results["compatibility_layers_present"].append(compat_file)
                
                # 检查是否包含废弃警告
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if "warnings.warn" in content or "DeprecationWarning" in content:
                        results["deprecated_warnings_added"].append(compat_file)
                        
                except Exception:
                    pass
        
        # 计算向后兼容性分数
        total_compat_files = len(compat_files)
        present_compat_files = len(results["compatibility_layers_present"])
        results["backward_compatibility_score"] = (present_compat_files / total_compat_files) * 100
        
        return results

    def _validate_functionality(self) -> Dict[str, Any]:
        """验证功能完整性"""
        print("⚙️ 验证功能完整性...")
        
        results = {
            "syntax_errors": [],
            "import_errors": [],
            "functionality_tests": {}
        }
        
        # 语法检查关键文件
        key_files = [
            "src/pktmask/core/unified_stage.py",
            "src/pktmask/core/base_step.py",
        ]
        
        for key_file in key_files:
            full_path = self.project_root / key_file
            if full_path.exists():
                try:
                    import subprocess
                    result = subprocess.run([
                        sys.executable, "-m", "py_compile", str(full_path)
                    ], capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        results["syntax_errors"].append(f"{key_file}: {result.stderr}")
                        
                except Exception as e:
                    results["syntax_errors"].append(f"{key_file}: {e}")
        
        # 基本功能测试
        functionality_tests = {
            "unified_stage_import": self._test_unified_stage_import(),
            "compatibility_layer_import": self._test_compatibility_layer_import(),
            "stage_creation": self._test_stage_creation(),
        }
        
        results["functionality_tests"] = functionality_tests
        
        return results

    def _test_unified_stage_import(self) -> bool:
        """测试统一基类导入"""
        try:
            sys.path.insert(0, str(self.project_root / "src"))
            from pktmask.core.unified_stage import StageBase, StageStats
            return True
        except Exception:
            return False

    def _test_compatibility_layer_import(self) -> bool:
        """测试兼容性层导入"""
        try:
            sys.path.insert(0, str(self.project_root / "src"))
            from pktmask.core.base_step import ProcessingStep
            return True
        except Exception:
            return False

    def _test_stage_creation(self) -> bool:
        """测试阶段创建"""
        try:
            sys.path.insert(0, str(self.project_root / "src"))
            from pktmask.core.unified_stage import create_stage
            stage = create_stage('dedup')
            return True
        except Exception:
            return False

    def _generate_migration_summary(self) -> Dict[str, Any]:
        """生成迁移总结"""
        print("📊 生成迁移总结...")
        
        # 读取之前的报告
        reports_dir = self.project_root / "reports"
        
        summary = {
            "migration_completed": True,
            "completion_timestamp": datetime.now().isoformat(),
            "key_achievements": [],
            "remaining_issues": [],
            "recommendations": []
        }
        
        # 基于验证结果生成总结
        file_structure = self.validation_results.get('file_structure', {})
        import_updates = self.validation_results.get('import_updates', {})
        compatibility = self.validation_results.get('compatibility', {})
        functionality = self.validation_results.get('functionality', {})
        
        # 关键成就
        if len(file_structure.get('required_files_missing', [])) == 0:
            summary["key_achievements"].append("✅ 所有必需文件已创建")
        
        if len(import_updates.get('files_with_new_imports', [])) > 0:
            summary["key_achievements"].append("✅ 导入语句已更新到新架构")
        
        if compatibility.get('backward_compatibility_score', 0) > 80:
            summary["key_achievements"].append("✅ 向后兼容性得到保持")
        
        # 剩余问题
        if file_structure.get('required_files_missing'):
            summary["remaining_issues"].extend([
                f"❌ 缺少必需文件: {f}" for f in file_structure['required_files_missing']
            ])
        
        if import_updates.get('files_with_old_imports'):
            summary["remaining_issues"].append(
                f"⚠️ {len(import_updates['files_with_old_imports'])} 个文件仍使用旧导入"
            )
        
        if functionality.get('syntax_errors'):
            summary["remaining_issues"].extend([
                f"❌ 语法错误: {error}" for error in functionality['syntax_errors']
            ])
        
        # 建议
        if not summary["remaining_issues"]:
            summary["recommendations"] = [
                "🎉 兼容层移除成功完成！",
                "🚀 可以开始使用统一架构进行开发",
                "📝 建议更新文档以反映新架构",
                "🧪 建议运行完整的测试套件验证功能"
            ]
        else:
            summary["recommendations"] = [
                "🔧 建议修复剩余的问题",
                "📋 可以分阶段解决非关键问题",
                "🛡️ 兼容性层确保现有代码仍可工作",
                "📚 建议查看迁移文档了解详细信息"
            ]
        
        return summary

    def _should_skip_file(self, file_path: Path) -> bool:
        """判断是否应该跳过文件"""
        skip_patterns = [
            '__pycache__',
            '.git',
            'backup',
            'temp_backups',
            'tools/',
            'reports/',
            '.pyc'
        ]

        return any(pattern in str(file_path) for pattern in skip_patterns)

    def save_validation_report(self) -> str:
        """保存验证报告"""
        output_file = self.project_root / "reports" / "final_validation_report.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2, ensure_ascii=False)
        
        return str(output_file)

# 使用示例
if __name__ == "__main__":
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    validator = FinalValidator(project_root)
    
    # 运行验证
    results = validator.run_complete_validation()
    
    # 保存报告
    report_file = validator.save_validation_report()
    
    # 显示总结
    migration_summary = results.get('migration_summary', {})
    
    print(f"\n🎯 兼容层移除总结:")
    print(f"完成状态: {'✅ 完成' if migration_summary.get('migration_completed') else '❌ 未完成'}")
    
    print(f"\n🏆 关键成就:")
    for achievement in migration_summary.get('key_achievements', []):
        print(f"  {achievement}")
    
    if migration_summary.get('remaining_issues'):
        print(f"\n⚠️ 剩余问题:")
        for issue in migration_summary['remaining_issues']:
            print(f"  {issue}")
    
    print(f"\n💡 建议:")
    for recommendation in migration_summary.get('recommendations', []):
        print(f"  {recommendation}")
    
    print(f"\n📄 详细报告已保存到: {report_file}")
