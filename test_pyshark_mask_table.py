#!/usr/bin/env python3
"""
独立的PyShark掩码表生成测试脚本

用于验证PyShark分析器生成的掩码表内容是否正确。
测试目标：分析 /Users/ricky/Downloads/samples/tls-single/tls_sample.pcap 并打印掩码表
"""

import sys
import os
from pathlib import Path
import json
import logging
import tempfile

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer
from src.pktmask.core.trim.stages.base_stage import StageContext
from src.pktmask.core.trim.models.simple_execution_result import SimpleExecutionResult

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PySharkMaskTableTest:
    """PyShark掩码表生成测试类"""
    
    def __init__(self):
        self.analyzer = PySharkAnalyzer()
        
    def test_mask_table_generation(self, input_file: str):
        """测试掩码表生成"""
        logger.info(f"测试PyShark掩码表生成：{input_file}")
        
        # 创建临时目录和文件
        temp_dir = tempfile.mkdtemp()
        tshark_output = os.path.join(temp_dir, "tshark_output.pcap")
        mask_table_output = os.path.join(temp_dir, "mask_table.json")
        
        # 模拟TShark输出（直接复制输入文件，因为我们主要测试PyShark）
        import shutil
        shutil.copy2(input_file, tshark_output)
        
        # 创建StageContext
        context = StageContext(
            input_file=Path(input_file),
            output_file=Path("/tmp/test_output.pcap"),
            work_dir=Path(temp_dir)
        )
        context.tshark_output = tshark_output
        context.mask_table_file = mask_table_output
        
        try:
            # 初始化PyShark分析器
            logger.info("初始化PyShark分析器...")
            if not self.analyzer.initialize():
                raise RuntimeError("PyShark分析器初始化失败")
            
            # 执行PyShark分析
            logger.info("执行PyShark分析...")
            result = self.analyzer.execute(context)
            
            logger.info(f"PyShark分析结果：{result.success}")
            processing_time = result.data.get('processing_time', 0)
            packet_count = result.data.get('packet_count', 0)
            logger.info(f"处理时间：{processing_time:.3f}秒")
            logger.info(f"处理的数据包数量：{packet_count}")
            
            # 分析掩码表（直接从上下文获取）
            if context.mask_table is not None:
                self.analyze_mask_table_object(context.mask_table)
            else:
                logger.error("掩码表对象未生成")
                
            # 分析流信息
            self.analyze_stream_info()
            
            return result
            
        except Exception as e:
            logger.error(f"测试失败：{e}")
            import traceback
            traceback.print_exc()
            return None
            
        finally:
            # 清理临时文件
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass
                
    def analyze_mask_table_object(self, mask_table):
        """分析掩码表对象内容"""
        logger.info("=" * 60)
        logger.info("掩码表内容分析")
        logger.info("=" * 60)
        
        try:
            logger.info(f"掩码表类型：{type(mask_table)}")
            logger.info(f"掩码条目总数：{mask_table.get_total_entry_count()}")
            
            # 获取所有流ID
            stream_ids = mask_table.get_stream_ids()
            logger.info(f"涉及的流数量：{len(stream_ids)}")
            
            # 详细分析每个流
            for stream_id in stream_ids:
                logger.info(f"\n流ID：{stream_id}")
                
                # 获取该流的所有条目
                stream_entries = mask_table._table.get(stream_id, [])
                logger.info(f"  条目数量：{len(stream_entries)}")
                
                # 按序列号排序
                stream_entries.sort(key=lambda x: x.seq_start)
                
                for i, entry in enumerate(stream_entries, 1):
                    seq_start = entry.seq_start
                    seq_end = entry.seq_end
                    mask_type = entry.mask_type
                    mask_spec = entry.mask_spec
                    
                    logger.info(f"    条目{i}：序列号[{seq_start}:{seq_end}), "
                               f"长度={seq_end - seq_start}, 类型={mask_type}")
                    
                    # 详细分析掩码规范
                    if mask_spec:
                        spec_type = type(mask_spec).__name__
                        logger.info(f"      掩码规范：{spec_type}")
                        
                        if hasattr(mask_spec, 'keep_bytes'):
                            keep_bytes = mask_spec.keep_bytes
                            logger.info(f"        保留前{keep_bytes}字节，其余置零")
                        elif spec_type == 'KeepAll':
                            logger.info(f"        完全保留载荷")
                        elif hasattr(mask_spec, 'ranges'):
                            ranges = mask_spec.ranges
                            logger.info(f"        置零范围：{ranges}")
                            
                    # 检查是否覆盖我们关心的序列号范围
                    if stream_id == "TCP_10.171.250.80:33492_10.50.50.161:443_forward":
                        if seq_start <= 644 < seq_end or seq_start <= 1865 < seq_end:
                            logger.info(f"      ⭐ 此条目覆盖目标序列号范围（644或1865）")
                            
        except Exception as e:
            logger.error(f"分析掩码表失败：{e}")
            import traceback
            traceback.print_exc()
            
    def analyze_stream_info(self):
        """分析流信息"""
        logger.info("\n" + "=" * 60)
        logger.info("流信息分析")
        logger.info("=" * 60)
        
        streams = self.analyzer._streams
        logger.info(f"检测到的流数量：{len(streams)}")
        
        for stream_id, stream_info in streams.items():
            logger.info(f"\n流ID：{stream_id}")
            logger.info(f"  协议：{stream_info.protocol}")
            logger.info(f"  源地址：{stream_info.src_ip}:{stream_info.src_port}")
            logger.info(f"  目标地址：{stream_info.dst_ip}:{stream_info.dst_port}")
            logger.info(f"  应用层协议：{stream_info.application_protocol}")
            logger.info(f"  数据包数量：{stream_info.packet_count}")
            logger.info(f"  总字节数：{stream_info.total_bytes}")
            
            if hasattr(stream_info, 'direction'):
                logger.info(f"  方向：{stream_info.direction}")
            if hasattr(stream_info, 'initial_seq'):
                logger.info(f"  初始序列号：{stream_info.initial_seq}")
            if hasattr(stream_info, 'last_seq'):
                logger.info(f"  最后序列号：{stream_info.last_seq}")
                
            # 检查目标流
            if stream_id == "TCP_10.171.250.80:33492_10.50.50.161:443_forward":
                logger.info(f"  ⭐ 这是我们关心的目标流")
                
    def print_packet_analysis(self):
        """打印数据包分析结果"""
        logger.info("\n" + "=" * 60)
        logger.info("数据包分析详情")
        logger.info("=" * 60)
        
        analyses = self.analyzer._packet_analyses
        logger.info(f"分析的数据包数量：{len(analyses)}")
        
        # 找到目标流的数据包
        target_packets = []
        for analysis in analyses:
            if analysis.stream_id == "TCP_10.171.250.80:33492_10.50.50.161:443_forward":
                target_packets.append(analysis)
                
        logger.info(f"目标流的数据包数量：{len(target_packets)}")
        
        for analysis in target_packets:
            logger.info(f"\n数据包{analysis.packet_number}:")
            logger.info(f"  时间戳：{analysis.timestamp}")
            logger.info(f"  序列号：{analysis.seq_number}")
            logger.info(f"  载荷长度：{analysis.payload_length}")
            logger.info(f"  应用层协议：{analysis.application_layer}")
            
            # 特别关注数据包14和15
            if analysis.packet_number in [14, 15]:
                logger.info(f"  ⭐ TLS Application Data包")

def main():
    """主函数"""
    input_file = "/Users/ricky/Downloads/samples/tls-single/tls_sample.pcap"
    
    logger.info("=" * 60)
    logger.info("PyShark掩码表生成测试")
    logger.info("=" * 60)
    logger.info(f"输入文件: {input_file}")
    
    # 检查输入文件
    if not os.path.exists(input_file):
        logger.error(f"输入文件不存在: {input_file}")
        return 1
        
    # 创建测试实例
    test = PySharkMaskTableTest()
    
    try:
        # 执行测试
        result = test.test_mask_table_generation(input_file)
        
        if result and result.success:
            # 打印数据包分析
            test.print_packet_analysis()
            
            logger.info("\n" + "=" * 60)
            logger.info("测试完成！")
            logger.info("=" * 60)
            return 0
        else:
            logger.error("测试失败")
            return 1
            
    except Exception as e:
        logger.error(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 