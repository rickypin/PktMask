# PktMask项目目录结构迁移计划

## 📊 项目概况

- **项目名称**: PktMask目录结构重组
- **文档版本**: v3.0 (基于预审查优化版)
- **创建日期**: 2025年1月
- **执行时间**: 预计3-4小时 (基于实际情况优化)
- **风险等级**: 低-中等 (经预审查验证)

## 🔍 **Phase 0: 预审查结果确认**

### ✅ **实际现状验证** (2025年1月执行)
- **根目录文件总数**: 21个 (实际统计)
- **需要迁移文件**: 13个
- **迁移后保留**: 8个 (符合目标 ≤8个)
- **功能状态**: pktmask模块导入正常，配置文件正常
- **Python使用**: run_tests.py正确使用sys.executable

### 📋 **精确的文件分类**
**配置文件 (6个)**:
- comprehensive_mask_recipe_sample.json
- custom_recipe.json
- demo_recipe.json
- mask_config.yaml
- simple_mask_recipe_sample.json
- tls_mask_recipe_sample.json

**脚本文件 (8个)**:
- build_app.sh
- hybrid_architecture_design.py
- manual_tcp_masker_test.py
- pre_migration_check.py (新创建)
- run_gui.py (保留)
- run_tcp_masker_test.py
- run_tests.py (保留)
- sequence_unification_strategy.py

**文档文件 (3个)**:
- CHANGELOG.md (保留)
- README.md (保留)
- tcp_payload_masker_phase1_4_validation_report.md

**保留文件 (8个)**:
- CHANGELOG.md, LICENSE, PktMask.spec, README.md
- pyproject.toml, pytest.ini, run_gui.py, run_tests.py

## 🎯 迁移目标与收益

### 主要目标
1. **根目录清理** - 从21个文件减少到8个文件 (62%减少)
2. **配置统一管理** - 将6个配置文件整合到config/目录
3. **文档结构优化** - 建立清晰的文档分类体系
4. **脚本资源整合** - 统一管理测试脚本和验证工具
5. **输出管理标准化** - 建立标准的输出目录结构

### 预期收益
- 📉 根目录文件减少 **62%** (从21个到8个) ✅**已验证**
- 🎯 配置统一管理 (从4个位置到1个)
- 📚 建立3级文档分类体系
- 🔧 提升项目可维护性和专业性
- 👥 降低新手学习门槛

### 成功标准
- ✅ 根目录文件数量 ≤ 8个 ✅**预审查确认可达成**
- ✅ 所有配置文件位于 `config/` 目录下
- ✅ 所有脚本文件位于 `scripts/` 子目录下
- ✅ 项目功能保持100%正常 ✅**预审查确认当前功能正常**
- ✅ 所有路径引用正确更新
- ✅ 测试套件100%通过

## 🗺️ 目标目录结构

