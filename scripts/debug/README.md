# PktMask GUI TLS-23掩码调试工具集

本工具集提供了一套完整的调试工具，用于分析和解决PktMask GUI操作中TLS-23 ApplicationData掩码失效的问题。

## 🎯 调试策略

采用结构化调试方法，在GUI处理链条的关键环节添加详细日志输出，逐步追踪数据流：

1. **GUI触发的maskstage调用入口追踪**
2. **Marker模块的TLS消息识别和规则生成验证**
3. **Masker模块的规则应用和payload掩码处理验证**
4. **最终pcap文件写入过程验证**

## 🛠️ 工具组件

### 1. 结构化调试分析器 (`gui_tls23_masking_debug.py`)

**功能**: 完整的GUI处理链条调试分析

**使用方法**:
```bash
python scripts/debug/gui_tls23_masking_debug.py <test_pcap_file>
```

**输出**:
- 详细的调试报告 (`debug_report.json`)
- 完整的调试日志 (`debug.log`)
- 问题分析和修复建议

**调试步骤**:
1. GUI配置传递链条追踪
2. NewMaskPayloadStage实例化和初始化
3. Marker模块TLS消息识别验证
4. Masker模块规则应用验证
5. 完整GUI流程端到端测试
6. 结果对比分析

### 2. 代码插桩工具 (`gui_debug_instrumentation.py`)

**功能**: 在主程序代码中添加临时调试日志

**使用方法**:
```bash
# 添加调试插桩
python scripts/debug/gui_debug_instrumentation.py instrument

# 运行GUI测试（手动操作或自动化测试）

# 恢复原始代码
python scripts/debug/gui_debug_instrumentation.py restore

# 清理备份文件
python scripts/debug/gui_debug_instrumentation.py clean
```

**插桩位置**:
- `NewMaskPayloadStage` 双模块调用前后
- `TLSProtocolMarker` 分析入口
- `PayloadMasker` 掩码应用入口

### 3. 快速验证工具 (`quick_tls23_verification.py`)

**功能**: 快速验证TLS-23掩码效果

**使用方法**:
```bash
# 单文件验证
python scripts/debug/quick_tls23_verification.py <processed_pcap_file>

# 对比验证
python scripts/debug/quick_tls23_verification.py <original_file> <processed_file>
```

**验证内容**:
- TLS-23消息总数统计
- 掩码成功率计算
- 未掩码数据样本展示
- 原始文件与处理后文件对比

### 4. 工具测试脚本 (`test_gui_debug_tools.py`)

**功能**: 测试调试工具的功能完整性

**使用方法**:
```bash
python scripts/debug/test_gui_debug_tools.py <test_pcap_file>
```

## 📋 调试流程

### 阶段1: 初步诊断

1. 运行结构化调试分析器：
   ```bash
   python scripts/debug/gui_tls23_masking_debug.py test.pcap
   ```

2. 查看生成的调试报告，重点关注：
   - GUI配置是否正确传递
   - Marker模块是否正确识别TLS-23消息
   - Masker模块是否正确应用掩码规则

### 阶段2: 深度分析（如需要）

1. 添加代码插桩：
   ```bash
   python scripts/debug/gui_debug_instrumentation.py instrument
   ```

2. 运行GUI操作或自动化测试

3. 分析详细的运行时日志

4. 恢复原始代码：
   ```bash
   python scripts/debug/gui_debug_instrumentation.py restore
   ```

### 阶段3: 结果验证

1. 使用快速验证工具检查处理结果：
   ```bash
   python scripts/debug/quick_tls23_verification.py original.pcap processed.pcap
   ```

2. 确认TLS-23掩码效果是否符合预期

## 🔑 关键检查点

### GUI配置传递
- `mask_payload_cb.isChecked()` 状态
- `build_pipeline_config()` 生成的配置
- `application_data: False` 配置项

### Marker模块
- TLS消息类型识别准确性
- 保留规则生成逻辑
- TLS-23消息是否被正确排除

### Masker模块
- 保留规则应用逻辑
- TCP序列号匹配算法
- 掩码操作实现

### 最终输出
- TLS-23消息体是否被置零
- 其他TLS消息类型是否正确保留
- 文件完整性验证

## ⚠️ 注意事项

1. **代码安全**: 插桩工具会临时修改主程序代码，测试完成后务必恢复
2. **GUI兼容性**: 调试过程中保持100% GUI兼容性
3. **理性化原则**: 遵循理性化原则，避免过度工程化的解决方案
4. **独立验证**: 使用独立测试脚本进行验证分析，严格禁止在验证阶段修改主程序代码

## 📊 预期输出示例

### 成功案例
```
🔍 GUI TLS-23掩码调试摘要
============================================================
📁 测试文件: test.pcap
📊 总步骤数: 6
✅ 成功步骤: 6
❌ 失败步骤: 0
🎯 整体状态: 成功

📈 TLS-23掩码验证:
   - TLS-23消息总数: 15
   - 已掩码消息数: 15
   - 掩码成功率: 100.00%
```

### 问题案例
```
🚨 发现 2 个问题:
   1. TLS-23掩码效果: 掩码成功率仅为 60.00% (影响: 高)
   2. Marker模块TLS消息识别验证: 规则生成异常 (影响: 高)

💡 修复建议:
   1. 🎯 检查Marker模块的TLS消息识别逻辑，确保正确识别TLS-23消息
   2. 🔍 验证保留规则生成是否正确排除TLS-23消息体
   3. 🔑 重点检查TLS-23 ApplicationData的掩码处理逻辑
```

## 🚀 快速开始

1. 准备测试用的pcap文件（包含TLS-23消息）
2. 运行工具测试脚本验证环境：
   ```bash
   python scripts/debug/test_gui_debug_tools.py test.pcap
   ```
3. 运行结构化调试分析：
   ```bash
   python scripts/debug/gui_tls23_masking_debug.py test.pcap
   ```
4. 根据调试报告中的问题分析和修复建议进行代码修改
5. 使用快速验证工具确认修复效果

## 📞 支持

如果在使用调试工具过程中遇到问题，请检查：
1. Python环境和依赖包是否完整
2. 测试pcap文件是否包含TLS流量
3. PktMask项目结构是否完整
4. 是否有足够的文件系统权限
