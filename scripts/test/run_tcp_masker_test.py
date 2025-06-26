#!/usr/bin/env python3
"""
自定义TCP载荷掩码器测试脚本
支持用户自定义输入文件、输出文件和掩码配置

使用方法:
    python3 run_tcp_masker_test.py --input input.pcap --output output.pcap [选项]

示例:
    # 基础测试
    python3 run_tcp_masker_test.py --input tests/data/tls-single/tls_sample.pcap --output masked_output.pcap
    
    # 指定掩码类型和参数
    python3 run_tcp_masker_test.py --input input.pcap --output output.pcap --mask-type mask_after --keep-bytes 10
    
    # 批量处理多个包
    python3 run_tcp_masker_test.py --input input.pcap --output output.pcap --packet-range 0-5
"""

import os
import sys
import argparse
import time
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def parse_packet_range(range_str):
    """解析包范围字符串，如 '0-5' 或 '1,3,5' 或 'all'"""
    if range_str == 'all':
        return None  # 表示处理所有包
    
    if '-' in range_str:
        start, end = map(int, range_str.split('-'))
        return list(range(start, end + 1))
    elif ',' in range_str:
        return [int(x.strip()) for x in range_str.split(',')]
    else:
        return [int(range_str)]

def create_masking_recipe(input_file, mask_type, keep_bytes, packet_range, payload_offset):
    """创建掩码配方"""
    from scapy.all import rdpcap
    from pktmask.core.tcp_payload_masker import PacketMaskInstruction, MaskingRecipe
    from pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll
    
    # 读取输入文件获取包信息
    print(f"📁 读取输入文件: {input_file}")
    packets = rdpcap(input_file)
    print(f"📦 文件包含 {len(packets)} 个数据包")
    
    # 确定要处理的包索引
    if packet_range is None:
        packet_indices = list(range(len(packets)))
    else:
        packet_indices = [i for i in packet_range if i < len(packets)]
    
    print(f"🎯 将处理包索引: {packet_indices}")
    
    # 创建掩码规范
    if mask_type == 'mask_after':
        mask_spec = MaskAfter(keep_bytes=keep_bytes)
    elif mask_type == 'mask_range':
        # 示例范围掩码：从keep_bytes位置开始掩码20字节
        ranges = [(keep_bytes, keep_bytes + 20)]  # (start, end) 元组格式
        mask_spec = MaskRange(ranges=ranges)
    elif mask_type == 'keep_all':
        mask_spec = KeepAll()
    else:
        raise ValueError(f"不支持的掩码类型: {mask_type}")
    
    print(f"🔧 掩码类型: {mask_type}")
    print(f"🔧 掩码参数: {mask_spec}")
    
    # 创建指令字典
    instructions = {}
    
    for i in packet_indices:
        packet = packets[i]
        
        instruction = PacketMaskInstruction(
            packet_index=i,
            packet_timestamp=str(packet.time),
            payload_offset=payload_offset,
            mask_spec=mask_spec
        )
        
        key = (i, str(packet.time))
        instructions[key] = instruction
    
    # 创建配方
    recipe = MaskingRecipe(
        instructions=instructions,
        total_packets=len(packets),
        metadata={
            "test_type": "custom",
            "mask_type": mask_type,
            "keep_bytes": keep_bytes,
            "payload_offset": payload_offset,
            "packet_indices": packet_indices,
            "source_file": input_file
        }
    )
    
    print(f"✅ 掩码配方创建完成，包含 {len(instructions)} 个指令")
    return recipe

