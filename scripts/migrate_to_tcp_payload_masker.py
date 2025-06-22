#!/usr/bin/env python3
"""
TCP Payload Masker 迁移工具

用于将使用旧Independent PCAP Masker的代码迁移到新的TCP Payload Masker API。
自动检测并转换代码中的导入、类名和方法调用。
"""

import os
import re
import sys
import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class MigrationRule:
    """迁移规则"""
    pattern: str           # 正则表达式模式
    replacement: str       # 替换文本
    description: str       # 规则描述
    is_import: bool = False  # 是否为导入语句
    is_class: bool = False   # 是否为类名
    is_method: bool = False  # 是否为方法调用


class TcpPayloadMaskerMigrator:
    """TCP Payload Masker 迁移器"""
    
    def __init__(self):
        self.migration_rules = self._create_migration_rules()
        self.migration_stats = {
            'files_processed': 0,
            'files_modified': 0,
            'total_replacements': 0,
            'rule_usage': {}
        }
    
    def _create_migration_rules(self) -> List[MigrationRule]:
        """创建迁移规则列表"""
        rules = [
            # 导入语句迁移
            MigrationRule(
                pattern=r'from\s+pktmask\.core\.independent_pcap_masker',
                replacement='from pktmask.core.tcp_payload_masker',
                description='更新模块导入路径',
                is_import=True
            ),
            MigrationRule(
                pattern=r'import\s+pktmask\.core\.independent_pcap_masker',
                replacement='import pktmask.core.tcp_payload_masker',
                description='更新模块导入路径',
                is_import=True
            ),
            
            # 类名迁移
            MigrationRule(
                pattern=r'\bIndependentPcapMasker\b',
                replacement='TcpPayloadMasker',
                description='Independent PCAP Masker -> TCP Payload Masker',
                is_class=True
            ),
            MigrationRule(
                pattern=r'\bMaskEntry\b',
                replacement='TcpKeepRangeEntry',
                description='MaskEntry -> TcpKeepRangeEntry',
                is_class=True
            ),
            MigrationRule(
                pattern=r'\bMaskingResult\b',
                replacement='TcpMaskingResult',
                description='MaskingResult -> TcpMaskingResult',
                is_class=True
            ),
            MigrationRule(
                pattern=r'\bSequenceMaskTable\b',
                replacement='TcpKeepRangeTable',
                description='SequenceMaskTable -> TcpKeepRangeTable',
                is_class=True
            ),
            MigrationRule(
                pattern=r'\bIndependentMaskerError\b',
                replacement='TcpPayloadMaskerError',
                description='IndependentMaskerError -> TcpPayloadMaskerError',
                is_class=True
            ),
            MigrationRule(
                pattern=r'\bMaskApplicationError\b',
                replacement='TcpKeepRangeApplicationError',
                description='MaskApplicationError -> TcpKeepRangeApplicationError',
                is_class=True
            ),
            
            # 方法名迁移
            MigrationRule(
                pattern=r'\.mask_pcap_with_sequences\(',
                replacement='.mask_tcp_payloads_with_keep_ranges(',
                description='主要API方法名更新',
                is_method=True
            ),
            MigrationRule(
                pattern=r'\.add_mask_entry\(',
                replacement='.add_keep_range_entry(',
                description='添加条目方法名更新',
                is_method=True
            ),
            MigrationRule(
                pattern=r'\.apply_masks_to_packets\(',
                replacement='.apply_keep_ranges_to_packets(',
                description='应用掩码方法名更新',
                is_method=True
            ),
            
            # 参数名迁移
            MigrationRule(
                pattern=r'\bmask_table\s*=',
                replacement='keep_range_table=',
                description='参数名：mask_table -> keep_range_table'
            ),
            MigrationRule(
                pattern=r'\bmask_entry\s*=',
                replacement='keep_range_entry=',
                description='参数名：mask_entry -> keep_range_entry'
            ),
            
            # 属性名迁移
            MigrationRule(
                pattern=r'\.mask_type\b',
                replacement='.protocol_hint',
                description='属性名：mask_type -> protocol_hint'
            ),
            MigrationRule(
                pattern=r'\.mask_params\b',
                replacement='.keep_ranges',
                description='属性名：mask_params -> keep_ranges'
            ),
            MigrationRule(
                pattern=r'\.streams_processed\b',
                replacement='.tcp_streams_processed',
                description='属性名：streams_processed -> tcp_streams_processed'
            ),
            
            # 枚举值迁移（旧的掩码类型到协议提示）
            MigrationRule(
                pattern=r'"mask_after"',
                replacement='"TLS"',
                description='掩码类型到协议提示的映射'
            ),
            MigrationRule(
                pattern=r'"mask_range"',
                replacement='"HTTP"',
                description='掩码类型到协议提示的映射'
            ),
            MigrationRule(
                pattern=r'"keep_all"',
                replacement='"UNKNOWN"',
                description='掩码类型到协议提示的映射'
            ),
        ]
        
        return rules
    
    def migrate_file(self, file_path: Path, dry_run: bool = False) -> Dict[str, any]:
        """迁移单个文件
        
        Args:
            file_path: 要迁移的文件路径
            dry_run: 是否只是预览而不实际修改
            
        Returns:
            迁移结果统计
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            modified_content = original_content
            file_stats = {
                'file_path': str(file_path),
                'replacements': [],
                'total_replacements': 0,
                'modified': False
            }
            
            # 应用所有迁移规则
            for rule in self.migration_rules:
                matches = list(re.finditer(rule.pattern, modified_content))
                if matches:
                    # 记录替换
                    for match in matches:
                        file_stats['replacements'].append({
                            'line': modified_content[:match.start()].count('\n') + 1,
                            'old_text': match.group(0),
                            'new_text': re.sub(rule.pattern, rule.replacement, match.group(0)),
                            'description': rule.description
                        })
                    
                    # 执行替换
                    modified_content = re.sub(rule.pattern, rule.replacement, modified_content)
                    
                    # 更新统计
                    rule_key = rule.description
                    if rule_key not in self.migration_stats['rule_usage']:
                        self.migration_stats['rule_usage'][rule_key] = 0
                    self.migration_stats['rule_usage'][rule_key] += len(matches)
                    
                    file_stats['total_replacements'] += len(matches)
                    self.migration_stats['total_replacements'] += len(matches)
            
            # 检查是否有修改
            file_stats['modified'] = original_content != modified_content
            
            # 写入文件（如果不是干运行且有修改）
            if not dry_run and file_stats['modified']:
                # 创建备份
                backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                
                # 写入修改后的内容
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                logger.info(f"已迁移文件: {file_path} ({file_stats['total_replacements']} 处修改)")
                self.migration_stats['files_modified'] += 1
            
            self.migration_stats['files_processed'] += 1
            return file_stats
            
        except Exception as e:
            logger.error(f"迁移文件失败 {file_path}: {e}")
            return {
                'file_path': str(file_path),
                'error': str(e),
                'modified': False
            }
    
    def migrate_directory(self, directory: Path, pattern: str = "*.py", 
                         recursive: bool = True, dry_run: bool = False) -> List[Dict]:
        """迁移目录中的所有匹配文件
        
        Args:
            directory: 目标目录
            pattern: 文件匹配模式
            recursive: 是否递归搜索子目录
            dry_run: 是否只是预览
            
        Returns:
            所有文件的迁移结果列表
        """
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        # 查找匹配的文件
        if recursive:
            files = list(directory.rglob(pattern))
        else:
            files = list(directory.glob(pattern))
        
        logger.info(f"在 {directory} 中找到 {len(files)} 个匹配文件")
        
        results = []
        for file_path in files:
            if file_path.is_file():
                result = self.migrate_file(file_path, dry_run)
                results.append(result)
        
        return results
    
    def generate_migration_report(self, results: List[Dict], output_file: Optional[Path] = None) -> str:
        """生成迁移报告
        
        Args:
            results: 迁移结果列表
            output_file: 输出文件路径（可选）
            
        Returns:
            报告内容
        """
        report_lines = [
            "# TCP Payload Masker 迁移报告",
            "",
            f"## 迁移统计",
            f"- 处理文件数: {self.migration_stats['files_processed']}",
            f"- 修改文件数: {self.migration_stats['files_modified']}",
            f"- 总替换数: {self.migration_stats['total_replacements']}",
            "",
            "## 规则使用统计",
        ]
        
        for rule, count in sorted(self.migration_stats['rule_usage'].items(), 
                                key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {rule}: {count} 次")
        
        report_lines.extend([
            "",
            "## 文件修改详情",
            ""
        ])
        
        for result in results:
            if result.get('modified', False):
                report_lines.append(f"### {result['file_path']}")
                report_lines.append(f"修改次数: {result['total_replacements']}")
                report_lines.append("")
                
                for replacement in result['replacements']:
                    report_lines.append(
                        f"- 第{replacement['line']}行: "
                        f"`{replacement['old_text']}` → `{replacement['new_text']}` "
                        f"({replacement['description']})"
                    )
                report_lines.append("")
        
        # 添加迁移指导
        report_lines.extend([
            "## 后续操作指导",
            "",
            "### 1. 验证迁移结果",
            "```bash",
            "# 运行测试确保迁移成功",
            "python -m pytest tests/",
            "```",
            "",
            "### 2. 更新配置",
            "- 检查配置文件中的类名和参数名",
            "- 更新掩码类型到协议提示的映射",
            "- 验证保留范围配置的正确性",
            "",
            "### 3. 性能优化",
            "- 启用TCP专用优化模式",
            "- 配置批量处理选项",
            "- 调整保留范围表设置",
            "",
            "### 4. 监控和调试",
            "- 使用新的性能指标API",
            "- 检查TCP流处理统计",
            "- 验证保留范围掩码效果",
        ])
        
        report_content = "\n".join(report_lines)
        
        # 输出到文件（如果指定）
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            logger.info(f"迁移报告已保存到: {output_file}")
        
        return report_content
    
    def create_compatibility_wrapper(self, output_file: Path) -> None:
        """创建兼容性包装器代码
        
        为旧代码提供向后兼容的接口包装
        """
        wrapper_code = '''"""
