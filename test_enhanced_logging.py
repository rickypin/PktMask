#!/usr/bin/env python3
"""
测试增强的日志记录功能

专门用于捕获"Failed to create pipeline: failed to create executor"错误的详细信息
"""

import sys
import logging
import platform

def setup_detailed_logging():
    """设置详细的日志记录"""
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pktmask_debug.log', mode='w')
        ]
    )
    
    # 确保所有相关模块的日志都被记录
    loggers_to_enable = [
        'pktmask.services.pipeline_service',
        'pktmask.core.pipeline.executor',
        'pktmask.core.pipeline.stages.mask_payload_v2.stage',
        'pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker',
        'pktmask.core.pipeline.stages.dedup',
        'pktmask.core.pipeline.stages.anon_ip',
        'pktmask.infrastructure.dependency.checker'
    ]
    
    for logger_name in loggers_to_enable:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
    
    print("详细日志记录已启用")
    print(f"日志文件: pktmask_debug.log")

def test_executor_creation_with_logging():
    """测试执行器创建并记录详细日志"""
    print("=" * 60)
    print("测试PipelineExecutor创建（增强日志记录）")
    print("=" * 60)
    print(f"平台: {platform.system()} {platform.release()}")
    print()
    
    try:
        # 导入并测试
        print("1. 导入pipeline服务...")
        from pktmask.services.pipeline_service import create_pipeline_executor, build_pipeline_config
        print("   ✓ 导入成功")
        
        print("\n2. 构建管道配置...")
        config = build_pipeline_config(
            enable_dedup=True,
            enable_anon=True,
            enable_mask=True  # 这个可能是问题所在
        )
        
        if config:
            print(f"   ✓ 配置构建成功: {list(config.keys())}")
            print(f"   配置详情: {config}")
        else:
            print("   ✗ 配置构建失败")
            return False
        
        print("\n3. 创建管道执行器（关键步骤）...")
        print("   注意：如果失败，请查看详细日志信息")
        
        try:
            executor = create_pipeline_executor(config)
            print("   ✅ 执行器创建成功！")
            
            if hasattr(executor, 'stages'):
                print(f"   ✓ 执行器包含 {len(executor.stages)} 个阶段:")
                for i, stage in enumerate(executor.stages):
                    print(f"      {i+1}. {stage.name}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ 执行器创建失败: {e}")
            print(f"   错误类型: {type(e).__name__}")
            
            # 打印简化的错误信息
            error_msg = str(e).lower()
            if "failed to create executor" in error_msg:
                print("   这是我们要解决的目标错误！")
            
            print("\n   详细错误信息已记录到日志文件中")
            print("   请检查 pktmask_debug.log 获取完整的错误堆栈")
            
            return False
            
    except Exception as e:
        print(f"❌ 测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_individual_stages():
    """单独测试各个阶段的创建"""
    print("\n" + "=" * 60)
    print("单独测试各阶段创建")
    print("=" * 60)
    
    # 测试DeduplicationStage
    print("\n1. 测试DeduplicationStage...")
    try:
        from pktmask.core.pipeline.stages.dedup import DeduplicationStage
        stage = DeduplicationStage({"enabled": True})
        stage.initialize()
        print("   ✓ DeduplicationStage 创建和初始化成功")
    except Exception as e:
        print(f"   ✗ DeduplicationStage 失败: {e}")
    
    # 测试AnonStage
    print("\n2. 测试AnonStage...")
    try:
        from pktmask.core.pipeline.stages.anon_ip import AnonStage
        stage = AnonStage({"enabled": True})
        stage.initialize()
        print("   ✓ AnonStage 创建和初始化成功")
    except Exception as e:
        print(f"   ✗ AnonStage 失败: {e}")
    
    # 测试NewMaskPayloadStage（最可能的问题源）
    print("\n3. 测试NewMaskPayloadStage...")
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
        stage = NewMaskPayloadStage({"enabled": True, "protocol": "tls"})
        stage.initialize()
        print("   ✓ NewMaskPayloadStage 创建和初始化成功")
    except Exception as e:
        print(f"   ✗ NewMaskPayloadStage 失败: {e}")
        print("   这很可能是问题的根源！")

def analyze_log_file():
    """分析日志文件中的错误信息"""
    print("\n" + "=" * 60)
    print("分析日志文件")
    print("=" * 60)
    
    try:
        with open('pktmask_debug.log', 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # 查找错误相关的行
        error_lines = []
        for line_num, line in enumerate(log_content.splitlines(), 1):
            if any(keyword in line.lower() for keyword in ['error', 'failed', 'exception', 'traceback']):
                error_lines.append(f"Line {line_num}: {line}")
        
        if error_lines:
            print(f"发现 {len(error_lines)} 行错误相关信息:")
            for line in error_lines[-20:]:  # 显示最后20行错误信息
                print(f"  {line}")
        else:
            print("日志文件中未发现明显的错误信息")
            
    except FileNotFoundError:
        print("日志文件不存在")
    except Exception as e:
        print(f"分析日志文件时出错: {e}")

def main():
    """主函数"""
    print("PktMask 增强日志记录测试")
    print("用于诊断 'Failed to create pipeline: failed to create executor' 错误")
    
    # 设置详细日志
    setup_detailed_logging()
    
    # 运行测试
    success = test_executor_creation_with_logging()
    
    # 单独测试各阶段
    test_individual_stages()
    
    # 分析日志
    analyze_log_file()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试通过！执行器创建成功")
    else:
        print("❌ 测试失败！请查看上述日志信息")
        print("\n建议:")
        print("1. 检查 pktmask_debug.log 文件获取完整错误信息")
        print("2. 特别关注 NewMaskPayloadStage 相关的错误")
        print("3. 检查 TShark 依赖是否正确安装")
        print("4. 在Windows环境下运行此测试获取平台特定的错误信息")
    
    print(f"\n详细日志已保存到: pktmask_debug.log")

if __name__ == "__main__":
    main()
