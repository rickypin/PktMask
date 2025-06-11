# PktMask 真实样本数据测试方案

## 📋 **方案概述**

这是一个完整的真实样本数据验证测试系统，覆盖 `tests/data/samples/` 目录下的所有16个子目录，验证PktMask对各种网络协议封装的处理能力。

## 🎯 **测试目标**

### 主要目标
- **100%目录覆盖**: 验证所有16个samples子目录中的文件
- **多协议支持**: 测试Plain IP、VLAN、MPLS、GRE、VXLAN等各种封装
- **功能完整性**: 验证封装检测、协议解析、IP提取、载荷处理全流程
- **性能基准**: 确保处理速度和资源使用在可接受范围内

### 验证范围
- ✅ **Plain IP** - 基础TCP/IP流量
- ✅ **Single VLAN** - 802.1Q单层VLAN
- ✅ **Double VLAN** - 802.1ad QinQ双层VLAN
- ✅ **MPLS** - 多协议标签交换
- ✅ **GRE** - 通用路由封装隧道
- ✅ **VXLAN** - 虚拟可扩展局域网
- ✅ **复合封装** - 多种协议组合
- ✅ **大规模数据** - 大IP地址集和多文件处理

## 🏗️ **架构设计**

### 核心组件

```
tests/integration/test_real_data_validation.py
├── RealDataValidator           # 真实数据验证器
├── SampleFileInfo             # 样本文件信息数据类
├── TestResult                 # 测试结果数据类
└── TestRealDataValidation     # 主测试类
```

### 测试分层

1. **目录覆盖测试** - 确保所有目录都有测试覆盖
2. **分类验证测试** - 按协议类别进行参数化测试
3. **综合验证测试** - 端到端完整验证流程

## 📁 **支持的样本类别**

| 目录名称 | 测试类别 | 预期封装 | 描述 |
|---------|----------|----------|------|
| `TLS/` | plain_ip | plain | 基础TCP/IP + TLS流量 |
| `TLS70/` | plain_ip_tls70 | plain | TLS 7.0版本流量 |
| `singlevlan/` | single_vlan | vlan | 单层VLAN封装(802.1Q) |
| `doublevlan/` | double_vlan | double_vlan | 双层VLAN封装(802.1ad QinQ) |
| `doublevlan_tls/` | double_vlan_tls | double_vlan | 双层VLAN + TLS组合 |
| `mpls/` | mpls | mpls | MPLS标签交换 |
| `gre/` | gre_tunnel | gre | GRE隧道封装 |
| `vxlan/` | vxlan | vxlan | VXLAN虚拟化网络 |
| `vxlan4787/` | vxlan_custom | vxlan | VXLAN自定义端口4787 |
| `vxlan_vlan/` | vxlan_vlan_composite | composite | VXLAN + VLAN复合封装 |
| `vlan_gre/` | vlan_gre_composite | composite | VLAN + GRE复合封装 |
| `IPTCP-200ips/` | large_ip_set | plain | 大IP地址集测试数据 |
| `IPTCP-TC-001-*` | test_case_001 | mixed | 测试用例001系列 |
| `IPTCP-TC-002-5-*` | test_case_002_5 | mixed | 测试用例002-5系列 |
| `IPTCP-TC-002-8-*` | test_case_002_8 | mixed | 测试用例002-8系列 |

## 🚀 **运行方法**

### 1. 集成到自动化测试

#### 完整测试模式 (包含真实数据验证)
```bash
# 运行所有测试，包括真实数据验证
python run_tests.py --full

# 只运行真实数据验证测试
python run_tests.py --type real_data

# 专门的样本验证模式
python run_tests.py --samples
```

#### 使用pytest直接运行
```bash
# 运行所有真实数据测试
pytest -m real_data -v

# 运行特定测试文件
pytest tests/integration/test_real_data_validation.py -v

# 运行特定类别测试
pytest -k "test_sample_category_validation and mpls" -v
```

### 2. 独立运行脚本

#### 基本用法
```bash
# 完整验证所有样本
python validate_samples.py

# 快速验证模式
python validate_samples.py --quick

# 只验证特定类别
python validate_samples.py --category mpls

# 静默模式运行
python validate_samples.py --quiet
```

#### 实用命令
```bash
# 检查样本目录状况
python validate_samples.py --check

# 查看所有可用类别
python validate_samples.py --list-categories

# 不生成HTML报告
python validate_samples.py --no-html
```

## 🔍 **验证方法**

### 验证指标

每个样本文件的验证包括以下方面：

1. **文件完整性**
   - 文件可读性
   - 包含有效数据包
   - 文件格式正确性

2. **封装检测准确性**
   - 自动识别封装类型
   - 统计各种封装类型数量
   - 验证检测结果合理性

3. **协议栈解析完整性**
   - 多层协议栈正确解析
   - IP层识别和提取
   - 协议递归处理

4. **数据提取有效性**
   - IP地址正确提取
   - TCP会话识别
   - 载荷数据可访问

5. **性能基准**
   - 处理时间合理
   - 内存使用可控
   - 错误率低于阈值

