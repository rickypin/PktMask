"""
TShark TLS 分析器

基于TShark命令行工具的深度TLS协议分析器，支持跨TCP段TLS消息识别和新协议类型处理。
这是TSharkEnhancedMaskProcessor的核心组件之一。

功能特性：
1. 深度协议解析：识别跨TCP段TLS记录和新协议类型(20-24)
2. 性能优化：分阶段过滤，减少JSON输出体积
3. 依赖检查：验证TShark工具可用性和版本兼容性
4. 错误处理：完整的异常处理和降级机制
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ..trim.models.tls_models import TLSRecordInfo, TLSAnalysisResult


def get_tshark_paths() -> List[str]:
    """获取TShark可执行文件的搜索路径"""
    paths = []
    
    # Windows路径
    windows_paths = [
        r"C:\Program Files\Wireshark\tshark.exe",
        r"C:\Program Files (x86)\Wireshark\tshark.exe",
    ]
    
    # macOS路径
    macos_paths = [
        "/Applications/Wireshark.app/Contents/MacOS/tshark",
        "/usr/local/bin/tshark",
        "/opt/homebrew/bin/tshark",
    ]
    
    # Linux路径
    linux_paths = [
        "/usr/bin/tshark",
        "/usr/local/bin/tshark",
        "/opt/wireshark/bin/tshark",
    ]
    
    # 根据操作系统添加相应路径
    import platform
    system = platform.system().lower()
    
    if system == "windows":
        paths.extend(windows_paths)
    elif system == "darwin":  # macOS
        paths.extend(macos_paths)
    elif system == "linux":
        paths.extend(linux_paths)
    
    # 添加通用路径
    paths.extend(["/usr/bin/tshark", "/usr/local/bin/tshark"])
    
    return paths


class TSharkTLSAnalyzer:
    """基于TShark的TLS协议分析器
    
    使用TShark的深度协议解析能力，识别跨TCP段TLS消息和支持新协议类型。
    """
    
    # TShark最低版本要求
    MIN_TSHARK_VERSION = (4, 0, 0)
    
    # 支持的TLS协议类型
    SUPPORTED_TLS_TYPES = [20, 21, 22, 23, 24]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化TShark TLS分析器
        
        Args:
            config: 配置参数字典
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # TShark执行文件路径
        self._tshark_path: Optional[str] = None
        
        # 性能配置
        self._timeout_seconds = self.config.get('tshark_timeout_seconds', 300)
        self._max_memory_mb = self.config.get('tshark_max_memory_mb', 1024)
        self._temp_dir = self.config.get('temp_dir', None)
        
        # TShark配置
        self._enable_tcp_reassembly = self.config.get('enable_tcp_reassembly', True)
        self._enable_tls_desegment = self.config.get('enable_tls_desegment', True)
        self._custom_executable = self.config.get('tshark_custom_executable', None)
        self._executable_paths = self.config.get('tshark_executable_paths', get_tshark_paths())
        
        # 调试配置
        self._verbose = self.config.get('verbose', False)
    
    def initialize(self) -> bool:
        """初始化分析器
        
        Returns:
            初始化是否成功
        """
        try:
            # 查找TShark可执行文件
            self._tshark_path = self._find_tshark_executable()
            if not self._tshark_path:
                self.logger.error("未找到TShark可执行文件")
                return False
            
            # 验证TShark版本
            version = self._get_tshark_version()
            if not self._validate_tshark_version(version):
                return False
            
            # 验证TShark功能
            if not self._verify_tshark_capabilities():
                return False
            
            self.logger.info(f"TShark TLS分析器初始化成功: {self._tshark_path}, 版本: {version}")
            return True
            
        except Exception as e:
            self.logger.error(f"TShark TLS分析器初始化失败: {e}")
            return False
    
    def check_dependencies(self) -> bool:
        """检查依赖工具可用性
        
        Returns:
            依赖是否可用
        """
        return self._tshark_path is not None and Path(self._tshark_path).exists()
    
    def analyze_file(self, pcap_file) -> List[TLSRecordInfo]:
        """分析PCAP文件中的TLS记录
        
        Args:
            pcap_file: 输入PCAP文件路径（字符串或Path对象）
            
        Returns:
            识别的TLS记录列表
            
        Raises:
            RuntimeError: 分析失败时抛出
        """
        # 确保pcap_file是Path对象
        if isinstance(pcap_file, str):
            pcap_file = Path(pcap_file)
        elif not isinstance(pcap_file, Path):
            pcap_file = Path(str(pcap_file))
            
        if not self.check_dependencies():
            raise RuntimeError("TShark依赖不可用")
        
        if not pcap_file.exists():
            raise FileNotFoundError(f"PCAP文件不存在: {pcap_file}")
        
        self.logger.info(f"开始分析PCAP文件: {pcap_file}")
        start_time = time.time()
        
        try:
            # 构建TShark命令
            cmd = self._build_tshark_command(pcap_file)
            
            # 执行TShark分析
            json_output = self._execute_tshark_command(cmd)
            
            # 解析JSON输出
            tls_records = self._parse_tshark_output(json_output)
            
            # 检测跨TCP段TLS消息
            tls_records = self._detect_cross_packet_records(tls_records)
            
            analysis_time = time.time() - start_time
            self.logger.info(f"TLS分析完成: 识别{len(tls_records)}个TLS记录, 耗时{analysis_time:.2f}秒")
            
            return tls_records
            
        except Exception as e:
            self.logger.error(f"TLS分析失败: {e}")
            raise RuntimeError(f"TLS分析失败: {e}") from e
    
    def _find_tshark_executable(self) -> Optional[str]:
        """查找TShark可执行文件
        
        Returns:
            TShark可执行文件路径，如果未找到则返回None
        """
        # 首先检查配置中指定的自定义可执行文件路径
        if self._custom_executable and Path(self._custom_executable).exists():
            return self._custom_executable
        
        # 检查PATH环境变量
        tshark_in_path = shutil.which('tshark')
        if tshark_in_path:
            return tshark_in_path
        
        # 检查配置中的搜索路径
        for path in self._executable_paths:
            if Path(path).exists():
                return path
        
        return None
    
    def _get_tshark_version(self) -> Optional[Tuple[int, int, int]]:
        """获取TShark版本信息
        
        Returns:
            TShark版本元组 (major, minor, patch)，失败时返回None
        """
        try:
            result = subprocess.run(
                [self._tshark_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # 解析版本号 (例如: "TShark (Wireshark) 4.2.1")
                import re
                version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', result.stdout)
                if version_match:
                    return tuple(map(int, version_match.groups()))
            
            return None
            
        except Exception as e:
            self.logger.warning(f"获取TShark版本失败: {e}")
            return None
    
    def _validate_tshark_version(self, version: Optional[Tuple[int, int, int]]) -> bool:
        """验证TShark版本是否符合要求
        
        Args:
            version: TShark版本元组
            
        Returns:
            版本是否符合要求
        """
        if version is None:
            self.logger.error("无法获取TShark版本信息")
            return False
        
        if version < self.MIN_TSHARK_VERSION:
            min_ver_str = '.'.join(map(str, self.MIN_TSHARK_VERSION))
            curr_ver_str = '.'.join(map(str, version))
            self.logger.error(f"TShark版本过低: {curr_ver_str} < {min_ver_str}")
            return False
        
        return True
    
    def _verify_tshark_capabilities(self) -> bool:
        """验证TShark功能支持
        
        Returns:
            功能是否支持
        """
        try:
            # 检查是否支持所需的协议和选项
            result = subprocess.run(
                [self._tshark_path, '-G', 'protocols'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.logger.error("TShark协议检查失败")
                return False
            
            protocols = result.stdout.lower()
            
            # 检查TLS协议支持
            if 'tls' not in protocols and 'ssl' not in protocols:
                self.logger.error("TShark不支持TLS/SSL协议解析")
                return False
            
            # 检查TCP协议支持
            if 'tcp' not in protocols:
                self.logger.error("TShark不支持TCP协议解析") 
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"TShark功能验证失败: {e}")
            return False
    
    def _build_tshark_command(self, pcap_file: Path) -> List[str]:
        """构建TShark命令行
        
        Args:
            pcap_file: 输入PCAP文件
            
        Returns:
            TShark命令参数列表
        """
        cmd = [self._tshark_path]
        
        # 输入文件
        cmd.extend(['-r', str(pcap_file)])
        
        # 输出格式为JSON
        cmd.extend(['-T', 'json'])
        
        # 仅输出必要字段，减少JSON体积和提升性能
        fields = [
            'frame.number',           # 包编号
            'tcp.stream',             # TCP流ID
            'tcp.seq',                # TCP序列号
            'tcp.len',                # TCP载荷长度
            'tls.record.content_type', # TLS内容类型
            'tls.record.length',      # TLS记录长度
            'tls.record.opaque_type', # TLS不透明类型
            'tls.record.version',     # TLS版本
            'tls.app_data',           # TLS应用数据
            # 添加分段检测关键字段
            'tls.segment',            # TLS分段标识
            'tls.segment.count',      # TLS分段总数
            'tls.segment.data',       # TLS分段数据
            'tls.reassembled_in',     # 重组在哪个包中
            # 注意: tls.record.fragment 在TShark 4.4.7等版本中不存在，已移除以确保兼容性
            'tcp.segment',            # TCP分段标识
            'tcp.reassembled_in'      # TCP重组在哪个包中
        ]
        
        for field in fields:
            cmd.extend(['-e', field])
        
        # 展开所有出现的字段
        cmd.extend(['-E', 'occurrence=a'])
        
        # 协议选项
        prefs = []
        
        if self._enable_tcp_reassembly:
            prefs.append('tcp.desegment_tcp_streams:TRUE')
        
        if self._enable_tls_desegment:
            prefs.append('tls.desegment_ssl_records:TRUE')
        
        # 应用协议选项
        for pref in prefs:
            cmd.extend(['-o', pref])
        
        # 过滤器：只分析TLS包，提升性能
        cmd.extend(['-Y', 'tls'])
        
        # 静默模式
        if not self._verbose:
            cmd.append('-q')
        
        return cmd
    
    def _execute_tshark_command(self, cmd: List[str]) -> str:
        """执行TShark命令
        
        Args:
            cmd: TShark命令参数列表
            
        Returns:
            TShark的JSON输出
            
        Raises:
            RuntimeError: 执行失败时抛出
        """
        self.logger.debug(f"执行TShark命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds
            )
            
            if result.returncode != 0:
                error_msg = f"TShark执行失败 (退出码: {result.returncode})"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise RuntimeError(error_msg)
            
            if not result.stdout.strip():
                self.logger.warning("TShark输出为空，可能文件中没有TLS流量")
                return "[]"  # 返回空JSON数组
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"TShark执行超时 (>{self._timeout_seconds}秒)")
        except Exception as e:
            raise RuntimeError(f"TShark执行异常: {e}") from e
    
    def _parse_tshark_output(self, json_output: str) -> List[TLSRecordInfo]:
        """解析TShark的JSON输出
        
        Args:
            json_output: TShark的JSON输出字符串
            
        Returns:
            解析的TLS记录列表
        """
        try:
            packets = json.loads(json_output)
            tls_records = []
            
            for packet_data in packets:
                try:
                    records = self._parse_packet_tls_records(packet_data)
                    tls_records.extend(records)
                except Exception as e:
                    self.logger.warning(f"解析包TLS记录失败: {e}")
                    continue
            
            self.logger.debug(f"解析完成，识别{len(tls_records)}个TLS记录")
            return tls_records
            
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON解析失败: {e}") from e
        except Exception as e:
            raise RuntimeError(f"TShark输出解析失败: {e}") from e
    
    def _parse_packet_tls_records(self, packet_data: Dict) -> List[TLSRecordInfo]:
        """解析单个包的TLS记录
        
        Args:
            packet_data: 包的JSON数据
            
        Returns:
            该包中的TLS记录列表
        """
        layers = packet_data.get('_source', {}).get('layers', {})
        
        # 提取基本信息
        frame_number = self._extract_field_int(layers, 'frame.number', 0)
        tcp_stream = self._extract_field_str(layers, 'tcp.stream', '')
        tcp_seq = self._extract_field_int(layers, 'tcp.seq', 0)
        
        # 提取TLS信息 - 支持TLS 1.3的opaque_type和其他版本的content_type
        content_types = self._extract_field_list(layers, 'tls.record.content_type')
        opaque_types = self._extract_field_list(layers, 'tls.record.opaque_type')  # TLS 1.3专用字段
        record_lengths = self._extract_field_list(layers, 'tls.record.length')
        tls_versions = self._extract_field_list(layers, 'tls.record.version')
        
        # 提取关键的分段检测信息
        tls_reassembled_in = self._extract_field_list(layers, 'tls.reassembled_in')
        tcp_reassembled_in = self._extract_field_list(layers, 'tcp.reassembled_in')
        has_tls_segment = bool(self._extract_field_list(layers, 'tls.segment'))
        has_tcp_segment = bool(self._extract_field_list(layers, 'tcp.segment'))
        
        records = []
        record_offset = 0
        
        # 检查这个包是否是分段的一部分
        is_segment_packet = has_tls_segment or has_tcp_segment
        reassembled_in_packet = None
        
        # 确定重组目标包编号
        if tls_reassembled_in:
            try:
                reassembled_in_packet = int(tls_reassembled_in[0])
            except (ValueError, IndexError):
                pass
        elif tcp_reassembled_in:
            try:
                reassembled_in_packet = int(tcp_reassembled_in[0])
            except (ValueError, IndexError):
                pass
        
        # 如果这是一个分段包且不是重组目标包，则为分段创建记录
        if is_segment_packet and reassembled_in_packet and reassembled_in_packet != frame_number:
            # 这是一个分段包，创建分段记录
            self.logger.info(f"🔍 [TLS跨包分析] 检测到分段包 {frame_number} → 重组到包 {reassembled_in_packet}")
            self.logger.info(f"🔍 [TLS跨包分析] 包{frame_number} TLS分段信息: has_tls_segment={has_tls_segment}, has_tcp_segment={has_tcp_segment}")
            self.logger.info(f"🔍 [TLS跨包分析] 包{frame_number} 重组信息: tls_reassembled_in={tls_reassembled_in}, tcp_reassembled_in={tcp_reassembled_in}")
            
            # 为分段创建占位记录，标记需要被掩码但没有完整TLS信息
            segment_record = TLSRecordInfo(
                packet_number=frame_number,
                content_type=23,  # 假设是ApplicationData分段
                version=(3, 1),   # 默认版本
                length=0,         # 分段长度暂时为0
                is_complete=False,
                spans_packets=[frame_number, reassembled_in_packet],  # 包含原包和重组包
                tcp_stream_id=f"TCP_{tcp_stream}",
                record_offset=0
            )
            records.append(segment_record)
            self.logger.info(f"🔍 [TLS跨包分析] 为分段包{frame_number}创建占位记录: content_type=23, spans_packets={segment_record.spans_packets}")
            return records
        
        # 确定最大记录数 - 基于所有TLS字段的最大长度
        max_records = max(len(content_types), len(opaque_types), len(record_lengths), len(tls_versions)) if any([content_types, opaque_types, record_lengths, tls_versions]) else 0
        
        # 处理正常的TLS记录（包括重组后的完整记录）
        # 合并并按顺序排列TLS类型字段
        all_tls_types = []
        
        # 先添加content_types的记录
        for j, content_type in enumerate(content_types):
            if content_type:
                all_tls_types.append((content_type, f"content_type[{j}] (TLS ≤1.2)"))
        
        # 再添加opaque_types的记录  
        for j, opaque_type in enumerate(opaque_types):
            if opaque_type:
                all_tls_types.append((opaque_type, f"opaque_type[{j}] (TLS 1.3)"))
        
        # 处理合并后的TLS记录
        for i in range(min(len(all_tls_types), len(record_lengths))):
            tls_type_str, tls_field_source = all_tls_types[i] if i < len(all_tls_types) else (None, "none")
            
            # 如果没有有效的TLS类型字段，跳过这个记录
            if not tls_type_str:
                self.logger.debug(f"TLS记录{i}没有有效的类型字段，跳过")
                continue
            
            self.logger.debug(f"TLS记录{i}使用{tls_field_source}: {tls_type_str}")
            try:
                content_type = int(tls_type_str, 0)  # 支持十六进制
                
                # 验证协议类型
                if content_type not in self.SUPPORTED_TLS_TYPES:
                    self.logger.debug(f"跳过不支持的TLS类型: {content_type}")
                    continue
                
                # 提取记录长度
                record_length = 0
                if i < len(record_lengths):
                    record_length = int(record_lengths[i], 0)
                
                # 提取TLS版本
                version = (3, 1)  # 默认TLS 1.0
                if i < len(tls_versions):
                    try:
                        version_int = int(tls_versions[i], 0)
                        major = (version_int >> 8) & 0xFF
                        minor = version_int & 0xFF
                        version = (major, minor)
                    except ValueError:
                        pass
                
                # 确定跨段信息
                spans_packets = [frame_number]
                is_complete = True
                
                # 如果这个包是重组目标，可能需要标记跨段信息
                if is_segment_packet or reassembled_in_packet == frame_number:
                    # 这是一个重组后的记录，标记为跨包
                    is_complete = True  # TShark已经重组完成
                    # spans_packets 会在后续的 _detect_cross_packet_records 中更新
                    
                    self.logger.info(f"🔍 [TLS跨包分析] 包{frame_number}包含重组的TLS记录: 类型={content_type}, 长度={record_length}, 字段来源={tls_field_source}")
                    if content_type == 23:
                        self.logger.info(f"🔍 [TLS-23跨包] 重组包{frame_number}: ApplicationData长度={record_length}, 字段来源={tls_field_source}, 需要智能掩码处理")
                
                # 创建TLS记录信息
                record = TLSRecordInfo(
                    packet_number=frame_number,
                    content_type=content_type,
                    version=version,
                    length=record_length,
                    is_complete=is_complete,
                    spans_packets=spans_packets,
                    tcp_stream_id=f"TCP_{tcp_stream}",
                    record_offset=record_offset
                )
                
                records.append(record)
                record_offset += 5 + record_length  # TLS头部5字节 + 记录长度
                
            except (ValueError, TypeError) as e:
                self.logger.warning(f"解析TLS记录失败: {e}")
                continue
        
        return records
    
    def _extract_field_int(self, layers: Dict, field_name: str, default: int = 0) -> int:
        """从layers中提取整数字段
        
        Args:
            layers: 包的layers数据
            field_name: 字段名
            default: 默认值
            
        Returns:
            字段的整数值
        """
        try:
            value = layers.get(field_name)
            if value is None:
                return default
            
            if isinstance(value, list) and value:
                value = value[0]
            
            if isinstance(value, str):
                return int(value, 0)  # 支持十六进制
            elif isinstance(value, int):
                return value
            else:
                return default
                
        except (ValueError, TypeError):
            return default
    
    def _extract_field_str(self, layers: Dict, field_name: str, default: str = '') -> str:
        """从layers中提取字符串字段
        
        Args:
            layers: 包的layers数据
            field_name: 字段名
            default: 默认值
            
        Returns:
            字段的字符串值
        """
        try:
            value = layers.get(field_name)
            if value is None:
                return default
            
            if isinstance(value, list) and value:
                value = value[0]
            
            return str(value)
            
        except (ValueError, TypeError):
            return default
    
    def _extract_field_list(self, layers: Dict, field_name: str) -> List[str]:
        """从layers中提取列表字段
        
        Args:
            layers: 包的layers数据
            field_name: 字段名
            
        Returns:
            字段的列表值
        """
        try:
            value = layers.get(field_name)
            if value is None:
                return []
            
            if isinstance(value, list):
                return [str(v) for v in value]
            else:
                return [str(value)]
                
        except (ValueError, TypeError):
            return []
    
    def _detect_cross_packet_records(self, tls_records: List[TLSRecordInfo]) -> List[TLSRecordInfo]:
        """检测跨TCP段的TLS记录
        
        Args:
            tls_records: 原始TLS记录列表
            
        Returns:
            增强的TLS记录列表，包含跨段检测结果
        """
        # 按TCP流分组
        stream_records = {}
        for record in tls_records:
            stream_id = record.tcp_stream_id
            if stream_id not in stream_records:
                stream_records[stream_id] = []
            stream_records[stream_id].append(record)
        
        enhanced_records = []
        
        # 对每个流进行跨段检测
        for stream_id, records in stream_records.items():
            # 按包编号排序
            records.sort(key=lambda r: r.packet_number)
            
            # 检测跨段记录
            enhanced_stream_records = self._detect_cross_packet_in_stream(records)
            enhanced_records.extend(enhanced_stream_records)
        
        return enhanced_records
    
    def _detect_cross_packet_in_stream(self, records: List[TLSRecordInfo]) -> List[TLSRecordInfo]:
        """在单个流中检测跨段TLS记录
        
        基于TShark的重组信息和TLS记录长度分析，检测跨TCP段的TLS记录
        
        Args:
            records: 单个流的TLS记录列表
            
        Returns:
            增强的TLS记录列表，包含跨段信息
        """
        enhanced_records = []
        segment_map = {}  # reassembled_packet -> [segment_packets]
        large_records = {}  # packet -> large_record_info
        
        # 第一遍：收集分段信息和大记录信息
        for record in records:
            # 检查显式分段记录
            if not record.is_complete and len(record.spans_packets) > 1:
                # 这是一个分段记录
                segment_packet = record.spans_packets[0]
                reassembled_packet = record.spans_packets[1]
                
                if reassembled_packet not in segment_map:
                    segment_map[reassembled_packet] = []
                segment_map[reassembled_packet].append(segment_packet)
                
                self.logger.info(f"🔍 [TLS跨包检测] 显式分段记录：包{segment_packet} → 重组到包{reassembled_packet}, 类型={record.content_type}")
                if record.content_type == 23:
                    self.logger.info(f"🔍 [TLS-23跨包] 发现ApplicationData分段：包{segment_packet}将在包{reassembled_packet}中重组")
            
            # 增强的大记录检测（针对ApplicationData）
            elif record.is_complete and record.content_type == 23:
                # ApplicationData记录，使用更精确的跨包检测标准
                typical_mtu_payload = 1460  # 典型的以太网MTU减去IP/TCP头部
                tcp_overhead = 60  # TCP头部和选项的最大开销
                effective_payload_limit = typical_mtu_payload - tcp_overhead  # ~1400字节
                
                # 多级检测标准
                is_definitely_cross_packet = record.length > typical_mtu_payload  # >1460字节
                is_probably_cross_packet = record.length > effective_payload_limit  # >1400字节
                is_possibly_cross_packet = record.length > 1200  # 保守估计
                
                if is_definitely_cross_packet or is_probably_cross_packet:
                    large_records[record.packet_number] = record
                    confidence = "确定" if is_definitely_cross_packet else "很可能" if is_probably_cross_packet else "可能"
                    self.logger.info(f"🔍 [TLS跨包检测] 检测到大ApplicationData记录：包{record.packet_number}, 长度={record.length}字节, {confidence}跨包")
                    self.logger.info(f"🔍 [TLS-23跨包] 大消息体检测：包{record.packet_number}, ApplicationData长度={record.length}, 需要分段掩码处理")
        
        # 第二遍：为大记录推断跨包信息，使用增强的检测算法
        packets_by_number = {r.packet_number: r for r in records}
        tcp_segments_analysis = self._analyze_tcp_segments_for_cross_packet(records)
        
        for packet_num, large_record in large_records.items():
            # 查找可能的前置包（分段包）
            segment_packets = []
            
            # 方法1：查找前面的包，看是否有指向当前包的重组信息
            for check_packet in range(max(1, packet_num - 15), packet_num):  # 扩大搜索范围
                if check_packet in packets_by_number:
                    check_record = packets_by_number[check_packet]
                    # 如果是不完整记录且有重组信息，可能是分段
                    if (not check_record.is_complete and 
                        len(check_record.spans_packets) > 1 and 
                        check_record.spans_packets[1] == packet_num):
                        segment_packets.append(check_packet)
            
            # 方法2：基于TCP序列号连续性分析（如果有相关信息）
            if packet_num in tcp_segments_analysis:
                additional_segments = tcp_segments_analysis[packet_num]
                segment_packets.extend(additional_segments)
                segment_packets = sorted(list(set(segment_packets)))  # 去重排序
            
            # 方法3：基于数据包时间间隔和载荷大小的启发式分析
            if not segment_packets:
                heuristic_segments = self._heuristic_segment_detection(
                    large_record, packets_by_number, packet_num
                )
                segment_packets.extend(heuristic_segments)
            
            # 如果找到分段包，则这是跨包记录
            if segment_packets:
                if packet_num not in segment_map:
                    segment_map[packet_num] = []
                segment_map[packet_num].extend(segment_packets)
                segment_map[packet_num] = sorted(list(set(segment_map[packet_num])))  # 去重排序
                self.logger.info(f"🔍 [TLS跨包检测] 基于多方法推断跨包：包{packet_num}, 前置分段={segment_map[packet_num]}")
                self.logger.info(f"🔍 [TLS-23跨包] 推断ApplicationData跨包：包{packet_num}, 跨包={segment_map[packet_num] + [packet_num]}, 总长度={large_record.length}")
            else:
                # 没有明确的分段包，但仍然是大记录，基于长度进行保守估算
                if large_record.length > 1460:  # 使用更严格的阈值
                    # 估算可能的分段包数量，基于典型MTU
                    estimated_segments = (large_record.length // 1400) + 1
                    estimated_start = max(1, packet_num - estimated_segments + 1)
                    
                    # 验证估算范围内是否有合适的候选包
                    valid_candidates = []
                    for candidate in range(estimated_start, packet_num):
                        if candidate in packets_by_number:
                            candidate_record = packets_by_number[candidate]
                            # 检查是否是同一TCP流且时间接近
                            if (candidate_record.tcp_stream_id == large_record.tcp_stream_id and
                                abs(candidate - packet_num) <= estimated_segments):
                                valid_candidates.append(candidate)
                    
                    if valid_candidates:
                        segment_map[packet_num] = valid_candidates
                        estimated_spans = valid_candidates + [packet_num]
                        self.logger.info(f"🔍 [TLS跨包检测] 估算跨包记录：包{packet_num}, 估算跨包={estimated_spans}, 基于长度{large_record.length}")
                        self.logger.info(f"🔍 [TLS-23跨包] 估算ApplicationData跨包：长度={large_record.length}字节, 估算需要{len(estimated_spans)}个包")
        
        # 第三遍：生成增强记录
        for record in records:
            if record.is_complete:
                # 检查这是否是一个重组目标包
                if record.packet_number in segment_map:
                    # 这是重组后的完整记录，更新spans_packets
                    all_spans = segment_map[record.packet_number] + [record.packet_number]
                    all_spans = sorted(list(set(all_spans)))  # 去重并排序
                    
                    enhanced_record = TLSRecordInfo(
                        packet_number=record.packet_number,
                        content_type=record.content_type,
                        version=record.version,
                        length=record.length,
                        is_complete=True,
                        spans_packets=all_spans,  # 包含所有相关的包
                        tcp_stream_id=record.tcp_stream_id,
                        record_offset=record.record_offset
                    )
                    
                    enhanced_records.append(enhanced_record)
                    
                    self.logger.info(f"🔍 [TLS跨包检测] 跨包记录创建完成：类型{record.content_type}, 跨包{all_spans}, 总长度{record.length}")
                    if record.content_type == 23:
                        self.logger.info(f"🔍 [TLS-23跨包] ApplicationData跨包记录：跨包{all_spans}, 消息体长度={record.length}, 需要分段掩码")
                else:
                    # 普通的单包记录
                    enhanced_records.append(record)
            # 分段记录不添加到最终结果中，因为它们已经合并到重组记录中
        
        cross_packet_count = sum(1 for r in enhanced_records if len(r.spans_packets) > 1)
        self.logger.info(f"🔍 [TLS跨包检测] 跨包检测完成：发现 {cross_packet_count} 个跨包记录")
        
        return enhanced_records
    
    def _analyze_tcp_segments_for_cross_packet(self, records: List[TLSRecordInfo]) -> Dict[int, List[int]]:
        """分析TCP段以检测跨包TLS记录
        
        Args:
            records: TLS记录列表
            
        Returns:
            包编号到前置分段包列表的映射
        """
        # 按包编号排序记录
        sorted_records = sorted(records, key=lambda r: r.packet_number)
        segment_analysis = {}
        
        # 分析相邻记录之间的关系
        for i in range(1, len(sorted_records)):
            current = sorted_records[i]
            previous = sorted_records[i-1]
            
            # 只分析ApplicationData记录
            if current.content_type != 23:
                continue
            
            # 检查是否在同一TCP流中
            if current.tcp_stream_id != previous.tcp_stream_id:
                continue
            
            # 检查包编号是否连续或接近
            packet_gap = current.packet_number - previous.packet_number
            if packet_gap > 10:  # 包间隔太大，不太可能是分段
                continue
            
            # 检查记录特征
            if (current.is_complete and current.length > 1400 and  # 当前是大记录
                (not previous.is_complete or previous.length < 1400)):  # 前一个是小记录或不完整
                # 可能的分段关系
                if current.packet_number not in segment_analysis:
                    segment_analysis[current.packet_number] = []
                segment_analysis[current.packet_number].append(previous.packet_number)
        
        return segment_analysis
    
    def _heuristic_segment_detection(
        self, 
        large_record: TLSRecordInfo, 
        packets_by_number: Dict[int, TLSRecordInfo],
        target_packet: int
    ) -> List[int]:
        """启发式分段检测
        
        Args:
            large_record: 大记录
            packets_by_number: 包编号到记录的映射
            target_packet: 目标包编号
            
        Returns:
            可能的分段包列表
        """
        candidates = []
        
        # 搜索范围：基于记录大小估算
        max_segments = min(10, (large_record.length // 1200) + 3)
        search_start = max(1, target_packet - max_segments)
        
        for packet_num in range(search_start, target_packet):
            if packet_num in packets_by_number:
                candidate = packets_by_number[packet_num]
                
                # 检查基本条件
                if (candidate.tcp_stream_id == large_record.tcp_stream_id and
                    candidate.content_type == 23):  # 同流的ApplicationData
                    
                    # 启发式条件：小记录或不完整记录
                    if (not candidate.is_complete or 
                        candidate.length < 1200 or
                        len(candidate.spans_packets) <= 1):
                        candidates.append(packet_num)
        
        # 返回最多5个最接近的候选包
        return candidates[-5:] if candidates else []
    
    def get_analysis_result(self, tls_records: List[TLSRecordInfo], total_packets: int) -> TLSAnalysisResult:
        """生成TLS分析结果
        
        Args:
            tls_records: TLS记录列表
            total_packets: 总包数
            
        Returns:
            TLS分析结果
        """
        cross_packet_records = [r for r in tls_records if r.is_cross_packet]
        
        return TLSAnalysisResult(
            total_packets=total_packets,
            tls_packets=len(set(r.packet_number for r in tls_records)),
            tls_records=tls_records,
            cross_packet_records=cross_packet_records,
            analysis_errors=[]
        ) 