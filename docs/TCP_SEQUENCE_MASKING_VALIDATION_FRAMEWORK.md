# TCP Sequence-Based Masking Validation Framework

## 验证框架概述

本文档详细描述了TCP序列号掩码机制重构的验证测试框架，确保新机制的正确性、性能和兼容性。验证框架采用分层测试策略，从单元测试到端到端集成测试，全面覆盖新机制的各个方面。

## TLS样本验证规范

### 测试文件: `tests/samples/tls-single/tls_sample.pcap`

**预期处理结果**:
- **需要置零的包**: 第14、15号包 (TLS Application Data, content type = 23)
- **保持不变的包**: 第4、6、7、9、10、12、16、19号包 (TLS Handshake/Alert, content type = 20/21/22)

**验证要点**:
1. **TLS头部保留**: 每个TLS记录的前5字节必须保留不变
2. **载荷精确置零**: TLS Application Data的载荷部分必须全部置零
3. **多记录处理**: 如果单个TCP段包含多个TLS记录，每个记录的头部都要保留
4. **序列号准确性**: 置零位置必须严格按照TCP序列号范围计算

### 详细验证矩阵

| 包号 | TLS Content Type | 预期操作 | 验证要点 |
|------|------------------|----------|----------|
| 4    | 22 (Handshake)   | 保持不变 | 整个包内容不变 |
| 6    | 22 (Handshake)   | 保持不变 | 整个包内容不变 |
| 7    | 22 (Handshake)   | 保持不变 | 整个包内容不变 |
| 9    | 22 (Handshake)   | 保持不变 | 整个包内容不变 |
| 10   | 22 (Handshake)   | 保持不变 | 整个包内容不变 |
| 12   | 22 (Handshake)   | 保持不变 | 整个包内容不变 |
| 14   | 23 (App Data)    | 载荷置零 | 保留5字节TLS头，载荷全零 |
| 15   | 23 (App Data)    | 载荷置零 | 保留5字节TLS头，载荷全零 |
| 16   | 20/21 (Alert)    | 保持不变 | 整个包内容不变 |
| 19   | 22 (Handshake)   | 保持不变 | 整个包内容不变 |

## Phase-by-Phase验证计划

### Phase 1: 数据结构验证

**验证目标**: 确保新的掩码表数据结构正确性

```python
class TestSequenceMaskTable:
    def test_tcp_stream_id_generation(self):
        """测试TCP流ID生成的正确性"""
        # 验证方向性标识正确
        # 验证相同连接不同方向生成不同ID
        
    def test_mask_entry_creation(self):
        """测试掩码条目创建"""
        # 验证序列号范围计算
        # 验证头部保留规则
        
    def test_mask_table_operations(self):
        """测试掩码表CRUD操作"""
        # 验证添加、查询、更新、删除操作
        # 验证按流ID分组功能
```

**验证数据**:
```python
# 测试用例数据
test_stream_data = {
    "src_ip": "192.168.1.100",
    "src_port": 12345,
    "dst_ip": "10.0.0.1", 
    "dst_port": 443,
    "direction": "forward"
}

expected_stream_id = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
```

### Phase 2: PyShark分析器验证

**验证目标**: 确保掩码表生成逻辑正确

```python
class TestPySharkAnalyzer:
    def test_tls_sample_analysis(self):
        """使用tls_sample.pcap测试分析器"""
        analyzer = PySharkAnalyzer()
        mask_table = analyzer.analyze("tests/samples/tls-single/tls_sample.pcap")
        
        # 验证只为包14、15生成掩码条目
        assert len([entry for entry in mask_table.entries 
                   if entry.packet_number in [14, 15]]) == 2
        
        # 验证包4、6、7、9、10、12、16、19不生成掩码条目
        assert len([entry for entry in mask_table.entries 
                   if entry.packet_number in [4,6,7,9,10,12,16,19]]) == 0
                   
    def test_tls_record_parsing(self):
        """测试TLS记录解析准确性"""
        # 验证TLS content type识别正确
        # 验证TLS记录边界计算正确
        # 验证多记录场景处理
        
    def test_sequence_number_calculation(self):
        """测试TCP序列号计算"""
        # 验证绝对序列号计算正确
        # 验证序列号范围计算准确
```

