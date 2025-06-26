#!/usr/bin/env python3
"""
TCP载荷掩码器样本分析脚本

功能：
- 提取所有TCP数据包的详细信息
- 记录每个包的：序列号、载荷长度、流向、载荷内容前几字节
- 识别TLS握手包、应用数据包、其他类型包
- 生成完整的数据包清单供测试参考
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加src路径以便导入PktMask模块
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from scapy.all import rdpcap, TCP, IP, Raw, Ether
    TLS = None  # TLS扩展不可用，使用原始数据分析
except ImportError:
    print("需要安装scapy:")
    print("pip install scapy")
    sys.exit(1)

class TlsSampleAnalyzer:
    """TLS样本分析器"""
    
    def __init__(self, pcap_file):
        self.pcap_file = pcap_file
        self.packets = []
        self.flows = {}
        self.analysis_result = {
            "metadata": {
                "file": str(pcap_file),
                "analysis_time": datetime.now().isoformat(),
                "analyzer_version": "1.0"
            },
            "summary": {
                "total_packets": 0,
                "tcp_packets": 0,
                "flows": [],
                "sequence_ranges": {},
                "tls_distribution": {}
            },
            "packets": []
        }
    
    def analyze(self):
        """执行完整分析"""
        print(f"📊 开始分析PCAP文件: {self.pcap_file}")
        
        # 1. 读取数据包
        try:
            self.packets = rdpcap(str(self.pcap_file))
            print(f"✅ 成功读取 {len(self.packets)} 个数据包")
        except Exception as e:
            print(f"❌ 读取PCAP文件失败: {e}")
            return None
        
        # 2. 分析数据包
        self._analyze_packets()
        
        # 3. 生成流信息
        self._analyze_flows()
        
        # 4. 生成统计信息
        self._generate_statistics()
        
        print("✅ 分析完成")
        return self.analysis_result
    
    def _analyze_packets(self):
        """分析每个数据包"""
        tcp_count = 0
        
        for i, pkt in enumerate(self.packets, 1):
            packet_info = {
                "packet_number": i,
                "timestamp": float(pkt.time),
                "size": len(pkt)
            }
            
            # 检查是否是TCP包
            if TCP in pkt and IP in pkt:
                tcp_count += 1
                tcp_info = self._analyze_tcp_packet(pkt)
                packet_info.update(tcp_info)
                
                # 检查TLS信息
                tls_info = self._analyze_tls_packet(pkt)
                if tls_info:
                    packet_info.update(tls_info)
            else:
                packet_info["protocol"] = "非TCP"
                packet_info["notes"] = "跳过非TCP数据包"
            
            self.analysis_result["packets"].append(packet_info)
        
        self.analysis_result["summary"]["total_packets"] = len(self.packets)
        self.analysis_result["summary"]["tcp_packets"] = tcp_count
    
    def _analyze_tcp_packet(self, pkt):
        """分析TCP数据包"""
        ip_layer = pkt[IP]
        tcp_layer = pkt[TCP]
        
        # 生成流ID (方向性)
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst
        src_port = tcp_layer.sport
        dst_port = tcp_layer.dport
        
        # 确定流方向 (根据端口443判断客户端/服务器)
        if dst_port == 443:
            direction = "forward"  # 客户端→服务器
            stream_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}"
        elif src_port == 443:
            direction = "reverse"  # 服务器→客户端
            stream_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}_{direction}"
        else:
            direction = "unknown"
            stream_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}"
        
        # 获取载荷信息
        payload_info = self._get_payload_info(pkt)
        
        tcp_info = {
            "protocol": "TCP",
            "stream_id": stream_id,
            "direction": direction,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_port": src_port,
            "dst_port": dst_port,
            "sequence": tcp_layer.seq,
            "ack": tcp_layer.ack,
            "flags": str(tcp_layer.flags),
            **payload_info
        }
        
        # 记录流信息
        if stream_id not in self.flows:
            self.flows[stream_id] = {
                "packets": [],
                "sequence_range": {"min": tcp_layer.seq, "max": tcp_layer.seq},
                "total_payload": 0
            }
        
        self.flows[stream_id]["packets"].append(len(self.analysis_result["packets"]) + 1)
        if payload_info["payload_length"] > 0:
            seq_end = tcp_layer.seq + payload_info["payload_length"]
            self.flows[stream_id]["sequence_range"]["max"] = max(
                self.flows[stream_id]["sequence_range"]["max"], seq_end
            )
            self.flows[stream_id]["total_payload"] += payload_info["payload_length"]
        
        return tcp_info
    
    def _get_payload_info(self, pkt):
        """获取载荷信息"""
        # 查找Raw层或应用层数据
        payload_data = None
        payload_length = 0
        
        if Raw in pkt:
            payload_data = bytes(pkt[Raw])
            payload_length = len(payload_data)
        elif TLS and TLS in pkt:
            # TLS层存在，获取TLS数据
            tls_layer = pkt[TLS]
            payload_data = bytes(tls_layer)
            payload_length = len(payload_data)
        
        # 生成载荷预览（前16字节的十六进制）
        payload_preview = ""
        if payload_data and len(payload_data) > 0:
            preview_bytes = payload_data[:16]
            payload_preview = preview_bytes.hex()
        
        return {
            "payload_length": payload_length,
            "payload_preview": payload_preview,
            "has_payload": payload_length > 0
        }
    
    def _analyze_tls_packet(self, pkt):
        """分析TLS信息"""
        tls_info = {}
        
        # 检查是否有载荷
        if not (Raw in pkt or (TLS and TLS in pkt)):
            return None
        
        # 获取载荷数据
        payload_data = None
        if Raw in pkt:
            payload_data = bytes(pkt[Raw])
        elif TLS and TLS in pkt:
            payload_data = bytes(pkt[TLS])
        
        if not payload_data or len(payload_data) < 5:
            return None
        
        # 分析TLS记录头 (5字节: Content Type + Version + Length)
        content_type = payload_data[0]
        version = int.from_bytes(payload_data[1:3], 'big')
        record_length = int.from_bytes(payload_data[3:5], 'big')
        
        # TLS Content Type映射
        content_types = {
            20: "ChangeCipherSpec",
            21: "Alert", 
            22: "Handshake",
            23: "ApplicationData",
            24: "Heartbeat"
        }
        
        tls_type = content_types.get(content_type, f"Unknown({content_type})")
        
        tls_info.update({
            "tls_content_type": content_type,
            "tls_type": tls_type,
            "tls_version": f"0x{version:04x}",
            "tls_record_length": record_length
        })
        
        # 如果是握手包，进一步分析握手类型
        if content_type == 22 and len(payload_data) > 5:
            handshake_type = payload_data[5]
            handshake_types = {
                0: "HelloRequest",
                1: "ClientHello",
                2: "ServerHello", 
                11: "Certificate",
                12: "ServerKeyExchange",
                13: "CertificateRequest",
                14: "ServerHelloDone",
                15: "CertificateVerify",
                16: "ClientKeyExchange",
                20: "Finished"
            }
            
            handshake_name = handshake_types.get(handshake_type, f"Unknown({handshake_type})")
            tls_info.update({
                "tls_handshake_type": handshake_type,
                "tls_handshake_name": handshake_name,
                "notes": f"TLS {handshake_name}"
            })
        elif content_type == 23:
            tls_info["notes"] = "TLS应用数据"
        else:
            tls_info["notes"] = f"TLS {tls_type}"
        
        return tls_info
    
    def _analyze_flows(self):
        """分析流信息"""
        flow_list = []
        sequence_ranges = {}
        
        for stream_id, flow_data in self.flows.items():
            flow_summary = {
                "stream_id": stream_id,
                "packet_count": len(flow_data["packets"]),
                "packet_numbers": flow_data["packets"],
                "sequence_start": flow_data["sequence_range"]["min"],
                "sequence_end": flow_data["sequence_range"]["max"],
                "total_payload_bytes": flow_data["total_payload"]
            }
            flow_list.append(flow_summary)
            sequence_ranges[stream_id] = flow_data["sequence_range"]
        
        self.analysis_result["summary"]["flows"] = flow_list
        self.analysis_result["summary"]["sequence_ranges"] = sequence_ranges
    
    def _generate_statistics(self):
        """生成统计信息"""
        tls_distribution = {}
        
        for packet in self.analysis_result["packets"]:
            if "tls_type" in packet:
                tls_type = packet["tls_type"]
                if tls_type not in tls_distribution:
                    tls_distribution[tls_type] = 0
                tls_distribution[tls_type] += 1
        
        self.analysis_result["summary"]["tls_distribution"] = tls_distribution
    
    def save_result(self, output_file):
        """保存分析结果到JSON文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.analysis_result, f, indent=2, ensure_ascii=False)
            print(f"✅ 分析结果已保存到: {output_file}")
            return True
        except Exception as e:
            print(f"❌ 保存分析结果失败: {e}")
            return False
    
    def print_summary(self):
        """打印分析摘要"""
        summary = self.analysis_result["summary"]
        
        print("\n" + "="*60)
        print("📊 TLS样本分析摘要")
        print("="*60)
        print(f"📁 文件: {self.analysis_result['metadata']['file']}")
        print(f"📦 总数据包: {summary['total_packets']}")
        print(f"🌐 TCP数据包: {summary['tcp_packets']}")
        print(f"🔄 TCP流: {len(summary['flows'])}")
        
        print(f"\n🔍 TLS包类型分布:")
        for tls_type, count in summary.get('tls_distribution', {}).items():
            print(f"  • {tls_type}: {count}个")
        
        print(f"\n📊 TCP流详情:")
        for flow in summary['flows']:
            print(f"  • {flow['stream_id']}")
            print(f"    包数量: {flow['packet_count']}")
            print(f"    包序号: {flow['packet_numbers']}")
            print(f"    序列号范围: {flow['sequence_start']} - {flow['sequence_end']}")
            print(f"    载荷总字节: {flow['total_payload_bytes']}")
            print()


def main():
    """主函数"""
    # 设置文件路径
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    sample_file = project_root / "tests" / "data" / "tls-single" / "tls_sample.pcap"
    output_file = script_dir / "tls_sample_analysis.json"
    
    # 检查样本文件
    if not sample_file.exists():
        print(f"❌ 样本文件不存在: {sample_file}")
        return 1
    
    # 执行分析
    analyzer = TlsSampleAnalyzer(sample_file)
    result = analyzer.analyze()
    
    if result is None:
        print("❌ 分析失败")
        return 1
    
    # 打印摘要
    analyzer.print_summary()
    
    # 保存结果
    if analyzer.save_result(output_file):
        print(f"\n✅ 阶段1完成！分析结果保存到: {output_file}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main()) 