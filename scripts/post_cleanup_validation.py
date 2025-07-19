#!/usr/bin/env python3
"""
清理后功能验证脚本
确保清理操作没有破坏任何功能

基于REVISED_DEPRECATED_CODE_CLEANUP_ACTION_PLAN.md制定
"""

import os
import subprocess
import sys
import time
from pathlib import Path

def test_module_imports():
    """测试关键模块导入"""
    print("📦 测试模块导入...")
    
    # 关键模块列表
    critical_modules = [
        'pktmask',
        'pktmask.core',
        'pktmask.core.pipeline',
        'pktmask.core.pipeline.executor',
        'pktmask.core.processors',
        'pktmask.core.processors.registry',
        'pktmask.gui',
        'pktmask.gui.main_window',
        'pktmask.cli',
        'pktmask.infrastructure',
        'pktmask.infrastructure.logging'
    ]
    
    failed_imports = []
    
    for module in critical_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            failed_imports.append((module, str(e)))
        except Exception as e:
            print(f"⚠️ {module}: 意外错误 - {e}")
            failed_imports.append((module, f"意外错误: {e}"))
    
    if failed_imports:
        print(f"\n❌ 导入测试失败: {len(failed_imports)}/{len(critical_modules)} 个模块")
        return False, failed_imports
    else:
        print(f"\n✅ 导入测试通过: {len(critical_modules)}/{len(critical_modules)} 个模块")
        return True, []

def test_processor_registry():
    """测试处理器注册表功能"""
    print("\n🔧 测试处理器注册表...")
    
    try:
        from pktmask.core.processors.registry import ProcessorRegistry
        
        # 测试处理器列表
        processors = ProcessorRegistry.list_processors()
        print(f"✅ 可用处理器: {processors}")
        
        # 测试获取处理器
        expected_processors = ['anonymize_ips', 'remove_dupes', 'mask_payloads']
        missing_processors = []
        
        for proc_name in expected_processors:
            try:
                processor = ProcessorRegistry.get_processor(proc_name)
                print(f"✅ {proc_name}: {processor.__class__.__name__}")
            except Exception as e:
                print(f"❌ {proc_name}: {e}")
                missing_processors.append(proc_name)
        
        if missing_processors:
            return False, f"缺少处理器: {missing_processors}"
        else:
            return True, f"所有处理器正常: {expected_processors}"
            
    except Exception as e:
        return False, f"处理器注册表错误: {e}"

def test_pipeline_executor():
    """测试管道执行器"""
    print("\n⚙️ 测试管道执行器...")
    
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        from pktmask.core.pipeline.config import build_pipeline_config
        
        # 创建测试配置
        config = build_pipeline_config(
            enable_anon=True,
            enable_dedup=True,
            enable_mask=True
        )
        
        if not config:
            return False, "无法创建管道配置"
        
        # 创建执行器
        executor = PipelineExecutor(config)
        print(f"✅ 管道执行器创建成功: {len(config)} 个阶段")
        
        # 测试阶段信息
        for i, stage in enumerate(executor.stages):
            stage_name = getattr(stage, 'name', stage.__class__.__name__)
            print(f"   阶段 {i+1}: {stage_name}")
        
        return True, f"管道执行器正常: {len(config)} 个阶段"
        
    except Exception as e:
        return False, f"管道执行器错误: {e}"

