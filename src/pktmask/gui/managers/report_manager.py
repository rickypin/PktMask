#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
报告管理器 - 负责报告生成和显示
"""

import os
from typing import TYPE_CHECKING, Dict, Any, Optional, List
from datetime import datetime

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.infrastructure.logging import get_logger

class ReportManager:
    """报告管理器 - 负责报告生成和显示"""
    
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)
    
    def update_log(self, message: str):
        """更新日志显示"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            
            # 添加到日志文本区域
            self.main_window.log_text.append(formatted_message)
            
            # 自动滚动到底部
            cursor = self.main_window.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.main_window.log_text.setTextCursor(cursor)
            
            self._logger.debug(f"UI日志更新: {message}")
            
        except Exception as e:
            self._logger.error(f"更新日志显示时发生错误: {e}")
    
    def generate_partial_summary_on_stop(self):
        """生成用户停止时的部分汇总统计"""
        separator_length = 70
        
        # 计算当前的时间
        if self.main_window.timer:
            self.main_window.timer.stop()
        
        # 停止统计管理器的计时
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            self.main_window.pipeline_manager.statistics.stop_timing()
            
        self.main_window.update_time_elapsed()
        
        partial_time = self.main_window.time_elapsed_label.text()
        partial_files = self.main_window.files_processed_count
        partial_packets = self.main_window.packets_processed_count
        
        # 生成停止汇总报告
        stop_report = f"\n{'='*separator_length}\n⏹️ PROCESSING STOPPED BY USER\n{'='*separator_length}\n"
        stop_report += f"📊 Partial Statistics (Completed Portion):\n"
        stop_report += f"   • Files Processed: {partial_files}\n"
        stop_report += f"   • Packets Processed: {partial_packets:,}\n"
        stop_report += f"   • Processing Time: {partial_time}\n"
        
        # 计算部分处理速度
        try:
            time_parts = partial_time.split(':')
            if len(time_parts) >= 2:
                minutes = int(time_parts[-2])
                seconds_with_ms = time_parts[-1].split('.')
                seconds = int(seconds_with_ms[0])
                total_seconds = minutes * 60 + seconds
                if total_seconds > 0 and partial_packets > 0:
                    speed = partial_packets / total_seconds
                    stop_report += f"   • Average Speed: {speed:,.0f} packets/second\n\n"
                else:
                    stop_report += f"   • Average Speed: N/A\n\n"
            else:
                stop_report += f"   • Average Speed: N/A\n\n"
        except:
            stop_report += f"   • Average Speed: N/A\n\n"
        
        # 显示已启用的处理步骤
        enabled_steps = []
        if self.main_window.mask_ip_cb.isChecked():
            enabled_steps.append("IP Masking")
        if self.main_window.dedup_packet_cb.isChecked():
            enabled_steps.append("Deduplication")
        if self.main_window.trim_packet_cb.isChecked():
            enabled_steps.append("Payload Trimming")
        
        stop_report += f"🔧 Configured Processing Steps: {', '.join(enabled_steps)}\n"
        stop_report += f"📁 Working Directory: {os.path.basename(self.main_window.base_dir) if self.main_window.base_dir else 'N/A'}\n"
        stop_report += f"⚠️ Processing was interrupted. All intermediate files have been cleaned up.\n"
        stop_report += f"❌ No completed output files were generated due to interruption.\n"
        stop_report += f"{'='*separator_length}\n"
        
        self.main_window.summary_text.append(stop_report)
        
        # 检查并显示文件处理状态
        if self.main_window.file_processing_results:
            files_status_report = self._generate_files_status_report(separator_length)
            self.main_window.summary_text.append(files_status_report)
        
        # 显示全局IP映射汇总（仅当有完全完成的文件时）
        if self.main_window.processed_files_count >= 1 and self.main_window.global_ip_mappings:
            global_partial_report = self._generate_global_ip_mappings_report(separator_length, True)
            if global_partial_report:
                self.main_window.summary_text.append(global_partial_report)
        
        # 修正的重启提示
        restart_hint = f"\n💡 RESTART INFORMATION:\n"
        restart_hint += f"   • Clicking 'Start' will restart processing from the beginning\n"
        restart_hint += f"   • All files will be reprocessed (no partial resume capability)\n"
        restart_hint += f"   • Any existing output files will be skipped to avoid overwriting\n"
        restart_hint += f"   • Processing will be performed completely for each file\n"
        self.main_window.summary_text.append(restart_hint)
    
    def _generate_files_status_report(self, separator_length: int) -> str:
        """生成文件处理状态报告"""
        files_status_report = f"\n{'='*separator_length}\n📋 FILES PROCESSING STATUS (At Stop)\n{'='*separator_length}\n"
        
        completed_files = 0
        partial_files = 0
        
        for filename, file_result in self.main_window.file_processing_results.items():
            steps_data = file_result['steps']
            if not steps_data:
                continue
            
            # 检查文件是否完整处理完成（所有配置的步骤都完成）
            expected_steps = set()
            if self.main_window.mask_ip_cb.isChecked():
                expected_steps.add("IP Masking")
            if self.main_window.dedup_packet_cb.isChecked():
                expected_steps.add("Deduplication")
            if self.main_window.trim_packet_cb.isChecked():
                expected_steps.add("Payload Trimming")
            
            completed_steps = set(steps_data.keys())
            is_fully_completed = expected_steps.issubset(completed_steps)
            
            if is_fully_completed:
                completed_files += 1
                files_status_report += self._generate_completed_file_report(filename, steps_data)
            else:
                partial_files += 1
                files_status_report += self._generate_partial_file_report(filename, completed_steps, expected_steps)
        
        if completed_files == 0 and partial_files > 0:
            files_status_report += f"\n⚠️ All files were only partially processed.\n"
            files_status_report += f"   No final output files were created.\n"
        elif completed_files > 0:
            files_status_report += f"\n📈 Summary: {completed_files} completed, {partial_files} partial\n"
        
        files_status_report += f"{'='*separator_length}\n"
        return files_status_report
    
    def _generate_completed_file_report(self, filename: str, steps_data: Dict) -> str:
        """生成已完成文件的报告"""
        report = f"\n✅ {filename}\n"
        report += f"   Status: FULLY COMPLETED\n"
        
        # 获取最终输出文件名
        step_order = ['Deduplication', 'IP Masking', 'Payload Trimming']
        final_output = None
        for step_name in reversed(step_order):
            if step_name in steps_data:
                output_file = steps_data[step_name]['data'].get('output_filename')
                if output_file and not output_file.startswith('tmp'):
                    final_output = output_file
                    break
        
        if final_output:
            report += f"   Output File: {final_output}\n"
        
        # 显示详细结果
        original_packets = 0
        file_ip_mappings = {}
        
        for step_name in step_order:
            if step_name in steps_data:
                data = steps_data[step_name]['data']
                if data.get('total_packets'):
                    original_packets = data.get('total_packets', 0)
                
                if step_name == 'IP Masking':
                    original_ips = data.get('original_ips', 0)
                    masked_ips = data.get('anonymized_ips', 0)
                    rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
                    report += f"   🛡️  IP Masking: {original_ips} → {masked_ips} IPs ({rate:.1f}%)\n"
                    file_ip_mappings = data.get('file_ip_mappings', {})
                    
                elif step_name == 'Deduplication':
                    unique = data.get('unique_packets', 0)
                    removed = data.get('removed_count', 0)
                    rate = (removed / original_packets * 100) if original_packets > 0 else 0
                    report += f"   🔄 Deduplication: {removed} removed ({rate:.1f}%)\n"
                
                elif step_name == 'Payload Trimming':
                    trimmed = data.get('trimmed_packets', 0)
                    rate = (trimmed / original_packets * 100) if original_packets > 0 else 0
                    report += f"   ✂️  Payload Trimming: {trimmed} trimmed ({rate:.1f}%)\n"
        
        # 显示IP映射（如果有）
        if file_ip_mappings:
            report += f"   🔗 IP Mappings ({len(file_ip_mappings)}):\n"
            for i, (orig_ip, new_ip) in enumerate(sorted(file_ip_mappings.items()), 1):
                if i <= 5:  # 只显示前5个
                    report += f"      {i}. {orig_ip} → {new_ip}\n"
                elif i == 6:
                    report += f"      ... and {len(file_ip_mappings) - 5} more\n"
                    break
        
        return report
    
    def _generate_partial_file_report(self, filename: str, completed_steps: set, expected_steps: set) -> str:
        """生成部分完成文件的报告"""
        report = f"\n🔄 {filename}\n"
        report += f"   Status: PARTIALLY PROCESSED (Interrupted)\n"
        report += f"   Completed Steps: {', '.join(completed_steps)}\n"
        report += f"   Missing Steps: {', '.join(expected_steps - completed_steps)}\n"
        report += f"   ❌ No final output file generated\n"
        report += f"   🗑️ Temporary files cleaned up automatically\n"
        return report
    
    def _generate_global_ip_mappings_report(self, separator_length: int, is_partial: bool = False) -> Optional[str]:
        """生成全局IP映射报告"""
        # 首先检查是否有IP匿名化处理
        if not self.main_window.mask_ip_cb.isChecked():
            return None
            
        # 检查是否有全局IP映射数据
        if not self.main_window.global_ip_mappings:
            return None
        
        # 检查是否有完全完成的文件
        has_completed_files = False
        for filename, file_result in self.main_window.file_processing_results.items():
            expected_steps = set()
            if self.main_window.mask_ip_cb.isChecked():
                expected_steps.add("IP Masking")
            if self.main_window.dedup_packet_cb.isChecked():
                expected_steps.add("Deduplication")
            if self.main_window.trim_packet_cb.isChecked():
                expected_steps.add("Payload Trimming")
            
            completed_steps = set(file_result['steps'].keys())
            if expected_steps.issubset(completed_steps):
                has_completed_files = True
                break
        
        if not has_completed_files:
            return None
        
        if is_partial:
            title = "🌐 IP MAPPINGS FROM COMPLETED FILES"
            subtitle = "📝 IP Mapping Table - From Successfully Completed Files Only:"
        else:
            title = "🌐 GLOBAL IP MAPPINGS (All Files Combined)"
            subtitle = "📝 Complete IP Mapping Table - Unique Entries Across All Files:"
        
        global_partial_report = f"\n{'='*separator_length}\n{title}\n{'='*separator_length}\n"
        global_partial_report += f"{subtitle}\n"
        global_partial_report += f"   • Total Unique IPs Mapped: {len(self.main_window.global_ip_mappings)}\n\n"
        
        sorted_global_mappings = sorted(self.main_window.global_ip_mappings.items())
        for i, (orig_ip, new_ip) in enumerate(sorted_global_mappings, 1):
            global_partial_report += f"   {i:2d}. {orig_ip:<16} → {new_ip}\n"
        
        if is_partial:
            global_partial_report += f"\n✅ All unique IP addresses across files have been\n"
            global_partial_report += f"   successfully anonymized with consistent mappings.\n"
        else:
            global_partial_report += f"\n✅ All unique IP addresses across {self.main_window.processed_files_count} files have been\n"
            global_partial_report += f"   successfully anonymized with consistent mappings.\n"
        
        global_partial_report += f"{'='*separator_length}\n"
        return global_partial_report
    
    def generate_file_complete_report(self, original_filename: str):
        """为单个文件生成完整的处理报告"""
        if original_filename not in self.main_window.file_processing_results:
            return
            
        file_results = self.main_window.file_processing_results[original_filename]
        steps_data = file_results['steps']
        
        if not steps_data:
            return
        
        # 增加已处理文件计数
        self.main_window.processed_files_count += 1
        
        separator_length = 70
        filename_display = original_filename
        
        # 文件处理标题
        header = f"\n{'='*separator_length}\n📄 FILE PROCESSING RESULTS: {filename_display}\n{'='*separator_length}"
        self.main_window.summary_text.append(header)
        
        # 获取原始包数（从第一个处理步骤获取）
        original_packets = 0
        output_filename = None
        if 'IP Masking' in steps_data:
            original_packets = steps_data['IP Masking']['data'].get('total_packets', 0)
            output_filename = steps_data['IP Masking']['data'].get('output_filename')
        elif 'Deduplication' in steps_data:
            original_packets = steps_data['Deduplication']['data'].get('total_packets', 0)
            output_filename = steps_data['Deduplication']['data'].get('output_filename')
        elif 'Payload Trimming' in steps_data:
            original_packets = steps_data['Payload Trimming']['data'].get('total_packets', 0)
            output_filename = steps_data['Payload Trimming']['data'].get('output_filename')
        
        # 从最后一个处理步骤获取最终输出文件名
        step_order = ['Deduplication', 'IP Masking', 'Payload Trimming']
        for step_name in reversed(step_order):
            if step_name in steps_data:
                final_output = steps_data[step_name]['data'].get('output_filename')
                if final_output:
                    output_filename = final_output
                    break
        
        # 显示原始包数和输出文件名
        self.main_window.summary_text.append(f"📦 Original Packets: {original_packets:,}")
        if output_filename:
            self.main_window.summary_text.append(f"📄 Output File: {output_filename}")
        self.main_window.summary_text.append("")
        
        # 按处理顺序显示各步骤结果
        file_ip_mappings = {}  # 存储当前文件的IP映射
        
        for step_name in step_order:
            if step_name in steps_data:
                step_result = steps_data[step_name]
                step_type = step_result['type']
                data = step_result['data']
                
                if step_type in ['mask_ip', 'mask_ips']:  # 修复：支持两种命名格式
                    # 使用新的IP统计数据
                    original_ips = data.get('original_ips', 0)
                    masked_ips = data.get('anonymized_ips', 0)
                    rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
                    line = f"  🛡️  {step_name:<18} | Original IPs: {original_ips:>3} | Masked IPs: {masked_ips:>3} | Rate: {rate:5.1f}%"
                    
                    # 获取文件级别的IP映射
                    file_ip_mappings = data.get('file_ip_mappings', {})
                    
                elif step_type == 'remove_dupes':
                    unique = data.get('unique_packets', 0)
                    removed = data.get('removed_count', 0)
                    total_before = data.get('total_packets', 0)
                    rate = (removed / total_before * 100) if total_before > 0 else 0
                    line = f"  🔄 {step_name:<18} | Unique Pkts: {unique:>4} | Removed Pkts: {removed:>4} | Rate: {rate:5.1f}%"
                
                elif step_type in ['intelligent_trim', 'trim_payloads']:  # 修复：支持两种命名格式
                    total = data.get('total_packets', 0)
                    trimmed = data.get('trimmed_packets', 0)
                    full_pkts = total - trimmed
                    rate = (trimmed / total * 100) if total > 0 else 0
                    line = f"  ✂️  {step_name:<18} | Full Pkts: {full_pkts:>5} | Trimmed Pkts: {trimmed:>4} | Rate: {rate:5.1f}%"
                else:
                    continue
                    
                self.main_window.summary_text.append(line)
        
        # 如果有IP映射，显示文件级别的IP映射
        if file_ip_mappings:
            self.main_window.summary_text.append("")
            self.main_window.summary_text.append("🔗 IP Mappings for this file:")
            sorted_mappings = sorted(file_ip_mappings.items())
            for i, (orig_ip, new_ip) in enumerate(sorted_mappings, 1):
                self.main_window.summary_text.append(f"   {i:2d}. {orig_ip:<16} → {new_ip}")
        
        self.main_window.summary_text.append(f"{'='*separator_length}")
    
    def generate_processing_finished_report(self):
        """生成处理完成时的报告"""
        separator_length = 70  # 保持一致的分隔线长度
        
        # 停止计时器
        if self.main_window.timer and self.main_window.timer.isActive():
            self.main_window.timer.stop()
        
        # 停止统计管理器的计时
        if hasattr(self.main_window, 'pipeline_manager') and hasattr(self.main_window.pipeline_manager, 'statistics'):
            self.main_window.pipeline_manager.statistics.stop_timing()
            
        self.main_window.update_time_elapsed()
        
        enabled_steps = []
        if self.main_window.dedup_packet_cb.isChecked():
            enabled_steps.append("Deduplication")
        if self.main_window.mask_ip_cb.isChecked():
            enabled_steps.append("IP Anonymization")
        if self.main_window.trim_packet_cb.isChecked():
            enabled_steps.append("Payload Trimming")
            
        completion_report = f"\n{'='*separator_length}\n🎉 PROCESSING COMPLETED!\n{'='*separator_length}\n"
        completion_report += f"🎯 All {self.main_window.processed_files_count} files have been successfully processed.\n"
        completion_report += f"📈 Files Processed: {self.main_window.processed_files_count}\n"
        completion_report += f"📊 Total Packets Processed: {self.main_window.packets_processed_count}\n"
        completion_report += f"⏱️ Time Elapsed: {self.main_window.time_elapsed_label.text()}\n"
        completion_report += f"🔧 Applied Processing Steps: {', '.join(enabled_steps)}\n"
        
        # 安全处理输出目录显示
        if self.main_window.current_output_dir:
            completion_report += f"📁 Output Location: {os.path.basename(self.main_window.current_output_dir)}\n"
        else:
            completion_report += f"📁 Output Location: Not specified\n"
            
        completion_report += f"📝 All processed files saved to output directory.\n"
        completion_report += f"{'='*separator_length}\n"
        
        self.main_window.summary_text.append(completion_report)
        
        # 修复：添加全局IP映射汇总报告（多文件处理时显示去重的全局IP映射）
        global_ip_report = self._generate_global_ip_mappings_report(separator_length, is_partial=False)
        if global_ip_report:
            self.main_window.summary_text.append(global_ip_report)
        
        # 修复：处理完成后自动保存Summary Report到输出目录
        self._save_summary_report_to_output()

    def set_final_summary_report(self, report: dict):
        """设置最终的汇总报告，包括详细的IP映射信息。"""
        subdir = report.get('path', 'N/A')
        stats = report.get('stats', {})
        total_mapping = report.get('data', {}).get('total_mapping', {})
        
        separator_length = 70  # 保持一致的分隔线长度
        
        # 添加IP映射的汇总信息，包括详细映射表
        text = f"\n{'='*separator_length}\n📋 DIRECTORY PROCESSING SUMMARY\n{'='*separator_length}\n"
        text += f"📂 Directory: {subdir}\n\n"
        text += f"🔒 IP Anonymization Summary:\n"
        text += f"   • Total Unique IPs Discovered: {stats.get('total_unique_ips', 'N/A')}\n"
        text += f"   • Total IPs Anonymized: {stats.get('total_mapped_ips', 'N/A')}\n\n"
        
        if total_mapping:
            text += f"📝 Complete IP Mapping Table (All Files):\n"
            # 按原始IP排序显示映射
            sorted_mappings = sorted(total_mapping.items())
            for i, (orig_ip, new_ip) in enumerate(sorted_mappings, 1):
                text += f"   {i:2d}. {orig_ip:<16} → {new_ip}\n"
            text += "\n"
        
        text += f"✅ All IP addresses have been successfully anonymized while\n"
        text += f"   preserving network structure and subnet relationships.\n"
        text += f"{'='*separator_length}\n"
        
        self.main_window.summary_text.append(text)

    def update_summary_report(self, data: Dict[str, Any]):
        """更新摘要报告显示"""
        try:
            # 根据数据类型生成不同的报告
            if 'filename' in data:
                # 单文件处理报告
                self._update_file_summary(data)
            elif 'step_results' in data:
                # 整体处理摘要
                self._update_overall_summary(data)
            else:
                step_type = data.get('type')
                if step_type and step_type.endswith('_final'):
                    report_data = data.get('report')
                    if report_data and 'mask_ip' in step_type:
                        self.set_final_summary_report(report_data)
                else:
                    self._logger.warning(f"未知的摘要报告数据格式: {data.keys()}")
                
        except Exception as e:
            self._logger.error(f"更新摘要报告时发生错误: {e}")
    
    def _update_file_summary(self, data: Dict[str, Any]):
        """更新单文件处理摘要"""
        filename = data.get('filename', 'Unknown file')
        
        # 获取当前摘要文本
        current_text = self.main_window.summary_text.toPlainText()
        
        # 生成文件摘要
        file_summary = self._generate_file_summary_text(data)
        
        # 追加到现有文本
        if current_text.strip():
            updated_text = current_text + "\n\n" + file_summary
        else:
            updated_text = file_summary
        
        self.main_window.summary_text.setPlainText(updated_text)
        
        # 滚动到底部
        cursor = self.main_window.summary_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.main_window.summary_text.setTextCursor(cursor)
    
    def _update_overall_summary(self, data: Dict[str, Any]):
        """更新整体处理摘要"""
        summary_text = self._generate_overall_summary_text(data)
        self.main_window.summary_text.setPlainText(summary_text)
    
    def _generate_file_summary_text(self, data: Dict[str, Any]) -> str:
        """生成单文件摘要文本"""
        filename = data.get('filename', 'Unknown file')
        summary_parts = [f"📄 {filename}"]
        
        # 处理结果统计
        results = data.get('results', {})
        for step_name, result in results.items():
            if isinstance(result, dict):
                if 'summary' in result:
                    summary_parts.append(f"  • {step_name}: {result['summary']}")
                elif 'packets_processed' in result:
                    summary_parts.append(f"  • {step_name}: {result['packets_processed']} packets")
                elif 'ips_anonymized' in result:
                    summary_parts.append(f"  • {step_name}: {result['ips_anonymized']} IPs anonymized")
        
        return '\n'.join(summary_parts)
    
    def _generate_overall_summary_text(self, data: Dict[str, Any]) -> str:
        """生成整体摘要文本"""
        summary_parts = ["📊 Processing Summary", "=" * 50]
        
        # 基本统计
        files_processed = data.get('files_processed', 0)
        total_files = data.get('total_files', 0)
        status = data.get('status', 'unknown')
        
        summary_parts.append(f"Status: {status.title().replace('_', ' ')}")
        summary_parts.append(f"Files Processed: {files_processed}/{total_files}")
        
        if files_processed > 0 and total_files > 0:
            percentage = (files_processed / total_files) * 100
            summary_parts.append(f"Completion: {percentage:.1f}%")
        
        summary_parts.append("")
        
        # 步骤统计
        step_results = data.get('step_results', {})
        if step_results:
            summary_parts.append("📈 Step Statistics:")
            
            # 聚合各步骤的统计
            step_stats = self._aggregate_step_statistics(step_results)
            
            for step_name, stats in step_stats.items():
                summary_parts.append(f"\n🔧 {step_name}:")
                for key, value in stats.items():
                    summary_parts.append(f"  • {key}: {value}")
        
        # 输出目录信息
        output_dir = data.get('output_directory')
        if output_dir:
            summary_parts.append(f"\n📁 Output Directory:")
            summary_parts.append(f"  {output_dir}")
        
        # 时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_parts.append(f"\n⏰ Generated: {timestamp}")
        
        return '\n'.join(summary_parts)
    
    def _generate_final_summary_text(self, data: Dict[str, Any]) -> str:
        """生成最终摘要文本"""
        summary_parts = ["🎯 Final Processing Report", "=" * 60]
        
        # 处理状态
        status = data.get('status', 'unknown')
        files_processed = data.get('files_processed', 0)
        total_files = data.get('total_files', 0)
        
        if status == 'completed':
            summary_parts.append("✅ Status: Successfully Completed")
        elif status == 'stopped_by_user':
            summary_parts.append("⏹️ Status: Stopped by User")
        else:
            summary_parts.append(f"❓ Status: {status.title()}")
        
        summary_parts.append(f"📊 Files Processed: {files_processed} of {total_files}")
        
        if files_processed > 0 and total_files > 0:
            percentage = (files_processed / total_files) * 100
            summary_parts.append(f"📈 Completion Rate: {percentage:.1f}%")
        
        summary_parts.append("")
        
        # 详细统计
        step_results = data.get('step_results', {})
        if step_results:
            summary_parts.append("📋 Detailed Statistics:")
            summary_parts.append("-" * 40)
            
            # 聚合统计
            aggregated_stats = self._aggregate_step_statistics(step_results)
            
            for step_name, stats in aggregated_stats.items():
                summary_parts.append(f"\n🔧 {step_name}:")
                for stat_name, stat_value in stats.items():
                    summary_parts.append(f"  • {stat_name}: {stat_value}")
        
        # 文件详情
        if step_results:
            summary_parts.append("\n📄 File Details:")
            summary_parts.append("-" * 30)
            
            for filename, file_results in step_results.items():
                summary_parts.append(f"\n📁 {filename}:")
                for step_name, result in file_results.items():
                    if isinstance(result, dict):
                        if 'summary' in result:
                            summary_parts.append(f"  • {step_name}: {result['summary']}")
                        else:
                            summary_parts.append(f"  • {step_name}: Processed")
        
        # 输出信息
        output_dir = data.get('output_directory')
        if output_dir:
            summary_parts.append(f"\n📂 Output Location:")
            summary_parts.append(f"  {output_dir}")
        
        # 生成时间
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_parts.append(f"\n🕒 Report Generated: {timestamp}")
        
        # 工具信息
        summary_parts.append("\n" + "=" * 60)
        summary_parts.append("🛠️ Generated by PktMask - Network Packet Processing Tool")
        
        return '\n'.join(summary_parts)
    
    def _aggregate_step_statistics(self, step_results: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """聚合步骤统计信息"""
        aggregated = {}
        
        for filename, file_results in step_results.items():
            for step_name, result in file_results.items():
                if step_name not in aggregated:
                    aggregated[step_name] = {}
                
                if isinstance(result, dict):
                    for key, value in result.items():
                        if isinstance(value, (int, float)):
                            # 数值类型进行累加
                            if key in aggregated[step_name]:
                                aggregated[step_name][key] += value
                            else:
                                aggregated[step_name][key] = value
                        elif key == 'summary' and isinstance(value, str):
                            # 摘要信息收集到列表
                            summary_key = 'summaries'
                            if summary_key not in aggregated[step_name]:
                                aggregated[step_name][summary_key] = []
                            aggregated[step_name][summary_key].append(f"{filename}: {value}")
        
        # 后处理：计算平均值、格式化显示等
        for step_name, stats in aggregated.items():
            if 'summaries' in stats:
                # 将摘要列表转换为计数
                summaries = stats.pop('summaries')
                stats['files_processed'] = len(summaries)
        
        return aggregated
    
    def clear_displays(self):
        """清空显示区域"""
        try:
            self.main_window.log_text.clear()
            self.main_window.summary_text.clear()
            self._logger.debug("清空日志和摘要显示")
            
        except Exception as e:
            self._logger.error(f"清空显示区域时发生错误: {e}")
    
    def export_summary_report(self, filepath: str) -> bool:
        """导出摘要报告到文件"""
        try:
            content = self.main_window.summary_text.toPlainText()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self._logger.info(f"摘要报告已导出到: {filepath}")
            return True
            
        except Exception as e:
            self._logger.error(f"导出摘要报告失败: {e}")
            return False
    
    def _save_summary_report_to_output(self):
        """私有方法：保存摘要报告到输出目录"""
        try:
            # 委托给FileManager或使用MainWindow的现有方法
            if hasattr(self.main_window, 'save_summary_report_to_output_dir'):
                self.main_window.save_summary_report_to_output_dir()
            elif hasattr(self.main_window, 'file_manager'):
                self.main_window.file_manager.save_summary_report_to_output_dir()
            else:
                self._logger.warning("无法找到保存Summary Report的方法")
        except Exception as e:
            self._logger.error(f"保存Summary Report到输出目录失败: {e}")

    def collect_step_result(self, data: dict):
        """收集每个步骤的处理结果，但不立即显示"""
        if not self.main_window.current_processing_file:
            return
            
        step_type = data.get('type')
        if not step_type or step_type.endswith('_final'):
            if step_type and step_type.endswith('_final'):
                # 处理最终报告，提取IP映射信息
                report_data = data.get('report')
                if report_data and 'mask_ip' in step_type:
                    self.set_final_summary_report(report_data)
            return
        
        # 标准化步骤名称 - 修复Pipeline和ReportManager之间的映射不匹配
        step_display_names = {
            'mask_ip': 'IP Masking',
            'mask_ips': 'IP Masking',  # 修复：Pipeline发送的是复数形式
            'remove_dupes': 'Deduplication', 
            'intelligent_trim': 'Payload Trimming',
            'trim_payloads': 'Payload Trimming'  # 修复：Pipeline发送的是trim_payloads
        }
        
        step_name = step_display_names.get(step_type, step_type)
        
        # 存储步骤结果
        self.main_window.file_processing_results[self.main_window.current_processing_file]['steps'][step_name] = {
            'type': step_type,
            'data': data
        }
        
        # 如果是IP匿名化步骤，提取文件级别的IP映射
        if step_type in ['mask_ip', 'mask_ips'] and 'file_ip_mappings' in data:
            if not hasattr(self.main_window, '_current_file_ips'):
                self.main_window._current_file_ips = {}
            self.main_window._current_file_ips[self.main_window.current_processing_file] = data['file_ip_mappings']
            # 将IP映射添加到全局映射中
            self.main_window.global_ip_mappings.update(data['file_ip_mappings']) 