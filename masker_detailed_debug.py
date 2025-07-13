#!/usr/bin/env python3
"""
Masker详细调试脚本

专门调试Masker模块为什么Frame 15没有被处理
"""

import json
import sys
import tempfile
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker


class DebugPayloadMasker(PayloadMasker):
    """调试版本的PayloadMasker，添加详细日志"""
    
    def __init__(self, config):
        super().__init__(config)
        self.debug_info = []
    
    def _process_packet(self, packet, rule_lookup):
        """重写_process_packet方法，添加详细调试信息"""
        try:
            # 查找最内层的 TCP/IP
            tcp_layer, ip_layer = self._find_innermost_tcp(packet)

            if tcp_layer is None or ip_layer is None:
                self.debug_info.append({
                    "packet": "non-TCP",
                    "action": "skipped"
                })
                return packet, False

            # 构建流标识
            stream_id = self._build_stream_id(ip_layer, tcp_layer)
            direction = self._determine_flow_direction(ip_layer, tcp_layer, stream_id)

            # 获取 TCP 载荷
            payload = bytes(tcp_layer.payload) if tcp_layer.payload else b''
            
            packet_info = {
                "src": f"{ip_layer.src}:{tcp_layer.sport}",
                "dst": f"{ip_layer.dst}:{tcp_layer.dport}",
                "stream_id": stream_id,
                "direction": direction,
                "tcp_seq": tcp_layer.seq,
                "payload_length": len(payload),
                "has_payload": len(payload) > 0
            }
            
            if not payload:
                packet_info["action"] = "no_payload"
                self.debug_info.append(packet_info)
                return packet, False

            # 检查是否有匹配的规则
            if stream_id not in rule_lookup or direction not in rule_lookup[stream_id]:
                packet_info["action"] = "no_matching_rules"
                packet_info["available_streams"] = list(rule_lookup.keys())
                if stream_id in rule_lookup:
                    packet_info["available_directions"] = list(rule_lookup[stream_id].keys())
                self.debug_info.append(packet_info)
                return packet, False

            # 直接使用绝对序列号
            seq_start = tcp_layer.seq
            seq_end = tcp_layer.seq + len(payload)
            
            packet_info["seq_range"] = f"{seq_start}-{seq_end}"
            packet_info["matching_rules"] = len(rule_lookup[stream_id][direction]['keep_set'])

            # 应用保留规则
            new_payload = self._apply_keep_rules(
                payload, seq_start, seq_end,
                rule_lookup[stream_id][direction]
            )

            # 检查载荷是否发生变化
            if new_payload == payload:
                packet_info["action"] = "no_change"
                packet_info["payload_preview"] = payload[:16].hex()
                self.debug_info.append(packet_info)
                return packet, False

            # 修改数据包载荷
            packet_info["action"] = "modified"
            packet_info["original_payload_preview"] = payload[:16].hex()
            packet_info["new_payload_preview"] = new_payload[:16].hex()
            self.debug_info.append(packet_info)
            
            modified_packet = self._modify_packet_payload(packet, tcp_layer, new_payload)
            return modified_packet, True

        except Exception as e:
            error_info = {
                "action": "error",
                "error": str(e)
            }
            self.debug_info.append(error_info)
            return packet, False
    
    def _apply_keep_rules_simple(self, payload: bytes, seg_start: int, seg_end: int,
                                rule_data: dict) -> bytes:
        """重写简单规则应用方法，添加详细调试"""
        keep_set = rule_data['keep_set']

        # 创建全零缓冲区
        buf = bytearray(len(payload))
        preserved_bytes = 0
        
        debug_rule_info = {
            "method": "simple",
            "payload_length": len(payload),
            "seg_range": f"{seg_start}-{seg_end}",
            "keep_rules": list(keep_set),
            "applied_rules": []
        }
        
        # 直接遍历保留集合中的每个区间
        for keep_start, keep_end in keep_set:
            # 计算与当前段的重叠部分
            overlap_start = max(keep_start, seg_start)
            overlap_end = min(keep_end, seg_end)

            rule_application = {
                "rule_range": f"{keep_start}-{keep_end}",
                "overlap_range": f"{overlap_start}-{overlap_end}",
                "has_overlap": overlap_start < overlap_end
            }

            if overlap_start < overlap_end:
                # 有重叠，计算在载荷中的偏移
                offset_left = overlap_start - seg_start
                offset_right = overlap_end - seg_start

                # 确保偏移在载荷范围内
                offset_left = max(0, offset_left)
                offset_right = min(len(payload), offset_right)

                if offset_left < offset_right:
                    # 恢复保留区间的原始数据
                    buf[offset_left:offset_right] = payload[offset_left:offset_right]
                    preserved_bytes += offset_right - offset_left
                    
                    rule_application["offset_range"] = f"{offset_left}-{offset_right}"
                    rule_application["preserved_bytes"] = offset_right - offset_left
                    rule_application["applied"] = True
                else:
                    rule_application["applied"] = False
                    rule_application["reason"] = "invalid_offset"
            else:
                rule_application["applied"] = False
                rule_application["reason"] = "no_overlap"
            
            debug_rule_info["applied_rules"].append(rule_application)

        # 计算掩码字节数
        masked_bytes = len(payload) - preserved_bytes
        
        debug_rule_info["preserved_bytes"] = preserved_bytes
        debug_rule_info["masked_bytes"] = masked_bytes
        debug_rule_info["original_preview"] = payload[:16].hex()
        debug_rule_info["result_preview"] = bytes(buf)[:16].hex()
        
        # 保存调试信息
        if not hasattr(self, 'rule_debug_info'):
            self.rule_debug_info = []
        self.rule_debug_info.append(debug_rule_info)
        
        # 更新统计信息（如果有的话）
        if hasattr(self, '_current_stats') and self._current_stats:
            self._current_stats.preserved_bytes += preserved_bytes
            self._current_stats.masked_bytes += masked_bytes
        
        # 总是返回处理后的载荷（全零缓冲区 + 保留区间的原始数据）
        return bytes(buf)