def test_gui_startup():
    """测试GUI启动"""
    print("\n🖥️ 测试GUI启动...")
    
    try:
        # 设置测试模式环境变量
        env = os.environ.copy()
        env['PKTMASK_TEST_MODE'] = 'true'
        env['PKTMASK_HEADLESS'] = 'true'
        
        # 测试GUI模块导入和初始化
        result = subprocess.run([
            sys.executable, '-c',
            '''
import os
os.environ["PKTMASK_TEST_MODE"] = "true"
os.environ["PKTMASK_HEADLESS"] = "true"
from pktmask.gui.main_window import main
window = main()
if window is not None:
    print("GUI_TEST_SUCCESS")
else:
    print("GUI_TEST_FAILED")
'''
        ], env=env, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "GUI_TEST_SUCCESS" in result.stdout:
            print("✅ GUI启动测试通过")
            return True, "GUI启动正常"
        else:
            print("❌ GUI启动测试失败:")
            print(f"   返回码: {result.returncode}")
            print(f"   输出: {result.stdout}")
            print(f"   错误: {result.stderr}")
            return False, f"GUI启动失败: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, "GUI启动超时"
    except Exception as e:
        return False, f"GUI测试错误: {e}"

def test_cli_commands():
    """测试CLI命令"""
    print("\n💻 测试CLI命令...")
    
    cli_commands = [
        (['--help'], "主帮助"),
        (['dedup', '--help'], "去重命令帮助"),
        (['anon', '--help'], "匿名化命令帮助"),
        (['mask', '--help'], "掩码命令帮助")
    ]
    
    failed_commands = []
    
    for cmd_args, description in cli_commands:
        try:
            result = subprocess.run([
                sys.executable, '-m', 'pktmask'
            ] + cmd_args, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print(f"✅ {description}")
            else:
                print(f"❌ {description}: 返回码 {result.returncode}")
                failed_commands.append((description, result.stderr))
                
        except subprocess.TimeoutExpired:
            print(f"❌ {description}: 超时")
            failed_commands.append((description, "超时"))
        except Exception as e:
            print(f"❌ {description}: {e}")
            failed_commands.append((description, str(e)))
    
    if failed_commands:
        return False, f"CLI命令失败: {[desc for desc, _ in failed_commands]}"
    else:
        return True, "所有CLI命令正常"

def test_configuration_system():
    """测试配置系统"""
    print("\n⚙️ 测试配置系统...")
    
    try:
        from pktmask.infrastructure.config import get_app_config
        
        # 测试配置加载
        config = get_app_config()
        print(f"✅ 配置加载成功")
        
        # 测试关键配置项
        required_sections = ['ui', 'processing', 'logging']
        missing_sections = []
        
        for section in required_sections:
            if hasattr(config, section):
                print(f"✅ 配置节: {section}")
            else:
                print(f"❌ 缺少配置节: {section}")
                missing_sections.append(section)
        
        if missing_sections:
            return False, f"缺少配置节: {missing_sections}"
        else:
            return True, "配置系统正常"
            
    except Exception as e:
        return False, f"配置系统错误: {e}"

def test_logging_system():
    """测试日志系统"""
    print("\n📝 测试日志系统...")
    
    try:
        from pktmask.infrastructure.logging import get_logger
        
        # 创建测试日志器
        logger = get_logger("test_validation")
        
        # 测试日志记录
        logger.info("测试日志消息")
        logger.debug("测试调试消息")
        logger.warning("测试警告消息")
        
        print("✅ 日志系统正常")
        return True, "日志系统正常"
        
    except Exception as e:
        return False, f"日志系统错误: {e}"

def run_comprehensive_validation():
    """运行综合验证"""
    print("🚀 PktMask清理后功能验证")
    print("="*60)
    
    # 检查工作目录
    if not Path("src/pktmask").exists():
        print("❌ 错误: 请在PktMask项目根目录运行此脚本")
        return False
    
    # 测试项目列表
    tests = [
        ("模块导入", test_module_imports),
        ("处理器注册表", test_processor_registry),
        ("管道执行器", test_pipeline_executor),
        ("配置系统", test_configuration_system),
        ("日志系统", test_logging_system),
        ("CLI命令", test_cli_commands),
        ("GUI启动", test_gui_startup)
    ]
    
    results = []
    total_tests = len(tests)
    passed_tests = 0
    
    print(f"\n🧪 开始执行 {total_tests} 项验证测试...\n")
    
    for test_name, test_func in tests:
        print(f"🔍 执行测试: {test_name}")
        try:
            success, message = test_func()
            results.append((test_name, success, message))
            if success:
                passed_tests += 1
                print(f"✅ {test_name}: 通过")
            else:
                print(f"❌ {test_name}: 失败 - {message}")
        except Exception as e:
            results.append((test_name, False, f"测试异常: {e}"))
            print(f"❌ {test_name}: 测试异常 - {e}")
        
        print()  # 空行分隔
    
    # 生成验证报告
    print("="*60)
    print("📋 验证结果报告")
    print("="*60)
    
    for test_name, success, message in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name:20} : {status}")
        if not success:
            print(f"{'':22} {message}")
    
    print(f"\n📊 总体结果: {passed_tests}/{total_tests} 项测试通过")
    
    if passed_tests == total_tests:
        print("🎉 所有验证测试通过! 清理操作成功，系统功能正常。")
        return True
    else:
        print("⚠️ 部分验证测试失败，请检查清理操作是否影响了系统功能。")
        return False

def main():
    """主函数"""
    try:
        success = run_comprehensive_validation()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⏹️ 验证被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 验证过程中发生意外错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
