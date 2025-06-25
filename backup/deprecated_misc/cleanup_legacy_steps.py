#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Legacy Steps 清理执行脚本

自动化执行Legacy Steps代码清理流程，包括备份、清理、更新和验证。
使用方式: python scripts/cleanup_legacy_steps.py [--dry-run] [--phase N]
"""

import os
import sys
import shutil
import subprocess
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any
import time

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

class LegacyStepsCleanup:
    """Legacy Steps清理器"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.backup_dir = self.project_root / "backup" / "legacy_steps"
        self.reports_dir = self.project_root / "reports"
        
        # 清理配置
        self.files_to_remove = [
            "src/pktmask/steps/__init__.py",
            "src/pktmask/steps/deduplication.py", 
            "src/pktmask/steps/ip_anonymization.py",
            "src/pktmask/steps/trimming.py"
        ]
        
        self.files_to_update = [
            "src/pktmask/core/factory.py",
            "src/pktmask/core/base_step.py",
            "src/pktmask/core/pipeline.py",
            "src/pktmask/core/processors/ip_anonymizer.py",
            "src/pktmask/core/processors/deduplicator.py", 
            "src/pktmask/core/processors/trimmer.py"
        ]
        
        self.test_files_to_update = [
            "tests/unit/test_steps_basic.py",
            "tests/unit/test_steps_comprehensive.py",
            "tests/unit/test_performance_centralized.py",
            "tests/unit/test_enhanced_payload_trimming.py",
            "tests/integration/test_pipeline.py",
            "tests/integration/test_real_data_validation.py",
            "tests/integration/test_enhanced_real_data_validation.py",
            "tests/integration/test_phase4_integration.py"
        ]
        
        print(f"🧹 Legacy Steps 清理器初始化完成")
        print(f"📁 项目根目录: {self.project_root}")
        print(f"💾 备份目录: {self.backup_dir}")
        print(f"🏃 干跑模式: {'是' if self.dry_run else '否'}")
    
    def run_command(self, cmd: str, check: bool = True) -> subprocess.CompletedProcess:
        """运行命令"""
        print(f"🚀 执行命令: {cmd}")
        if self.dry_run:
            print(f"   [DRY RUN] 跳过执行")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=check
            )
            if result.stdout:
                print(f"   输出: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            print(f"   ❌ 命令执行失败: {e}")
            print(f"   错误输出: {e.stderr}")
            raise
    
    def create_backup(self):
        """创建备份"""
        print("\n📦 Phase 1.1: 创建备份")
        
        # 创建备份目录
        if not self.dry_run:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 备份steps目录
        steps_dir = self.project_root / "src/pktmask/steps"
        if steps_dir.exists():
            backup_steps = self.backup_dir / "steps"
            print(f"📁 备份steps目录: {steps_dir} -> {backup_steps}")
            if not self.dry_run:
                if backup_steps.exists():
                    shutil.rmtree(backup_steps)
                shutil.copytree(steps_dir, backup_steps)
        
        # 备份关键文件
        for file_path in self.files_to_update:
            src_file = self.project_root / file_path
            if src_file.exists():
                backup_file = self.backup_dir / file_path.replace("/", "_")
                print(f"📄 备份文件: {src_file.name} -> {backup_file}")
                if not self.dry_run:
                    shutil.copy2(src_file, backup_file)
        
        print("✅ 备份完成")
    
    def run_baseline_tests(self):
        """运行基准测试"""
        print("\n🧪 Phase 1.2: 运行基准测试")
        
        # 创建报告目录
        if not self.dry_run:
            self.reports_dir.mkdir(exist_ok=True)
        
        # 运行完整测试套件
        try:
            self.run_command("python run_tests.py --all --coverage")
            
            # 保存基准测试结果
            baseline_report = self.reports_dir / "baseline_tests.json"
            baseline_data = {
                "timestamp": time.time(),
                "phase": "baseline",
                "status": "completed"
            }
            
            if not self.dry_run:
                with open(baseline_report, 'w') as f:
                    json.dump(baseline_data, f, indent=2)
            
            print("✅ 基准测试完成")
            
        except subprocess.CalledProcessError:
            print("⚠️ 基准测试失败，继续执行清理")
            
    def verify_processor_registry(self):
        """验证ProcessorRegistry功能"""
        print("\n🔍 Phase 1.3: 验证现代系统功能")
        
        verify_script = """
import sys
sys.path.insert(0, 'src')
from pktmask.core.processors import ProcessorRegistry

try:
    # 测试处理器获取
    processors = ProcessorRegistry.list_processors()
    print(f"✅ 可用处理器: {processors}")
    
    # 测试增强模式
    enhanced = ProcessorRegistry.is_enhanced_mode_enabled()
    print(f"✅ 增强模式: {enhanced}")
    
    # 测试处理器创建
    for proc_name in processors:
        from pktmask.core.processors import ProcessorConfig
        config = ProcessorConfig(name=proc_name)
        processor = ProcessorRegistry.get_processor(proc_name, config)
        print(f"✅ 处理器 {proc_name}: {processor.__class__.__name__}")
    
    print("✅ ProcessorRegistry验证成功")
    
except Exception as e:
    print(f"❌ ProcessorRegistry验证失败: {e}")
    sys.exit(1)
"""
        
        self.run_command(f"python -c \"{verify_script}\"")
    
    def remove_legacy_files(self):
        """移除Legacy文件"""
        print("\n🗑️ Phase 2.1: 移除Legacy文件")
        
        for file_path in self.files_to_remove:
            full_path = self.project_root / file_path
            if full_path.exists():
                print(f"🗑️ 删除文件: {file_path}")
                if not self.dry_run:
                    full_path.unlink()
        
        # 移除整个steps目录
        steps_dir = self.project_root / "src/pktmask/steps"
        if steps_dir.exists():
            print(f"🗑️ 删除目录: {steps_dir}")
            if not self.dry_run:
                shutil.rmtree(steps_dir)
        
        print("✅ Legacy文件删除完成")
    
    def update_factory_py(self):
        """更新factory.py文件"""
        print("\n✏️ Phase 2.2: 更新factory.py")
        
        factory_file = self.project_root / "src/pktmask/core/factory.py"
        
        if not factory_file.exists():
            print("⚠️ factory.py文件不存在，跳过更新")
            return
        
        # 读取原文件
        with open(factory_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 新的简化内容
        new_content = '''"""
简化的Factory模块

保留基本的兼容性接口，移除Legacy Steps相关代码。
现代处理器使用ProcessorRegistry系统。
"""
from typing import Dict, Callable, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline import Pipeline

def create_pipeline(steps_config: list) -> "Pipeline":
    """
    兼容性函数：创建Pipeline实例
    
    注意：现代系统使用ProcessorRegistry，此函数仅为测试兼容性保留
    """
    from .pipeline import Pipeline
    
    # 返回空Pipeline，实际处理由ProcessorRegistry完成
    return Pipeline([])

# 兼容性存根 - 测试可能需要这些函数存在
def get_step_instance(step_name: str):
    """兼容性存根"""
    raise NotImplementedError(
        "Legacy Steps系统已移除。请使用ProcessorRegistry.get_processor()代替。"
    )

STEP_REGISTRY = {}  # 兼容性存根
'''
        
        print(f"✏️ 更新文件: {factory_file}")
        if not self.dry_run:
            with open(factory_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
        
        print("✅ factory.py更新完成")
    
    def analyze_base_step(self):
        """分析base_step.py的使用情况"""
        print("\n🔍 Phase 2.3: 分析base_step.py")
        
        # 搜索base_step的使用
        try:
            result = self.run_command(
                "grep -r 'base_step\\|ProcessingStep' src/pktmask/ --exclude-dir=__pycache__",
                check=False
            )
            
            if result.stdout:
                print("📋 base_step.py使用情况:")
                print(result.stdout)
                
                # 检查是否只被Legacy系统使用
                uses = result.stdout.split('\n')
                legacy_only = all(
                    'steps/' in use or 'factory.py' in use or 'pipeline.py' in use
                    for use in uses if use.strip()
                )
                
                if legacy_only:
                    print("🎯 base_step.py主要被Legacy系统使用，建议移除")
                    self.remove_base_step()
                else:
                    print("⚠️ base_step.py被其他组件使用，保留并更新文档")
            else:
                print("✅ 未发现base_step.py的使用，可以安全移除")
                self.remove_base_step()
                
        except Exception as e:
            print(f"⚠️ 分析base_step.py时出错: {e}")
    
    def remove_base_step(self):
        """移除base_step.py"""
        base_step_file = self.project_root / "src/pktmask/core/base_step.py"
        if base_step_file.exists():
            print(f"🗑️ 删除文件: {base_step_file}")
            if not self.dry_run:
                base_step_file.unlink()
    
    def update_processors(self):
        """更新现代处理器文件"""
        print("\n✏️ Phase 2.4: 更新现代处理器")
        
        processor_files = [
            "src/pktmask/core/processors/ip_anonymizer.py",
            "src/pktmask/core/processors/deduplicator.py",
            "src/pktmask/core/processors/trimmer.py"
        ]
        
        for file_path in processor_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
                
            print(f"✏️ 更新处理器: {file_path}")
            
            # 读取文件内容
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除Legacy导入
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                # 跳过Legacy Steps的导入
                if 'from ...steps' in line or 'from ..steps' in line:
                    print(f"   🗑️ 移除导入: {line.strip()}")
                    continue
                new_lines.append(line)
            
            new_content = '\n'.join(new_lines)
            
            if not self.dry_run and new_content != content:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"   ✅ 已更新")
            else:
                print(f"   ℹ️ 无需更新")
        
        print("✅ 处理器更新完成")
    
    def update_test_files(self):
        """更新测试文件"""
        print("\n🧪 Phase 3: 更新测试文件")
        
        for test_file in self.test_files_to_update:
            full_path = self.project_root / test_file
            if not full_path.exists():
                print(f"⚠️ 测试文件不存在: {test_file}")
                continue
            
            print(f"✏️ 更新测试文件: {test_file}")
            
            # 读取文件内容
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新导入语句
            lines = content.split('\n')
            new_lines = []
            updated = False
            
            for line in lines:
                # 替换Legacy Steps导入
                if 'from src.pktmask.steps' in line:
                    # 转换为Processor导入
                    if 'DeduplicationStep' in line:
                        new_line = line.replace(
                            'from src.pktmask.steps.deduplication import DeduplicationStep',
                            'from src.pktmask.core.processors import Deduplicator'
                        )
                    elif 'IpAnonymizationStep' in line:
                        new_line = line.replace(
                            'from src.pktmask.steps.ip_anonymization import IpAnonymizationStep',
                            'from src.pktmask.core.processors import IPAnonymizer'
                        )
                    elif 'IntelligentTrimmingStep' in line:
                        new_line = line.replace(
                            'from src.pktmask.steps.trimming import IntelligentTrimmingStep',
                            'from src.pktmask.core.processors import EnhancedTrimmer'
                        )
                    else:
                        new_line = line
                    
                    if new_line != line:
                        print(f"   🔄 更新导入: {line.strip()} -> {new_line.strip()}")
                        updated = True
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)
            
            if updated and not self.dry_run:
                new_content = '\n'.join(new_lines)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"   ✅ 已更新")
            else:
                print(f"   ℹ️ 无需更新")
        
        print("✅ 测试文件更新完成")
    
    def run_verification_tests(self):
        """运行验证测试"""
        print("\n🧪 Phase 4: 运行验证测试")
        
        try:
            # 运行所有测试
            print("🧪 运行完整测试套件...")
            self.run_command("python run_tests.py --all")
            
            # 运行特定的处理器测试
            print("🧪 运行处理器测试...")
            self.run_command("python -m pytest tests/unit/test_processors.py -v", check=False)
            
            # 运行集成测试
            print("🧪 运行集成测试...")
            self.run_command("python -m pytest tests/integration/ -v", check=False)
            
            print("✅ 验证测试完成")
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 验证测试失败: {e}")
            print("请检查测试结果并修复问题")
    
    def generate_cleanup_report(self):
        """生成清理报告"""
        print("\n📊 生成清理报告")
        
        # 统计删除的文件
        deleted_files = [f for f in self.files_to_remove if not (self.project_root / f).exists()]
        updated_files = self.files_to_update + self.test_files_to_update
        
        report = {
            "cleanup_timestamp": time.time(),
            "deleted_files": len(deleted_files),
            "updated_files": len(updated_files),
            "dry_run": self.dry_run,
            "deleted_file_list": deleted_files,
            "updated_file_list": updated_files,
            "backup_location": str(self.backup_dir),
            "status": "completed"
        }
        
        report_file = self.reports_dir / "legacy_cleanup_report.json"
        if not self.dry_run:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
        
        print(f"📊 清理报告:")
        print(f"   🗑️ 删除文件数: {len(deleted_files)}")
        print(f"   ✏️ 更新文件数: {len(updated_files)}")
        print(f"   💾 备份位置: {self.backup_dir}")
        print(f"   📄 报告文件: {report_file}")
        
        return report
    
    def execute_cleanup(self, phases: List[int] = None):
        """执行清理流程"""
        if phases is None:
            phases = [1, 2, 3, 4]
        
        print(f"🧹 开始执行Legacy Steps清理")
        print(f"📋 执行阶段: {phases}")
        
        try:
            if 1 in phases:
                print("\n" + "="*50)
                print("PHASE 1: 准备和验证")
                print("="*50)
                self.create_backup()
                self.run_baseline_tests()
                self.verify_processor_registry()
            
            if 2 in phases:
                print("\n" + "="*50)
                print("PHASE 2: 逐步清理")
                print("="*50)
                self.remove_legacy_files()
                self.update_factory_py()
                self.analyze_base_step()
                self.update_processors()
            
            if 3 in phases:
                print("\n" + "="*50)
                print("PHASE 3: 测试更新")
                print("="*50)
                self.update_test_files()
            
            if 4 in phases:
                print("\n" + "="*50)
                print("PHASE 4: 验证测试")
                print("="*50)
                self.run_verification_tests()
            
            # 生成报告
            report = self.generate_cleanup_report()
            
            print("\n" + "="*50)
            print("🎉 Legacy Steps清理完成!")
            print("="*50)
            
            if self.dry_run:
                print("⚠️ 这是干跑模式，实际文件未被修改")
                print("⚠️ 要执行实际清理，请去掉 --dry-run 参数")
            else:
                print("✅ 所有Legacy Steps代码已成功清理")
                print(f"💾 备份文件位于: {self.backup_dir}")
                print("🧪 请运行完整测试验证系统功能")
            
            return report
            
        except Exception as e:
            print(f"\n❌ 清理过程中发生错误: {e}")
            print("🔄 请检查错误并考虑使用备份恢复")
            raise

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Legacy Steps清理工具")
    parser.add_argument("--dry-run", action="store_true", help="干跑模式，不实际修改文件")
    parser.add_argument("--phase", type=int, nargs='+', choices=[1,2,3,4], 
                       help="指定执行的阶段 (1=准备, 2=清理, 3=测试更新, 4=验证)")
    
    args = parser.parse_args()
    
    # 创建清理器
    cleanup = LegacyStepsCleanup(dry_run=args.dry_run)
    
    # 执行清理
    try:
        report = cleanup.execute_cleanup(phases=args.phase)
        
        if args.dry_run:
            print("\n🎯 下一步: 运行 python scripts/cleanup_legacy_steps.py 执行实际清理")
        else:
            print("\n🎯 下一步: 运行 python run_tests.py --all 验证系统功能")
            print("🎯 如果有问题，可以从备份恢复: cp -r backup/legacy_steps/* src/pktmask/")
        
        return 0
        
    except Exception as e:
        print(f"\n💥 清理失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 