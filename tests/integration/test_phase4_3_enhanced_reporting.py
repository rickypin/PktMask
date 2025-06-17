#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 4.3 Enhanced Reporting 集成测试

测试Enhanced Trimmer智能报告增强功能
验证智能协议处理统计、策略应用信息等报告生成
"""

import pytest
import os
import sys
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.gui.managers.report_manager import ReportManager


class TestEnhancedReporting:
    """Enhanced Trimmer智能报告功能测试"""
    
    def setup_method(self):
        """设置测试环境"""
        # 创建模拟的主窗口
        self.mock_main_window = Mock()
        self.mock_main_window.file_processing_results = {}
        self.mock_main_window.global_ip_mappings = {}
        self.mock_main_window.processed_files_count = 0
        self.mock_main_window.packets_processed_count = 0
        self.mock_main_window.current_output_dir = "/test/output"
        
        # 创建模拟的UI组件
        self.mock_main_window.summary_text = Mock()
        self.mock_main_window.summary_text.append = Mock()
        self.mock_main_window.summary_text.toPlainText = Mock(return_value="")
        self.mock_main_window.summary_text.setPlainText = Mock()
        
        # 创建模拟的复选框
        self.mock_main_window.mask_ip_cb = Mock()
        self.mock_main_window.mask_ip_cb.isChecked = Mock(return_value=False)
        self.mock_main_window.dedup_packet_cb = Mock()
        self.mock_main_window.dedup_packet_cb.isChecked = Mock(return_value=False)
        self.mock_main_window.trim_packet_cb = Mock()
        self.mock_main_window.trim_packet_cb.isChecked = Mock(return_value=True)
        
        # 创建模拟的时间标签
        self.mock_main_window.time_elapsed_label = Mock()
        self.mock_main_window.time_elapsed_label.text = Mock(return_value="00:02:30")
        
        # 创建模拟的定时器
        self.mock_main_window.timer = Mock()
        self.mock_main_window.timer.isActive = Mock(return_value=False)
        self.mock_main_window.timer.stop = Mock()
        
        # 创建ReportManager实例
        self.report_manager = ReportManager(self.mock_main_window)
    
    def test_is_enhanced_trimming_detection(self):
        """测试Enhanced Trimmer检测功能"""
        # 测试Enhanced Trimmer数据
        enhanced_data = {
            'processing_mode': 'Enhanced Intelligent Mode',
            'protocol_stats': {'tls_packets': 50, 'other_packets': 100},
            'strategies_applied': ['TLSTrimStrategy', 'DefaultStrategy'],
            'enhancement_level': '4x accuracy improvement',
            'stage_performance': {'tshark': 1.2, 'pyshark': 2.3}
        }
        
        assert self.report_manager._is_enhanced_trimming(enhanced_data) is True
        
        # 测试普通Trimmer数据
        normal_data = {
            'total_packets': 500,
            'trimmed_packets': 200
        }
        
        assert self.report_manager._is_enhanced_trimming(normal_data) is False
        
        # 测试部分Enhanced特征
        partial_enhanced_data = {
            'total_packets': 500,
            'protocol_stats': {'tls_packets': 100}
        }
        
        assert self.report_manager._is_enhanced_trimming(partial_enhanced_data) is True
    
    def test_generate_enhanced_trimming_report_line(self):
        """测试Enhanced Trimmer报告行生成"""
        enhanced_data = {
            'total_packets': 1000,
            'trimmed_packets': 300,
            'protocol_stats': {
                'tls_packets': 400,
                'other_packets': 600
            }
        }
        
        line = self.report_manager._generate_enhanced_trimming_report_line(
            "Payload Trimming", enhanced_data
        )
        
        # 验证报告行包含Enhanced Mode标识
        assert "Enhanced Mode" in line
        assert "Total: 1000" in line
        assert "Trimmed:  300" in line
        assert "Rate:  30.0%" in line
        assert "✂️" in line
    
    def test_generate_enhanced_trimming_report_for_file(self):
        """测试单文件Enhanced Trimmer报告生成"""
        # 设置文件处理结果
        filename = "test.pcap"
        self.mock_main_window.file_processing_results = {
            filename: {
                'steps': {
                    'Payload Trimming': {
                        'type': 'intelligent_trim',
                        'data': {
                            'processing_mode': 'Enhanced Intelligent Mode',
                            'total_packets': 1500,
                            'protocol_stats': {
                                'tls_packets': 800,
                                'other_packets': 700
                            },
                            'strategies_applied': ['TLSTrimStrategy', 'DefaultStrategy'],
                            'enhancement_level': '4x accuracy improvement'
                        }
                    }
                }
            }
        }
        
        report = self.report_manager._generate_enhanced_trimming_report_for_file(filename, 70)
        
        # 验证报告内容
        assert report is not None
        assert f"Enhanced Trimming Details for {filename}" in report
        assert "TLS: 800 packets (53.3%) - Handshake preserved" in report
        assert "Other: 700 packets (46.7%) - Generic strategy" in report
        assert "TLSTrimStrategy, DefaultStrategy" in report
        assert "4x accuracy improvement" in report
    
    def test_generate_enhanced_trimming_total_report(self):
        """测试Enhanced Trimmer总报告生成"""
        # 设置多个文件的处理结果
        self.mock_main_window.file_processing_results = {
            'file1.pcap': {
                'steps': {
                    'Payload Trimming': {
                        'type': 'intelligent_trim',
                        'data': {
                            'processing_mode': 'Enhanced Intelligent Mode',
                            'total_packets': 1000,
                            'protocol_stats': {
                                'tls_packets': 600,
                                'other_packets': 400
                            },
                            'strategies_applied': ['TLSTrimStrategy', 'DefaultStrategy']
                        }
                    }
                }
            },
            'file2.pcap': {
                'steps': {
                    'Payload Trimming': {
                        'type': 'intelligent_trim',
                        'data': {
                            'processing_mode': 'Enhanced Intelligent Mode',
                            'total_packets': 500,
                            'protocol_stats': {
                                'tls_packets': 300,
                                'other_packets': 200
                            },
                            'strategies_applied': ['TLSTrimStrategy', 'DefaultStrategy']
                        }
                    }
                }
            }
        }
        
        report = self.report_manager._generate_enhanced_trimming_report(70, is_partial=False)
        
        # 验证总报告内容
        assert report is not None
        assert "ENHANCED TRIMMING INTELLIGENCE REPORT" in report
        assert "Processing Mode: Intelligent Auto-Detection" in report
        assert "Enhancement Level: 4x accuracy improvement" in report
        assert "Enhanced Files: 2/2" in report
        
        # 验证协议统计
        assert "TLS packets: 900" in report   # 600 + 300
        assert "Other packets: 600" in report # 400 + 200
        assert "Total processed: 1,500 packets in 4 stages" in report
        
        # 验证策略列表
        assert "TLSTrimStrategy" in report
        assert "DefaultStrategy" in report
    
    def test_enhanced_reporting_integration_in_file_complete_report(self):
        """测试Enhanced报告在文件完成报告中的集成"""
        filename = "enhanced_test.pcap"
        
        # 设置文件处理结果
        self.mock_main_window.file_processing_results = {
            filename: {
                'steps': {
                    'Payload Trimming': {
                        'type': 'intelligent_trim',
                        'data': {
                            'processing_mode': 'Enhanced Intelligent Mode',
                            'total_packets': 800,
                            'trimmed_packets': 300,
                            'protocol_stats': {
                                'tls_packets': 500,
                                'other_packets': 300
                            },
                            'strategies_applied': ['TLSTrimStrategy', 'DefaultStrategy'],
                            'enhancement_level': '4x accuracy improvement'
                        }
                    }
                }
            }
        }
        
        # 模拟已处理文件计数
        self.mock_main_window.processed_files_count = 0
        
        # 生成文件完成报告
        self.report_manager.generate_file_complete_report(filename)
        
        # 验证Enhanced报告被调用
        calls = self.mock_main_window.summary_text.append.call_args_list
        report_content = '\n'.join([str(call[0][0]) for call in calls])
        
        # 验证包含Enhanced Mode标识
        assert "Enhanced Mode" in report_content
        assert "Enhanced Trimming Details" in report_content
    
    def test_enhanced_reporting_integration_in_processing_finished_report(self):
        """测试Enhanced报告在处理完成报告中的集成"""
        # 设置处理完成状态
        self.mock_main_window.processed_files_count = 2
        self.mock_main_window.packets_processed_count = 1500
        
        # 设置文件处理结果
        self.mock_main_window.file_processing_results = {
            'file1.pcap': {
                'steps': {
                    'Payload Trimming': {
                        'type': 'intelligent_trim',
                        'data': {
                            'processing_mode': 'Enhanced Intelligent Mode',
                            'total_packets': 800,
                            'protocol_stats': {
                                'tls_packets': 600,
                                'other_packets': 200
                            }
                        }
                    }
                }
            },
            'file2.pcap': {
                'steps': {
                    'Payload Trimming': {
                        'type': 'intelligent_trim',
                        'data': {
                            'processing_mode': 'Enhanced Intelligent Mode',
                            'total_packets': 700,
                            'protocol_stats': {
                                'tls_packets': 500,
                                'other_packets': 200
                            }
                        }
                    }
                }
            }
        }
        
        # 生成处理完成报告
        with patch.object(self.report_manager, '_save_summary_report_to_output'):
            self.report_manager.generate_processing_finished_report()
        
        # 验证Enhanced总报告被调用
        calls = self.mock_main_window.summary_text.append.call_args_list
        report_content = '\n'.join([str(call[0][0]) for call in calls])
        
        # 验证包含Enhanced Intelligence Report
        assert "ENHANCED TRIMMING INTELLIGENCE REPORT" in report_content
        assert "Intelligent Auto-Detection" in report_content
    
    def test_mixed_trimming_modes_reporting(self):
        """测试混合裁切模式的报告生成"""
        # 设置混合模式：一个Enhanced，一个普通
        self.mock_main_window.file_processing_results = {
            'enhanced.pcap': {
                'steps': {
                    'Payload Trimming': {
                        'type': 'intelligent_trim',
                        'data': {
                            'processing_mode': 'Enhanced Intelligent Mode',
                            'total_packets': 500,
                            'protocol_stats': {'tls_packets': 300, 'other_packets': 200}
                        }
                    }
                }
            },
            'normal.pcap': {
                'steps': {
                    'Payload Trimming': {
                        'type': 'trim_payloads',
                        'data': {
                            'total_packets': 300,
                            'trimmed_packets': 150
                        }
                    }
                }
            }
        }
        
        # 测试Enhanced报告只包含Enhanced文件
        report = self.report_manager._generate_enhanced_trimming_report(70)
        
        assert report is not None
        assert "Enhanced Files: 1/2" in report  # 只有1个Enhanced文件
        assert "Total processed: 500 packets" in report  # 只统计Enhanced文件的包
    
    def test_no_enhanced_trimming_files(self):
        """测试没有Enhanced Trimmer文件时的报告生成"""
        # 设置只有普通Trimmer的文件
        self.mock_main_window.file_processing_results = {
            'normal.pcap': {
                'steps': {
                    'Payload Trimming': {
                        'type': 'trim_payloads',
                        'data': {
                            'total_packets': 300,
                            'trimmed_packets': 150
                        }
                    }
                }
            }
        }
        
        # 测试Enhanced报告返回None
        report = self.report_manager._generate_enhanced_trimming_report(70)
        assert report is None
        
        # 测试单文件Enhanced报告返回None
        file_report = self.report_manager._generate_enhanced_trimming_report_for_file('normal.pcap', 70)
        assert file_report is None


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v']) 