TCP Payload Masker 兼容性包装器

为使用旧Independent PCAP Masker API的代码提供向后兼容性。
这是一个临时解决方案，建议尽快迁移到新API。
"""

import warnings
from typing import Dict, List, Optional, Any

# 导入新的TCP Payload Masker
from pktmask.core.tcp_payload_masker import (
    TcpPayloadMasker,
    TcpKeepRangeEntry,
    TcpMaskingResult,
    TcpKeepRangeTable,
    TcpPayloadMaskerError
)


class IndependentPcapMasker(TcpPayloadMasker):
    """Independent PCAP Masker 兼容性包装器
    
    ⚠️ 已弃用：请使用TcpPayloadMasker替代
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        warnings.warn(
            "IndependentPcapMasker已弃用，请使用TcpPayloadMasker",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config)
    
    def mask_pcap_with_sequences(self, input_pcap: str, mask_table, output_pcap: str):
        """兼容性方法：mask_pcap_with_sequences -> mask_tcp_payloads_with_keep_ranges"""
        warnings.warn(
            "mask_pcap_with_sequences已弃用，请使用mask_tcp_payloads_with_keep_ranges",
            DeprecationWarning,
            stacklevel=2
        )
        return self.mask_tcp_payloads_with_keep_ranges(input_pcap, mask_table, output_pcap)


