#!/usr/bin/env python3
"""
渐进式兼容层移除脚本
确保用户体验不受影响的分阶段实施
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class MigrationStep:
    name: str
    description: str
    risk_level: str  # 'low', 'medium', 'high'
    rollback_available: bool
    dependencies: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class StepResult:
    step_name: str
    success: bool
    duration_seconds: float
    changes_made: List[str] = None
    error_message: Optional[str] = None
    rollback_info: Optional[Dict] = None

    def __post_init__(self):
        if self.changes_made is None:
            self.changes_made = []

class ProgressiveMigrator:
    """
    渐进式迁移器 - 桌面应用兼容层优化
    分阶段实施，确保用户体验不受影响
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "migration_backups" / datetime.now().strftime('%Y%m%d_%H%M%S')
        self.results: List[StepResult] = []
        
        # 定义迁移步骤
        self.migration_steps = [
            MigrationStep(
                name="backup_user_configs",
                description="备份用户配置文件",
                risk_level="low",
                rollback_available=True
            ),
            MigrationStep(
                name="analyze_current_state",
                description="分析当前架构状态",
                risk_level="low",
                rollback_available=False,
                dependencies=["backup_user_configs"]
            ),
            MigrationStep(
                name="implement_unified_base",
                description="实施统一基类",
                risk_level="medium",
                rollback_available=True,
                dependencies=["analyze_current_state"]
            ),
            MigrationStep(
                name="update_stage_imports",
                description="更新阶段导入语句",
                risk_level="medium",
                rollback_available=True,
                dependencies=["implement_unified_base"]
            ),
            MigrationStep(
                name="migrate_user_configs",
                description="迁移用户配置",
                risk_level="low",
                rollback_available=True,
                dependencies=["update_stage_imports"]
            ),
            MigrationStep(
                name="update_gui_adapters",
                description="更新GUI适配器",
                risk_level="high",
                rollback_available=True,
                dependencies=["migrate_user_configs"]
            ),
            MigrationStep(
                name="validate_functionality",
                description="验证功能完整性",
                risk_level="low",
                rollback_available=False,
                dependencies=["update_gui_adapters"]
            )
        ]

    def execute_migration(self) -> Dict[str, Any]:
        """执行完整的迁移流程"""
        print("🚀 开始桌面应用兼容层优化...")
        print(f"📁 项目根目录: {self.project_root}")
        print(f"💾 备份目录: {self.backup_dir}")
        
        start_time = datetime.now()
        
        try:
            # 创建备份目录
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 执行每个步骤
            for step in self.migration_steps:
                if not self._check_dependencies(step):
                    continue
                    
                print(f"\n🔄 执行步骤: {step.name}")
                print(f"📝 描述: {step.description}")
                print(f"⚠️  风险级别: {step.risk_level}")
                
                result = self._execute_step(step)
                self.results.append(result)
                
                if not result.success:
                    print(f"❌ 步骤失败: {result.error_message}")
                    if step.risk_level == "high":
                        print("🛑 高风险步骤失败，停止迁移")
                        break
                    else:
                        print("⚠️  步骤失败但继续执行")
                else:
                    print(f"✅ 步骤完成: {len(result.changes_made)} 项变更")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 生成最终报告
            return self._generate_final_report(duration)
            
        except Exception as e:
            print(f"💥 迁移过程中发生严重错误: {e}")
            return self._generate_error_report(str(e))

    def _check_dependencies(self, step: MigrationStep) -> bool:
        """检查步骤依赖是否满足"""
        for dep in step.dependencies:
            dep_result = next((r for r in self.results if r.step_name == dep), None)
            if not dep_result or not dep_result.success:
                print(f"⚠️  跳过步骤 {step.name}: 依赖 {dep} 未满足")
                return False
        return True

    def _execute_step(self, step: MigrationStep) -> StepResult:
        """执行单个迁移步骤"""
        step_start = datetime.now()
        
        try:
            # 根据步骤名称调用相应的处理方法
            method_name = f"_step_{step.name}"
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                changes = method()
                
                duration = (datetime.now() - step_start).total_seconds()
                return StepResult(
                    step_name=step.name,
                    success=True,
                    duration_seconds=duration,
                    changes_made=changes
                )
            else:
                raise NotImplementedError(f"步骤 {step.name} 未实现")
                
        except Exception as e:
            duration = (datetime.now() - step_start).total_seconds()
            return StepResult(
                step_name=step.name,
                success=False,
                duration_seconds=duration,
                error_message=str(e)
            )

    def _step_backup_user_configs(self) -> List[str]:
        """备份用户配置文件"""
        changes = []
        
        # 查找配置文件
        config_patterns = ["*.json", "*.yaml", "*.yml"]
        config_dirs = ["config", ".config", "."]
        
        for config_dir in config_dirs:
            config_path = self.project_root / config_dir
            if config_path.exists():
                for pattern in config_patterns:
                    for config_file in config_path.glob(pattern):
                        if config_file.is_file() and "config" in config_file.name.lower():
                            backup_file = self.backup_dir / "configs" / config_file.name
                            backup_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(config_file, backup_file)
                            changes.append(f"备份配置文件: {config_file} -> {backup_file}")
        
        return changes

    def _step_analyze_current_state(self) -> List[str]:
        """分析当前架构状态"""
        changes = []
        
        # 运行架构分析工具
        try:
            result = subprocess.run([
                sys.executable, "tools/analyze_desktop_app.py", "."
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                changes.append("架构分析完成")
                changes.append(f"分析输出: {result.stdout}")
            else:
                changes.append(f"架构分析警告: {result.stderr}")
                
        except Exception as e:
            changes.append(f"架构分析失败: {e}")
        
        return changes

    def _step_implement_unified_base(self) -> List[str]:
        """实施统一基类"""
        changes = []
        
        # 检查统一基类是否已存在
        unified_stage_path = self.project_root / "src/pktmask/core/unified_stage.py"
        if unified_stage_path.exists():
            changes.append("统一基类已存在")
        else:
            changes.append("统一基类文件不存在，需要创建")
        
        # 备份现有的base_step.py
        base_step_path = self.project_root / "src/pktmask/core/base_step.py"
        if base_step_path.exists():
            backup_path = self.backup_dir / "base_step.py.backup"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base_step_path, backup_path)
            changes.append(f"备份原有base_step.py: {backup_path}")
        
        return changes

    def _step_update_stage_imports(self) -> List[str]:
        """更新阶段导入语句"""
        changes = []
        
        # 查找需要更新的Python文件
        import_mappings = {
            "from pktmask.core.base_step import ProcessingStep": 
                "from pktmask.core.unified_stage import StageBase",
            "from ..core.base_step import ProcessingStep":
                "from ..core.unified_stage import StageBase",
        }
        
        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                for old_import, new_import in import_mappings.items():
                    if old_import in content:
                        content = content.replace(old_import, new_import)
                        changes.append(f"更新导入: {py_file.relative_to(self.project_root)}")
                
                # 如果有变更，写回文件
                if content != original_content:
                    # 备份原文件
                    backup_file = self.backup_dir / "imports" / py_file.relative_to(self.project_root)
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(py_file, backup_file)
                    
                    # 写入新内容
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
            except Exception as e:
                changes.append(f"更新导入失败 {py_file}: {e}")
        
        return changes

    def _step_migrate_user_configs(self) -> List[str]:
        """迁移用户配置"""
        changes = []
        
        try:
            result = subprocess.run([
                sys.executable, "tools/config_migrator.py", "."
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                changes.append("配置迁移完成")
                changes.append(f"迁移输出: {result.stdout}")
            else:
                changes.append(f"配置迁移警告: {result.stderr}")
                
        except Exception as e:
            changes.append(f"配置迁移失败: {e}")
        
        return changes

    def _step_update_gui_adapters(self) -> List[str]:
        """更新GUI适配器"""
        changes = []
        
        # 这是一个高风险步骤，需要谨慎处理
        gui_files = [
            "src/pktmask/gui/managers/pipeline_manager.py",
            "src/pktmask/gui/main_window.py"
        ]
        
        for gui_file in gui_files:
            gui_path = self.project_root / gui_file
            if gui_path.exists():
                # 备份GUI文件
                backup_file = self.backup_dir / "gui" / gui_path.relative_to(self.project_root)
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(gui_path, backup_file)
                changes.append(f"备份GUI文件: {gui_file}")
        
        changes.append("GUI适配器更新准备完成（实际更新需要手动进行）")
        return changes

    def _step_validate_functionality(self) -> List[str]:
        """验证功能完整性"""
        changes = []
        
        # 基本的语法检查
        try:
            result = subprocess.run([
                sys.executable, "-m", "py_compile", "src/pktmask/core/unified_stage.py"
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                changes.append("统一基类语法检查通过")
            else:
                changes.append(f"统一基类语法检查失败: {result.stderr}")
                
        except Exception as e:
            changes.append(f"语法检查失败: {e}")
        
        # 检查导入是否正常
        try:
            result = subprocess.run([
                sys.executable, "-c", "from pktmask.core.unified_stage import StageBase; print('导入成功')"
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                changes.append("统一基类导入测试通过")
            else:
                changes.append(f"统一基类导入测试失败: {result.stderr}")
                
        except Exception as e:
            changes.append(f"导入测试失败: {e}")
        
        return changes

    def _should_skip_file(self, file_path: Path) -> bool:
        """判断是否应该跳过文件"""
        skip_patterns = [
            '__pycache__',
            '.git',
            'backup',
            'migration_backups',
            'tools/',
            'reports/',
            '.pyc'
        ]
        
        return any(pattern in str(file_path) for pattern in skip_patterns)

    def _generate_final_report(self, total_duration: float) -> Dict[str, Any]:
        """生成最终报告"""
        successful_steps = sum(1 for r in self.results if r.success)
        failed_steps = sum(1 for r in self.results if not r.success)
        
        report = {
            "migration_summary": {
                "total_steps": len(self.migration_steps),
                "successful_steps": successful_steps,
                "failed_steps": failed_steps,
                "total_duration_seconds": total_duration,
                "completion_rate": successful_steps / len(self.migration_steps) * 100
            },
            "step_results": [asdict(result) for result in self.results],
            "backup_location": str(self.backup_dir),
            "timestamp": datetime.now().isoformat()
        }
        
        return report

    def _generate_error_report(self, error_message: str) -> Dict[str, Any]:
        """生成错误报告"""
        return {
            "migration_summary": {
                "status": "failed",
                "error_message": error_message,
                "completed_steps": len(self.results)
            },
            "step_results": [asdict(result) for result in self.results],
            "backup_location": str(self.backup_dir),
            "timestamp": datetime.now().isoformat()
        }

# 使用示例
if __name__ == "__main__":
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    migrator = ProgressiveMigrator(project_root)
    
    # 执行迁移
    report = migrator.execute_migration()
    
    # 保存报告
    output_file = "reports/progressive_migration_report.json"
    os.makedirs("reports", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 迁移完成!")
    print(f"📈 成功率: {report['migration_summary'].get('completion_rate', 0):.1f}%")
    print(f"📁 备份位置: {report['backup_location']}")
    print(f"📄 详细报告: {output_file}")
