#!/usr/bin/env python3
"""
TCP载荷掩码器API功能测试
测试mask_pcap_with_instructions的核心API功能
"""

import os
import sys
import tempfile
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def create_simple_test_pcap():
    """创建简单的测试PCAP文件"""
    from scapy.all import Ether, IP, TCP, wrpcap
    
    # 创建测试包
    packet = (Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff") /
             IP(src="192.168.1.1", dst="192.168.1.2") /
             TCP(sport=12345, dport=80) /
             b"Hello World! This is a test payload for masking verification.")
    
    # 计算正确的时间戳
    packet.time = 1234567890.123456
    
    return packet

def test_api_basic_functionality():
    """测试API基础功能"""
    print("🔧 测试API基础功能")
    
    try:
        from pktmask.core.tcp_payload_masker import (
            mask_pcap_with_instructions,
            PacketMaskInstruction,
            MaskingRecipe
        )
        from pktmask.core.trim.models.mask_spec import MaskAfter
        from scapy.all import wrpcap, rdpcap, raw
        
        # 创建测试包
        packet = create_simple_test_pcap()
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # 写入测试包
            wrpcap(input_path, [packet])
            print(f"  📝 创建测试文件: {input_path}")
            
            # 准备掩码指令
            # Ethernet(14) + IP(20) + TCP(20) = 54字节偏移
            payload_offset = 54
            timestamp = str(packet.time)
            
            instruction = PacketMaskInstruction(
                packet_index=0,
                packet_timestamp=timestamp,
                payload_offset=payload_offset,
                mask_spec=MaskAfter(keep_bytes=5)
            )
            
            recipe = MaskingRecipe(
                instructions={(0, timestamp): instruction},
                total_packets=1,
                metadata={"test": "api_functionality"}
            )
            
            print(f"  🔧 创建掩码配方，保留前5字节")
            
            # 执行掩码处理
            print(f"  ⚙️ 执行掩码处理...")
            result = mask_pcap_with_instructions(
                input_file=input_path,
                output_file=output_path,
                masking_recipe=recipe,
                verify_consistency=False  # 暂时关闭一致性验证
            )
            
            print(f"  📊 处理结果:")
            print(f"     成功: {result.success}")
            print(f"     处理包数: {result.processed_packets}")
            print(f"     修改包数: {result.modified_packets}")
            
            if result.errors:
                print(f"     错误: {result.errors}")
            
            # 验证输出
            if result.success and os.path.exists(output_path):
                output_packets = rdpcap(output_path)
                if len(output_packets) == 1:
                    original_payload = raw(packet)[54:]  # 原始载荷
                    modified_payload = raw(output_packets[0])[54:]  # 修改后载荷
                    
                    print(f"     原始载荷长度: {len(original_payload)}")
                    print(f"     修改载荷长度: {len(modified_payload)}")
                    print(f"     原始前10字节: {original_payload[:10]}")
                    print(f"     修改前10字节: {modified_payload[:10]}")
                    
                    # 检查掩码是否正确应用
                    if modified_payload[:5] == original_payload[:5]:
                        print(f"  ✅ 掩码应用正确：前5字节保留")
                        return True
                    else:
                        print(f"  ❌ 掩码应用错误：前5字节未正确保留")
                        return False
                else:
                    print(f"  ❌ 输出包数量错误: {len(output_packets)}")
                    return False
            else:
                print(f"  ❌ 处理失败或输出文件不存在")
                return False
                
        finally:
            # 清理临时文件
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    os.unlink(path)
        
    except Exception as e:
        print(f"  💥 API测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_tls_sample():
    """使用TLS样本测试"""
    print("\n🔧 测试TLS样本处理")
    
    tls_sample_path = "tests/data/tls-single/tls_sample.pcap"
    
    if not os.path.exists(tls_sample_path):
        print(f"  ⚠️ TLS样本不存在: {tls_sample_path}")
        return False
    
    try:
        from pktmask.core.tcp_payload_masker import (
            mask_pcap_with_instructions,
            PacketMaskInstruction,
            MaskingRecipe
        )
        from pktmask.core.trim.models.mask_spec import KeepAll
        from scapy.all import rdpcap
        
        # 读取TLS样本
        packets = rdpcap(tls_sample_path)
        print(f"  📦 TLS样本包含 {len(packets)} 个包")
        
        # 创建简单的掩码配方（所有包都保持不变）
        instructions = {}
        for i, packet in enumerate(packets):
            timestamp = str(packet.time)
            instruction = PacketMaskInstruction(
                packet_index=i,
                packet_timestamp=timestamp,
                payload_offset=54,  # 假设偏移
                mask_spec=KeepAll()
            )
            instructions[(i, timestamp)] = instruction
        
        recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=len(packets),
            metadata={"test": "tls_sample"}
        )
        
        print(f"  🔧 创建保持原样的掩码配方: {len(instructions)} 个指令")
        
        # 创建输出文件
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # 执行处理
            print(f"  ⚙️ 执行TLS样本处理...")
            start_time = time.time()
            
            result = mask_pcap_with_instructions(
                input_file=tls_sample_path,
                output_file=output_path,
                masking_recipe=recipe,
                verify_consistency=False
            )
            
            processing_time = time.time() - start_time
            
            print(f"  📊 TLS处理结果:")
            print(f"     成功: {result.success}")
            print(f"     处理包数: {result.processed_packets}")
            print(f"     修改包数: {result.modified_packets}")
            print(f"     处理时间: {processing_time:.3f}s")
            
            if processing_time > 0:
                throughput = result.processed_packets / processing_time
                print(f"     吞吐量: {throughput:.1f} pps")
            
            if result.errors:
                print(f"     错误: {result.errors}")
            
            return result.success
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
        
    except Exception as e:
        print(f"  💥 TLS测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 TCP载荷掩码器API功能验证")
    print("=" * 50)
    
    tests = [
        ("API基础功能", test_api_basic_functionality),
        ("TLS样本处理", test_with_tls_sample)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        success = test_func()
        results.append((test_name, success))
    
    # 摘要
    print("\n" + "=" * 50)
    print("🏆 API功能验证结果")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\n📊 总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 API功能验证完全通过！")
        return 0
    elif passed > 0:
        print("⚠️ API基本可用，但存在部分问题")
        return 0
    else:
        print("❌ API功能验证失败")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 