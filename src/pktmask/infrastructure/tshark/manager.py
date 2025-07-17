#!/usr/bin/env python3
"""
Cross-platform TShark Manager

Unified management for TShark detection, configuration, and initialization
across MacOS and Windows platforms.
"""

import os
import platform
import shutil
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from pktmask.infrastructure.logging import get_logger


class TSharkStatus(Enum):
    """TShark availability status"""
    AVAILABLE = "available"
    MISSING = "missing"
    VERSION_TOO_LOW = "version_too_low"
    EXECUTION_ERROR = "execution_error"
    PERMISSION_ERROR = "permission_error"


@dataclass
class TSharkInfo:
    """TShark installation information"""
    path: Optional[str] = None
    version: Optional[Tuple[int, int, int]] = None
    version_string: str = ""
    status: TSharkStatus = TSharkStatus.MISSING
    error_message: str = ""
    platform_specific_paths: List[str] = None
    
    def __post_init__(self):
        if self.platform_specific_paths is None:
            self.platform_specific_paths = []
    
    @property
    def is_available(self) -> bool:
        """Check if TShark is available and usable"""
        return self.status == TSharkStatus.AVAILABLE
    
    @property
    def version_formatted(self) -> str:
        """Get formatted version string"""
        if self.version:
            return ".".join(map(str, self.version))
        return "Unknown"


