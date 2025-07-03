#!/usr/bin/env python3
"""
MaskStage 核心组件诊断脚本

专门用于诊断 TSharkEnhancedMaskProcessor 的三个核心组件：
1. TSharkTLSAnalyzer (TShark分析器)
2. TLSMaskRuleGenerator (规则生成器) 
3. ScapyMaskApplier (Scapy应用器)

该脚本验证协议适配模式是否正常工作，还是降级到了 fallback 模式。

使用方法：
python scripts/diagnose_maskstage_components.py [test.pcap]
"""

import sys
import logging
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

def test_core_components_import():
    """测试核心组件导入状态"""
    print("🔍 阶段 1: 测试核心组件导入状态")
    print("-" * 60)
    
    components = {}
    import_results = {}
    
    # 测试 TSharkTLSAnalyzer 导入
    try:
        from src.pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
        components['tshark_tls_analyzer'] = TSharkTLSAnalyzer
        import_results['tshark_tls_analyzer'] = True
        print("✅ TSharkTLSAnalyzer 导入成功")
    except ImportError as e:
        import_results['tshark_tls_analyzer'] = False
        print(f"❌ TSharkTLSAnalyzer 导入失败: {e}")
    except Exception as e:
        import_results['tshark_tls_analyzer'] = False
        print(f"❌ TSharkTLSAnalyzer 导入异常: {e}")
    
    # 测试 TLSMaskRuleGenerator 导入
    try:
        from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
        components['tls_mask_rule_generator'] = TLSMaskRuleGenerator
        import_results['tls_mask_rule_generator'] = True
        print("✅ TLSMaskRuleGenerator 导入成功")
    except ImportError as e:
        import_results['tls_mask_rule_generator'] = False
        print(f"❌ TLSMaskRuleGenerator 导入失败: {e}")
    except Exception as e:
        import_results['tls_mask_rule_generator'] = False
        print(f"❌ TLSMaskRuleGenerator 导入异常: {e}")
    
    # 测试 ScapyMaskApplier 导入
    try:
        from src.pktmask.core.processors.scapy_mask_applier import ScapyMaskApplier
        components['scapy_mask_applier'] = ScapyMaskApplier
        import_results['scapy_mask_applier'] = True
        print("✅ ScapyMaskApplier 导入成功")
    except ImportError as e:
        import_results['scapy_mask_applier'] = False
        print(f"❌ ScapyMaskApplier 导入失败: {e}")
    except Exception as e:
        import_results['scapy_mask_applier'] = False
        print(f"❌ ScapyMaskApplier 导入异常: {e}")
    
    # 测试 TSharkEnhancedMaskProcessor 导入
    try:
        from src.pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
        components['tshark_enhanced_mask_processor'] = TSharkEnhancedMaskProcessor
        import_results['tshark_enhanced_mask_processor'] = True
        print("✅ TSharkEnhancedMaskProcessor 导入成功")
    except ImportError as e:
        import_results['tshark_enhanced_mask_processor'] = False
        print(f"❌ TSharkEnhancedMaskProcessor 导入失败: {e}")
    except Exception as e:
        import_results['tshark_enhanced_mask_processor'] = False
        print(f"❌ TSharkEnhancedMaskProcessor 导入异常: {e}")
    
    return components, import_results

def test_processor_initialization():
    """测试处理器初始化"""
    print("\n🔍 阶段 2: 测试处理器初始化")
    print("-" * 60)
    
    try:
        from src.pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
        from src.pktmask.core.processors.base_processor import ProcessorConfig
        
        # 创建处理器配置
        config = ProcessorConfig(
            enabled=True,
            name="tshark_enhanced_mask_debug",
            priority=1
        )
        
        print(f"📋 创建处理器配置: {config.name}")
        
        # 创建处理器实例
        processor = TSharkEnhancedMaskProcessor(config)
        print("✅ TSharkEnhancedMaskProcessor 实例创建成功")
        
        # 测试初始化
        init_success = processor.initialize()
        print(f"📋 处理器初始化结果: {init_success}")
        
        if init_success:
            print("✅ 处理器初始化成功")
        else:
            print("❌ 处理器初始化失败")
        
        return processor, init_success
        
    except Exception as e:
        print(f"❌ 处理器初始化异常: {e}")
        traceback.print_exc()
        return None, False