def run_masking_test(input_file, output_file, recipe, verify_consistency=False):
    """运行掩码测试"""
    from pktmask.core.tcp_payload_masker import mask_pcap_with_instructions
    from scapy.all import rdpcap
    
    print(f"\n🚀 开始执行掩码处理")
    print(f"📥 输入文件: {input_file}")
    print(f"📤 输出文件: {output_file}")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📁 创建输出目录: {output_dir}")
    
    # 执行掩码处理
    start_time = time.time()
    
    result = mask_pcap_with_instructions(
        input_file=input_file,
        output_file=output_file,
        masking_recipe=recipe,
        verify_consistency=verify_consistency
    )
    
    processing_time = time.time() - start_time
    
    # 显示结果
    print(f"\n📊 处理结果:")
    print(f"  ✅ 成功: {result.success}")
    print(f"  ⏱️  处理时间: {processing_time:.3f}秒")
    print(f"  📦 处理包数: {result.processed_packets}")
    print(f"  🔧 修改包数: {result.modified_packets}")
    print(f"  📁 输出文件: {result.output_file}")
    
    if result.errors:
        print(f"  ⚠️  错误信息:")
        for error in result.errors:
            print(f"    - {error}")
    
    # 验证输出文件
    if os.path.exists(output_file):
        output_packets = rdpcap(output_file)
        input_packets = rdpcap(input_file)
        
        print(f"\n📋 文件对比:")
        print(f"  📥 输入包数: {len(input_packets)}")
        print(f"  📤 输出包数: {len(output_packets)}")
        print(f"  📏 文件大小: {os.path.getsize(input_file)} -> {os.path.getsize(output_file)} 字节")
        
        if processing_time > 0:
            pps = len(input_packets) / processing_time
            print(f"  🚀 处理速度: {pps:.1f} pps")
    
    return result

def save_recipe_to_file(recipe, filename):
    """保存掩码配方到JSON文件"""
    recipe_dict = {
        "total_packets": recipe.total_packets,
        "metadata": recipe.metadata,
        "instructions": []
    }
    
    for (index, timestamp), instruction in recipe.instructions.items():
        inst_dict = {
            "packet_index": instruction.packet_index,
            "packet_timestamp": instruction.packet_timestamp,
            "payload_offset": instruction.payload_offset,
            "mask_spec_type": type(instruction.mask_spec).__name__,
            "mask_spec_params": {}
        }
        
        # 根据掩码类型保存参数
        if hasattr(instruction.mask_spec, 'keep_bytes'):
            inst_dict["mask_spec_params"]["keep_bytes"] = instruction.mask_spec.keep_bytes
        elif hasattr(instruction.mask_spec, 'ranges'):
            inst_dict["mask_spec_params"]["ranges"] = [
                {"start": r[0], "end": r[1]} for r in instruction.mask_spec.ranges
            ]
        
        recipe_dict["instructions"].append(inst_dict)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(recipe_dict, f, indent=2, ensure_ascii=False)
    
    print(f"💾 掩码配方已保存到: {filename}")

def load_recipe_from_file(filename):
    """从JSON文件加载掩码配方"""
    from pktmask.core.tcp_payload_masker import PacketMaskInstruction, MaskingRecipe
    from pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll
    
    print(f"📄 加载掩码配方: {filename}")
    
    if not os.path.exists(filename):
        raise FileNotFoundError(f"配方文件不存在: {filename}")
    
    with open(filename, 'r', encoding='utf-8') as f:
        recipe_dict = json.load(f)
    
    instructions = {}
    
    for inst_dict in recipe_dict["instructions"]:
        # 重建mask_spec对象
        mask_spec_type = inst_dict["mask_spec_type"]
        mask_spec_params = inst_dict["mask_spec_params"]
        
        if mask_spec_type == "MaskAfter":
            mask_spec = MaskAfter(keep_bytes=mask_spec_params["keep_bytes"])
        elif mask_spec_type == "MaskRange":
            ranges = [(r["start"], r["end"]) for r in mask_spec_params["ranges"]]
            mask_spec = MaskRange(ranges=ranges)
        elif mask_spec_type == "KeepAll":
            mask_spec = KeepAll()
        else:
            raise ValueError(f"不支持的掩码类型: {mask_spec_type}")
        
        # 创建指令对象
        instruction = PacketMaskInstruction(
            packet_index=inst_dict["packet_index"],
            packet_timestamp=inst_dict["packet_timestamp"],
            payload_offset=inst_dict["payload_offset"],
            mask_spec=mask_spec
        )
        
        key = (inst_dict["packet_index"], inst_dict["packet_timestamp"])
        instructions[key] = instruction
    
    # 重建配方对象
    recipe = MaskingRecipe(
        instructions=instructions,
        total_packets=recipe_dict["total_packets"],
        metadata=recipe_dict["metadata"]
    )
    
    print(f"✅ 成功加载配方，包含 {len(instructions)} 个指令")
    print(f"📋 配方元数据: {recipe.metadata}")
    
    return recipe