### 成功标准

- **单文件验证**: 错误率 < 20%，至少检测到一种封装，提取到IP地址
- **类别验证**: 类别内文件成功率 ≥ 80%
- **整体验证**: 全局成功率 ≥ 90%，测试文件数 ≥ 8个

### 错误处理

- **文件级错误**: 记录具体错误信息，不影响其他文件测试
- **包级错误**: 统计错误包数量，允许一定比例的处理失败
- **类别级错误**: 单个类别失败不影响整体验证

## 📊 **报告系统**

### 自动生成报告

1. **JSON详细报告**
   - 位置: `reports/real_data_validation_report.json`
   - 内容: 完整测试结果、统计信息、错误详情

2. **HTML交互报告**
   - 位置: `reports/samples_validation_report.html`
   - 内容: 可视化测试结果、过滤和搜索功能

3. **控制台实时输出**
   - 测试进度显示
   - 实时结果反馈
   - 错误信息及时提示

### 报告内容

```json
{
  "test_summary": {
    "total_files": 15,
    "successful_files": 14,
    "success_rate": 0.933,
    "test_timestamp": "2025-06-11 18:30:45",
    "categories_tested": 8
  },
  "category_stats": {
    "mpls": {
      "total_files": 2,
      "successful_files": 2,
      "success_rate": 1.0,
      "total_packets": 2000,
      "avg_processing_time": 0.18
    }
  },
  "detailed_results": [...]
}
```

## 🔧 **配置和自定义**

### 测试参数调整

在 `RealDataValidator` 中可以调整：

```python
class SampleFileInfo:
    max_test_packets: int = 100  # 限制测试包数量
    
class RealDataValidator:
    # 成功率阈值
    ERROR_RATE_THRESHOLD = 0.2    # 20%错误率
    SUCCESS_RATE_THRESHOLD = 0.8  # 80%成功率
```

### pytest标记

- `@pytest.mark.real_data` - 真实数据测试标记
- `@pytest.mark.integration` - 集成测试标记  
- `@pytest.mark.slow` - 耗时测试标记

### 目录配置

在 `get_sample_file_map()` 方法中可以：
- 添加新的样本目录
- 修改预期封装类型
- 调整文件匹配模式

## ⚡ **性能优化**

### 测试优化策略

1. **包数量限制**: 每个文件最多测试100个包
2. **并行执行**: 支持pytest并行插件
3. **快速失败**: 可配置最大失败数

4. **智能跳过**: 自动跳过空目录和无效文件
5. **缓存机制**: 重复测试时利用缓存

### 资源控制

- **内存管理**: 及时释放大型pcap文件
- **时间控制**: 单个测试有超时保护
- **错误限制**: 防止无限错误循环

## 🔄 **CI/CD 集成**

### GitHub Actions示例

```yaml
name: Real Data Validation
on: [push, pull_request]

jobs:
  validate-samples:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Setup Python
      uses: actions/setup-python@v3
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Run samples validation
      run: python run_tests.py --samples
    - name: Upload reports
      uses: actions/upload-artifact@v3
      with:
        name: validation-reports
        path: reports/
```

### 持续监控

- **每次提交**: 运行快速验证
- **每日构建**: 运行完整验证
- **版本发布**: 强制100%通过率

## 🛠️ **扩展指南**

### 添加新的样本类别

1. **放置样本文件**
   ```bash
   mkdir tests/data/samples/new_protocol/
   cp your_samples.pcap tests/data/samples/new_protocol/
   ```

2. **配置测试类别**
   ```python
   # 在 get_sample_file_map() 中添加
   "new_protocol": {
       "category": "new_protocol_category",
       "encapsulation": "expected_type",
       "description": "新协议描述",
       "pattern": "*.pcap"
   }
   ```

3. **更新参数化测试**
   ```python
   @pytest.mark.parametrize("category", [
       "plain_ip", "single_vlan", ..., "new_protocol_category"
   ])
   ```

### 自定义验证逻辑

继承 `RealDataValidator` 并重写关键方法：

```python
class CustomValidator(RealDataValidator):
    def validate_sample_file(self, sample_info: SampleFileInfo) -> TestResult:
        # 自定义验证逻辑
        pass
```

## ❓ **故障排除**

### 常见问题

1. **样本文件缺失**
   ```bash
   python validate_samples.py --check
   ```

2. **Python环境问题**
   ```bash
   # 使用虚拟环境
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

3. **依赖问题**
   ```bash
   pip install scapy pytest pytest-html
   ```

### 调试技巧

- 使用 `-s` 选项查看详细输出
- 单独测试特定类别排查问题
- 检查 `reports/` 目录下的详细报告

## 📚 **相关文档**

- [PktMask 用户手册](README.md)
- [测试框架文档](AUTOMATED_TESTING_REBUILD_SUMMARY.md)
- [多层封装处理](MULTI_LAYER_ENCAPSULATION_IMPLEMENTATION_PLAN.md)

---

**最后更新**: 2025年6月11日  
**适用版本**: PktMask v2.0+  
**维护者**: PktMask开发团队 