#!/usr/bin/env python3
"""
Masker模块规则处理调试脚本

专门调试Masker模块中_preprocess_keep_rules方法的规则分类逻辑，
验证tls_applicationdata_header规则是否被正确分类到header_only_ranges。
"""

import sys
import os
import json
import logging
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
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MaskerRuleProcessingDebugger:
    """Masker规则处理调试器"""
    
    def __init__(self):
        self.test_file = "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap"
        self.output_dir = Path("output/masker_debug")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置
        self.config = {
            'protocol': 'tls',
            'mode': 'enhanced',
            'marker_config': {},
            'masker_config': {},
            'preserve': {
                'handshake': True,
                'application_data': False,  # 关键：TLS-23应该只保留头部
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
    
    def debug_rule_processing(self):
        """调试规则处理流程"""
        logger.info("开始调试Masker规则处理流程")
        
        debug_results = {
            "test_file": self.test_file,
            "config": self.config,
            "marker_results": {},
            "masker_preprocessing": {},
            "rule_classification": {},
            "problem_analysis": {}
        }
        
        try:
            # 1. 生成Marker规则
            debug_results["marker_results"] = self._debug_marker_rules()
            
            # 2. 调试Masker预处理
            debug_results["masker_preprocessing"] = self._debug_masker_preprocessing(
                debug_results["marker_results"]["keep_rules"]
            )
            
            # 3. 分析规则分类
            debug_results["rule_classification"] = self._analyze_rule_classification(
                debug_results["marker_results"]["keep_rules"],
                debug_results["masker_preprocessing"]["rule_lookup"]
            )
            
            # 4. 问题分析
            debug_results["problem_analysis"] = self._analyze_problems(debug_results)
            
        except Exception as e:
            logger.error(f"调试过程出错: {e}")
            debug_results["error"] = str(e)
        
        # 保存结果
        report_file = self.output_dir / "masker_rule_processing_debug.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(debug_results, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"调试报告已保存: {report_file}")
        
        return debug_results
    
    def _debug_marker_rules(self) -> Dict[str, Any]:
        """调试Marker规则生成"""
        logger.info("调试Marker规则生成")
        
        marker_results = {
            "rules_generated": 0,
            "tls23_rules": [],
            "rule_types": {},
            "keep_rules": None
        }
        
        try:
            # 创建TLS Marker
            marker = TLSProtocolMarker(self.config.get('marker_config', {}))
            marker.preserve_config = self.config.get('preserve', {})
            
            # 分析文件生成规则
            keep_rules = marker.analyze_file(self.test_file, self.config)
            marker_results["keep_rules"] = keep_rules
            marker_results["rules_generated"] = len(keep_rules.rules)
            
            # 分析TLS-23相关规则
            for rule in keep_rules.rules:
                rule_type = rule.rule_type
                marker_results["rule_types"][rule_type] = marker_results["rule_types"].get(rule_type, 0) + 1
                
                if rule.metadata.get('tls_content_type') == 23:
                    marker_results["tls23_rules"].append({
                        'stream_id': rule.stream_id,
                        'direction': rule.direction,
                        'seq_start': rule.seq_start,
                        'seq_end': rule.seq_end,
                        'rule_type': rule.rule_type,
                        'preserve_strategy': rule.metadata.get('preserve_strategy'),
                        'metadata': rule.metadata
                    })
            
            logger.info(f"Marker生成了 {marker_results['rules_generated']} 条规则，"
                       f"其中 {len(marker_results['tls23_rules'])} 条TLS-23规则")
            
        except Exception as e:
            logger.error(f"Marker规则生成失败: {e}")
            marker_results["error"] = str(e)
        
        return marker_results
    
    def _debug_masker_preprocessing(self, keep_rules) -> Dict[str, Any]:
        """调试Masker预处理逻辑"""
        logger.info("调试Masker预处理逻辑")
        
        preprocessing_results = {
            "rule_lookup": {},
            "stream_directions": {},
            "strategy_distribution": {},
            "preprocessing_details": {}
        }
        
        try:
            # 创建PayloadMasker
            masker = PayloadMasker(self.config.get('masker_config', {}))
            
            # 调用预处理方法
            rule_lookup = masker._preprocess_keep_rules(keep_rules)
            preprocessing_results["rule_lookup"] = rule_lookup
            
            # 分析每个流方向的规则分布
            for stream_id, directions in rule_lookup.items():
                preprocessing_results["stream_directions"][stream_id] = {}
                
                for direction, rule_data in directions.items():
                    direction_info = {
                        "header_only_ranges": rule_data.get('header_only_ranges', []),
                        "full_preserve_ranges": rule_data.get('full_preserve_ranges', []),
                        "header_only_count": len(rule_data.get('header_only_ranges', [])),
                        "full_preserve_count": len(rule_data.get('full_preserve_ranges', [])),
                        "total_ranges": len(rule_data.get('header_only_ranges', [])) + len(rule_data.get('full_preserve_ranges', []))
                    }
                    
                    preprocessing_results["stream_directions"][stream_id][direction] = direction_info
            
            # 统计策略分布
            total_header_only = 0
            total_full_preserve = 0
            
            for stream_data in preprocessing_results["stream_directions"].values():
                for direction_data in stream_data.values():
                    total_header_only += direction_data["header_only_count"]
                    total_full_preserve += direction_data["full_preserve_count"]
            
            preprocessing_results["strategy_distribution"] = {
                "header_only_total": total_header_only,
                "full_preserve_total": total_full_preserve,
                "total_rules": total_header_only + total_full_preserve
            }
            
            logger.info(f"预处理完成: {total_header_only} 个header_only规则, "
                       f"{total_full_preserve} 个full_preserve规则")
            
        except Exception as e:
            logger.error(f"Masker预处理失败: {e}")
            preprocessing_results["error"] = str(e)
        
        return preprocessing_results
    
    def _analyze_rule_classification(self, keep_rules, rule_lookup) -> Dict[str, Any]:
        """分析规则分类结果"""
        logger.info("分析规则分类结果")
        
        classification_analysis = {
            "tls23_rule_mapping": [],
            "classification_correctness": {},
            "missing_rules": [],
            "misclassified_rules": []
        }
        
        try:
            # 分析每个TLS-23规则的分类情况
            for rule in keep_rules.rules:
                if rule.metadata.get('tls_content_type') == 23:
                    stream_id = rule.stream_id
                    direction = rule.direction
                    preserve_strategy = rule.metadata.get('preserve_strategy')
                    
                    # 检查规则是否被正确分类
                    if stream_id in rule_lookup and direction in rule_lookup[stream_id]:
                        rule_data = rule_lookup[stream_id][direction]
                        header_only_ranges = rule_data.get('header_only_ranges', [])
                        full_preserve_ranges = rule_data.get('full_preserve_ranges', [])
                        
                        rule_range = (rule.seq_start, rule.seq_end)
                        
                        found_in_header_only = rule_range in header_only_ranges
                        found_in_full_preserve = rule_range in full_preserve_ranges
                        
                        classification_info = {
                            "rule_id": f"{stream_id}:{direction}:{rule.seq_start}-{rule.seq_end}",
                            "rule_type": rule.rule_type,
                            "preserve_strategy": preserve_strategy,
                            "expected_classification": "header_only" if preserve_strategy == "header_only" else "full_preserve",
                            "found_in_header_only": found_in_header_only,
                            "found_in_full_preserve": found_in_full_preserve,
                            "correctly_classified": None
                        }
                        
                        # 判断分类是否正确
                        if preserve_strategy == "header_only":
                            classification_info["correctly_classified"] = found_in_header_only and not found_in_full_preserve
                        else:
                            classification_info["correctly_classified"] = found_in_full_preserve and not found_in_header_only
                        
                        classification_analysis["tls23_rule_mapping"].append(classification_info)
                        
                        # 记录错误分类
                        if not classification_info["correctly_classified"]:
                            classification_analysis["misclassified_rules"].append(classification_info)
                    else:
                        # 规则完全丢失
                        missing_rule = {
                            "rule_id": f"{stream_id}:{direction}:{rule.seq_start}-{rule.seq_end}",
                            "rule_type": rule.rule_type,
                            "preserve_strategy": preserve_strategy
                        }
                        classification_analysis["missing_rules"].append(missing_rule)
            
            # 统计分类正确性
            total_tls23_rules = len(classification_analysis["tls23_rule_mapping"])
            correctly_classified = sum(1 for r in classification_analysis["tls23_rule_mapping"] if r["correctly_classified"])
            
            classification_analysis["classification_correctness"] = {
                "total_tls23_rules": total_tls23_rules,
                "correctly_classified": correctly_classified,
                "misclassified": len(classification_analysis["misclassified_rules"]),
                "missing": len(classification_analysis["missing_rules"]),
                "accuracy": correctly_classified / total_tls23_rules if total_tls23_rules > 0 else 0.0
            }
            
            logger.info(f"规则分类分析: {correctly_classified}/{total_tls23_rules} 正确分类 "
                       f"({classification_analysis['classification_correctness']['accuracy']:.2%})")
            
        except Exception as e:
            logger.error(f"规则分类分析失败: {e}")
            classification_analysis["error"] = str(e)
        
        return classification_analysis
    
    def _analyze_problems(self, debug_results) -> Dict[str, Any]:
        """分析问题"""
        logger.info("分析问题")
        
        problem_analysis = {
            "identified_problems": [],
            "root_cause": None,
            "recommendations": []
        }
        
        try:
            classification = debug_results.get("rule_classification", {})
            correctness = classification.get("classification_correctness", {})
            
            # 检查分类准确性
            if correctness.get("accuracy", 0.0) < 1.0:
                problem_analysis["identified_problems"].append({
                    "type": "rule_classification_error",
                    "description": f"TLS-23规则分类准确性只有 {correctness.get('accuracy', 0.0):.2%}",
                    "details": {
                        "misclassified": correctness.get("misclassified", 0),
                        "missing": correctness.get("missing", 0)
                    }
                })
            
            # 检查是否有TLS-23规则被错误分类
            misclassified_rules = classification.get("misclassified_rules", [])
            if misclassified_rules:
                problem_analysis["identified_problems"].append({
                    "type": "tls23_header_only_misclassification",
                    "description": "TLS-23头部保留规则被错误分类",
                    "details": misclassified_rules
                })
            
            # 检查策略分布
            strategy_dist = debug_results.get("masker_preprocessing", {}).get("strategy_distribution", {})
            if strategy_dist.get("header_only_total", 0) == 0:
                problem_analysis["identified_problems"].append({
                    "type": "no_header_only_rules",
                    "description": "没有header_only规则被正确分类",
                    "details": strategy_dist
                })
            
            # 确定根本原因
            if problem_analysis["identified_problems"]:
                problem_analysis["root_cause"] = "Masker模块的_preprocess_keep_rules方法在处理preserve_strategy时存在逻辑错误"
                
                problem_analysis["recommendations"] = [
                    "检查_preprocess_keep_rules方法中preserve_strategy的映射逻辑",
                    "验证rule.metadata.get('preserve_strategy')是否正确返回'header_only'",
                    "确认TLS-23规则的preserve_strategy字段设置正确",
                    "修复规则分类逻辑，确保header_only规则被正确处理"
                ]
            else:
                problem_analysis["root_cause"] = "规则分类正常，问题可能在其他环节"
            
        except Exception as e:
            logger.error(f"问题分析失败: {e}")
            problem_analysis["error"] = str(e)
        
        return problem_analysis


def main():
    """主函数"""
    debugger = MaskerRuleProcessingDebugger()
    results = debugger.debug_rule_processing()
    
    # 打印关键结果
    print("\n" + "="*60)
    print("Masker规则处理调试结果")
    print("="*60)
    
    if "error" in results:
        print(f"❌ 调试失败: {results['error']}")
        return
    
    # Marker结果
    marker_results = results.get("marker_results", {})
    print(f"Marker生成规则: {marker_results.get('rules_generated', 0)}")
    print(f"TLS-23规则数量: {len(marker_results.get('tls23_rules', []))}")
    
    # Masker预处理结果
    preprocessing = results.get("masker_preprocessing", {})
    strategy_dist = preprocessing.get("strategy_distribution", {})
    print(f"Header-only规则: {strategy_dist.get('header_only_total', 0)}")
    print(f"Full-preserve规则: {strategy_dist.get('full_preserve_total', 0)}")
    
    # 分类正确性
    classification = results.get("rule_classification", {})
    correctness = classification.get("classification_correctness", {})
    print(f"分类准确性: {correctness.get('accuracy', 0.0):.2%}")
    
    # 问题分析
    problems = results.get("problem_analysis", {})
    identified_problems = problems.get("identified_problems", [])
    print(f"\n发现问题数量: {len(identified_problems)}")
    
    for i, problem in enumerate(identified_problems, 1):
        print(f"  {i}. {problem.get('description', 'Unknown problem')}")
    
    if problems.get("root_cause"):
        print(f"\n根本原因: {problems['root_cause']}")
    
    print("="*60)
    
    return results


if __name__ == "__main__":
    main()
