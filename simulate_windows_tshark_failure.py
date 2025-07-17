#!/usr/bin/env python3
"""
模拟Windows环境下TShark失败的情况

用于测试我们的Windows兼容性修复是否有效
"""

import sys
import logging
import platform
import subprocess
from unittest.mock import patch, MagicMock

def setup_debug_logging():
    """设置详细的调试日志"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('windows_simulation.log', mode='w', encoding='utf-8')
        ]
    )
    
    # 启用所有相关模块的调试日志
    debug_loggers = [
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker',
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.base',
    ]
    
    for logger_name in debug_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
    
    print("Windows模拟调试日志已启用")

def simulate_tshark_not_found():
    """模拟tshark未找到的情况"""
    print("\n=== 模拟TShark未找到 ===")
    
    def mock_subprocess_run(*args, **kwargs):
        if 'tshark' in str(args[0]):
            raise FileNotFoundError("The system cannot find the file specified")
        return subprocess.run(*args, **kwargs)
    
    with patch('subprocess.run', side_effect=mock_subprocess_run), \
         patch('os.name', 'nt'):
        
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            marker = TLSProtocolMarker({})
            print("✓ TLSProtocolMarker创建成功")
            
            success = marker.initialize()
            if success:
                print("✅ 初始化成功 - Windows兼容性修复生效！")
                print("   即使tshark未找到，系统也能继续运行")
            else:
                print("❌ 初始化失败 - 需要进一步修复")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()

def simulate_tshark_permission_denied():
    """模拟tshark权限被拒绝的情况"""
    print("\n=== 模拟TShark权限被拒绝 ===")
    
    def mock_subprocess_run(*args, **kwargs):
        if 'tshark' in str(args[0]):
            raise PermissionError("Access is denied")
        return subprocess.run(*args, **kwargs)
    
    with patch('subprocess.run', side_effect=mock_subprocess_run), \
         patch('os.name', 'nt'):
        
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            marker = TLSProtocolMarker({})
            print("✓ TLSProtocolMarker创建成功")
            
            success = marker.initialize()
            if success:
                print("✅ 初始化成功 - Windows权限问题处理生效！")
            else:
                print("❌ 初始化失败 - 权限问题未解决")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")

def simulate_tshark_timeout():
    """模拟tshark超时的情况"""
    print("\n=== 模拟TShark超时 ===")
    
    def mock_subprocess_run(*args, **kwargs):
        if 'tshark' in str(args[0]):
            raise subprocess.TimeoutExpired(args[0], kwargs.get('timeout', 10))
        return subprocess.run(*args, **kwargs)
    
    with patch('subprocess.run', side_effect=mock_subprocess_run), \
         patch('os.name', 'nt'):
        
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            marker = TLSProtocolMarker({})
            print("✓ TLSProtocolMarker创建成功")
            
            success = marker.initialize()
            if success:
                print("✅ 初始化成功 - Windows超时处理生效！")
            else:
                print("❌ 初始化失败 - 超时问题未解决")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")

def simulate_tshark_none_output():
    """模拟tshark返回None输出的情况"""
    print("\n=== 模拟TShark返回None输出 ===")
    
    def mock_subprocess_run(*args, **kwargs):
        if 'tshark' in str(args[0]):
            # 创建一个模拟的CompletedProcess对象，stdout为None
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = None
            mock_result.stderr = None
            return mock_result
        return subprocess.run(*args, **kwargs)
    
    with patch('subprocess.run', side_effect=mock_subprocess_run), \
         patch('os.name', 'nt'):
        
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            marker = TLSProtocolMarker({})
            print("✓ TLSProtocolMarker创建成功")
            
            success = marker.initialize()
            if success:
                print("✅ 初始化成功 - Windows None输出处理生效！")
            else:
                print("❌ 初始化失败 - None输出问题未解决")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")

def simulate_tshark_empty_output():
    """模拟tshark返回空输出的情况"""
    print("\n=== 模拟TShark返回空输出 ===")
    
    def mock_subprocess_run(*args, **kwargs):
        if 'tshark' in str(args[0]):
            # 创建一个模拟的CompletedProcess对象，输出为空
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            return mock_result
        return subprocess.run(*args, **kwargs)
    
    with patch('subprocess.run', side_effect=mock_subprocess_run), \
         patch('os.name', 'nt'):
        
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            marker = TLSProtocolMarker({})
            print("✓ TLSProtocolMarker创建成功")
            
            success = marker.initialize()
            if success:
                print("✅ 初始化成功 - Windows空输出处理生效！")
            else:
                print("❌ 初始化失败 - 空输出问题未解决")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")

def test_full_pipeline_with_simulated_failure():
    """测试完整的管道创建过程（模拟Windows失败）"""
    print("\n=== 测试完整管道创建（模拟Windows TShark失败）===")
    
    def mock_subprocess_run(*args, **kwargs):
        if 'tshark' in str(args[0]):
            raise FileNotFoundError("The system cannot find the file specified")
        return subprocess.run(*args, **kwargs)
    
    with patch('subprocess.run', side_effect=mock_subprocess_run), \
         patch('os.name', 'nt'):
        
        try:
            from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
            
            # 构建包含mask的配置
            config = build_pipeline_config(
                enable_dedup=True,
                enable_anon=True,
                enable_mask=True
            )
            
            if config:
                print(f"✓ 配置构建成功: {list(config.keys())}")
                
                try:
                    executor = create_pipeline_executor(config)
                    print("✅ 执行器创建成功 - 完整的Windows兼容性修复生效！")
                    
                    if hasattr(executor, 'stages'):
                        print(f"✓ 执行器包含{len(executor.stages)}个阶段")
                        
                except Exception as e:
                    print(f"❌ 执行器创建失败: {e}")
                    if "Marker模块初始化返回False" in str(e):
                        print("   这是我们要解决的目标错误")
                    
            else:
                print("✗ 配置构建失败")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()

def main():
    """主函数"""
    print("Windows TShark失败情况模拟测试")
    print("=" * 50)
    print(f"当前平台: {platform.system()}")
    print("注意：此测试模拟Windows环境下的各种TShark失败情况")
    print()
    
    # 设置调试日志
    setup_debug_logging()
    
    # 运行各种失败情况的模拟测试
    simulate_tshark_not_found()
    simulate_tshark_permission_denied()
    simulate_tshark_timeout()
    simulate_tshark_none_output()
    simulate_tshark_empty_output()
    
    # 测试完整的管道创建
    test_full_pipeline_with_simulated_failure()
    
    print("\n" + "=" * 50)
    print("Windows模拟测试完成")
    print("详细日志已保存到: windows_simulation.log")
    print("\n如果所有模拟测试都通过，说明Windows兼容性修复应该有效")
    print("如果在实际Windows环境中仍有问题，可能需要进一步的特定修复")

if __name__ == "__main__":
    main()