```
PktMask/
├── README.md                    # 项目说明 ✅保留
├── CHANGELOG.md                 # 版本历史 ✅保留
├── LICENSE                      # 许可证 ✅保留
├── pyproject.toml              # Python项目配置 ✅保留
├── pytest.ini                 # 测试配置 ✅保留
├── PktMask.spec               # 打包配置 ✅保留
├── run_gui.py                 # GUI启动脚本 ✅保留
├── run_tests.py               # 测试运行脚本 ✅保留
│
├── src/pktmask/               # 源代码 (保持不变)
├── tests/                     # 测试目录 (保持不变)  
├── assets/                    # 静态资源 (保持不变)
│
├── config/                    # 🆕 统一配置管理
│   ├── default/              # 默认配置
│   │   └── mask_config.yaml ⬅️ 从根目录迁移
│   ├── samples/              # 示例配置
│   │   ├── simple_mask_recipe.json ⬅️ 重命名
│   │   ├── comprehensive_mask_recipe.json ⬅️ 重命名
│   │   ├── demo_recipe.json ⬅️ 从根目录迁移
│   │   ├── custom_recipe.json ⬅️ 从根目录迁移
│   │   └── tls_mask_recipe.json ⬅️ 重命名
│   ├── production/           # 生产配置
│   │   └── dual_strategy_deployment.yaml
│   └── test/                 # 测试配置
│       └── validation_test_config.json
│
├── scripts/                   # 🆕 工具脚本统一管理
│   ├── build/                # 构建脚本
│   │   └── build_app.sh ⬅️ 从根目录迁移
│   ├── test/                 # 测试脚本
│   │   ├── manual_tcp_masker_test.py ⬅️ 从根目录迁移
│   │   ├── run_tcp_masker_test.py ⬅️ 从根目录迁移
│   │   ├── validate_tcp_masking.sh
│   │   └── validate_tcp_masking_simple.sh
│   ├── validation/           # 验证脚本
│   │   ├── analyze_tls_sample.py
│   │   ├── validate_tls_sample.py
│   │   └── tls_sample_analysis.json
│   ├── migration/            # 迁移脚本
│   │   ├── migrate_to_tcp_payload_masker.py
│   │   ├── sequence_unification_strategy.py ⬅️ 从根目录迁移
│   │   ├── hybrid_architecture_design.py ⬅️ 从根目录迁移
│   │   ├── update_paths.py
│   │   ├── simple_validator.py
│   │   ├── validate_migration.py
│   │   └── pre_migration_audit.py ⬅️ 新增
│   └── hooks/                # Git hooks
│       ├── hook-pydantic.py
│       └── hook-yaml.py
│
├── docs/                      # 🆕 文档结构重组
│   ├── README.md             # 文档索引
│   ├── api/                  # API文档
│   ├── development/          # 开发文档
│   │   ├── implementation/
│   │   ├── architecture/
│   │   └── migration/
│   ├── reports/              # 技术报告
│   │   └── tcp_payload_masker_phase1_4_validation_report.md ⬅️ 从根目录迁移
│   └── user/                 # 用户文档
│
├── examples/                  # 示例代码 (清理嵌套)
│   ├── basic_usage.py
│   ├── advanced_usage.py
│   ├── performance_testing.py
│   └── output/              # 示例输出
│
└── output/                    # 🆕 统一输出目录
    ├── processed/            # 处理后的文件
    ├── reports/             # 生成的报告
    └── temp/               # 临时文件
```

## 📋 **修正的执行计划 (6个阶段)**

### Phase 0: 预审查与问题修复 (新增) (45分钟)

#### 0.1 环境准备和状态确认
```bash
# 验证当前工作目录清洁
git status
git stash  # 如果有未提交的更改

# 创建备份分支
git checkout -b backup-before-migration
git push origin backup-before-migration

# 创建工作分支
git checkout -b directory-structure-migration-v3
```

#### 0.2 修复识别的问题
```bash
# 清理预审查临时文件
rm -f pre_migration_check.py pre_migration_audit.json

# 验证功能正常
python3 -c "import sys; sys.path.insert(0, 'src'); import pktmask; print('✅ 模块导入正常')"

# 测试配置加载
python3 -c "import yaml; yaml.safe_load(open('mask_config.yaml')); print('✅ 配置正常')"
```

**验证点**: 环境准备完成，当前功能确认正常

#### ✅ Phase 0 实施结果 (2025年6月26日)
- [x] Git 工作区干净 (`git status`)。
- [x] 已创建备份分支 `backup-before-migration`。
- [x] 已创建工作分支 `directory-structure-migration-v3`。
- [x] 已删除 `pre_migration_audit.json`（未发现 `pre_migration_check.py`）。
- [x] `pktmask` 模块成功导入。
- [x] `mask_config.yaml` 配置成功加载。
- [x] `tests/unit/test_config.py` 全部 19 项测试 **通过**。

### Phase 1: 准备与备份 (35分钟) ⬆️*增加5分钟验证时间*

