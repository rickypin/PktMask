"""
PktMask 统一依赖检查器

本模块实现了统一的依赖检查接口，整合了分散在各个模块中的tshark检查逻辑，
并提供了标准化的依赖状态报告功能。
"""

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from pktmask.infrastructure.logging import get_logger
from pktmask.infrastructure.tshark import TSharkManager, TSharkStatus, TLSMarkerValidator


class DependencyStatus(Enum):
    """依赖状态枚举"""
    SATISFIED = "satisfied"
    MISSING = "missing"
    VERSION_MISMATCH = "version_mismatch"
    PERMISSION_ERROR = "permission_error"
    EXECUTION_ERROR = "execution_error"


@dataclass
class DependencyResult:
    """依赖检查结果"""
    name: str
    status: DependencyStatus
    version_found: Optional[str] = None
    version_required: Optional[str] = None
    path: Optional[str] = None
    error_message: Optional[str] = None
    
    @property
    def is_satisfied(self) -> bool:
        """检查依赖是否满足"""
        return self.status == DependencyStatus.SATISFIED


class DependencyChecker:
    """统一的依赖检查器
    
    整合现有的分散检查逻辑，提供标准化的依赖验证接口。
    复用scripts/check_tshark_dependencies.py中的成熟逻辑。
    """
    
    # TShark相关常量 (复用自现有代码)
    MIN_TSHARK_VERSION = (4, 2, 0)
    DEFAULT_TSHARK_PATHS = [
        "/usr/bin/tshark",
        "/usr/local/bin/tshark", 
        "/opt/wireshark/bin/tshark",
        "C:\\Program Files\\Wireshark\\tshark.exe",
        "C:\\Program Files (x86)\\Wireshark\\tshark.exe"
    ]
    REQUIRED_PROTOCOLS = ["tcp", "tls", "ssl", "ip", "ipv6"]
    REQUIRED_FIELDS = [
        "tcp.seq", "tcp.seq_raw", "tcp.len", "tcp.payload",
        "tls.record.content_type", "tls.record.length",
        "frame.number", "frame.time_relative"
    ]
    
    def __init__(self, custom_tshark_path: Optional[str] = None):
        """初始化依赖检查器

        Args:
            custom_tshark_path: 自定义TShark路径
        """
        self.logger = get_logger(__name__)
        self._cache = {}  # 简单的结果缓存

        # 使用新的TSharkManager
        self.tshark_manager = TSharkManager(custom_path=custom_tshark_path)

        # TLS marker验证器
        self.tls_validator = TLSMarkerValidator(tshark_manager=self.tshark_manager)
    
    def check_all_dependencies(self, use_cache: bool = True) -> Dict[str, DependencyResult]:
        """检查所有依赖
        
        Args:
            use_cache: 是否使用缓存结果
            
        Returns:
            依赖检查结果字典
        """
        if use_cache and 'all_dependencies' in self._cache:
            return self._cache['all_dependencies']
        
        results = {}
        results['tshark'] = self.check_tshark()
        
        # 未来可扩展其他依赖
        # results['python'] = self.check_python_version()
        # results['scapy'] = self.check_scapy()
        
        if use_cache:
            self._cache['all_dependencies'] = results
        
        return results
    
    def are_dependencies_satisfied(self) -> bool:
        """检查所有依赖是否满足"""
        results = self.check_all_dependencies()
        return all(result.is_satisfied for result in results.values())
    
    def get_status_messages(self) -> List[str]:
        """获取状态消息用于GUI显示"""
        results = self.check_all_dependencies()
        messages = []
        
        for name, result in results.items():
            if not result.is_satisfied:
                messages.append(self._format_error_message(result))
        
        return messages

    def get_tshark_installation_guide(self) -> Dict[str, Any]:
        """获取TShark安装指导

        Returns:
            平台特定的安装指导信息
        """
        return self.tshark_manager.get_installation_guide()

    def validate_tls_marker_functionality(self) -> Dict[str, any]:
        """验证TLS marker功能的完整性

        Returns:
            TLS marker验证结果详情
        """
        tls_validation = self.tls_validator.validate_tls_marker_support()

        return {
            'success': tls_validation.success,
            'missing_capabilities': tls_validation.missing_capabilities,
            'error_messages': tls_validation.error_messages,
            'detailed_results': tls_validation.detailed_results,
            'tshark_path': tls_validation.tshark_path,
            'validation_report': self.tls_validator.generate_validation_report(tls_validation)
        }
    
    def check_tshark(self) -> DependencyResult:
        """检查tshark依赖 - 使用新的TSharkManager"""
        try:
            # 使用TSharkManager进行检测
            tshark_info = self.tshark_manager.detect_tshark()

            # 转换TSharkStatus到DependencyStatus
            status_mapping = {
                TSharkStatus.AVAILABLE: DependencyStatus.SATISFIED,
                TSharkStatus.MISSING: DependencyStatus.MISSING,
                TSharkStatus.VERSION_TOO_LOW: DependencyStatus.VERSION_MISMATCH,
                TSharkStatus.EXECUTION_ERROR: DependencyStatus.EXECUTION_ERROR,
                TSharkStatus.PERMISSION_ERROR: DependencyStatus.PERMISSION_ERROR
            }

            dependency_status = status_mapping.get(tshark_info.status, DependencyStatus.EXECUTION_ERROR)

            # 如果TShark可用，进行TLS功能验证
            if tshark_info.is_available:
                # 使用专门的TLS marker验证器
                tls_validation = self.tls_validator.validate_tls_marker_support()

                if not tls_validation.success:
                    return DependencyResult(
                        name="tshark",
                        status=DependencyStatus.EXECUTION_ERROR,
                        path=tshark_info.path,
                        version_found=tshark_info.version_formatted,
                        version_required=self._format_version(self.MIN_TSHARK_VERSION),
                        error_message=f"TLS marker validation failed: {'; '.join(tls_validation.error_messages)}"
                    )

            return DependencyResult(
                name="tshark",
                status=dependency_status,
                path=tshark_info.path,
                version_found=tshark_info.version_formatted if tshark_info.version else None,
                version_required=self._format_version(self.MIN_TSHARK_VERSION),
                error_message=tshark_info.error_message if tshark_info.error_message else None
            )

        except Exception as e:
            self.logger.error(f"TShark dependency check failed: {e}")
            return DependencyResult(
                name="tshark",
                status=DependencyStatus.EXECUTION_ERROR,
                version_required=self._format_version(self.MIN_TSHARK_VERSION),
                error_message=f"Unexpected error during TShark check: {e}"
            )
    
    def _find_tshark_executable(self, custom_path: Optional[str] = None) -> Optional[str]:
        """查找tshark可执行文件 (复用自scripts/check_tshark_dependencies.py)"""
        # 1. 检查自定义路径
        if custom_path:
            if Path(custom_path).exists():
                return custom_path
            else:
                self.logger.warning(f"Custom tshark path does not exist: {custom_path}")
                return None
        
        # 2. 检查默认路径
        for path in self.DEFAULT_TSHARK_PATHS:
            if Path(path).exists():
                return path
        
        # 3. 在系统PATH中搜索
        return shutil.which('tshark')
    
    def _check_tshark_version(self, tshark_path: str) -> Dict[str, any]:
        """检查tshark版本 (复用自scripts/check_tshark_dependencies.py)"""
        result = {
            'success': False,
            'version': None,
            'version_string': '',
            'meets_requirement': False,
            'error': None
        }
        
        try:
            proc = subprocess.run(
                [tshark_path, '-v'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if proc.returncode != 0:
                result['error'] = f"tshark -v returned non-zero exit code: {proc.returncode}"
                return result
            
            output = proc.stdout + proc.stderr
            result['version_string'] = output.strip()
            
            version = self._parse_tshark_version(output)
            if version:
                result['version'] = version
                result['meets_requirement'] = version >= self.MIN_TSHARK_VERSION
                result['success'] = True
            else:
                result['error'] = "Unable to parse version number"
                
        except subprocess.TimeoutExpired:
            result['error'] = "tshark -v execution timeout"
        except Exception as e:
            result['error'] = f"Version check failed: {e}"
        
        return result
    
    def _parse_tshark_version(self, output: str) -> Optional[Tuple[int, int, int]]:
        """从tshark -v输出解析版本号 (复用自现有代码)"""
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
        if not m:
            return None
        return tuple(map(int, m.groups()))
    
    def _check_protocol_support(self, tshark_path: str) -> Dict[str, any]:
        """检查协议支持 (简化版本)"""
        result = {
            'success': False,
            'supported_protocols': [],
            'missing_protocols': [],
            'error': None
        }
        
        try:
            proc = subprocess.run(
                [tshark_path, '-G', 'protocols'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if proc.returncode != 0:
                result['error'] = f"tshark -G protocols returned non-zero exit code: {proc.returncode}"
                return result
            
            protocols = proc.stdout.lower()
            
            for protocol in self.REQUIRED_PROTOCOLS:
                if protocol in protocols:
                    result['supported_protocols'].append(protocol)
                else:
                    result['missing_protocols'].append(protocol)
            
            result['success'] = len(result['missing_protocols']) == 0
            
        except subprocess.TimeoutExpired:
            result['error'] = "Protocol support check timeout"
        except Exception as e:
            result['error'] = f"Protocol support check failed: {e}"
        
        return result
    
    def _check_json_output(self, tshark_path: str) -> Dict[str, any]:
        """检查JSON输出功能 (复用自scripts/check_tshark_dependencies.py)"""
        result = {
            'success': False,
            'error': None
        }
        
        try:
            # 创建一个最小的测试命令
            proc = subprocess.run(
                [tshark_path, '-T', 'json', '-c', '0'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # 即使没有输入文件，tshark也应该能够识别JSON格式选项
            # 返回码可能不是0，但不应该有格式错误
            if 'json' in proc.stderr.lower() and 'invalid' in proc.stderr.lower():
                result['error'] = "JSON output format not supported"
            else:
                result['success'] = True
                
        except subprocess.TimeoutExpired:
            result['error'] = "JSON output test timeout"
        except Exception as e:
            result['error'] = f"JSON output test failed: {e}"
        
        return result
    
    def _format_version(self, version: Tuple[int, int, int]) -> str:
        """格式化版本号"""
        return '.'.join(map(str, version))
    
    def _format_error_message(self, result: DependencyResult) -> str:
        """格式化错误消息用于GUI显示"""
        if result.status == DependencyStatus.MISSING:
            return f"{result.name.upper()} not found in system PATH"
        elif result.status == DependencyStatus.VERSION_MISMATCH:
            return f"{result.name.upper()} version too old: {result.version_found}, required: ≥{result.version_required}"
        elif result.status == DependencyStatus.PERMISSION_ERROR:
            return f"{result.name.upper()} permission denied: {result.error_message}"
        elif result.status == DependencyStatus.EXECUTION_ERROR:
            return f"{result.name.upper()} execution error: {result.error_message}"
        else:
            return f"{result.name.upper()} unknown error: {result.error_message}"
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
