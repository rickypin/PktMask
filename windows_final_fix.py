#!/usr/bin/env python3
"""
Windows平台最终修复脚本

基于"Marker模块初始化返回False"错误的最终解决方案
"""

import sys
import logging
import platform
import os

def setup_comprehensive_logging():
    """设置全面的日志记录"""
    # 创建带时间戳的日志文件
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f'pktmask_final_fix_{timestamp}.log'
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_filename, mode='w', encoding='utf-8')
        ]
    )
    
    # 启用所有相关模块的调试日志
    debug_loggers = [
        'pktmask.services.pipeline_service',
        'pktmask.core.pipeline.executor',
        'pktmask.core.pipeline.stages.mask_payload_v2.stage',
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker',
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.base',
        'pktmask.infrastructure.dependency.checker'
    ]
    
    for logger_name in debug_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
    
    print(f"全面日志记录已启用，日志文件: {log_filename}")
    return log_filename

def check_windows_environment():
    """检查Windows环境"""
    print("=== Windows环境检查 ===")
    
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    
    if platform.system() == "Windows":
        print("✓ 确认在Windows环境中运行")
        
        # 检查常见的Windows Wireshark路径
        wireshark_paths = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
        ]
        
        tshark_found = False
        for path in wireshark_paths:
            if os.path.exists(path):
                print(f"✓ 找到TShark: {path}")
                tshark_found = True
                break
        
        if not tshark_found:
            print("⚠️  未在常见位置找到TShark")
            print("   这可能是问题的根源")
    else:
        print(f"⚠️  当前在{platform.system()}环境，不是Windows")
    
    print()

def test_tshark_availability():
    """测试TShark可用性"""
    print("=== TShark可用性测试 ===")
    
    import subprocess
    
    commands_to_test = ['tshark', 'tshark.exe']
    
    for cmd in commands_to_test:
        print(f"测试命令: {cmd}")
        
        try:
            result = subprocess.run(
                [cmd, '-v'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            print(f"  ✓ 命令执行成功")
            print(f"  返回码: {result.returncode}")
            
            if result.stdout:
                first_line = result.stdout.split('\n')[0]
                print(f"  版本信息: {first_line}")
            else:
                print(f"  ⚠️  stdout为空")
                
        except FileNotFoundError:
            print(f"  ❌ 命令未找到: {cmd}")
        except subprocess.TimeoutExpired:
            print(f"  ❌ 命令超时: {cmd}")
        except Exception as e:
            print(f"  ❌ 命令执行失败: {cmd}, 错误: {e}")
    
    print()

def test_pipeline_creation_with_detailed_logging():
    """测试管道创建（详细日志）"""
    print("=== 管道创建测试（详细日志）===")
    
    try:
        print("1. 导入服务模块...")
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        print("   ✓ 服务模块导入成功")
        
        print("2. 构建配置...")
        config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True
        )
        
        if config:
            print(f"   ✓ 配置构建成功: {list(config.keys())}")
            print(f"   配置详情: {config}")
        else:
            print("   ❌ 配置构建失败")
            return False
        
        print("3. 创建管道执行器...")
        print("   注意：这是失败的关键步骤，请仔细查看日志")
        
        try:
            executor = create_pipeline_executor(config)
            print("   ✅ 执行器创建成功！")
            
            if hasattr(executor, 'stages'):
                print(f"   ✓ 执行器包含{len(executor.stages)}个阶段:")
                for i, stage in enumerate(executor.stages):
                    print(f"      {i+1}. {stage.name}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ 执行器创建失败: {e}")
            print(f"   错误类型: {type(e).__name__}")
            
            # 详细分析错误
            error_msg = str(e)
            if "Marker模块初始化返回False" in error_msg:
                print("   🎯 确认这是Marker模块初始化问题")
                print("   这表明TShark检查在Windows环境下失败了")
            elif "Failed to create executor" in error_msg:
                print("   🔍 这是执行器创建的通用错误")
            
            return False
            
    except Exception as e:
        print(f"❌ 测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def provide_windows_specific_solutions():
    """提供Windows特定的解决方案"""
    print("\n=== Windows特定解决方案 ===")
    
    print("基于'Marker模块初始化返回False'错误，以下是Windows环境的解决方案:")
    print()
    
    print("🔧 立即可尝试的解决方案:")
    print("1. 安装Wireshark:")
    print("   - 从 https://www.wireshark.org/download.html 下载最新版本")
    print("   - 确保安装时选择了'TShark'组件")
    print("   - 安装后重启计算机")
    print()
    
    print("2. 检查PATH环境变量:")
    print("   - 打开命令提示符，运行: tshark -v")
    print("   - 如果失败，将Wireshark安装目录添加到PATH")
    print("   - 通常是: C:\\Program Files\\Wireshark")
    print()
    
    print("3. 权限问题:")
    print("   - 以管理员身份运行PktMask")
    print("   - 右键点击PktMask图标，选择'以管理员身份运行'")
    print()
    
    print("4. 防病毒软件:")
    print("   - 临时禁用Windows Defender或其他防病毒软件")
    print("   - 将PktMask添加到防病毒软件的白名单")
    print()
    
    print("🔧 高级解决方案:")
    print("5. 手动指定TShark路径:")
    print("   - 如果TShark安装在非标准位置")
    print("   - 可以通过配置文件指定完整路径")
    print()
    
    print("6. 使用便携版Wireshark:")
    print("   - 下载Wireshark便携版")
    print("   - 将tshark.exe放在PktMask同一目录")
    print()
    
    print("7. 检查Windows事件日志:")
    print("   - 打开事件查看器")
    print("   - 查看应用程序日志中的相关错误")

def main():
    """主函数"""
    print("PktMask Windows平台最终修复方案")
    print("=" * 50)
    print("专门解决'Marker模块初始化返回False'错误")
    print()
    
    # 设置全面日志
    log_file = setup_comprehensive_logging()
    
    # 环境检查
    check_windows_environment()
    
    # TShark可用性测试
    test_tshark_availability()
    
    # 核心测试
    success = test_pipeline_creation_with_detailed_logging()
    
    # 提供解决方案
    provide_windows_specific_solutions()
    
    print("\n" + "=" * 50)
    print("测试完成")
    
    if success:
        print("✅ 测试通过！问题已解决")
        print("如果之前有问题，现在应该可以正常使用PktMask了")
    else:
        print("❌ 问题仍然存在")
        print("请按照上述解决方案逐一尝试")
        print("特别注意TShark的安装和PATH配置")
    
    print(f"\n📋 详细日志已保存到: {log_file}")
    print("如果问题持续存在，请将此日志文件提供给技术支持")
    
    print("\n🔄 修复后的验证步骤:")
    print("1. 重新启动PktMask应用")
    print("2. 尝试处理一个小的pcap文件")
    print("3. 确保所有功能(去重、匿名化、掩码)都能正常工作")

if __name__ == "__main__":
    main()
