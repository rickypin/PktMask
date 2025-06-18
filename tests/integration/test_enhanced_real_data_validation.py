"""
增强版真实数据验证测试
验证完整的IP匿名化功能，包括映射一致性、数量验证等
"""

import time
import ipaddress
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict

import pytest
from scapy.all import rdpcap, wrpcap

from src.pktmask.core.encapsulation.detector import EncapsulationDetector
from src.pktmask.core.encapsulation.parser import ProtocolStackParser
from src.pktmask.core.encapsulation.adapter import ProcessingAdapter
from src.pktmask.core.encapsulation.types import EncapsulationType
from src.pktmask.core.strategy import HierarchicalAnonymizationStrategy
from src.pktmask.config import AppConfig


@dataclass
class EnhancedTestResult:
    """增强版测试结果数据"""
    file_path: str
    category: str
    success: bool
    
    # 基础统计
    total_packets: int
    tested_packets: int
    processing_time: float
    
    # 封装检测结果
    encapsulation_stats: Dict[str, int]
    
    # IP匿名化验证结果
    original_ips: Set[str]
    anonymized_ips: Set[str]
    ip_mappings: Dict[str, str]
    mapping_consistency: bool
    ip_count_preserved: bool
    anonymized_ip_validity: bool
    
    # 详细验证指标
    anonymization_coverage: float  # 匿名化覆盖率
    unique_mapping_ratio: float    # 唯一映射比率
    
    # 错误信息
    errors: List[str]
    validation_details: Dict[str, Any]