#### 1.1 功能验证 (增强)
```bash
# 确保当前状态功能正常
python3 -m pytest tests/unit/test_config.py -v
python3 -c "import sys; sys.path.insert(0, 'src'); import pktmask"
timeout 10s python3 run_gui.py &  # 测试GUI启动
sleep 5 && pkill -f run_gui.py
```

#### 1.2 创建新目录结构
```bash
# 创建所有必需的目录
mkdir -p config/{default,samples,production,test}
mkdir -p scripts/{build,test,validation,migration}
mkdir -p docs/{api,development/{implementation,architecture,migration},reports,user}
mkdir -p output/{processed,reports,temp}
```

**验证点**: 目录结构创建完成，当前功能正常

#### ✅ Phase 1 实施结果 (2025年6月26日)
- [x] 单元测试再次通过（19/19）。
- [x] `pktmask` 模块导入正常。
- [x] GUI 启动并在 5 秒内成功初始化后被安全终止。
- [x] 已创建/确认以下目录存在：
  - `config/{default,samples,production,test}`
  - `scripts/{build,test,validation,migration}`
  - `docs/api`, `docs/development/{implementation,architecture,migration}`, `docs/reports`, `docs/user`
  - `output/{processed,reports,temp}`
- [x] 当前功能验证全部通过。

### Phase 2: 配置文件迁移 (40分钟) ⬆️*增加10分钟*

#### 2.1 移动配置文件 (精确映射)
```bash
# 移动主配置文件
git mv mask_config.yaml config/default/

# 移动并重命名示例配置 (基于预审查结果)
git mv simple_mask_recipe_sample.json config/samples/simple_mask_recipe.json
git mv comprehensive_mask_recipe_sample.json config/samples/comprehensive_mask_recipe.json
git mv demo_recipe.json config/samples/
git mv custom_recipe.json config/samples/
git mv tls_mask_recipe_sample.json config/samples/tls_mask_recipe.json

# 移动生产和测试配置
if [ -d "conf/production" ]; then
    git mv conf/production/* config/production/
    rmdir conf/production conf
fi

if [ -d "test_configs" ]; then
    git mv test_configs/* config/test/
    rmdir test_configs
fi
```

#### 2.2 更新配置路径引用 (增强验证)
```bash
# 使用自动化工具更新路径
python3 scripts/migration/update_paths.py --phase 2 --dry-run  # 预览
python3 scripts/migration/update_paths.py --phase 2           # 实际执行

# 验证配置加载
python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from pktmask.config import defaults
    print('✅ 配置模块导入正常')
except Exception as e:
    print(f'❌ 配置导入失败: {e}')
    sys.exit(1)
"
```

**验证点**: 配置文件迁移完成，路径引用正确更新，配置加载测试通过

#### ✅ Phase 2 实施结果 (2025年6月26日)
- [x] 配置文件 6 个及生产/测试配置已全部移至 `config/`，并按计划重命名。
- [x] `conf/`、`test_configs/` 目录清理完毕（仅剩未跟踪的系统文件将于最终清理）。
- [x] 运行 `update_paths.py --phase 2` 成功更新 2 处核心路径引用并生成报告 `output/reports/path_update_report.md`。
- [x] 单元测试 `test_config.py` 仍全部通过，配置加载正常。
- [x] 手动 YAML 读取验证通过 (`config/default/mask_config.yaml`)。

### Phase 3: 脚本文件重组 (40分钟) ⬆️*增加10分钟*

#### 3.1 移动脚本文件 (精确映射)
```bash
# 移动根目录脚本到对应位置 (基于预审查结果)
git mv manual_tcp_masker_test.py scripts/test/
git mv run_tcp_masker_test.py scripts/test/
git mv build_app.sh scripts/build/
git mv sequence_unification_strategy.py scripts/migration/
git mv hybrid_architecture_design.py scripts/migration/

# 重组现有 scripts/ 目录
git mv scripts/analyze_tls_sample.py scripts/validation/
git mv scripts/validate_tls_sample.py scripts/validation/
git mv scripts/tls_sample_analysis.json scripts/validation/
git mv scripts/validate_tcp_masking.sh scripts/test/
git mv scripts/validate_tcp_masking_simple.sh scripts/test/
git mv scripts/migrate_to_tcp_payload_masker.py scripts/migration/

# 移动 hooks 到 scripts/hooks
if [ -d "hooks" ]; then
    git mv hooks scripts/
fi

# 移动预审查工具到正确位置
git mv scripts/migration/pre_migration_audit.py scripts/migration/
```

