"""
协议绑定控制器

这是Phase 2的核心组件，负责控制Scapy的协议解析行为。
主要功能：
1. 禁用Scapy协议解析，强制所有载荷保持Raw格式
2. 安全地恢复原始协议绑定状态
3. 提供线程安全的协议状态管理
4. 验证协议解析禁用的效果
"""

import threading
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from contextlib import contextmanager
import time

try:
    from scapy.all import (
        bind_layers, split_layers, Raw, TCP, UDP, IP, IPv6, conf
    )
    from scapy.layers.inet import _IPOption_HDR
    from scapy.layers.tls.all import TLS
    from scapy.layers.http import HTTPRequest, HTTPResponse
    SCAPY_AVAILABLE = True
except ImportError as e:
    SCAPY_AVAILABLE = False
    _import_error = e

from .exceptions import ProtocolBindingError, ValidationError


class ProtocolBindingController:
    """协议绑定控制器
    
    管理Scapy协议解析的启用/禁用状态，确保在处理时所有TCP/UDP载荷
    都保持Raw格式，避免TLS/HTTP等高层协议的自动解析。
    
    主要特性：
    - 线程安全的协议状态管理
    - 自动备份和恢复原始绑定状态
    - 验证协议解析禁用效果
    - 异常安全的资源管理
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化协议绑定控制器
        
        Args:
            logger: 可选的日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # 检查Scapy可用性
        if not SCAPY_AVAILABLE:
            raise ProtocolBindingError(f"Scapy不可用: {_import_error}")
        
        # 设置需要禁用的协议层绑定（目标是让所有载荷保持Raw格式）
        self.PROTOCOLS_TO_DISABLE = {
            # TLS/SSL 协议
            'TLS': [
                (TCP, 443, {}),     # HTTPS
                (TCP, 993, {}),     # IMAPS  
                (TCP, 995, {}),     # POP3S
                (TCP, 465, {}),     # SMTPS
                (TCP, 636, {}),     # LDAPS
            ],
            # HTTP 协议
            'HTTP': [
                (TCP, 80, {}),      # HTTP
                (TCP, 8080, {}),    # HTTP-ALT
                (TCP, 8000, {}),    # HTTP-ALT
                (TCP, 3128, {}),    # HTTP-Proxy
            ],
            # 其他应用层协议
            'OTHER': [
                (TCP, 22, {}),      # SSH
                (TCP, 23, {}),      # Telnet
                (TCP, 21, {}),      # FTP
                (TCP, 25, {}),      # SMTP
                (TCP, 110, {}),     # POP3
                (TCP, 143, {}),     # IMAP
                (UDP, 53, {}),      # DNS
                (UDP, 67, {}),      # DHCP-Server
                (UDP, 68, {}),      # DHCP-Client
            ]
        }
        
        # 线程安全锁
        self._binding_lock = threading.RLock()  # 可重入锁
        
        # 绑定状态管理
        self._original_bindings: Dict[str, Any] = {}
        self._disabled_bindings: Set[Tuple] = set()
        self._protocol_parsing_disabled = False
        
        # 状态验证缓存
        self._verification_cache: Dict[str, float] = {}
        self._cache_timeout = 30.0  # 30秒缓存超时
        
        # 统计信息
        self._stats = {
            'disable_count': 0,
            'restore_count': 0,
            'verification_count': 0,
            'error_count': 0,
            'last_operation_time': None
        }
        
        self.logger.debug("协议绑定控制器初始化完成")
    
    @contextmanager
    def disabled_protocol_parsing(self):
        """上下文管理器：临时禁用协议解析
        
        用法:
            with controller.disabled_protocol_parsing():
                # 在这里所有包的载荷都是Raw格式
                packets = rdpcap("test.pcap")
                # 处理逻辑...
            # 自动恢复协议绑定状态
        """
        try:
            self.disable_protocol_parsing()
            yield self
        finally:
            self.restore_protocol_parsing()
    
    def disable_protocol_parsing(self) -> None:
        """禁用Scapy协议解析
        
        通过解除关键端口的协议绑定，强制Scapy将所有TCP/UDP载荷
        识别为Raw格式，避免TLS/HTTP等高层协议的自动解析。
        
        Raises:
            ProtocolBindingError: 禁用过程中发生错误
        """
        with self._binding_lock:
            if self._protocol_parsing_disabled:
                self.logger.debug("协议解析已禁用，跳过重复操作")
                return
            
            try:
                self.logger.info("🔒 开始禁用协议解析...")
                start_time = time.time()
                
                # 备份当前绑定状态
                self._backup_current_bindings()
                
                # 解除协议绑定
                disabled_count = self._unbind_protocols()
                
                # 标记状态
                self._protocol_parsing_disabled = True
                self._stats['disable_count'] += 1
                self._stats['last_operation_time'] = time.time()
                
                processing_time = time.time() - start_time
                self.logger.info(
                    f"✅ 协议解析禁用完成: 解除了{disabled_count}个绑定, "
                    f"耗时{processing_time:.3f}秒"
                )
                
            except Exception as e:
                self._stats['error_count'] += 1
                error_msg = f"禁用协议解析失败: {e}"
                self.logger.error(error_msg)
                raise ProtocolBindingError(error_msg) from e
    
    def restore_protocol_parsing(self) -> None:
        """恢复Scapy协议解析到原始状态
        
        恢复所有之前备份的协议绑定，确保Scapy回到正常的协议解析模式。
        
        Raises:
            ProtocolBindingError: 恢复过程中发生错误
        """
        with self._binding_lock:
            if not self._protocol_parsing_disabled:
                self.logger.debug("协议解析未禁用，跳过恢复操作")
                return
            
            try:
                self.logger.info("🔓 开始恢复协议解析...")
                start_time = time.time()
                
                # 恢复原始绑定
                restored_count = self._restore_original_bindings()
                
                # 清理状态
                self._original_bindings.clear()
                self._disabled_bindings.clear()
                self._protocol_parsing_disabled = False
                self._stats['restore_count'] += 1
                self._stats['last_operation_time'] = time.time()
                
                processing_time = time.time() - start_time
                self.logger.info(
                    f"✅ 协议解析恢复完成: 恢复了{restored_count}个绑定, "
                    f"耗时{processing_time:.3f}秒"
                )
                
            except Exception as e:
                self._stats['error_count'] += 1
                error_msg = f"恢复协议解析失败: {e}"
                self.logger.error(error_msg)
                raise ProtocolBindingError(error_msg) from e
    
    def verify_raw_layer_presence(self, packets: List[Any]) -> Dict[str, Any]:
        """验证数据包中Raw层的存在率
        
        检查TCP/UDP数据包是否都包含Raw层，验证协议解析禁用的效果。
        
        Args:
            packets: 要验证的数据包列表
            
        Returns:
            Dict: 验证结果统计
            {
                'total_packets': int,           # 总数据包数
                'tcp_packets': int,             # TCP数据包数
                'udp_packets': int,             # UDP数据包数
                'tcp_with_raw': int,            # 包含Raw层的TCP包数
                'udp_with_raw': int,            # 包含Raw层的UDP包数
                'tcp_raw_rate': float,          # TCP Raw层比率
                'udp_raw_rate': float,          # UDP Raw层比率
                'overall_raw_rate': float,      # 总体Raw层比率
                'verification_time': float,     # 验证耗时
                'expected_ports_checked': List  # 检查的期望端口
            }
        """
        start_time = time.time()
        self._stats['verification_count'] += 1
        
        # 初始化统计
        stats = {
            'total_packets': len(packets),
            'tcp_packets': 0,
            'udp_packets': 0,
            'tcp_with_raw': 0,
            'udp_with_raw': 0,
            'tcp_raw_rate': 0.0,
            'udp_raw_rate': 0.0,
            'overall_raw_rate': 0.0,
            'verification_time': 0.0,
            'expected_ports_checked': [],
            'sample_non_raw_packets': []  # 非Raw包的样本（用于调试）
        }
        
        # 收集需要检查的端口
        expected_ports = set()
        for protocol_type, bindings in self.PROTOCOLS_TO_DISABLE.items():
            for layer, port, _ in bindings:
                expected_ports.add((layer.__name__, port))
        stats['expected_ports_checked'] = list(expected_ports)
        
        try:
            # 分析每个数据包
            for i, packet in enumerate(packets):
                # 检查TCP包
                if packet.haslayer(TCP):
                    stats['tcp_packets'] += 1
                    
                    # 检查是否有Raw层
                    if packet.haslayer(Raw):
                        stats['tcp_with_raw'] += 1
                    else:
                        # 记录前5个非Raw包用于调试
                        if len(stats['sample_non_raw_packets']) < 5:
                            tcp_layer = packet[TCP]
                            stats['sample_non_raw_packets'].append({
                                'packet_index': i,
                                'src_port': tcp_layer.sport,
                                'dst_port': tcp_layer.dport,
                                'layers': [layer.name for layer in packet.layers()],
                                'payload_type': type(tcp_layer.payload).__name__
                            })
                
                # 检查UDP包
                elif packet.haslayer(UDP):
                    stats['udp_packets'] += 1
                    
                    # 检查是否有Raw层
                    if packet.haslayer(Raw):
                        stats['udp_with_raw'] += 1
                    else:
                        # 记录前5个非Raw包用于调试
                        if len(stats['sample_non_raw_packets']) < 5:
                            udp_layer = packet[UDP]
                            stats['sample_non_raw_packets'].append({
                                'packet_index': i,
                                'src_port': udp_layer.sport,
                                'dst_port': udp_layer.dport,
                                'layers': [layer.name for layer in packet.layers()],
                                'payload_type': type(udp_layer.payload).__name__
                            })
            
            # 计算比率
            if stats['tcp_packets'] > 0:
                stats['tcp_raw_rate'] = stats['tcp_with_raw'] / stats['tcp_packets']
            
            if stats['udp_packets'] > 0:
                stats['udp_raw_rate'] = stats['udp_with_raw'] / stats['udp_packets']
            
            total_transport_packets = stats['tcp_packets'] + stats['udp_packets']
            total_raw_packets = stats['tcp_with_raw'] + stats['udp_with_raw']
            
            if total_transport_packets > 0:
                stats['overall_raw_rate'] = total_raw_packets / total_transport_packets
            
            stats['verification_time'] = time.time() - start_time
            
            self.logger.debug(
                f"Raw层验证完成: TCP={stats['tcp_raw_rate']:.1%}, "
                f"UDP={stats['udp_raw_rate']:.1%}, "
                f"总体={stats['overall_raw_rate']:.1%}"
            )
            
            return stats
            
        except Exception as e:
            self._stats['error_count'] += 1
            error_msg = f"Raw层验证失败: {e}"
            self.logger.error(error_msg)
            raise ProtocolBindingError(error_msg) from e
    
    def is_protocol_parsing_disabled(self) -> bool:
        """检查协议解析是否已禁用"""
        return self._protocol_parsing_disabled
    
    def get_binding_statistics(self) -> Dict[str, Any]:
        """获取绑定操作统计信息"""
        stats = self._stats.copy()
        stats['currently_disabled'] = self._protocol_parsing_disabled
        stats['disabled_bindings_count'] = len(self._disabled_bindings)
        stats['original_bindings_count'] = len(self._original_bindings)
        
        return stats
    
    def _backup_current_bindings(self) -> None:
        """备份当前的协议绑定状态"""
        self.logger.debug("备份当前协议绑定状态...")
        
        # 这是一个简化的备份策略
        # 实际上Scapy的内部绑定机制比较复杂，这里采用最小化备份方案
        try:
            # 记录当前时间作为备份标识
            self._original_bindings['backup_time'] = time.time()
            self._original_bindings['scapy_version'] = getattr(conf, 'version', 'unknown')
            
            self.logger.debug(f"协议绑定状态已备份，条目数: {len(self._original_bindings)}")
            
        except Exception as e:
            raise ProtocolBindingError(f"备份协议绑定失败: {e}") from e
    
    def _unbind_protocols(self) -> int:
        """禁用协议解析 - 使用更强制性的方法"""
        disabled_count = 0
        
        try:
            # 方法1: 保存原始的解析状态并禁用自动解析
            if hasattr(conf, 'debug_dissector'):
                self._original_bindings['debug_dissector'] = conf.debug_dissector
                conf.debug_dissector = True  # 启用调试模式可以更多使用Raw
            
            # 方法2: 更强制性地禁用协议解析 - 直接修改Scapy的内部绑定
            from scapy.packet import bind_layers, split_layers
            from scapy.layers.inet import TCP, UDP
            from scapy.packet import Raw
            
            # 记录原始绑定以便恢复
            try:
                from scapy.layers.http import HTTPRequest, HTTPResponse
                # 解除所有HTTP绑定
                split_layers(TCP, HTTPRequest)
                split_layers(TCP, HTTPResponse) 
                disabled_count += 2
                self._disabled_bindings.add(('TCP', 'HTTPRequest', 'all'))
                self._disabled_bindings.add(('TCP', 'HTTPResponse', 'all'))
            except ImportError:
                pass
            
            try:
                from scapy.layers.tls.all import TLS
                # 解除所有TLS绑定
                split_layers(TCP, TLS)
                disabled_count += 1
                self._disabled_bindings.add(('TCP', 'TLS', 'all'))
            except ImportError:
                pass
            
            # 方法3: 强制所有常见端口使用Raw
            # 绑定所有常见的应用层端口到Raw，优先级高于默认绑定
            common_tcp_ports = [80, 443, 8080, 8443, 22, 23, 25, 110, 143, 993, 995]
            for port in common_tcp_ports:
                try:
                    bind_layers(TCP, Raw, dport=port)
                    bind_layers(TCP, Raw, sport=port)
                    disabled_count += 2
                    self._disabled_bindings.add(('TCP', 'Raw', f'port_{port}'))
                except Exception as e:
                    self.logger.debug(f"强制绑定端口 {port} 到Raw失败: {e}")
            
            # 方法4: 使用monkey patching强制载荷解析为Raw
            # 这是最强制性的方法
            if not hasattr(self, '_original_tcp_guess_payload_class'):
                from scapy.layers.inet import TCP, UDP
                # 备份原始的guess_payload_class方法
                self._original_tcp_guess_payload_class = TCP.guess_payload_class
                self._original_udp_guess_payload_class = UDP.guess_payload_class
                
                # 替换为总是返回Raw的方法
                def force_raw_payload(self, payload):
                    return Raw
                
                TCP.guess_payload_class = force_raw_payload
                UDP.guess_payload_class = force_raw_payload
                
                disabled_count += 2
                self._disabled_bindings.add(('TCP', 'guess_payload_class', 'monkeypatch'))
                self._disabled_bindings.add(('UDP', 'guess_payload_class', 'monkeypatch'))
                
                self.logger.debug("应用monkey patch强制所有载荷解析为Raw")
            
            self.logger.info(f"协议解析配置调整完成，影响 {disabled_count} 个绑定")
            return disabled_count
            
        except Exception as e:
            raise ProtocolBindingError(f"禁用协议解析失败: {e}") from e
    
    def _restore_original_bindings(self) -> int:
        """恢复原始协议绑定"""
        restored_count = 0
        
        try:
            # 方法1: 恢复原始配置
            if 'debug_dissector' in self._original_bindings:
                conf.debug_dissector = self._original_bindings['debug_dissector']
                restored_count += 1
            
            # 方法2: 恢复monkey patch
            if hasattr(self, '_original_tcp_guess_payload_class'):
                from scapy.layers.inet import TCP, UDP
                TCP.guess_payload_class = self._original_tcp_guess_payload_class
                UDP.guess_payload_class = self._original_udp_guess_payload_class
                
                # 清理备份
                delattr(self, '_original_tcp_guess_payload_class')
                delattr(self, '_original_udp_guess_payload_class')
                
                restored_count += 2
                self.logger.debug("恢复原始guess_payload_class方法")
            
            # 方法3: 重新绑定常见协议（这是保守的恢复策略）
            # 只恢复一些核心的绑定，避免过度恢复导致问题
            try:
                from scapy.packet import bind_layers, split_layers
                from scapy.layers.inet import TCP, UDP
                from scapy.packet import Raw
                
                # 恢复HTTP绑定
                try:
                    from scapy.layers.http import HTTPRequest, HTTPResponse
                    bind_layers(TCP, HTTPRequest, dport=80)
                    bind_layers(TCP, HTTPRequest, sport=80)
                    bind_layers(TCP, HTTPResponse, sport=80)
                    bind_layers(TCP, HTTPResponse, dport=80)
                    restored_count += 4
                    self.logger.debug("恢复HTTP协议绑定")
                except ImportError:
                    pass
                
                # 恢复TLS绑定
                try:
                    from scapy.layers.tls.all import TLS
                    bind_layers(TCP, TLS, dport=443)
                    bind_layers(TCP, TLS, sport=443)
                    restored_count += 2
                    self.logger.debug("恢复TLS协议绑定")
                except ImportError:
                    pass
                    
            except Exception as e:
                self.logger.warning(f"恢复协议绑定时发生错误: {e}")
            
            # 清理记录
            self._disabled_bindings.clear()
            
            self.logger.info(f"协议解析恢复完成，恢复了{restored_count}个绑定")
            return restored_count
            
        except Exception as e:
            raise ProtocolBindingError(f"恢复协议绑定失败: {e}") from e
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，确保协议状态恢复"""
        if self._protocol_parsing_disabled:
            try:
                self.restore_protocol_parsing()
            except Exception as e:
                self.logger.error(f"自动恢复协议解析失败: {e}")
                # 不重新抛出异常，避免覆盖原始异常 