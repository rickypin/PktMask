#!/usr/bin/env python3
"""
适配器导入关系分析脚本

分析所有文件中对适配器的导入关系，生成迁移清单。
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# 需要迁移的适配器文件映射
ADAPTER_MIGRATIONS = {
    # 原路径 -> 新路径
    "pktmask.core.adapters.processor_adapter": "pktmask.adapters.processor_adapter",
    "pktmask.core.encapsulation.adapter": "pktmask.adapters.encapsulation_adapter",
    "pktmask.domain.adapters.event_adapter": "pktmask.adapters.event_adapter",
    "pktmask.domain.adapters.statistics_adapter": "pktmask.adapters.statistics_adapter",
    "pktmask.stages.adapters.anon_compat": "pktmask.adapters.compatibility.anon_compat",
    "pktmask.stages.adapters.dedup_compat": "pktmask.adapters.compatibility.dedup_compat",
}

# 类名变更映射
CLASS_RENAMES = {
    "ProcessorAdapterStage": "ProcessorAdapter",
    # 添加其他需要重命名的类
}


def find_python_files(root_dir: Path) -> List[Path]:
    """查找所有Python文件"""
    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # 跳过虚拟环境和缓存目录
        dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', '.git', 'output'}]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    
    return python_files


def analyze_imports(file_path: Path) -> Dict[str, List[Dict]]:
    """分析单个文件的导入语句"""
    imports = defaultdict(list)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"无法读取文件 {file_path}: {e}")
        return imports
    
    # 匹配 import 语句
    import_patterns = [
        # from xxx import yyy
        r'^\s*from\s+([a-zA-Z0-9_.]+)\s+import\s+([^#\n]+)',
        # import xxx
        r'^\s*import\s+([a-zA-Z0-9_.]+)(?:\s+as\s+\w+)?',
    ]
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        for pattern in import_patterns:
            match = re.match(pattern, line)
            if match:
                module = match.group(1)
                
                # 检查是否是需要迁移的适配器
                for old_module, new_module in ADAPTER_MIGRATIONS.items():
                    if module == old_module or module.startswith(old_module + '.'):
                        import_info = {
                            'line_number': line_num,
                            'line': line.strip(),
                            'old_module': old_module,
                            'new_module': new_module,
                            'type': 'from_import' if 'from' in line else 'import'
                        }
                        
                        # 如果是 from import，获取导入的内容
                        if len(match.groups()) > 1:
                            import_info['imported_names'] = [
                                name.strip() for name in match.group(2).split(',')
                            ]
                        
                        imports[str(file_path)].append(import_info)
    
    return dict(imports)


def find_class_usage(file_path: Path) -> Dict[str, List[Dict]]:
    """查找需要重命名的类使用情况"""
    usages = defaultdict(list)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"无法读取文件 {file_path}: {e}")
        return usages
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        for old_name, new_name in CLASS_RENAMES.items():
            if old_name in line:
                usage_info = {
                    'line_number': line_num,
                    'line': line.strip(),
                    'old_name': old_name,
                    'new_name': new_name
                }
                usages[str(file_path)].append(usage_info)
    
    return dict(usages)


def generate_migration_report(root_dir: Path) -> Dict:
    """生成迁移报告"""
    print("正在分析项目文件...")
    
    python_files = find_python_files(root_dir / 'src')
    python_files.extend(find_python_files(root_dir / 'tests'))
    
    report = {
        'total_files': len(python_files),
        'affected_files': {},
        'import_changes': {},
        'class_renames': {},
        'statistics': {
            'files_with_imports': 0,
            'total_import_changes': 0,
            'files_with_class_usage': 0,
            'total_class_renames': 0
        }
    }
    
    print(f"找到 {len(python_files)} 个Python文件")
    
    # 分析导入关系
    for file_path in python_files:
        imports = analyze_imports(file_path)
        if imports:
            for file_str, import_list in imports.items():
                report['import_changes'][file_str] = import_list
                report['affected_files'][file_str] = True
                report['statistics']['files_with_imports'] += 1
                report['statistics']['total_import_changes'] += len(import_list)
        
        # 分析类使用情况
        class_usages = find_class_usage(file_path)
        if class_usages:
            for file_str, usage_list in class_usages.items():
                if file_str not in report['class_renames']:
                    report['class_renames'][file_str] = []
                report['class_renames'][file_str].extend(usage_list)
                report['affected_files'][file_str] = True
                report['statistics']['files_with_class_usage'] += 1
                report['statistics']['total_class_renames'] += len(usage_list)
    
    return report


def generate_migration_checklist(report: Dict) -> List[str]:
    """生成迁移清单"""
    checklist = []
    
    # 按文件分组
    for file_path in sorted(report['affected_files'].keys()):
        checklist.append(f"\n## {file_path}")
        
        # 导入变更
        if file_path in report['import_changes']:
            checklist.append("### 导入变更:")
            for change in report['import_changes'][file_path]:
                checklist.append(f"  - 第 {change['line_number']} 行: {change['old_module']} -> {change['new_module']}")
        
        # 类名变更
        if file_path in report['class_renames']:
            checklist.append("### 类名变更:")
            for rename in report['class_renames'][file_path]:
                checklist.append(f"  - 第 {rename['line_number']} 行: {rename['old_name']} -> {rename['new_name']}")
    
    return checklist


def main():
    """主函数"""
    root_dir = Path(__file__).parent.parent.parent
    output_dir = root_dir / 'output' / 'reports' / 'adapter_refactoring'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成报告
    report = generate_migration_report(root_dir)
    
    # 保存详细报告
    report_file = output_dir / 'import_analysis_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n分析报告已保存到: {report_file}")
    
    # 生成迁移清单
    checklist = generate_migration_checklist(report)
    checklist_file = output_dir / 'migration_checklist.md'
    
    with open(checklist_file, 'w', encoding='utf-8') as f:
        f.write("# 适配器迁移清单\n\n")
        f.write(f"总计需要修改 {len(report['affected_files'])} 个文件\n")
        f.write(f"- 导入变更: {report['statistics']['total_import_changes']} 处\n")
        f.write(f"- 类名变更: {report['statistics']['total_class_renames']} 处\n")
        f.write('\n'.join(checklist))
    
    print(f"迁移清单已保存到: {checklist_file}")
    
    # 打印摘要
    print("\n=== 分析摘要 ===")
    print(f"扫描文件数: {report['total_files']}")
    print(f"受影响文件数: {len(report['affected_files'])}")
    print(f"需要修改的导入语句: {report['statistics']['total_import_changes']}")
    print(f"需要重命名的类使用: {report['statistics']['total_class_renames']}")
    
    return report


if __name__ == "__main__":
    main()