#### 3.2 更新脚本路径引用和权限验证
```bash
python3 scripts/migration/update_paths.py --phase 3 --dry-run  # 预览
python3 scripts/migration/update_paths.py --phase 3           # 实际执行

# 验证脚本权限
chmod +x scripts/build/build_app.sh
chmod +x scripts/test/validate_tcp_masking*.sh
```

**验证点**: 脚本文件重组完成，引用路径正确更新，权限保持

### Phase 4: 文档重组 (25分钟) ⬆️*增加5分钟*

#### 4.1 移动文档文件 (精确映射)
```bash
# 移动技术报告 (基于预审查结果)
git mv tcp_payload_masker_phase1_4_validation_report.md docs/reports/

# 创建文档索引
cat > docs/README.md << 'EOF'
# PktMask 文档目录

## 📚 文档分类

- `api/` - API参考文档
- `development/` - 开发相关文档
  - `implementation/` - 实现详情
  - `architecture/` - 架构设计
  - `migration/` - 迁移相关
- `reports/` - 技术报告和验证结果
- `user/` - 用户使用文档

## 🔗 快速链接

- [项目主页](../README.md)
- [变更日志](../CHANGELOG.md)
- [技术报告](reports/)
EOF
```

#### 4.2 更新文档引用
```bash
python3 scripts/migration/update_paths.py --phase 4 --dry-run  # 预览
python3 scripts/migration/update_paths.py --phase 4           # 实际执行
```

**验证点**: 文档重组完成，索引文件创建

### Phase 5: 输出整合与清理 (35分钟) ⬆️*增加15分钟*

#### 5.1 修复嵌套问题和整合输出
```bash
# 修复 examples/examples 嵌套问题
if [ -d "examples/examples" ]; then
    mv examples/examples/* examples/ 2>/dev/null || true
    if [ -d "examples/examples/output" ]; then
        mv examples/examples/output/* examples/output/ 2>/dev/null || true
    fi
    rmdir examples/examples 2>/dev/null || true
fi

# 整合现有输出到标准目录
if [ -d "reports" ] && [ "$(ls -A reports 2>/dev/null)" ]; then
    mv reports/* output/reports/ 2>/dev/null || true
    rmdir reports 2>/dev/null || true
fi

if [ -d "output" ] && [ "$(ls -A output 2>/dev/null)" ]; then
    # 将现有 output/ 内容移到 output/processed/
    find output -maxdepth 1 -type f -exec mv {} output/processed/ \; 2>/dev/null || true
fi
```

#### 5.2 最终路径更新和完整验证
```bash
python3 scripts/migration/update_paths.py --phase 5 --dry-run  # 预览
python3 scripts/migration/update_paths.py --phase 5           # 实际执行

# 完整功能验证
python3 -m pytest tests/unit/test_config.py -v
python3 -c "import sys; sys.path.insert(0, 'src'); import pktmask"
timeout 10s python3 run_gui.py &
sleep 5 && pkill -f run_gui.py
```

**验证点**: 输出目录整合完成，嵌套问题解决，功能验证通过

## 🛡️ **增强的安全措施与验证**

### 每阶段验证步骤 (强化)
每个Phase完成后**必须**执行以下验证:

