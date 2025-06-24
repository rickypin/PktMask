import argparse
import logging
from pathlib import Path
import yaml
import sys

# 确保能从src目录导入PktMask模块
# 这是为了在项目根目录运行此脚本时，能够找到pktmask包
try:
    # 尝试将src目录添加到Python路径
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root / 'src'))
    
    from pktmask.core.tcp_payload_masker import (
        TcpPayloadMasker,
        TcpKeepRangeTable,
        TcpKeepRangeEntry,
        TcpPayloadMaskerError
    )
except ImportError as e:
    print(f"Error: 无法导入 PktMask 模块。请确保脚本位于项目根目录，并且依赖已安装。")
    print(f"详细错误: {e}")
    sys.exit(1)


def setup_logging(level=logging.INFO):
    """配置日志记录"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        stream=sys.stdout,
    )


def load_keep_range_table_from_config(config_path: Path) -> TcpKeepRangeTable:
    """从YAML配置文件加载并构建TcpKeepRangeTable"""
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)

    if 'keep_range_rules' not in config_data or not isinstance(config_data['keep_range_rules'], list):
        raise ValueError("配置文件格式错误: 必须包含一个名为 'keep_range_rules' 的列表")

    keep_range_table = TcpKeepRangeTable()
    rules = config_data['keep_range_rules']
    
    logging.info(f"从 {config_path.name} 加载了 {len(rules)} 条掩码规则。")

    for i, rule in enumerate(rules):
        try:
            # 使用字典解包来创建条目，这很灵活
            entry = TcpKeepRangeEntry(**rule)
            keep_range_table.add_keep_range_entry(entry)
        except (TypeError, ValueError) as e:
            raise ValueError(f"规则 #{i+1} 格式错误: {e}\n规则内容: {rule}")

    return keep_range_table


def main():
    """主执行函数"""
    parser = argparse.ArgumentParser(
        description="独立的 TCP 载荷掩码测试脚本",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--input-pcap',
        type=Path,
        required=True,
        help="输入的PCAP文件路径"
    )
    parser.add_argument(
        '--config',
        type=Path,
        required=True,
        help="定义了掩码规则的YAML配置文件路径"
    )
    parser.add_argument(
        '--output-pcap',
        type=Path,
        required=True,
        help="掩码后输出的PCAP文件路径"
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help="设置日志级别"
    )

    args = parser.parse_args()

    # 设置日志
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(log_level)

    try:
        # 1. 加载掩码表
        logging.info("正在从配置文件加载掩码表...")
        keep_range_table = load_keep_range_table_from_config(args.config)
        
        # 打印一些关于掩码表的信息
        stats = keep_range_table.get_statistics()
        logging.debug(f"掩码表统计: {stats['total_entries']} 个条目, {stats['tcp_streams_count']} 个流")

        # 2. 初始化掩码器
        # 我们可以传递自定义配置，但这里使用默认配置
        masker = TcpPayloadMasker()

        # 3. 执行掩码操作
        logging.info(f"🚀 开始处理PCAP文件: {args.input_pcap} -> {args.output_pcap}")
        result = masker.mask_tcp_payloads_with_keep_ranges(
            input_pcap=str(args.input_pcap),
            keep_range_table=keep_range_table,
            output_pcap=str(args.output_pcap)
        )

        # 4. 报告结果
        if result.success:
            logging.info("🎉 处理成功!")
            print("\n" + "="*20 + " 处理结果摘要 " + "="*20)
            print(result.get_summary())
            print("="*58)
        else:
            logging.error("❌ 处理失败。")
            print(f"\n错误信息: {result.error_message}")

    except (FileNotFoundError, ValueError, TcpPayloadMaskerError) as e:
        logging.error(f"发生致命错误: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"发生未预料的错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 