class TSharkManager:
    """Cross-platform TShark manager"""
    
    # Minimum required TShark version
    MIN_VERSION = (4, 2, 0)
    
    # Platform-specific search paths
    PLATFORM_PATHS = {
        'Darwin': [  # macOS
            '/usr/local/bin/tshark',
            '/opt/homebrew/bin/tshark',  # Apple Silicon Homebrew
            '/usr/bin/tshark',
            '/Applications/Wireshark.app/Contents/MacOS/tshark',
            '/opt/wireshark/bin/tshark',
        ],
        'Windows': [  # Windows
            r'C:\Program Files\Wireshark\tshark.exe',
            r'C:\Program Files (x86)\Wireshark\tshark.exe',
            r'C:\ProgramData\chocolatey\bin\tshark.exe',  # Chocolatey
            r'C:\tools\wireshark\tshark.exe',  # Alternative Chocolatey path
        ],
        'Linux': [  # Linux
            '/usr/bin/tshark',
            '/usr/local/bin/tshark',
            '/opt/wireshark/bin/tshark',
            '/snap/bin/wireshark.tshark',  # Snap package
        ]
    }
    
    def __init__(self, custom_path: Optional[str] = None):
        """Initialize TShark manager
        
        Args:
            custom_path: Custom TShark executable path
        """
        self.logger = get_logger('tshark_manager')
        self.custom_path = custom_path
        self._cached_info: Optional[TSharkInfo] = None
        self._system = platform.system()
        
        self.logger.debug(f"TShark manager initialized for platform: {self._system}")
    
    def detect_tshark(self, force_refresh: bool = False) -> TSharkInfo:
        """Detect TShark installation
        
        Args:
            force_refresh: Force refresh cached information
            
        Returns:
            TShark installation information
        """
        if not force_refresh and self._cached_info:
            return self._cached_info
        
        self.logger.info("Starting TShark detection...")
        
        # Try custom path first
        if self.custom_path:
            info = self._check_tshark_path(self.custom_path)
            if info.is_available:
                self._cached_info = info
                self.logger.info(f"TShark found at custom path: {self.custom_path}")
                return info
            else:
                self.logger.warning(f"Custom TShark path failed: {info.error_message}")
        
        # Try platform-specific paths
        platform_paths = self.PLATFORM_PATHS.get(self._system, [])
        for path in platform_paths:
            if Path(path).exists():
                info = self._check_tshark_path(path)
                if info.is_available:
                    self._cached_info = info
                    self.logger.info(f"TShark found at: {path}")
                    return info
        
        # Try system PATH
        system_path = shutil.which('tshark')
        if system_path:
            info = self._check_tshark_path(system_path)
            if info.is_available:
                self._cached_info = info
                self.logger.info(f"TShark found in system PATH: {system_path}")
                return info
        
        # TShark not found
        error_info = TSharkInfo(
            status=TSharkStatus.MISSING,
            error_message="TShark executable not found in system PATH or default locations",
            platform_specific_paths=platform_paths
        )
        self._cached_info = error_info
        self.logger.error("TShark not found on system")
        return error_info
    
    def _check_tshark_path(self, path: str) -> TSharkInfo:
        """Check specific TShark path
        
        Args:
            path: Path to TShark executable
            
        Returns:
            TShark information for this path
        """
        try:
            # Check if file exists and is executable
            path_obj = Path(path)
            if not path_obj.exists():
                return TSharkInfo(
                    path=path,
                    status=TSharkStatus.MISSING,
                    error_message=f"File does not exist: {path}"
                )
            
            # Try to execute tshark -v
            result = subprocess.run(
                [path, '-v'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return TSharkInfo(
                    path=path,
                    status=TSharkStatus.EXECUTION_ERROR,
                    error_message=f"tshark -v returned exit code {result.returncode}"
                )
            
            # Parse version
            version_output = result.stdout + result.stderr
            version = self._parse_version(version_output)
            
            if not version:
                return TSharkInfo(
                    path=path,
                    status=TSharkStatus.EXECUTION_ERROR,
                    error_message="Unable to parse TShark version",
                    version_string=version_output.strip()
                )
            
            # Check version requirement
            if version < self.MIN_VERSION:
                return TSharkInfo(
                    path=path,
                    version=version,
                    version_string=version_output.strip(),
                    status=TSharkStatus.VERSION_TOO_LOW,
                    error_message=f"TShark version {'.'.join(map(str, version))} is too low, "
                                f"minimum required: {'.'.join(map(str, self.MIN_VERSION))}"
                )
            
            # Success
            return TSharkInfo(
                path=path,
                version=version,
                version_string=version_output.strip(),
                status=TSharkStatus.AVAILABLE
            )
            
        except subprocess.TimeoutExpired:
            return TSharkInfo(
                path=path,
                status=TSharkStatus.EXECUTION_ERROR,
                error_message="TShark execution timeout"
            )
        except PermissionError:
            return TSharkInfo(
                path=path,
                status=TSharkStatus.PERMISSION_ERROR,
                error_message="Permission denied to execute TShark"
            )
        except Exception as e:
            return TSharkInfo(
                path=path,
                status=TSharkStatus.EXECUTION_ERROR,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def _parse_version(self, version_output: str) -> Optional[Tuple[int, int, int]]:
        """Parse TShark version from output
        
        Args:
            version_output: Output from tshark -v command
            
        Returns:
            Version tuple (major, minor, patch) or None if parsing failed
        """
        # Look for version pattern like "TShark (Wireshark) 4.2.0"
        patterns = [
            r'TShark.*?(\d+)\.(\d+)\.(\d+)',
            r'wireshark.*?(\d+)\.(\d+)\.(\d+)',
            r'version.*?(\d+)\.(\d+)\.(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, version_output, re.IGNORECASE)
            if match:
                try:
                    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                except ValueError:
                    continue
        
        return None
    
    def get_installation_guide(self) -> Dict[str, Any]:
        """Get platform-specific installation guide
        
        Returns:
            Installation guide information
        """
        guides = {
            'Darwin': {
                'platform': 'macOS',
                'methods': [
                    {
                        'name': 'Homebrew (Recommended)',
                        'commands': [
                            'brew install --cask wireshark'
                        ],
                        'description': 'Install via Homebrew package manager'
                    },
                    {
                        'name': 'Official Installer',
                        'commands': [],
                        'description': 'Download from https://www.wireshark.org/download.html',
                        'url': 'https://www.wireshark.org/download.html'
                    }
                ],
                'common_paths': self.PLATFORM_PATHS.get('Darwin', [])
            },
            'Windows': {
                'platform': 'Windows',
                'methods': [
                    {
                        'name': 'Official Installer (Recommended)',
                        'commands': [],
                        'description': 'Download from https://www.wireshark.org/download.html',
                        'url': 'https://www.wireshark.org/download.html'
                    },
                    {
                        'name': 'Chocolatey',
                        'commands': [
                            'choco install wireshark'
                        ],
                        'description': 'Install via Chocolatey package manager'
                    }
                ],
                'common_paths': self.PLATFORM_PATHS.get('Windows', [])
            },
            'Linux': {
                'platform': 'Linux',
                'methods': [
                    {
                        'name': 'Package Manager',
                        'commands': [
                            'sudo apt install wireshark  # Ubuntu/Debian',
                            'sudo dnf install wireshark-cli  # Fedora',
                            'sudo yum install wireshark  # CentOS/RHEL'
                        ],
                        'description': 'Install via system package manager'
                    }
                ],
                'common_paths': self.PLATFORM_PATHS.get('Linux', [])
            }
        }
        
        return guides.get(self._system, {
            'platform': self._system,
            'methods': [],
            'common_paths': []
        })
    
    def verify_tls_capabilities(self, tshark_path: str) -> Dict[str, bool]:
        """Verify TLS-specific capabilities required by tls marker

        Args:
            tshark_path: Path to TShark executable

        Returns:
            Dictionary of capability check results
        """
        capabilities = {
            'tls_protocol_support': False,
            'json_output_support': False,
            'field_extraction_support': False,
            'tcp_reassembly_support': False,
            'tls_record_parsing': False,
            'tls_app_data_extraction': False,
            'tcp_stream_tracking': False,
            'two_pass_analysis': False
        }

        try:
            # Check protocol support
            result = subprocess.run(
                [tshark_path, '-G', 'protocols'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                protocols = result.stdout.lower()
                capabilities['tls_protocol_support'] = 'tls' in protocols and 'ssl' in protocols

            # Check JSON output support
            result = subprocess.run(
                [tshark_path, '-T', 'json', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            capabilities['json_output_support'] = result.returncode == 0

            # Check field extraction support
            result = subprocess.run(
                [tshark_path, '-G', 'fields'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                fields = result.stdout

                # Required fields for TLS marker functionality
                required_basic_fields = [
                    'frame.number', 'frame.protocols', 'frame.time_relative',
                    'tcp.stream', 'tcp.seq', 'tcp.seq_raw', 'tcp.len', 'tcp.payload'
                ]

                required_tls_fields = [
                    'tls.record.content_type', 'tls.record.opaque_type',
                    'tls.record.length', 'tls.record.version',
                    'tls.app_data', 'tls.segment.data'
                ]

                required_ip_fields = [
                    'ip.src', 'ip.dst', 'ipv6.src', 'ipv6.dst',
                    'tcp.srcport', 'tcp.dstport'
                ]

                all_required_fields = required_basic_fields + required_tls_fields + required_ip_fields

                capabilities['field_extraction_support'] = all(
                    field in fields for field in all_required_fields
                )

                # Specific TLS capabilities
                capabilities['tls_record_parsing'] = all(
                    field in fields for field in required_tls_fields[:4]  # Basic TLS record fields
                )

                capabilities['tls_app_data_extraction'] = 'tls.app_data' in fields
                capabilities['tcp_stream_tracking'] = 'tcp.stream' in fields

            # Check two-pass analysis support (-2 flag)
            result = subprocess.run(
                [tshark_path, '-2', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            capabilities['two_pass_analysis'] = result.returncode == 0

            # Check TCP reassembly support
            result = subprocess.run(
                [tshark_path, '-o', 'tcp.desegment_tcp_streams:TRUE', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            capabilities['tcp_reassembly_support'] = result.returncode == 0

        except Exception as e:
            self.logger.error(f"Error verifying TLS capabilities: {e}")

        return capabilities

    def verify_tls_marker_requirements(self, tshark_path: str) -> Tuple[bool, List[str]]:
        """Comprehensive verification of TLS marker requirements

        Args:
            tshark_path: Path to TShark executable

        Returns:
            Tuple of (all_requirements_met, list_of_missing_requirements)
        """
        capabilities = self.verify_tls_capabilities(tshark_path)

        # Critical requirements for TLS marker functionality
        critical_requirements = {
            'tls_protocol_support': 'TLS/SSL protocol support',
            'json_output_support': 'JSON output format support',
            'field_extraction_support': 'Required field extraction support',
            'tcp_reassembly_support': 'TCP stream reassembly support',
            'tls_record_parsing': 'TLS record parsing support',
            'tls_app_data_extraction': 'TLS application data extraction',
            'tcp_stream_tracking': 'TCP stream tracking support',
            'two_pass_analysis': 'Two-pass analysis support (-2 flag)'
        }

        missing_requirements = []
        for capability, description in critical_requirements.items():
            if not capabilities.get(capability, False):
                missing_requirements.append(description)

        all_requirements_met = len(missing_requirements) == 0

        if all_requirements_met:
            self.logger.info("All TLS marker requirements verified successfully")
        else:
            self.logger.warning(f"Missing TLS marker requirements: {missing_requirements}")

        return all_requirements_met, missing_requirements
    
    def get_tshark_info(self) -> Optional[TSharkInfo]:
        """Get cached TShark information
        
        Returns:
            Cached TShark information or None if not detected yet
        """
        return self._cached_info
    
    def set_custom_path(self, path: str) -> bool:
        """Set custom TShark path and verify it
        
        Args:
            path: Custom TShark executable path
            
        Returns:
            True if path is valid and TShark is usable
        """
        self.custom_path = path
        self._cached_info = None  # Clear cache
        
        info = self.detect_tshark(force_refresh=True)
        return info.is_available
