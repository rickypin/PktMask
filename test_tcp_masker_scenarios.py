#!/usr/bin/env python3
"""
TCP载荷掩码器场景测试验证脚本
用于验证test_scenarios/目录下的配置文件和执行场景测试
"""

import os
import sys
import yaml
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import shutil

class TcpMaskerScenarioValidator:
    def __init__(self):
        self.scenarios_dir = Path("test_scenarios")
        self.sample_file = Path("tests/data/tls-single/tls_sample.pcap")
        self.analysis_file = Path("scripts/tls_sample_analysis.json")
        self.output_dir = Path("test_outputs")
        self.test_script = Path("run_tcp_masker_test.py")
        
        # 创建输出目录
        self.output_dir.mkdir(exist_ok=True)
        
        # 加载分析结果
        with open(self.analysis_file, 'r', encoding='utf-8') as f:
            self.analysis_data = json.load(f)
    
    def validate_scenario_configs(self) -> Dict[str, Any]:
        """验证所有场景配置文件的正确性"""
        print("🔍 验证测试场景配置文件...")
        validation_results = {}
        
        scenario_files = list(self.scenarios_dir.glob("scenario_*.yaml"))
        if not scenario_files:
            print("❌ 未找到任何场景配置文件")
            return {}
        
        for scenario_file in sorted(scenario_files):
            print(f"\n📄 验证场景: {scenario_file.name}")
            result = self._validate_single_scenario(scenario_file)
            validation_results[scenario_file.name] = result
            
            # 打印验证结果
            if result['valid']:
                print(f"  ✅ 配置有效: {result['metadata']['name']}")
                print(f"  📊 预期修改包数: {result['metadata']['expected_modified_packets']}")
                print(f"  📦 掩码字节数: {result['metadata']['expected_masked_bytes']}")
            else:
                print(f"  ❌ 配置无效: {', '.join(result['errors'])}")
        
        return validation_results
    
    def _validate_single_scenario(self, scenario_file: Path) -> Dict[str, Any]:
        """验证单个场景配置文件"""
        result = {
            'valid': False,
            'errors': [],
            'metadata': {},
            'keep_range_rules': [],
            'verification': {}
        }
        
        try:
            with open(scenario_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 验证必需字段
            required_sections = ['metadata', 'keep_range_rules', 'verification']
            for section in required_sections:
                if section not in config:
                    result['errors'].append(f"缺少必需的配置段: {section}")
            
            if result['errors']:
                return result
            
            # 验证metadata
            metadata = config['metadata']
            required_metadata = ['name', 'description', 'expected_modified_packets', 'test_type']
            for field in required_metadata:
                if field not in metadata:
                    result['errors'].append(f"metadata缺少字段: {field}")
            
            # 验证keep_range_rules
            keep_rules = config['keep_range_rules']
            if not isinstance(keep_rules, list):
                result['errors'].append("keep_range_rules必须是列表")
            else:
                for i, rule in enumerate(keep_rules):
                    rule_errors = self._validate_keep_range_rule(rule, i)
                    result['errors'].extend(rule_errors)
            
            # 验证verification
            verification = config['verification']
            if 'target_packets' not in verification:
                result['errors'].append("verification缺少target_packets字段")
            
            if not result['errors']:
                result['valid'] = True
                result['metadata'] = metadata
                result['keep_range_rules'] = keep_rules
                result['verification'] = verification
        
        except Exception as e:
            result['errors'].append(f"配置文件解析错误: {str(e)}")
        
        return result
    
    def _validate_keep_range_rule(self, rule: Dict, index: int) -> List[str]:
        """验证单个保留范围规则"""
        errors = []
        required_fields = ['stream_id', 'sequence_start', 'sequence_end']
        
        for field in required_fields:
            if field not in rule:
                errors.append(f"规则{index}缺少字段: {field}")
        
        # 验证序列号范围
        if 'sequence_start' in rule and 'sequence_end' in rule:
            if rule['sequence_start'] >= rule['sequence_end']:
                errors.append(f"规则{index}序列号范围无效: start >= end")
        
        # 验证stream_id格式
        if 'stream_id' in rule:
            stream_id = rule['stream_id']
            if not stream_id.startswith('TCP_'):
                errors.append(f"规则{index}流ID格式错误: {stream_id}")
            if not (stream_id.endswith('_forward') or stream_id.endswith('_reverse')):
                errors.append(f"规则{index}流ID缺少方向后缀: {stream_id}")
        
        return errors
    
    def run_scenario_test(self, scenario_name: str) -> Dict[str, Any]:
        """运行单个场景测试"""
        scenario_file = self.scenarios_dir / f"{scenario_name}.yaml"
        if not scenario_file.exists():
            return {'success': False, 'error': f"场景文件不存在: {scenario_file}"}
        
        print(f"\n🚀 执行场景测试: {scenario_name}")
        
        # 准备输出文件
        output_file = self.output_dir / f"{scenario_name}_output.pcap"
        
        try:
            # 执行测试命令
            cmd = [
                sys.executable, str(self.test_script),
                "--input-pcap", str(self.sample_file),
                "--config", str(scenario_file),
                "--output-pcap", str(output_file),
                "--log-level", "DEBUG"
            ]
            
            print(f"📝 执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ 测试执行成功")
                # 分析输出结果
                analysis = self._analyze_test_output(scenario_name, output_file, result.stdout)
                return {'success': True, 'analysis': analysis, 'stdout': result.stdout}
            else:
                print(f"❌ 测试执行失败: {result.stderr}")
                return {'success': False, 'error': result.stderr, 'stdout': result.stdout}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': "测试执行超时"}
        except Exception as e:
            return {'success': False, 'error': f"测试执行异常: {str(e)}"}
    
    def _analyze_test_output(self, scenario_name: str, output_file: Path, stdout: str) -> Dict[str, Any]:
        """分析测试输出结果"""
        analysis = {
            'file_exists': output_file.exists(),
            'file_size': 0,
            'modified_packets': 0,
            'stdout_analysis': {}
        }
        
        if output_file.exists():
            analysis['file_size'] = output_file.stat().st_size
        
        # 分析stdout中的统计信息
        lines = stdout.split('\n')
        for line in lines:
            if '修改了' in line and '个数据包' in line:
                # 提取修改的包数量
                try:
                    # 查找形如 "2/22 个数据包被修改" 的模式
                    import re
                    match = re.search(r'(\d+)/\d+\s*个数据包被修改', line)
                    if match:
                        analysis['modified_packets'] = int(match.group(1))
                except:
                    pass
            
            if '掩码字节:' in line:
                try:
                    # 提取掩码字节数，格式: "掩码字节: 306"
                    parts = line.split('掩码字节:')[1].split(',')[0]
                    analysis['stdout_analysis']['masked_bytes'] = int(parts.strip())
                except:
                    pass
            
            if '保留字节:' in line:
                try:
                    # 提取保留字节数，格式: "保留字节: 10"
                    parts = line.split('保留字节:')[1].split('(')[0]
                    analysis['stdout_analysis']['kept_bytes'] = int(parts.strip())
                except:
                    pass
        
        return analysis
    
    def run_all_scenarios(self) -> Dict[str, Any]:
        """运行所有场景测试"""
        print("🎯 开始执行所有场景测试...")
        
        # 首先验证配置
        validation_results = self.validate_scenario_configs()
        
        # 执行测试
        test_results = {}
        valid_scenarios = [name for name, result in validation_results.items() if result['valid']]
        
        for scenario_file in valid_scenarios:
            scenario_name = scenario_file.replace('.yaml', '')
            test_result = self.run_scenario_test(scenario_name)
            test_results[scenario_name] = test_result
        
        return {
            'validation': validation_results,
            'tests': test_results,
            'summary': self._generate_test_summary(validation_results, test_results)
        }
    
    def _generate_test_summary(self, validation_results: Dict, test_results: Dict) -> Dict[str, Any]:
        """生成测试总结"""
        total_scenarios = len(validation_results)
        valid_scenarios = sum(1 for r in validation_results.values() if r['valid'])
        successful_tests = sum(1 for r in test_results.values() if r['success'])
        
        return {
            'total_scenarios': total_scenarios,
            'valid_scenarios': valid_scenarios,
            'successful_tests': successful_tests,
            'validation_rate': valid_scenarios / total_scenarios if total_scenarios > 0 else 0,
            'success_rate': successful_tests / valid_scenarios if valid_scenarios > 0 else 0
        }
    
    def generate_test_report(self, results: Dict[str, Any]) -> str:
        """生成详细的测试报告"""
        report = []
        report.append("# TCP载荷掩码器场景测试报告")
        report.append("")
        report.append(f"**生成时间**: {self._get_timestamp()}")
        report.append("")
        
        # 总结信息
        summary = results['summary']
        report.append("## 测试总结")
        report.append(f"- **总场景数**: {summary['total_scenarios']}")
        report.append(f"- **有效场景数**: {summary['valid_scenarios']}")
        report.append(f"- **成功测试数**: {summary['successful_tests']}")
        report.append(f"- **配置验证率**: {summary['validation_rate']:.1%}")
        report.append(f"- **测试成功率**: {summary['success_rate']:.1%}")
        report.append("")
        
        # 场景详情
        report.append("## 场景测试详情")
        for scenario_name, test_result in results['tests'].items():
            report.append(f"### {scenario_name}")
            if test_result['success']:
                analysis = test_result['analysis']
                report.append(f"- ✅ **测试状态**: 成功")
                report.append(f"- **输出文件**: 存在 ({analysis['file_size']} 字节)")
                report.append(f"- **修改包数**: {analysis['modified_packets']}")
            else:
                report.append(f"- ❌ **测试状态**: 失败")
                report.append(f"- **错误信息**: {test_result['error']}")
            report.append("")
        
        return "\n".join(report)
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def main():
    """主函数"""
    validator = TcpMaskerScenarioValidator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "validate":
            # 只验证配置
            results = validator.validate_scenario_configs()
            print(f"\n📊 验证完成，有效场景: {sum(1 for r in results.values() if r['valid'])}/{len(results)}")
        
        elif command == "test":
            if len(sys.argv) > 2:
                # 测试单个场景
                scenario_name = sys.argv[2]
                result = validator.run_scenario_test(scenario_name)
                if result['success']:
                    print(f"✅ 场景 {scenario_name} 测试成功")
                else:
                    print(f"❌ 场景 {scenario_name} 测试失败: {result['error']}")
            else:
                print("❌ 请指定要测试的场景名称")
        
        elif command == "all":
            # 运行所有测试
            results = validator.run_all_scenarios()
            
            # 生成报告
            report = validator.generate_test_report(results)
            
            # 保存报告
            report_file = Path("test_outputs/scenario_test_report.md")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"\n📄 测试报告已保存: {report_file}")
            print(f"✅ 测试成功率: {results['summary']['success_rate']:.1%}")
        
        else:
            print(f"❌ 未知命令: {command}")
    
    else:
        print("TCP载荷掩码器场景测试工具")
        print("用法:")
        print("  python test_tcp_masker_scenarios.py validate  # 验证配置文件")
        print("  python test_tcp_masker_scenarios.py test <scenario_name>  # 测试单个场景")
        print("  python test_tcp_masker_scenarios.py all       # 运行所有测试")

if __name__ == "__main__":
    main() 