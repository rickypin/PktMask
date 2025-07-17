#!/usr/bin/env python3
"""
Windows环境专用的PipelineExecutor调试脚本

专门用于在Windows环境下捕获"Failed to create pipeline: failed to create executor"错误
"""

import sys
import logging
import platform
import os
import subprocess

def setup_windows_debug_logging():
    """设置Windows专用的详细日志记录"""
    # 创建日志文件名包含时间戳
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f'pktmask_windows_debug_{timestamp}.log'
    
    # 配置详细日志
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
        'pktmask.infrastructure.dependency.checker'
    ]
    
    for logger_name in debug_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
    
    print(f"Windows调试日志已启用，日志文件: {log_filename}")
    return log_filename

def check_windows_environment():
    """检查Windows环境特定信息"""
    print("=== Windows环境检查 ===")
    
    if platform.system() != "Windows":
        print(f"⚠️  当前平台: {platform.system()}，不是Windows环境")
        print("   此脚本主要用于Windows环境调试，但会继续运行")
    else:
        print(f"✓ Windows环境: {platform.system()} {platform.release()}")
        print(f"✓ Windows版本: {platform.version()}")
    
    print(f"Python版本: {sys.version}")
    print(f"Python可执行文件: {sys.executable}")
    print(f"当前工作目录: {os.getcwd()}")
    print()

def check_subprocess_behavior():
    """检查subprocess在当前环境下的行为"""
    print("=== subprocess行为检查 ===")
    
    try:
        # 测试基本的subprocess调用
        result = subprocess.run(['echo', 'test'], capture_output=True, text=True, timeout=5)
        print(f"✓ 基本subprocess调用成功")
        print(f"  返回码: {result.returncode}")
        print(f"  stdout类型: {type(result.stdout)}")
        print(f"  stderr类型: {type(result.stderr)}")
        
        if result.stdout is None:
            print("  ⚠️  stdout为None - 这可能是Windows打包环境的问题")
        if result.stderr is None:
            print("  ⚠️  stderr为None - 这可能是Windows打包环境的问题")
            
    except Exception as e:
        print(f"✗ subprocess测试失败: {e}")
    
    # 测试tshark调用（如果可用）
    try:
        result = subprocess.run(['tshark', '-v'], capture_output=True, text=True, timeout=10)
        print(f"✓ tshark调用成功")
        print(f"  返回码: {result.returncode}")
        if result.stdout:
            print(f"  版本信息: {result.stdout.split()[1] if len(result.stdout.split()) > 1 else 'unknown'}")
        else:
            print("  ⚠️  tshark输出为空或None")
    except FileNotFoundError:
        print("✗ tshark未找到 - 这可能是问题的根源")
    except subprocess.TimeoutExpired:
        print("✗ tshark调用超时")
    except Exception as e:
        print(f"✗ tshark测试失败: {e}")
    
    print()

