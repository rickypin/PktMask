#!/usr/bin/env python3
"""测试修复后的Enhanced Trimmer功能"""

import logging
from pathlib import Path
from src.pktmask.core.processors.enhanced_trimmer import EnhancedTrimmer

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_enhanced_trimmer():
    """测试Enhanced Trimmer修复"""
    # 使用TLS样本文件
    input_file = Path('tests/samples/TLS/tls_sample.pcap')
    output_dir = Path('/Users/ricky/Downloads/TestCases/TLS')
    output_dir.mkdir(parents=True, exist_ok=True)

    print('=== 测试Enhanced Trimmer修复 ===')
    print(f'输入文件: {input_file}')
    print(f'输出目录: {output_dir}')
    print(f'修复说明: Scapy回写器现在使用原始文件而不是TShark重组文件')
    print()

    try:
        # 创建默认配置
        config = {
            'tls_mask_application_data': True,
            'tls_keep_handshake': True,
            'http_mask_body': True,
            'http_keep_headers': True
        }
        trimmer = EnhancedTrimmer(config)
        
        # 确保输出文件路径正确
        output_file = output_dir / f"tls_sample_masked.pcap"
        result = trimmer.process_file(input_file, output_file)
        print(f'✅ 处理成功: {result}')
        return True
    except Exception as e:
        print(f'❌ 处理失败: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_enhanced_trimmer()
    exit(0 if success else 1) 