def debug_masker_processing():
    """调试Masker处理过程"""
    print("=" * 80)
    print("Masker详细处理调试")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    config = {
        'preserve': {
            'handshake': True,
            'application_data': False,
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        }
    }
    
    # 1. 生成KeepRuleSet
    print("\n1. 生成KeepRuleSet")
    print("-" * 50)
    
    marker = TLSProtocolMarker(config)
    ruleset = marker.analyze_file(test_file, config)
    
    print(f"生成的规则数量: {len(ruleset.rules)}")
    
    # 2. 使用调试版本的Masker
    print("\n2. 使用调试版本的Masker处理")
    print("-" * 50)
    
    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
        output_file = tmp_file.name
    
    debug_masker = DebugPayloadMasker({})
    masking_stats = debug_masker.apply_masking(test_file, output_file, ruleset)
    
    print(f"处理结果:")
    print(f"  成功: {masking_stats.success}")
    print(f"  处理包数: {masking_stats.processed_packets}")
    print(f"  修改包数: {masking_stats.modified_packets}")
    
    # 3. 分析调试信息
    print("\n3. 数据包处理详情")
    print("-" * 50)
    
    for i, info in enumerate(debug_masker.debug_info):
        if info.get("has_payload", False):
            print(f"\n包#{i+1}: {info['src']} -> {info['dst']}")
            print(f"  流ID: {info['stream_id']}, 方向: {info['direction']}")
            print(f"  序列号范围: {info['seq_range']}")
            print(f"  载荷长度: {info['payload_length']}")
            print(f"  动作: {info['action']}")
            
            if info['action'] == 'no_matching_rules':
                print(f"  可用流: {info.get('available_streams', [])}")
                print(f"  可用方向: {info.get('available_directions', [])}")
            elif info['action'] == 'modified':
                print(f"  原始载荷: {info['original_payload_preview']}")
                print(f"  新载荷: {info['new_payload_preview']}")
            elif info['action'] == 'no_change':
                print(f"  载荷预览: {info['payload_preview']}")
    
    # 4. 分析规则应用详情
    if hasattr(debug_masker, 'rule_debug_info'):
        print("\n4. 规则应用详情")
        print("-" * 50)
        
        for i, rule_info in enumerate(debug_masker.rule_debug_info):
            print(f"\n规则应用#{i+1}:")
            print(f"  载荷长度: {rule_info['payload_length']}")
            print(f"  段范围: {rule_info['seg_range']}")
            print(f"  保留规则数: {len(rule_info['keep_rules'])}")
            print(f"  保留字节数: {rule_info['preserved_bytes']}")
            print(f"  掩码字节数: {rule_info['masked_bytes']}")
            print(f"  原始预览: {rule_info['original_preview']}")
            print(f"  结果预览: {rule_info['result_preview']}")
            
            for j, applied_rule in enumerate(rule_info['applied_rules']):
                print(f"    规则#{j+1}: {applied_rule['rule_range']}")
                print(f"      重叠: {applied_rule['overlap_range']}")
                print(f"      应用: {'✅' if applied_rule['applied'] else '❌'}")
                if not applied_rule['applied']:
                    print(f"      原因: {applied_rule.get('reason', 'unknown')}")
                elif 'preserved_bytes' in applied_rule:
                    print(f"      保留字节: {applied_rule['preserved_bytes']}")
    
    return {
        "masking_stats": {
            "success": masking_stats.success,
            "processed_packets": masking_stats.processed_packets,
            "modified_packets": masking_stats.modified_packets,
            "masked_bytes": masking_stats.masked_bytes,
            "preserved_bytes": masking_stats.preserved_bytes
        },
        "debug_info": debug_masker.debug_info,
        "rule_debug_info": getattr(debug_masker, 'rule_debug_info', [])
    }


def main():
    """主函数"""
    try:
        results = debug_masker_processing()
        
        # 保存调试结果
        with open("masker_detailed_debug_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n详细调试结果已保存到: masker_detailed_debug_results.json")
        
    except Exception as e:
        print(f"❌ 详细调试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
