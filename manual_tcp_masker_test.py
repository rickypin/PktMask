#!/usr/bin/env python3
"""
TCP载荷掩码器手动测试脚本
用于快速验证新实现的tcp_payload_masker模块的完整功能

使用方法:
    python3 manual_tcp_masker_test.py [测试类型]
    
测试类型:
    basic      - 基础功能测试
    tls        - TLS样本测试  
    custom     - 自定义测试
    all        - 运行所有测试
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def test_module_import():
    """测试模块导入"""
    print("🔧 测试1: 模块导入验证")
    try:
        from pktmask.core.tcp_payload_masker import (
            mask_pcap_with_instructions,
            get_api_version,
            PacketMaskInstruction,
            MaskingRecipe,
            PacketMaskingResult
        )
        from pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll
        
        print(f"  ✅ 模块导入成功")
        print(f"  📌 API版本: {get_api_version()}")
        return True, "模块导入成功"
        
    except ImportError as e:
        print(f"  ❌ 导入失败: {e}")
        return False, f"导入失败: {e}"

def create_simple_masking_recipe():
    """创建简单的掩码配方示例"""
    print("\n🔧 测试2: 创建掩码配方")
    
    try:
        from pktmask.core.tcp_payload_masker import (
            PacketMaskInstruction, MaskingRecipe
        )
        from pktmask.core.trim.models.mask_spec import MaskAfter
        
        # 创建简单的掩码指令
        instructions = {}
        
        # 示例：对包0应用MaskAfter(5)掩码（保留前5字节，其余置零）
        instruction = PacketMaskInstruction(
            packet_index=0,
            packet_timestamp="1234567890.123456",
            payload_offset=54,  # 假设ETH(14) + IP(20) + TCP(20) = 54字节头部
            mask_spec=MaskAfter(keep_bytes=5)
        )
        
        # 使用(index, timestamp)作为key
        key = (0, "1234567890.123456")
        instructions[key] = instruction
        
        # 创建掩码配方
        recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=1,
            metadata={"test_type": "simple_mask_after"}
        )
        
        print(f"  ✅ 掩码配方创建成功")
        print(f"  📝 包含指令数: {len(instructions)}")
        print(f"  📝 总包数: {recipe.total_packets}")
        
        return True, recipe
        
    except Exception as e:
        print(f"  ❌ 配方创建失败: {e}")
        return False, None

def test_basic_functionality():
    """测试基础功能"""
    print("\n🔧 测试3: 基础功能验证")
    
    try:
        from scapy.all import Ether, IP, TCP, wrpcap, rdpcap
        from pktmask.core.tcp_payload_masker import mask_pcap_with_instructions
        
        # 创建测试包
        test_payload = b"Hello World! This is a test payload for masking verification."
        packet = (Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff") /
                 IP(src="192.168.1.1", dst="192.168.1.2") /
                 TCP(sport=12345, dport=80) /
                 test_payload)
        
        # 设置时间戳
        packet.time = 1234567890.123456
        
        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_input:
            input_file = tmp_input.name
            wrpcap(input_file, [packet])
        
        # 创建掩码配方
        success, recipe = create_simple_masking_recipe()
        if not success:
            return False, "掩码配方创建失败"
        
        # 执行掩码处理
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_output:
            output_file = tmp_output.name
            
        result = mask_pcap_with_instructions(
            input_file=input_file,
            output_file=output_file,
            masking_recipe=recipe,
            verify_consistency=False
        )
        
        print(f"  ✅ 掩码处理完成")
        print(f"  📊 处理结果: 成功={result.success}")
        print(f"  📊 处理包数: {result.processed_packets}")
        print(f"  📊 修改包数: {result.modified_packets}")
        
        # 验证结果
        if os.path.exists(output_file):
            output_packets = rdpcap(output_file)
            print(f"  ✅ 输出文件创建成功，包含 {len(output_packets)} 个包")
            
            # 清理临时文件
            os.unlink(input_file)
            os.unlink(output_file)
        
        return True, "基础功能验证成功"
        
    except Exception as e:
        print(f"  ❌ 基础功能测试失败: {e}")
        return False, f"基础功能测试失败: {e}"

def test_tls_sample():
    """测试TLS样本文件"""
    print("\n🔧 测试4: TLS样本文件测试")
    
    tls_file = "tests/data/tls-single/tls_sample.pcap"
    if not os.path.exists(tls_file):
        print(f"  ❌ TLS样本文件不存在: {tls_file}")
        return False, "TLS样本文件不存在"
    
    try:
        from scapy.all import rdpcap
        from pktmask.core.tcp_payload_masker import (
            mask_pcap_with_instructions, PacketMaskInstruction, MaskingRecipe
        )
        from pktmask.core.trim.models.mask_spec import MaskAfter
        
        # 读取TLS样本
        packets = rdpcap(tls_file)
        print(f"  📁 TLS样本包含 {len(packets)} 个包")
        
        # 创建简单的掩码配方（对前几个包应用掩码）
        instructions = {}
        
        for i in range(min(3, len(packets))):  # 只处理前3个包
            packet = packets[i]
            instruction = PacketMaskInstruction(
                packet_index=i,
                packet_timestamp=str(packet.time),
                payload_offset=60,  # 估算的TCP载荷偏移
                mask_spec=MaskAfter(keep_bytes=5)
            )
            key = (i, str(packet.time))
            instructions[key] = instruction
        
        recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=len(packets),
            metadata={"test_type": "tls_sample", "source_file": tls_file}
        )
        
        # 执行掩码处理
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_output:
            output_file = tmp_output.name
            
        start_time = time.time()
        result = mask_pcap_with_instructions(
            input_file=tls_file,
            output_file=output_file,
            masking_recipe=recipe,
            verify_consistency=False
        )
        processing_time = time.time() - start_time
        
        print(f"  ✅ TLS样本处理完成")
        print(f"  📊 处理时间: {processing_time:.3f}秒")
        print(f"  📊 处理速度: {len(packets)/processing_time:.1f} pps")
        print(f"  📊 处理结果: 成功={result.success}")
        print(f"  📊 处理包数: {result.processed_packets}")
        print(f"  📊 修改包数: {result.modified_packets}")
        
        if result.errors:
            print(f"  ⚠️  错误信息: {result.errors}")
        
        # 验证输出文件
        if os.path.exists(output_file):
            output_packets = rdpcap(output_file)
            print(f"  ✅ 输出文件包含 {len(output_packets)} 个包")
            os.unlink(output_file)
        
        return True, "TLS样本测试成功"
        
    except Exception as e:
        print(f"  ❌ TLS样本测试失败: {e}")
        return False, f"TLS样本测试失败: {e}"

def show_usage_examples():
    """显示使用示例"""
    print("\n📚 使用示例")
    print("=" * 60)
    
    print("\n1. 基础Python API使用:")
    print("""
    from pktmask.core.tcp_payload_masker import (
        mask_pcap_with_instructions, PacketMaskInstruction, MaskingRecipe
    )
    from pktmask.core.trim.models.mask_spec import MaskAfter
    
    # 创建单个包的掩码指令
    instruction = PacketMaskInstruction(
        packet_index=0,                    # 包索引
        packet_timestamp="1234567890.123", # 时间戳
        payload_offset=54,                 # TCP载荷偏移量
        mask_spec=MaskAfter(keep_bytes=5)  # 保留前5字节
    )
    
    # 创建掩码配方
    recipe = MaskingRecipe(
        instructions={(0, "1234567890.123"): instruction},
        total_packets=1
    )
    
    # 执行掩码处理
    result = mask_pcap_with_instructions(
        input_file="input.pcap",
        output_file="output.pcap", 
        masking_recipe=recipe
    )
    """)
    
    print("\n2. 支持的掩码类型:")
    print("""
    # 保留前N字节，其余置零
    MaskAfter(keep_bytes=5)
    
    # 指定范围掩码
    MaskRange(ranges=[RangeSpec(start=10, length=20)])
    
    # 保留全部（不掩码）
    KeepAll()
    """)
    
    print("\n3. 文件路径配置:")
    print("""
    输入文件: 任何有效的PCAP/PCAPNG文件
    输出文件: 自动创建，建议使用.pcap扩展名
    
    示例:
    input_file = "tests/data/tls-single/tls_sample.pcap"
    output_file = "output/masked_tls.pcap"
    """)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TCP载荷掩码器手动测试")
    parser.add_argument('test_type', nargs='?', default='all', 
                       choices=['basic', 'tls', 'custom', 'all', 'usage'],
                       help='测试类型')
    
    args = parser.parse_args()
    
    print("🚀 TCP载荷掩码器手动测试")
    print("=" * 50)
    
    if args.test_type == 'usage':
        show_usage_examples()
        return
    
    results = []
    
    # 基础测试
    if args.test_type in ['basic', 'all']:
        success, message = test_module_import()
        results.append(('模块导入', success, message))
        
        if success:
            success, message = test_basic_functionality()
            results.append(('基础功能', success, message))
    
    # TLS测试
    if args.test_type in ['tls', 'all']:
        success, message = test_tls_sample()
        results.append(('TLS样本', success, message))
    
    # 显示结果总结
    print("\n📊 测试结果总结")
    print("=" * 50)
    
    success_count = 0
    for test_name, success, message in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name:12} | {status} | {message}")
        if success:
            success_count += 1
    
    print(f"\n总计: {success_count}/{len(results)} 个测试通过")
    
    if args.test_type in ['all', 'usage']:
        show_usage_examples()

if __name__ == "__main__":
    main() 