# MaskStage 迁移指南

> **版本**: v1.0.0  
> **日期**: 2025-07-13  
> **适用范围**: PktMask ≥ 3.0  

## 概述

PktMask 3.0 引入了全新的双模块架构 `NewMaskPayloadStage`，替代了旧版的 `MaskPayloadStage`。本指南将帮助您从旧版实现迁移到新版实现。

## 为什么要迁移？

### 新版优势

1. **双模块架构**: 协议分析与掩码应用完全解耦
2. **更好的性能**: 流式处理和内存优化
3. **协议无关**: 支持 TLS、HTTP 等多种协议
4. **易于扩展**: 新增协议仅需扩展 Marker 模块
5. **增强的错误处理**: 多级错误恢复和降级机制
6. **完善的监控**: 性能监控和调试接口

### 旧版问题

1. **单体架构**: 协议耦合度高，难以扩展
2. **性能瓶颈**: 无法针对不同协议优化
3. **调试困难**: 无法独立验证各个组件
4. **维护成本**: 添加新协议需要修改核心逻辑

## 迁移步骤

### 1. 自动迁移（推荐）

新版实现完全向后兼容，大多数情况下无需修改代码：

```python
# 旧版代码（仍然有效）
from pktmask.core.pipeline.stages import MaskStage

stage = MaskStage({
    "mode": "enhanced",
    "recipe_dict": {...}
})
```

系统会自动使用新版实现，并在日志中显示：
```
INFO: 使用新一代双模块架构 MaskPayloadStage
```

### 2. 显式使用新版（推荐）

```python
# 新版代码
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

stage = NewMaskPayloadStage({
    "protocol": "tls",
    "mode": "enhanced",
    "marker_config": {
        "tls": {
            "preserve_handshake": True,
            "preserve_application_data": False
        }
    }
})
```

### 3. 配置格式迁移

#### 旧版配置格式
```python
config = {
    "mode": "enhanced",
    "recipe_dict": {
        "tls_20_strategy": "keep_all",
        "tls_23_strategy": "mask_payload"
    }
}
```

#### 新版配置格式
```python
config = {
    "protocol": "tls",
    "mode": "enhanced",
    "marker_config": {
        "tls": {
            "preserve_handshake": True,
            "preserve_application_data": False,
            "preserve_alert": True
        }
    },
    "masker_config": {
        "chunk_size": 1000,
        "verify_checksums": True
    }
}
```

## 配置映射表

| 旧版参数 | 新版参数 | 说明 |
|---------|---------|------|
| `mode: "enhanced"` | `mode: "enhanced"` | 处理模式保持不变 |
| `mode: "basic"` | `mode: "basic"` | 基础模式保持不变 |
| `recipe_dict` | `marker_config.tls` | TLS 配置映射到 marker 配置 |
| `tls_20_strategy: "keep_all"` | `preserve_handshake: true` | TLS 握手保留 |
| `tls_23_strategy: "mask_payload"` | `preserve_application_data: false` | 应用数据掩码 |

## 测试迁移

### 1. 单元测试
```bash
# 测试新版实现
python -m pytest tests/unit/pipeline/stages/mask_payload_v2/ -v
```

### 2. 集成测试
```python
# 测试配置兼容性
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

# 使用旧版配置格式
legacy_config = {
    "mode": "enhanced",
    "recipe_dict": {"tls_23_strategy": "mask_payload"}
}

stage = NewMaskPayloadStage(legacy_config)
assert stage.initialize()
```

### 3. 性能对比
```python
import time
from pktmask.core.pipeline.stages.mask_payload.stage import MaskPayloadStage
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

# 测试处理时间
def benchmark_stage(stage_class, config, test_file):
    stage = stage_class(config)
    stage.initialize()
    
    start_time = time.time()
    result = stage.process_file(test_file, "/tmp/output.pcap")
    duration = time.time() - start_time
    
    return duration, result

# 比较性能
old_time, old_result = benchmark_stage(MaskPayloadStage, legacy_config, "test.pcap")
new_time, new_result = benchmark_stage(NewMaskPayloadStage, legacy_config, "test.pcap")

print(f"旧版耗时: {old_time:.3f}s")
print(f"新版耗时: {new_time:.3f}s")
print(f"性能提升: {(old_time - new_time) / old_time * 100:.1f}%")
```

## 故障排除

### 1. 导入错误
```python
# 错误: ImportError: No module named 'mask_payload_v2'
# 解决: 确保使用最新版本的 PktMask
pip install --upgrade pktmask
```

### 2. 配置不兼容
```python
# 错误: 配置参数不被识别
# 解决: 使用配置转换工具
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

stage = NewMaskPayloadStage(legacy_config)  # 自动转换
```

### 3. 性能问题
```python
# 如果新版性能不如预期，可以调整配置
config = {
    "protocol": "tls",
    "mode": "enhanced",
    "masker_config": {
        "chunk_size": 2000,  # 增加块大小
        "verify_checksums": False  # 禁用校验和验证
    },
    "performance_config": {
        "enable_monitoring": False  # 禁用性能监控
    }
}
```

## 回滚方案

如果遇到问题需要回滚到旧版：

### 1. 配置回滚
```python
# 在 PipelineExecutor 配置中禁用新版
config = {
    "mask": {
        "use_new_implementation": False,  # 强制使用旧版
        "mode": "enhanced"
    }
}
```

### 2. 代码回滚
```python
# 显式使用旧版实现
from pktmask.core.pipeline.stages.mask_payload.stage import MaskPayloadStage

stage = MaskPayloadStage(config)
```

## 支持和帮助

- **文档**: 查看 `docs/architecture/NEW_MASKSTAGE_UNIFIED_DESIGN.md`
- **示例**: 参考 `tests/unit/pipeline/stages/mask_payload_v2/`
- **问题报告**: 提交 GitHub Issue 并标记 `migration` 标签

## 时间表

- **当前**: 新旧版本并存，自动使用新版
- **下一版本**: 旧版标记为废弃，发出警告
- **未来版本**: 完全移除旧版实现

建议尽早迁移到新版实现，以获得更好的性能和功能。
