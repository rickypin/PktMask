#!/usr/bin/env python3
"""
智能导入语句更新工具
保持向后兼容，避免破坏性变更
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple

class SmartImportUpdater:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

        # 保守的导入映射 - 只更新明确需要的
        self.import_mappings = {
            # 基类导入更新
            'from pktmask.core.base_step import ProcessingStep':
                'from pktmask.core.unified_stage import StageBase',
            'from ..core.base_step import ProcessingStep':
                'from ..core.unified_stage import StageBase',
            'from ...core.base_step import ProcessingStep':
                'from ...core.unified_stage import StageBase',
            
            # 适配器导入更新
            'from pktmask.adapters.processor_adapter import PipelineProcessorAdapter':
                'from pktmask.core.unified_stage import StageBase',
            'from ..adapters.processor_adapter import PipelineProcessorAdapter':
                'from ..core.unified_stage import StageBase',
        }

        # 类继承映射 - 更保守
        self.class_mappings = {
            'ProcessingStep': 'StageBase',
            'PipelineProcessorAdapter': 'StageBase'
        }

        # 需要跳过的文件 - 避免破坏兼容层
        self.skip_patterns = {
            '__pycache__',
            '.git',
            'backup',
            'migration_backups',
            'tools/',
            'reports/',
            'src/pktmask/core/base_step.py',  # 保留兼容层
            'src/pktmask/adapters/compatibility/',  # 保留兼容适配器
            'src/pktmask/core/unified_stage.py',  # 跳过新的基类文件
        }

    def update_all_files(self) -> Dict[str, int]:
        """更新所有文件的导入语句"""
        results = {'files_updated': 0, 'imports_updated': 0, 'classes_updated': 0}

        print("🔄 开始智能导入更新...")

        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue

            updates = self._update_file(py_file)
            if updates['total'] > 0:
                results['files_updated'] += 1
                results['imports_updated'] += updates['imports']
                results['classes_updated'] += updates['classes']

        return results

    def _should_skip_file(self, file_path: Path) -> bool:
        """判断是否应该跳过文件"""
        file_str = str(file_path)
        return any(pattern in file_str for pattern in self.skip_patterns)

    def _update_file(self, file_path: Path) -> Dict[str, int]:
        """更新单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            import_updates = 0
            class_updates = 0

            # 更新导入语句
            for old_import, new_import in self.import_mappings.items():
                if old_import in content:
                    content = content.replace(old_import, new_import)
                    import_updates += 1
                    print(f"  📦 更新导入: {file_path.relative_to(self.project_root)}")

            # 更新类继承
            for old_class, new_class in self.class_mappings.items():
                # 匹配类继承模式
                pattern = rf'class\s+(\w+)\s*\(\s*{re.escape(old_class)}\s*\)'
                replacement = rf'class \1({new_class})'

                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    class_updates += 1
                    print(f"  🏗️  更新类继承: {file_path.relative_to(self.project_root)}")

            # 如果有更新，写回文件
            total_updates = import_updates + class_updates
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

            return {
                'imports': import_updates,
                'classes': class_updates,
                'total': total_updates
            }

        except Exception as e:
            print(f"❌ 更新文件失败 {file_path}: {e}")
            return {'imports': 0, 'classes': 0, 'total': 0}

    def update_gui_pipeline_manager(self) -> List[str]:
        """专门更新GUI Pipeline Manager"""
        changes = []
        
        pipeline_manager_path = self.project_root / "src/pktmask/gui/managers/pipeline_manager.py"
        if not pipeline_manager_path.exists():
            return ["Pipeline Manager文件不存在"]

        try:
            with open(pipeline_manager_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content

            # 更新导入语句 - 使用新的统一架构
            import_updates = [
                ('from pktmask.core.pipeline.executor import PipelineExecutor',
                 'from pktmask.core.unified_stage import ModernPipelineExecutor'),
                ('from pktmask.core.pipeline.models import PipelineConfig',
                 'from pktmask.core.unified_stage import PipelineConfig'),
            ]

            for old_import, new_import in import_updates:
                if old_import in content:
                    content = content.replace(old_import, new_import)
                    changes.append(f"更新导入: {old_import} -> {new_import}")

            # 更新类名引用
            class_updates = [
                ('PipelineExecutor', 'ModernPipelineExecutor'),
            ]

            for old_class, new_class in class_updates:
                # 只替换类实例化和类型注解
                patterns = [
                    (rf'\b{old_class}\s*\(', f'{new_class}('),
                    (rf':\s*{old_class}\b', f': {new_class}'),
                    (rf'=\s*{old_class}\s*\(', f'= {new_class}('),
                ]

                for pattern, replacement in patterns:
                    if re.search(pattern, content):
                        content = re.sub(pattern, replacement, content)
                        changes.append(f"更新类引用: {old_class} -> {new_class}")

            # 如果有更新，写回文件
            if content != original_content:
                with open(pipeline_manager_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                changes.append("Pipeline Manager更新完成")
            else:
                changes.append("Pipeline Manager无需更新")

        except Exception as e:
            changes.append(f"Pipeline Manager更新失败: {e}")

        return changes

    def create_compatibility_wrapper(self) -> List[str]:
        """创建兼容性包装器"""
        changes = []

        # 更新 base_step.py 以提供更好的兼容性
        base_step_path = self.project_root / "src/pktmask/core/base_step.py"
        if base_step_path.exists():
            try:
                compatibility_content = '''import abc
import warnings
from pathlib import Path
from typing import Optional, Dict, List, Union

from .unified_stage import StageBase, StageStats


class ProcessingStep(StageBase):
    """
    ProcessingStep 兼容性包装
    
    ！！！迁移提示！！！
    这个类是为了兼容旧的 ProcessingStep 接口而保留的。
    推荐新代码直接继承 StageBase。
    
    现有的 ProcessingStep 子类可以：
    1. 暂时继续使用这个兼容层
    2. 将 process_file 方法重命名为 process_file_legacy
    3. 最终迁移到直接继承 StageBase
    """
    
    # 保持旧的 suffix 属性以兼容
    suffix: str = ""
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        # 发出迁移提示（仅在第一次创建实例时）
        if not hasattr(self.__class__, '_migration_warning_shown'):
            warnings.warn(
                f"{self.__class__.__name__} 继承自 ProcessingStep（兼容层）。"
                "推荐迁移到直接继承 StageBase 以获得更好的功能。",
                FutureWarning,
                stacklevel=2
            )
            self.__class__._migration_warning_shown = True
    
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> Union[StageStats, Dict, None]:
        """统一的处理方法 - 兼容新旧接口"""
        
        # 尝试调用新的方法（如果子类已经迁移）
        if hasattr(self, 'process_file_legacy'):
            # 子类提供了 legacy 方法，使用它
            result = self.process_file_legacy(str(input_path), str(output_path))
            return self._convert_legacy_result_to_stage_stats(result)
        
        # 如果子类重写了 process_file，直接调用
        # 这里使用一个技巧来检测子类是否重写了 process_file
        child_method = getattr(type(self), 'process_file', None)
        if child_method and child_method is not ProcessingStep.process_file:
            # 子类重写了 process_file，但我们需要避免无限递归
            # 这种情况下，假设子类期望旧的接口
            result = self._call_legacy_process_file(str(input_path), str(output_path))
            return self._convert_legacy_result_to_stage_stats(result)
        
        # 如果都没有，抛出错误
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 process_file_legacy 方法，"
            "或者直接继承 StageBase 并实现新的 process_file 方法。"
        )
    
    def _call_legacy_process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """调用子类的旧版 process_file 方法"""
        # 这里需要一个巧妙的方法来调用子类的原始 process_file
        # 我们直接查找子类的方法并调用
        for cls in type(self).__mro__[1:]:  # 跳过自己，从父类开始
            if hasattr(cls, 'process_file') and cls is not ProcessingStep:
                method = getattr(cls, 'process_file')
                if callable(method):
                    return method(self, input_path, output_path)
        return None
    
    def _convert_legacy_result_to_stage_stats(self, result: Optional[Dict]) -> Optional[StageStats]:
        """将旧格式结果转换为新的 StageStats"""
        if result is None:
            return None
        
        if isinstance(result, dict):
            return StageStats(
                stage_name=self.name,
                packets_processed=result.get('total_packets', 0),
                packets_modified=result.get('modified_packets', 0),
                duration_ms=result.get('duration_ms', 0.0),
                extra_metrics=result
            )
        
        return result
'''

                with open(base_step_path, 'w', encoding='utf-8') as f:
                    f.write(compatibility_content)
                
                changes.append("更新base_step.py兼容性包装器")

            except Exception as e:
                changes.append(f"更新base_step.py失败: {e}")

        return changes

    def generate_update_report(self, results: Dict[str, int], gui_changes: List[str], 
                             compat_changes: List[str]) -> Dict[str, any]:
        """生成更新报告"""
        return {
            "import_updates": {
                "files_updated": results['files_updated'],
                "imports_updated": results['imports_updated'],
                "classes_updated": results['classes_updated']
            },
            "gui_updates": gui_changes,
            "compatibility_updates": compat_changes,
            "recommendations": [
                "✅ 导入语句已更新到统一架构",
                "🔄 GUI组件已准备好使用新架构",
                "🛡️ 兼容性包装器已更新",
                "📝 建议运行测试验证功能完整性"
            ]
        }

# 使用示例
if __name__ == "__main__":
    import sys
    import json
    
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    updater = SmartImportUpdater(project_root)
    
    # 执行导入更新
    results = updater.update_all_files()
    
    # 更新GUI Pipeline Manager
    gui_changes = updater.update_gui_pipeline_manager()
    
    # 创建兼容性包装器
    compat_changes = updater.create_compatibility_wrapper()
    
    # 生成报告
    report = updater.generate_update_report(results, gui_changes, compat_changes)
    
    print(f"\n📊 导入更新完成:")
    print(f"   - 更新文件数: {results['files_updated']}")
    print(f"   - 更新导入数: {results['imports_updated']}")
    print(f"   - 更新类数: {results['classes_updated']}")
    
    print(f"\n🖥️  GUI更新:")
    for change in gui_changes:
        print(f"   - {change}")
    
    print(f"\n🛡️ 兼容性更新:")
    for change in compat_changes:
        print(f"   - {change}")
    
    # 保存报告
    output_file = "reports/import_update_report.json"
    os.makedirs("reports", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 更新报告已保存到: {output_file}")