def test_core_components_availability(processor):
    """测试核心组件可用性"""
    print("\n🔍 阶段 3: 测试核心组件可用性")
    print("-" * 60)
    
    if not processor:
        print("❌ 处理器实例不可用，跳过核心组件测试")
        return False
    
    try:
        # 检查 _has_core_components 方法
        if hasattr(processor, '_has_core_components'):
            has_components = processor._has_core_components()
            print(f"📋 _has_core_components() 返回: {has_components}")
            
            if has_components:
                print("✅ 核心组件全部可用")
                
                # 详细检查各个组件
                if hasattr(processor, '_tshark_analyzer'):
                    analyzer_status = processor._tshark_analyzer is not None
                    print(f"  📋 TShark分析器: {analyzer_status}")
                
                if hasattr(processor, '_rule_generator'):
                    generator_status = processor._rule_generator is not None
                    print(f"  📋 规则生成器: {generator_status}")
                
                if hasattr(processor, '_scapy_applier'):
                    applier_status = processor._scapy_applier is not None
                    print(f"  📋 Scapy应用器: {applier_status}")
                    
            else:
                print("❌ 核心组件不完整")
                
                # 检查哪些组件缺失
                if hasattr(processor, '_tshark_analyzer'):
                    if processor._tshark_analyzer is None:
                        print("  ❌ TShark分析器缺失")
                    else:
                        print("  ✅ TShark分析器存在")
                
                if hasattr(processor, '_rule_generator'):
                    if processor._rule_generator is None:
                        print("  ❌ 规则生成器缺失")
                    else:
                        print("  ✅ 规则生成器存在")
                
                if hasattr(processor, '_scapy_applier'):
                    if processor._scapy_applier is None:
                        print("  ❌ Scapy应用器缺失")
                    else:
                        print("  ✅ Scapy应用器存在")
            
            return has_components
        else:
            print("❌ 处理器缺少 _has_core_components 方法")
            return False
            
    except Exception as e:
        print(f"❌ 检查核心组件时出错: {e}")
        traceback.print_exc()
        return False

def test_individual_component_creation():
    """测试各个核心组件的单独创建"""
    print("\n🔍 阶段 4: 测试各个核心组件的单独创建")
    print("-" * 60)
    
    component_instances = {}
    
    # 测试 TSharkTLSAnalyzer 创建
    try:
        from src.pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
        
        analyzer_config = {
            'tshark_executable_paths': [],  # 将使用默认路径
            'tshark_timeout_seconds': 60,
            'enable_detailed_logging': True
        }
        
        analyzer = TSharkTLSAnalyzer(analyzer_config)
        component_instances['tshark_tls_analyzer'] = analyzer
        print("✅ TSharkTLSAnalyzer 实例创建成功")
        
        # 测试初始化
        if hasattr(analyzer, 'initialize'):
            init_result = analyzer.initialize()
            print(f"  📋 TSharkTLSAnalyzer 初始化: {init_result}")
        
    except Exception as e:
        print(f"❌ TSharkTLSAnalyzer 创建失败: {e}")
    
    # 测试 TLSMaskRuleGenerator 创建
    try:
        from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
        
        generator_config = {
            'preserve_ratio': 0.3,
            'min_preserve_bytes': 100,
            'enable_detailed_logging': True
        }
        
        generator = TLSMaskRuleGenerator(generator_config)
        component_instances['tls_mask_rule_generator'] = generator
        print("✅ TLSMaskRuleGenerator 实例创建成功")
        
    except Exception as e:
        print(f"❌ TLSMaskRuleGenerator 创建失败: {e}")
    
    # 测试 ScapyMaskApplier 创建
    try:
        from src.pktmask.core.processors.scapy_mask_applier import ScapyMaskApplier
        
        applier_config = {
            'enable_detailed_logging': True,
            'enable_boundary_safety': True
        }
        
        applier = ScapyMaskApplier(applier_config)
        component_instances['scapy_mask_applier'] = applier
        print("✅ ScapyMaskApplier 实例创建成功")
        
    except Exception as e:
        print(f"❌ ScapyMaskApplier 创建失败: {e}")
    
    return component_instances

