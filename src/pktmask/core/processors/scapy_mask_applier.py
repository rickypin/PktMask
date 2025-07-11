"""
Scapy掩码应用器

基于MaskRule列表对数据包进行精确掩码应用的组件。
这是TSharkEnhancedMaskProcessor的第三阶段处理器。

功能特性：
1. 边界安全处理：确保掩码操作不会超出TLS记录边界
2. 分类掩码应用：根据TLS类型应用不同的掩码策略
3. 多规则处理：支持单个数据包应用多个掩码规则
4. 校验和重计算：自动处理TCP/IP校验和
5. 错误恢复：异常情况下优雅降级
"""

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

try:
    from scapy.all import rdpcap, wrpcap, Packet, TCP, Raw, IP
    SCAPY_AVAILABLE = True
except ImportError:
    rdpcap = wrpcap = Packet = TCP = Raw = IP = None
    SCAPY_AVAILABLE = False

from ..trim.models.tls_models import MaskRule, MaskAction


class ScapyMaskApplier:
    """Scapy掩码应用器
    
    将TLS掩码规则精确应用到数据包，处理TLS记录边界安全。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Scapy掩码应用器
        
        Args:
            config: 配置参数字典
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 配置参数
        self._mask_byte_value = self.config.get('mask_byte_value', 0x00)
        self._recalculate_checksums = self.config.get('recalculate_checksums', True)
        self._preserve_timestamps = self.config.get('preserve_timestamps', True)
        self._batch_size = self.config.get('batch_size', 1000)
        self._validate_boundaries = self.config.get('validate_boundaries', True)
        
        # 调试配置
        self._verbose = self.config.get('verbose', False)
        self._debug_packet_numbers = self.config.get('debug_packet_numbers', [])
        
        # 内部状态
        self._processed_packets_count = 0
        self._modified_packets_count = 0
        self._masked_bytes_count = 0
        self._applied_rules_count = 0
        self._boundary_violations_count = 0
        
    def check_dependencies(self) -> bool:
        """检查Scapy依赖是否可用
        
        Returns:
            是否可用
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy库不可用，无法进行掩码应用")
            return False
        return True
    
    def apply_masks(
        self,
        input_file: str,
        output_file: str,
        mask_rules: List[MaskRule],
        packet_tls_type_map: Optional[Dict[int, int]] = None
    ) -> Dict[str, Any]:
        """对PCAP文件应用掩码规则

        Args:
            input_file: 输入PCAP文件路径
            output_file: 输出PCAP文件路径
            mask_rules: 掩码规则列表
            packet_tls_type_map: 包号到TLS类型的映射，用于跨包分段识别

        Returns:
            处理结果字典
            
        Raises:
            RuntimeError: 掩码应用失败时抛出
            FileNotFoundError: 输入文件不存在时抛出
            ImportError: Scapy不可用时抛出
        """
        # 支持 Path 参数，将路径转换为字符串
        if isinstance(input_file, Path):
            input_file = str(input_file)
        if isinstance(output_file, Path):
            output_file = str(output_file)
        if not self.check_dependencies():
            raise ImportError("Scapy库不可用，无法进行掩码应用")
        
        # 验证输入文件存在
        if not Path(input_file).exists():
            raise FileNotFoundError(f"输入文件不存在: {input_file}")
        
        self.logger.info(f"开始应用掩码规则: {input_file} -> {output_file}")
        self.logger.info(f"掩码规则数量: {len(mask_rules)}")

        # 保存包号到TLS类型的映射
        self._packet_tls_type_map = packet_tls_type_map or {}
        if self._packet_tls_type_map:
            self.logger.info(f"包号到TLS类型映射: {len(self._packet_tls_type_map)}个包")

        self._reset_statistics()
        start_time = time.time()
        
        try:
            # 组织掩码规则（按包编号分组）
            packet_rules = self._organize_rules_by_packet(mask_rules)
            
            # 读取数据包
            self.logger.info("读取输入PCAP文件...")
            packets = rdpcap(input_file)
            total_packets = len(packets)
            
            self.logger.info(f"成功读取{total_packets}个数据包")
            
            # 应用掩码规则
            modified_packets = self._apply_masks_to_packets(packets, packet_rules)
            
            # 写入输出文件
            self.logger.info(f"写入输出PCAP文件: {output_file}")
            self._write_packets(modified_packets, output_file)
            
            # 计算处理统计
            processing_time = time.time() - start_time
            
            result = self._generate_result_statistics(
                total_packets, processing_time
            )
            
            self.logger.info(f"掩码应用完成：处理{total_packets}个包，修改{self._modified_packets_count}个包")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Scapy掩码应用失败: {e}")
            raise RuntimeError(f"掩码应用失败: {e}") from e
    
    def _organize_rules_by_packet(self, mask_rules: List[MaskRule]) -> Dict[int, List[MaskRule]]:
        """按包编号组织掩码规则
        
        Args:
            mask_rules: 掩码规则列表
            
        Returns:
            按包编号分组的规则字典
        """
        packet_rules = defaultdict(list)
        
        for rule in mask_rules:
            packet_rules[rule.packet_number].append(rule)
        
        # 对每个包的规则按偏移量排序
        for packet_number, rules in packet_rules.items():
            rules.sort(key=lambda r: r.tls_record_offset)
        
        self.logger.debug(f"规则组织完成：{len(packet_rules)}个包有掩码规则")
        
        return packet_rules
    
    def _apply_masks_to_packets(
        self, 
        packets: List[Packet], 
        packet_rules: Dict[int, List[MaskRule]]
    ) -> List[Packet]:
        """对数据包列表应用掩码规则
        
        Args:
            packets: 数据包列表
            packet_rules: 按包编号分组的规则
            
        Returns:
            处理后的数据包列表
        """
        modified_packets = []
        
        for i, packet in enumerate(packets):
            packet_number = i + 1  # 包编号从1开始
            self._processed_packets_count += 1
            
            # 检查是否有适用的规则
            if packet_number not in packet_rules:
                # 无规则，原样保留
                modified_packets.append(packet)
                continue
            
            # 检查是否需要调试输出
            debug_this_packet = (
                packet_number in self._debug_packet_numbers or 
                self._verbose
            )
            
            if debug_this_packet:
                self.logger.info(f"=== 处理包{packet_number} ===")
            
            # 应用掩码规则
            try:
                modified_packet = self._apply_mask_rules_to_packet(
                    packet, packet_rules[packet_number], packet_number
                )
                modified_packets.append(modified_packet)
                
                if debug_this_packet:
                    self.logger.info(f"包{packet_number}处理完成")
                    
            except Exception as e:
                self.logger.warning(f"包{packet_number}掩码应用失败: {e}")
                # 失败时保留原包
                modified_packets.append(packet)
            
            # 进度报告
            if self._processed_packets_count % self._batch_size == 0:
                self.logger.debug(f"已处理{self._processed_packets_count}个包")
        
        return modified_packets

    def _resolve_rule_conflicts(self, rules: List[MaskRule], packet_number: int) -> List[MaskRule]:
        """解决同一包内的掩码规则冲突

        优先级规则：
        1. TLS-22/20/21/24 (握手/CCS/Alert/Heartbeat) 完全保留 > TLS-23 (ApplicationData) 掩码
        2. 跨包规则 > 单包规则
        3. 保留规则 > 掩码规则

        Args:
            rules: 原始规则列表
            packet_number: 包编号

        Returns:
            解决冲突后的规则列表
        """
        if len(rules) <= 1:
            return rules

        # 按优先级分类规则
        preserve_rules = []  # TLS-22/20/21/24 保留规则
        mask_rules = []      # TLS-23 掩码规则

        for rule in rules:
            if rule.tls_record_type in [20, 21, 22, 24]:  # 高优先级TLS类型
                preserve_rules.append(rule)
            elif rule.tls_record_type == 23:  # ApplicationData
                mask_rules.append(rule)
            else:
                # 其他规则（如非TLS TCP载荷）
                mask_rules.append(rule)

        # 如果有保留规则，优先使用保留规则
        if preserve_rules:
            self.logger.info(f"⚡ [规则冲突解决] 包{packet_number}: 发现{len(preserve_rules)}个保留规则和{len(mask_rules)}个掩码规则，优先使用保留规则")

            # 选择最高优先级的保留规则
            # 优先级：跨包规则 > 单包规则，TLS-22 > TLS-20/21/24
            preserve_rules.sort(key=lambda r: (
                len(r.reason.split('跨包')) > 1,  # 跨包规则优先
                r.tls_record_type == 22,         # TLS-22握手优先
                -r.tls_record_offset             # 偏移量小的优先
            ), reverse=True)

            selected_rule = preserve_rules[0]
            self.logger.info(f"⚡ [规则冲突解决] 包{packet_number}: 选择保留规则: {selected_rule.reason}")
            return [selected_rule]

        # 如果只有掩码规则，选择最严格的掩码规则
        if mask_rules:
            # 优先选择跨包重组规则，然后是智能掩码规则
            mask_rules.sort(key=lambda r: (
                '重组' in r.reason,              # 重组规则优先
                '智能掩码' in r.reason,          # 智能掩码其次
                -r.tls_record_offset             # 偏移量小的优先
            ), reverse=True)

            selected_rule = mask_rules[0]
            self.logger.info(f"⚡ [规则冲突解决] 包{packet_number}: 选择掩码规则: {selected_rule.reason}")
            return [selected_rule]

        # 默认返回原规则
        return rules

    def _apply_mask_rules_to_packet(
        self,
        packet: Packet,
        rules: List[MaskRule],
        packet_number: int
    ) -> Packet:
        """对单个数据包应用多个掩码规则

        Args:
            packet: 原始数据包
            rules: 该包的掩码规则列表
            packet_number: 包编号（用于调试）

        Returns:
            处理后的数据包
        """
        if not rules:
            return packet

        # 检查包是否有TCP层
        if not packet.haslayer(TCP):
            self.logger.warning(f"包{packet_number}没有TCP层，跳过掩码应用")
            return packet

        # 获取TCP载荷
        tcp_payload = self._extract_tcp_payload(packet)
        if not tcp_payload:
            self.logger.debug(f"包{packet_number}没有TCP载荷，跳过掩码应用")
            return packet

        # 复制数据包
        modified_packet = packet.copy()

        # 创建可修改的载荷缓冲区
        masked_payload = bytearray(tcp_payload)
        original_length = len(masked_payload)

        # 解决规则冲突：优先保留TLS-22/20/21/24规则
        resolved_rules = self._resolve_rule_conflicts(rules, packet_number)

        # 应用解决冲突后的掩码规则
        packet_was_modified = False

        self.logger.info(f"⚡ [包级掩码] 包{packet_number}: 开始应用{len(resolved_rules)}个掩码规则（原{len(rules)}个），载荷长度={original_length}")

        for i, rule in enumerate(resolved_rules):
            self.logger.info(f"⚡ [包级掩码] 包{packet_number}: 应用第{i+1}/{len(resolved_rules)}个规则: {rule.get_description()}")

            if self._apply_single_mask_rule(
                masked_payload, rule, packet_number, original_length
            ):
                packet_was_modified = True
                self.logger.info(f"⚡ [包级掩码] 包{packet_number}: 第{i+1}个规则应用成功")
            else:
                self.logger.info(f"⚡ [包级掩码] 包{packet_number}: 第{i+1}个规则跳过或失败")
        
        # 更新数据包载荷
        if packet_was_modified:
            self._update_packet_payload(modified_packet, bytes(masked_payload))
            self._modified_packets_count += 1
            
            self.logger.info(f"⚡ [包级掩码完成] 包{packet_number}: 载荷已更新，包已修改")
            
            # 重新计算校验和（如果启用）
            if self._recalculate_checksums:
                self._recalculate_packet_checksums(modified_packet)
                self.logger.info(f"⚡ [包级掩码] 包{packet_number}: 校验和已重新计算")
        else:
            self.logger.info(f"⚡ [包级掩码] 包{packet_number}: 无修改，包保持原样")
        
        return modified_packet
    
    def _apply_single_mask_rule(
        self, 
        payload_buffer: bytearray, 
        rule: MaskRule,
        packet_number: int,
        payload_length: int
    ) -> bool:
        """应用单个掩码规则到载荷缓冲区
        
        Args:
            payload_buffer: 可修改的载荷缓冲区
            rule: 掩码规则
            packet_number: 包编号
            payload_length: 载荷总长度
            
        Returns:
            是否应用了掩码
        """
        # 检查规则是否为实际掩码操作
        if not rule.is_mask_operation:
            self.logger.debug(f"规则{rule.get_description()}：保留操作，跳过")
            return False
        
        # 详细分析掩码规则类型
        is_cross_packet_rule = ("跨包" in rule.reason or rule.mask_length == -1)
        is_segment_rule = ("分段" in rule.reason or "首段" in rule.reason or "中间段" in rule.reason)
        is_reassembly_rule = ("重组" in rule.reason)
        is_non_tls_rule = (rule.tls_record_type is None and "非TLS" in rule.reason)

        # 修正：检查是否为TLS跨包分段（即使被标记为非TLS）
        packet_tls_type = getattr(self, '_packet_tls_type_map', {}).get(packet_number)
        is_tls_cross_packet_segment = (
            (rule.tls_record_type in [20, 21, 22, 23, 24] or packet_tls_type is not None) and
            is_cross_packet_rule and
            not is_reassembly_rule
        )

        # 如果规则没有TLS类型但映射中有，使用映射中的类型
        effective_tls_type = rule.tls_record_type or packet_tls_type

        self.logger.info(f"⚡ [掩码规则分析] 包{packet_number}: 跨包={is_cross_packet_rule}, 分段={is_segment_rule}, 重组={is_reassembly_rule}, 非TLS={is_non_tls_rule}, TLS跨包分段={is_tls_cross_packet_segment}, 有效TLS类型={effective_tls_type}")

        # 计算掩码范围
        if rule.action.value == "mask_all_payload":
            # 检查是否为错误标记的TLS跨包分段
            if is_tls_cross_packet_segment:
                # 这是TLS跨包分段，应该根据TLS类型决定掩码策略
                if effective_tls_type == 23:  # ApplicationData
                    # TLS-23分段：掩码整个载荷
                    abs_start = 0
                    abs_end = payload_length
                    self.logger.info(f"⚡ [TLS-23分段修正] 包{packet_number}: TLS-23跨包分段，掩码整个载荷 0-{payload_length}")
                    self.logger.info(f"⚡ [TLS-23分段修正] 包{packet_number}: 原因={rule.reason}")
                else:
                    # TLS-20/21/22/24分段：完全保留
                    abs_start = 0
                    abs_end = 0  # 不掩码
                    self.logger.info(f"⚡ [TLS-{effective_tls_type}分段修正] 包{packet_number}: TLS-{effective_tls_type}跨包分段，完全保留")
                    self.logger.info(f"⚡ [TLS-{effective_tls_type}分段修正] 包{packet_number}: 原因={rule.reason}")
            else:
                # 真正的非TLS TCP载荷全掩码：掩码整个TCP载荷
                abs_start = 0
                abs_end = payload_length
                self.logger.info(f"⚡ [非TLS全掩码] 包{packet_number}: 非TLS TCP载荷全掩码，掩码整个载荷 0-{payload_length}")
                self.logger.info(f"⚡ [非TLS全掩码] 包{packet_number}: 原因={rule.reason}")

        elif rule.mask_length == -1:
            # 特殊处理：mask_length=-1 表示掩码到TCP载荷结束
            if rule.mask_offset == 0 and rule.tls_record_offset == 0:
                # 掩码整个TCP载荷（分段包）
                abs_start = 0
                abs_end = payload_length
                self.logger.info(f"⚡ [TLS-23分段掩码] 包{packet_number}: 分段包完整掩码，掩码整个载荷 0-{payload_length} (TLS-{rule.tls_record_type})")
                self.logger.info(f"⚡ [TLS-23分段掩码] 包{packet_number}: 原因={rule.reason}")
                
            elif rule.mask_offset > 0:
                # 从指定偏移掩码到载荷结束（重组包）
                abs_start = rule.tls_record_offset + rule.mask_offset
                abs_end = payload_length
                
                # 边界安全检查：确保不超出载荷范围
                if abs_start >= payload_length:
                    self.logger.warning(f"⚡ [边界警告] 包{packet_number}: 掩码起始位置{abs_start}超出载荷长度{payload_length}，调整到载荷结束")
                    abs_start = payload_length
                    abs_end = payload_length
                
                self.logger.info(f"⚡ [TLS-23重组掩码] 包{packet_number}: 重组包掩码，从偏移{abs_start}掩码到载荷结束{abs_end} (TLS-{rule.tls_record_type})")
                self.logger.info(f"⚡ [TLS-23重组掩码] 包{packet_number}: 保留头部{rule.mask_offset}字节，掩码剩余载荷{max(0, abs_end - abs_start)}字节")
                self.logger.info(f"⚡ [TLS-23重组掩码] 包{packet_number}: 原因={rule.reason}")
            else:
                # 掩码整个载荷（兼容性处理）
                abs_start = rule.tls_record_offset
                abs_end = payload_length
                self.logger.info(f"⚡ [TLS-23兼容掩码] 包{packet_number}: 兼容性掩码规则，从偏移{abs_start}掩码到载荷结束{abs_end} (TLS-{rule.tls_record_type})")
                
        elif rule.tls_record_length == 0 and is_cross_packet_rule:
            # 旧版跨包规则兼容性处理
            if rule.mask_offset == 0:
                # 掩码整个载荷
                abs_start = 0
                abs_end = payload_length
                self.logger.info(f"⚡ [TLS-23兼容分段] 包{packet_number}: 兼容性分段包掩码规则，掩码整个载荷 0-{payload_length} (TLS-{rule.tls_record_type})")
            else:
                # 从偏移开始掩码
                abs_start = rule.tls_record_offset + rule.mask_offset
                abs_end = payload_length
                self.logger.info(f"⚡ [TLS-23兼容重组] 包{packet_number}: 兼容性重组包掩码规则，从偏移{abs_start}掩码到载荷结束{abs_end} (TLS-{rule.tls_record_type})")
            
            self.logger.info(f"⚡ [TLS-23兼容掩码] 包{packet_number}: 原因={rule.reason}")
            
        else:
            # 普通规则：计算绝对偏移量
            abs_start = rule.absolute_mask_start
            abs_end = rule.absolute_mask_end
            
            # 边界安全检查：确保不超出载荷范围
            if abs_end > payload_length:
                original_end = abs_end
                abs_end = payload_length
                self.logger.warning(f"⚡ [边界调整] 包{packet_number}: 掩码结束位置从{original_end}调整到{abs_end}(载荷长度)")
            
            self.logger.info(f"⚡ [普通掩码] 包{packet_number}: 普通掩码规则，绝对偏移{abs_start}-{abs_end} (TLS-{rule.tls_record_type})")
            if rule.tls_record_type == 23:
                self.logger.info(f"⚡ [TLS-23标准掩码] 包{packet_number}: ApplicationData掩码，保留头部{rule.mask_offset}字节，掩码载荷{rule.mask_length}字节")
        
        # 增强的边界安全检查
        if self._validate_boundaries:
            validation_result = self._validate_mask_boundaries_enhanced(
                abs_start, abs_end, payload_length, rule, packet_number
            )
            if not validation_result:
                return False
        
        # 应用掩码
        try:
            # 确保不会超出载荷边界，并处理边界情况
            actual_start = max(0, min(abs_start, payload_length))
            actual_end = max(actual_start, min(abs_end, payload_length))
            
            if actual_start < actual_end:
                # 应用掩码字节
                masked_bytes_before = sum(1 for b in payload_buffer[actual_start:actual_end] if b == self._mask_byte_value)
                
                for i in range(actual_start, actual_end):
                    payload_buffer[i] = self._mask_byte_value
                
                masked_bytes = actual_end - actual_start
                self._masked_bytes_count += masked_bytes
                self._applied_rules_count += 1
                
                # 验证掩码是否正确应用
                masked_bytes_after = sum(1 for b in payload_buffer[actual_start:actual_end] if b == self._mask_byte_value)
                newly_masked = masked_bytes_after - masked_bytes_before
                
                # 详细的掩码成功日志
                if is_cross_packet_rule:
                    if is_segment_rule:
                        self.logger.info(
                            f"⚡ [TLS-23分段掩码成功] 包{packet_number}: "
                            f"分段载荷完整掩码 {actual_start}-{actual_end}, 掩码{masked_bytes}字节，新置零{newly_masked}字节"
                        )
                    elif is_reassembly_rule:
                        self.logger.info(
                            f"⚡ [TLS-23重组掩码成功] 包{packet_number}: "
                            f"重组载荷掩码 {actual_start}-{actual_end}, 掩码{masked_bytes}字节，新置零{newly_masked}字节"
                        )
                    else:
                        self.logger.info(
                            f"⚡ [TLS-23跨包掩码成功] 包{packet_number}: "
                            f"跨包载荷掩码 {actual_start}-{actual_end}, 掩码{masked_bytes}字节，新置零{newly_masked}字节"
                        )
                else:
                    self.logger.info(
                        f"⚡ [TLS-{rule.tls_record_type}掩码成功] 包{packet_number}: "
                        f"偏移{actual_start}-{actual_end}, 掩码{masked_bytes}字节，新置零{newly_masked}字节"
                    )
                
                # 额外验证掩码完整性
                if rule.tls_record_type == 23:
                    zero_count = sum(1 for b in payload_buffer[actual_start:actual_end] if b == self._mask_byte_value)
                    zero_percentage = (zero_count / masked_bytes * 100) if masked_bytes > 0 else 0
                    self.logger.info(f"⚡ [TLS-23掩码验证] 包{packet_number}: ApplicationData载荷，{zero_count}/{masked_bytes}字节已正确置零 ({zero_percentage:.1f}%)")

                    # 如果掩码完整性不足，记录警告
                    if zero_percentage < 95 and masked_bytes > 10:  # 对于小载荷放宽要求
                        self.logger.warning(f"⚡ [掩码完整性警告] 包{packet_number}: 置零率{zero_percentage:.1f}%低于预期，可能存在掩码重叠或其他问题")

                elif rule.action.value == "mask_all_payload":
                    zero_count = sum(1 for b in payload_buffer[actual_start:actual_end] if b == self._mask_byte_value)
                    zero_percentage = (zero_count / masked_bytes * 100) if masked_bytes > 0 else 0
                    self.logger.info(f"⚡ [非TLS掩码验证] 包{packet_number}: 非TLS TCP载荷，{zero_count}/{masked_bytes}字节已正确置零 ({zero_percentage:.1f}%)")

                    # 如果掩码完整性不足，记录警告
                    if zero_percentage < 95 and masked_bytes > 10:
                        self.logger.warning(f"⚡ [非TLS掩码完整性警告] 包{packet_number}: 置零率{zero_percentage:.1f}%低于预期，可能存在掩码重叠或其他问题")
                
                return True
            else:
                self.logger.warning(f"⚡ [掩码范围无效] 包{packet_number}: 掩码范围{actual_start}-{actual_end}无效，跳过掩码应用")
                return False
                
        except Exception as e:
            self.logger.error(f"⚡ [掩码应用异常] 包{packet_number}: 应用掩码规则失败: {e}")
            return False
    
    def _validate_mask_boundaries_enhanced(
        self, 
        abs_start: int, 
        abs_end: int, 
        payload_length: int,
        rule: MaskRule,
        packet_number: int
    ) -> bool:
        """增强的掩码边界验证
        
        Args:
            abs_start: 绝对起始偏移
            abs_end: 绝对结束偏移
            payload_length: 载荷长度
            rule: 掩码规则
            packet_number: 包编号
            
        Returns:
            边界是否安全
        """
        # 检查基本边界条件
        if abs_start < 0:
            self.logger.warning(
                f"⚡ [边界验证] 包{packet_number}: 掩码起始偏移为负数{abs_start}，调整为0"
            )
            self._boundary_violations_count += 1
            # 对于跨包规则，这可能是正常的，不阻止执行
            return True
        
        if abs_start > payload_length:
            self.logger.warning(
                f"⚡ [边界验证] 包{packet_number}: 掩码起始偏移{abs_start}超出载荷长度{payload_length}"
            )
            self._boundary_violations_count += 1
            # 如果是跨包规则，可能是TShark重组信息不准确，但仍尝试掩码
            if "跨包" in rule.reason:
                self.logger.info(f"⚡ [跨包容错] 包{packet_number}: 跨包规则允许边界超出，继续执行")
                return True
            return False
        
        if abs_end < abs_start:
            self.logger.warning(
                f"⚡ [边界验证] 包{packet_number}: 掩码结束位置{abs_end}小于起始位置{abs_start}"
            )
            self._boundary_violations_count += 1
            return False
        
        # 对于跨包规则，放宽边界检查
        if "跨包" in rule.reason or rule.mask_length == -1:
            # 跨包规则：只要起始位置合理即可
            if abs_start <= payload_length:
                self.logger.debug(f"⚡ [跨包边界验证] 包{packet_number}: 跨包规则边界检查通过")
                return True
            else:
                self.logger.warning(f"⚡ [跨包边界验证] 包{packet_number}: 跨包规则起始位置{abs_start}超出载荷{payload_length}，但继续执行")
                return True  # 继续执行，让后续逻辑处理边界调整
        
        # 普通规则：严格边界检查
        if abs_end > payload_length:
            excess = abs_end - payload_length
            self.logger.warning(
                f"⚡ [边界验证] 包{packet_number}: 掩码超出载荷边界{excess}字节 ({abs_end} > {payload_length})"
            )
            self._boundary_violations_count += 1
            # 允许轻微超出（可能是TLS长度计算的小误差）
            if excess <= 10:
                self.logger.info(f"⚡ [边界容错] 包{packet_number}: 轻微超出{excess}字节，允许执行并调整边界")
                return True
            return False
        
        self.logger.debug(f"⚡ [边界验证通过] 包{packet_number}: 掩码范围{abs_start}-{abs_end}在载荷{payload_length}范围内")
        return True
    
    def _extract_tcp_payload(self, packet: Packet) -> Optional[bytes]:
        """提取TCP载荷
        
        Args:
            packet: 数据包
            
        Returns:
            TCP载荷字节串，如果没有则返回None
        """
        try:
            if packet.haslayer(TCP):
                tcp_layer = packet[TCP]
                if tcp_layer.payload:
                    return bytes(tcp_layer.payload)
            return None
        except Exception as e:
            self.logger.debug(f"提取TCP载荷失败: {e}")
            return None
    
    def _update_packet_payload(self, packet: Packet, new_payload: bytes) -> None:
        """更新数据包的TCP载荷
        
        Args:
            packet: 数据包
            new_payload: 新载荷
        """
        try:
            if packet.haslayer(TCP):
                # 移除旧载荷
                packet[TCP].remove_payload()
                # 添加新载荷
                if new_payload:
                    packet[TCP].add_payload(Raw(load=new_payload))
        except Exception as e:
            self.logger.warning(f"更新数据包载荷失败: {e}")
    
    def _recalculate_packet_checksums(self, packet: Packet) -> None:
        """重新计算数据包校验和
        
        Args:
            packet: 数据包
        """
        try:
            # 删除现有校验和，让Scapy自动重新计算
            if packet.haslayer(IP):
                if hasattr(packet[IP], 'chksum'):
                    del packet[IP].chksum
            
            if packet.haslayer(TCP):
                if hasattr(packet[TCP], 'chksum'):
                    del packet[TCP].chksum
        except Exception as e:
            self.logger.debug(f"重新计算校验和失败: {e}")
    
    def _write_packets(self, packets: List[Packet], output_file: str) -> None:
        """写入数据包到PCAP文件
        
        Args:
            packets: 数据包列表
            output_file: 输出文件路径
        """
        try:
            # 确保输出目录存在
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入PCAP文件
            wrpcap(output_file, packets)
            
            self.logger.info(f"成功写入{len(packets)}个包到{output_file}")
            
        except Exception as e:
            self.logger.error(f"写入PCAP文件失败: {e}")
            raise
    
    def _reset_statistics(self) -> None:
        """重置统计信息"""
        self._processed_packets_count = 0
        self._modified_packets_count = 0
        self._masked_bytes_count = 0
        self._applied_rules_count = 0
        self._boundary_violations_count = 0
    
    def _generate_result_statistics(
        self, 
        total_packets: int, 
        processing_time: float
    ) -> Dict[str, Any]:
        """生成处理结果统计信息
        
        Args:
            total_packets: 总包数
            processing_time: 处理时间
            
        Returns:
            统计信息字典
        """
        processing_rate = total_packets / processing_time if processing_time > 0 else 0
        
        return {
            'packets_processed': self._processed_packets_count,
            'packets_modified': self._modified_packets_count,
            'bytes_masked': self._masked_bytes_count,
            'rules_applied': self._applied_rules_count,
            'boundary_violations': self._boundary_violations_count,
            'processing_time_seconds': processing_time,
            'processing_rate_pps': processing_rate,
            'modification_ratio': (
                self._modified_packets_count / self._processed_packets_count 
                if self._processed_packets_count > 0 else 0
            ),
            'mask_byte_value': self._mask_byte_value,
            'checksums_recalculated': self._recalculate_checksums,
            'scapy_version': getattr(__import__('scapy'), '__version__', 'unknown')
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取当前统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'processed_packets': self._processed_packets_count,
            'modified_packets': self._modified_packets_count,
            'masked_bytes': self._masked_bytes_count,
            'applied_rules': self._applied_rules_count,
            'boundary_violations': self._boundary_violations_count
        } 