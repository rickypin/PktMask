#!/usr/bin/env python3
"""
全面验证帧144修复效果

对所有TLS测试用例进行回归测试，确保修复没有引入新问题，
同时验证各种TLS消息类型的处理正确性。
"""

import json
import subprocess
import sys
from pathlib import Path
import os

class ComprehensiveFixValidator:
    def __init__(self):
        self.test_data_dir = Path("tests/data/tls")
        self.test_files = [
            "ssl_3.pcap",
            "tls_1_0_multi_segment_google-https.pcap", 
            "tls_1_0_sslerr1-70.pcap",
            "tls_1_2-2.pcap",
            "tls_1_2_double_vlan.pcap",
            "tls_1_2_plainip.pcap",
            "tls_1_2_single_vlan.pcap",
            "tls_1_3_0-RTT-2_22_23_mix.pcap"
        ]
        
    def validate_all_test_files(self):
        """验证所有测试文件的处理效果"""
        print("=== 全面验证修复效果 ===")
        
        try:
            # 导入修复后的Marker模块
            sys.path.insert(0, str(Path.cwd()))
            from src.pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            # 创建测试配置
            test_config = {
                'preserve': {
                    'handshake': True,
                    'application_data': False,  # 只保留头部
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                }
            }
            
            results = []
            
            for test_file in self.test_files:
                file_path = self.test_data_dir / test_file
                if not file_path.exists():
                    print(f"⚠️  测试文件不存在: {test_file}")
                    continue
                
                print(f"\n--- 测试文件: {test_file} ---")
                
                try:
                    # 创建Marker实例
                    marker = TLSProtocolMarker(test_config)
                    
                    # 分析文件
                    ruleset = marker.analyze_file(str(file_path), test_config)
                    
                    # 统计规则
                    rule_stats = self.analyze_ruleset(ruleset)
                    
                    # 检查异常规则
                    anomalies = self.check_rule_anomalies(ruleset)
                    
                    result = {
                        'file': test_file,
                        'total_rules': len(ruleset.rules),
                        'rule_stats': rule_stats,
                        'anomalies': anomalies,
                        'status': 'PASS' if not anomalies else 'WARN'
                    }
                    
                    results.append(result)
                    
                    print(f"  总规则数: {result['total_rules']}")
                    print(f"  规则统计: {rule_stats}")
                    if anomalies:
                        print(f"  ⚠️  异常: {anomalies}")
                    else:
                        print(f"  ✅ 正常")
                        
                except Exception as e:
                    print(f"  ❌ 分析失败: {e}")
                    results.append({
                        'file': test_file,
                        'status': 'FAIL',
                        'error': str(e)
                    })
            
            # 汇总结果
            self.summarize_results(results)
            
        except Exception as e:
            print(f"验证失败: {e}")
            import traceback
            traceback.print_exc()
    
    def analyze_ruleset(self, ruleset):
        """分析规则集的统计信息"""
        stats = {
            'tls_handshake': 0,
            'tls_applicationdata_header': 0,
            'tls_alert': 0,
            'tls_changecipherspec': 0,
            'tls_heartbeat': 0,
            'other': 0
        }
        
        for rule in ruleset.rules:
            rule_type = rule.rule_type.lower()
            if 'handshake' in rule_type:
                stats['tls_handshake'] += 1
            elif 'applicationdata' in rule_type:
                stats['tls_applicationdata_header'] += 1
            elif 'alert' in rule_type:
                stats['tls_alert'] += 1
            elif 'changecipherspec' in rule_type:
                stats['tls_changecipherspec'] += 1
            elif 'heartbeat' in rule_type:
                stats['tls_heartbeat'] += 1
            else:
                stats['other'] += 1
        
        return stats
    
    def check_rule_anomalies(self, ruleset):
        """检查规则中的异常情况"""
        anomalies = []
        
        for rule in ruleset.rules:
            rule_length = rule.seq_end - rule.seq_start
            
            # 检查异常大的规则
            if rule_length > 2048:
                anomalies.append(f"异常大规则: {rule.rule_type} {rule_length}字节")
            
            # 检查ChangeCipherSpec规则大小
            if 'changecipherspec' in rule.rule_type.lower() and rule_length > 100:
                anomalies.append(f"异常大ChangeCipherSpec: {rule_length}字节")
            
            # 检查Alert规则大小
            if 'alert' in rule.rule_type.lower() and rule_length > 50:
                anomalies.append(f"异常大Alert: {rule_length}字节")
            
            # 检查ApplicationData头部规则
            if 'applicationdata' in rule.rule_type.lower() and 'header' in rule.rule_type.lower():
                if rule_length != 5:
                    anomalies.append(f"ApplicationData头部规则长度错误: {rule_length}字节")
            
            # 检查跨段规则的合理性
            if hasattr(rule, 'metadata') and rule.metadata:
                is_cross_segment = rule.metadata.get('is_cross_segment', False)
                if is_cross_segment:
                    declared_length = rule.metadata.get('declared_length', 0)
                    actual_length = rule.metadata.get('actual_length', 0)
                    
                    if declared_length > 16384:
                        anomalies.append(f"跨段规则声明长度过大: {declared_length}字节")
                    
                    if rule_length > 2048:
                        anomalies.append(f"跨段规则范围过大: {rule_length}字节")
        
        return anomalies
    
    def summarize_results(self, results):
        """汇总测试结果"""
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        
        total_files = len(results)
        pass_files = len([r for r in results if r.get('status') == 'PASS'])
        warn_files = len([r for r in results if r.get('status') == 'WARN'])
        fail_files = len([r for r in results if r.get('status') == 'FAIL'])
        
        print(f"总测试文件数: {total_files}")
        print(f"通过: {pass_files}, 警告: {warn_files}, 失败: {fail_files}")
        
        if fail_files > 0:
            print(f"\n❌ 失败的文件:")
            for result in results:
                if result.get('status') == 'FAIL':
                    print(f"  {result['file']}: {result.get('error', 'Unknown error')}")
        
        if warn_files > 0:
            print(f"\n⚠️  有警告的文件:")
            for result in results:
                if result.get('status') == 'WARN':
                    print(f"  {result['file']}: {result['anomalies']}")
        
        # 统计规则类型分布
        print(f"\n规则类型分布:")
        total_stats = {
            'tls_handshake': 0,
            'tls_applicationdata_header': 0,
            'tls_alert': 0,
            'tls_changecipherspec': 0,
            'tls_heartbeat': 0,
            'other': 0
        }
        
        for result in results:
            if 'rule_stats' in result:
                for key, value in result['rule_stats'].items():
                    total_stats[key] += value
        
        for rule_type, count in total_stats.items():
            if count > 0:
                print(f"  {rule_type}: {count}")
        
        # 特别检查ChangeCipherSpec规则
        changecipherspec_count = total_stats['tls_changecipherspec']
        print(f"\n✅ ChangeCipherSpec规则总数: {changecipherspec_count}")
        
        # 检查是否有异常
        has_anomalies = any(result.get('anomalies') for result in results)
        if not has_anomalies:
            print(f"✅ 所有规则都在合理范围内，修复成功！")
        else:
            print(f"⚠️  仍有一些异常需要关注")
    
    def test_specific_frame144(self):
        """专门测试帧144的修复效果"""
        print("\n=== 专门测试帧144修复效果 ===")
        
        test_file = self.test_data_dir / "tls_1_2_double_vlan.pcap"
        if not test_file.exists():
            print("测试文件不存在")
            return
        
        try:
            # 导入修复后的Marker模块
            sys.path.insert(0, str(Path.cwd()))
            from src.pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            test_config = {
                'preserve': {
                    'handshake': True,
                    'application_data': False,
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                }
            }
            
            marker = TLSProtocolMarker(test_config)
            ruleset = marker.analyze_file(str(test_file), test_config)
            
            # 获取帧144数据
            frame144_data = self.get_frame_data(str(test_file), 144)
            if not frame144_data:
                print("无法获取帧144数据")
                return
            
            tcp_seq = int(frame144_data.get('tcp.seq_raw', ['0'])[0])
            tcp_len = int(frame144_data.get('tcp.len', ['0'])[0])
            frame144_start = tcp_seq
            frame144_end = tcp_seq + tcp_len
            
            print(f"帧144范围: {frame144_start} - {frame144_end}")
            
            # 查找与帧144重叠的规则
            overlapping_rules = []
            for rule in ruleset.rules:
                overlap_start = max(rule.seq_start, frame144_start)
                overlap_end = min(rule.seq_end, frame144_end)
                
                if overlap_start < overlap_end:
                    overlapping_rules.append(rule)
            
            print(f"与帧144重叠的规则数: {len(overlapping_rules)}")
            
            for rule in overlapping_rules:
                print(f"  规则: {rule.rule_type} ({rule.seq_start}-{rule.seq_end})")
                
                if rule.rule_type == "tls_applicationdata_header":
                    print(f"    ✅ 正确的ApplicationData头部规则")
                elif "changecipherspec" in rule.rule_type.lower():
                    print(f"    ❌ 仍然有ChangeCipherSpec规则重叠!")
            
        except Exception as e:
            print(f"帧144测试失败: {e}")
    
    def get_frame_data(self, file_path, frame_number):
        """获取指定帧的数据"""
        cmd = [
            "tshark", "-r", file_path,
            "-Y", f"frame.number == {frame_number}",
            "-T", "json",
            "-e", "tcp.seq_raw",
            "-e", "tcp.len"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            frame_data = json.loads(result.stdout)[0]["_source"]["layers"]
            return frame_data
        except Exception:
            return None
    
    def run_validation(self):
        """运行完整验证"""
        print("开始全面验证修复效果")
        print("=" * 60)
        
        self.validate_all_test_files()
        self.test_specific_frame144()
        
        print("\n" + "=" * 60)
        print("验证完成")

if __name__ == "__main__":
    validator = ComprehensiveFixValidator()
    validator.run_validation()
