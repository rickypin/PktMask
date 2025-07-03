#!/usr/bin/env python3
"""
TLS-23跨包长消息掩码调试测试脚本

用途：
1. 测试新增的详细调试日志是否正常工作
2. 验证TLS-23跨包处理的三个阶段
3. 提供问题排查的快速验证工具

使用方法：
python scripts/debug_tls23_cross_packet.py <input.pcap> [output.pcap]
"""

import sys
import logging
import time
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
from src.pktmask.core.processors.base_processor import ProcessorConfig
from src.pktmask.config.settings import AppConfig

def override_enhanced_config_for_debug():
    """临时覆盖增强配置以启用调试功能"""
    try:
        # 直接修改配置文件中的调试选项
        from pathlib import Path
        import yaml
        
        config_path = Path("config/default/mask_config.yaml")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 确保tools.tshark_enhanced部分存在
            if 'tools' not in config:
                config['tools'] = {}
            if 'tshark_enhanced' not in config['tools']:
                config['tools']['tshark_enhanced'] = {}
            
            # 启用详细日志记录和调试功能
            config['tools']['tshark_enhanced'].update({
                'enable_detailed_logging': True,
                'enable_performance_monitoring': True,
                'enable_boundary_safety': True,
                'enable_error_analytics': True,
                'error_report_detail_level': 'verbose'
            })
            
            # 写回配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            print("🔧 已启用增强配置的详细日志记录")
            return True
            
    except Exception as e:
        print(f"⚠️ 修改配置文件失败: {e}")
        return False


def setup_debug_logging():
    """设置详细的调试日志"""
    # 配置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 确保所有相关组件的日志都能输出
    logger_names = [
        'pktmask.core.processors.tshark_tls_analyzer',
        'pktmask.core.processors.tls_mask_rule_generator', 
        'pktmask.core.processors.scapy_mask_applier',
        'pktmask.core.processors.tshark_enhanced_mask_processor'
    ]
    
    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
    
    print("🔧 调试日志已启用，日志级别：INFO")
    print("🔧 将显示所有TLS-23跨包处理的详细日志")
    print()

def create_debug_config() -> ProcessorConfig:
    """创建用于调试的处理器配置"""
    return ProcessorConfig(
        enabled=True,
        name="tshark_enhanced_debug",
        priority=1
    )

def analyze_processing_result(result: Dict[str, Any]) -> None:
    """分析处理结果并输出统计信息"""
    print("\n" + "="*60)
    print("🔍 TLS-23跨包处理结果分析")
    print("="*60)
    
    if not result.get('success', False):
        print("❌ 处理失败")
        if 'error' in result:
            print(f"错误信息: {result['error']}")
        return
    
    stats = result.get('stats', {})
    
    print("✅ 处理成功")
    print(f"📊 TLS记录数: {stats.get('tls_records_found', 0)}")
    print(f"📊 掩码规则数: {stats.get('mask_rules_generated', 0)}")
    print(f"📊 处理包数: {stats.get('packets_processed', 0)}")
    print(f"📊 修改包数: {stats.get('packets_modified', 0)}")
    
    processing_mode = stats.get('processing_mode', 'unknown')
    print(f"📊 处理模式: {processing_mode}")
    
    if 'stage_performance' in stats:
        stage_perf = stats['stage_performance']
        print(f"⏱️  Stage 1 (TShark分析): {stage_perf.get('stage1_tshark_analysis', 0):.2f}秒")
        print(f"⏱️  Stage 2 (规则生成): {stage_perf.get('stage2_rule_generation', 0):.2f}秒") 
        print(f"⏱️  Stage 3 (掩码应用): {stage_perf.get('stage3_scapy_application', 0):.2f}秒")
        print(f"⏱️  总耗时: {stage_perf.get('total_duration', 0):.2f}秒")
    
    # 分析是否可能有TLS-23跨包处理
    if stats.get('tls_records_found', 0) > 0:
        print(f"✅ 发现TLS记录，可能包含TLS-23跨包消息")
    else:
        print("⚠️  未发现TLS记录，可能不是TLS流量文件")
    
    if stats.get('packets_modified', 0) > 0:
        print(f"✅ 有包被修改，掩码可能已应用")
    else:
        print("⚠️  没有包被修改，可能没有需要掩码的TLS-23内容")