def test_tshark_tool_detection():
    """测试 TShark 工具检测"""
    print("\n🔍 阶段 5: TShark 工具检测")
    print("-" * 60)
    
    try:
        from src.pktmask.config.defaults import get_tshark_paths
        
        # 获取 TShark 路径
        tshark_paths = get_tshark_paths()
        print(f"📋 TShark 候选路径: {tshark_paths}")
        
        # 测试 TShark 可用性
        import subprocess
        import shutil
        
        # 检查系统 PATH 中的 tshark
        tshark_in_path = shutil.which('tshark')
        if tshark_in_path:
            print(f"✅ TShark 在 PATH 中找到: {tshark_in_path}")
            
            # 测试 TShark 版本
            try:
                result = subprocess.run(['tshark', '-v'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    print(f"✅ TShark 版本检测成功: {version_line}")
                    
                    # 测试 TShark 功能
                    result = subprocess.run(['tshark', '-G', 'fields'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print("✅ TShark 功能验证成功")
                        return True
                    else:
                        print(f"❌ TShark 功能验证失败: {result.stderr}")
                else:
                    print(f"❌ TShark 版本检测失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("❌ TShark 命令超时")
            except Exception as e:
                print(f"❌ TShark 测试异常: {e}")
        else:
            print("❌ TShark 在 PATH 中未找到")
        
        return False
        
    except Exception as e:
        print(f"❌ TShark 检测异常: {e}")
        return False

def test_tshark_initialization_detailed(tshark_analyzer):
    """详细测试 TShark 分析器初始化"""
    print("\n🔧 TShark 分析器详细初始化测试")
    print("-" * 40)
    
    if not tshark_analyzer:
        print("❌ TShark 分析器实例不可用")
        return False
    
    try:
        # 检查分析器属性
        if hasattr(tshark_analyzer, '_config'):
            print(f"📋 TShark 配置: {tshark_analyzer._config}")
        
        # 检查工具路径配置
        if hasattr(tshark_analyzer, '_tshark_executable_paths'):
            print(f"📋 TShark 可执行路径: {tshark_analyzer._tshark_executable_paths}")
        
        # 检查是否已初始化
        if hasattr(tshark_analyzer, '_tshark_path'):
            tshark_path = getattr(tshark_analyzer, '_tshark_path', None)
            print(f"📋 TShark 最终路径: {tshark_path}")
            
            if tshark_path:
                print("✅ TShark 路径已确定")
                return True
            else:
                print("❌ TShark 路径未确定")
        
        return False
        
    except Exception as e:
        print(f"❌ TShark 详细测试异常: {e}")
        return False

def test_core_pipeline_execution(processor, test_file):
    """测试核心管道执行"""
    print("\n🚀 核心管道执行测试")
    print("-" * 40)
    
    if not processor or not processor._has_core_components():
        print("❌ 处理器或核心组件不可用")
        return False
    
    if not test_file or not Path(test_file).exists():
        print("❌ 测试文件不可用，跳过管道测试")
        return False
    
         try:
         import time
         output_file = f"debug_output_{int(time.time())}.pcap"
        
        print(f"📋 测试文件: {test_file}")
        print(f"📋 输出文件: {output_file}")
        
        # 执行处理
        import time as time_module
        start_time = time_module.time()
        result = processor.process_file(test_file, output_file)
        duration = time_module.time() - start_time
        
        print(f"⏱️  处理耗时: {duration:.2f}秒")
        
        if result and hasattr(result, 'success') and result.success:
            print("✅ 核心管道执行成功")
            
            # 显示统计信息
            if hasattr(result, 'stats'):
                stats = result.stats
                print(f"📊 统计信息: {stats}")
            
            return True
        else:
            print("❌ 核心管道执行失败")
            if result and hasattr(result, 'error'):
                print(f"错误信息: {result.error}")
            return False
            
    except Exception as e:
        print(f"❌ 管道测试异常: {e}")
        traceback.print_exc()
        return False

def analyze_initialization_sequence(processor):
    """分析初始化序列"""
    if not processor:
        return
    
    print("📋 处理器初始化序列分析:")
    
    # 检查处理器状态
    if hasattr(processor, '_is_initialized'):
        print(f"  - 处理器已初始化: {processor._is_initialized}")
    
    # 检查核心组件初始化方法
    if hasattr(processor, '_initialize_core_components'):
        print("  - 核心组件初始化方法存在")
    
    # 检查是否有降级处理器
    if hasattr(processor, '_fallback_processor'):
        fallback = getattr(processor, '_fallback_processor', None)
        if fallback:
            print("  - 发现降级处理器，可能已启用降级模式")
        else:
            print("  - 无降级处理器，使用正常模式")

def main():
    """主函数"""
    print("🔍 MaskStage 核心组件诊断")
    print("="*80)
    
    # 设置日志
    setup_logging()
    
    # 获取测试文件
    test_file = None
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        if not Path(test_file).exists():
            print(f"⚠️ 测试文件不存在: {test_file}")
            test_file = None
    
    if not test_file:
        # 尝试使用默认测试文件
        default_test_files = [
            "tests/data/tls/tls_1_0_multi_segment_google-https.pcap",
            "tests/data/tls/ssl_3.pcapng"
        ]
        for test_path in default_test_files:
            if Path(test_path).exists():
                test_file = test_path
                break
    
    if test_file:
        print(f"📁 使用测试文件: {test_file}")
    else:
        print("⚠️ 没有可用的测试文件，将跳过实际处理测试")
    
    test_results = {}
    
    try:
        # 1. 测试核心组件导入
        components, import_results = test_core_components_import()
        test_results.update(import_results)
        
        # 2. 测试处理器初始化
        processor, init_success = test_processor_initialization()
        test_results['processor_initialization'] = init_success
        
        # 3. 测试核心组件可用性
        if processor:
            has_components = test_core_components_availability(processor)
            test_results['has_core_components'] = has_components
        else:
            test_results['has_core_components'] = False
        
        # 4. 测试各个组件单独创建
        print("\n🔍 阶段 4: 测试各个组件单独创建")
        component_instances = test_individual_component_creation()
        test_results['individual_component_creation'] = len(component_instances) > 0
        
        # 5. TShark 工具检测
        tshark_available = test_tshark_tool_detection()
        test_results['tshark_tool_available'] = tshark_available
        
        # 6. 核心管道执行测试
        if processor and processor._has_core_components():
            pipeline_success = test_core_pipeline_execution(processor, test_file)
            test_results['pipeline_execution'] = pipeline_success
        else:
            print("❌ 核心组件不可用，跳过管道测试")
            test_results['pipeline_execution'] = False
        
        # 6. TShark详细诊断
        print("\n🔧 阶段 6: TShark详细诊断")
        tshark_analyzer = component_instances.get('tshark_tls_analyzer')
        if tshark_analyzer:
            tshark_detailed = test_tshark_initialization_detailed(tshark_analyzer)
            test_results['tshark_detailed'] = tshark_detailed
        else:
            test_results['tshark_detailed'] = False
        
        # 7. 初始化序列分析
        print("\n🔍 阶段 7: 初始化序列分析")
        if processor:
            analyze_initialization_sequence(processor)
        
    except Exception as e:
        print(f"❌ 诊断过程出错: {e}")
        traceback.print_exc()
    
    # 输出诊断摘要
    print("\n" + "="*80)
    print("📊 诊断摘要")
    print("="*80)
    
    for test_name, result in test_results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test_name}: {result}")
    
    # 输出建议
    print("\n💡 诊断建议:")
    if not test_results.get('has_core_components', False):
        print("   🔧 核心组件不可用，需要检查:")
        print("      - TShark工具是否安装且版本兼容")
        print("      - 三个核心组件的导入和初始化状态")
        print("      - 配置参数是否正确")
    
    if test_results.get('has_core_components', False):
        print("   ✅ 核心组件可用，应该使用协议适配模式")
    else:
        print("   ⚠️ 核心组件不可用，系统会降级到 fallback_enhanced_trimmer 模式")
    
    if test_results.get('pipeline_execution', False):
        print("   🚀 核心管道执行成功，可以继续调试 TLS-23 跨包处理")
    else:
        print("   ⚠️ 核心管道执行失败，需要先解决管道问题")

if __name__ == "__main__":
    main() 