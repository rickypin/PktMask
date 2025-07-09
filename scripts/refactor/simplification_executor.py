#!/usr/bin/env python3
"""
PktMask 抽象层次简化重构执行器

自动化执行重构计划中的各个阶段，确保每个步骤都能被验证和回滚。
"""

import os
import sys
import subprocess
import shutil
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

@dataclass
class RefactorStep:
    """重构步骤定义"""
    name: str
    description: str
    files_to_modify: List[str]
    backup_needed: bool = True
    validation_command: Optional[str] = None
    rollback_possible: bool = True

@dataclass
class RefactorResult:
    """重构结果"""
    step_name: str
    success: bool
    duration_seconds: float
    files_modified: List[str]
    backup_path: Optional[str] = None
    error_message: Optional[str] = None
    validation_passed: bool = False

class SimplificationExecutor:
    """简化重构执行器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backup_dir = project_root / "refactor_backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results: List[RefactorResult] = []
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 定义重构步骤
        self.steps = self._define_refactor_steps()
    
    def _define_refactor_steps(self) -> Dict[str, List[RefactorStep]]:
        """定义所有重构步骤"""
        return {
            "phase1": [
                RefactorStep(
                    name="remove_masking_processor_wrapper",
                    description="移除 MaskPayloadProcessor 包装类",
                    files_to_modify=[
                        "src/pktmask/core/processors/masking_processor.py",
                        "src/pktmask/core/pipeline/stages/mask_payload/stage.py"
                    ],
                    validation_command="python -m pytest tests/unit/test_mask_payload_stage.py -v"
                ),
                RefactorStep(
                    name="simplify_processor_adapter",
                    description="简化 PipelineProcessorAdapter",
                    files_to_modify=[
                        "src/pktmask/adapters/processor_adapter.py"
                    ],
                    validation_command="python -m pytest tests/integration/test_pipeline_adapter.py -v"
                ),
                RefactorStep(
                    name="update_adapter_usage",
                    description="更新适配器使用点",
                    files_to_modify=[
                        "src/pktmask/core/pipeline/stages/mask_payload/stage.py",
                        "src/pktmask/core/pipeline/executor.py"
                    ],
                    validation_command="python -m pytest tests/e2e/test_complete_workflow.py -v"
                )
            ],
            "phase2": [
                RefactorStep(
                    name="create_simple_event_system",
                    description="创建简化的事件系统",
                    files_to_modify=[
                        "src/pktmask/core/events/simple_events.py"
                    ],
                    validation_command="python -m pytest tests/unit/test_simple_events.py -v"
                ),
                RefactorStep(
                    name="simplify_event_coordinator",
                    description="简化 EventCoordinator",
                    files_to_modify=[
                        "src/pktmask/gui/managers/event_coordinator.py"
                    ],
                    validation_command="python -m pytest tests/unit/test_event_coordinator.py -v"
                ),
                RefactorStep(
                    name="remove_event_adapter",
                    description="移除 EventDataAdapter",
                    files_to_modify=[
                        "src/pktmask/adapters/event_adapter.py",
                        "src/pktmask/gui/managers/event_coordinator.py"
                    ],
                    validation_command="python -m pytest tests/integration/test_gui_events.py -v"
                )
            ],
            "phase3": [
                RefactorStep(
                    name="create_processor_stage_base",
                    description="创建统一的 ProcessorStage 基类",
                    files_to_modify=[
                        "src/pktmask/core/pipeline/processor_stage.py"
                    ],
                    validation_command="python -m pytest tests/unit/test_processor_stage.py -v"
                ),
                RefactorStep(
                    name="refactor_mask_payload_stage",
                    description="重构 MaskPayloadStage 为直接集成",
                    files_to_modify=[
                        "src/pktmask/core/pipeline/stages/mask_payload/stage.py"
                    ],
                    validation_command="python -m pytest tests/unit/test_mask_payload_stage_direct.py -v"
                ),
                RefactorStep(
                    name="remove_processor_adapter",
                    description="完全移除 PipelineProcessorAdapter",
                    files_to_modify=[
                        "src/pktmask/adapters/processor_adapter.py",
                        "src/pktmask/core/pipeline/executor.py"
                    ],
                    validation_command="python -m pytest tests/e2e/test_pipeline_without_adapters.py -v"
                )
            ],
            "phase4": [
                RefactorStep(
                    name="cleanup_deprecated_files",
                    description="清理废弃的文件和导入",
                    files_to_modify=[
                        "src/pktmask/adapters/__init__.py",
                        "src/pktmask/core/processors/__init__.py"
                    ],
                    validation_command="python -c 'import pktmask; print(\"Import successful\")'"
                ),
                RefactorStep(
                    name="optimize_performance",
                    description="优化性能和内存使用",
                    files_to_modify=[
                        "src/pktmask/core/processors/tshark_enhanced_mask_processor.py"
                    ],
                    validation_command="python scripts/performance/benchmark_simplification.py"
                ),
                RefactorStep(
                    name="update_documentation",
                    description="更新架构文档",
                    files_to_modify=[
                        "docs/architecture/",
                        "README.md"
                    ],
                    validation_command="python scripts/validation/check_documentation.py"
                )
            ]
        }
    
    def execute_phase(self, phase_name: str) -> bool:
        """执行指定阶段的重构"""
        if phase_name not in self.steps:
            print(f"❌ 未知阶段: {phase_name}")
            return False
        
        print(f"\n🚀 开始执行阶段: {phase_name}")
        print("=" * 50)
        
        phase_steps = self.steps[phase_name]
        phase_success = True
        
        for step in phase_steps:
            result = self._execute_step(step)
            self.results.append(result)
            
            if not result.success:
                print(f"❌ 步骤失败: {step.name}")
                print(f"   错误: {result.error_message}")
                phase_success = False
                
                # 询问是否继续
                if not self._ask_continue_on_error():
                    break
            else:
                print(f"✅ 步骤完成: {step.name}")
        
        if phase_success:
            print(f"\n🎉 阶段 {phase_name} 完成!")
        else:
            print(f"\n⚠️  阶段 {phase_name} 部分失败")
        
        return phase_success
    
    def _execute_step(self, step: RefactorStep) -> RefactorResult:
        """执行单个重构步骤"""
        start_time = time.time()
        backup_path = None
        
        print(f"\n📝 执行步骤: {step.name}")
        print(f"   描述: {step.description}")
        
        try:
            # 创建备份
            if step.backup_needed:
                backup_path = self._create_backup(step.files_to_modify)
                print(f"   备份创建: {backup_path}")
            
            # 执行重构逻辑
            modified_files = self._apply_refactor_changes(step)
            
            # 运行验证
            validation_passed = False
            if step.validation_command:
                validation_passed = self._run_validation(step.validation_command)
            
            duration = time.time() - start_time
            
            return RefactorResult(
                step_name=step.name,
                success=True,
                duration_seconds=duration,
                files_modified=modified_files,
                backup_path=backup_path,
                validation_passed=validation_passed
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return RefactorResult(
                step_name=step.name,
                success=False,
                duration_seconds=duration,
                files_modified=[],
                backup_path=backup_path,
                error_message=str(e)
            )
    
    def _create_backup(self, files: List[str]) -> str:
        """创建文件备份"""
        backup_subdir = self.backup_dir / f"step_{len(self.results)}"
        backup_subdir.mkdir(exist_ok=True)
        
        for file_path in files:
            src_path = self.project_root / file_path
            if src_path.exists():
                dst_path = backup_subdir / file_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
        
        return str(backup_subdir)
    
    def _apply_refactor_changes(self, step: RefactorStep) -> List[str]:
        """应用重构变更"""
        # 这里应该调用具体的重构实现
        # 为了演示，我们只是返回文件列表
        print(f"   应用变更到: {step.files_to_modify}")
        
        # 实际实现中，这里会调用具体的重构函数
        # 例如: refactor_functions[step.name]()
        
        return step.files_to_modify
    
    def _run_validation(self, command: str) -> bool:
        """运行验证命令"""
        print(f"   运行验证: {command}")
        try:
            result = subprocess.run(
                command.split(),
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                print("   ✅ 验证通过")
                return True
            else:
                print(f"   ❌ 验证失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("   ⏰ 验证超时")
            return False
        except Exception as e:
            print(f"   ❌ 验证异常: {e}")
            return False
    
    def _ask_continue_on_error(self) -> bool:
        """询问是否在错误时继续"""
        while True:
            response = input("是否继续执行下一步? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("请输入 y 或 n")
    
    def rollback_step(self, step_index: int) -> bool:
        """回滚指定步骤"""
        if step_index >= len(self.results):
            print(f"❌ 无效的步骤索引: {step_index}")
            return False
        
        result = self.results[step_index]
        if not result.backup_path:
            print(f"❌ 步骤 {result.step_name} 没有备份，无法回滚")
            return False
        
        print(f"🔄 回滚步骤: {result.step_name}")
        
        try:
            backup_path = Path(result.backup_path)
            for file_path in result.files_modified:
                src_path = backup_path / file_path
                dst_path = self.project_root / file_path
                
                if src_path.exists():
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    print(f"   恢复: {file_path}")
            
            print(f"✅ 步骤 {result.step_name} 回滚完成")
            return True
            
        except Exception as e:
            print(f"❌ 回滚失败: {e}")
            return False
    
    def generate_report(self) -> str:
        """生成重构报告"""
        report_path = self.backup_dir / "refactor_report.json"
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_steps": len(self.results),
            "successful_steps": sum(1 for r in self.results if r.success),
            "failed_steps": sum(1 for r in self.results if not r.success),
            "total_duration": sum(r.duration_seconds for r in self.results),
            "steps": [
                {
                    "name": r.step_name,
                    "success": r.success,
                    "duration": r.duration_seconds,
                    "files_modified": r.files_modified,
                    "validation_passed": r.validation_passed,
                    "error": r.error_message
                }
                for r in self.results
            ]
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return str(report_path)

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python simplification_executor.py <phase_name>")
        print("可用阶段: phase1, phase2, phase3, phase4, all")
        return
    
    phase_name = sys.argv[1]
    executor = SimplificationExecutor(project_root)
    
    if phase_name == "all":
        # 执行所有阶段
        for phase in ["phase1", "phase2", "phase3", "phase4"]:
            success = executor.execute_phase(phase)
            if not success:
                print(f"\n❌ 阶段 {phase} 失败，停止执行")
                break
    else:
        # 执行指定阶段
        executor.execute_phase(phase_name)
    
    # 生成报告
    report_path = executor.generate_report()
    print(f"\n📊 重构报告已生成: {report_path}")

if __name__ == "__main__":
    main()