def check_debug_log_patterns():
    """检查调试日志模式指南"""
    print("\n" + "="*60)
    print("🔍 调试日志模式检查指南") 
    print("="*60)
    print("请在上面的日志输出中查找以下关键模式：")
    print()
    
    patterns = [
        ("🔍 [TLS跨包分析]", "TShark分析阶段检测到跨包分段"),
        ("🔍 [TLS-23跨包]", "专门针对TLS-23的跨包处理"),
        ("🔧 [规则生成跨包]", "为跨包记录生成掩码规则"),
        ("🔧 [TLS-23跨包规则]", "TLS-23跨包的具体掩码规则"),
        ("🔧 [TLS-23分段规则]", "TLS-23分段包的掩码规则"),
        ("⚡ [TLS-23分段掩码]", "TLS-23分段包的掩码应用"),
        ("⚡ [TLS-23掩码]", "TLS-23常规掩码应用"),
        ("⚡ [包级掩码]", "包级别的掩码应用流程"),
        ("🚀 [TLS-23跨包处理]", "主流程的TLS-23跨包统计")
    ]
    
    for pattern, description in patterns:
        print(f"  {pattern}")
        print(f"    → {description}")
        print()
    
    print("✅ 如果看到上述日志模式，说明调试日志正常工作")
    print("❌ 如果没有看到相关模式，可能需要检查：")
    print("   1. 输入文件是否包含TLS-23跨包消息")
    print("   2. TShark是否正确安装和配置")
    print("   3. 日志级别是否设置为INFO或更详细")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python scripts/debug_tls23_cross_packet.py <input.pcap> [output.pcap]")
        print()
        print("示例:")
        print("  python scripts/debug_tls23_cross_packet.py tests/data/tls/tls_1_0_multi_segment_google-https.pcap")
        print("  python scripts/debug_tls23_cross_packet.py input.pcap debug_output.pcap")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"debug_output_{int(time.time())}.pcap"
    
    # 验证输入文件
    if not Path(input_file).exists():
        print(f"❌ 输入文件不存在: {input_file}")
        sys.exit(1)
    
    print("🚀 TLS-23跨包长消息掩码调试测试")
    print("="*60)
    print(f"📁 输入文件: {input_file}")
    print(f"📁 输出文件: {output_file}")
    print()
    
    # 启用调试配置
    override_enhanced_config_for_debug()
    
    # 设置调试日志
    setup_debug_logging()
    
    try:
        # 创建处理器配置
        config = create_debug_config()
        print(f"🔧 创建TSharkEnhancedMaskProcessor，配置: {config.name}")
        
        # 创建处理器
        processor = TSharkEnhancedMaskProcessor(config)
        
        # 初始化处理器
        print("🔧 初始化处理器...")
        if not processor.initialize():
            print("❌ 处理器初始化失败")
            sys.exit(1)
        
        print("✅ 处理器初始化成功")
        print()
        print("🚀 开始TLS-23跨包处理，请观察下面的详细日志:")
        print("-" * 60)
        
        # 处理文件
        start_time = time.time()
        result = processor.process_file(input_file, output_file)
        duration = time.time() - start_time
        
        print("-" * 60)
        print(f"⏱️  总处理时间: {duration:.2f}秒")
        
        # 分析结果
        analyze_processing_result(result.__dict__ if hasattr(result, '__dict__') else result)
        
        # 输出调试日志检查指南
        check_debug_log_patterns()
        
        # 清理资源
        if hasattr(processor, 'cleanup'):
            processor.cleanup()
        
        print(f"\n✅ 调试测试完成，输出文件: {output_file}")
        
    except Exception as e:
        print(f"\n❌ 调试测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 