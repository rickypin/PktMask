#!/usr/bin/env python3
"""
GUI-后端端到端测试脚本

模拟 GUI 处理流程，验证修复后的 TLS-23 掩码效果。
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pktmask.core.processors.registry import ProcessorRegistry
from pktmask.core.processors.base_processor import ProcessorConfig
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

def find_test_pcap():
    """查找测试用的 PCAP 文件"""
    test_dirs = [
        "tests/data/tls",
        "tests/data",
        "tests/samples",
        "data/samples"
    ]
    
    for test_dir in test_dirs:
        test_path = project_root / test_dir
        if test_path.exists():
            # 查找 .pcap 或 .pcapng 文件
            for ext in ["*.pcap", "*.pcapng"]:
                pcap_files = list(test_path.glob(ext))
                if pcap_files:
                    return pcap_files[0]
    
    return None

def simulate_gui_processing(input_file, output_file):
    """模拟 GUI 处理流程"""
    print("=" * 60)
    print("模拟 GUI 处理流程")
    print("=" * 60)
    
    # 步骤 1: 创建 ProcessorConfig (模拟 GUI)
    gui_config = ProcessorConfig(
        enabled=True,
        name='mask_payloads'
    )
    print(f"1. GUI 创建配置: {gui_config}")
    
    # 步骤 2: 通过 ProcessorRegistry 获取处理器 (模拟 GUI 调用)
    try:
        processor = ProcessorRegistry.get_processor('mask_payloads', gui_config)
        print(f"2. 成功获取处理器: {type(processor).__name__}")
        
        # 检查配置
        preserve_config = processor.config.get('marker_config', {}).get('preserve', {})
        app_data_setting = preserve_config.get('application_data')
        print(f"3. 关键配置检查: application_data={app_data_setting}")
        
        if app_data_setting is False:
            print("✅ TLS-23 掩码配置正确")
        else:
            print("❌ TLS-23 掩码配置错误")
            return False
            
    except Exception as e:
        print(f"❌ 获取处理器失败: {e}")
        return False
    
    # 步骤 3: 处理文件 (模拟 GUI 处理)
    try:
        print(f"4. 开始处理文件: {input_file}")
        result = processor.process_file(str(input_file), str(output_file))
        
        if hasattr(result, 'success') and result.success:
            print("✅ 文件处理成功")
            return True
        else:
            print(f"❌ 文件处理失败: {result}")
            return False
            
    except Exception as e:
        print(f"❌ 文件处理异常: {e}")
        return False

def simulate_direct_api_processing(input_file, output_file):
    """模拟直接 API 调用"""
    print("\n" + "=" * 60)
    print("模拟直接 API 调用")
    print("=" * 60)
    
    # 直接创建 NewMaskPayloadStage
    direct_config = {
        "protocol": "tls",
        "mode": "enhanced",
        "marker_config": {
            "preserve": {
                "application_data": False,
                "handshake": True,
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True
            }
        },
        "masker_config": {
            "chunk_size": 1000,
            "verify_checksums": True
        }
    }
    
    print(f"1. 直接 API 配置: application_data={direct_config['marker_config']['preserve']['application_data']}")
    
    try:
        processor = NewMaskPayloadStage(direct_config)
        print(f"2. 成功创建处理器: {type(processor).__name__}")
        
        # 处理文件
        print(f"3. 开始处理文件: {input_file}")
        result = processor.process_file(str(input_file), str(output_file))
        
        if hasattr(result, 'success') and result.success:
            print("✅ 文件处理成功")
            return True
        else:
            print(f"❌ 文件处理失败: {result}")
            return False
            
    except Exception as e:
        print(f"❌ 处理异常: {e}")
        return False

def compare_output_files(gui_output, api_output):
    """比较两个输出文件"""
    print("\n" + "=" * 60)
    print("输出文件对比")
    print("=" * 60)
    
    if not gui_output.exists():
        print("❌ GUI 输出文件不存在")
        return False
        
    if not api_output.exists():
        print("❌ API 输出文件不存在")
        return False
    
    # 比较文件大小
    gui_size = gui_output.stat().st_size
    api_size = api_output.stat().st_size
    
    print(f"文件大小对比:")
    print(f"  GUI 输出: {gui_size} 字节")
    print(f"  API 输出: {api_size} 字节")
    
    # 如果大小相同，进行字节级比较
    if gui_size == api_size:
        with open(gui_output, 'rb') as f1, open(api_output, 'rb') as f2:
            gui_content = f1.read()
            api_content = f2.read()
            
            if gui_content == api_content:
                print("✅ 输出文件完全一致")
                return True
            else:
                print("⚠️ 输出文件大小相同但内容不同")
                return False
    else:
        size_diff = abs(gui_size - api_size)
        print(f"⚠️ 输出文件大小不同，差异: {size_diff} 字节")
        return False

def main():
    """主函数"""
    print("GUI-后端端到端测试")
    print("验证修复后的 GUI 和 API 处理结果一致性")
    
    # 查找测试文件
    test_pcap = find_test_pcap()
    if not test_pcap:
        print("❌ 未找到测试用的 PCAP 文件")
        print("请确保 tests/data/ 目录下有 PCAP 文件")
        return False
    
    print(f"使用测试文件: {test_pcap}")
    
    # 创建临时输出目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        gui_output = temp_path / "gui_output.pcap"
        api_output = temp_path / "api_output.pcap"
        
        # 测试 1: 模拟 GUI 处理
        gui_success = simulate_gui_processing(test_pcap, gui_output)
        
        # 测试 2: 模拟直接 API 调用
        api_success = simulate_direct_api_processing(test_pcap, api_output)
        
        # 测试 3: 比较输出文件
        if gui_success and api_success:
            files_match = compare_output_files(gui_output, api_output)
        else:
            files_match = False
        
        # 总结
        print("\n" + "=" * 60)
        print("端到端测试结果总结")
        print("=" * 60)
        
        if gui_success and api_success and files_match:
            print("✅ 端到端测试成功!")
            print("   - GUI 处理成功")
            print("   - API 处理成功") 
            print("   - 输出文件一致")
            print("   - TLS-23 掩码修复生效")
            return True
        else:
            print("❌ 端到端测试失败!")
            print(f"   - GUI 处理: {'成功' if gui_success else '失败'}")
            print(f"   - API 处理: {'成功' if api_success else '失败'}")
            print(f"   - 文件一致: {'是' if files_match else '否'}")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
