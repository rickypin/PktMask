#!/usr/bin/env python3
"""
PktMask目录结构迁移 - 路径更新脚本

此脚本用于自动更新迁移后的文件路径引用，确保所有配置文件、导入路径和相对路径都正确更新。

使用方法:
    python3 scripts/migration/update_paths.py [--dry-run] [--phase PHASE_NUMBER]
    
参数:
    --dry-run: 仅显示将要进行的更改，不实际修改文件
    --phase: 指定要更新的阶段 (2=配置文件, 3=脚本文件, 4=文档, 5=输出)
"""

import os
import re
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PathUpdater:
    """路径更新器 - 负责更新文件中的路径引用"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent.parent
        self.changes_made = []
        
    def update_config_paths(self) -> None:
        """Phase 2: 更新配置文件路径引用"""
        logger.info("=== Phase 2: 更新配置文件路径引用 ===")
        
        # 配置文件路径映射
        config_mappings = {
            # 原路径 -> 新路径
            "mask_config.yaml": "config/default/mask_config.yaml",
            "simple_mask_recipe_sample.json": "config/samples/simple_mask_recipe.json",
            "comprehensive_mask_recipe_sample.json": "config/samples/comprehensive_mask_recipe.json",
            "demo_recipe.json": "config/samples/demo_recipe.json",
            "custom_recipe.json": "config/samples/custom_recipe.json",
            "tls_mask_recipe_sample.json": "config/samples/tls_mask_recipe.json",
            "test_configs/": "config/test/",
            "conf/production/": "config/production/"
        }
        
        # 需要更新的文件列表
        files_to_update = [
            "src/pktmask/config/defaults.py",
            "src/pktmask/config/settings.py",
            "examples/basic_usage.py",
            "examples/advanced_usage.py",
            "examples/performance_testing.py",
            "run_tests.py",
            "src/pktmask/resources/config_template.yaml"
        ]
        
        for file_path in files_to_update:
            self._update_file_paths(file_path, config_mappings, "配置文件路径")
    
    def update_script_paths(self) -> None:
        """Phase 3: 更新脚本文件路径引用"""
        logger.info("=== Phase 3: 更新脚本文件路径引用 ===")
        
        # 脚本路径映射
        script_mappings = {
            "manual_tcp_masker_test.py": "scripts/test/manual_tcp_masker_test.py",
            "run_tcp_masker_test.py": "scripts/test/run_tcp_masker_test.py",
            "build_app.sh": "scripts/build/build_app.sh",
            "scripts/analyze_tls_sample.py": "scripts/validation/analyze_tls_sample.py",
            "scripts/validate_tls_sample.py": "scripts/validation/validate_tls_sample.py",
            "scripts/migrate_to_tcp_payload_masker.py": "scripts/migration/migrate_to_tcp_payload_masker.py",
            "sequence_unification_strategy.py": "scripts/migration/sequence_unification_strategy.py",
            "hybrid_architecture_design.py": "scripts/migration/hybrid_architecture_design.py",
            "hooks/": "scripts/hooks/"
        }
        
        # 需要更新脚本引用的文件
        files_to_update = [
            "README.md",
            "run_tests.py",
            "examples/basic_usage.py",
            "examples/advanced_usage.py",
            "docs/README.md"  # 如果存在的话
        ]
        
        for file_path in files_to_update:
            self._update_file_paths(file_path, script_mappings, "脚本路径")
    
    def update_doc_paths(self) -> None:
        """Phase 4: 更新文档路径引用"""
        logger.info("=== Phase 4: 更新文档路径引用 ===")
        
        # 文档路径映射
        doc_mappings = {
            "tcp_payload_masker_phase1_4_validation_report.md": "docs/reports/tcp_payload_masker_phase1_4_validation_report.md"
        }
        
        # 需要更新文档引用的文件
        files_to_update = [
            "README.md",
            "docs/README.md"  # 如果存在的话
        ]
        
        for file_path in files_to_update:
            self._update_file_paths(file_path, doc_mappings, "文档路径")
    
    def update_output_paths(self) -> None:
        """Phase 5: 更新输出路径引用"""
        logger.info("=== Phase 5: 更新输出路径引用 ===")
        
        # 输出路径映射
        output_mappings = {
            "output/": "output/processed/",
            "reports/": "output/reports/",
            "examples/output/": "examples/output/",  # 保持不变
            "examples/examples/output/": "examples/output/"  # 修复嵌套
        }
        
        # 需要更新输出路径的文件
        files_to_update = [
            "src/pktmask/gui/managers/report_manager.py",
            "src/pktmask/gui/managers/file_manager.py",
            "src/pktmask/core/pipeline.py",
            "examples/basic_usage.py",
            "examples/advanced_usage.py",
            "examples/performance_testing.py",
            "run_tests.py"
        ]
        
        for file_path in files_to_update:
            self._update_file_paths(file_path, output_mappings, "输出路径")
    
    def _update_file_paths(self, file_path: str, mappings: Dict[str, str], update_type: str) -> None:
        """更新单个文件中的路径引用"""
        full_path = self.project_root / file_path
        
        if not full_path.exists():
            logger.warning(f"文件不存在，跳过: {file_path}")
            return
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            changes_in_file = []
            
            # 应用路径映射
            for old_path, new_path in mappings.items():
                # 使用正则表达式进行更精确的匹配
                patterns = [
                    # 直接字符串匹配
                    re.escape(old_path),
                    # 带引号的路径
                    f'["\']\\s*{re.escape(old_path)}\\s*["\']',
                    # 路径连接
                    f'os\\.path\\.join\\([^)]*["\']\\s*{re.escape(old_path)}\\s*["\']',
                    f'Path\\([^)]*["\']\\s*{re.escape(old_path)}\\s*["\']'
                ]
                
                for pattern in patterns:
                    if re.search(pattern, content):
                        content = re.sub(pattern, lambda m: m.group().replace(old_path, new_path), content)
                        changes_in_file.append(f"{old_path} -> {new_path}")
            
            # 如果有变更，写入文件
            if content != original_content:
                if not self.dry_run:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                logger.info(f"✅ 更新 {update_type}: {file_path}")
                for change in changes_in_file:
                    logger.info(f"   📝 {change}")
                
                self.changes_made.extend([(file_path, change) for change in changes_in_file])
            
        except Exception as e:
            logger.error(f"❌ 更新文件失败 {file_path}: {e}")
    
    def update_import_paths(self) -> None:
        """更新Python导入路径"""
        logger.info("=== 更新Python导入路径 ===")
        
        # 查找所有Python文件
        python_files = []
        for pattern in ["src/**/*.py", "tests/**/*.py", "examples/*.py", "scripts/**/*.py"]:
            python_files.extend(self.project_root.glob(pattern))
        
        # 相对导入路径映射
        import_mappings = {
            # 如果有相对导入需要更新，在这里添加
        }
        
        for py_file in python_files:
            if py_file.exists():
                self._check_import_paths(py_file)
    
    def _check_import_paths(self, py_file: Path) -> None:
        """检查Python文件中的导入路径"""
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否有相对路径导入问题
            relative_imports = re.findall(r'from\s+\.\.\s+import|import\s+\.\.|from\s+\.[^.\s]+\s+import', content)
            if relative_imports:
                logger.info(f"📍 发现相对导入路径: {py_file.relative_to(self.project_root)}")
                for imp in relative_imports:
                    logger.info(f"   🔍 {imp.strip()}")
                    
        except Exception as e:
            logger.error(f"❌ 检查导入路径失败 {py_file}: {e}")
    
    def create_summary_report(self) -> None:
        """创建更新摘要报告"""
        logger.info("=== 生成更新摘要报告 ===")
        
        report_path = self.project_root / "output" / "reports" / "path_update_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# PktMask路径更新报告\n\n")
            f.write(f"**执行模式**: {'DRY RUN (预览模式)' if self.dry_run else 'LIVE RUN (实际执行)'}\n")
            f.write(f"**总更改数**: {len(self.changes_made)}\n\n")
            
            f.write("## 详细更改列表\n\n")
            for file_path, change in self.changes_made:
                f.write(f"- **{file_path}**: {change}\n")
            
            f.write("\n## 验证步骤\n\n")
            f.write("1. 运行测试: `python3 run_tests.py --quick`\n")
            f.write("2. 启动GUI: `python3 run_gui.py`\n")
            f.write("3. 运行示例: `cd examples && python3 basic_usage.py`\n")
            f.write("4. 检查配置: 验证配置文件正确加载\n")
        
        logger.info(f"📊 报告已生成: {report_path}")

def main():
    parser = argparse.ArgumentParser(description="PktMask路径更新脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅预览更改，不实际执行")
    parser.add_argument("--phase", type=int, choices=[2, 3, 4, 5], help="指定要执行的阶段")
    
    args = parser.parse_args()
    
    updater = PathUpdater(dry_run=args.dry_run)
    
    if args.dry_run:
        logger.info("🔍 DRY RUN模式 - 仅预览更改")
    else:
        logger.info("🚀 LIVE RUN模式 - 实际执行更改")
    
    try:
        if args.phase:
            # 执行指定阶段
            if args.phase == 2:
                updater.update_config_paths()
            elif args.phase == 3:
                updater.update_script_paths()
            elif args.phase == 4:
                updater.update_doc_paths()
            elif args.phase == 5:
                updater.update_output_paths()
        else:
            # 执行所有阶段
            updater.update_config_paths()
            updater.update_script_paths()
            updater.update_doc_paths()
            updater.update_output_paths()
        
        # 检查导入路径
        updater.update_import_paths()
        
        # 生成摘要报告
        updater.create_summary_report()
        
        logger.info(f"✅ 路径更新完成! 总共进行了 {len(updater.changes_made)} 处更改")
        
        if not args.dry_run:
            logger.info("⚠️  请运行以下命令验证更改:")
            logger.info("   python3 run_tests.py --quick")
            logger.info("   python3 run_gui.py")
        
    except Exception as e:
        logger.error(f"❌ 路径更新失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 