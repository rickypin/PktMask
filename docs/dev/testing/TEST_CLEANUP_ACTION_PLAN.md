# PktMask 测试脚本清理行动计划

> **制定日期**: 2025-07-25  
> **执行期限**: 1周内完成  
> **目标**: 将测试成功率从53%提升至95%以上

## 🎯 清理目标

### 主要目标
1. **修复1个完全失效的测试文件**
2. **修复6个部分失效的测试文件**
3. **建立测试质量保证机制**
4. **清理临时调试代码和过时引用**

### 成功标准
- [ ] 测试成功率达到95%以上
- [ ] 所有导入路径正确且一致
- [ ] 无过时引用和断言错误
- [ ] 建立自动化测试质量检查

## 📋 具体行动清单

### 🔴 第1天: 高优先级修复 (2小时)

#### 任务1.1: 修复导入路径错误 (30分钟)
**文件**: `tests/unit/test_temporary_file_management.py`

**操作步骤**:
1. 打开文件 `tests/unit/test_temporary_file_management.py`
2. 找到第20行的错误导入:
   ```python
   from pktmask.core.pipeline.stages.masking_stage.stage import MaskingStage
   ```
3. 替换为正确导入:
   ```python
   from pktmask.core.pipeline.stages.masking_stage.stage import MaskingStage
   ```
4. 查找并替换所有 `MaskingStage` 为 `MaskingStage`
5. 运行测试验证: `python -m pytest tests/unit/test_temporary_file_management.py -v`

**验证标准**: 测试文件能够成功加载，无导入错误

#### 任务1.2: 修复测试断言错误 (60分钟)
**文件**: `tests/unit/test_masking_stage_stage.py`

**操作步骤**:
1. **修复显示名称断言** (15分钟):
   - 找到 `test_display_name_and_description` 方法
   - 将断言从 `"Mask Payloads (v2)"` 改为 `"Mask Payloads"`

2. **移除不存在方法引用** (30分钟):
   - 找到 `test_process_file_integration` 和 `test_process_file_without_initialization`
   - 移除或替换 `validate_inputs` 方法引用
   - 使用实际存在的方法进行测试

3. **修复配置测试** (15分钟):
   - 找到 `test_default_config_values` 方法
   - 更新配置期望值，适配新的配置结构

**验证标准**: 所有9个测试都能通过

#### 任务1.3: 验证修复效果 (30分钟)
**操作步骤**:
1. 运行修复的测试文件:
   ```bash
   python -m pytest tests/unit/test_temporary_file_management.py -v
   python -m pytest tests/unit/test_masking_stage_stage.py -v
   ```
2. 检查测试通过率
3. 记录修复结果

**验证标准**: 两个文件的测试都能成功运行

### 🟡 第2-3天: 中优先级修复 (4小时)

#### 任务2.1: 验证可疑测试文件 (2小时)
**文件列表**:
- `test_masking_stage_masker.py`
- `test_masking_stage_tls_marker.py`
- `test_tls_flow_analyzer.py`
- `test_unified_services.py`

**操作步骤** (每个文件30分钟):
1. 运行测试: `python -m pytest tests/unit/[文件名] -v --tb=short`
2. 识别失败原因:
   - 配置问题
   - 依赖缺失
   - 测试数据缺失
   - 外部工具依赖
3. 记录问题和修复方案
4. 实施修复
5. 验证修复效果

#### 任务2.2: 修复运行时问题 (2小时)
根据任务2.1的发现，针对性修复:

**常见问题和解决方案**:
1. **配置问题**: 添加缺失的配置文件或Mock配置
2. **依赖缺失**: 安装缺失的Python包或Mock依赖
3. **测试数据缺失**: 创建Mock测试数据或添加真实测试文件
4. **外部工具依赖**: Mock外部工具调用（如tshark）

### 🟢 第4-5天: 质量保证和自动化 (4小时)

#### 任务3.1: 建立测试CI检查 (2小时)
**操作步骤**:
1. 创建测试导入检查脚本
2. 创建测试质量验证脚本
3. 集成到CI/CD流程
4. 测试自动化检查