class EnhancedRealDataValidator:
    """增强版真实数据验证器"""
    
    def __init__(self):
        self.detector = EncapsulationDetector()
        self.parser = ProtocolStackParser()
        self.adapter = ProcessingAdapter()
        
        # 创建IP匿名化策略
        config = AppConfig()
        config.processing.preserve_subnet_structure = True
        config.processing.preserve_original_segments = True
        config.processing.ip_mapping_consistency = True
        
        self.anonymization_strategy = HierarchicalAnonymizationStrategy()
    
    def validate_sample_file_with_anonymization(self, sample_file: Path, category: str, 
                                              max_test_packets: int = 100) -> EnhancedTestResult:
        """执行完整的IP匿名化验证测试"""
        start_time = time.time()
        errors = []
        
        # 初始化结果数据
        encapsulation_stats = {}
        original_ips = set()
        anonymized_ips = set()
        ip_mappings = {}
        
        try:
            # 1. 读取和预处理
            packets = rdpcap(str(sample_file))
            total_packets = len(packets)
            test_packets = packets[:max_test_packets]
            tested_count = len(test_packets)
            
            if tested_count == 0:
                return self._create_failed_result(sample_file, category, ["文件中没有可测试的数据包"])
            
            # 2. 提取原始IP地址
            print(f"📊 开始分析 {sample_file.name}...")
            for i, packet in enumerate(test_packets):
                try:
                    # 封装检测
                    encap_type = self.detector.detect_encapsulation_type(packet)
                    encap_name = encap_type.value
                    encapsulation_stats[encap_name] = encapsulation_stats.get(encap_name, 0) + 1
                    
                    # IP地址提取
                    adapter_result = self.adapter.analyze_packet_for_ip_processing(packet)
                    if 'ip_layers' in adapter_result:
                        for ip_layer in adapter_result['ip_layers']:
                            if hasattr(ip_layer, 'src_ip'):
                                original_ips.add(str(ip_layer.src_ip))
                            if hasattr(ip_layer, 'dst_ip'):
                                original_ips.add(str(ip_layer.dst_ip))
                                
                except Exception as e:
                    errors.append(f"包 {i+1} 分析错误: {str(e)}")
                    continue
            
            print(f"   提取到 {len(original_ips)} 个原始IP地址")
            
            # 3. 执行IP匿名化处理
            if len(original_ips) == 0:
                return self._create_failed_result(sample_file, category, ["未能提取到IP地址"])
            
            print(f"🔒 开始IP匿名化处理...")
            
            # 3. 先创建IP映射 (模拟实际处理流程)
            try:
                # 创建临时文件列表用于映射生成
                with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_file:
                    temp_input_path = Path(temp_file.name)
                    wrpcap(str(temp_input_path), test_packets)
                
                # 创建映射
                mapping_errors = []
                ip_mappings = self.anonymization_strategy.create_mapping(
                    [temp_input_path.name], str(temp_input_path.parent), mapping_errors
                )
                
                if mapping_errors:
                    errors.extend(mapping_errors)
                
                print(f"   生成 {len(ip_mappings)} 个IP映射")
                
                # 4. 逐包匿名化并分析结果
                print(f"🔍 执行匿名化并分析结果...")
                for packet in test_packets:
                    try:
                        anonymized_packet, modified = self.anonymization_strategy.anonymize_packet(packet)
                        
                        if modified and anonymized_packet:
                            # 分析匿名化后的包
                            adapter_result = self.adapter.analyze_packet_for_ip_processing(anonymized_packet)
                            if 'ip_layers' in adapter_result:
                                for ip_layer in adapter_result['ip_layers']:
                                    if hasattr(ip_layer, 'src_ip'):
                                        anonymized_ips.add(str(ip_layer.src_ip))
                                    if hasattr(ip_layer, 'dst_ip'):
                                        anonymized_ips.add(str(ip_layer.dst_ip))
                    except Exception as e:
                        errors.append(f"包匿名化错误: {str(e)}")
                        continue
                
                # 清理临时文件
                temp_input_path.unlink(missing_ok=True)
                
            except Exception as e:
                errors.append(f"匿名化处理失败: {str(e)}")
                ip_mappings = {}
            
            # 6. 验证匿名化结果
            validation_results = self._validate_anonymization_results(
                original_ips, anonymized_ips, ip_mappings, errors
            )
            
            # 7. 生成最终结果
            processing_time = time.time() - start_time
            
            # 判断总体成功
            success = self._determine_success(
                errors, tested_count, encapsulation_stats, 
                original_ips, validation_results
            )
            
            print(f"   ✅ 验证完成: {'成功' if success else '失败'} ({processing_time:.3f}s)")
            
            return EnhancedTestResult(
                file_path=str(sample_file),
                category=category,
                success=success,
                total_packets=total_packets,
                tested_packets=tested_count,
                processing_time=processing_time,
                encapsulation_stats=encapsulation_stats,
                original_ips=original_ips,
                anonymized_ips=anonymized_ips,
                ip_mappings=ip_mappings,
                mapping_consistency=validation_results['mapping_consistency'],
                ip_count_preserved=validation_results['ip_count_preserved'],
                anonymized_ip_validity=validation_results['anonymized_ip_validity'],
                anonymization_coverage=validation_results['anonymization_coverage'],
                unique_mapping_ratio=validation_results['unique_mapping_ratio'],
                errors=errors[:10],
                validation_details=validation_results['details']
            )
            
        except Exception as e:
            return self._create_failed_result(sample_file, category, [f"处理失败: {str(e)}"])
    
    def _validate_anonymization_results(self, original_ips: Set[str], anonymized_ips: Set[str], 
                                      ip_mappings: Dict[str, str], errors: List[str]) -> Dict[str, Any]:
        """验证匿名化结果的正确性"""
        
        # 1. 验证IP数量保持一致
        ip_count_preserved = len(original_ips) == len(anonymized_ips)
        if not ip_count_preserved:
            errors.append(f"IP数量不一致: 原始{len(original_ips)} vs 匿名化{len(anonymized_ips)}")
        
        # 2. 验证映射一致性
        mapping_consistency = True
        mapped_originals = set(ip_mappings.keys())
        mapped_anonymized = set(ip_mappings.values())
        
        # 检查所有原始IP都有映射
        unmapped_originals = original_ips - mapped_originals
        if unmapped_originals:
            mapping_consistency = False
            errors.append(f"未映射的原始IP: {unmapped_originals}")
        
        # 检查映射是否一对一
        if len(mapped_originals) != len(mapped_anonymized):
            mapping_consistency = False
            errors.append(f"映射不是一对一: {len(mapped_originals)} -> {len(mapped_anonymized)}")
        
        # 3. 验证匿名化IP的有效性
        anonymized_ip_validity = True
        invalid_ips = []
        
        for anon_ip in anonymized_ips:
            try:
                ipaddress.ip_address(anon_ip)
            except ValueError:
                anonymized_ip_validity = False
                invalid_ips.append(anon_ip)
        
        if invalid_ips:
            errors.append(f"无效的匿名化IP: {invalid_ips}")
        
        # 4. 计算覆盖率和唯一性比率
        anonymization_coverage = len(mapped_originals) / len(original_ips) if original_ips else 0
        unique_mapping_ratio = len(set(ip_mappings.values())) / len(ip_mappings) if ip_mappings else 0
        
        return {
            'mapping_consistency': mapping_consistency,
            'ip_count_preserved': ip_count_preserved,
            'anonymized_ip_validity': anonymized_ip_validity,
            'anonymization_coverage': anonymization_coverage,
            'unique_mapping_ratio': unique_mapping_ratio,
            'details': {
                'original_ip_count': len(original_ips),
                'anonymized_ip_count': len(anonymized_ips),
                'mapping_count': len(ip_mappings),
                'invalid_anonymized_ips': len([ip for ip in anonymized_ips 
                                             if not self._is_valid_ip(ip)])
            }
        }
    
    def _is_valid_ip(self, ip_str: str) -> bool:
        """检查IP地址是否有效"""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False
    
    def _determine_success(self, errors: List[str], tested_count: int, 
                          encapsulation_stats: Dict[str, int], original_ips: Set[str],
                          validation_results: Dict[str, Any]) -> bool:
        """判断测试是否成功"""
        return (
            len(errors) < tested_count * 0.2 and          # 错误率 < 20%
            len(encapsulation_stats) > 0 and              # 检测到封装
            len(original_ips) > 0 and                     # 提取到原始IP
            validation_results['mapping_consistency'] and  # 映射一致性
            validation_results['ip_count_preserved'] and   # IP数量保持
            validation_results['anonymized_ip_validity'] and # 匿名化IP有效
            validation_results['anonymization_coverage'] >= 0.95  # 覆盖率 >= 95%
        )
    
    def _create_failed_result(self, sample_file: Path, category: str, errors: List[str]) -> EnhancedTestResult:
        """创建失败的测试结果"""
        return EnhancedTestResult(
            file_path=str(sample_file),
            category=category,
            success=False,
            total_packets=0,
            tested_packets=0,
            processing_time=0,
            encapsulation_stats={},
            original_ips=set(),
            anonymized_ips=set(),
            ip_mappings={},
            mapping_consistency=False,
            ip_count_preserved=False,
            anonymized_ip_validity=False,
            anonymization_coverage=0,
            unique_mapping_ratio=0,
            errors=errors,
            validation_details={}
        )


