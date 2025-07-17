#!/usr/bin/env python3
"""
Windows平台PipelineExecutor修复验证脚本

专门用于验证"Failed to create pipeline: failed to create executor"错误的修复效果
"""

import sys
import platform

def main():
    """主验证函数"""
    print("PktMask Windows平台修复验证")
    print("=" * 40)
    print(f"平台: {platform.system()} {platform.release()}")
    
    if platform.system() != "Windows":
        print("⚠️  注意：当前不在Windows环境，但修复应该向后兼容")
    
    print("\n正在验证修复效果...")
    
    try:
        # 1. 测试基础导入
        print("1. 测试基础模块导入...")
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        print("   ✓ 基础模块导入成功")
        
        # 2. 测试配置构建
        print("2. 测试管道配置构建...")
        config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True
        )
        if config:
            print(f"   ✓ 配置构建成功，包含{len(config)}个阶段")
        else:
            print("   ✗ 配置构建失败")
            return False
        
        # 3. 测试执行器创建（关键测试）
        print("3. 测试执行器创建（关键测试）...")
        try:
            executor = create_pipeline_executor(config)
            print("   ✅ 执行器创建成功 - 修复生效！")
            
            # 验证执行器结构
            if hasattr(executor, 'stages'):
                print(f"   ✓ 执行器包含{len(executor.stages)}个处理阶段")
                for i, stage in enumerate(executor.stages):
                    print(f"      阶段{i+1}: {stage.name}")
            
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            if "failed to create executor" in error_msg:
                print("   ❌ 执行器创建失败 - 这是目标修复的错误！")
                print(f"   错误详情: {e}")
                print("\n🔧 修复建议:")
                print("   1. 确保已应用最新的Windows兼容性修复")
                print("   2. 检查Wireshark是否正确安装")
                print("   3. 尝试以管理员权限运行应用")
                print("   4. 检查Windows防病毒软件是否阻止了应用")
                return False
            else:
                print(f"   ❌ 执行器创建失败（其他原因）: {e}")
                return False
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        print("请确保在正确的Python环境中运行此脚本")
        return False
    except Exception as e:
        print(f"❌ 验证过程出现异常: {e}")
        return False

def quick_test():
    """快速测试函数，用于集成到其他脚本"""
    try:
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        config = build_pipeline_config(enable_dedup=True, enable_anon=True, enable_mask=True)
        if config:
            executor = create_pipeline_executor(config)
            return True
    except:
        return False

if __name__ == "__main__":
    success = main()
    
    print("\n" + "=" * 40)
    if success:
        print("✅ 验证通过！Windows平台修复生效")
        print("\n现在可以正常使用PktMask的所有功能：")
        print("- Remove Dupes (去重)")
        print("- Anonymize IPs (IP匿名化)")
        print("- Mask Payloads (载荷掩码)")
        sys.exit(0)
    else:
        print("❌ 验证失败！需要进一步调试")
        print("\n请检查:")
        print("1. 是否在Windows环境下运行")
        print("2. 是否已正确应用修复")
        print("3. 系统依赖是否满足要求")
        sys.exit(1)
