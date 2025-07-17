#!/usr/bin/env python3
"""
测试Windows平台PipelineExecutor修复效果
"""

import os
import sys
import traceback
import platform

def test_dependency_checker_fix():
    """测试依赖检查器修复"""
    print("=== 测试依赖检查器修复 ===")
    
    try:
        from pktmask.infrastructure.dependency.checker import DependencyChecker
        checker = DependencyChecker()
        
        # 测试tshark检查
        result = checker.check_tshark()
        print(f"TShark检查状态: {result.status.name}")
        if result.path:
            print(f"TShark路径: {result.path}")
        if result.version_found:
            print(f"TShark版本: {result.version_found}")
        if result.error_message:
            print(f"错误信息: {result.error_message}")
        
        # 检查是否成功或有Windows兼容性处理
        if result.status.name in ['SATISFIED', 'EXECUTION_ERROR']:
            if "Windows compatibility" in (result.error_message or ""):
                print("✓ Windows兼容性处理生效")
            else:
                print("✓ TShark检查正常")
        else:
            print("✗ TShark检查失败")
            
    except Exception as e:
        print(f"✗ 依赖检查器测试失败: {e}")
        traceback.print_exc()
    
    print()

def test_tls_marker_fix():
    """测试TLS Marker修复"""
    print("=== 测试TLS Marker修复 ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        # 创建TLS Marker
        marker = TLSProtocolMarker({})
        print("✓ TLSProtocolMarker创建成功")
        
        # 测试初始化
        try:
            success = marker.initialize()
            if success:
                print("✓ TLSProtocolMarker初始化成功")
            else:
                print("✗ TLSProtocolMarker初始化返回False")
        except Exception as e:
            print(f"✗ TLSProtocolMarker初始化失败: {e}")
            # 检查是否是Windows兼容性相关的错误
            if "Windows" in str(e) or "timeout" in str(e).lower():
                print("  (可能是Windows兼容性问题，但已有处理逻辑)")
            traceback.print_exc()
            
    except Exception as e:
        print(f"✗ TLS Marker测试失败: {e}")
        traceback.print_exc()
    
    print()

def test_pipeline_executor_creation():
    """测试管道执行器创建"""
    print("=== 测试管道执行器创建 ===")
    
    try:
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        
        # 测试不同配置
        test_configs = [
            {"enable_dedup": True, "enable_anon": False, "enable_mask": False},
            {"enable_dedup": False, "enable_anon": True, "enable_mask": False},
            {"enable_dedup": True, "enable_anon": True, "enable_mask": False},
            {"enable_dedup": True, "enable_anon": True, "enable_mask": True},
        ]
        
        for i, config_params in enumerate(test_configs):
            try:
                config = build_pipeline_config(**config_params)
                if config:
                    executor = create_pipeline_executor(config)
                    stages = list(config.keys())
                    print(f"✓ 配置{i+1}执行器创建成功: {stages}")
                else:
                    print(f"✗ 配置{i+1}构建失败")
            except Exception as e:
                print(f"✗ 配置{i+1}执行器创建失败: {e}")
                # 检查是否是已知的Windows问题
                if "failed to create executor" in str(e).lower():
                    print(f"  这是目标修复的错误！")
                    traceback.print_exc()
                
    except Exception as e:
        print(f"✗ 管道执行器测试失败: {e}")
        traceback.print_exc()
    
    print()

def test_stage_initialization():
    """测试各阶段初始化"""
    print("=== 测试各阶段初始化 ===")
    
    # 测试DeduplicationStage
    try:
        from pktmask.core.pipeline.stages.dedup import DeduplicationStage
        stage = DeduplicationStage({"enabled": True})
        stage.initialize()
        print("✓ DeduplicationStage初始化成功")
    except Exception as e:
        print(f"✗ DeduplicationStage初始化失败: {e}")
    
    # 测试AnonStage
    try:
        from pktmask.core.pipeline.stages.anon_ip import AnonStage
        stage = AnonStage({"enabled": True})
        stage.initialize()
        print("✓ AnonStage初始化成功")
    except Exception as e:
        print(f"✗ AnonStage初始化失败: {e}")
    
    # 测试NewMaskPayloadStage
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        stage = NewMaskPayloadStage({"enabled": True, "protocol": "tls"})
        stage.initialize()
        print("✓ NewMaskPayloadStage初始化成功")
    except Exception as e:
        print(f"✗ NewMaskPayloadStage初始化失败: {e}")
        if "tshark" in str(e).lower() or "windows" in str(e).lower():
            print("  (可能是tshark相关的Windows问题)")
    
    print()

def simulate_gui_usage():
    """模拟GUI使用场景"""
    print("=== 模拟GUI使用场景 ===")
    
    try:
        # 模拟GUI中的管道创建流程
        from pktmask.services.pipeline_service import build_pipeline_config, create_pipeline_executor
        
        # 模拟用户选择了所有功能
        config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True
        )
        
        if not config:
            print("✗ GUI配置构建失败")
            return
        
        print(f"✓ GUI配置构建成功: {list(config.keys())}")
        
        # 尝试创建执行器（这是失败的关键点）
        try:
            executor = create_pipeline_executor(config)
            print("✅ GUI执行器创建成功 - 修复生效！")
            
            # 验证执行器有正确的stages
            if hasattr(executor, 'stages'):
                print(f"✓ 执行器包含{len(executor.stages)}个阶段")
            
        except Exception as e:
            print(f"❌ GUI执行器创建失败: {e}")
            print("这表明修复可能不完整，需要进一步调试")
            traceback.print_exc()
            
    except Exception as e:
        print(f"✗ GUI使用场景测试失败: {e}")
        traceback.print_exc()
    
    print()

def main():
    """主函数"""
    print("Windows平台PipelineExecutor修复效果测试")
    print("=" * 50)
    print(f"当前平台: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version}")
    print()
    
    # 运行各项测试
    test_dependency_checker_fix()
    test_tls_marker_fix()
    test_stage_initialization()
    test_pipeline_executor_creation()
    simulate_gui_usage()
    
    print("=" * 50)
    print("测试完成")
    print("\n如果所有测试都通过，说明Windows平台的修复生效")
    print("如果仍有失败，请检查具体的错误信息进行进一步调试")

if __name__ == "__main__":
    main()
