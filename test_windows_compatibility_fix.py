#!/usr/bin/env python3
"""
测试Windows兼容性修复的有效性

专门验证我们对"Marker模块初始化返回False"错误的修复
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
            logging.FileHandler('windows_compatibility_test.log', mode='w', encoding='utf-8')
        ]
    )
    
    # 启用所有相关模块的调试日志
    debug_loggers = [
        'pktmask.services.pipeline_service',
        'pktmask.core.pipeline.executor',
        'pktmask.core.pipeline.stages.mask_payload_v2.stage',
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker',
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.base',
    ]
    
    for logger_name in debug_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
    
    print("Windows兼容性测试日志已启用")

def test_current_implementation():
    """测试当前的实现"""
    print("=== 测试当前实现 ===")
    
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
                print("✅ 执行器创建成功！")
                
                if hasattr(executor, 'stages'):
                    print(f"✓ 执行器包含{len(executor.stages)}个阶段:")
                    for i, stage in enumerate(executor.stages):
                        print(f"   {i+1}. {stage.name}")
                
                return True
                
            except Exception as e:
                print(f"❌ 执行器创建失败: {e}")
                
                # 分析错误类型
                error_msg = str(e)
                if "Marker模块初始化返回False" in error_msg:
                    print("   🎯 这是我们要解决的目标错误！")
                elif "Failed to create executor" in error_msg:
                    print("   🔍 这是执行器创建失败的通用错误")
                
                return False
        else:
            print("✗ 配置构建失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tls_marker_directly():
    """直接测试TLS Marker"""
    print("\n=== 直接测试TLS Marker ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        print("✓ TLSProtocolMarker导入成功")
        
        # 测试创建
        marker = TLSProtocolMarker({})
        print("✓ TLSProtocolMarker创建成功")
        
        # 测试初始化
        print("开始初始化...")
        success = marker.initialize()
        
        if success:
            print("✅ TLSProtocolMarker初始化成功")
            return True
        else:
            print("❌ TLSProtocolMarker初始化返回False")
            print("   这表明我们的Windows兼容性修复可能还不够完善")
            return False
            
    except Exception as e:
        print(f"❌ TLS Marker测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_newmaskpayloadstage_directly():
    """直接测试NewMaskPayloadStage"""
    print("\n=== 直接测试NewMaskPayloadStage ===")
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        
        print("✓ NewMaskPayloadStage导入成功")
        
        # 测试创建
        stage = NewMaskPayloadStage({"enabled": True, "protocol": "tls"})
        print("✓ NewMaskPayloadStage创建成功")
        
        # 测试初始化
        print("开始初始化...")
        try:
            stage.initialize()
            print("✅ NewMaskPayloadStage初始化成功")
            return True
        except Exception as e:
            print(f"❌ NewMaskPayloadStage初始化失败: {e}")
            
            # 分析错误
            error_msg = str(e)
            if "Marker模块初始化返回False" in error_msg:
                print("   🎯 确认这是Marker模块的问题")
            elif "RuntimeError" in str(type(e)):
                print("   🔍 这是一个运行时错误，可能与依赖相关")
            
            return False
            
    except Exception as e:
        print(f"❌ NewMaskPayloadStage测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_log_for_specific_errors():
    """分析日志中的特定错误"""
    print("\n=== 分析日志中的特定错误 ===")
    
    try:
        with open('windows_compatibility_test.log', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找特定的错误模式
        error_patterns = [
            "Marker模块初始化返回False",
            "TLS analyzer component initialization failed",
            "TShark execution failed",
            "FileNotFoundError",
            "PermissionError",
            "TimeoutExpired",
            "subprocess",
            "tshark"
        ]
        
        found_errors = {}
        lines = content.split('\n')
        
        for pattern in error_patterns:
            matching_lines = [line for line in lines if pattern.lower() in line.lower()]
            if matching_lines:
                found_errors[pattern] = matching_lines[-3:]  # 最后3行
        
        if found_errors:
            print("发现的特定错误模式:")
            for pattern, error_lines in found_errors.items():
                print(f"\n  {pattern}:")
                for line in error_lines:
                    print(f"    {line}")
        else:
            print("未发现特定的错误模式")
            
        # 查找Windows相关的日志
        windows_lines = [line for line in lines if 'windows' in line.lower()]
        if windows_lines:
            print(f"\nWindows相关日志 ({len(windows_lines)} 条):")
            for line in windows_lines[-5:]:  # 最后5条
                print(f"  {line}")
                
    except FileNotFoundError:
        print("日志文件不存在")
    except Exception as e:
        print(f"分析日志文件失败: {e}")

def provide_recommendations():
    """提供建议"""
    print("\n=== 建议和下一步 ===")
    
    print("基于测试结果，如果问题仍然存在，建议:")
    print()
    print("1. 🔍 检查Windows环境:")
    print("   - 确保Wireshark已正确安装")
    print("   - 检查tshark.exe是否在系统PATH中")
    print("   - 尝试在命令行直接运行 'tshark -v'")
    print()
    print("2. 🛠️ 权限问题:")
    print("   - 以管理员权限运行PktMask")
    print("   - 检查Windows防病毒软件是否阻止了应用")
    print("   - 确保应用有权限执行subprocess")
    print()
    print("3. 📋 收集更多信息:")
    print("   - 在Windows环境下运行此测试脚本")
    print("   - 提供完整的错误日志")
    print("   - 检查Windows事件查看器中的相关错误")
    print()
    print("4. 🔧 可能的进一步修复:")
    print("   - 添加更多的Windows特定容错处理")
    print("   - 考虑提供tshark的替代方案")
    print("   - 实现完全离线的掩码模式")

def main():
    """主函数"""
    print("PktMask Windows兼容性修复测试")
    print("=" * 50)
    print(f"平台: {platform.system()} {platform.release()}")
    print()
    
    # 设置调试日志
    setup_debug_logging()
    
    # 运行测试
    results = []
    
    print("运行各项测试...")
    results.append(("TLS Marker直接测试", test_tls_marker_directly()))
    results.append(("NewMaskPayloadStage直接测试", test_newmaskpayloadstage_directly()))
    results.append(("完整执行器创建测试", test_current_implementation()))
    
    # 分析日志
    analyze_log_for_specific_errors()
    
    # 总结结果
    print("\n" + "=" * 50)
    print("测试结果总结:")
    
    all_passed = True
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 所有测试通过！Windows兼容性修复有效")
        print("如果在实际Windows环境中仍有问题，可能是环境特定的问题")
    else:
        print("⚠️  部分测试失败，需要进一步修复")
        
    provide_recommendations()
    
    print(f"\n📋 详细日志已保存到: windows_compatibility_test.log")

if __name__ == "__main__":
    main()
