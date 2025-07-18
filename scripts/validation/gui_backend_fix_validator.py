#!/usr/bin/env python3
"""
GUI-后端处理差异修复验证脚本

验证 ProcessorRegistry 修复是否解决了 GUI 和直接 API 调用的配置差异问题。
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pktmask.core.processors.registry import ProcessorRegistry
from pktmask.core.processors.base_processor import ProcessorConfig
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

def setup_logging():
    """设置日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_gui_config_creation():
    """测试 GUI 配置创建过程"""
    print("=" * 60)
    print("测试 1: GUI 配置创建过程")
    print("=" * 60)
    
    # 模拟 GUI 创建 ProcessorConfig 的过程
    gui_config = ProcessorConfig(
        enabled=True,
        name='mask_payloads'
    )
    
    print(f"GUI ProcessorConfig: {gui_config}")
    print(f"  - enabled: {gui_config.enabled}")
    print(f"  - name: {gui_config.name}")
    print(f"  - priority: {gui_config.priority}")
    
    # 通过 ProcessorRegistry 获取处理器（模拟 GUI 调用）
    try:
        processor = ProcessorRegistry.get_processor('mask_payloads', gui_config)
        print(f"\n✅ 成功创建处理器: {type(processor).__name__}")
        
        # 检查处理器配置
        if hasattr(processor, 'config'):
            print(f"处理器配置: {processor.config}")
            
            # 检查关键配置项
            marker_config = processor.config.get('marker_config', {})
            preserve_config = marker_config.get('preserve', {})
            application_data_setting = preserve_config.get('application_data', None)
            
            print(f"\n关键配置检查:")
            print(f"  - protocol: {processor.config.get('protocol')}")
            print(f"  - mode: {processor.config.get('mode')}")
            print(f"  - preserve.application_data: {application_data_setting}")
            
            if application_data_setting is False:
                print("✅ TLS-23 掩码配置正确: application_data=False")
            else:
                print("❌ TLS-23 掩码配置错误: application_data 应该为 False")
                
        return processor
        
    except Exception as e:
        print(f"❌ 创建处理器失败: {e}")
        return None

def test_direct_api_config():
    """测试直接 API 配置创建"""
    print("\n" + "=" * 60)
    print("测试 2: 直接 API 配置创建")
    print("=" * 60)
    
    # 直接 API 调用配置
    direct_config = {
        "protocol": "tls",
        "mode": "enhanced",
        "marker_config": {
            "preserve": {
                "application_data": False,  # 关键配置
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
    
    print(f"直接 API 配置: {direct_config}")
    
    try:
        processor = NewMaskPayloadStage(direct_config)
        print(f"✅ 成功创建处理器: {type(processor).__name__}")
        
        # 检查配置
        preserve_config = processor.marker_config.get('preserve', {})
        application_data_setting = preserve_config.get('application_data', None)
        
        print(f"\n关键配置检查:")
        print(f"  - protocol: {processor.protocol}")
        print(f"  - mode: {processor.mode}")
        print(f"  - preserve.application_data: {application_data_setting}")
        
        return processor
        
    except Exception as e:
        print(f"❌ 创建处理器失败: {e}")
        return None

def compare_configurations(gui_processor, api_processor):
    """比较 GUI 和 API 处理器的配置"""
    print("\n" + "=" * 60)
    print("测试 3: 配置对比分析")
    print("=" * 60)
    
    if not gui_processor or not api_processor:
        print("❌ 无法进行配置对比，因为处理器创建失败")
        return False
    
    # 比较关键配置项
    gui_config = gui_processor.config
    api_config = api_processor.config
    
    print("配置对比:")
    print(f"  GUI protocol: {gui_config.get('protocol')} | API protocol: {api_config.get('protocol')}")
    print(f"  GUI mode: {gui_config.get('mode')} | API mode: {api_config.get('mode')}")
    
    # 比较 preserve 配置
    gui_preserve = gui_config.get('marker_config', {}).get('preserve', {})
    api_preserve = api_config.get('marker_config', {}).get('preserve', {})
    
    print(f"\nPreserve 配置对比:")
    for key in ['application_data', 'handshake', 'alert', 'change_cipher_spec', 'heartbeat']:
        gui_val = gui_preserve.get(key, 'N/A')
        api_val = api_preserve.get(key, 'N/A')
        match = "✅" if gui_val == api_val else "❌"
        print(f"  {match} {key}: GUI={gui_val} | API={api_val}")
    
    # 检查关键的 application_data 配置
    gui_app_data = gui_preserve.get('application_data')
    api_app_data = api_preserve.get('application_data')
    
    if gui_app_data == api_app_data == False:
        print("\n✅ 配置一致性检查通过: TLS-23 掩码配置正确")
        return True
    else:
        print(f"\n❌ 配置一致性检查失败: application_data 配置不一致")
        print(f"   GUI: {gui_app_data}, API: {api_app_data}")
        return False

def test_processor_registry_mapping():
    """测试 ProcessorRegistry 映射"""
    print("\n" + "=" * 60)
    print("测试 4: ProcessorRegistry 映射检查")
    print("=" * 60)
    
    # 检查处理器映射
    available_processors = ProcessorRegistry.list_processors()
    print(f"可用处理器: {available_processors}")
    
    # 检查 mask_payloads 映射
    if 'mask_payloads' in available_processors:
        print("✅ mask_payloads 处理器已注册")
        
        # 获取处理器信息
        try:
            info = ProcessorRegistry.get_processor_info('mask_payloads')
            print(f"处理器信息: {info}")
        except Exception as e:
            print(f"⚠️ 获取处理器信息失败: {e}")
    else:
        print("❌ mask_payloads 处理器未注册")

def main():
    """主函数"""
    setup_logging()
    
    print("GUI-后端处理差异修复验证")
    print("验证 ProcessorRegistry 修复是否解决配置差异问题")
    
    # 测试 1: GUI 配置创建
    gui_processor = test_gui_config_creation()
    
    # 测试 2: 直接 API 配置创建
    api_processor = test_direct_api_config()
    
    # 测试 3: 配置对比
    config_match = compare_configurations(gui_processor, api_processor)
    
    # 测试 4: ProcessorRegistry 映射检查
    test_processor_registry_mapping()
    
    # 总结
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)
    
    if gui_processor and api_processor and config_match:
        print("✅ 修复验证成功!")
        print("   - GUI 和 API 配置格式一致")
        print("   - TLS-23 掩码配置正确 (application_data=False)")
        print("   - ProcessorRegistry 正确转换配置格式")
        return True
    else:
        print("❌ 修复验证失败!")
        print("   需要进一步调试和修复")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