**关键测试数据**:
```python
# TLS Application Data包的预期掩码条目
expected_mask_entries = [
    {
        "packet_number": 14,
        "tcp_stream_id": "TCP_x.x.x.x:port1_y.y.y.y:port2_forward",
        "seq_start": 12345,  # 实际计算值
        "seq_end": 12400,    # 实际计算值
        "mask_type": "tls_application_data",
        "preserve_headers": [(12345, 12349)]  # 保留5字节TLS头
    },
    # 包15的类似条目
]
```

### Phase 3: Scapy回写器验证

**验证目标**: 确保序列号匹配和置零逻辑正确

```python
class TestScapyRewriter:
    def test_sequence_matching_accuracy(self):
        """测试序列号匹配准确性"""
        rewriter = ScapyRewriter()
        
        # 测试精确匹配
        packet_seq = 12345
        payload_len = 100
        mask_entry = MaskEntry(seq_start=12350, seq_end=12380)
        
        is_match, start_offset, end_offset = rewriter.match_sequence_range(
            packet_seq, payload_len, mask_entry
        )
        
        assert is_match == True
        assert start_offset == 5  # 12350 - 12345
        assert end_offset == 35   # 12380 - 12345
        
    def test_tls_sample_masking(self):
        """使用tls_sample.pcap测试完整置零流程"""
        # 加载掩码表
        mask_table = load_mask_table("mask_table.json")
        
        # 处理PCAP文件
        rewriter = ScapyRewriter()
        processed_packets = rewriter.apply_masks("tls_sample.pcap", mask_table)
        
        # 验证包14、15的TLS载荷被置零
        packet_14 = processed_packets[13]  # 0-based index
        packet_15 = processed_packets[14]
        
        # 检查TLS头部（前5字节）保留
        assert packet_14.payload[:5] != b'\x00\x00\x00\x00\x00'
        # 检查TLS载荷（5字节后）被置零
        assert packet_14.payload[5:] == b'\x00' * (len(packet_14.payload) - 5)
        
    def test_non_matching_packets_unchanged(self):
        """验证非匹配包保持不变"""
        # 验证包4、6、7、9、10、12、16、19完全不变
```

### Phase 4: 协议策略验证

**验证目标**: 确保协议策略框架的可扩展性

```python
class TestProtocolStrategies:
    def test_tls_strategy(self):
        """测试TLS协议策略"""
        strategy = TLSMaskStrategy()
        
        # 测试协议检测
        assert strategy.detect_protocol(tls_packet) == True
        assert strategy.detect_protocol(http_packet) == False
        
        # 测试掩码条目生成
        mask_entries = strategy.generate_mask_entries(tls_packets)
        assert len(mask_entries) > 0
        
    def test_http_strategy(self):
        """测试HTTP协议策略"""
        strategy = HTTPMaskStrategy()
        
        # 测试HTTP请求/响应识别
        # 测试HTTP头部保留逻辑
        
    def test_strategy_factory(self):
        """测试策略工厂机制"""
        factory = ProtocolStrategyFactory()
        
        # 测试策略注册
        factory.register("tls", TLSMaskStrategy)
        
        # 测试策略获取
        strategy = factory.get_strategy("tls")
        assert isinstance(strategy, TLSMaskStrategy)
```

### Phase 5: 端到端集成验证

**验证目标**: 确保完整流程正确性和性能

