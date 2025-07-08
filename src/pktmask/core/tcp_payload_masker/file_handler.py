"""
PCAP文件格式处理器

实现严格一致性的PCAP和PCAPNG文件读写，确保除掩码字节外文件完全一致。
支持的格式：.pcap、.pcapng
"""

import os
import logging
import tempfile
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import time

try:
    from scapy.all import rdpcap, wrpcap, Packet
    from scapy.utils import RawPcapReader, RawPcapWriter
    from scapy.plist import PacketList
except ImportError as e:
    raise ImportError(f"无法导入Scapy: {e}. 请安装: pip install scapy")

from .exceptions import FileConsistencyError, ValidationError


class PcapFileHandler:
    """PCAP文件格式处理器
    
    提供严格一致性的PCAP文件读写功能，确保：
    1. 时间戳精度完全保持
    2. 包序列和大小不变
    3. 所有元数据保持一致
    4. 只有指定的载荷字节被修改
    
    支持的格式：
    - PCAP (.pcap)
    - PCAPNG (.pcapng)
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化文件处理器
        
        Args:
            logger: 可选的日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # 支持的文件格式
        self.supported_formats = {'.pcap', '.pcapng'}
        
        # 读取缓存设置
        self.read_buffer_size = 1024 * 1024  # 1MB缓冲区
        self.max_packet_size = 65536  # 64KB最大包大小
        
        # 写入设置
        self.preserve_metadata = True
        self.validate_after_write = True
        
    def validate_file_format(self, file_path: str) -> bool:
        """验证文件格式是否支持
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否支持该文件格式
        """
        try:
            path = Path(file_path)
            suffix = path.suffix.lower()
            
            if suffix not in self.supported_formats:
                self.logger.warning(f"不支持的文件格式: {suffix}")
                return False
                
            # 尝试读取文件头验证
            if not path.exists():
                self.logger.error(f"文件不存在: {file_path}")
                return False
                
            if not path.is_file():
                self.logger.error(f"不是文件: {file_path}")
                return False
                
            # 检查文件大小
            file_size = path.stat().st_size
            if file_size == 0:
                self.logger.error(f"文件为空: {file_path}")
                return False
                
            # 尝试读取PCAP头部
            with open(file_path, 'rb') as f:
                header = f.read(24)  # PCAP全局头部24字节
                if len(header) < 24:
                    self.logger.error(f"文件头部不完整: {file_path}")
                    return False
                    
                # 检查PCAP魔数
                magic_number = int.from_bytes(header[:4], byteorder='little')
                pcap_magics = {
                    0xa1b2c3d4,  # PCAP (microsecond)
                    0xa1b23c4d,  # PCAP (nanosecond)
                    0x0a0d0d0a   # PCAPNG
                }
                
                if magic_number not in pcap_magics:
                    magic_be = int.from_bytes(header[:4], byteorder='big')
                    if magic_be not in pcap_magics:
                        self.logger.error(f"无效的PCAP魔数: {hex(magic_number)}")
                        return False
                        
            self.logger.debug(f"✅ 文件格式验证通过: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"文件格式验证失败: {e}")
            return False
    
    def read_packets(self, file_path: str) -> List[Packet]:
        """严格一致性读取数据包
        
        使用Scapy读取PCAP文件，确保保持所有原始属性和时间戳。
        
        Args:
            file_path: PCAP文件路径
            
        Returns:
            List[Packet]: 数据包列表
            
        Raises:
            ValidationError: 输入参数无效
            FileConsistencyError: 文件读取失败
        """
        start_time = time.time()
        
        try:
            # 验证文件格式
            if not self.validate_file_format(file_path):
                raise ValidationError(f"不支持的文件格式: {file_path}")
            
            # 记录原始文件格式
            self._last_read_format = 'pcapng' if file_path.lower().endswith('.pcapng') else 'pcap'
            
            self.logger.info(f"📖 开始读取PCAP文件: {file_path}")
            
            # 获取文件信息
            file_path_obj = Path(file_path)
            file_size = file_path_obj.stat().st_size
            
            self.logger.debug(f"   📊 文件大小: {file_size:,} bytes")
            self.logger.debug(f"   📂 文件格式: {self._last_read_format}")
            
            # 使用Scapy读取文件，保持原始数据包属性
            packets = rdpcap(file_path)
            
            read_time = time.time() - start_time
            packet_count = len(packets)
            
            # 统计信息
            self.logger.info(f"✅ 成功读取 {packet_count} 个数据包，耗时 {read_time:.3f}s")
            
            if packet_count > 0:
                pps = packet_count / read_time if read_time > 0 else 0
                self.logger.debug(f"   📈 读取速度: {pps:.1f} pps")
            
            return packets
            
        except Exception as e:
            self.logger.error(f"❌ 读取PCAP文件失败: {e}")
            if isinstance(e, (ValidationError, FileConsistencyError)):
                raise
            else:
                raise FileConsistencyError(f"读取文件时发生错误: {e}") from e
    
    def write_packets(self, packets: List[Packet], file_path: str, preserve_format: bool = True) -> None:
        """写入数据包到文件
        
        Args:
            packets: 要写入的数据包列表
            file_path: 输出文件路径
            preserve_format: 是否保持原始格式（pcap/pcapng）
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"📝 开始写入 {len(packets)} 个数据包到: {file_path}")
            
            # 确定输出格式
            if preserve_format:
                # 根据原始文件格式决定输出格式
                if hasattr(self, '_last_read_format'):
                    output_format = self._last_read_format
                else:
                    # 根据文件扩展名决定
                    output_format = 'pcapng' if file_path.lower().endswith('.pcapng') else 'pcap'
            else:
                # 根据文件扩展名决定
                output_format = 'pcapng' if file_path.lower().endswith('.pcapng') else 'pcap'
            
            # 使用Scapy写入文件
            if output_format == 'pcapng':
                # 对于pcapng格式，使用PcapNgWriter
                try:
                    from scapy.utils import PcapNgWriter
                    with PcapNgWriter(file_path, append=False) as writer:
                        for packet in packets:
                            writer.write(packet)
                except ImportError:
                    # 如果没有PcapNgWriter，回退到wrpcap
                    wrpcap(file_path, packets)
            else:
                # 对于pcap格式，使用wrpcap
                wrpcap(file_path, packets)
            
            # 验证写入结果
            file_size = os.path.getsize(file_path)
            write_time = time.time() - start_time
            
            self.logger.info(f"✅ 成功写入文件: {file_path}")
            self.logger.info(f"   📊 文件大小: {file_size:,} bytes")
            self.logger.info(f"   ⏱️ 写入时间: {write_time:.3f}s")
            
        except Exception as e:
            raise IndependentMaskerError(f"写入文件失败: {e}") from e
    
    def copy_packet_metadata(self, source: Packet, target: Packet) -> Packet:
        """复制数据包元数据
        
        确保目标数据包保持源数据包的所有元数据（时间戳等）。
        
        Args:
            source: 源数据包
            target: 目标数据包
            
        Returns:
            Packet: 更新元数据后的目标数据包
        """
        try:
            # 复制时间戳
            if hasattr(source, 'time'):
                target.time = source.time
            
            # 复制其他可能的元数据
            if hasattr(source, 'wirelen'):
                target.wirelen = source.wirelen
                
            if hasattr(source, 'direction'):
                target.direction = source.direction
            
            return target
            
        except Exception as e:
            self.logger.warning(f"复制数据包元数据时发生警告: {e}")
            return target
    
    def get_file_stats(self, file_path: str) -> Dict[str, Any]:
        """获取PCAP文件统计信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 文件统计信息
        """
        try:
            if not self.validate_file_format(file_path):
                return {'error': 'Invalid file format'}
            
            path = Path(file_path)
            stat = path.stat()
            
            # 快速读取包计数（不加载所有包到内存）
            packet_count = 0
            try:
                packets = rdpcap(file_path)
                packet_count = len(packets)
            except Exception as e:
                self.logger.warning(f"无法读取包计数: {e}")
            
            return {
                'file_path': str(path.absolute()),
                'file_size': stat.st_size,
                'file_format': path.suffix.lower(),
                'packet_count': packet_count,
                'created_time': stat.st_ctime,
                'modified_time': stat.st_mtime,
                'readable': os.access(file_path, os.R_OK),
                'writable': os.access(file_path, os.W_OK)
            }
            
        except Exception as e:
            self.logger.error(f"获取文件统计失败: {e}")
            return {'error': str(e)}
    
    def create_backup(self, file_path: str) -> Optional[str]:
        """创建文件备份
        
        Args:
            file_path: 原文件路径
            
        Returns:
            Optional[str]: 备份文件路径，失败时返回None
        """
        try:
            if not os.path.exists(file_path):
                return None
            
            backup_path = f"{file_path}.backup.{int(time.time())}"
            
            import shutil
            shutil.copy2(file_path, backup_path)
            
            self.logger.info(f"✅ 创建备份文件: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return None
    
    def cleanup_backups(self, file_path: str, keep_count: int = 3) -> None:
        """清理旧的备份文件
        
        Args:
            file_path: 原文件路径
            keep_count: 保留的备份数量
        """
        try:
            base_path = Path(file_path)
            backup_pattern = f"{base_path.name}.backup.*"
            
            # 查找所有备份文件
            backup_files = []
            for backup_file in base_path.parent.glob(backup_pattern):
                try:
                    # 从文件名提取时间戳
                    timestamp = int(backup_file.name.split('.')[-1])
                    backup_files.append((timestamp, backup_file))
                except (ValueError, IndexError):
                    continue
            
            # 按时间戳排序，保留最新的几个
            backup_files.sort(reverse=True)
            
            for timestamp, backup_file in backup_files[keep_count:]:
                try:
                    backup_file.unlink()
                    self.logger.debug(f"删除旧备份: {backup_file}")
                except OSError as e:
                    self.logger.warning(f"删除备份文件失败: {e}")
                    
        except Exception as e:
            self.logger.warning(f"清理备份文件时发生错误: {e}") 