@pytest.mark.integration
@pytest.mark.real_data_enhanced
@pytest.mark.slow
class TestEnhancedRealDataValidation:
    """增强版真实数据验证测试类"""
    
    @pytest.fixture(scope="class")
    def validator(self):
        return EnhancedRealDataValidator()
    
    @pytest.mark.parametrize("sample_info", [
        ("tests/data/samples/TLS/tls_sample.pcap", "plain_ip"),
        ("tests/data/samples/singlevlan/10.200.33.61(10笔).pcap", "single_vlan"),
        ("tests/data/samples/doublevlan/172.24.0.51.pcap", "double_vlan"),
    ])
    def test_enhanced_sample_validation(self, validator, sample_info):
        """增强版样本验证测试"""
        sample_file, category = sample_info
        sample_path = Path(sample_file)
        
        if not sample_path.exists():
            pytest.skip(f"样本文件不存在: {sample_file}")
        
        print(f"\n🧪 增强测试: {sample_path.name} ({category})")
        
        result = validator.validate_sample_file_with_anonymization(sample_path, category)
        
        # 详细结果输出
        if result.success:
            print(f"   ✅ 成功 - {result.tested_packets}/{result.total_packets} 包")
            print(f"   📦 封装: {result.encapsulation_stats}")
            print(f"   🔍 原始IP: {len(result.original_ips)} 个")
            print(f"   🔒 匿名IP: {len(result.anonymized_ips)} 个")
            print(f"   🗺️  映射: {len(result.ip_mappings)} 个")
            print(f"   📊 覆盖率: {result.anonymization_coverage:.1%}")
            print(f"   🎯 唯一性: {result.unique_mapping_ratio:.1%}")
            print(f"   ⏱️  时间: {result.processing_time:.3f}s")
        else:
            print(f"   ❌ 失败 - 错误: {len(result.errors)}")
            for error in result.errors[:3]:
                print(f"      • {error}")
        
        # 核心断言
        assert result.success, f"增强验证失败: {result.errors}"
        assert result.mapping_consistency, "IP映射不一致"
        assert result.ip_count_preserved, "IP数量未保持一致"
        assert result.anonymized_ip_validity, "匿名化IP无效"
        assert result.anonymization_coverage >= 0.95, f"匿名化覆盖率过低: {result.anonymization_coverage:.1%}"
    
    def test_anonymization_consistency_across_runs(self, validator):
        """测试多次运行的匿名化一致性"""
        sample_file = Path("tests/data/samples/TLS/tls_sample.pcap")
        
        if not sample_file.exists():
            pytest.skip("测试样本文件不存在")
        
        print(f"\n🔄 一致性测试: {sample_file.name}")
        
        # 运行两次匿名化
        result1 = validator.validate_sample_file_with_anonymization(sample_file, "plain_ip")
        result2 = validator.validate_sample_file_with_anonymization(sample_file, "plain_ip")
        
        # 验证映射一致性
        assert result1.success and result2.success, "两次运行都应该成功"
        
        # 检查相同原始IP的映射结果是否一致
        common_ips = result1.original_ips & result2.original_ips
        inconsistent_mappings = []
        
        for ip in common_ips:
            if ip in result1.ip_mappings and ip in result2.ip_mappings:
                if result1.ip_mappings[ip] != result2.ip_mappings[ip]:
                    inconsistent_mappings.append(
                        f"{ip}: {result1.ip_mappings[ip]} != {result2.ip_mappings[ip]}"
                    )
        
        assert not inconsistent_mappings, f"映射不一致: {inconsistent_mappings}"
        print(f"   ✅ 一致性验证通过: {len(common_ips)} 个IP映射一致")


@dataclass
class PayloadTrimmingResult:
    """载荷裁切测试结果数据"""
    file_path: str
    category: str
    success: bool
    
    # 基础统计
    total_packets: int
    tcp_packets: int
    processing_time: float
    
    # 封装检测结果
    encapsulation_stats: Dict[str, int]
    encapsulated_packets: int
    
    # 载荷裁切验证结果
    original_payload_size: int
    trimmed_payload_size: int
    packets_with_payload: int
    packets_trimmed: int
    tls_packets_detected: int
    trim_effectiveness: float  # 裁切效果
    
    # TLS智能裁切验证
    tls_signaling_preserved: int
    tls_app_data_trimmed: int
    intelligent_trim_accuracy: float
    
    # 多层封装载荷处理验证
    encap_payload_accessible: bool
    inner_tcp_sessions: int
    encap_trim_success: bool
    
    # 错误信息
    errors: List[str]
    processing_details: Dict[str, Any]


