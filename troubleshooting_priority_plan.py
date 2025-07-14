#!/usr/bin/env python3
"""
问题排查优先级和实施步骤计划
基于配置差异分析制定的系统性排查方案
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Callable
from pathlib import Path
import logging

@dataclass
class TroubleshootingStep:
    """排查步骤"""
    priority: int  # 1-5, 1为最高优先级
    category: str  # 'config', 'code', 'data', 'integration'
    title: str
    description: str
    expected_outcome: str
    tools_needed: List[str]
    estimated_time: str  # 预估时间
    dependencies: List[str]  # 依赖的前置步骤

class TroubleshootingPlan:
    """排查计划"""
    
    def __init__(self):
        self.steps = self._define_steps()
        self.results = {}
    
    def _define_steps(self) -> List[TroubleshootingStep]:
        """定义排查步骤"""
        return [
            # 优先级1: 关键配置验证
            TroubleshootingStep(
                priority=1,
                category="config",
                title="验证配置传递路径",
                description="使用配置对比工具验证 GUI 和脚本的配置是否正确传递到 TLSProtocolMarker",
                expected_outcome="识别配置结构差异，确认 preserve_config 是否正确设置",
                tools_needed=["config_comparison_tool.py"],
                estimated_time="15分钟",
                dependencies=[]
            ),
            
            TroubleshootingStep(
                priority=1,
                category="config",
                title="修复配置结构不匹配",
                description="基于发现的配置差异，修复 GUI 或脚本中的配置结构，确保 TLSProtocolMarker 能正确读取 application_data 设置",
                expected_outcome="配置结构统一，TLS-23 掩码行为一致",
                tools_needed=["代码编辑器"],
                estimated_time="30分钟",
                dependencies=["验证配置传递路径"]
            ),
            
            # 优先级2: 中间结果验证
            TroubleshootingStep(
                priority=2,
                category="code",
                title="Stage 创建和初始化验证",
                description="使用中间检查点工具验证 NewMaskPayloadStage 和 TLSProtocolMarker 的创建过程",
                expected_outcome="确认 Stage 和 Marker 实例的配置属性正确",
                tools_needed=["config_comparison_tool.py (MiddlewareCheckpoint)"],
                estimated_time="20分钟",
                dependencies=["修复配置结构不匹配"]
            ),
            
            TroubleshootingStep(
                priority=2,
                category="data",
                title="规则生成过程验证",
                description="验证 TLSProtocolMarker 为 TLS-23 消息生成的保留规则是否正确",
                expected_outcome="确认 TLS-23 规则生成逻辑正确，只保留5字节头部",
                tools_needed=["debug_logging_enhancer.py", "测试 PCAP 文件"],
                estimated_time="25分钟",
                dependencies=["Stage 创建和初始化验证"]
            ),
            
            # 优先级3: 端到端测试
            TroubleshootingStep(
                priority=3,
                category="integration",
                title="单文件对比测试",
                description="使用相同的测试文件分别通过 GUI 和脚本处理，对比输出结果",
                expected_outcome="两种方式的输出文件完全一致",
                tools_needed=["tests/data/tls/ 中的测试文件", "文件对比工具"],
                estimated_time="20分钟",
                dependencies=["规则生成过程验证"]
            ),
            
            TroubleshootingStep(
                priority=3,
                category="data",
                title="TLS-23 消息体掩码验证",
                description="使用 tls23_marker 工具验证处理后的文件中 TLS-23 消息体是否正确掩码",
                expected_outcome="TLS-23 消息体只保留5字节头部，其余部分被掩码",
                tools_needed=["pktmask.tools.tls23_marker", "JSON 分析工具"],
                estimated_time="15分钟",
                dependencies=["单文件对比测试"]
            ),
            
            # 优先级4: 深度调试
            TroubleshootingStep(
                priority=4,
                category="code",
                title="启用详细调试日志",
                description="使用调试日志增强工具，记录完整的处理流程",
                expected_outcome="获得详细的执行日志，定位具体的差异点",
                tools_needed=["debug_logging_enhancer.py"],
                estimated_time="30分钟",
                dependencies=["TLS-23 消息体掩码验证"]
            ),
            
            TroubleshootingStep(
                priority=4,
                category="code",
                title="代码路径差异分析",
                description="分析 GUI 异步线程处理和脚本同步处理的代码路径差异",
                expected_outcome="识别可能影响处理结果的代码路径差异",
                tools_needed=["代码分析工具", "调试器"],
                estimated_time="45分钟",
                dependencies=["启用详细调试日志"]
            ),
            
            # 优先级5: 回归测试
            TroubleshootingStep(
                priority=5,
                category="integration",
                title="批量文件回归测试",
                description="使用 tests/data/tls/ 目录下的所有文件进行回归测试",
                expected_outcome="所有测试文件的处理结果一致",
                tools_needed=["自动化测试脚本"],
                estimated_time="30分钟",
                dependencies=["代码路径差异分析"]
            ),
            
            TroubleshootingStep(
                priority=5,
                category="integration",
                title="性能和稳定性测试",
                description="验证修复后的代码在不同场景下的性能和稳定性",
                expected_outcome="修复不影响性能，处理结果稳定",
                tools_needed=["性能测试工具", "大文件测试集"],
                estimated_time="60分钟",
                dependencies=["批量文件回归测试"]
            )
        ]
    
    def get_steps_by_priority(self, priority: int) -> List[TroubleshootingStep]:
        """按优先级获取步骤"""
        return [step for step in self.steps if step.priority == priority]
    
    def get_next_steps(self, completed_steps: List[str]) -> List[TroubleshootingStep]:
        """获取下一步可执行的步骤"""
        available_steps = []
        
        for step in self.steps:
            # 检查依赖是否满足
            if all(dep in completed_steps for dep in step.dependencies):
                if step.title not in completed_steps:
                    available_steps.append(step)
        
        # 按优先级排序
        return sorted(available_steps, key=lambda x: x.priority)
    
    def generate_execution_plan(self) -> str:
        """生成执行计划"""
        plan = ["# 问题排查执行计划\n"]
        
        for priority in range(1, 6):
            steps = self.get_steps_by_priority(priority)
            if steps:
                plan.append(f"## 优先级 {priority}\n")
                
                for step in steps:
                    plan.append(f"### {step.title}")
                    plan.append(f"**类别**: {step.category}")
                    plan.append(f"**描述**: {step.description}")
                    plan.append(f"**预期结果**: {step.expected_outcome}")
                    plan.append(f"**所需工具**: {', '.join(step.tools_needed)}")
                    plan.append(f"**预估时间**: {step.estimated_time}")
                    if step.dependencies:
                        plan.append(f"**依赖步骤**: {', '.join(step.dependencies)}")
                    plan.append("")
        
        return "\n".join(plan)
    
    def generate_quick_start_guide(self) -> str:
        """生成快速开始指南"""
        guide = ["# 快速开始指南\n"]
        
        # 获取优先级1的步骤
        critical_steps = self.get_steps_by_priority(1)
        
        guide.append("## 🚨 立即执行（优先级1）\n")
        guide.append("基于前面的分析，我们已经识别出了关键问题：**配置结构不匹配**\n")
        
        for i, step in enumerate(critical_steps, 1):
            guide.append(f"### 步骤 {i}: {step.title}")
            guide.append(f"```bash")
            if "config_comparison_tool.py" in step.tools_needed:
                guide.append(f"python config_comparison_tool.py")
            guide.append(f"```")
            guide.append(f"**预期**: {step.expected_outcome}\n")
        
        guide.append("## 🔧 关键修复点\n")
        guide.append("根据分析，需要修复以下配置结构：\n")
        guide.append("**GUI 配置问题**:")
        guide.append("```python")
        guide.append('# 当前错误结构')
        guide.append('"marker_config": {')
        guide.append('    "preserve": {  # ❌ TLSProtocolMarker 无法读取')
        guide.append('        "application_data": False')
        guide.append('    }')
        guide.append('}')
        guide.append("")
        guide.append('# 应该修复为')
        guide.append('"marker_config": {')
        guide.append('    "application_data": False  # ✅ 直接在顶层')
        guide.append('}')
        guide.append("```\n")
        
        return "\n".join(guide)

def main():
    """主函数"""
    plan = TroubleshootingPlan()
    
    # 生成完整执行计划
    execution_plan = plan.generate_execution_plan()
    Path("troubleshooting_execution_plan.md").write_text(execution_plan, encoding='utf-8')
    
    # 生成快速开始指南
    quick_guide = plan.generate_quick_start_guide()
    Path("quick_start_guide.md").write_text(quick_guide, encoding='utf-8')
    
    print("📋 排查计划已生成:")
    print(f"  - 完整执行计划: troubleshooting_execution_plan.md")
    print(f"  - 快速开始指南: quick_start_guide.md")
    
    # 显示下一步行动
    next_steps = plan.get_next_steps([])
    print(f"\n🎯 建议立即执行的步骤:")
    for step in next_steps[:3]:  # 显示前3个步骤
        print(f"  {step.priority}. {step.title} ({step.estimated_time})")

if __name__ == "__main__":
    main()