```python
class TestEndToEndIntegration:
    def test_complete_tls_workflow(self):
        """完整的TLS文件处理流程测试"""
        # 1. TShark预处理
        preprocessor = TSharkPreprocessor()
        reassembled_file = preprocessor.process("tls_sample.pcap")
        
        # 2. PyShark分析
        analyzer = PySharkAnalyzer()
        mask_table = analyzer.analyze(reassembled_file)
        
        # 3. Scapy回写
        rewriter = ScapyRewriter()
        output_file = rewriter.apply_masks(reassembled_file, mask_table)
        
        # 4. 验证最终结果
        self.verify_tls_sample_results(output_file)
        
    def test_performance_benchmarks(self):
        """性能基准测试"""
        large_file = "tests/samples/large_tls_file.pcap"
        
        start_time = time.time()
        process_file(large_file)
        end_time = time.time()
        
        processing_time = end_time - start_time
        file_size = os.path.getsize(large_file)
        packets_per_second = get_packet_count(large_file) / processing_time
        
        # 验证性能目标
        assert packets_per_second >= 1000  # ≥1000 pps
        assert get_memory_usage() < 100    # <100MB/1000包
        
    def test_backward_compatibility(self):
        """向后兼容性测试"""
        # 使用现有测试样本验证
        test_files = [
            "tests/samples/http/http_sample.pcap",
            "tests/samples/TLS/tls_complex.pcap",
            "tests/samples/singlevlan/vlan_sample.pcap"
        ]
        
        for test_file in test_files:
            # 新系统处理结果
            new_result = process_with_new_system(test_file)
            # 旧系统处理结果  
            old_result = process_with_old_system(test_file)
            
            # 验证核心功能一致性（允许实现细节差异）
            assert compare_core_functionality(new_result, old_result)
```

## 性能验证基准

### 1. 处理速度基准
- **目标**: ≥1000 pps (packets per second)
- **测试方法**: 使用不同大小的PCAP文件测试
- **验证点**: 
  - 小文件（<1MB）: ≥2000 pps
  - 中等文件（1-10MB）: ≥1500 pps  
  - 大文件（>10MB）: ≥1000 pps

### 2. 内存使用基准
- **目标**: <100MB/1000包
- **测试方法**: 监控处理过程中的内存峰值
- **验证点**:
  - 基础内存: <50MB
  - 1000包处理: <100MB
  - 10000包处理: <500MB

### 3. 序列号匹配精度
- **目标**: ≥99%匹配准确率
- **测试方法**: 人工验证关键测试用例
- **验证点**:
  - 精确匹配: 100%准确
  - 边界匹配: ≥99%准确
  - 跨包匹配: ≥95%准确

## 错误处理验证

### 1. 异常场景测试
```python
class TestErrorHandling:
    def test_corrupted_pcap_file(self):
        """测试损坏的PCAP文件处理"""
        # 验证优雅降级，不崩溃
        
    def test_incomplete_tcp_stream(self):
        """测试不完整的TCP流处理"""
        # 验证部分数据正确处理
        
    def test_unsupported_protocol(self):
        """测试不支持的协议处理"""
        # 验证回退到通用处理机制
        
    def test_memory_pressure(self):
        """测试内存压力场景"""
        # 验证内存不足时的处理策略
```

### 2. 边界条件测试
- **序列号回绕**: 测试TCP序列号32位回绕情况
- **零长度载荷**: 测试空TCP载荷的处理
- **巨大文件**: 测试GB级别文件的处理能力
- **并发处理**: 测试多文件并发处理的稳定性

## 验证工具和脚本

### 1. 自动化验证脚本
```bash
#!/bin/bash
# validate_tcp_masking.sh

echo "开始TCP序列号掩码机制验证..."

# Phase 1: 单元测试
pytest tests/unit/test_sequence_mask_table.py -v

# Phase 2: PyShark分析器测试  
pytest tests/unit/test_pyshark_analyzer.py -v

# Phase 3: Scapy回写器测试
pytest tests/unit/test_scapy_rewriter.py -v

# Phase 4: 协议策略测试
pytest tests/unit/test_protocol_strategies.py -v

# Phase 5: 集成测试
pytest tests/integration/test_tcp_masking_e2e.py -v

# TLS样本专项验证
python scripts/validate_tls_sample.py

echo "验证完成！"
```

