#!/usr/bin/env python3
"""
专门测试Marker模块初始化的脚本

用于诊断"Marker模块初始化返回False"错误
"""

import sys
import logging
import platform

def setup_debug_logging():
    """设置详细的调试日志"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('marker_debug.log', mode='w', encoding='utf-8')
        ]
    )
    
    # 启用所有相关模块的调试日志
    debug_loggers = [
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker',
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.base',
        'pktmask.infrastructure.dependency.checker'
    ]
    
    for logger_name in debug_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
    
    print("Marker调试日志已启用")

def test_tls_marker_creation():
    """测试TLS Marker的创建"""
    print("=== 测试TLS Marker创建 ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        print("✓ TLSProtocolMarker导入成功")
        
        # 测试不同的配置
        configs_to_test = [
            {},  # 空配置
            {'tshark_path': None},  # 明确设置为None
            {'tshark_path': 'tshark'},  # 使用默认路径
        ]
        
        for i, config in enumerate(configs_to_test):
            print(f"\n--- 测试配置 {i+1}: {config} ---")
            
            try:
                marker = TLSProtocolMarker(config)
                print(f"✓ TLSProtocolMarker创建成功，配置: {config}")
                
                # 测试初始化
                print("开始初始化...")
                success = marker.initialize()
                
                if success:
                    print("✅ TLSProtocolMarker初始化成功")
                else:
                    print("❌ TLSProtocolMarker初始化返回False")
                    print("这是我们要解决的问题！")
                
            except Exception as e:
                print(f"❌ TLSProtocolMarker创建或初始化失败: {e}")
                import traceback
                traceback.print_exc()
        
    except ImportError as e:
        print(f"❌ TLSProtocolMarker导入失败: {e}")
    except Exception as e:
        print(f"❌ 测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()

def test_tshark_directly():
    """直接测试tshark可用性"""
    print("\n=== 直接测试TShark可用性 ===")
    
    import subprocess
    import os
    
    tshark_commands = ['tshark', 'tshark.exe']
    
    for cmd in tshark_commands:
        print(f"\n--- 测试命令: {cmd} ---")
        
        try:
            result = subprocess.run(
                [cmd, '-v'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            print(f"✓ 命令执行成功")
            print(f"  返回码: {result.returncode}")
            print(f"  stdout类型: {type(result.stdout)}")
            print(f"  stderr类型: {type(result.stderr)}")
            
            if result.stdout:
                lines = result.stdout.split('\n')
                if lines:
                    print(f"  版本信息: {lines[0]}")
            else:
                print(f"  ⚠️  stdout为空或None")
                
            if result.stderr:
                print(f"  stderr: {result.stderr[:100]}...")
                
        except FileNotFoundError:
            print(f"❌ 命令未找到: {cmd}")
        except subprocess.TimeoutExpired:
            print(f"❌ 命令超时: {cmd}")
        except Exception as e:
            print(f"❌ 命令执行失败: {cmd}, 错误: {e}")

def test_dependency_checker():
    """测试依赖检查器"""
    print("\n=== 测试依赖检查器 ===")
    
    try:
        from pktmask.infrastructure.dependency.checker import DependencyChecker
        
        checker = DependencyChecker()
        print("✓ DependencyChecker创建成功")
        
        # 检查tshark
        print("检查tshark依赖...")
        result = checker.check_tshark()
        
        print(f"  状态: {result.status.name}")
        print(f"  路径: {result.path}")
        print(f"  版本: {result.version_found}")
        print(f"  错误信息: {result.error_message}")
        
        if result.status.name == 'SATISFIED':
            print("✅ 依赖检查器认为tshark可用")
        else:
            print("❌ 依赖检查器认为tshark不可用")
            
    except Exception as e:
        print(f"❌ 依赖检查器测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_windows_specific_paths():
    """测试Windows特定的tshark路径"""
    print("\n=== 测试Windows特定路径 ===")
    
    if platform.system() != "Windows":
        print("⚠️  当前不在Windows环境，跳过Windows特定测试")
        return
    
    import os
    
    # Windows常见的tshark安装路径
    windows_paths = [
        r"C:\Program Files\Wireshark\tshark.exe",
        r"C:\Program Files (x86)\Wireshark\tshark.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Wireshark\tshark.exe"),
        os.path.join(os.getcwd(), "tshark.exe"),
        os.path.join(os.path.dirname(sys.executable), "tshark.exe"),
    ]
    
    for path in windows_paths:
        print(f"检查路径: {path}")
        if os.path.exists(path):
            print(f"  ✓ 文件存在")
            if os.access(path, os.X_OK):
                print(f"  ✓ 文件可执行")
            else:
                print(f"  ⚠️  文件不可执行")
        else:
            print(f"  ❌ 文件不存在")

def analyze_log_file():
    """分析日志文件"""
    print("\n=== 分析日志文件 ===")
    
    try:
        with open('marker_debug.log', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找关键错误信息
        error_keywords = ['error', 'failed', 'exception', 'traceback', 'timeout', 'not found']
        
        lines = content.split('\n')
        error_lines = []
        
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in error_keywords):
                error_lines.append(f"Line {i+1}: {line}")
        
        if error_lines:
            print(f"发现 {len(error_lines)} 行错误相关信息:")
            for line in error_lines[-10:]:  # 显示最后10行
                print(f"  {line}")
        else:
            print("日志中未发现明显错误")
            
        # 查找初始化相关信息
        init_lines = [line for line in lines if 'initializ' in line.lower()]
        if init_lines:
            print(f"\n初始化相关信息 ({len(init_lines)} 条):")
            for line in init_lines[-5:]:  # 显示最后5条
                print(f"  {line}")
                
    except FileNotFoundError:
        print("日志文件不存在")
    except Exception as e:
        print(f"分析日志文件失败: {e}")

def main():
    """主函数"""
    print("PktMask Marker模块初始化调试")
    print("=" * 50)
    print(f"平台: {platform.system()} {platform.release()}")
    print()
    
    # 设置调试日志
    setup_debug_logging()
    
    # 运行各项测试
    test_tshark_directly()
    test_dependency_checker()
    test_windows_specific_paths()
    test_tls_marker_creation()
    
    # 分析日志
    analyze_log_file()
    
    print("\n" + "=" * 50)
    print("调试完成")
    print("详细日志已保存到: marker_debug.log")
    print("\n如果Marker初始化仍然失败，请检查:")
    print("1. TShark是否正确安装")
    print("2. TShark是否在系统PATH中")
    print("3. 是否有权限执行TShark")
    print("4. Windows防病毒软件是否阻止了subprocess调用")

if __name__ == "__main__":
    main()
