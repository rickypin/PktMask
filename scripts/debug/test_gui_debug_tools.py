#!/usr/bin/env python3
"""
GUI调试工具测试脚本

本脚本用于测试GUI调试工具的功能，验证调试流程的有效性。

使用方法：
    python scripts/debug/test_gui_debug_tools.py <test_pcap_file>
"""

import sys
import subprocess
from pathlib import Path

def test_debug_tools(test_file: str):
    """测试调试工具"""
    print("🧪 开始测试GUI调试工具")
    print("="*60)
    
    project_root = Path(__file__).parent.parent.parent
    
    # 1. 测试结构化调试脚本
    print("📋 步骤1: 测试结构化调试脚本")
    debug_script = project_root / "scripts" / "debug" / "gui_tls23_masking_debug.py"
    
    try:
        result = subprocess.run([
            sys.executable, str(debug_script), test_file
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ 结构化调试脚本执行成功")
            print("📊 输出摘要:")
            # 显示最后几行输出
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines[-10:]:
                print(f"   {line}")
        else:
            print("❌ 结构化调试脚本执行失败")
            print(f"错误输出: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("⏰ 结构化调试脚本执行超时")
    except Exception as e:
        print(f"❌ 结构化调试脚本执行异常: {e}")
    
    # 2. 测试插桩工具
    print(f"\n🔧 步骤2: 测试插桩工具")
    instrument_script = project_root / "scripts" / "debug" / "gui_debug_instrumentation.py"
    
    try:
        # 测试插桩
        print("   2.1 添加调试插桩...")
        result = subprocess.run([
            sys.executable, str(instrument_script), "instrument"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ 插桩添加成功")
        else:
            print(f"   ❌ 插桩添加失败: {result.stderr}")
            return
        
        # 测试恢复
        print("   2.2 恢复原始代码...")
        result = subprocess.run([
            sys.executable, str(instrument_script), "restore"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ 代码恢复成功")
        else:
            print(f"   ❌ 代码恢复失败: {result.stderr}")
            
    except Exception as e:
        print(f"   ❌ 插桩工具测试异常: {e}")
    
    # 3. 验证工具文件完整性
    print(f"\n📁 步骤3: 验证工具文件完整性")
    
    required_files = [
        "scripts/debug/gui_tls23_masking_debug.py",
        "scripts/debug/gui_debug_instrumentation.py",
        "scripts/debug/test_gui_debug_tools.py"
    ]
    
    all_files_exist = True
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (缺失)")
            all_files_exist = False
    
    if all_files_exist:
        print("   🎯 所有调试工具文件完整")
    else:
        print("   ⚠️ 部分调试工具文件缺失")
    
    # 4. 生成使用指南
    print(f"\n📖 步骤4: 生成使用指南")
    
    usage_guide = f"""
🔍 PktMask GUI TLS-23掩码调试指南
{'='*60}

📋 调试流程：

1️⃣ 运行结构化调试分析：
   python scripts/debug/gui_tls23_masking_debug.py {test_file}
   
   这将生成详细的调试报告，包括：
   - GUI配置传递链条追踪
   - NewMaskPayloadStage实例化验证
   - Marker模块TLS消息识别验证
   - Masker模块规则应用验证
   - 端到端GUI流程测试
   - TLS-23掩码效果验证

2️⃣ 如需更详细的运行时日志，可添加调试插桩：
   # 添加插桩
   python scripts/debug/gui_debug_instrumentation.py instrument
   
   # 运行GUI测试（手动操作GUI或运行自动化测试）
   
   # 恢复原始代码
   python scripts/debug/gui_debug_instrumentation.py restore

3️⃣ 分析调试结果：
   - 查看生成的调试报告 (debug_report.json)
   - 查看详细日志 (debug.log)
   - 根据问题分析和修复建议进行代码修改

🎯 重点关注环节：
- Marker模块是否正确识别TLS-23消息
- 保留规则是否正确排除TLS-23消息体
- Masker模块是否正确应用掩码规则
- 最终输出文件中TLS-23消息体是否被置零

⚠️ 注意事项：
- 插桩会临时修改主程序代码，测试完成后务必恢复
- 调试过程中保持GUI 100%兼容性
- 遵循理性化原则，避免过度工程化的解决方案
"""
    
    print(usage_guide)
    
    # 保存使用指南
    guide_file = project_root / "scripts" / "debug" / "DEBUG_USAGE_GUIDE.md"
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(usage_guide)
    
    print(f"📄 使用指南已保存: {guide_file}")
    
    print(f"\n🎯 GUI调试工具测试完成！")
    print(f"💡 现在可以使用这些工具来调试TLS-23掩码问题")


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("使用方法: python scripts/debug/test_gui_debug_tools.py <test_pcap_file>")
        sys.exit(1)
    
    test_file = sys.argv[1]
    if not Path(test_file).exists():
        print(f"❌ 测试文件不存在: {test_file}")
        sys.exit(1)
    
    test_debug_tools(test_file)


if __name__ == "__main__":
    main()