def analyze_recipe(recipe):
    """分析掩码配方的详细信息"""
    print(f"\n🔍 **掩码配方详细分析**")
    print(f"=" * 60)
    
    # 基础信息
    print(f"📦 总包数: {recipe.total_packets}")
    print(f"🔧 指令数: {len(recipe.instructions)}")
    print(f"📄 元数据: {recipe.metadata}")
    
    # 按掩码类型分组统计
    mask_type_stats = {}
    payload_offset_stats = {}
    packet_indices = []
    
    for (packet_index, timestamp), instruction in recipe.instructions.items():
        mask_type = type(instruction.mask_spec).__name__
        mask_type_stats[mask_type] = mask_type_stats.get(mask_type, 0) + 1
        
        offset = instruction.payload_offset
        payload_offset_stats[offset] = payload_offset_stats.get(offset, 0) + 1
        
        packet_indices.append(packet_index)
    
    print(f"\n📊 **掩码类型分布:**")
    for mask_type, count in mask_type_stats.items():
        print(f"  {mask_type}: {count} 个包")
    
    print(f"\n📏 **载荷偏移分布:**")
    for offset, count in payload_offset_stats.items():
        print(f"  偏移 {offset}: {count} 个包")
    
    print(f"\n🎯 **包索引范围:** {min(packet_indices)} - {max(packet_indices)}")
    
    # 显示前5个指令的详细信息
    print(f"\n🔧 **前5个指令详情:**")
    for i, ((packet_index, timestamp), instruction) in enumerate(list(recipe.instructions.items())[:5]):
        print(f"  指令 {i+1}:")
        print(f"    包索引: {packet_index}")
        print(f"    时间戳: {timestamp}")
        print(f"    载荷偏移: {instruction.payload_offset}")
        print(f"    掩码类型: {type(instruction.mask_spec).__name__}")
        if hasattr(instruction.mask_spec, 'keep_bytes'):
            print(f"    保留字节: {instruction.mask_spec.keep_bytes}")
        elif hasattr(instruction.mask_spec, 'ranges'):
            print(f"    掩码范围: {instruction.mask_spec.ranges}")
    
    if len(recipe.instructions) > 5:
        print(f"  ... 还有 {len(recipe.instructions) - 5} 个指令")

