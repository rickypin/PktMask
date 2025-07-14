#!/usr/bin/env python3
"""
GUI环境下TLS-23消息体掩码失效问题深度分析

严格禁止修改主程序代码，仅用于验证分析。
重点关注GUI环境与直接调用的差异。
"""

import sys
import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gui_tls23_analysis.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class GUITls23MaskingAnalyzer:
    """GUI环境下TLS-23掩码失效问题分析器"""
    
    def __init__(self):
        self.test_files = [
            "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap",
            "tests/data/tls/tls_1_2_plainip.pcap",
            "tests/data/tls/https-justlaunchpage.pcap"
        ]
        self.output_dir = Path("output/gui_tls23_analysis")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # GUI配置模拟
        self.gui_config = {
            'protocol': 'tls',
            'mode': 'enhanced',
            'marker_config': {},
            'masker_config': {},
            'preserve': {
                'handshake': True,
                'application_data': False,  # 关键：TLS-23消息体应该被掩码
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
        self.analysis_results = {}
    
    def run_comprehensive_analysis(self):
        """运行综合分析"""
        logger.info("开始GUI环境下TLS-23掩码失效问题深度分析")
        
        for test_file in self.test_files:
            if not Path(test_file).exists():
                logger.warning(f"测试文件不存在: {test_file}")
                continue
                
            logger.info(f"分析测试文件: {test_file}")
            file_results = self._analyze_single_file(test_file)
            self.analysis_results[test_file] = file_results
        
        # 生成综合报告
        self._generate_comprehensive_report()
        
        return self.analysis_results
    
    def _analyze_single_file(self, test_file: str) -> Dict[str, Any]:
        """分析单个测试文件"""
        file_results = {
            'test_file': test_file,
            'timestamp': time.time(),
            'gui_simulation': {},
            'direct_call': {},
            'marker_analysis': {},
            'masker_analysis': {},
            'comparison': {}
        }
        
        try:
            # 1. GUI调用模拟分析
            file_results['gui_simulation'] = self._simulate_gui_call(test_file)
            
            # 2. 直接调用分析
            file_results['direct_call'] = self._direct_call_analysis(test_file)
            
            # 3. Marker模块独立分析
            file_results['marker_analysis'] = self._analyze_marker_module(test_file)
            
            # 4. Masker模块独立分析
            file_results['masker_analysis'] = self._analyze_masker_module(test_file)
            
            # 5. 对比分析
            file_results['comparison'] = self._compare_results(file_results)
            
        except Exception as e:
            logger.error(f"分析文件 {test_file} 时出错: {e}")
            file_results['error'] = str(e)
        
        return file_results
    
    def _simulate_gui_call(self, test_file: str) -> Dict[str, Any]:
        """模拟GUI调用流程"""
        logger.info(f"模拟GUI调用流程: {test_file}")
        
        gui_results = {
            'config_used': self.gui_config.copy(),
            'processing_steps': [],
            'output_file': None,
            'stats': None,
            'tls23_verification': {}
        }
        
        try:
            # 模拟GUI配置传递过程
            gui_results['processing_steps'].append("1. GUI配置创建")
            
            # 创建NewMaskPayloadStage实例（模拟GUI调用）
            stage = NewMaskPayloadStage(self.gui_config)
            gui_results['processing_steps'].append("2. NewMaskPayloadStage实例化")
            
            # 初始化（模拟PipelineExecutor中的自动初始化）
            stage.initialize()
            gui_results['processing_steps'].append("3. Stage自动初始化")
            
            # 处理文件
            output_file = self.output_dir / f"gui_output_{Path(test_file).name}"
            stats = stage.process_file(test_file, str(output_file))
            
            gui_results['output_file'] = str(output_file)
            gui_results['stats'] = {
                'packets_processed': stats.packets_processed,
                'packets_modified': stats.packets_modified,
                'duration_ms': stats.duration_ms
            }
            gui_results['processing_steps'].append("4. 文件处理完成")
            
            # 验证TLS-23掩码效果
            gui_results['tls23_verification'] = self._verify_tls23_masking(str(output_file))
            
        except Exception as e:
            logger.error(f"GUI调用模拟失败: {e}")
            gui_results['error'] = str(e)
        
        return gui_results
    
    def _direct_call_analysis(self, test_file: str) -> Dict[str, Any]:
        """直接调用分析"""
        logger.info(f"直接调用分析: {test_file}")
        
        direct_results = {
            'config_used': self.gui_config.copy(),
            'output_file': None,
            'stats': None,
            'tls23_verification': {}
        }
        
        try:
            # 直接创建和调用
            stage = NewMaskPayloadStage(self.gui_config)
            stage.initialize()
            
            output_file = self.output_dir / f"direct_output_{Path(test_file).name}"
            stats = stage.process_file(test_file, str(output_file))
            
            direct_results['output_file'] = str(output_file)
            direct_results['stats'] = {
                'packets_processed': stats.packets_processed,
                'packets_modified': stats.packets_modified,
                'duration_ms': stats.duration_ms
            }
            
            # 验证TLS-23掩码效果
            direct_results['tls23_verification'] = self._verify_tls23_masking(str(output_file))
            
        except Exception as e:
            logger.error(f"直接调用分析失败: {e}")
            direct_results['error'] = str(e)
        
        return direct_results
    
    def _analyze_marker_module(self, test_file: str) -> Dict[str, Any]:
        """独立分析Marker模块"""
        logger.info(f"独立分析Marker模块: {test_file}")
        
        marker_results = {
            'rules_generated': 0,
            'tls23_rules': [],
            'rule_types': {},
            'preserve_config': self.gui_config.get('preserve', {})
        }
        
        try:
            # 创建TLS Marker
            marker = TLSProtocolMarker(self.gui_config.get('marker_config', {}))
            marker.initialize()
            
            # 分析文件生成规则
            keep_rules = marker.analyze_file(test_file, self.gui_config)
            
            marker_results['rules_generated'] = len(keep_rules.rules)
            
            # 分析TLS-23相关规则
            for rule in keep_rules.rules:
                if rule.metadata.get('tls_content_type') == 23:
                    marker_results['tls23_rules'].append({
                        'stream_id': rule.stream_id,
                        'direction': rule.direction,
                        'seq_start': rule.seq_start,
                        'seq_end': rule.seq_end,
                        'rule_type': rule.rule_type,
                        'preserve_strategy': rule.metadata.get('preserve_strategy'),
                        'frame_number': rule.metadata.get('frame_number')
                    })
                
                # 统计规则类型
                rule_type = rule.rule_type
                marker_results['rule_types'][rule_type] = marker_results['rule_types'].get(rule_type, 0) + 1
            
        except Exception as e:
            logger.error(f"Marker模块分析失败: {e}")
            marker_results['error'] = str(e)
        
        return marker_results
    
    def _analyze_masker_module(self, test_file: str) -> Dict[str, Any]:
        """独立分析Masker模块"""
        logger.info(f"独立分析Masker模块: {test_file}")
        
        masker_results = {
            'masking_applied': False,
            'packets_modified': 0,
            'rule_matching': {}
        }
        
        try:
            # 首先生成规则
            marker = TLSProtocolMarker(self.gui_config.get('marker_config', {}))
            marker.initialize()
            keep_rules = marker.analyze_file(test_file, self.gui_config)
            
            # 创建Masker并应用规则
            masker = PayloadMasker(self.gui_config.get('masker_config', {}))
            masker.initialize()
            
            output_file = self.output_dir / f"masker_output_{Path(test_file).name}"
            masking_stats = masker.apply_masking(test_file, str(output_file), keep_rules)
            
            masker_results['masking_applied'] = masking_stats.success
            masker_results['packets_modified'] = masking_stats.packets_modified
            
            # 验证掩码效果
            masker_results['tls23_verification'] = self._verify_tls23_masking(str(output_file))
            
        except Exception as e:
            logger.error(f"Masker模块分析失败: {e}")
            masker_results['error'] = str(e)
        
        return masker_results

    def _verify_tls23_masking(self, pcap_file: str) -> Dict[str, Any]:
        """验证TLS-23消息体掩码效果"""
        logger.info(f"验证TLS-23掩码效果: {pcap_file}")

        verification_results = {
            'file_exists': False,
            'tls23_messages_found': 0,
            'tls23_bodies_masked': 0,
            'tls23_headers_preserved': 0,
            'masking_effectiveness': 0.0,
            'sample_analysis': []
        }

        if not Path(pcap_file).exists():
            logger.warning(f"输出文件不存在: {pcap_file}")
            return verification_results

        verification_results['file_exists'] = True

        try:
            # 使用tshark分析TLS-23消息
            import subprocess

            # 提取TLS-23 ApplicationData消息
            cmd = [
                'tshark', '-r', pcap_file,
                '-Y', 'tls.record.content_type == 23',
                '-T', 'fields',
                '-e', 'frame.number',
                '-e', 'tcp.stream',
                '-e', 'tcp.seq_raw',
                '-e', 'tcp.len',
                '-e', 'tls.record.length',
                '-e', 'data.data'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                verification_results['tls23_messages_found'] = len([l for l in lines if l.strip()])

                # 分析每个TLS-23消息
                for line in lines:
                    if not line.strip():
                        continue

                    fields = line.split('\t')
                    if len(fields) >= 6:
                        frame_num = fields[0]
                        tcp_stream = fields[1]
                        tcp_seq = fields[2]
                        tcp_len = fields[3]
                        tls_len = fields[4]
                        data_hex = fields[5] if len(fields) > 5 else ""

                        # 分析数据内容
                        is_header_preserved, is_body_masked = self._analyze_tls23_data(data_hex, int(tls_len) if tls_len else 0)

                        if is_header_preserved:
                            verification_results['tls23_headers_preserved'] += 1
                        if is_body_masked:
                            verification_results['tls23_bodies_masked'] += 1

                        # 记录样本分析
                        if len(verification_results['sample_analysis']) < 5:
                            verification_results['sample_analysis'].append({
                                'frame': frame_num,
                                'tcp_stream': tcp_stream,
                                'tcp_seq': tcp_seq,
                                'tls_length': tls_len,
                                'header_preserved': is_header_preserved,
                                'body_masked': is_body_masked,
                                'data_preview': data_hex[:40] if data_hex else ""
                            })

                # 计算掩码有效性
                if verification_results['tls23_messages_found'] > 0:
                    verification_results['masking_effectiveness'] = (
                        verification_results['tls23_bodies_masked'] /
                        verification_results['tls23_messages_found']
                    )

        except Exception as e:
            logger.error(f"TLS-23掩码验证失败: {e}")
            verification_results['error'] = str(e)

        return verification_results

    def _analyze_tls23_data(self, data_hex: str, tls_length: int) -> Tuple[bool, bool]:
        """分析TLS-23数据的掩码状态"""
        if not data_hex or len(data_hex) < 10:  # 至少5字节TLS头部
            return False, False

        try:
            # 转换为字节数组
            data_bytes = bytes.fromhex(data_hex.replace(':', ''))

            # 检查TLS记录头部（前5字节）
            if len(data_bytes) >= 5:
                # TLS记录头部应该被保留（非全零）
                header_bytes = data_bytes[:5]
                is_header_preserved = not all(b == 0 for b in header_bytes)

                # 检查消息体部分（5字节之后）
                if len(data_bytes) > 5:
                    body_bytes = data_bytes[5:]
                    # 消息体应该被掩码（全零或大部分为零）
                    zero_count = sum(1 for b in body_bytes if b == 0)
                    is_body_masked = zero_count / len(body_bytes) > 0.8  # 80%以上为零认为被掩码
                else:
                    is_body_masked = True  # 只有头部，认为体部分已被掩码

                return is_header_preserved, is_body_masked

        except Exception as e:
            logger.warning(f"分析TLS-23数据失败: {e}")

        return False, False

    def _compare_results(self, file_results: Dict[str, Any]) -> Dict[str, Any]:
        """对比分析结果"""
        comparison = {
            'gui_vs_direct': {},
            'marker_effectiveness': {},
            'masker_effectiveness': {},
            'problem_identification': []
        }

        try:
            # GUI vs 直接调用对比
            gui_stats = file_results.get('gui_simulation', {}).get('stats', {})
            direct_stats = file_results.get('direct_call', {}).get('stats', {})

            comparison['gui_vs_direct'] = {
                'packets_processed_match': gui_stats.get('packets_processed') == direct_stats.get('packets_processed'),
                'packets_modified_match': gui_stats.get('packets_modified') == direct_stats.get('packets_modified'),
                'gui_packets_processed': gui_stats.get('packets_processed', 0),
                'direct_packets_processed': direct_stats.get('packets_processed', 0),
                'gui_packets_modified': gui_stats.get('packets_modified', 0),
                'direct_packets_modified': direct_stats.get('packets_modified', 0)
            }

            # TLS-23掩码效果对比
            gui_tls23 = file_results.get('gui_simulation', {}).get('tls23_verification', {})
            direct_tls23 = file_results.get('direct_call', {}).get('tls23_verification', {})

            comparison['tls23_masking_comparison'] = {
                'gui_effectiveness': gui_tls23.get('masking_effectiveness', 0.0),
                'direct_effectiveness': direct_tls23.get('masking_effectiveness', 0.0),
                'gui_messages_found': gui_tls23.get('tls23_messages_found', 0),
                'direct_messages_found': direct_tls23.get('tls23_messages_found', 0),
                'effectiveness_match': abs(gui_tls23.get('masking_effectiveness', 0.0) - direct_tls23.get('masking_effectiveness', 0.0)) < 0.1
            }

            # 问题识别
            if comparison['tls23_masking_comparison']['gui_effectiveness'] < 0.8:
                comparison['problem_identification'].append("GUI环境下TLS-23掩码效果不佳")

            if not comparison['gui_vs_direct']['packets_processed_match']:
                comparison['problem_identification'].append("GUI与直接调用处理包数不一致")

            if not comparison['tls23_masking_comparison']['effectiveness_match']:
                comparison['problem_identification'].append("GUI与直接调用TLS-23掩码效果不一致")

        except Exception as e:
            logger.error(f"结果对比失败: {e}")
            comparison['error'] = str(e)

        return comparison

    def _generate_comprehensive_report(self):
        """生成综合分析报告"""
        report_file = self.output_dir / "gui_tls23_analysis_report.json"

        report = {
            'analysis_timestamp': time.time(),
            'analysis_summary': {
                'files_analyzed': len(self.analysis_results),
                'total_problems_found': 0,
                'critical_issues': [],
                'recommendations': []
            },
            'detailed_results': self.analysis_results
        }

        # 汇总问题
        for file_path, results in self.analysis_results.items():
            problems = results.get('comparison', {}).get('problem_identification', [])
            report['analysis_summary']['total_problems_found'] += len(problems)

            for problem in problems:
                if problem not in report['analysis_summary']['critical_issues']:
                    report['analysis_summary']['critical_issues'].append(problem)

        # 生成建议
        if "GUI环境下TLS-23掩码效果不佳" in report['analysis_summary']['critical_issues']:
            report['analysis_summary']['recommendations'].append(
                "检查GUI配置传递过程中preserve_config的正确性"
            )
            report['analysis_summary']['recommendations'].append(
                "验证Marker模块在GUI环境下的TLS-23规则生成逻辑"
            )
            report['analysis_summary']['recommendations'].append(
                "检查Masker模块的规则应用和优先级处理"
            )

        # 保存报告
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"综合分析报告已保存: {report_file}")

        # 打印关键发现
        print("\n" + "="*60)
        print("GUI环境下TLS-23掩码失效问题分析报告")
        print("="*60)
        print(f"分析文件数量: {report['analysis_summary']['files_analyzed']}")
        print(f"发现问题总数: {report['analysis_summary']['total_problems_found']}")
        print("\n关键问题:")
        for issue in report['analysis_summary']['critical_issues']:
            print(f"  - {issue}")
        print("\n建议措施:")
        for rec in report['analysis_summary']['recommendations']:
            print(f"  - {rec}")
        print("="*60)


def main():
    """主函数"""
    analyzer = GUITls23MaskingAnalyzer()
    results = analyzer.run_comprehensive_analysis()

    print(f"\n分析完成，结果保存在: {analyzer.output_dir}")
    return results


if __name__ == "__main__":
    main()
