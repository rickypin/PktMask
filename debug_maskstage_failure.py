#!/usr/bin/env python3
"""
PktMask Maskstage双模块架构掩码失效问题诊断工具

阶段1：增强诊断能力
- 在Marker模块和Masker模块的关键步骤添加详细日志记录
- 记录规则生成数量、内容、传递过程和应用匹配情况
- 添加调试模式输出TLS-23消息的预期vs实际保留规则对比

执行约束：
- 严格遵循用户偏好：使用独立测试脚本进行验证分析
- 在验证阶段严禁修改主程序代码
- 保持100% GUI兼容性和协议无关设计原则
"""

import sys
import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker
from pktmask.core.pipeline.stages.mask_payload_v2.marker.types import KeepRule, KeepRuleSet


class MaskstageFailureDiagnostic:
    """Maskstage双模块架构掩码失效问题诊断器"""
    
    def __init__(self, debug_mode: bool = True):
        self.debug_mode = debug_mode
        self.logger = self._setup_logger()
        
        # 测试文件路径
        self.test_files = [
            "tests/data/tls/tls_1_2_pop_mix.pcapng",  # 完全未掩码案例
            "tests/data/tls/tls_1_0_multi_segment_google-https.pcap",  # 部分未掩码案例
        ]
        
        # 诊断结果
        self.diagnostic_results = {}
    
    def _setup_logger(self) -> logging.Logger:
        """设置详细的调试日志"""
        logger = logging.getLogger("maskstage_diagnostic")
        logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        # 创建文件处理器
        log_file = "output/maskstage_diagnostic.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def diagnose_marker_module(self, pcap_path: str) -> Dict[str, Any]:
        """诊断Marker模块的规则生成过程"""
        self.logger.info(f"=== 开始诊断Marker模块: {pcap_path} ===")
        
        # 创建TLS Marker实例
        marker_config = {
            'preserve': {
                'handshake': True,
                'application_data': False,  # TLS-23应该只保留头部
                'alert': True,
                'change_cipher_spec': True
            }
        }
        
        marker = TLSProtocolMarker(marker_config)
        
        # 记录初始配置
        self.logger.debug(f"Marker配置: {marker_config}")
        
        try:
            # 调用analyze_file方法
            self.logger.info("调用Marker.analyze_file()...")
            keep_rules = marker.analyze_file(pcap_path, marker_config)
            
            # 详细记录规则集合信息
            self.logger.info(f"Marker返回规则集合类型: {type(keep_rules)}")
            self.logger.info(f"规则总数: {len(keep_rules.rules)}")
            self.logger.info(f"TCP流数量: {len(keep_rules.tcp_flows)}")
            self.logger.info(f"元数据: {keep_rules.metadata}")
            
            # 检查是否有错误信息
            if keep_rules.metadata.get('analysis_failed'):
                self.logger.error(f"Marker分析失败: {keep_rules.metadata.get('error')}")
                return {
                    'success': False,
                    'error': keep_rules.metadata.get('error'),
                    'rules_count': 0,
                    'rules': []
                }
            
            # 详细记录每条规则
            tls23_rules = []
            for i, rule in enumerate(keep_rules.rules):
                rule_info = {
                    'index': i,
                    'stream_id': rule.stream_id,
                    'direction': rule.direction,
                    'seq_start': rule.seq_start,
                    'seq_end': rule.seq_end,
                    'rule_type': rule.rule_type,
                    'metadata': rule.metadata,
                    'length': rule.seq_end - rule.seq_start
                }
                
                self.logger.debug(f"规则#{i}: {rule_info}")
                
                # 特别关注TLS-23相关规则
                if 'tls' in rule.rule_type.lower() and '23' in str(rule.metadata):
                    tls23_rules.append(rule_info)
                    self.logger.info(f"发现TLS-23规则: {rule_info}")
            
            self.logger.info(f"TLS-23相关规则数量: {len(tls23_rules)}")
            
            return {
                'success': True,
                'rules_count': len(keep_rules.rules),
                'tls23_rules_count': len(tls23_rules),
                'rules': [
                    {
                        'stream_id': rule.stream_id,
                        'direction': rule.direction,
                        'seq_start': rule.seq_start,
                        'seq_end': rule.seq_end,
                        'rule_type': rule.rule_type,
                        'metadata': rule.metadata
                    }
                    for rule in keep_rules.rules
                ],
                'tls23_rules': tls23_rules,
                'tcp_flows': dict(keep_rules.tcp_flows),
                'metadata': keep_rules.metadata,
                'keep_rules_object': keep_rules  # 保存对象用于后续Masker测试
            }
            
        except Exception as e:
            self.logger.error(f"Marker模块异常: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'rules_count': 0,
                'rules': []
            }
    
    def diagnose_masker_module(self, pcap_path: str, keep_rules: KeepRuleSet) -> Dict[str, Any]:
        """诊断Masker模块的规则应用过程"""
        self.logger.info(f"=== 开始诊断Masker模块: {pcap_path} ===")
        
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # 创建Payload Masker实例
            masker_config = {}
            masker = PayloadMasker(masker_config)
            
            # 记录输入规则信息
            self.logger.info(f"输入规则数量: {len(keep_rules.rules)}")
            self.logger.debug(f"规则详情: {[str(rule) for rule in keep_rules.rules]}")
            
            # 调用apply_masking方法
            self.logger.info("调用Masker.apply_masking()...")
            masking_stats = masker.apply_masking(pcap_path, output_path, keep_rules)
            
            # 详细记录掩码统计信息
            self.logger.info(f"掩码处理成功: {masking_stats.success}")
            self.logger.info(f"处理包数: {masking_stats.processed_packets}")
            self.logger.info(f"修改包数: {masking_stats.modified_packets}")
            self.logger.info(f"掩码字节数: {masking_stats.masked_bytes}")
            self.logger.info(f"保留字节数: {masking_stats.preserved_bytes}")
            self.logger.info(f"错误数: {len(masking_stats.errors)}")
            self.logger.info(f"警告数: {len(masking_stats.warnings)}")

            if masking_stats.errors:
                self.logger.error(f"错误详情: {masking_stats.errors}")
            if masking_stats.warnings:
                self.logger.warning(f"警告详情: {masking_stats.warnings}")

            return {
                'success': masking_stats.success,
                'processed_packets': masking_stats.processed_packets,
                'modified_packets': masking_stats.modified_packets,
                'masked_bytes': masking_stats.masked_bytes,
                'preserved_bytes': masking_stats.preserved_bytes,
                'errors': masking_stats.errors,
                'warnings': masking_stats.warnings,
                'output_file': output_path,
                'masking_stats': masking_stats
            }
            
        except Exception as e:
            self.logger.error(f"Masker模块异常: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'processed_packets': 0,
                'modified_packets': 0,
                'exception_details': {
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'traceback': str(e.__traceback__)
                }
            }
        finally:
            # 清理临时文件
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def diagnose_masker_original_failure(self, pcap_path: str, keep_rules: KeepRuleSet) -> Dict[str, Any]:
        """深度诊断Masker模块原始处理失败的具体原因"""
        self.logger.info(f"=== 开始诊断Masker模块原始处理失败原因: {pcap_path} ===")

        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            # 创建Payload Masker实例，但禁用降级处理
            masker_config = {
                'fallback_handler': {
                    'enable_fallback': False  # 禁用降级处理，强制暴露原始错误
                }
            }
            masker = PayloadMasker(masker_config)

            # 检查输入文件
            if not os.path.exists(pcap_path):
                return {'error': f'输入文件不存在: {pcap_path}'}

            file_size = os.path.getsize(pcap_path)
            self.logger.info(f"输入文件大小: {file_size} 字节")

            # 检查规则集合
            self.logger.info(f"规则集合验证:")
            self.logger.info(f"  - 规则总数: {len(keep_rules.rules)}")
            self.logger.info(f"  - TCP流数: {len(keep_rules.tcp_flows)}")

            # 尝试构建规则查找结构
            self.logger.info("测试规则查找结构构建...")
            try:
                if hasattr(masker, '_build_lookup_structure'):
                    lookup_structure = masker._build_lookup_structure(keep_rules)
                    self.logger.info(f"规则查找结构构建成功")
                    self.logger.info(f"查找结构键: {list(lookup_structure.keys())}")

                    # 检查每个流的规则数据
                    for stream_key, stream_data in lookup_structure.items():
                        self.logger.info(f"流 {stream_key}:")
                        for direction, rule_data in stream_data.items():
                            rule_count = rule_data.get('range_count', 0)
                            self.logger.info(f"  {direction}: {rule_count} 条规则")

                            # 检查规则数据结构
                            if 'ranges' in rule_data:
                                ranges = rule_data['ranges']
                                self.logger.debug(f"    规则范围: {ranges[:3]}..." if len(ranges) > 3 else f"    规则范围: {ranges}")
                else:
                    self.logger.warning("Masker没有_build_lookup_structure方法")

            except Exception as e:
                self.logger.error(f"规则查找结构构建失败: {e}", exc_info=True)
                return {
                    'success': False,
                    'error': f'规则查找结构构建失败: {e}',
                    'error_type': 'lookup_structure_build_error',
                    'exception_details': str(e.__traceback__)
                }

            # 尝试直接调用apply_masking，捕获原始异常
            self.logger.info("开始调用Masker.apply_masking()（禁用降级处理）...")

            try:
                masking_stats = masker.apply_masking(pcap_path, output_path, keep_rules)

                # 如果到这里说明没有异常，检查结果
                self.logger.info(f"原始处理完成，成功: {masking_stats.success}")

                if not masking_stats.success:
                    self.logger.error(f"原始处理失败，错误: {masking_stats.errors}")
                    return {
                        'success': False,
                        'error': 'original_processing_failed',
                        'masking_stats': masking_stats,
                        'errors': masking_stats.errors,
                        'warnings': masking_stats.warnings
                    }

                return {
                    'success': True,
                    'masking_stats': masking_stats,
                    'note': '原始处理成功，没有触发降级'
                }

            except Exception as original_exception:
                # 捕获到原始异常！
                self.logger.error(f"捕获到原始处理异常: {original_exception}", exc_info=True)

                # 详细分析异常
                exception_analysis = {
                    'exception_type': type(original_exception).__name__,
                    'exception_message': str(original_exception),
                    'exception_args': getattr(original_exception, 'args', []),
                }

                # 如果是特定类型的异常，进行更详细的分析
                if 'scapy' in str(original_exception).lower():
                    exception_analysis['category'] = 'scapy_error'
                elif 'memory' in str(original_exception).lower():
                    exception_analysis['category'] = 'memory_error'
                elif 'file' in str(original_exception).lower() or 'io' in str(original_exception).lower():
                    exception_analysis['category'] = 'file_io_error'
                elif 'tcp' in str(original_exception).lower():
                    exception_analysis['category'] = 'tcp_processing_error'
                else:
                    exception_analysis['category'] = 'unknown_error'

                return {
                    'success': False,
                    'error': 'original_processing_exception',
                    'exception_analysis': exception_analysis,
                    'full_exception': str(original_exception),
                    'input_file_size': file_size,
                    'rules_count': len(keep_rules.rules)
                }

        except Exception as e:
            self.logger.error(f"诊断过程异常: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'diagnostic_exception: {e}',
                'exception_type': type(e).__name__
            }
        finally:
            # 清理临时文件
            if os.path.exists(output_path):
                os.unlink(output_path)

    def diagnose_masker_failure_details(self, pcap_path: str, keep_rules: KeepRuleSet) -> Dict[str, Any]:
        """深度诊断Masker模块失败的具体原因"""
        self.logger.info(f"=== 开始深度诊断Masker模块失败原因: {pcap_path} ===")

        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            # 创建Payload Masker实例
            masker_config = {}
            masker = PayloadMasker(masker_config)

            # 检查输入文件是否存在和可读
            if not os.path.exists(pcap_path):
                return {'error': f'输入文件不存在: {pcap_path}'}

            file_size = os.path.getsize(pcap_path)
            self.logger.info(f"输入文件大小: {file_size} 字节")

            # 检查规则集合的有效性
            self.logger.info(f"规则集合验证:")
            self.logger.info(f"  - 规则总数: {len(keep_rules.rules)}")
            self.logger.info(f"  - TCP流数: {len(keep_rules.tcp_flows)}")

            # 按流ID和方向分组规则
            rules_by_flow = {}
            for rule in keep_rules.rules:
                flow_key = f"{rule.stream_id}_{rule.direction}"
                if flow_key not in rules_by_flow:
                    rules_by_flow[flow_key] = []
                rules_by_flow[flow_key].append(rule)

            self.logger.info(f"  - 流分组: {list(rules_by_flow.keys())}")
            for flow_key, rules in rules_by_flow.items():
                self.logger.info(f"    {flow_key}: {len(rules)} 条规则")

            # 尝试调用apply_masking并捕获详细错误
            self.logger.info("开始调用Masker.apply_masking()...")

            # 检查Masker内部方法
            if hasattr(masker, '_build_lookup_structure'):
                self.logger.info("检查规则查找结构构建...")
                try:
                    lookup_structure = masker._build_lookup_structure(keep_rules)
                    self.logger.info(f"规则查找结构构建成功: {type(lookup_structure)}")
                    if hasattr(lookup_structure, 'keys'):
                        self.logger.info(f"查找结构键: {list(lookup_structure.keys())}")
                except Exception as e:
                    self.logger.error(f"规则查找结构构建失败: {e}", exc_info=True)
                    return {'error': f'规则查找结构构建失败: {e}'}

            # 实际调用apply_masking
            masking_stats = masker.apply_masking(pcap_path, output_path, keep_rules)

            # 检查输出文件
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                self.logger.info(f"输出文件大小: {output_size} 字节")

                # 比较文件大小
                if output_size == file_size:
                    self.logger.warning("输出文件与输入文件大小相同，可能是直接复制")
                elif output_size == 0:
                    self.logger.error("输出文件为空")
                else:
                    self.logger.info("输出文件大小正常变化")

            return {
                'success': masking_stats.success,
                'processed_packets': masking_stats.processed_packets,
                'modified_packets': masking_stats.modified_packets,
                'masked_bytes': masking_stats.masked_bytes,
                'preserved_bytes': masking_stats.preserved_bytes,
                'errors': masking_stats.errors,
                'warnings': masking_stats.warnings,
                'input_file_size': file_size,
                'output_file_size': os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                'rules_by_flow': {k: len(v) for k, v in rules_by_flow.items()},
                'masking_stats': masking_stats
            }

        except Exception as e:
            self.logger.error(f"Masker深度诊断异常: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'exception_type': type(e).__name__,
                'exception_details': str(e.__traceback__)
            }
        finally:
            # 清理临时文件
            if os.path.exists(output_path):
                os.unlink(output_path)

    def run_comprehensive_diagnosis(self) -> Dict[str, Any]:
        """运行完整的诊断流程"""
        self.logger.info("开始PktMask Maskstage双模块架构掩码失效问题诊断")
        
        results = {}
        
        for pcap_file in self.test_files:
            if not os.path.exists(pcap_file):
                self.logger.warning(f"测试文件不存在: {pcap_file}")
                continue
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"诊断文件: {pcap_file}")
            self.logger.info(f"{'='*60}")
            
            # 阶段1：诊断Marker模块
            marker_result = self.diagnose_marker_module(pcap_file)
            
            # 阶段2：诊断Masker模块（如果Marker成功）
            masker_result = {}
            masker_deep_result = {}
            if marker_result['success'] and 'keep_rules_object' in marker_result:
                masker_result = self.diagnose_masker_module(
                    pcap_file,
                    marker_result['keep_rules_object']
                )

                # 如果Masker失败，进行深度诊断
                if not masker_result.get('success', False):
                    self.logger.info("Masker模块失败，开始深度诊断...")

                    # 首先尝试捕获原始异常
                    masker_original_result = self.diagnose_masker_original_failure(
                        pcap_file,
                        marker_result['keep_rules_object']
                    )

                    # 然后进行常规深度诊断
                    masker_deep_result = self.diagnose_masker_failure_details(
                        pcap_file,
                        marker_result['keep_rules_object']
                    )

                    # 合并结果
                    masker_deep_result['original_failure_analysis'] = masker_original_result
            
            # 汇总结果
            results[pcap_file] = {
                'marker': marker_result,
                'masker': masker_result,
                'masker_deep': masker_deep_result
            }
        
        # 生成诊断报告
        self._generate_diagnostic_report(results)
        
        return results
    
    def _generate_diagnostic_report(self, results: Dict[str, Any]):
        """生成诊断报告"""
        report_path = "output/maskstage_diagnostic_report.json"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"诊断报告已保存: {report_path}")
        
        # 生成摘要
        self.logger.info("\n" + "="*60)
        self.logger.info("诊断摘要")
        self.logger.info("="*60)
        
        for pcap_file, result in results.items():
            self.logger.info(f"\n文件: {pcap_file}")
            
            marker = result.get('marker', {})
            if marker.get('success'):
                self.logger.info(f"  ✅ Marker模块: 成功生成 {marker.get('rules_count', 0)} 条规则")
                self.logger.info(f"     - TLS-23规则: {marker.get('tls23_rules_count', 0)} 条")
            else:
                self.logger.error(f"  ❌ Marker模块: 失败 - {marker.get('error', '未知错误')}")
            
            masker = result.get('masker', {})
            if masker.get('success'):
                self.logger.info(f"  ✅ Masker模块: 处理 {masker.get('processed_packets', 0)} 包，修改 {masker.get('modified_packets', 0)} 包")
            elif masker:
                self.logger.error(f"  ❌ Masker模块: 失败 - {masker.get('error', '未知错误')}")
            else:
                self.logger.warning(f"  ⚠️  Masker模块: 未执行（Marker失败）")


def main():
    """主函数"""
    print("PktMask Maskstage双模块架构掩码失效问题诊断工具")
    print("阶段1：增强诊断能力")
    print("-" * 60)
    
    # 创建诊断器
    diagnostic = MaskstageFailureDiagnostic(debug_mode=True)
    
    # 运行诊断
    results = diagnostic.run_comprehensive_diagnosis()
    
    print("\n诊断完成！请查看日志文件获取详细信息：")
    print("- output/maskstage_diagnostic.log")
    print("- output/maskstage_diagnostic_report.json")


if __name__ == "__main__":
    main()
