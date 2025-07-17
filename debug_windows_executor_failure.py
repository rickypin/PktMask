#!/usr/bin/env python3
"""
Windows平台PipelineExecutor创建失败诊断脚本

专门诊断"Failed to create pipeline: failed to create executor"错误
"""

import os
import sys
import traceback
import platform
from pathlib import Path

def check_basic_environment():
    """检查基础环境"""
    print("=== 基础环境检查 ===")
    print(f"Python版本: {sys.version}")
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.executable}")
    print()

def check_imports():
    """检查关键模块导入"""
    print("=== 模块导入检查 ===")
    
    # 检查基础模块
    modules_to_check = [
        'pktmask',
        'pktmask.services.pipeline_service',
        'pktmask.core.pipeline.executor',
        'pktmask.core.pipeline.stages.dedup',
        'pktmask.core.pipeline.stages.anon_ip',
        'pktmask.core.pipeline.stages.mask_payload_v2.stage',
        'scapy.all',
    ]
    
    for module_name in modules_to_check:
        try:
            __import__(module_name)
            print(f"✓ {module_name}")
        except Exception as e:
            print(f"✗ {module_name}: {e}")
    print()

def check_dependencies():
    """检查依赖工具"""
    print("=== 依赖工具检查 ===")
    
    try:
        from pktmask.infrastructure.dependency.checker import DependencyChecker
        checker = DependencyChecker()
        
        # 检查tshark
        tshark_result = checker.check_tshark()
        print(f"TShark状态: {tshark_result.status.name}")
        if tshark_result.path:
            print(f"TShark路径: {tshark_result.path}")
        if tshark_result.version_found:
            print(f"TShark版本: {tshark_result.version_found}")
        if tshark_result.error_message:
            print(f"TShark错误: {tshark_result.error_message}")
        
        # 检查scapy
        scapy_result = checker.check_scapy()
        print(f"Scapy状态: {scapy_result.status.name}")
        if scapy_result.version_found:
            print(f"Scapy版本: {scapy_result.version_found}")
        if scapy_result.error_message:
            print(f"Scapy错误: {scapy_result.error_message}")
            
    except Exception as e:
        print(f"依赖检查失败: {e}")
        traceback.print_exc()
    print()

def test_pipeline_config():
    """测试管道配置创建"""
    print("=== 管道配置测试 ===")
    
    try:
        from pktmask.services.pipeline_service import build_pipeline_config
        
        # 测试不同配置组合
        configs_to_test = [
            {"enable_dedup": True, "enable_anon": False, "enable_mask": False},
            {"enable_dedup": False, "enable_anon": True, "enable_mask": False},
            {"enable_dedup": True, "enable_anon": True, "enable_mask": False},
            {"enable_dedup": True, "enable_anon": True, "enable_mask": True},
        ]
        
        for i, config_params in enumerate(configs_to_test):
            try:
                config = build_pipeline_config(**config_params)
                if config:
                    print(f"✓ 配置{i+1}: {len(config)}个阶段 - {list(config.keys())}")
                else:
                    print(f"✗ 配置{i+1}: 返回空配置")
            except Exception as e:
                print(f"✗ 配置{i+1}: {e}")
                
    except Exception as e:
        print(f"配置测试失败: {e}")
        traceback.print_exc()
    print()

def test_stage_creation():
    """测试各个阶段的创建"""
    print("=== 阶段创建测试 ===")
    
    # 测试DeduplicationStage
    try:
        from pktmask.core.pipeline.stages.dedup import DeduplicationStage
        stage = DeduplicationStage({"enabled": True})
        stage.initialize()
        print("✓ DeduplicationStage创建和初始化成功")
    except Exception as e:
        print(f"✗ DeduplicationStage失败: {e}")
        traceback.print_exc()
    
    # 测试AnonStage
    try:
        from pktmask.core.pipeline.stages.anon_ip import AnonStage
        stage = AnonStage({"enabled": True})
        stage.initialize()
        print("✓ AnonStage创建和初始化成功")
    except Exception as e:
        print(f"✗ AnonStage失败: {e}")
        traceback.print_exc()
    
    # 测试NewMaskPayloadStage（可能是问题所在）
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        stage = NewMaskPayloadStage({"enabled": True, "protocol": "tls"})
        stage.initialize()
        print("✓ NewMaskPayloadStage创建和初始化成功")
    except Exception as e:
        print(f"✗ NewMaskPayloadStage失败: {e}")
        traceback.print_exc()
    print()

