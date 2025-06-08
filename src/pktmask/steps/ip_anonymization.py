#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP 地址处理核心模块
包含 IP 地址替换的核心逻辑
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from scapy.all import PcapReader, PcapNgReader, wrpcap, IP, IPv6, TCP, UDP

from ..core.base_step import ProcessingStep
from ..core.events import PipelineEvents
from ..core.strategy import AnonymizationStrategy
from ..utils.file_selector import select_files
from ..utils.reporting import Reporter
from ..utils.time import current_time
from ..common.constants import ProcessingConstants
from ..infrastructure.logging import get_logger


class IpAnonymizationStep(ProcessingStep):
    """
    IP 匿名化处理步骤。
    该步骤协调一个策略（用于生成映射）和一个报告器（用于保存结果）。
    """
    suffix: str = ProcessingConstants.MASK_IP_SUFFIX
    
    def __init__(self, strategy: AnonymizationStrategy, reporter: Reporter):
        super().__init__()
        self._strategy = strategy
        self._reporter = reporter
        self._rel_subdir: Optional[str] = None
        self._logger = get_logger('ip_anonymization')

    @property
    def name(self) -> str:
        return "Mask IP"

    def set_reporter_path(self, path: str, rel_path: str):
        self._rel_subdir = rel_path
        # 兼容旧的报告器接口
        if hasattr(self._reporter, 'set_report_path'):
            self._reporter.set_report_path(path, rel_path)

    def prepare_for_directory(self, subdir_path: str, all_pcap_files: List[str]):
        """在处理目录前，预扫描所有文件以建立完整的IP映射。"""
        self._logger.info(f"准备目录级IP映射: {subdir_path}, 文件数量: {len(all_pcap_files)}")
        self._strategy.build_mapping_from_directory(all_pcap_files)
        self._logger.info("目录级IP映射构建完成")

    def process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """处理单个pcap文件，使用预先生成的映射替换IP地址。"""
        self._logger.debug(f"开始处理文件: {input_path}")
        new_packets = []
        anonymized_count = 0
        total_count = 0
        file_ips = set()  # 当前文件中发现的所有IP地址
        
        ext = os.path.splitext(input_path)[1].lower()
        reader_cls = PcapNgReader if ext == ".pcapng" else PcapReader

        with reader_cls(input_path) as reader:
            for pkt in reader:
                total_count += 1
                # 提取数据包中的IP地址
                if IP in pkt:
                    file_ips.add(pkt[IP].src)
                    file_ips.add(pkt[IP].dst)
                if IPv6 in pkt:
                    file_ips.add(pkt[IPv6].src)
                    file_ips.add(pkt[IPv6].dst)
                
                new_pkt, is_anonymized = self._strategy.anonymize_packet(pkt)
                if is_anonymized:
                    anonymized_count += 1
                new_packets.append(new_pkt)
        
        # 确保输出文件的目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        wrpcap(output_path, new_packets, append=False)
        self._logger.info(f"处理完成: {input_path} -> {output_path}, 匿名化包数: {anonymized_count}/{total_count}")
        
        # 计算当前文件中被映射的IP数量
        ip_map = self._strategy.get_ip_map()
        file_mapped_ips = set(ip for ip in file_ips if ip in ip_map)
        
        # 返回单文件处理的统计信息
        return {
            'subdir': os.path.basename(os.path.dirname(input_path)),
            'input_filename': os.path.basename(input_path),
            'output_filename': os.path.basename(output_path),
            'total_packets': total_count,
            'anonymized_packets': anonymized_count,
            'original_ips': len(file_ips),
            'anonymized_ips': len(file_mapped_ips),
            'file_ip_mappings': {ip: ip_map[ip] for ip in file_mapped_ips}
        }

    def finalize_directory_processing(self) -> Optional[Dict]:
        """在目录处理完成后，生成并返回最终的报告。"""
        if not self._rel_subdir:
            return None

        ip_map = self._strategy.get_ip_map()
        summary_stats = {
            "total_unique_ips": len(ip_map),
            "total_mapped_ips": len(ip_map)
        }
        report = self._reporter.finalize_report_for_directory(self._rel_subdir, summary_stats, ip_map)
        
        self._strategy.reset()
        
        return {'report': report}


def create_ip_anonymization_step(strategy: AnonymizationStrategy, reporter: Reporter) -> IpAnonymizationStep:
    return IpAnonymizationStep(strategy=strategy, reporter=reporter) 