#### 任务3.2: 清理临时调试代码 (1小时)
**操作步骤**:
1. 搜索临时调试代码模式:
   ```bash
   grep -r "print(" tests/
   grep -r "TODO" tests/
   grep -r "FIXME" tests/
   grep -r "DEBUG" tests/
   ```
2. 清理或正式化临时代码
3. 更新注释和文档

#### 任务3.3: 文档更新 (1小时)
**操作步骤**:
1. 更新测试文档
2. 创建测试维护指南
3. 更新项目README中的测试部分

## 🔧 修复脚本和工具

### 自动化导入路径修复脚本
```bash
#!/bin/bash
# scripts/fix_test_imports.sh

echo "🔧 修复测试文件导入路径..."

# 修复masking_stage导入
find tests/ -name "*.py" -exec sed -i '' \
  's/pktmask\.core\.pipeline\.stages\.masking_stage\.stage/pktmask.core.pipeline.stages.masking_stage.stage/g' {} \;

# 修复类名引用
find tests/ -name "*.py" -exec sed -i '' \
  's/MaskingStage/MaskingStage/g' {} \;

echo "✅ 导入路径修复完成"
```

### 测试验证脚本
```bash
#!/bin/bash
# scripts/validate_tests.sh

echo "🔍 验证测试文件状态..."

# 检查导入错误
python -c "
import sys
from pathlib import Path
import subprocess

test_files = list(Path('tests/unit').glob('*.py'))
failed_files = []

for test_file in test_files:
    try:
        result = subprocess.run([
            'python', '-m', 'pytest', str(test_file), '--collect-only', '-q'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f'✅ {test_file.name}: 收集成功')
        else:
            print(f'❌ {test_file.name}: 收集失败')
            failed_files.append(test_file.name)
    except Exception as e:
        print(f'❌ {test_file.name}: {e}')
        failed_files.append(test_file.name)

print(f'\n📊 总结: {len(test_files) - len(failed_files)}/{len(test_files)} 文件正常')
if failed_files:
    print(f'❌ 失败文件: {failed_files}')
    sys.exit(1)
"
```

### 临时调试代码清理脚本
```bash
#!/bin/bash
# scripts/cleanup_debug_code.sh

echo "🧹 清理临时调试代码..."

# 查找可疑的调试代码
echo "🔍 查找临时调试代码:"
grep -rn "print(" tests/ --include="*.py" | head -10
grep -rn "TODO" tests/ --include="*.py" | head -10
grep -rn "FIXME" tests/ --include="*.py" | head -10

echo "📝 请手动审查上述代码并决定是否清理"
```

## 📊 进度跟踪

### 每日检查清单

#### 第1天完成标准
- [ ] `test_temporary_file_management.py` 导入错误修复
- [ ] `test_masking_stage_stage.py` 断言错误修复
- [ ] 两个文件测试通过率达到100%

#### 第2-3天完成标准
- [ ] 4个可疑测试文件状态确认
- [ ] 识别的问题全部修复
- [ ] 整体测试通过率达到90%以上

#### 第4-5天完成标准
- [ ] CI/CD测试检查建立
- [ ] 临时调试代码清理完成
- [ ] 测试文档更新完成
- [ ] 整体测试通过率达到95%以上

### 风险缓解

#### 潜在风险
1. **修复引入新问题**: 修复过程中可能破坏现有功能
2. **外部依赖问题**: 某些测试可能依赖外部工具或数据
3. **时间超期**: 复杂问题可能需要更多时间

#### 缓解措施
1. **渐进式修复**: 每次只修复一个文件，立即验证
2. **备份机制**: 修复前备份原始文件
3. **Mock策略**: 对外部依赖使用Mock，提高测试稳定性

## ✅ 完成验证

### 最终验证清单
- [ ] 所有测试文件都能成功加载
- [ ] 测试通过率达到95%以上
- [ ] 无导入路径错误
- [ ] 无过时引用和断言错误
- [ ] 建立了自动化质量检查
- [ ] 文档已更新

### 成功标准
完成后应该达到：
- **测试成功率**: 95%以上
- **代码质量**: 无明显技术债务
- **维护性**: 建立了持续质量保证机制

---

**制定时间**: 2025-07-25  
**预计完成**: 2025-08-01  
**负责人**: 开发团队  
**审查人**: 项目负责人