class MaskEntry(TcpKeepRangeEntry):
    """MaskEntry 兼容性包装器
    
    ⚠️ 已弃用：请使用TcpKeepRangeEntry替代
    """
    
    def __init__(self, stream_id: str, sequence_start: int, sequence_end: int,
                 mask_type: str = "keep_range", mask_params: Optional[List] = None, **kwargs):
        warnings.warn(
            "MaskEntry已弃用，请使用TcpKeepRangeEntry",
            DeprecationWarning,
            stacklevel=2
        )
        
        # 转换旧参数到新格式
        keep_ranges = mask_params or [(0, 5)]  # 默认保留头部5字节
        protocol_hint = self._convert_mask_type(mask_type)
        
        super().__init__(
            stream_id=stream_id,
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            keep_ranges=keep_ranges,
            protocol_hint=protocol_hint,
            **kwargs
        )
        
        # 保留旧属性以兼容
        self.mask_type = mask_type
        self.mask_params = mask_params
    
    def _convert_mask_type(self, mask_type: str) -> str:
        """转换旧的掩码类型到协议提示"""
        mapping = {
            "mask_after": "TLS",
            "mask_range": "HTTP",
            "keep_all": "UNKNOWN"
        }
        return mapping.get(mask_type, "UNKNOWN")


