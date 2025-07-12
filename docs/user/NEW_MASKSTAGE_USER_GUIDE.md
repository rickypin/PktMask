# MaskStage 用户指南

> **版本**: v2.0.0
> **更新日期**: 2025-07-12
> **适用版本**: PktMask ≥ 2.0

## 概述

PktMask 采用双模块架构掩码处理阶段，提供高性能、可扩展和可靠的掩码处理能力。

### 主要特性

- **双模块架构**: 协议分析与掩码应用分离
- **多协议支持**: TLS、HTTP 等协议智能识别
- **增强错误处理**: 多级错误恢复机制
- **性能优化**: 流式处理和内存管理

## 快速开始

### 基础使用

```python
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

# 创建掩码处理阶段
stage = NewMaskPayloadStage({
    "protocol": "tls",
    "mode": "enhanced"
})

# 初始化
stage.initialize()

# 处理文件
result = stage.process_file("input.pcap", "output.pcap")
print(f"处理了 {result.packets_processed} 个数据包")
```

### 自动迁移（推荐）

现有代码无需修改，系统会自动使用新版实现：

```python
# 现有代码保持不变
from pktmask.core.pipeline.stages import MaskStage

stage = MaskStage({"mode": "enhanced"})
# 自动使用新版 NewMaskPayloadStage
```

## 配置选项

### 基础配置

```python
config = {
    "protocol": "tls",        # 协议类型: "tls", "http", "auto"
    "mode": "enhanced"        # 处理模式: "enhanced", "basic"
}
```

### 高级配置

```python
config = {
    "protocol": "tls",
    "mode": "enhanced",
    
    # Marker模块配置
    "marker_config": {
        "tls": {
            "preserve_handshake": True,           # 保留握手消息
            "preserve_application_data": False,   # 掩码应用数据
            "preserve_alert": True,               # 保留警告消息
            "preserve_change_cipher_spec": True   # 保留密码规格变更
        }
    },
    
    # Masker模块配置
    "masker_config": {
        "chunk_size": 1000,          # 处理块大小
        "verify_checksums": True,    # 验证校验和
        "max_memory_mb": 2048        # 最大内存使用(MB)
    },
    
    # 性能配置
    "performance_config": {
        "enable_monitoring": True,    # 启用性能监控
        "detailed_logging": False    # 详细日志记录
    },
    
    # 错误处理配置
    "error_recovery": {
        "max_retries": 3,            # 最大重试次数
        "fallback_mode": "copy_original",  # 降级模式
        "error_threshold": 0.05      # 错误率阈值
    }
}
```

## 处理模式

### Enhanced 模式（推荐）

使用双模块架构进行智能协议分析和精确掩码：

```python
config = {
    "protocol": "tls",
    "mode": "enhanced"
}
```

**特点**:
- 智能TLS消息识别
- 精确的载荷掩码
- 跨TCP段处理
- 序列号回绕处理

### Basic 模式

快速文件复制模式，适用于测试或简单场景：

```python
config = {
    "mode": "basic"
}
```

**特点**:
- 快速文件复制
- 最小资源消耗
- 适用于测试环境

## 协议支持

### TLS 协议

```python
config = {
    "protocol": "tls",
    "marker_config": {
        "tls": {
            "preserve_handshake": True,        # TLS 握手 (类型 22)
            "preserve_application_data": False, # 应用数据 (类型 23)
            "preserve_alert": True,            # 警告消息 (类型 21)
            "preserve_change_cipher_spec": True # 密码规格变更 (类型 20)
        }
    }
}
```

### HTTP 协议（预留）

```python
config = {
    "protocol": "http",
    "marker_config": {
        "http": {
            "preserve_headers": True,
            "preserve_body": False
        }
    }
}
```

### 自动检测

```python
config = {
    "protocol": "auto"  # 自动检测协议类型
}
```

## 性能优化

### 内存优化

```python
config = {
    "masker_config": {
        "chunk_size": 2000,      # 增加块大小提升吞吐量
        "max_memory_mb": 4096    # 增加内存限制
    },
    "performance_config": {
        "enable_monitoring": False  # 禁用监控减少开销
    }
}
```

### 处理速度优化

```python
config = {
    "masker_config": {
        "verify_checksums": False,  # 禁用校验和验证
        "chunk_size": 5000         # 大块处理
    },
    "error_recovery": {
        "max_retries": 1           # 减少重试次数
    }
}
```

## 错误处理

### 自动恢复

系统提供多级错误恢复机制：

1. **重试机制**: 自动重试失败的操作
2. **降级处理**: 失败时自动降级到安全模式
3. **错误记录**: 详细的错误日志和统计

### 降级模式

```python
config = {
    "error_recovery": {
        "fallback_mode": "copy_original",  # 复制原文件
        # "fallback_mode": "minimal_mask", # 最小掩码
        # "fallback_mode": "skip_file",    # 跳过文件
        # "fallback_mode": "safe_mode"     # 安全模式
    }
}
```

## 监控和调试

### 性能监控

```python
config = {
    "performance_config": {
        "enable_monitoring": True,
        "detailed_logging": True
    }
}

stage = NewMaskPayloadStage(config)
result = stage.process_file("input.pcap", "output.pcap")

# 查看性能统计
print(f"处理时间: {result.duration_ms}ms")
print(f"内存峰值: {result.extra_metrics.get('peak_memory_mb')}MB")
```

### 调试模式

```python
config = {
    "mode": "debug",  # 启用调试模式
    "performance_config": {
        "detailed_logging": True
    }
}
```

## 故障排除

### 常见问题

1. **内存不足**
   ```python
   config = {
       "masker_config": {
           "chunk_size": 500,      # 减少块大小
           "max_memory_mb": 1024   # 降低内存限制
       }
   }
   ```

2. **处理速度慢**
   ```python
   config = {
       "masker_config": {
           "verify_checksums": False,  # 禁用校验和
           "chunk_size": 2000         # 增加块大小
       }
   }
   ```

3. **协议识别错误**
   ```python
   config = {
       "protocol": "tls",  # 明确指定协议
       "mode": "enhanced"
   }
   ```

### 日志分析

查看详细日志：
```bash
# 启用详细日志
export PKTMASK_LOG_LEVEL=DEBUG

# 运行处理
python your_script.py

# 查看日志文件
tail -f logs/maskstage_main.log
```

## 最佳实践

1. **使用 Enhanced 模式**: 获得最佳的处理效果
2. **明确指定协议**: 避免自动检测的开销
3. **合理设置内存限制**: 根据系统资源调整
4. **启用错误恢复**: 提高处理的健壮性
5. **监控性能指标**: 及时发现和解决问题

## 迁移指南

详细的迁移指南请参考：`docs/migration/MASKSTAGE_MIGRATION_GUIDE.md`

## 支持

- **文档**: `docs/architecture/NEW_MASKSTAGE_UNIFIED_DESIGN.md`
- **示例**: `tests/unit/pipeline/stages/mask_payload_v2/`
- **问题报告**: GitHub Issues
