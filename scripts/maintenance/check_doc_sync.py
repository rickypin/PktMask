#!/usr/bin/env python3
"""
文档同步检查脚本

检查文档中引用的组件是否在代码中存在，帮助识别过时的文档。
"""

import os
import re
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 要检查的组件名称模式
COMPONENT_PATTERNS = [
    r'\b(\w+Processor)\b',
    r'\b(\w+Adapter)\b',
    r'\b(\w+Stage)\b',
    r'\b(\w+Analyzer)\b',
    r'\b(\w+Masker)\b',
    r'\b(\w+Manager)\b',
]

# 要忽略的常见词汇
IGNORE_WORDS = {
    'BaseProcessor', 'StageBase', 'ProcessorResult', 
    'StageStats', 'ProcessorConfig', 'MaskingRecipe'
}


def find_components_in_docs(doc_path: Path) -> Set[str]:
    """在文档中查找组件名称"""
    components = set()
    
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for pattern in COMPONENT_PATTERNS:
            matches = re.findall(pattern, content)
            components.update(matches)
            
    except Exception as e:
        print(f"Error reading {doc_path}: {e}")
        
    return components - IGNORE_WORDS


def find_components_in_code(src_path: Path) -> Set[str]:
    """在代码中查找定义的类"""
    components = set()
    
    for py_file in src_path.rglob('*.py'):
        if '__pycache__' in str(py_file):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 查找类定义
            class_matches = re.findall(r'class\s+(\w+)\s*\(', content)
            components.update(class_matches)
            
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
            
    return components


def check_doc_sync(doc_path: Path, code_components: Set[str]) -> Tuple[List[str], List[str]]:
    """检查单个文档的同步状态"""
    doc_components = find_components_in_docs(doc_path)
    
    # 查找在文档中提到但代码中不存在的组件
    missing_in_code = []
    found_in_code = []
    
    for component in doc_components:
        if component not in code_components:
            missing_in_code.append(component)
        else:
            found_in_code.append(component)
            
    return missing_in_code, found_in_code


def main():
    """主函数"""
    print("🔍 文档同步检查\n")
    
    # 收集代码中的所有组件
    src_path = PROJECT_ROOT / 'src'
    code_components = find_components_in_code(src_path)
    print(f"✅ 在代码中找到 {len(code_components)} 个组件\n")
    
    # 检查所有文档
    docs_path = PROJECT_ROOT / 'docs'
    problems = []
    
    for doc_file in docs_path.rglob('*.md'):
        # 跳过 README 和其他非技术文档
        if doc_file.name in ['README.md', 'DOCUMENT_STATUS.md']:
            continue
            
        missing, found = check_doc_sync(doc_file, code_components)
        
        if missing:
            rel_path = doc_file.relative_to(PROJECT_ROOT)
            problems.append({
                'path': rel_path,
                'missing': missing,
                'found': found
            })
    
    # 输出结果
    if problems:
        print("⚠️  发现以下文档可能已过时：\n")
        
        for problem in sorted(problems, key=lambda x: len(x['missing']), reverse=True):
            print(f"📄 {problem['path']}")
            print(f"   ❌ 不存在的组件: {', '.join(problem['missing'])}")
            if problem['found']:
                print(f"   ✅ 存在的组件: {', '.join(problem['found'][:3])}...")
            print()
            
        # 分类统计
        current_problems = [p for p in problems if 'current/' in str(p['path'])]
        archive_problems = [p for p in problems if 'archive/' in str(p['path'])]
        
        print("\n📊 统计:")
        print(f"   - current/ 目录下: {len(current_problems)} 个文档需要更新")
        print(f"   - archive/ 目录下: {len(archive_problems)} 个文档已归档")
        print(f"   - 其他目录: {len(problems) - len(current_problems) - len(archive_problems)} 个文档")
        
        if current_problems:
            print("\n❗ 建议优先更新 current/ 目录下的文档")
            
    else:
        print("✅ 所有文档都与代码同步！")
        
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