def test_dependency_checker():
    """测试依赖检查器"""
    print("=== 依赖检查器测试 ===")
    
    try:
        from pktmask.infrastructure.dependency.checker import DependencyChecker
        checker = DependencyChecker()
        
        print("✓ DependencyChecker导入成功")
        
        # 测试tshark检查
        print("检查tshark依赖...")
        result = checker.check_tshark()
        
        print(f"  状态: {result.status.name}")
        print(f"  路径: {result.path}")
        print(f"  版本: {result.version_found}")
        
        if result.error_message:
            print(f"  错误信息: {result.error_message}")
            
        if "Windows compatibility" in (result.error_message or ""):
            print("  ✓ Windows兼容性处理已生效")
            
    except Exception as e:
        print(f"✗ 依赖检查器测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def test_executor_creation_detailed():
    """详细测试执行器创建过程"""
    print("=== 详细执行器创建测试 ===")
    
    try:
        print("1. 导入服务模块...")
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        print("   ✓ 服务模块导入成功")
        
        print("2. 构建配置...")
        # 先测试简单配置
        simple_config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=False,
            enable_mask=False
        )
        
        if simple_config:
            print(f"   ✓ 简单配置构建成功: {list(simple_config.keys())}")
            
            print("3. 测试简单配置执行器创建...")
            try:
                executor = create_pipeline_executor(simple_config)
                print("   ✅ 简单配置执行器创建成功")
            except Exception as e:
                print(f"   ❌ 简单配置执行器创建失败: {e}")
                return False
        
        # 测试包含mask的完整配置
        print("4. 测试完整配置...")
        full_config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True
        )
        
        if full_config:
            print(f"   ✓ 完整配置构建成功: {list(full_config.keys())}")
            
            print("5. 测试完整配置执行器创建...")
            try:
                executor = create_pipeline_executor(full_config)
                print("   ✅ 完整配置执行器创建成功")
                
                if hasattr(executor, 'stages'):
                    print(f"   ✓ 执行器包含{len(executor.stages)}个阶段")
                
                return True
                
            except Exception as e:
                print(f"   ❌ 完整配置执行器创建失败: {e}")
                print(f"   错误类型: {type(e).__name__}")
                
                # 分析错误类型
                error_msg = str(e).lower()
                if "failed to create executor" in error_msg:
                    print("   🎯 这是目标错误！")
                elif "tshark" in error_msg:
                    print("   🔍 错误与tshark相关")
                elif "import" in error_msg:
                    print("   🔍 错误与模块导入相关")
                elif "permission" in error_msg:
                    print("   🔍 错误与权限相关")
                
                return False
        
    except Exception as e:
        print(f"❌ 执行器创建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_potential_issues():
    """分析潜在的Windows特定问题"""
    print("=== 潜在问题分析 ===")
    
    issues_found = []
    
    # 检查是否在打包环境中
    if hasattr(sys, 'frozen'):
        issues_found.append("应用运行在打包环境中（PyInstaller等）")
    
    # 检查Python路径
    if 'site-packages' not in sys.path[0]:
        issues_found.append("Python路径可能异常")
    
    # 检查环境变量
    if 'PATH' in os.environ:
        path_dirs = os.environ['PATH'].split(os.pathsep)
        wireshark_in_path = any('wireshark' in dir.lower() for dir in path_dirs)
        if not wireshark_in_path:
            issues_found.append("PATH中未找到Wireshark目录")
    
    # 检查常见的Windows Wireshark安装位置
    common_paths = [
        r"C:\Program Files\Wireshark\tshark.exe",
        r"C:\Program Files (x86)\Wireshark\tshark.exe"
    ]
    
    tshark_found = False
    for path in common_paths:
        if os.path.exists(path):
            tshark_found = True
            print(f"✓ 找到tshark: {path}")
            break
    
    if not tshark_found:
        issues_found.append("未在常见位置找到tshark.exe")
    
    if issues_found:
        print("发现的潜在问题:")
        for issue in issues_found:
            print(f"  • {issue}")
    else:
        print("未发现明显的环境问题")
    
    print()

def main():
    """主函数"""
    print("PktMask Windows环境执行器创建调试")
    print("=" * 50)
    
    # 设置日志
    log_file = setup_windows_debug_logging()
    
    # 运行各项检查
    check_windows_environment()
    check_subprocess_behavior()
    analyze_potential_issues()
    test_dependency_checker()
    
    # 核心测试
    success = test_executor_creation_detailed()
    
    print("=" * 50)
    if success:
        print("✅ 所有测试通过！执行器创建成功")
        print("如果在实际Windows环境中仍有问题，请提供详细的错误日志")
    else:
        print("❌ 执行器创建失败！")
        print("\n🔧 建议的解决步骤:")
        print("1. 确保Wireshark已正确安装")
        print("2. 将Wireshark安装目录添加到系统PATH")
        print("3. 以管理员权限运行应用")
        print("4. 检查Windows防病毒软件是否阻止了应用")
        print("5. 如果是打包应用，确保tshark.exe包含在应用包中")
    
    print(f"\n📋 详细日志已保存到: {log_file}")
    print("请将此日志文件提供给开发者以进行进一步分析")

if __name__ == "__main__":
    main()
