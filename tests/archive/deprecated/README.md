# 已废弃测试脚本归档

> **清理日期**: 2025-07-23  
> **清理原因**: 架构重构后模块失效  
> **清理类别**: P0 (完全失效) + P1 (部分失效)

## 📋 清理清单

### P0 - 完全失效的测试脚本

#### 1. 适配器层相关测试
- **test_adapter_exceptions.py** - 测试 `pktmask.adapters.adapter_exceptions`
- **test_encapsulation_basic.py** - 测试 `src.pktmask.core.encapsulation` 模块
- **失效原因**: 项目已完成架构重构，适配器层已被移除，相关模块不存在

#### 2. 旧版处理器测试
- **test_enhanced_ip_anonymization.py** - 测试增强IP匿名化处理器
- **test_enhanced_payload_masking.py** - 测试增强载荷掩码处理器
- **失效原因**: 处理器架构已统一为 StageBase 架构，旧版处理器已废弃

#### 3. 步骤模块测试
- **test_steps_basic.py** - 测试 Steps 模块
- **失效原因**: 代码中显示 `IntelligentTrimmingStage has been refactored`，相关步骤已重构

#### 4. 性能集中测试
- **test_performance_centralized.py** - 集中性能测试
- **失效原因**: 导入的模块如 `EnhancedTrimmer`, `_process_pcap_data_enhanced` 等已不存在

### P1 - 部分失效的测试脚本

#### 5. 主模块测试
- **test_main_module.py** - 测试主模块结构
- **问题**: 期望的导入路径 `from .gui.main_window import main` 与实际不符
- **当前实际**: 使用 CLI 命令注册方式，无 `main()` 函数

#### 6. 策略综合测试
- **test_strategy_comprehensive.py** - 策略模块测试
- **问题**: 导入路径使用 `src.pktmask.core.strategy`，应为 `pktmask.core.strategy`

#### 7. 工具测试
- **test_tls_flow_analyzer_protocol_cleanup.py** - TLS流量分析器测试
- **问题**: 导入路径使用 `src.pktmask.tools.tls_flow_analyzer`，应为 `pktmask.tools.tls_flow_analyzer`

### P2 - 可能过时的测试脚本

#### 8. 多TLS记录掩码测试
- **test_multi_tls_record_masking.py** - 多TLS记录掩码测试
- **问题**: 导入的模块如 `TSharkTLSAnalyzer`, `TLSMaskRuleGenerator` 等已不存在
- **失效原因**: 基于旧的处理器架构，已被新的双模块架构替代

### P3 - 需要更新的测试脚本

#### 9. TLS模型测试
- **test_tls_models.py** - TLS协议模型测试
- **问题**: 导入的模块如 `TLSProcessingStrategy`, `MaskAction` 等已不存在
- **失效原因**: 基于旧的trim模块架构，相关模型已不存在

#### 10. TLS规则冲突解决测试
- **test_tls_rule_conflict_resolution.py** - TLS掩码规则冲突解决测试
- **问题**: 导入的模块如 `ScapyMaskApplier` 已不存在
- **失效原因**: 基于旧的处理器架构，已被新的PayloadMasker替代

#### 11. TLS策略测试
- **test_tls_strategy.py** - TLS协议裁切策略测试
- **问题**: 导入的模块如 `TLSTrimStrategy` 等已不存在
- **失效原因**: 基于旧的trim策略架构，相关策略已不存在

## 📊 清理统计

| 类别 | 文件数量 | 清理状态 |
|------|----------|----------|
| P0 - 完全失效 | 4个 | ✅ 已清理 |
| P1 - 部分失效 | 3个 | ✅ 已清理 |
| P2 - 可能过时 | 1个 | ✅ 已清理 |
| P3 - 需要更新 | 3个 | ✅ 已清理 |
| **总计** | **11个** | **✅ 已完成** |

## 🔄 恢复说明

如果需要恢复任何测试脚本，可以从此归档目录复制回原位置：

```bash
# 恢复单个文件示例
cp tests/archive/deprecated/test_adapter_exceptions.py tests/unit/

# 恢复所有文件示例
cp tests/archive/deprecated/*.py tests/unit/
```

## 📁 归档文件列表

```
tests/archive/deprecated/
├── README.md                                    # 归档说明文档
├── test_adapter_exceptions.py                   # 适配器异常测试
├── test_encapsulation_basic.py                  # 封装基础测试
├── test_enhanced_ip_anonymization.py            # 增强IP匿名化测试
├── test_enhanced_payload_masking.py             # 增强载荷掩码测试
├── test_main_module.py                          # 主模块测试
├── test_multi_tls_record_masking.py             # 多TLS记录掩码测试
├── test_performance_centralized.py              # 性能集中测试
├── test_steps_basic.py                          # 步骤基础测试
├── test_strategy_comprehensive.py               # 策略综合测试
├── test_tls_flow_analyzer_protocol_cleanup.py   # TLS分析器协议清理测试
├── test_tls_models.py                           # TLS协议模型测试
├── test_tls_rule_conflict_resolution.py         # TLS规则冲突解决测试
├── test_tls_strategy.py                         # TLS协议裁切策略测试
├── test_deduplication_stage.py                  # 旧版去重阶段测试
├── test_ip_anonymization.py                     # 旧版IP匿名化测试
├── test_infrastructure_basic.py                 # 基础设施测试（适配器依赖）
├── test_compatibility.py                        # V2兼容性测试
└── test_stage_integration.py                    # 阶段集成测试（旧API）
```

## ⚠️ 注意事项

1. **这些测试脚本已确认失效**，不建议直接恢复使用
2. **如需类似功能的测试**，建议基于当前架构重新编写
3. **归档文件仅供参考**，了解历史测试覆盖范围

## 📝 后续建议

1. **补充测试覆盖**: 为当前架构编写对应的测试脚本
2. **定期审查**: 建立定期测试脚本有效性审查机制
3. **文档更新**: 更新测试文档，反映当前的测试架构
