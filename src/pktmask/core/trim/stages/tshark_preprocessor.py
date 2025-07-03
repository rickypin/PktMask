#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TShark预处理器

使用TShark进行TCP流重组和IP碎片重组处理，为后续的协议分析阶段提供预处理数据。
该阶段是Enhanced Trim Payloads处理流程的第一阶段。
"""

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging

from .base_stage import BaseStage, StageContext
from .stage_result import StageResult, StageStatus, StageMetrics
from ...processors.base_processor import ProcessorResult
from ....config.defaults import get_tshark_paths


class TSharkPreprocessor(BaseStage):
    """TShark预处理器
    
    负责使用TShark执行以下预处理任务：
    1. TCP流重组 - 将分段的TCP数据重新组装
    2. IP碎片重组 - 将IP分片重新组装成完整的IP数据包
    3. 生成适合后续分析的PCAP文件
    
    这是多阶段处理流程的第一阶段，为PyShark分析器和Scapy回写器提供清理后的数据。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化TShark预处理器
        
        Args:
            config: 配置参数字典，包含TShark相关设置
        """
        super().__init__("TShark预处理器", config)
        
        # TShark执行文件路径
        self._tshark_path: Optional[str] = None
        
        # 重组配置 - 从配置或默认值获取
        self._enable_reassembly = self.get_config_value('tshark_enable_reassembly', True)
        self._enable_defragmentation = self.get_config_value('tshark_enable_defragmentation', True)
        self._timeout_seconds = self.get_config_value('tshark_timeout_seconds', 300)
        
        # 性能配置
        self._max_memory_mb = self.get_config_value('tshark_max_memory_mb', 1024)
        self._temp_dir = self.get_config_value('temp_dir', None)
        
        # 可执行文件路径配置
        self._executable_paths = self.get_config_value('tshark_executable_paths', get_tshark_paths())
        self._custom_executable = self.get_config_value('tshark_custom_executable', None)
    
    def _initialize_impl(self) -> None:
        """初始化TShark预处理器"""
        # 查找TShark可执行文件
        self._tshark_path = self._find_tshark_executable()
        if not self._tshark_path:
            raise RuntimeError("未找到TShark可执行文件，请确保Wireshark已正确安装")
        
        # 验证TShark版本
        version = self._get_tshark_version()
        self._logger.info(f"Found TShark version: {version}")
        
        # 验证TShark功能
        self._verify_tshark_capabilities()
        
        self._logger.info("TShark preprocessor initialization completed")
    
    def _find_tshark_executable(self) -> Optional[str]:
        """查找TShark可执行文件
        
        Returns:
            TShark可执行文件路径，如果未找到则返回None
        """
        # 首先检查配置中指定的自定义可执行文件路径
        if self._custom_executable and os.path.exists(self._custom_executable):
            return self._custom_executable
        
        # 检查PATH环境变量
        tshark_in_path = shutil.which('tshark')
        if tshark_in_path:
            return tshark_in_path
        
        # 检查配置中的搜索路径
        for path in self._executable_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _get_tshark_version(self) -> str:
        """获取TShark版本信息
        
        Returns:
            TShark版本字符串
        """
        try:
            result = subprocess.run(
                [self._tshark_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # 提取版本号 (通常在第一行)
                version_line = result.stdout.split('\n')[0]
                return version_line.strip()
            else:
                return "未知版本"
                
        except Exception as e:
            self._logger.warning(f"获取TShark版本失败: {e}")
            return "版本检查失败"
    
    def _verify_tshark_capabilities(self) -> None:
        """验证TShark功能支持
        
        Raises:
            RuntimeError: 如果关键功能不可用
        """
        # 检查是否支持所需的重组选项
        try:
            # 测试重组参数是否有效
            result = subprocess.run(
                [self._tshark_path, '-G', 'defaultprefs'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise RuntimeError("TShark功能验证失败，可能版本过旧")
                
            prefs = result.stdout.lower()
            
            # 检查TCP重组支持
            if self._enable_reassembly and 'tcp.desegment' not in prefs:
                self._logger.warning("TShark可能不支持TCP重组功能")
            
            # 检查IP重组支持  
            if self._enable_defragmentation and 'ip.defragment' not in prefs:
                self._logger.warning("TShark可能不支持IP碎片重组功能")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("TShark响应超时，可能安装有问题")
        except Exception as e:
            self._logger.warning(f"TShark功能验证失败: {e}")
            raise RuntimeError(f"TShark功能验证失败: {e}")
    
    def validate_inputs(self, context: StageContext) -> bool:
        """验证输入参数
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            验证是否成功
        """
        # 检查输入文件
        if not context.input_file.exists():
            self._logger.error(f"输入文件不存在: {context.input_file}")
            return False
        
        if context.input_file.stat().st_size == 0:
            self._logger.error(f"输入文件为空: {context.input_file}")
            return False
        
        # 检查输出目录
        context.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 检查工作目录
        context.work_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查TShark可用性
        if not self.is_initialized or not self._tshark_path:
            self._logger.error("TShark预处理器未正确初始化")
            return False
        
        return True
    
    def execute(self, context: StageContext) -> ProcessorResult:
        """执行TShark预处理
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            处理结果
        """
        context.current_stage = self.name
        progress_callback = self.get_progress_callback(context)
        # 临时屏蔽TShark预处理，直接使用原始输入文件作为后续阶段输入
        self._logger.info("临时屏蔽TShark预处理，使用原始输入文件作为后续阶段输入")
        context.tshark_output = context.input_file
        return ProcessorResult(
            success=True,
            data={
                'tshark_output': str(context.input_file),
                'message': "TShark预处理已屏蔽，直接使用原始文件"
            },
            stats={}
        )
    
    def _create_temp_file(self, context: StageContext, prefix: str, suffix: str) -> Path:
        """创建临时文件
        
        Args:
            context: 阶段执行上下文
            prefix: 文件名前缀
            suffix: 文件名后缀
            
        Returns:
            临时文件路径
        """
        # 使用指定的临时目录或工作目录
        temp_dir = Path(self._temp_dir) if self._temp_dir else context.work_dir
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(
            prefix=f"{prefix}_",
            suffix=suffix,
            dir=str(temp_dir)
        )
        os.close(fd)  # 关闭文件描述符
        
        temp_file = Path(temp_path)
        context.register_temp_file(temp_file)
        
        return temp_file
    
    def _build_tshark_command(self, input_file: Path, output_file: Path) -> List[str]:
        """构建TShark命令行
        
        Args:
            input_file: 输入PCAP文件
            output_file: 输出PCAP文件
            
        Returns:
            TShark命令行参数列表
        """
        cmd = [self._tshark_path]
        
        # 输入文件
        cmd.extend(['-r', str(input_file)])
        
        # 输出文件
        cmd.extend(['-w', str(output_file)])
        
        # 重组选项
        prefs = []
        
        if self._enable_reassembly:
            # 启用TCP重组
            prefs.extend([
                'tcp.desegment_tcp_streams:TRUE',
                'tcp.reassemble_out_of_order:TRUE'
            ])
        
        if self._enable_defragmentation:
            # 启用IP碎片重组
            prefs.extend([
                'ip.defragment:TRUE',
                'ipv6.defragment:TRUE'
            ])
        
        # 应用首选项
        for pref in prefs:
            cmd.extend(['-o', pref])
        
        # 内存限制 - 使用缓冲区大小参数替代
        # 注意：TShark没有直接的内存限制参数，我们移除这个无效的参数
        # if self._max_memory_mb > 0:
        #     cmd.extend(['-C', str(self._max_memory_mb)])  # -C是配置文件参数，不是内存限制
        
        # 安静模式，减少输出
        cmd.append('-q')
        
        return cmd
    
    def _execute_tshark(self, cmd: List[str], progress_callback) -> Dict[str, Any]:
        """执行TShark命令
        
        Args:
            cmd: TShark命令行参数
            progress_callback: 进度回调函数
            
        Returns:
            执行统计信息
        """
        import time
        
        self._logger.info(f"执行TShark命令: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            # 启动TShark进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # 等待完成或超时
            try:
                stdout, stderr = process.communicate(timeout=self._timeout_seconds)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RuntimeError(f"TShark执行超时 (>{self._timeout_seconds}秒)")
            
            execution_time = time.time() - start_time
            
            # 检查执行结果
            if return_code != 0:
                error_msg = f"TShark执行失败 (退出码: {return_code})"
                if stderr:
                    error_msg += f": {stderr}"
                raise RuntimeError(error_msg)
            
            # 解析输出统计信息
            stats = self._parse_tshark_output(stdout, stderr)
            stats['execution_time'] = execution_time
            stats['return_code'] = return_code
            
            # 更新进度到80%
            progress_callback(0.8)
            
            return stats
            
        except Exception as e:
            self._logger.error(f"TShark执行异常: {e}")
            raise
    
    def _parse_tshark_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """解析TShark输出信息
        
        Args:
            stdout: 标准输出
            stderr: 错误输出
            
        Returns:
            解析后的统计信息
        """
        stats = {
            'packets_processed': 0,
            'reassembled_streams': 0,
            'defragmented_packets': 0,
            'warnings': 0,
            'errors': 0
        }
        
        # 解析标准输出中的统计信息
        for line in stdout.split('\n'):
            line = line.strip().lower()
            
            # 提取包数量信息
            if 'packets' in line and 'processed' in line:
                try:
                    # 尝试提取数字
                    import re
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        stats['packets_processed'] = int(numbers[0])
                except ValueError:
                    pass
        
        # 解析错误输出中的警告和错误
        for line in stderr.split('\n'):
            line = line.strip().lower()
            
            if 'warning' in line:
                stats['warnings'] += 1
            elif 'error' in line:
                stats['errors'] += 1
        
        return stats
    
    def _verify_output(self, output_file: Path) -> None:
        """验证输出文件
        
        Args:
            output_file: 输出文件路径
            
        Raises:
            RuntimeError: 如果输出文件无效
        """
        if not output_file.exists():
            raise RuntimeError("TShark未生成输出文件")
        
        if output_file.stat().st_size == 0:
            raise RuntimeError("TShark生成了空的输出文件")
        
        # 简单验证PCAP文件头
        try:
            with open(output_file, 'rb') as f:
                header = f.read(4)
                # PCAP文件魔数: 0xA1B2C3D4 或 0xD4C3B2A1
                if header not in [b'\xa1\xb2\xc3\xd4', b'\xd4\xc3\xb2\xa1']:
                    # 也可能是PCAPNG格式
                    f.seek(0)
                    header = f.read(8)
                    if not header.startswith(b'\x0a\x0d\x0d\x0a'):
                        self._logger.warning("输出文件可能不是有效的PCAP格式")
        except Exception as e:
            self._logger.warning(f"无法验证输出文件格式: {e}")
    
    def _update_stats(self, context: StageContext, execution_stats: Dict[str, Any]) -> None:
        """更新统计信息
        
        Args:
            context: 阶段执行上下文
            execution_stats: 执行统计信息
        """
        # 更新基础统计
        self.stats.update(execution_stats)
        
        # 更新上下文统计
        context.stats.update({
            'tshark_preprocessing': execution_stats,
            'input_size': context.input_file.stat().st_size,
            'output_size': context.output_file.stat().st_size if context.output_file.exists() else 0
        })
    
    def get_estimated_duration(self, context: StageContext) -> float:
        """估算处理时间
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            估算的处理时间（秒）
        """
        if not context.input_file.exists():
            return 1.0
        
        # 基于文件大小估算（TShark相对较快）
        file_size_mb = context.input_file.stat().st_size / (1024 * 1024)
        
        # TShark处理速度约为每MB 0.05-0.2秒，取决于重组复杂度
        base_time = file_size_mb * 0.1
        
        # 重组会增加处理时间
        if self._enable_reassembly:
            base_time *= 1.5
        
        if self._enable_defragmentation:
            base_time *= 1.2
        
        return max(0.51, base_time)
    
    def get_required_tools(self) -> List[str]:
        """获取所需的外部工具列表
        
        Returns:
            工具名称列表
        """
        return ['tshark']
    
    def check_tool_availability(self) -> Dict[str, bool]:
        """检查外部工具可用性
        
        Returns:
            工具可用性字典
        """
        return {
            'tshark': self._tshark_path is not None and os.path.exists(self._tshark_path)
        }
    
    def get_description(self) -> str:
        """获取处理器描述
        
        Returns:
            处理器功能描述
        """
        return ("TShark预处理器 - 执行TCP流重组和IP碎片重组，"
                "为后续协议分析阶段提供清理后的PCAP数据")
    
    def _cleanup_impl(self, context: StageContext) -> None:
        """清理实现
        
        Args:
            context: 阶段执行上下文
        """
        # 基类会自动清理临时文件，这里不需要额外操作
        pass 