# PktMask 架构重构行动计划

> **目标**: 15天内完成架构简化，消除技术债务  
> **策略**: 激进重构，完全淘汰遗留系统  
> **原则**: 简化优先，功能保持，性能提升  

## 🚀 立即行动项 (第1-3天)

### Day 1: GUI架构迁移准备

```bash
# 1. 创建重构分支
git checkout -b refactor/architecture-simplification
git push -u origin refactor/architecture-simplification

# 2. 备份当前实现
cp src/pktmask/gui/main_window.py src/pktmask/gui/main_window_legacy.py

# 3. 启用简化架构
mv src/pktmask/gui/simplified_main_window.py src/pktmask/gui/main_window.py
```

**验证步骤**:
- [ ] 应用正常启动
- [ ] GUI界面显示正确
- [ ] 基本功能可用

### Day 2: 删除旧管理器系统

```bash
# 完全移除管理器目录
rm -rf src/pktmask/gui/managers/

# 更新导入引用 (如果有)
grep -r "from.*managers" src/ --include="*.py"
# 手动修复发现的导入问题
```

**验证步骤**:
- [ ] 无编译错误
- [ ] 所有GUI功能正常
- [ ] 事件处理正确

### Day 3: 功能完整性验证

**测试清单**:
- [ ] 目录选择功能
- [ ] 处理选项配置
- [ ] 开始/停止处理
- [ ] 进度显示
- [ ] 统计报告
- [ ] 错误处理

## ⚡ 核心重构 (第4-10天)

### Day 4-5: 实现DeduplicationStage

**创建新文件**: `src/pktmask/core/pipeline/stages/dedup.py`

```python
from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats

class DeduplicationStage(StageBase):
    name: str = "DeduplicationStage"
    
    def __init__(self, config=None):
        super().__init__()
        self.config = config or {}
    
    def process_file(self, input_path, output_path):
        # 实现去重逻辑
        # 返回 StageStats 对象
        pass
```

### Day 6-7: 移除BaseProcessor系统

**删除文件**:
```bash
rm src/pktmask/core/processors/base_processor.py
rm src/pktmask/core/processors/ip_anonymizer.py
rm src/pktmask/core/processors/deduplicator.py
rm src/pktmask/core/processors/registry.py
```

**更新PipelineExecutor**:
```python
# 直接创建Stage实例，移除Registry依赖
def _create_stages(self, config):
    stages = []
    if config.get('enable_dedup'):
        from .stages.dedup import DeduplicationStage
        stages.append(DeduplicationStage())
    # ... 其他stages
    return stages
```

### Day 8-10: 修复TLS Maskstage

**创建格式标准化器**: `src/pktmask/core/pipeline/stages/mask_payload_v2/utils/format_normalizer.py`

**集成到PayloadMasker**:
```python
def apply_masking(self, input_path, output_path, keep_rules):
    with FileFormatNormalizer() as normalizer:
        normalized_input, is_temp = normalizer.normalize_to_pcap(input_path)
        return self._apply_masking_internal(normalized_input, output_path, keep_rules)
```

## 🔧 优化完善 (第11-15天)

### Day 11-12: 错误处理英文化

**批量替换中文文档字符串**:
```bash
# 查找所有中文文档字符串
grep -r "\"\"\".*[\u4e00-\u9fff]" src/ --include="*.py"

# 手动替换为英文版本
# 示例: "处理异常的主要入口点" → "Main entry point for exception handling"
```

### Day 13-14: 性能优化

**实现区间树查找**:
```python
class OptimizedRuleProcessor:
    def __init__(self, rules):
        self.sorted_rules = sorted(rules, key=lambda r: r.start_seq)
    
    def find_overlapping_rules(self, seq_start, seq_end):
        # 真正的O(log n)二分查找实现
        pass
```

### Day 15: 最终验证

**完整测试套件**:
- [ ] 功能回归测试
- [ ] 性能基准测试  
- [ ] TLS掩码验证
- [ ] 大文件处理测试

## 📊 成功指标

### 量化目标

| 指标 | 当前值 | 目标值 | 验证方法 |
|------|--------|--------|----------|
| 文件数量 | ~150 | ~100 | `find src/ -name "*.py" \| wc -l` |
| 组件数量 | 9 | 3 | 架构图验证 |
| TLS掩码成功率 | 36.36% | >95% | E2E测试 |
| 代码行数 | 当前 | -3000行 | `cloc src/` |

### 功能验证

**GUI功能保持100%**:
- 界面布局不变
- 所有按钮功能正常
- 处理流程完整
- 统计报告准确

**处理功能增强**:
- PCAP文件处理 ✅
- PCAPNG文件处理 ✅ (新增)
- 大文件处理优化 ✅
- 错误处理改善 ✅

## 🛡️ 风险控制

### 回滚机制

```bash
# 如果出现问题，快速回滚
git checkout main
git branch -D refactor/architecture-simplification

# 或恢复备份文件
mv src/pktmask/gui/main_window_legacy.py src/pktmask/gui/main_window.py
```

### 验证检查点

**每日检查**:
- 代码编译无错误
- 基本功能可用
- 性能无明显下降

**阶段检查**:
- Day 3: GUI架构迁移完成
- Day 7: 处理器统一完成  
- Day 10: TLS问题修复完成
- Day 15: 全面验证通过

## 📋 实施清单

### 准备阶段
- [ ] 创建重构分支
- [ ] 备份关键文件
- [ ] 设置测试环境

### 执行阶段
- [ ] GUI架构简化 (Day 1-3)
- [ ] 处理器统一 (Day 4-7)
- [ ] TLS问题修复 (Day 8-10)
- [ ] 错误处理优化 (Day 11-12)
- [ ] 性能优化 (Day 13-14)
- [ ] 最终验证 (Day 15)

### 完成阶段
- [ ] 合并到主分支
- [ ] 更新文档
- [ ] 部署验证
- [ ] 清理临时文件

## 🎯 预期收益

**立即收益**:
- TLS掩码功能修复
- 文件格式兼容性解决
- 错误处理标准化

**中期收益**:
- 开发效率提升50%
- 维护成本降低60%
- 代码质量显著改善

**长期收益**:
- 架构健康度提升
- 技术债务清零
- 扩展能力增强

---

**开始重构**: 立即执行Day 1任务，开启PktMask架构现代化之旅！
