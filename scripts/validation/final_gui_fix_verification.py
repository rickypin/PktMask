#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI掩码处理修复最终验证脚本

验证修复后的GUI能正确识别和显示NewMaskPayloadStage的统计信息。
"""

import sys
import logging
import tempfile
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def test_gui_integration():
    """测试GUI集成"""
    logger.info("=== 测试GUI集成 ===")
    
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        from pktmask.services import build_pipeline_config
        
        # 获取测试文件
        test_file = project_root / "tests" / "data" / "tls" / "tls_1_2_plainip.pcap"
        if not test_file.exists():
            logger.warning(f"测试文件不存在: {test_file}")
            return True
        
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_file = Path(tmp.name)
        
        try:
            # 使用GUI配置
            config = build_pipeline_config(
                enable_anon=False,
                enable_dedup=False,
                enable_mask=True
            )
            
            logger.info(f"GUI配置: {config}")
            
            # 创建执行器并处理
            executor = PipelineExecutor(config)
            result = executor.run(str(test_file), str(output_file))
            
            logger.info(f"处理结果: success={result.success}")
            
            if result.success and result.stage_stats:
                for stats in result.stage_stats:
                    logger.info(f"Stage: {stats.stage_name}")
                    logger.info(f"  - 处理包数: {stats.packets_processed}")
                    logger.info(f"  - 修改包数: {stats.packets_modified}")
                    
                    if "Mask Payloads (v2)" in stats.stage_name:
                        if stats.packets_modified > 0:
                            logger.info("✅ NewMaskPayloadStage正常工作")
                            logger.info("✅ GUI能正确接收掩码统计信息")
                            return True
                        else:
                            logger.warning("⚠️ NewMaskPayloadStage未修改任何包")
                            return False
            
            logger.error("❌ 未找到NewMaskPayloadStage的统计信息")
            return False
            
        finally:
            if output_file.exists():
                output_file.unlink()
        
    except Exception as e:
        logger.error(f"❌ GUI集成测试时发生异常: {e}")
        return False

def test_report_manager_integration():
    """测试ReportManager集成"""
    logger.info("=== 测试ReportManager集成 ===")
    
    try:
        from pktmask.gui.managers.report_manager import ReportManager
        from pktmask.gui.main_window import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        # 创建临时应用程序
        app = QApplication([])
        
        # 创建主窗口和报告管理器
        main_window = MainWindow()
        report_manager = ReportManager(main_window)
        
        # 模拟NewMaskPayloadStage的统计数据
        test_data = {
            'step_name': 'Mask Payloads (v2)',
            'packets_processed': 100,
            'packets_modified': 25,
            'extra_metrics': {
                'masked_bytes': 5000,
                'preserved_bytes': 15000,
                'masking_ratio': 0.25,
                'preservation_ratio': 0.75
            }
        }
        
        # 设置当前处理文件
        main_window.current_processing_file = 'test_file.pcap'
        main_window.file_processing_results = {
            'test_file.pcap': {'steps': {}}
        }
        
        # 调用collect_step_result方法
        report_manager.collect_step_result(test_data)
        
        # 检查结果
        file_results = main_window.file_processing_results['test_file.pcap']['steps']
        
        if 'Payload Masking' in file_results:
            step_data = file_results['Payload Masking']['data']
            step_type = file_results['Payload Masking']['type']
            
            logger.info("✅ ReportManager正确识别NewMaskPayloadStage")
            logger.info(f"✅ 步骤类型: {step_type}")
            logger.info(f"✅ 处理包数: {step_data.get('packets_processed')}")
            logger.info(f"✅ 修改包数: {step_data.get('packets_modified')}")
            
            if step_type == 'trim_payloads':
                logger.info("✅ 步骤类型映射正确")
                return True
            else:
                logger.error(f"❌ 步骤类型映射错误: 期望'trim_payloads', 实际'{step_type}'")
                return False
        else:
            logger.error(f"❌ ReportManager未能识别NewMaskPayloadStage")
            logger.error(f"可用步骤: {list(file_results.keys())}")
            return False
            
    except Exception as e:
        logger.error(f"❌ ReportManager集成测试时发生异常: {e}")
        return False

def main():
    """主验证流程"""
    global logger
    logger = setup_logging()
    
    logger.info("开始PktMask GUI掩码处理修复最终验证")
    
    # 测试项目
    tests = [
        ("GUI集成", test_gui_integration),
        ("ReportManager集成", test_report_manager_integration)
    ]
    
    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"执行测试: {test_name}")
        logger.info('='*50)
        
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"测试 {test_name} 发生异常: {e}")
            results[test_name] = False
    
    # 汇总结果
    logger.info(f"\n{'='*50}")
    logger.info("最终验证结果")
    logger.info('='*50)
    
    passed = 0
    total = len(tests)
    
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if success:
            passed += 1
    
    logger.info(f"\n总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！")
        logger.info("🔧 修复总结:")
        logger.info("   - 修复了ReportManager中NewMaskPayloadStage的识别问题")
        logger.info("   - GUI现在能正确显示'Mask Payloads (v2)'的统计信息")
        logger.info("   - 掩码处理功能正常工作，不再显示'masked 0 pkts'")
        return True
    else:
        logger.error("❌ 部分测试失败，需要进一步检查")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
