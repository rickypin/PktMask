#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Chinese Text Detection Script for PktMask

This script scans the PktMask codebase for Chinese characters in code files,
documentation, and configuration files to enforce the English-Only Coding Policy.

Usage:
    python scripts/maintenance/check_chinese_text.py [--fix] [--report]
    
Options:
    --fix     Attempt to auto-fix simple cases (interactive mode)
    --report  Generate detailed compliance report
    --ci      CI mode - exit with error code if Chinese text found
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Chinese character pattern (Unicode range for CJK characters)
CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')

# File extensions to check
CHECKED_EXTENSIONS = {'.py', '.md', '.txt', '.yml', '.yaml', '.json', '.toml', '.cfg', '.ini'}

# Directories to exclude from scanning
EXCLUDED_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 
    'node_modules', '.tox', 'build', 'dist', '.mypy_cache'
}

# Files to exclude from scanning
EXCLUDED_FILES = {
    'CHANGELOG.md',  # May contain Chinese in historical entries
    'CONTRIBUTORS.md',  # May contain Chinese names
}

@dataclass
class ChineseTextIssue:
    """Represents a Chinese text issue found in a file"""
    file_path: str
    line_number: int
    line_content: str
    chinese_text: str
    issue_type: str  # 'comment', 'docstring', 'string_literal', 'other'
    severity: str    # 'critical', 'high', 'medium', 'low'

@dataclass
class ComplianceReport:
    """Compliance report data structure"""
    scan_date: str
    total_files_scanned: int
    files_with_issues: int
    total_issues: int
    issues_by_type: Dict[str, int]
    issues_by_severity: Dict[str, int]
    compliance_rate: float
    issues: List[ChineseTextIssue]

class ChineseTextDetector:
    """Main class for detecting Chinese text in codebase"""
    
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.issues: List[ChineseTextIssue] = []
        
    def scan_codebase(self) -> ComplianceReport:
        """Scan entire codebase for Chinese text"""
        print(f"🔍 Scanning codebase at: {self.root_path}")
        
        total_files = 0
        files_with_issues = 0
        
        for file_path in self._get_files_to_scan():
            total_files += 1
            file_issues = self._scan_file(file_path)
            
            if file_issues:
                files_with_issues += 1
                self.issues.extend(file_issues)
                
        return self._generate_report(total_files, files_with_issues)
    
    def _get_files_to_scan(self) -> List[Path]:
        """Get list of files to scan"""
        files_to_scan = []
        
        for file_path in self.root_path.rglob('*'):
            # Skip directories
            if file_path.is_dir():
                continue
                
            # Skip excluded directories
            if any(excluded_dir in file_path.parts for excluded_dir in EXCLUDED_DIRS):
                continue
                
            # Skip excluded files
            if file_path.name in EXCLUDED_FILES:
                continue
                
            # Check file extension
            if file_path.suffix in CHECKED_EXTENSIONS:
                files_to_scan.append(file_path)
                
        return sorted(files_to_scan)
    
    def _scan_file(self, file_path: Path) -> List[ChineseTextIssue]:
        """Scan a single file for Chinese text"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    chinese_matches = CHINESE_PATTERN.findall(line)
                    if chinese_matches:
                        chinese_text = ', '.join(chinese_matches)
                        issue_type = self._classify_issue_type(line, file_path.suffix)
                        severity = self._determine_severity(issue_type, file_path)
                        
                        issue = ChineseTextIssue(
                            file_path=str(file_path.relative_to(self.root_path)),
                            line_number=line_num,
                            line_content=line.strip(),
                            chinese_text=chinese_text,
                            issue_type=issue_type,
                            severity=severity
                        )
                        issues.append(issue)
                        
        except Exception as e:
            print(f"⚠️  Warning: Could not read {file_path}: {e}")
            
        return issues
    
    def _classify_issue_type(self, line: str, file_extension: str) -> str:
        """Classify the type of Chinese text issue"""
        line_stripped = line.strip()
        
        if file_extension == '.py':
            # Python-specific classification
            if line_stripped.startswith('#'):
                return 'comment'
            elif '"""' in line or "'''" in line:
                return 'docstring'
            elif any(quote in line for quote in ['"', "'"]):
                return 'string_literal'
            else:
                return 'other'
        elif file_extension == '.md':
            return 'documentation'
        elif file_extension in {'.yml', '.yaml', '.json', '.toml'}:
            return 'configuration'
        else:
            return 'other'
    
    def _determine_severity(self, issue_type: str, file_path: Path) -> str:
        """Determine severity of the issue"""
        # Critical: Core pipeline stages, public APIs
        if 'core/pipeline/stages' in str(file_path):
            return 'critical'
        
        # High: GUI components, infrastructure modules
        if any(component in str(file_path) for component in ['gui/', 'infrastructure/']):
            return 'high'
        
        # Medium: Documentation, configuration
        if issue_type in ['documentation', 'configuration']:
            return 'medium'
        
        # High: Docstrings and user-facing strings
        if issue_type in ['docstring', 'string_literal']:
            return 'high'
        
        # Medium: Comments
        if issue_type == 'comment':
            return 'medium'
        
        return 'low'
    
    def _generate_report(self, total_files: int, files_with_issues: int) -> ComplianceReport:
        """Generate compliance report"""
        issues_by_type = {}
        issues_by_severity = {}
        
        for issue in self.issues:
            issues_by_type[issue.issue_type] = issues_by_type.get(issue.issue_type, 0) + 1
            issues_by_severity[issue.severity] = issues_by_severity.get(issue.severity, 0) + 1
        
        compliance_rate = ((total_files - files_with_issues) / total_files * 100) if total_files > 0 else 100.0
        
        return ComplianceReport(
            scan_date=datetime.now().isoformat(),
            total_files_scanned=total_files,
            files_with_issues=files_with_issues,
            total_issues=len(self.issues),
            issues_by_type=issues_by_type,
            issues_by_severity=issues_by_severity,
            compliance_rate=compliance_rate,
            issues=self.issues
        )

