
🔍 PktMask GUI TLS-23掩码调试指南
============================================================

📋 调试流程：

1️⃣ 运行结构化调试分析：
   python scripts/debug/gui_tls23_masking_debug.py tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap
   
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