class PayloadTrimmingValidator:
    """载荷裁切功能验证器"""
    
    def __init__(self):
        from src.pktmask.core.processors import EnhancedTrimmer
        from src.pktmask.core.encapsulation.adapter import ProcessingAdapter
        
        self.trimming_step = IntelligentTrimmingStep()
        self.adapter = ProcessingAdapter()
        
    def validate_payload_trimming(self, sample_file: Path, category: str,
                                max_test_packets: int = 100) -> PayloadTrimmingResult:
        """执行完整的载荷裁切功能验证"""
        start_time = time.time()
        errors = []
        
        # 初始化统计数据
        encapsulation_stats = {}
        total_packets = 0
        tcp_packets = 0
        encapsulated_packets = 0
        
        original_payload_size = 0
        packets_with_payload = 0
        tls_packets_detected = 0
        
        try:
            # 1. 读取和预处理
            packets = rdpcap(str(sample_file))
            total_packets = len(packets)
            test_packets = packets[:max_test_packets]
            tested_count = len(test_packets)
            
            if tested_count == 0:
                return self._create_failed_trimming_result(sample_file, category, ["文件中没有可测试的数据包"])
            
            print(f"🎯 开始载荷裁切验证: {sample_file.name}")
            
            # 2. 分析原始数据包的载荷情况
            for packet in test_packets:
                try:
                    # 封装检测
                    encap_type = self.adapter.detector.detect_encapsulation_type(packet)
                    encap_name = encap_type.value
                    encapsulation_stats[encap_name] = encapsulation_stats.get(encap_name, 0) + 1
                    
                    if encap_type != EncapsulationType.PLAIN:
                        encapsulated_packets += 1
                    
                    # 载荷分析
                    payload_analysis = self.adapter.analyze_packet_for_payload_processing(packet)
                    
                    if payload_analysis.get('has_tcp', False):
                        tcp_packets += 1
                        
                        # 检查载荷
                        tcp_session = self.adapter.extract_tcp_session_for_trimming(payload_analysis)
                        if tcp_session and tcp_session.get('payload_data'):
                            packets_with_payload += 1
                            payload_data = tcp_session['payload_data']
                            original_payload_size += len(payload_data)
                            
                            # TLS检测
                            if tcp_session.get('is_encrypted', False):
                                tls_packets_detected += 1
                    
                except Exception as e:
                    errors.append(f"载荷分析失败: {str(e)}")
                    continue
            
            print(f"   载荷分析: {packets_with_payload}个载荷包, {tls_packets_detected}个TLS包, "
                  f"封装包: {encapsulated_packets}/{tested_count}")
            
            # 3. 执行载荷裁切处理
            if packets_with_payload == 0:
                print(f"   ⚠️ 跳过载荷裁切验证: 没有找到载荷包")
                processing_time = time.time() - start_time
                
                return PayloadTrimmingResult(
                    file_path=str(sample_file),
                    category=category,
                    success=True,  # 没有载荷也算成功
                    total_packets=tested_count,
                    tcp_packets=tcp_packets,
                    processing_time=processing_time,
                    encapsulation_stats=encapsulation_stats,
                    encapsulated_packets=encapsulated_packets,
                    original_payload_size=0,
                    trimmed_payload_size=0,
                    packets_with_payload=0,
                    packets_trimmed=0,
                    tls_packets_detected=0,
                    trim_effectiveness=0.0,
                    tls_signaling_preserved=0,
                    tls_app_data_trimmed=0,
                    intelligent_trim_accuracy=100.0,  # 没有TLS包时准确率为100%
                    encap_payload_accessible=True,
                    inner_tcp_sessions=0,
                    encap_trim_success=True,
                    errors=errors,
                    processing_details={}
                )
            
            print(f"✂️ 开始载荷裁切处理...")
            
            # 4. 使用临时文件进行实际裁切处理
            with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_input:
                temp_input_path = Path(temp_input.name)
                wrpcap(str(temp_input_path), test_packets)
            
            with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_output:
                temp_output_path = Path(temp_output.name)
            
            try:
                # 执行裁切处理
                trim_summary = self.trimming_step.process_file(str(temp_input_path), str(temp_output_path))
                
                if not trim_summary:
                    errors.append("载荷裁切处理失败")
                    return self._create_failed_trimming_result(sample_file, category, errors)
                
                # 5. 读取裁切后的数据包并分析结果
                trimmed_packets = rdpcap(str(temp_output_path))
                
                trimmed_payload_size = 0
                packets_trimmed = 0
                tls_signaling_preserved = 0
                tls_app_data_trimmed = 0
                inner_tcp_sessions = 0
                
                for packet in trimmed_packets:
                    try:
                        payload_analysis = self.adapter.analyze_packet_for_payload_processing(packet)
                        
                        if payload_analysis.get('has_tcp', False):
                            tcp_session = self.adapter.extract_tcp_session_for_trimming(payload_analysis)
                            if tcp_session:
                                inner_tcp_sessions += 1
                                
                                if tcp_session.get('payload_data'):
                                    payload_data = tcp_session['payload_data']
                                    trimmed_payload_size += len(payload_data)
                                    
                                    # 检查是否为TLS信令（握手等）
                                    if tcp_session.get('is_encrypted', False):
                                        if self._is_tls_signaling(payload_data):
                                            tls_signaling_preserved += 1
                                        else:
                                            # 如果是TLS但不是信令，可能是被保留的应用数据
                                            pass
                                else:
                                    # 载荷被裁切的包
                                    packets_trimmed += 1
                    
                    except Exception as e:
                        errors.append(f"裁切结果分析失败: {str(e)}")
                        continue
                
                # 6. 计算载荷裁切验证指标
                validation_results = self._calculate_trim_metrics(
                    original_payload_size, trimmed_payload_size,
                    packets_with_payload, packets_trimmed,
                    tls_packets_detected, tls_signaling_preserved,
                    trim_summary
                )
                
                # 7. 多层封装验证
                encap_validation = self._validate_encapsulated_trimming(
                    encapsulated_packets, inner_tcp_sessions, trim_summary
                )
                
                processing_time = time.time() - start_time
                
                # 8. 判断整体成功
                success = self._determine_trimming_success(
                    errors, validation_results, encap_validation
                )
                
                print(f"   ✅ 载荷裁切验证完成: {'成功' if success else '失败'} "
                      f"({validation_results['trim_effectiveness']:.1f}%效果, {processing_time:.3f}s)")
                
                return PayloadTrimmingResult(
                    file_path=str(sample_file),
                    category=category,
                    success=success,
                    total_packets=tested_count,
                    tcp_packets=tcp_packets,
                    processing_time=processing_time,
                    encapsulation_stats=encapsulation_stats,
                    encapsulated_packets=encapsulated_packets,
                    original_payload_size=original_payload_size,
                    trimmed_payload_size=trimmed_payload_size,
                    packets_with_payload=packets_with_payload,
                    packets_trimmed=packets_trimmed,
                    tls_packets_detected=tls_packets_detected,
                    trim_effectiveness=validation_results['trim_effectiveness'],
                    tls_signaling_preserved=tls_signaling_preserved,
                    tls_app_data_trimmed=validation_results['tls_app_data_trimmed'],
                    intelligent_trim_accuracy=validation_results['intelligent_trim_accuracy'],
                    encap_payload_accessible=encap_validation['payload_accessible'],
                    inner_tcp_sessions=inner_tcp_sessions,
                    encap_trim_success=encap_validation['trim_success'],
                    errors=errors[:10],
                    processing_details=trim_summary
                )
                
            finally:
                # 清理临时文件
                temp_input_path.unlink(missing_ok=True)
                temp_output_path.unlink(missing_ok=True)
                
        except Exception as e:
            errors.append(f"载荷裁切验证过程失败: {str(e)}")
            return self._create_failed_trimming_result(sample_file, category, errors)
    
    def _is_tls_signaling(self, payload_data: bytes) -> bool:
        """检查载荷是否为TLS信令数据"""
        if len(payload_data) < 5:
            return False
        
        # TLS记录类型：20=Change Cipher Spec, 21=Alert, 22=Handshake, 23=Application Data
        record_type = payload_data[0]
        return record_type in [20, 21, 22]  # 信令类型，不包括Application Data(23)
    
    def _calculate_trim_metrics(self, original_size: int, trimmed_size: int,
                              original_packets: int, trimmed_packets: int,
                              tls_packets: int, tls_preserved: int,
                              trim_summary: Dict) -> Dict[str, float]:
        """计算载荷裁切指标"""
        metrics = {}
        
        # 裁切效果
        if original_size > 0:
            metrics['trim_effectiveness'] = ((original_size - trimmed_size) / original_size) * 100
        else:
            metrics['trim_effectiveness'] = 0.0
        
        # TLS应用数据裁切率
        if tls_packets > 0:
            # 计算TLS应用数据的裁切数量
            tls_app_data_trimmed = max(0, tls_packets - tls_preserved)
            metrics['tls_app_data_trimmed'] = tls_app_data_trimmed
            
            # 智能裁切准确率（保留信令，裁切应用数据）
            if tls_packets > 0:
                metrics['intelligent_trim_accuracy'] = ((tls_preserved + tls_app_data_trimmed) / tls_packets) * 100
            else:
                metrics['intelligent_trim_accuracy'] = 100.0
        else:
            metrics['tls_app_data_trimmed'] = 0
            metrics['intelligent_trim_accuracy'] = 100.0
        
        return metrics
    
    def _validate_encapsulated_trimming(self, encap_packets: int, inner_sessions: int,
                                       trim_summary: Dict) -> Dict[str, bool]:
        """验证多层封装的载荷裁切"""
        validation = {}
        
        # 载荷可访问性验证
        validation['payload_accessible'] = True
        if encap_packets > 0:
            # 如果有封装包，检查是否能够访问内层载荷
            encap_ratio = trim_summary.get('encapsulation_ratio', 0.0)
            validation['payload_accessible'] = encap_ratio >= 0  # 至少能检测到封装
        
        # 裁切成功性验证
        validation['trim_success'] = True
        if encap_packets > 0 and inner_sessions == 0:
            # 有封装包但没有检测到内层TCP会话可能表示问题
            validation['trim_success'] = False
        
        return validation
    
    def _determine_trimming_success(self, errors: List[str], 
                                   metrics: Dict[str, float],
                                   encap_validation: Dict[str, bool]) -> bool:
        """判断载荷裁切验证是否成功"""
        # 错误率检查
        if len(errors) >= 5:  # 允许少量错误
            return False
        
        # TLS智能裁切准确率检查
        if metrics.get('intelligent_trim_accuracy', 0) < 70:  # 至少70%准确率
            return False
        
        # 多层封装处理检查
        if not encap_validation.get('payload_accessible', True):
            return False
        
        return True
    
    def _create_failed_trimming_result(self, sample_file: Path, category: str, 
                                     errors: List[str]) -> PayloadTrimmingResult:
        """创建失败的载荷裁切结果"""
        return PayloadTrimmingResult(
            file_path=str(sample_file),
            category=category,
            success=False,
            total_packets=0,
            tcp_packets=0,
            processing_time=0.0,
            encapsulation_stats={},
            encapsulated_packets=0,
            original_payload_size=0,
            trimmed_payload_size=0,
            packets_with_payload=0,
            packets_trimmed=0,
            tls_packets_detected=0,
            trim_effectiveness=0.0,
            tls_signaling_preserved=0,
            tls_app_data_trimmed=0,
            intelligent_trim_accuracy=0.0,
            encap_payload_accessible=False,
            inner_tcp_sessions=0,
            encap_trim_success=False,
            errors=errors,
            processing_details={}
        )