```bash
# 1. 基础功能验证 (增强)
python3 -m pytest tests/unit/test_config.py -v
python3 -c "import sys; sys.path.insert(0, 'src'); import pktmask; print('✅ 导入正常')"

# 2. GUI启动验证 (改进)
timeout 15s python3 run_gui.py &
PID=$!
sleep 10
if kill -0 $PID 2>/dev/null; then
    echo "✅ GUI启动正常"
    kill $PID
else
    echo "❌ GUI启动失败"
fi

# 3. 配置加载验证 (新增)
python3 -c "
import yaml
try:
    with open('config/default/mask_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print('✅ 新配置路径正常')
except Exception as e:
    print(f'❌ 配置路径错误: {e}')
    exit(1)
"

# 4. Git状态检查
git status --porcelain
```

### 自动化验证工具 (增强)
```bash
# 使用增强验证脚本检查迁移完整性
python3 scripts/migration/validate_migration.py --comprehensive

# 如果发现问题，可以自动修复
python3 scripts/migration/validate_migration.py --fix-issues
```

## 🔧 **修正的时间估算**

| 阶段 | 原计划 | 修正后 | 说明 |
|------|--------|--------|------|
| Phase 0 | 无 | 45分钟 | 新增预审查和问题修复 |
| Phase 1 | 30分钟 | 35分钟 | 增加功能验证时间 |
| Phase 2 | 30分钟 | 40分钟 | 增加配置验证时间 |
| Phase 3 | 30分钟 | 40分钟 | 增加脚本权限检查 |
| Phase 4 | 20分钟 | 25分钟 | 增加文档验证 |
| Phase 5 | 20分钟 | 35分钟 | 增强最终验证 |
| **总计** | **2.5小时** | **3.5小时** | **增加1小时缓冲，更加安全** |

## ✅ **修正的最终验证清单**

### 功能验证 (增强)
- [ ] **测试套件**: `python3 -m pytest tests/unit/test_config.py -v` 100%通过
- [ ] **模块导入**: `python3 -c "import sys; sys.path.insert(0, 'src'); import pktmask"` 正常
- [ ] **GUI启动**: `python3 run_gui.py` 正常启动 (15秒测试)
- [ ] **配置加载**: 新路径`config/default/mask_config.yaml`正确加载
- [ ] **示例执行**: `cd examples && python3 basic_usage.py` 正常执行

### 结构验证 (精确)
- [ ] **根目录清洁**: 恰好8个文件 (README, CHANGELOG, LICENSE, pyproject.toml, pytest.ini, PktMask.spec, run_gui.py, run_tests.py)
- [ ] **配置统一**: 6个配置文件100%在 `config/` 下
- [ ] **脚本整理**: 8个脚本文件100%在 `scripts/` 子目录下
- [ ] **文档组织**: 3个文档文件正确分类，索引文件创建
- [ ] **输出统一**: 统一使用 `output/` 目录，嵌套问题解决

### 技术验证 (强化)
- [ ] **导入路径**: 无损坏的Python导入，配置模块正常
- [ ] **Git历史**: Git历史完整，使用 `git mv` 保持文件历史  
- [ ] **依赖关系**: 所有依赖关系正确，路径引用更新
- [ ] **文件权限**: shell脚本保持可执行权限

## 📈 **预期成果总结 (基于实际数据)**

### 定量改进 (已验证)
- ✅ **根目录文件**: 62% 减少 (21个 → 8个) **✅已通过预审查确认**
- ✅ **配置集中度**: 100% 统一 (4个位置 → 1个位置)  
- ✅ **脚本组织**: 100% 分类 (3个位置 → 结构化子目录)
- ✅ **文档结构**: 建立3级分类体系

### 定性提升 (预期)
- 🎯 **可维护性**: 大幅提升，符合Python项目最佳实践
- 👥 **新手友好**: 降低学习门槛，清晰的项目结构
- 🏗️ **扩展性**: 为未来功能扩展提供良好基础  
- 🎖️ **专业性**: 提升项目整体专业形象

---

**⚠️ 重要提醒**: 严格按Phase顺序执行，每个阶段完成后必须验证，确保无误后再进行下一阶段！

**🔥 关键改进**: 基于预审查结果，文件数量、分类、迁移映射均已精确确认，时间估算更加合理，验证步骤大幅增强。 