def test_executor_creation():
    """测试执行器创建"""
    print("=== 执行器创建测试 ===")
    
    try:
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        
        # 测试最简单的配置
        simple_config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=False,
            enable_mask=False
        )
        
        if simple_config:
            print(f"简单配置创建成功: {simple_config}")
            
            try:
                executor = create_pipeline_executor(simple_config)
                print("✓ 简单配置执行器创建成功")
            except Exception as e:
                print(f"✗ 简单配置执行器创建失败: {e}")
                traceback.print_exc()
        else:
            print("✗ 简单配置创建失败")
            
        # 测试包含mask的配置
        full_config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True
        )
        
        if full_config:
            print(f"完整配置创建成功: {full_config}")
            
            try:
                executor = create_pipeline_executor(full_config)
                print("✓ 完整配置执行器创建成功")
            except Exception as e:
                print(f"✗ 完整配置执行器创建失败: {e}")
                traceback.print_exc()
        else:
            print("✗ 完整配置创建失败")
            
    except Exception as e:
        print(f"执行器创建测试失败: {e}")
        traceback.print_exc()
    print()

def test_tls_marker_specifically():
    """专门测试TLS Marker组件"""
    print("=== TLS Marker专项测试 ===")

    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker

        # 创建TLS Marker
        marker = TLSProtocolMarker({})
        print("✓ TLSProtocolMarker创建成功")

        # 尝试初始化
        try:
            success = marker.initialize()
            if success:
                print("✓ TLSProtocolMarker初始化成功")
            else:
                print("✗ TLSProtocolMarker初始化返回False")
        except Exception as e:
            print(f"✗ TLSProtocolMarker初始化失败: {e}")
            traceback.print_exc()

    except Exception as e:
        print(f"TLS Marker测试失败: {e}")
        traceback.print_exc()
    print()

def test_windows_specific_issues():
    """测试Windows特定问题"""
    print("=== Windows特定问题测试 ===")

    # 测试subprocess调用
    try:
        import subprocess
        result = subprocess.run(['echo', 'test'], capture_output=True, text=True, timeout=5)
        if result.stdout is None:
            print("✗ subprocess.run返回None stdout - 这可能是Windows打包应用的问题")
        else:
            print("✓ subprocess.run正常工作")
    except Exception as e:
        print(f"✗ subprocess测试失败: {e}")

    # 测试文件权限
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test")
            tmp_path = tmp.name

        # 尝试读取
        with open(tmp_path, 'rb') as f:
            data = f.read()

        # 清理
        os.unlink(tmp_path)
        print("✓ 文件操作正常")
    except Exception as e:
        print(f"✗ 文件操作失败: {e}")

    # 测试路径处理
    try:
        from pathlib import Path
        test_path = Path("test_dir") / "test_file.txt"
        print(f"✓ 路径处理正常: {test_path}")
    except Exception as e:
        print(f"✗ 路径处理失败: {e}")

    print()

def simulate_windows_environment():
    """模拟Windows环境进行测试"""
    print("=== 模拟Windows环境测试 ===")

    # 临时修改os.name来模拟Windows
    original_os_name = os.name
    try:
        os.name = 'nt'

        # 重新测试依赖检查
        try:
            from pktmask.infrastructure.dependency.checker import DependencyChecker
            checker = DependencyChecker()

            # 在模拟Windows环境下检查tshark
            print("模拟Windows环境下的tshark检查...")
            # 注意：这只是模拟，实际的tshark路径检查仍然会基于真实的文件系统

        except Exception as e:
            print(f"模拟Windows环境测试失败: {e}")

    finally:
        # 恢复原始os.name
        os.name = original_os_name

    print()

def main():
    """主函数"""
    print("Windows平台PipelineExecutor创建失败诊断")
    print("=" * 50)

    check_basic_environment()
    check_imports()
    check_dependencies()
    test_pipeline_config()
    test_stage_creation()
    test_executor_creation()
    test_tls_marker_specifically()
    test_windows_specific_issues()
    simulate_windows_environment()

    print("诊断完成")
    print("\n=== 建议的解决方案 ===")
    print("基于诊断结果，Windows上的'failed to create executor'错误可能由以下原因导致：")
    print("1. TShark依赖检查在Windows打包环境下失败")
    print("2. subprocess.run在Windows下返回None stdout/stderr")
    print("3. 文件权限或路径访问问题")
    print("4. Windows特定的模块导入或初始化问题")
    print("\n建议检查：")
    print("- 确保Wireshark已正确安装")
    print("- 检查应用是否以管理员权限运行")
    print("- 验证tshark.exe是否在系统PATH中")
    print("- 检查Windows防病毒软件是否阻止了subprocess调用")

if __name__ == "__main__":
    main()