### 2. TLS样本验证脚本
```python
#!/usr/bin/env python3
# scripts/validate_tls_sample.py

def validate_tls_sample():
    """专门验证tls_sample.pcap的处理结果"""
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    output_file = "output/tls_sample_masked.pcap"
    
    # 处理文件
    result = process_tcp_masking(input_file, output_file)
    
    # 验证结果
    packets = load_packets(output_file)
    
    # 检查包14、15的置零效果
    for packet_num in [14, 15]:
        packet = packets[packet_num - 1]  # 转换为0-based索引
        
        # 验证TLS头部保留
        tls_header = packet.payload[:5]
        assert tls_header != b'\x00\x00\x00\x00\x00', f"包{packet_num}的TLS头部被错误置零"
        
        # 验证TLS载荷置零
        tls_payload = packet.payload[5:]
        assert tls_payload == b'\x00' * len(tls_payload), f"包{packet_num}的TLS载荷未完全置零"
    
    # 检查其他包保持不变
    for packet_num in [4, 6, 7, 9, 10, 12, 16, 19]:
        original_packet = load_original_packet(input_file, packet_num)
        processed_packet = packets[packet_num - 1]
        
        assert original_packet.payload == processed_packet.payload, \
            f"包{packet_num}被错误修改"
    
    print("✅ TLS样本验证通过！")

if __name__ == "__main__":
    validate_tls_sample()
```

## 持续集成验证

### 1. CI流水线配置
```yaml
# .github/workflows/tcp_masking_validation.yml
name: TCP Masking Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.8
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
        
    - name: Run validation suite
      run: |
        chmod +x scripts/validate_tcp_masking.sh
        ./scripts/validate_tcp_masking.sh
        
    - name: Generate coverage report
      run: |
        pytest --cov=src/pktmask/core/trim --cov-report=html
        
    - name: Upload coverage
      uses: actions/upload-artifact@v2
      with:
        name: coverage-report
        path: htmlcov/
```

### 2. 验证门禁标准
- **单元测试通过率**: 100%
- **代码覆盖率**: ≥80%
- **TLS样本验证**: 100%通过
- **性能回归**: 无显著下降（<5%）
- **内存泄漏检查**: 无内存泄漏

## 验证报告模板

### 验证完成报告
```markdown
# TCP序列号掩码机制验证报告

## 验证概述
- **验证日期**: 2024-XX-XX
- **验证版本**: v2.0.0
- **验证环境**: Ubuntu 20.04, Python 3.8

## 验证结果汇总
- **单元测试**: 125/125 通过 (100%)
- **集成测试**: 45/45 通过 (100%)
- **TLS样本验证**: ✅ 通过
- **性能基准**: ✅ 达标 (1200 pps)
- **内存使用**: ✅ 达标 (80MB/1000包)

## 关键验证点
### TLS样本处理验证
- [x] 包14、15正确置零（保留TLS头部）
- [x] 包4、6、7、9、10、12、16、19保持不变
- [x] 序列号匹配准确率: 99.8%

### 性能验证
- [x] 处理速度: 1200 pps（超出目标20%）
- [x] 内存使用: 80MB/1000包（低于目标20%）
- [x] 序列号匹配时间: 0.3ms（低于目标70%）

## 发现的问题
- 无关键问题
- 2个次要性能优化建议（见详细报告）

## 结论
TCP序列号掩码机制已准备好部署到生产环境。
```

通过这个全面的验证框架，我们可以确保TCP序列号掩码机制重构的质量和可靠性，为生产环境部署提供充分的质量保证。 