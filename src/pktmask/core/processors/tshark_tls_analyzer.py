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
        
        self.logger.info(f"Starting PCAP file analysis: {pcap_file}")
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
        
        records = []
        record_offset = 0
        
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
                
                # 简化的记录创建：所有记录都标记为完整，跨包检测由后续的长度检测处理
                spans_packets = [frame_number]
                is_complete = True

                self.logger.debug(f"🔍 [TLS记录解析] 包{frame_number}: 类型=TLS-{content_type}, 长度={record_length}字节, 字段来源={tls_field_source}")
                
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
        """基于记录长度的简化跨包检测

        Args:
            tls_records: 原始TLS记录列表

        Returns:
            增强的TLS记录列表，包含跨包检测结果
        """
        enhanced_records = []
        cross_packet_count = 0

        self.logger.info(f"🔍 [TLS跨包检测] 开始基于长度的跨包检测，共{len(tls_records)}个记录")

        for record in tls_records:
            if self._is_cross_packet_by_length(record):
                # 创建跨包版本
                spans = self._estimate_packet_spans(record)
                enhanced_record = TLSRecordInfo(
                    packet_number=record.packet_number,
                    content_type=record.content_type,
                    version=record.version,
                    length=record.length,
                    is_complete=True,
                    spans_packets=spans,
                    tcp_stream_id=record.tcp_stream_id,
                    record_offset=record.record_offset
                )
                enhanced_records.append(enhanced_record)
                cross_packet_count += 1

                self.logger.info(f"🔍 [TLS跨包检测] 检测到跨包记录：包{record.packet_number}, 类型=TLS-{record.content_type}, 长度={record.length}字节, 跨包{spans}")
            else:
                # 保持原记录
                enhanced_records.append(record)

        self.logger.info(f"🔍 [TLS跨包检测] 跨包检测完成：发现 {cross_packet_count} 个跨包记录")
        return enhanced_records

    def _is_cross_packet_by_length(self, record: TLSRecordInfo, threshold: int = 1200) -> bool:
        """基于记录长度判断是否跨包

        Args:
            record: TLS记录信息
            threshold: 跨包检测阈值（字节）

        Returns:
            是否为跨包记录
        """
        # TLS记录总大小 = 头部5字节 + 载荷长度
        total_size = record.length + 5

        # 考虑网络开销的保守阈值
        is_cross_packet = total_size > threshold

        if is_cross_packet:
            self.logger.debug(f"🔍 [长度检测] TLS-{record.content_type}记录总大小{total_size}字节 > 阈值{threshold}字节，判定为跨包")

        return is_cross_packet

    def _estimate_packet_spans(self, record: TLSRecordInfo, conservative_range: int = 20) -> List[int]:
        """保守的跨包记录包范围估算

        由于网络环境的复杂性（重传、间隔包、非连续分段等），精确估算跨包范围
        非常困难。因此采用保守策略：为大记录生成一个保守的包范围，确保不遗漏
        可能的分段包。

        Args:
            record: TLS记录信息
            conservative_range: 保守的向前搜索范围

        Returns:
            估算的包编号列表
        """
        total_size = record.length + 5

        # 基于记录大小确定保守范围
        if total_size <= 1500:
            # 小记录：可能跨2-3个包
            search_range = 5
        elif total_size <= 3000:
            # 中等记录：可能跨3-5个包
            search_range = 10
        else:
            # 大记录：可能跨更多包
            search_range = conservative_range

        # 向前搜索，生成保守的包范围
        start_packet = max(1, record.packet_number - search_range + 1)
        spans = list(range(start_packet, record.packet_number + 1))

        self.logger.debug(f"🔍 [保守包范围估算] TLS-{record.content_type}总大小{total_size}字节，"
                         f"保守搜索范围{search_range}，包范围{spans}")

        return spans

    def _detect_cross_packet_in_stream(self, records: List[TLSRecordInfo]) -> List[TLSRecordInfo]:
        """已废弃：旧的复杂跨包检测方法

        该方法已被基于长度的简化检测替代，保留仅为兼容性
        """
        self.logger.warning("调用了已废弃的_detect_cross_packet_in_stream方法，请使用新的基于长度的检测")
        return records


    
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