class MaskingResult(TcpMaskingResult):
    """MaskingResult 兼容性包装器
    
    ⚠️ 已弃用：请使用TcpMaskingResult替代
    """
    
    def __init__(self, **kwargs):
        warnings.warn(
            "MaskingResult已弃用，请使用TcpMaskingResult",
            DeprecationWarning,
            stacklevel=2
        )
        
        # 兼容旧参数名
        if 'streams_processed' in kwargs:
            kwargs['tcp_streams_processed'] = kwargs.pop('streams_processed')
        
        super().__init__(**kwargs)
        
        # 保留旧属性名以兼容
        self.streams_processed = self.tcp_streams_processed


class SequenceMaskTable(TcpKeepRangeTable):
    """SequenceMaskTable 兼容性包装器
    
    ⚠️ 已弃用：请使用TcpKeepRangeTable替代
    """
    
    def __init__(self):
        warnings.warn(
            "SequenceMaskTable已弃用，请使用TcpKeepRangeTable",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__()
    
    def add_mask_entry(self, entry):
        """兼容性方法：add_mask_entry -> add_keep_range_entry"""
        warnings.warn(
            "add_mask_entry已弃用，请使用add_keep_range_entry",
            DeprecationWarning,
            stacklevel=2
        )
        return self.add_keep_range_entry(entry)


# 异常类兼容性
class IndependentMaskerError(TcpPayloadMaskerError):
    """IndependentMaskerError 兼容性包装器"""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "IndependentMaskerError已弃用，请使用TcpPayloadMaskerError",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)


# 为了完全向后兼容，创建别名
MaskApplicationError = TcpPayloadMaskerError


# 迁移指导函数
def get_migration_guide() -> str:
    """获取迁移指导信息"""
    return """
    TCP Payload Masker 迁移指导：
    
    1. 类名迁移：
       - IndependentPcapMasker → TcpPayloadMasker
       - MaskEntry → TcpKeepRangeEntry  
       - MaskingResult → TcpMaskingResult
       - SequenceMaskTable → TcpKeepRangeTable
    
    2. 方法名迁移：
       - mask_pcap_with_sequences → mask_tcp_payloads_with_keep_ranges
       - add_mask_entry → add_keep_range_entry
    
    3. 参数名迁移：
       - mask_table → keep_range_table
       - mask_type → protocol_hint
       - mask_params → keep_ranges
    
    4. 概念转换：
       - 从"掩码类型"转为"保留范围"概念
       - 从"记录要掩码的内容"转为"记录要保留的内容"
       - 隐私优先：默认掩码所有，只保留指定范围
    
    5. 运行迁移工具：
       python scripts/migrate_to_tcp_payload_masker.py --directory /path/to/code
    """
'''
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(wrapper_code)
        
        logger.info(f"兼容性包装器已创建: {output_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TCP Payload Masker 迁移工具")
    parser.add_argument('--file', type=Path, help='迁移单个文件')
    parser.add_argument('--directory', type=Path, help='迁移目录中的所有Python文件')
    parser.add_argument('--pattern', default='*.py', help='文件匹配模式（默认: *.py）')
    parser.add_argument('--recursive', action='store_true', help='递归搜索子目录')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际修改文件')
    parser.add_argument('--report', type=Path, help='生成迁移报告文件')
    parser.add_argument('--create-wrapper', type=Path, help='创建兼容性包装器文件')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    migrator = TcpPayloadMaskerMigrator()
    
    # 创建兼容性包装器
    if args.create_wrapper:
        migrator.create_compatibility_wrapper(args.create_wrapper)
        return
    
    results = []
    
    # 迁移单个文件
    if args.file:
        if not args.file.exists():
            logger.error(f"文件不存在: {args.file}")
            sys.exit(1)
        
        result = migrator.migrate_file(args.file, args.dry_run)
        results.append(result)
    
    # 迁移目录
    elif args.directory:
        if not args.directory.exists():
            logger.error(f"目录不存在: {args.directory}")
            sys.exit(1)
        
        results = migrator.migrate_directory(
            args.directory, args.pattern, args.recursive, args.dry_run
        )
    
    else:
        parser.print_help()
        return
    
    # 生成报告
    if results:
        report = migrator.generate_migration_report(results, args.report)
        
        if not args.report:
            print("\n" + report)
        
        # 输出总结
        modified_files = [r for r in results if r.get('modified', False)]
        logger.info(f"迁移完成: {len(modified_files)}/{len(results)} 个文件被修改")
        
        if args.dry_run:
            logger.info("这是预览模式 - 实际文件未被修改")
        elif modified_files:
            logger.info("备份文件已创建（.backup扩展名）")


if __name__ == '__main__':
    main()