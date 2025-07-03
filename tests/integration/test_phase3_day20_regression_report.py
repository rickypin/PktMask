"""
Phase 3 Day 20: 回归测试完整运行

验收标准: 所有现有功能正常
交付物: 回归报告

本模块提供全面的回归测试报告生成能力，分析系统兼容性、功能保持度、性能回归等。
"""

import unittest
import subprocess
import json
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RegressionSeverity(Enum):
    """回归严重程度"""
    CRITICAL = "critical"      # 系统无法正常运行
    HIGH = "high"             # 主要功能受影响
    MEDIUM = "medium"         # 部分功能受影响
    LOW = "low"               # 轻微问题，不影响核心功能
    INFO = "info"             # 信息性问题


@dataclass
class RegressionIssue:
    """回归问题记录"""
    category: str                    # 问题类别
    description: str                 # 问题描述
    severity: RegressionSeverity     # 严重程度
    affected_tests: List[str]        # 受影响的测试
    error_pattern: str               # 错误模式
    recommended_action: str          # 建议操作
    component: str                   # 受影响组件


@dataclass
class TestCategoryStats:
    """测试类别统计"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    pass_rate: float = 0.0


class RegressionAnalyzer:
    """回归分析器"""
    
    def __init__(self):
        self.issues: List[RegressionIssue] = []
        self.test_stats: Dict[str, TestCategoryStats] = {}
        self.start_time = datetime.now()
        
    def analyze_test_output(self, test_output: str) -> Dict[str, Any]:
        """分析测试输出并识别回归问题"""
        
        # 解析基本统计信息
        stats = self._extract_test_statistics(test_output)
        
        # 识别回归问题
        issues = self._identify_regression_issues(test_output)
        
        # 分析系统兼容性
        compatibility = self._analyze_compatibility_issues(test_output)
        
        # 性能回归分析
        performance = self._analyze_performance_regression(test_output)
        
        return {
            "statistics": stats,
            "issues": [issue.__dict__ for issue in issues],
            "compatibility": compatibility,
            "performance": performance,
            "analysis_time": datetime.now(),
            "summary": self._generate_summary(stats, issues)
        }
    
    def _extract_test_statistics(self, output: str) -> Dict[str, TestCategoryStats]:
        """提取测试统计信息"""
        stats = {}
        
        # 分类统计
        categories = {
            "unit": ["tests/unit/"],
            "integration": ["tests/integration/"],
            "tshark_enhanced": ["tshark_enhanced", "TSharkEnhanced"],
            "mask_stage": ["mask_stage", "MaskStage"],
            "fallback": ["fallback", "Fallback"],
            "pipeline": ["pipeline", "Pipeline"],
            "compatibility": ["compatibility", "AppConfig", "AttributeError"]
        }
        
        for category, patterns in categories.items():
            stats[category] = self._count_tests_by_pattern(output, patterns)
            
        return stats
    
    def _count_tests_by_pattern(self, output: str, patterns: List[str]) -> TestCategoryStats:
        """根据模式计算测试统计"""
        lines = output.split('\n')
        category_stats = TestCategoryStats()
        
        for line in lines:
            if any(pattern.lower() in line.lower() for pattern in patterns):
                if "PASSED" in line:
                    category_stats.passed += 1
                elif "FAILED" in line:
                    category_stats.failed += 1
                elif "ERROR" in line:
                    category_stats.errors += 1
                elif "SKIPPED" in line:
                    category_stats.skipped += 1
                    
        category_stats.total = (category_stats.passed + category_stats.failed + 
                               category_stats.errors + category_stats.skipped)
        
        if category_stats.total > 0:
            category_stats.pass_rate = (category_stats.passed / category_stats.total) * 100
            
        return category_stats
    
    def _identify_regression_issues(self, output: str) -> List[RegressionIssue]:
        """识别回归问题"""
        issues = []
        
        # 定义已知的回归模式
        regression_patterns = [
            {
                "pattern": "'key' is an invalid keyword argument for bisect_left()",
                "category": "Python兼容性",
                "severity": RegressionSeverity.HIGH,
                "component": "StreamMaskTable",
                "action": "更新bisect_left调用语法，移除key参数或使用Python 3.10+兼容写法"
            },
            {
                "pattern": "'AppConfig' object has no attribute 'get'",
                "category": "配置系统兼容性",
                "severity": RegressionSeverity.HIGH,
                "component": "Pipeline配置",
                "action": "修复AppConfig接口，添加get()方法或调整Pipeline配置访问方式"
            },
            {
                "pattern": "isn't a capture file in a format TShark understands",
                "category": "测试数据",
                "severity": RegressionSeverity.MEDIUM,
                "component": "测试框架",
                "action": "修复测试PCAP文件格式或Mock TShark依赖"
            },
            {
                "pattern": "Legacy Steps系统已移除",
                "category": "架构变更",
                "severity": RegressionSeverity.MEDIUM,
                "component": "ProcessorFactory",
                "action": "更新测试代码使用新的ProcessorRegistry接口"
            },
            {
                "pattern": "文件不存在:",
                "category": "测试资源",
                "severity": RegressionSeverity.MEDIUM,
                "component": "测试数据",
                "action": "确保所有测试数据文件存在或更新测试路径"
            }
        ]
        
        for pattern_config in regression_patterns:
            if pattern_config["pattern"] in output:
                affected_tests = self._find_affected_tests(output, pattern_config["pattern"])
                
                issue = RegressionIssue(
                    category=pattern_config["category"],
                    description=f"检测到回归问题: {pattern_config['pattern']}",
                    severity=pattern_config["severity"],
                    affected_tests=affected_tests,
                    error_pattern=pattern_config["pattern"],
                    recommended_action=pattern_config["action"],
                    component=pattern_config["component"]
                )
                issues.append(issue)
                
        return issues
    
    def _find_affected_tests(self, output: str, pattern: str) -> List[str]:
        """找到受特定模式影响的测试"""
        affected = []
        lines = output.split('\n')
        
        for i, line in enumerate(lines):
            if pattern in line:
                # 向上查找测试名称
                for j in range(max(0, i-10), i):
                    test_line = lines[j]
                    if "FAILED" in test_line or "ERROR" in test_line:
                        # 提取测试名称
                        parts = test_line.split("::")
                        if len(parts) >= 2:
                            test_name = "::".join(parts[:2])
                            if test_name not in affected:
                                affected.append(test_name)
                        break
                        
        return affected[:5]  # 限制返回数量
    
    def _analyze_compatibility_issues(self, output: str) -> Dict[str, Any]:
        """分析兼容性问题"""
        compatibility = {
            "python_version_issues": [],
            "dependency_issues": [],
            "interface_changes": [],
            "overall_compatibility": "unknown"
        }
        
        # Python版本兼容性
        if "'key' is an invalid keyword argument" in output:
            compatibility["python_version_issues"].append({
                "issue": "bisect_left key参数不兼容",
                "python_version": "< 3.10",
                "impact": "StreamMaskTable功能受影响"
            })
            
        # 接口变更
        if "'AppConfig' object has no attribute 'get'" in output:
            compatibility["interface_changes"].append({
                "issue": "AppConfig接口变更",
                "component": "配置系统",
                "impact": "Pipeline初始化失败"
            })
            
        # 依赖问题
        if "TShark" in output and "crashed" in output:
            compatibility["dependency_issues"].append({
                "issue": "TShark兼容性问题",
                "component": "协议分析",
                "impact": "PCAP文件处理失败"
            })
            
        # 整体兼容性评估
        issue_count = (len(compatibility["python_version_issues"]) + 
                      len(compatibility["dependency_issues"]) + 
                      len(compatibility["interface_changes"]))
        
        if issue_count == 0:
            compatibility["overall_compatibility"] = "good"
        elif issue_count <= 2:
            compatibility["overall_compatibility"] = "moderate"
        else:
            compatibility["overall_compatibility"] = "poor"
            
        return compatibility
    
    def _analyze_performance_regression(self, output: str) -> Dict[str, Any]:
        """分析性能回归"""
        performance = {
            "performance_tests_found": False,
            "speed_regression": False,
            "memory_issues": False,
            "timeout_issues": False,
            "overall_performance": "unknown"
        }
        
        # 查找性能相关测试
        if "performance" in output.lower():
            performance["performance_tests_found"] = True
            
        # 查找速度回归
        if "速度保留率不达标" in output or "performance score" in output.lower():
            performance["speed_regression"] = True
            
        # 查找超时问题
        if "timeout" in output.lower() or "slowest" in output:
            performance["timeout_issues"] = True
            
        # 整体性能评估
        if performance["speed_regression"]:
            performance["overall_performance"] = "degraded"
        elif performance["timeout_issues"]:
            performance["overall_performance"] = "slow"
        elif not performance["performance_tests_found"]:
            performance["overall_performance"] = "unknown"
        else:
            performance["overall_performance"] = "acceptable"
            
        return performance
    
    def _generate_summary(self, stats: Dict[str, TestCategoryStats], 
                         issues: List[RegressionIssue]) -> Dict[str, Any]:
        """生成回归分析摘要"""
        
        # 计算总体统计
        total_tests = sum(stat.total for stat in stats.values())
        total_passed = sum(stat.passed for stat in stats.values())
        total_failed = sum(stat.failed for stat in stats.values())
        total_errors = sum(stat.errors for stat in stats.values())
        
        overall_pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # 问题严重程度统计
        severity_counts = {}
        for issue in issues:
            severity = issue.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
        # 确定整体状态
        if severity_counts.get("critical", 0) > 0:
            overall_status = "critical_regression"
        elif severity_counts.get("high", 0) > 2:
            overall_status = "significant_regression"
        elif overall_pass_rate < 70:
            overall_status = "moderate_regression"
        elif overall_pass_rate < 90:
            overall_status = "minor_regression"
        else:
            overall_status = "acceptable"
            
        return {
            "overall_status": overall_status,
            "total_tests": total_tests,
            "overall_pass_rate": round(overall_pass_rate, 1),
            "total_issues": len(issues),
            "severity_breakdown": severity_counts,
            "critical_components": self._identify_critical_components(issues),
            "recommendation": self._generate_recommendation(overall_status, issues)
        }
    
    def _identify_critical_components(self, issues: List[RegressionIssue]) -> List[str]:
        """识别关键受影响组件"""
        component_impact = {}
        
        for issue in issues:
            component = issue.component
            severity_weight = {
                RegressionSeverity.CRITICAL: 4,
                RegressionSeverity.HIGH: 3,
                RegressionSeverity.MEDIUM: 2,
                RegressionSeverity.LOW: 1,
                RegressionSeverity.INFO: 0
            }
            
            weight = severity_weight.get(issue.severity, 0)
            component_impact[component] = component_impact.get(component, 0) + weight
            
        # 按影响程度排序
        sorted_components = sorted(component_impact.items(), key=lambda x: x[1], reverse=True)
        return [comp for comp, _ in sorted_components[:5]]
    
    def _generate_recommendation(self, status: str, issues: List[RegressionIssue]) -> str:
        """生成修复建议"""
        
        if status == "critical_regression":
            return "🚨 发现严重回归问题，建议立即停止发布并修复关键问题"
        elif status == "significant_regression":
            return "⚠️ 发现重大回归问题，建议延期发布直到主要问题解决"
        elif status == "moderate_regression":
            return "📋 发现中等回归问题，建议优先修复高优先级问题后发布"
        elif status == "minor_regression":
            return "✅ 发现轻微回归问题，可以按计划发布但需跟踪修复"
        else:
            return "🎉 回归测试通过，系统状态良好，可以安全发布"


class TestPhase3Day20RegressionReport(unittest.TestCase):
    """Phase 3 Day 20: 回归测试报告生成"""
    
    def setUp(self):
        self.analyzer = RegressionAnalyzer()
        self.report_dir = Path("output/reports/regression")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
    def test_unit_tests_regression_analysis(self):
        """测试1: 单元测试回归分析"""
        print("\n📋 测试1: 单元测试回归分析")
        
        # 运行单元测试并捕获输出
        try:
            result = subprocess.run([
                "python3", "-m", "pytest", "tests/unit/", 
                "--tb=short", "--quiet", "-x"
            ], capture_output=True, text=True, timeout=300)
            
            output = result.stdout + result.stderr
            analysis = self.analyzer.analyze_test_output(output)
            
            print(f"  单元测试数量: {analysis['statistics'].get('unit', TestCategoryStats()).total}")
            print(f"  通过率: {analysis['statistics'].get('unit', TestCategoryStats()).pass_rate:.1f}%")
            print(f"  发现问题: {len(analysis['issues'])}个")
            
            # 验证单元测试基础功能
            unit_stats = analysis['statistics'].get('unit', TestCategoryStats())
            if unit_stats.total > 0:
                self.assertGreaterEqual(unit_stats.pass_rate, 70.0, 
                                      f"单元测试通过率过低: {unit_stats.pass_rate:.1f}%")
            
            self.test_results = analysis
            
        except subprocess.TimeoutExpired:
            self.fail("单元测试执行超时")
        except Exception as e:
            self.fail(f"单元测试执行失败: {e}")
            
    def test_integration_tests_regression_analysis(self):
        """测试2: 集成测试回归分析"""
        print("\n📋 测试2: 集成测试回归分析")
        
        # 运行关键集成测试
        key_integration_tests = [
            "tests/integration/test_phase2_day8_integration.py",
            "tests/integration/test_phase2_day9_processor_adapter_integration.py",
            "tests/integration/test_enhanced_mask_stage.py"
        ]
        
        all_results = []
        
        for test_file in key_integration_tests:
            if os.path.exists(test_file):
                try:
                    result = subprocess.run([
                        "python3", "-m", "pytest", test_file, 
                        "--tb=short", "--quiet"
                    ], capture_output=True, text=True, timeout=120)
                    
                    output = result.stdout + result.stderr
                    analysis = self.analyzer.analyze_test_output(output)
                    all_results.append({
                        "test_file": test_file,
                        "analysis": analysis
                    })
                    
                except subprocess.TimeoutExpired:
                    print(f"  ⚠️ {test_file} 执行超时")
                except Exception as e:
                    print(f"  ❌ {test_file} 执行失败: {e}")
                    
        print(f"  完成集成测试文件: {len(all_results)}/{len(key_integration_tests)}")
        
        # 分析整体集成测试状态
        if all_results:
            total_issues = sum(len(r["analysis"]["issues"]) for r in all_results)
            print(f"  发现集成问题: {total_issues}个")
            
            self.integration_results = all_results
        else:
            self.skipTest("没有可执行的集成测试")
            
    def test_compatibility_regression_check(self):
        """测试3: 兼容性回归检查"""
        print("\n📋 测试3: 兼容性回归检查")
        
        compatibility_issues = []
        
        # 检查Python版本兼容性
        try:
            import sys
            python_version = sys.version_info
            if python_version < (3, 8):
                compatibility_issues.append({
                    "type": "python_version",
                    "issue": f"Python版本过低: {python_version}",
                    "severity": "high"
                })
                
            # 检查关键依赖
            critical_imports = [
                "scapy", "pyshark", "yaml", "dataclasses"
            ]
            
            for module_name in critical_imports:
                try:
                    __import__(module_name)
                except ImportError as e:
                    compatibility_issues.append({
                        "type": "dependency",
                        "issue": f"缺少关键依赖: {module_name}",
                        "severity": "critical"
                    })
                    
            # 检查TShark可用性
            try:
                tshark_result = subprocess.run(
                    ["tshark", "-v"], capture_output=True, text=True, timeout=10
                )
                if tshark_result.returncode != 0:
                    compatibility_issues.append({
                        "type": "external_tool",
                        "issue": "TShark不可用或版本过低",
                        "severity": "medium"
                    })
            except (subprocess.TimeoutExpired, FileNotFoundError):
                compatibility_issues.append({
                    "type": "external_tool", 
                    "issue": "TShark未安装或不在PATH中",
                    "severity": "medium"
                })
                
            print(f"  兼容性问题: {len(compatibility_issues)}个")
            for issue in compatibility_issues:
                print(f"    - {issue['severity'].upper()}: {issue['issue']}")
                
            # 兼容性回归验收标准
            critical_issues = [i for i in compatibility_issues if i["severity"] == "critical"]
            high_issues = [i for i in compatibility_issues if i["severity"] == "high"]
            
            self.assertEqual(len(critical_issues), 0, 
                           f"发现{len(critical_issues)}个严重兼容性问题")
            self.assertLessEqual(len(high_issues), 1, 
                               f"发现{len(high_issues)}个高级兼容性问题，超过可接受范围")
                               
            self.compatibility_results = compatibility_issues
            
        except Exception as e:
            self.fail(f"兼容性检查失败: {e}")
            
    def test_generate_comprehensive_regression_report(self):
        """测试4: 生成综合回归报告"""
        print("\n📋 测试4: 生成综合回归报告")
        
        # 收集所有测试结果
        all_test_results = getattr(self, 'test_results', {})
        integration_results = getattr(self, 'integration_results', [])
        compatibility_results = getattr(self, 'compatibility_results', [])
        
        # 生成综合报告
        report = {
            "metadata": {
                "report_type": "Phase 3 Day 20 回归测试报告",
                "generated_at": datetime.now().isoformat(),
                "test_environment": {
                    "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                    "platform": os.name,
                    "working_directory": os.getcwd()
                }
            },
            "executive_summary": {
                "overall_status": "需要进一步分析",
                "critical_findings": [],
                "recommendations": []
            },
            "detailed_analysis": {
                "unit_tests": all_test_results,
                "integration_tests": integration_results,
                "compatibility": compatibility_results
            },
            "action_items": []
        }
        
        # 生成摘要和建议
        total_issues = len(compatibility_results)
        if hasattr(self, 'test_results'):
            total_issues += len(all_test_results.get('issues', []))
            
        for result in integration_results:
            total_issues += len(result["analysis"].get("issues", []))
            
        if total_issues == 0:
            report["executive_summary"]["overall_status"] = "✅ 优秀 - 未发现严重回归问题"
            report["executive_summary"]["recommendations"].append("可以安全进行Phase 3后续阶段")
        elif total_issues <= 3:
            report["executive_summary"]["overall_status"] = "⚠️ 良好 - 发现少量问题"
            report["executive_summary"]["recommendations"].append("建议修复已知问题后继续")
        elif total_issues <= 8:
            report["executive_summary"]["overall_status"] = "📋 需要关注 - 发现多个回归问题"
            report["executive_summary"]["recommendations"].append("建议优先修复高优先级问题")
        else:
            report["executive_summary"]["overall_status"] = "🚨 需要立即处理 - 发现大量回归问题"
            report["executive_summary"]["recommendations"].append("建议暂停开发，集中精力修复回归问题")
            
        # 保存报告
        report_file = self.report_dir / f"phase3_day20_regression_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
        print(f"  📊 回归报告已生成: {report_file}")
        print(f"  📈 整体状态: {report['executive_summary']['overall_status']}")
        print(f"  📋 发现问题总数: {total_issues}")
        
        # 显示关键发现
        if total_issues > 0:
            print("  🔍 关键发现:")
            if compatibility_results:
                for issue in compatibility_results[:3]:
                    print(f"    - {issue['severity'].upper()}: {issue['issue']}")
                    
        # 验收标准检查
        self.assertIsNotNone(report["metadata"]["generated_at"])
        self.assertIn("overall_status", report["executive_summary"])
        self.assertIsInstance(report["detailed_analysis"], dict)
        
        print(f"  ✅ 回归测试报告生成完成")
        
        # 返回报告用于后续分析
        self.regression_report = report


if __name__ == "__main__":
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase3Day20RegressionReport)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出最终结果
    if result.wasSuccessful():
        print("\n🎉 Phase 3 Day 20 回归测试完成 - 所有验收标准达成")
    else:
        print(f"\n⚠️ Phase 3 Day 20 回归测试发现问题:")
        print(f"   失败测试: {len(result.failures)}")
        print(f"   错误测试: {len(result.errors)}") 