def create_custom_recipe_interactively():
    """交互式创建自定义掩码配方"""
    from pktmask.core.tcp_payload_masker import PacketMaskInstruction, MaskingRecipe
    from pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll
    
    print(f"\n🎨 **交互式掩码配方创建**")
    print(f"=" * 60)
    
    # 获取基本信息
    total_packets = int(input("📦 请输入总包数: "))
    
    instructions = {}
    
    while True:
        print(f"\n➕ **添加新指令** (当前已有 {len(instructions)} 个指令)")
        
        try:
            packet_index = int(input("包索引: "))
            packet_timestamp = input("包时间戳: ")
            payload_offset = int(input("载荷偏移: "))
            
            print("掩码类型: 1) MaskAfter  2) MaskRange  3) KeepAll")
            mask_choice = int(input("选择 (1-3): "))
            
            if mask_choice == 1:
                keep_bytes = int(input("保留字节数: "))
                mask_spec = MaskAfter(keep_bytes=keep_bytes)
            elif mask_choice == 2:
                ranges_str = input("掩码范围 (格式: start1,end1;start2,end2): ")
                ranges = []
                for range_str in ranges_str.split(';'):
                    start, end = map(int, range_str.split(','))
                    ranges.append((start, end))
                mask_spec = MaskRange(ranges=ranges)
            elif mask_choice == 3:
                mask_spec = KeepAll()
            else:
                print("❌ 无效选择")
                continue
            
            instruction = PacketMaskInstruction(
                packet_index=packet_index,
                packet_timestamp=packet_timestamp,
                payload_offset=payload_offset,
                mask_spec=mask_spec
            )
            
            key = (packet_index, packet_timestamp)
            instructions[key] = instruction
            
            print(f"✅ 指令已添加: 包{packet_index}, {type(mask_spec).__name__}")
            
        except (ValueError, KeyboardInterrupt) as e:
            print(f"⚠️ 输入错误或中断: {e}")
            break
        
        continue_choice = input("\n继续添加指令? (y/n): ").lower().strip()
        if continue_choice != 'y':
            break
    
    # 创建配方
    recipe = MaskingRecipe(
        instructions=instructions,
        total_packets=total_packets,
        metadata={
            "test_type": "interactive_custom",
            "created_instructions": len(instructions)
        }
    )
    
    print(f"\n✅ 自定义配方创建完成，包含 {len(instructions)} 个指令")
    return recipe

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="自定义TCP载荷掩码器测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基础测试
  python3 run_tcp_masker_test.py --input tests/data/tls-single/tls_sample.pcap --output output.pcap
  
  # 保留前10字节，其余置零
  python3 run_tcp_masker_test.py --input input.pcap --output output.pcap --mask-type mask_after --keep-bytes 10
  
  # 只处理前5个包
  python3 run_tcp_masker_test.py --input input.pcap --output output.pcap --packet-range 0-4
  
  # 处理指定包
  python3 run_tcp_masker_test.py --input input.pcap --output output.pcap --packet-range 1,3,5
        """
    )
    
    # 必需参数
    parser.add_argument('--input', '-i', required=True,
                       help='输入PCAP文件路径')
    parser.add_argument('--output', '-o', required=True,
                       help='输出PCAP文件路径')
    
    # 可选参数
    parser.add_argument('--mask-type', choices=['mask_after', 'mask_range', 'keep_all'],
                       default='mask_after', help='掩码类型 (默认: mask_after)')
    parser.add_argument('--keep-bytes', type=int, default=5,
                       help='保留字节数 (默认: 5)')
    parser.add_argument('--payload-offset', type=int, default=54,
                       help='TCP载荷偏移量 (默认: 54)')
    parser.add_argument('--packet-range', default='all',
                       help='处理包范围，如 "0-5" 或 "1,3,5" 或 "all" (默认: all)')
    parser.add_argument('--verify-consistency', action='store_true',
                       help='启用一致性验证')
    parser.add_argument('--save-recipe', 
                       help='保存掩码配方到JSON文件')
    parser.add_argument('--load-recipe', 
                       help='从JSON文件加载掩码配方')
    parser.add_argument('--analyze-recipe', action='store_true',
                       help='分析掩码配方的详细信息')
    parser.add_argument('--interactive', action='store_true',
                       help='交互式创建自定义掩码配方')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    
    args = parser.parse_args()
    
    # 验证输入文件
    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在: {args.input}")
        return 1
    
    print("🚀 自定义TCP载荷掩码器测试")
    print("=" * 60)
    print(f"📥 输入文件: {args.input}")
    print(f"📤 输出文件: {args.output}")
    print(f"🔧 掩码类型: {args.mask_type}")
    print(f"🔧 保留字节: {args.keep_bytes}")
    print(f"🔧 载荷偏移: {args.payload_offset}")
    print(f"🎯 包范围: {args.packet_range}")
    
    try:
        recipe = None
        
        # 交互式创建配方模式
        if args.interactive:
            recipe = create_custom_recipe_interactively()
            if args.save_recipe:
                save_recipe_to_file(recipe, args.save_recipe)
        
        # 加载外部配方模式
        elif args.load_recipe:
            recipe = load_recipe_from_file(args.load_recipe)
        
        # 自动生成配方模式
        else:
            # 解析包范围
            packet_range = parse_packet_range(args.packet_range)
            
            # 创建掩码配方
            recipe = create_masking_recipe(
                input_file=args.input,
                mask_type=args.mask_type,
                keep_bytes=args.keep_bytes,
                packet_range=packet_range,
                payload_offset=args.payload_offset
            )
            
            # 保存配方（如果指定）
            if args.save_recipe:
                save_recipe_to_file(recipe, args.save_recipe)
        
        # 分析配方（如果启用）
        if args.analyze_recipe:
            analyze_recipe(recipe)
        
        # 执行掩码处理
        result = run_masking_test(
            input_file=args.input,
            output_file=args.output,
            recipe=recipe,
            verify_consistency=args.verify_consistency
        )
        
        if result.success:
            print("\n🎉 测试成功完成！")
            print(f"✅ 输出文件已生成: {args.output}")
            return 0
        else:
            print("\n❌ 测试失败")
            return 1
            
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 