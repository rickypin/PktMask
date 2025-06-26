#!/usr/bin/env python3
"""
PktMask目录结构迁移验证脚本

此脚本用于验证目录结构迁移的完整性，确保所有文件都正确迁移且功能正常。

使用方法:
    python3 scripts/migration/validate_migration.py [--verbose] [--fix-issues]
    
参数:
    --verbose: 显示详细的验证过程
    --fix-issues: 自动修复发现的问题
"""

import os
import sys
import json
import argparse
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationValidator:
    """迁移验证器 - 验证目录结构迁移的完整性"""
    
    def __init__(self, verbose: bool = False, fix_issues: bool = False):
        self.verbose = verbose
        self.fix_issues = fix_issues
        self.project_root = Path(__file__).parent.parent.parent
        self.issues_found = []
        self.validation_results = {}
        
    def validate_directory_structure(self) -> bool:
        """验证目录结构是否符合预期"""
        logger.info("=== 验证目录结构 ===")
        
        # 期望的目录结构
        expected_dirs = [
            "config/default",
            "config/samples", 
            "config/production",
            "config/test",
            "scripts/build",
            "scripts/test",
            "scripts/validation",
            "scripts/migration",
            "scripts/hooks",
            "docs/api",
            "docs/development",
            "docs/reports",
            "docs/user",
            "output/processed",
            "output/reports",
            "output/temp"
        ]
        
        missing_dirs = []
        for dir_path in expected_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                missing_dirs.append(dir_path)
                if self.fix_issues:
                    full_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"✅ 创建缺失目录: {dir_path}")
        
        if missing_dirs:
            if not self.fix_issues:
                self.issues_found.extend([f"缺失目录: {d}" for d in missing_dirs])
                logger.error(f"❌ 发现 {len(missing_dirs)} 个缺失目录")
            
        self.validation_results['directory_structure'] = {
            'status': 'pass' if not missing_dirs or self.fix_issues else 'fail',
            'missing_dirs': missing_dirs,
            'expected_count': len(expected_dirs)
        }
        
        return len(missing_dirs) == 0 or self.fix_issues
    
    def validate_file_migrations(self) -> bool:
        """验证文件迁移是否正确"""
        logger.info("=== 验证文件迁移 ===")
        
        # 期望的文件迁移映射
        expected_files = {
            # 配置文件
            "config/default/mask_config.yaml": "mask_config.yaml",
            "config/samples/simple_mask_recipe.json": "simple_mask_recipe_sample.json",
            "config/samples/comprehensive_mask_recipe.json": "comprehensive_mask_recipe_sample.json",
            "config/samples/demo_recipe.json": "demo_recipe.json",
            "config/samples/custom_recipe.json": "custom_recipe.json",
            "config/samples/tls_mask_recipe.json": "tls_mask_recipe_sample.json",
            
            # 脚本文件
            "scripts/test/manual_tcp_masker_test.py": "manual_tcp_masker_test.py",
            "scripts/test/run_tcp_masker_test.py": "run_tcp_masker_test.py",
            "scripts/build/build_app.sh": "build_app.sh",
            "scripts/migration/sequence_unification_strategy.py": "sequence_unification_strategy.py",
            "scripts/migration/hybrid_architecture_design.py": "hybrid_architecture_design.py",
            
            # 文档文件
            "docs/reports/tcp_payload_masker_phase1_4_validation_report.md": "tcp_payload_masker_phase1_4_validation_report.md"
        }
        
        missing_files = []
        incorrect_locations = []
        
        for new_path, old_filename in expected_files.items():
            new_full_path = self.project_root / new_path
            old_full_path = self.project_root / old_filename
            
            if not new_full_path.exists():
                if old_full_path.exists():
                    incorrect_locations.append((old_filename, new_path))
                else:
                    missing_files.append(new_path)
        
        if missing_files:
            self.issues_found.extend([f"缺失文件: {f}" for f in missing_files])
            logger.error(f"❌ 发现 {len(missing_files)} 个缺失文件")
            
        if incorrect_locations:
            self.issues_found.extend([f"文件未迁移: {old} -> {new}" for old, new in incorrect_locations])
            logger.error(f"❌ 发现 {len(incorrect_locations)} 个未迁移文件")
        
        self.validation_results['file_migrations'] = {
            'status': 'pass' if not missing_files and not incorrect_locations else 'fail',
            'missing_files': missing_files,
            'incorrect_locations': incorrect_locations,
            'expected_count': len(expected_files)
        }
        
        return len(missing_files) == 0 and len(incorrect_locations) == 0
    
    def validate_path_references(self) -> bool:
        """验证路径引用是否正确更新"""
        logger.info("=== 验证路径引用 ===")
        
        # 检查可能包含旧路径引用的文件
        files_to_check = [
            "src/pktmask/config/defaults.py",
            "examples/basic_usage.py",
            "examples/advanced_usage.py",
            "run_tests.py",
            "README.md"
        ]
        
        # 旧路径模式 (这些应该已经被更新)
        old_patterns = [
            "mask_config.yaml",
            "simple_mask_recipe_sample.json",
            "manual_tcp_masker_test.py",
            "build_app.sh",
            "tcp_payload_masker_phase1_4_validation_report.md"
        ]
        
        path_issues = []
        
        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    for pattern in old_patterns:
                        if pattern in content:
                            path_issues.append(f"{file_path} 包含旧路径引用: {pattern}")
                            
                except Exception as e:
                    logger.warning(f"无法检查文件 {file_path}: {e}")
        
        if path_issues:
            self.issues_found.extend(path_issues)
            logger.error(f"❌ 发现 {len(path_issues)} 个路径引用问题")
        
        self.validation_results['path_references'] = {
            'status': 'pass' if not path_issues else 'fail',
            'issues': path_issues,
            'checked_files': len(files_to_check)
        }
        
        return len(path_issues) == 0
    
    def validate_functionality(self) -> bool:
        """验证基本功能是否正常"""
        logger.info("=== 验证基本功能 ===")
        
        functionality_results = {}
        
        # 测试1: 检查Python模块导入
        try:
            import sys
            sys.path.insert(0, str(self.project_root / "src"))
            import pktmask
            functionality_results['module_import'] = 'pass'
            logger.info("✅ Python模块导入正常")
        except Exception as e:
            functionality_results['module_import'] = f'fail: {e}'
            logger.error(f"❌ Python模块导入失败: {e}")
            self.issues_found.append(f"模块导入失败: {e}")
        
        # 测试2: 检查配置文件加载
        try:
            config_path = self.project_root / "config" / "default" / "mask_config.yaml"
            if config_path.exists():
                functionality_results['config_loading'] = 'pass'
                logger.info("✅ 配置文件存在")
            else:
                functionality_results['config_loading'] = 'fail: 配置文件不存在'
                logger.error("❌ 配置文件不存在")
                self.issues_found.append("配置文件不存在")
        except Exception as e:
            functionality_results['config_loading'] = f'fail: {e}'
            logger.error(f"❌ 配置文件检查失败: {e}")
            self.issues_found.append(f"配置文件检查失败: {e}")
        
        # 测试3: 运行快速测试 (如果可用)
        try:
            test_script = self.project_root / "run_tests.py"
            if test_script.exists():
                result = subprocess.run([
                    sys.executable, str(test_script), "--quick"
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    functionality_results['quick_tests'] = 'pass'
                    logger.info("✅ 快速测试通过")
                else:
                    functionality_results['quick_tests'] = f'fail: 退出码 {result.returncode}'
                    logger.error(f"❌ 快速测试失败: 退出码 {result.returncode}")
                    if self.verbose:
                        logger.error(f"测试输出: {result.stderr}")
                    self.issues_found.append(f"快速测试失败: 退出码 {result.returncode}")
            else:
                functionality_results['quick_tests'] = 'skip: 测试脚本不存在'
                logger.warning("⚠️  测试脚本不存在，跳过测试")
                
        except subprocess.TimeoutExpired:
            functionality_results['quick_tests'] = 'fail: 超时'
            logger.error("❌ 快速测试超时")
            self.issues_found.append("快速测试超时")
        except Exception as e:
            functionality_results['quick_tests'] = f'fail: {e}'
            logger.error(f"❌ 快速测试失败: {e}")
            self.issues_found.append(f"快速测试失败: {e}")
        
        self.validation_results['functionality'] = functionality_results
        
        # 如果模块导入和配置加载都正常，则认为基本功能正常
        basic_checks = ['module_import', 'config_loading']
        all_basic_pass = all(functionality_results.get(check, '').startswith('pass') for check in basic_checks)
        
        return all_basic_pass
    
    def validate_cleanup(self) -> bool:
        """验证清理工作是否完成"""
        logger.info("=== 验证清理工作 ===")
        
        # 应该被移动或删除的文件/目录
        items_to_cleanup = [
            "mask_config.yaml",
            "simple_mask_recipe_sample.json",
            "comprehensive_mask_recipe_sample.json",
            "demo_recipe.json",
            "custom_recipe.json",
            "tls_mask_recipe_sample.json",
            "manual_tcp_masker_test.py",
            "run_tcp_masker_test.py",
            "build_app.sh",
            "sequence_unification_strategy.py",
            "hybrid_architecture_design.py",
            "tcp_payload_masker_phase1_4_validation_report.md",
            "conf",
            "test_configs",
            "hooks",
            "examples/examples"  # 嵌套目录
        ]
        
        cleanup_issues = []
        
        for item in items_to_cleanup:
            item_path = self.project_root / item
            if item_path.exists():
                cleanup_issues.append(f"未清理项目: {item}")
                if self.fix_issues:
                    try:
                        if item_path.is_dir():
                            import shutil
                            shutil.rmtree(item_path)
                        else:
                            item_path.unlink()
                        logger.info(f"✅ 清理项目: {item}")
                    except Exception as e:
                        logger.error(f"❌ 清理失败 {item}: {e}")
        
        if cleanup_issues:
            if not self.fix_issues:
                self.issues_found.extend(cleanup_issues)
                logger.error(f"❌ 发现 {len(cleanup_issues)} 个未清理项目")
        
        self.validation_results['cleanup'] = {
            'status': 'pass' if not cleanup_issues or self.fix_issues else 'fail',
            'issues': cleanup_issues,
            'checked_items': len(items_to_cleanup)
        }
        
        return len(cleanup_issues) == 0 or self.fix_issues
    
    def generate_validation_report(self) -> None:
        """生成验证报告"""
        logger.info("=== 生成验证报告 ===")
        
        report_dir = self.project_root / "output" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON格式详细报告
        json_report = {
            "validation_timestamp": "2025-01-XX",  # 实际使用时需要动态生成
            "project_root": str(self.project_root),
            "validation_options": {
                "verbose": self.verbose,
                "fix_issues": self.fix_issues
            },
            "overall_status": "pass" if not self.issues_found else "fail",
            "issues_count": len(self.issues_found),
            "issues_found": self.issues_found,
            "detailed_results": self.validation_results
        }
        
        json_path = report_dir / "migration_validation_report.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        
        # Markdown格式摘要报告
        md_path = report_dir / "migration_validation_summary.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# PktMask目录结构迁移验证报告\n\n")
            f.write(f"**验证状态**: {'✅ 通过' if not self.issues_found else '❌ 发现问题'}\n")
            f.write(f"**问题数量**: {len(self.issues_found)}\n")
            f.write(f"**修复模式**: {'启用' if self.fix_issues else '禁用'}\n\n")
            
            f.write("## 验证结果概览\n\n")
            for category, result in self.validation_results.items():
                status = result.get('status', 'unknown')
                emoji = '✅' if status == 'pass' else '❌'
                f.write(f"- {emoji} **{category}**: {status}\n")
            
            if self.issues_found:
                f.write("\n## 发现的问题\n\n")
                for i, issue in enumerate(self.issues_found, 1):
                    f.write(f"{i}. {issue}\n")
            
            f.write("\n## 建议后续步骤\n\n")
            if not self.issues_found:
                f.write("🎉 迁移验证通过！项目已成功重组。\n\n")
                f.write("建议执行以下最终验证步骤：\n")
                f.write("1. 运行完整测试套件\n")
                f.write("2. 启动GUI确认功能正常\n")
                f.write("3. 运行示例脚本验证\n")
            else:
                f.write("⚠️ 发现问题需要解决。\n\n")
                f.write("建议执行步骤：\n")
                f.write("1. 使用 --fix-issues 参数自动修复\n")
                f.write("2. 手动检查无法自动修复的问题\n")
                f.write("3. 重新运行验证\n")
        
        logger.info(f"📊 验证报告已生成:")
        logger.info(f"   - 详细报告: {json_path}")
        logger.info(f"   - 摘要报告: {md_path}")
    
    def run_validation(self) -> bool:
        """运行完整的迁移验证"""
        logger.info("🚀 开始PktMask目录结构迁移验证")
        
        validation_steps = [
            ("目录结构", self.validate_directory_structure),
            ("文件迁移", self.validate_file_migrations),
            ("路径引用", self.validate_path_references),
            ("基本功能", self.validate_functionality),
            ("清理工作", self.validate_cleanup)
        ]
        
        passed_steps = 0
        total_steps = len(validation_steps)
        
        for step_name, step_func in validation_steps:
            logger.info(f"📋 验证步骤: {step_name}")
            try:
                if step_func():
                    logger.info(f"✅ {step_name}验证通过")
                    passed_steps += 1
                else:
                    logger.error(f"❌ {step_name}验证失败")
            except Exception as e:
                logger.error(f"❌ {step_name}验证异常: {e}")
                self.issues_found.append(f"{step_name}验证异常: {e}")
        
        # 生成验证报告
        self.generate_validation_report()
        
        # 输出最终结果
        success_rate = (passed_steps / total_steps) * 100
        logger.info(f"📊 验证完成: {passed_steps}/{total_steps} 步骤通过 ({success_rate:.1f}%)")
        
        if self.issues_found:
            logger.error(f"❌ 发现 {len(self.issues_found)} 个问题:")
            for issue in self.issues_found[:5]:  # 只显示前5个问题
                logger.error(f"   • {issue}")
            if len(self.issues_found) > 5:
                logger.error(f"   ... 还有 {len(self.issues_found) - 5} 个问题 (详见报告)")
        else:
            logger.info("🎉 迁移验证完全通过！")
        
        return len(self.issues_found) == 0

def main():
    parser = argparse.ArgumentParser(description="PktMask目录结构迁移验证脚本")
    parser.add_argument("--verbose", action="store_true", help="显示详细验证过程")
    parser.add_argument("--fix-issues", action="store_true", help="自动修复发现的问题")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    validator = MigrationValidator(verbose=args.verbose, fix_issues=args.fix_issues)
    
    try:
        success = validator.run_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ 验证过程失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 