def print_console_report(report: ComplianceReport):
    """Print compliance report to console"""
    print("\n" + "="*80)
    print("📊 CHINESE TEXT COMPLIANCE REPORT")
    print("="*80)
    
    print(f"📅 Scan Date: {report.scan_date}")
    print(f"📁 Total Files Scanned: {report.total_files_scanned}")
    print(f"❌ Files with Issues: {report.files_with_issues}")
    print(f"🔍 Total Issues Found: {report.total_issues}")
    print(f"✅ Compliance Rate: {report.compliance_rate:.1f}%")
    
    if report.issues_by_severity:
        print("\n📈 Issues by Severity:")
        for severity, count in sorted(report.issues_by_severity.items()):
            emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(severity, '⚪')
            print(f"  {emoji} {severity.title()}: {count}")
    
    if report.issues_by_type:
        print("\n📋 Issues by Type:")
        for issue_type, count in sorted(report.issues_by_type.items()):
            print(f"  • {issue_type.replace('_', ' ').title()}: {count}")
    
    if report.issues:
        print(f"\n🔍 Detailed Issues (showing first 20):")
        print("-" * 80)
        
        for i, issue in enumerate(report.issues[:20]):
            severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(issue.severity, '⚪')
            print(f"{severity_emoji} {issue.file_path}:{issue.line_number}")
            print(f"   Type: {issue.issue_type} | Chinese: {issue.chinese_text}")
            print(f"   Line: {issue.line_content[:100]}{'...' if len(issue.line_content) > 100 else ''}")
            print()
        
        if len(report.issues) > 20:
            print(f"... and {len(report.issues) - 20} more issues")
    
    print("="*80)

def save_json_report(report: ComplianceReport, output_path: Path):
    """Save compliance report as JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(report), f, indent=2, ensure_ascii=False)
    print(f"📄 Detailed report saved to: {output_path}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Detect Chinese text in PktMask codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/maintenance/check_chinese_text.py
  python scripts/maintenance/check_chinese_text.py --report
  python scripts/maintenance/check_chinese_text.py --ci
        """
    )
    
    parser.add_argument('--report', action='store_true',
                       help='Generate detailed JSON report')
    parser.add_argument('--ci', action='store_true',
                       help='CI mode - exit with error if issues found')
    parser.add_argument('--output', type=Path, 
                       default=Path('reports/chinese_text_compliance.json'),
                       help='Output path for JSON report')
    
    args = parser.parse_args()
    
    # Determine project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent.parent  # Go up from scripts/maintenance/
    
    # Create detector and scan
    detector = ChineseTextDetector(project_root)
    report = detector.scan_codebase()
    
    # Print console report
    print_console_report(report)
    
    # Save JSON report if requested
    if args.report:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save_json_report(report, args.output)
    
    # CI mode - exit with error if issues found
    if args.ci and report.total_issues > 0:
        print(f"\n❌ CI Mode: Found {report.total_issues} Chinese text issues")
        print("Please translate all Chinese text to English before merging")
        sys.exit(1)
    
    # Success message
    if report.total_issues == 0:
        print("\n✅ SUCCESS: No Chinese text found - codebase is compliant!")
    else:
        print(f"\n⚠️  ACTION REQUIRED: Found {report.total_issues} issues to resolve")
        print("Run with --report flag to generate detailed JSON report")

if __name__ == '__main__':
    main()