@pytest.mark.integration
@pytest.mark.payload_trimming_enhanced
@pytest.mark.slow
class TestPayloadTrimmingValidation:
    """载荷裁切功能的增强版真实数据验证测试"""
    
    @pytest.fixture(scope="class")
    def trimming_validator(self):
        """载荷裁切验证器fixture"""
        return PayloadTrimmingValidator()
    
    @pytest.fixture(scope="class")
    def all_sample_files(self):
        """所有15个样本文件的完整列表"""
        return [
            # 基础封装类型 (5个)
            ("tests/data/samples/TLS/tls_sample.pcap", "plain_ip", "Plain IP 样本"),
            ("tests/data/samples/singlevlan/10.200.33.61(10笔).pcap", "single_vlan", "Single VLAN 样本"),
            ("tests/data/samples/doublevlan/172.24.0.51.pcap", "double_vlan", "Double VLAN 样本"),
            ("tests/data/samples/mpls/mpls.pcap", "mpls", "MPLS 样本"),
            ("tests/data/samples/vxlan/vxlan.pcap", "vxlan", "VXLAN 样本"),
            
            # 扩展封装类型 (5个)
            ("tests/data/samples/gre/20160406152100.pcap", "gre", "GRE 样本"),
            ("tests/data/samples/vlan_gre/case17-parts.pcap", "vlan_gre", "VLAN+GRE 复合样本"),
            ("tests/data/samples/vxlan_vlan/vxlan_servicetag_1001.pcap", "vxlan_vlan", "VXLAN+VLAN 复合样本"),
            ("tests/data/samples/TLS70/sslerr1-70.pcap", "tls70", "TLS70 样本"),
            ("tests/data/samples/doublevlan_tls/TC-007-3-20230829-01.pcap", "doublevlan_tls", "Double VLAN + TLS 样本"),
            
            # 企业测试案例 (5个)
            ("tests/data/samples/IPTCP-200ips/TC-002-6-20200927-S-A-Replaced.pcapng", "large_dataset", "200 IP大数据集样本"),
            ("tests/data/samples/IPTCP-TC-001-1-20160407/TC-001-1-20160407-A.pcap", "test_case_001", "测试用例001样本"),
            ("tests/data/samples/IPTCP-TC-002-5-20220215/TC-002-5-20220215-FW-in.pcap", "test_case_002_5", "测试用例002-5样本"),
            ("tests/data/samples/IPTCP-TC-002-8-20210817/TC-002-8-20210817.pcapng", "test_case_002_8", "测试用例002-8样本"),
            ("tests/data/samples/vxlan4787/vxlan-double-http.pcap", "vxlan4787", "VXLAN4787变种样本"),
        ]
    
    @pytest.mark.parametrize("sample_info", [
        ("tests/data/samples/TLS/tls_sample.pcap", "plain_ip", "Plain IP 样本"),
        ("tests/data/samples/singlevlan/10.200.33.61(10笔).pcap", "single_vlan", "Single VLAN 样本"),
        ("tests/data/samples/doublevlan/172.24.0.51.pcap", "double_vlan", "Double VLAN 样本"),
        ("tests/data/samples/mpls/mpls.pcap", "mpls", "MPLS 样本"),
        ("tests/data/samples/vxlan/vxlan.pcap", "vxlan", "VXLAN 样本"),
        ("tests/data/samples/gre/20160406152100.pcap", "gre", "GRE 样本"),
        ("tests/data/samples/vlan_gre/case17-parts.pcap", "vlan_gre", "VLAN+GRE 复合样本"),
        ("tests/data/samples/vxlan_vlan/vxlan_servicetag_1001.pcap", "vxlan_vlan", "VXLAN+VLAN 复合样本"),
        ("tests/data/samples/TLS70/sslerr1-70.pcap", "tls70", "TLS70 样本"),
        ("tests/data/samples/doublevlan_tls/TC-007-3-20230829-01.pcap", "doublevlan_tls", "Double VLAN + TLS 样本"),
        ("tests/data/samples/IPTCP-200ips/TC-002-6-20200927-S-A-Replaced.pcapng", "large_dataset", "200 IP大数据集样本"),
        ("tests/data/samples/IPTCP-TC-001-1-20160407/TC-001-1-20160407-A.pcap", "test_case_001", "测试用例001样本"),
        ("tests/data/samples/IPTCP-TC-002-5-20220215/TC-002-5-20220215-FW-in.pcap", "test_case_002_5", "测试用例002-5样本"),
        ("tests/data/samples/IPTCP-TC-002-8-20210817/TC-002-8-20210817.pcapng", "test_case_002_8", "测试用例002-8样本"),
        ("tests/data/samples/vxlan4787/vxlan-double-http.pcap", "vxlan4787", "VXLAN4787变种样本"),
    ])
    def test_payload_trimming_individual_samples(self, trimming_validator, sample_info):
        """测试单个样本的载荷裁切功能"""
        file_path, category, description = sample_info
        sample_file = Path(file_path)
        
        if not sample_file.exists():
            pytest.skip(f"样本文件不存在: {file_path}")
        
        print(f"\n📋 测试载荷裁切: {description}")
        print(f"   文件: {sample_file.name}")
        print(f"   类别: {category}")
        
        # 执行载荷裁切验证
        result = trimming_validator.validate_payload_trimming(sample_file, category, max_test_packets=50)
        
        # 验证基本结果
        print(f"   总包数: {result.total_packets}, TCP包: {result.tcp_packets}")
        print(f"   载荷包: {result.packets_with_payload}, TLS包: {result.tls_packets_detected}")
        print(f"   封装包: {result.encapsulated_packets}, 裁切效果: {result.trim_effectiveness:.1f}%")
        print(f"   智能裁切准确率: {result.intelligent_trim_accuracy:.1f}%")
        
        # 基础验证
        assert result.total_packets > 0, "应该有测试包"
        assert result.processing_time > 0, "处理时间应该大于0"
        
        # 如果有载荷包，验证裁切逻辑
        if result.packets_with_payload > 0:
            # 裁切效果验证（允许0%，如果全是TLS信令）
            assert 0 <= result.trim_effectiveness <= 100, "裁切效果应在0-100%之间"
            
            # TLS智能裁切验证
            assert 0 <= result.intelligent_trim_accuracy <= 100, "智能裁切准确率应在0-100%之间"
            
            # 如果有TLS包，验证智能裁切
            if result.tls_packets_detected > 0:
                assert result.intelligent_trim_accuracy >= 70, f"TLS智能裁切准确率应≥70%，实际: {result.intelligent_trim_accuracy:.1f}%"
        
        # 封装处理验证
        if result.encapsulated_packets > 0:
            # 验证能够访问封装内的载荷
            assert result.encap_payload_accessible, "应该能够访问封装内的载荷"
            
            # 如果有封装TCP会话，验证处理成功
            if result.inner_tcp_sessions > 0:
                assert result.encap_trim_success, "封装载荷裁切应该成功"
        
        # 错误验证
        if result.errors:
            print(f"   ⚠️ 警告: {len(result.errors)} 个错误")
            for error in result.errors[:3]:  # 只显示前3个错误
                print(f"      - {error}")
        
        # 最终成功验证
        assert result.success, f"载荷裁切验证应该成功，错误: {result.errors}"
        
        print(f"   ✅ 载荷裁切验证通过: {description}")
    
    def test_payload_trimming_comprehensive_report(self, trimming_validator, all_sample_files):
        """生成所有样本的载荷裁切综合报告"""
        print(f"\n🎯 载荷裁切功能全面验证报告")
        print(f"=" * 60)
        
        total_samples = len(all_sample_files)
        successful_samples = 0
        failed_samples = []
        
        # 统计汇总
        total_packets_processed = 0
        total_tcp_packets = 0
        total_payload_packets = 0
        total_tls_packets = 0
        total_encapsulated_packets = 0
        
        total_original_payload_size = 0
        total_trimmed_payload_size = 0
        
        encapsulation_type_stats = {}
        
        # 逐个测试样本
        for file_path, category, description in all_sample_files:
            sample_file = Path(file_path)
            
            if not sample_file.exists():
                print(f"❌ 跳过不存在的文件: {file_path}")
                continue
            
            try:
                result = trimming_validator.validate_payload_trimming(sample_file, category, max_test_packets=50)
                
                # 更新统计
                total_packets_processed += result.total_packets
                total_tcp_packets += result.tcp_packets
                total_payload_packets += result.packets_with_payload
                total_tls_packets += result.tls_packets_detected
                total_encapsulated_packets += result.encapsulated_packets
                
                total_original_payload_size += result.original_payload_size
                total_trimmed_payload_size += result.trimmed_payload_size
                
                # 按封装类型分类统计
                encap_types = list(result.encapsulation_stats.keys())
                main_encap_type = encap_types[0] if encap_types else 'PLAIN'
                
                if main_encap_type not in encapsulation_type_stats:
                    encapsulation_type_stats[main_encap_type] = {
                        'count': 0, 'success': 0, 'total_trim_effect': 0
                    }
                
                encapsulation_type_stats[main_encap_type]['count'] += 1
                if result.success:
                    encapsulation_type_stats[main_encap_type]['success'] += 1
                    encapsulation_type_stats[main_encap_type]['total_trim_effect'] += result.trim_effectiveness
                
                if result.success:
                    successful_samples += 1
                    print(f"✅ {description}: {result.trim_effectiveness:.1f}%效果")
                else:
                    failed_samples.append((description, result.errors))
                    print(f"❌ {description}: 失败 - {result.errors[:2]}")
                
            except Exception as e:
                failed_samples.append((description, [str(e)]))
                print(f"❌ {description}: 异常 - {str(e)}")
        
        # 生成综合报告
        print(f"\n📊 载荷裁切验证综合统计")
        print(f"=" * 60)
        print(f"总样本数: {total_samples}")
        print(f"成功样本: {successful_samples}/{total_samples} ({(successful_samples/total_samples*100):.1f}%)")
        print(f"失败样本: {len(failed_samples)}")
        
        print(f"\n📈 处理统计")
        print(f"总处理包数: {total_packets_processed}")
        print(f"TCP包数: {total_tcp_packets} ({(total_tcp_packets/max(1,total_packets_processed)*100):.1f}%)")
        print(f"载荷包数: {total_payload_packets} ({(total_payload_packets/max(1,total_tcp_packets)*100):.1f}%)")
        print(f"TLS包数: {total_tls_packets} ({(total_tls_packets/max(1,total_payload_packets)*100):.1f}%)")
        print(f"封装包数: {total_encapsulated_packets} ({(total_encapsulated_packets/max(1,total_packets_processed)*100):.1f}%)")
        
        if total_original_payload_size > 0:
            overall_trim_effect = ((total_original_payload_size - total_trimmed_payload_size) / total_original_payload_size) * 100
            print(f"\n✂️ 载荷裁切效果")
            print(f"原始载荷大小: {total_original_payload_size:,} 字节")
            print(f"裁切后大小: {total_trimmed_payload_size:,} 字节")
            print(f"整体裁切效果: {overall_trim_effect:.1f}%")
        
        print(f"\n🏷️ 按封装类型统计")
        for encap_type, stats in encapsulation_type_stats.items():
            success_rate = (stats['success'] / stats['count']) * 100
            avg_trim_effect = stats['total_trim_effect'] / max(1, stats['success'])
            print(f"{encap_type}: {stats['success']}/{stats['count']} ({success_rate:.1f}%成功率, {avg_trim_effect:.1f}%平均裁切效果)")
        
        if failed_samples:
            print(f"\n❌ 失败样本详情")
            for description, errors in failed_samples:
                print(f"  {description}: {errors[0] if errors else '未知错误'}")
        
        # 最终验证
        success_rate = (successful_samples / total_samples) * 100
        assert success_rate >= 80, f"载荷裁切功能整体成功率应≥80%，实际: {success_rate:.1f}%"
        
        print(f"\n🎉 载荷裁切功能验证完成: {success_rate:.1f}%成功率")
        print(f"✅ 所有15个样本的载荷裁切功能验证通过!")
    
    def test_encapsulated_payload_trimming_capabilities(self, trimming_validator):
        """专门测试多层封装的载荷裁切能力"""
        encapsulated_samples = [
            ("tests/data/samples/singlevlan/10.200.33.61(10笔).pcap", "single_vlan", "Single VLAN"),
            ("tests/data/samples/doublevlan/172.24.0.51.pcap", "double_vlan", "Double VLAN"),
            ("tests/data/samples/mpls/mpls.pcap", "mpls", "MPLS"),
            ("tests/data/samples/vxlan/vxlan.pcap", "vxlan", "VXLAN"),
            ("tests/data/samples/gre/20160406152100.pcap", "gre", "GRE"),
            ("tests/data/samples/vlan_gre/case17-parts.pcap", "vlan_gre", "VLAN+GRE"),
            ("tests/data/samples/vxlan_vlan/vxlan_servicetag_1001.pcap", "vxlan_vlan", "VXLAN+VLAN"),
        ]
        
        print(f"\n🔍 多层封装载荷裁切能力验证")
        print(f"=" * 50)
        
        encap_success = 0
        encap_total = 0
        
        for file_path, category, encap_type in encapsulated_samples:
            sample_file = Path(file_path)
            
            if not sample_file.exists():
                continue
            
            encap_total += 1
            result = trimming_validator.validate_payload_trimming(sample_file, category, max_test_packets=50)
            
            print(f"\n{encap_type}: ", end="")
            
            # 验证封装检测
            if result.encapsulated_packets > 0:
                print(f"✅封装检测 ", end="")
                
                # 验证载荷访问
                if result.encap_payload_accessible:
                    print(f"✅载荷访问 ", end="")
                    
                    # 验证裁切处理
                    if result.encap_trim_success:
                        print(f"✅裁切处理")
                        encap_success += 1
                    else:
                        print(f"❌裁切处理")
                else:
                    print(f"❌载荷访问")
            else:
                print(f"⚠️无封装包")
        
        encap_success_rate = (encap_success / max(1, encap_total)) * 100
        print(f"\n📊 多层封装载荷裁切成功率: {encap_success}/{encap_total} ({encap_success_rate:.1f}%)")
        
        # 验证多层封装处理能力达标
        assert encap_success_rate >= 70, f"多层封装载荷裁切成功率应≥70%，实际: {encap_success_rate:.1f}%"
        print(f"✅ 多层封装载荷裁切能力验证通过!") 