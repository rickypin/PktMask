#!/usr/bin/env python3
"""
PktMask 桌面应用架构分析工具
专注于用户体验和配置兼容性分析
"""

import ast
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, asdict
import importlib.util

@dataclass
class ComponentInfo:
    file_path: str
    component_type: str  # 'stage', 'gui', 'config', 'adapter'
    dependencies: List[str]
    user_facing: bool  # 是否直接影响用户体验
    config_keys: List[str]  # 相关的配置项

@dataclass
class UserImpactAnalysis:
    affected_features: List[str]
    config_changes: Dict[str, str]  # 旧配置 -> 新配置
    workflow_changes: List[str]
    migration_complexity: str  # 'low', 'medium', 'high'

@dataclass
class CompatibilityLayerInfo:
    file_path: str
    layer_type: str  # 'adapter', 'compatibility', 'legacy'
    target_components: List[str]
    removal_impact: str  # 'low', 'medium', 'high'
    replacement_strategy: str

class DesktopAppAnalyzer:
    """
    桌面应用 Pipeline 管理器
    专注于用户体验，避免过度复杂化
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.gui_components: List[ComponentInfo] = []
        self.stage_components: List[ComponentInfo] = []
        self.config_dependencies: Dict[str, Set[str]] = {}
        self.user_workflows: List[str] = []
        self.compatibility_layers: List[CompatibilityLayerInfo] = []
        self.legacy_imports: Dict[str, List[str]] = {}

    def analyze_desktop_app(self) -> Dict[str, any]:
        """分析桌面应用的架构和用户影响"""
        print("🔍 开始分析桌面应用架构...")
        
        self._analyze_gui_components()
        self._analyze_stage_usage()
        self._analyze_config_dependencies()
        self._analyze_compatibility_layers()
        self._analyze_legacy_imports()
        self._analyze_user_workflows()

        return {
            "gui_components": [asdict(comp) for comp in self.gui_components],
            "stage_components": [asdict(comp) for comp in self.stage_components],
            "compatibility_layers": [asdict(layer) for layer in self.compatibility_layers],
            "legacy_imports": self.legacy_imports,
            "config_dependencies": {k: list(v) for k, v in self.config_dependencies.items()},
            "user_impact": asdict(self._assess_user_impact()),
            "migration_strategy": self._generate_migration_strategy()
        }

    def _analyze_gui_components(self):
        """分析GUI组件和用户界面"""
        print("📱 分析GUI组件...")
        
        gui_paths = [
            "src/pktmask/gui/",
            "src/pktmask/config/settings.py"
        ]

        for gui_path in gui_paths:
            full_path = self.project_root / gui_path
            if full_path.exists():
                if full_path.is_file():
                    self._analyze_gui_file(full_path)
                else:
                    for py_file in full_path.rglob("*.py"):
                        self._analyze_gui_file(py_file)

    def _analyze_gui_file(self, file_path: Path):
        """分析单个GUI文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 分析导入和依赖
            dependencies = self._extract_imports(content)
            config_keys = self._extract_config_keys(content)
            
            # 判断是否面向用户
            user_facing = any(keyword in content.lower() for keyword in [
                'qwidget', 'qmainwindow', 'qdialog', 'button', 'label', 
                'checkbox', 'progress', 'ui', 'window'
            ])
            
            component = ComponentInfo(
                file_path=str(file_path.relative_to(self.project_root)),
                component_type='gui',
                dependencies=dependencies,
                user_facing=user_facing,
                config_keys=config_keys
            )
            
            self.gui_components.append(component)
            
        except Exception as e:
            print(f"⚠️  分析GUI文件失败 {file_path}: {e}")

    def _analyze_stage_usage(self):
        """分析处理阶段的使用情况"""
        print("⚙️  分析处理阶段...")
        
        stage_dirs = [
            "src/pktmask/core/pipeline/stages/",
            "src/pktmask/stages/",
            "src/pktmask/steps/"
        ]

        for stage_dir in stage_dirs:
            stage_path = self.project_root / stage_dir
            if stage_path.exists():
                for py_file in stage_path.rglob("*.py"):
                    if py_file.name != "__init__.py":
                        self._analyze_stage_file(py_file)

    def _analyze_stage_file(self, file_path: Path):
        """分析单个阶段文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            dependencies = self._extract_imports(content)
            config_keys = self._extract_config_keys(content)
            
            # 检查是否是处理阶段
            is_stage = any(keyword in content for keyword in [
                'StageBase', 'ProcessingStep', 'process_file', 'Stage'
            ])
            
            if is_stage:
                component = ComponentInfo(
                    file_path=str(file_path.relative_to(self.project_root)),
                    component_type='stage',
                    dependencies=dependencies,
                    user_facing=False,
                    config_keys=config_keys
                )
                
                self.stage_components.append(component)
                
        except Exception as e:
            print(f"⚠️  分析阶段文件失败 {file_path}: {e}")

    def _analyze_compatibility_layers(self):
        """分析兼容层组件"""
        print("🔗 分析兼容层组件...")
        
        compat_paths = [
            "src/pktmask/adapters/",
            "src/pktmask/core/adapters/",
            "src/pktmask/core/base_step.py",
            "src/pktmask/steps/"
        ]
        
        for compat_path in compat_paths:
            full_path = self.project_root / compat_path
            if full_path.exists():
                if full_path.is_file():
                    self._analyze_compatibility_file(full_path)
                else:
                    for py_file in full_path.rglob("*.py"):
                        self._analyze_compatibility_file(py_file)

    def _analyze_compatibility_file(self, file_path: Path):
        """分析兼容层文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 识别兼容层类型
            layer_type = 'legacy'
            if 'adapter' in file_path.name.lower():
                layer_type = 'adapter'
            elif 'compat' in file_path.name.lower():
                layer_type = 'compatibility'
            elif 'base_step' in file_path.name:
                layer_type = 'legacy'
            
            # 提取目标组件
            target_components = []
            if 'ProcessingStep' in content:
                target_components.append('ProcessingStep')
            if 'StageBase' in content:
                target_components.append('StageBase')
            
            # 评估移除影响
            removal_impact = 'low'
            if any(keyword in content.lower() for keyword in ['warning', 'deprecated', 'legacy']):
                removal_impact = 'low'
            elif 'gui' in str(file_path).lower():
                removal_impact = 'high'
            else:
                removal_impact = 'medium'
            
            compat_layer = CompatibilityLayerInfo(
                file_path=str(file_path.relative_to(self.project_root)),
                layer_type=layer_type,
                target_components=target_components,
                removal_impact=removal_impact,
                replacement_strategy=self._determine_replacement_strategy(content, layer_type)
            )
            
            self.compatibility_layers.append(compat_layer)
            
        except Exception as e:
            print(f"⚠️  分析兼容层文件失败 {file_path}: {e}")

    def _analyze_legacy_imports(self):
        """分析遗留导入"""
        print("📦 分析遗留导入...")
        
        legacy_patterns = [
            'from pktmask.steps',
            'from pktmask.core.base_step',
            'ProcessingStep',
            'from ..steps',
            'from .steps'
        ]
        
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                found_patterns = []
                for pattern in legacy_patterns:
                    if pattern in content:
                        found_patterns.append(pattern)
                
                if found_patterns:
                    rel_path = str(py_file.relative_to(self.project_root))
                    self.legacy_imports[rel_path] = found_patterns
                    
            except Exception:
                continue

    def _analyze_config_dependencies(self):
        """分析配置依赖关系"""
        print("⚙️  分析配置依赖...")
        
        config_files = [
            "src/pktmask/config/settings.py",
            "src/pktmask/config/defaults.py"
        ]

        for config_file in config_files:
            config_path = self.project_root / config_file
            if config_path.exists():
                self._extract_config_dependencies(config_path)

    def _extract_config_dependencies(self, config_path: Path):
        """提取配置依赖"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 简单的配置键提取
            config_keys = self._extract_config_keys(content)
            
            rel_path = str(config_path.relative_to(self.project_root))
            self.config_dependencies[rel_path] = set(config_keys)
            
        except Exception as e:
            print(f"⚠️  提取配置依赖失败 {config_path}: {e}")

    def _analyze_user_workflows(self):
        """分析用户工作流程"""
        print("👤 分析用户工作流程...")
        
        # 基于GUI代码分析用户可能的操作流程
        self.user_workflows = [
            "选择输入目录 -> 配置处理选项 -> 开始处理",
            "加载配置文件 -> 批量处理",
            "查看处理结果 -> 导出报告",
            "修改默认设置 -> 保存配置"
        ]

    def _extract_imports(self, content: str) -> List[str]:
        """提取导入语句"""
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except:
            # 如果AST解析失败，使用简单的字符串匹配
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    imports.append(line)
        
        return imports

    def _extract_config_keys(self, content: str) -> List[str]:
        """提取配置键"""
        config_keys = []
        
        # 简单的配置键模式匹配
        import re
        patterns = [
            r"['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]",  # 字符串中的键
            r"\.([a-zA-Z_][a-zA-Z0-9_]*)",  # 属性访问
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            config_keys.extend(matches)
        
        # 过滤常见的配置相关键
        config_related = [key for key in config_keys if any(
            keyword in key.lower() for keyword in [
                'config', 'setting', 'option', 'enable', 'disable',
                'default', 'path', 'dir', 'file'
            ]
        )]
        
        return list(set(config_related))

    def _determine_replacement_strategy(self, content: str, layer_type: str) -> str:
        """确定替换策略"""
        if layer_type == 'adapter':
            return "直接移除，使用统一基类"
        elif layer_type == 'compatibility':
            return "渐进式移除，提供迁移指南"
        else:
            return "保留兼容性，添加废弃警告"

    def _assess_user_impact(self) -> UserImpactAnalysis:
        """评估对用户的影响"""
        return UserImpactAnalysis(
            affected_features=[
                "处理阶段配置界面",
                "进度显示和统计",
                "错误处理和恢复"
            ],
            config_changes={
                "processing.stages": "processing.pipeline_stages",
                "ui.stage_options": "ui.pipeline_options"
            },
            workflow_changes=[
                "配置文件格式可能需要更新",
                "某些高级选项的位置可能调整"
            ],
            migration_complexity="low"
        )

    def _generate_migration_strategy(self) -> Dict[str, any]:
        """生成迁移策略"""
        return {
            "phase1": {
                "name": "后端统一",
                "description": "统一处理阶段基类，不影响用户界面",
                "user_impact": "无",
                "rollback_plan": "保留原有适配器"
            },
            "phase2": {
                "name": "配置迁移",
                "description": "自动迁移用户配置文件",
                "user_impact": "首次启动时自动迁移",
                "rollback_plan": "备份原配置文件"
            },
            "phase3": {
                "name": "界面优化",
                "description": "优化用户界面，移除冗余选项",
                "user_impact": "界面更简洁",
                "rollback_plan": "保留旧界面选项"
            }
        }

# 使用示例
if __name__ == "__main__":
    import sys
    
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    analyzer = DesktopAppAnalyzer(project_root)
    results = analyzer.analyze_desktop_app()

    print(f"\n📊 分析结果:")
    print(f"发现 {len(results['gui_components'])} 个GUI组件")
    print(f"发现 {len(results['stage_components'])} 个处理阶段")
    print(f"发现 {len(results['compatibility_layers'])} 个兼容层组件")
    print(f"发现 {len(results['legacy_imports'])} 个文件包含遗留导入")
    print(f"用户影响复杂度: {results['user_impact']['migration_complexity']}")
    print(f"迁移策略: {len(results['migration_strategy'])} 个阶段")
    
    # 保存结果
    output_file = "reports/desktop_analysis.json"
    os.makedirs("reports", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 分析结果已保存到: {output_file}")
