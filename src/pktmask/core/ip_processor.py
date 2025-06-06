#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP 地址处理核心模块
包含 IP 地址替换的核心逻辑
"""

import os
from datetime import datetime
from typing import Dict, Tuple, List

from scapy.all import PcapReader, PcapNgReader, wrpcap, IP, IPv6, TCP, UDP

from pktmask.core.pipeline import ProcessingStep
from pktmask.core.strategy import AnonymizationStrategy
from pktmask.utils.file_selector import select_files
from pktmask.utils.reporting import generate_report

def current_time() -> str:
    """获取当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class IpAnonymizationStep(ProcessingStep):
    """
    IP匿名化处理步骤。
    该步骤使用一个可配置的策略来替换pcap文件中的IP地址。
    """
    def __init__(self, strategy: AnonymizationStrategy):
        if not isinstance(strategy, AnonymizationStrategy):
            raise TypeError("strategy must be an instance of AnonymizationStrategy")
        self._strategy = strategy

    @property
    def suffix(self) -> str:
        return "-Replaced"

    def _process_packet(self, packet, mapping: Dict[str, str]):
        """处理单个数据包"""
        if packet.haslayer(IP):
            ip_layer = packet.getlayer(IP)
            orig_src = ip_layer.src
            ip_layer.src = mapping.get(orig_src, orig_src)
            orig_dst = ip_layer.dst
            ip_layer.dst = mapping.get(orig_dst, orig_dst)
            if hasattr(ip_layer, "chksum"): del ip_layer.chksum
            if packet.haslayer(TCP) and hasattr(packet.getlayer(TCP), "chksum"): del packet.getlayer(TCP).chksum
            elif packet.haslayer(UDP) and hasattr(packet.getlayer(UDP), "chksum"): del packet.getlayer(UDP).chksum
        
        if packet.haslayer(IPv6):
            ipv6_layer = packet.getlayer(IPv6)
            orig_src = ipv6_layer.src
            ipv6_layer.src = mapping.get(orig_src, orig_src)
            orig_dst = ipv6_layer.dst
            ipv6_layer.dst = mapping.get(orig_dst, orig_dst)
            if hasattr(ipv6_layer, "chksum"): del ipv6_layer.chksum
            if packet.haslayer(TCP) and hasattr(packet.getlayer(TCP), "chksum"): del packet.getlayer(TCP).chksum
            elif packet.haslayer(UDP) and hasattr(packet.getlayer(UDP), "chksum"): del packet.getlayer(UDP).chksum

        return packet

    def _process_file(self, file_path: str, mapping: Dict[str, str], error_log: List[str]) -> Tuple[bool, Dict[str, str]]:
        """处理单个文件，返回成功状态和该文件的IP映射"""
        try:
            file_used_ips = set()
            
            ext = os.path.splitext(file_path)[1].lower()
            reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
            
            packets = []
            with reader_class(file_path) as reader:
                for packet in reader:
                    if packet.haslayer(IP):
                        file_used_ips.add(packet.getlayer(IP).src)
                        file_used_ips.add(packet.getlayer(IP).dst)
                    if packet.haslayer(IPv6):
                        file_used_ips.add(packet.getlayer(IPv6).src)
                        file_used_ips.add(packet.getlayer(IPv6).dst)
                    packets.append(self._process_packet(packet, mapping))

            base, ext = os.path.splitext(file_path)
            new_file_path = f"{base}{self.suffix}{ext}"
            wrpcap(new_file_path, packets)

            file_mapping = {ip: mapping[ip] for ip in file_used_ips if ip in mapping}
            return True, file_mapping
        except Exception as e:
            error_log.append(f"{current_time()} - Error processing file {file_path}: {str(e)}")
            return False, {}

    def process_directory(self, subdir_path: str, base_path: str = None, progress_callback=None):
        def log(level, message):
            if progress_callback:
                progress_callback('log', {'level': level, 'message': message})

        if base_path is None:
            base_path = os.path.dirname(subdir_path)
        
        rel_subdir = os.path.relpath(subdir_path, base_path)
        start_time = datetime.now()
        
        files_to_process, reason = select_files(subdir_path, self.suffix)

        if not files_to_process:
            log('info', f"[IP Anonymize] In '{rel_subdir}': {reason}")
            return
            
        log('info', f"[IP Anonymize] In '{rel_subdir}': Found {len(files_to_process)} files to process. Reason: {reason}")
        
        error_log = []
        
        # 1. 使用策略创建IP映射
        log('info', f"[IP Anonymize] Pre-calculating IP mapping using {self._strategy.__class__.__name__}...")
        try:
            global_mapping = self._strategy.create_mapping(files_to_process, subdir_path, error_log)
        except Exception as e:
            log('critical', f"[IP Anonymize] Fatal error during IP mapping creation: {e}")
            error_log.append(f"{current_time()} - Fatal error during IP mapping creation: {e}")
            return
        log('info', f"[IP Anonymize] Pre-calculation completed. Total unique IPs found: {len(global_mapping)}")

        # 2. 处理每个文件
        processed_file_count = 0
        actual_used_ips = set()
        file_mappings = {}
        file_ip_counts = {}

        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            rel_file_path = os.path.relpath(file_path, base_path)
            log('info', f"[IP Anonymize] Processing file: {rel_file_path}")
            
            success, file_mapping = self._process_file(file_path, global_mapping, error_log)
            if not success:
                log('error', f"[IP Anonymize] Error processing file, skipped.")
                continue
            
            processed_file_count += 1
            file_ip_counts[f] = len(file_mapping)
            actual_used_ips.update(file_mapping.keys())
            file_mappings[f] = file_mapping
            
            new_filename = f"{os.path.splitext(f)[0]}{self.suffix}{os.path.splitext(f)[1]}"
            rel_new_path = os.path.relpath(os.path.join(subdir_path, new_filename), base_path)
            log('info', f"[IP Anonymize] File processed successfully: {rel_new_path} (Unique IPs: {len(file_mapping)})")
            if progress_callback:
                progress_callback('file_result', {
                    'type': 'ip_replacement',
                    'filename': f,
                    'new_filename': new_filename,
                    'unique_ips': len(file_mapping)
                })

        # 3. 生成报告
        final_mapping = {ip: global_mapping[ip] for ip in actual_used_ips if ip in global_mapping}
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        stats = {
            "processed_file_count": processed_file_count,
            "total_unique_ips": len(final_mapping),
            "total_time_seconds": round(elapsed_time, 2),
            "file_ip_counts": file_ip_counts
        }
        
        report_data = {
            "stats": stats,
            "file_mappings": file_mappings,
            "total_mapping": final_mapping,
            "error_log": error_log
        }
        
        # 保存报告文件并发送回调
        generate_report(
            subdir_path=subdir_path,
            rel_subdir=rel_subdir,
            processed_file_count=stats["processed_file_count"],
            final_mapping=final_mapping,
            elapsed_time=stats["total_time_seconds"],
            file_ip_counts=stats["file_ip_counts"],
            file_mappings=file_mappings,
            error_log=error_log
        ) # Keep generating file for external use
        
        if progress_callback:
            report_data['rel_subdir'] = rel_subdir
            progress_callback('step_summary', {'type': 'ip_replacement', 'report': report_data})

        log('info', f"[IP Anonymize] In '{rel_subdir}': Processing completed. Successfully processed {processed_file_count} files.")
        for error in error_log:
            log('error', f"[IP Anonymize] ERROR: {error}") 