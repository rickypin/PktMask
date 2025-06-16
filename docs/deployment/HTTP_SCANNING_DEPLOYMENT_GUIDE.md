# HTTP载荷扫描策略生产部署指南

## 概述

本指南提供了HTTP载荷扫描策略从开发环境到生产环境的完整部署流程，包括迁移管理、监控配置和故障处理操作手册。

## 1. 部署前准备

### 1.1 环境要求
```yaml
生产环境要求:
  - Python: >= 3.8
  - 内存: >= 8GB (推荐16GB)
  - CPU: >= 4核心 (推荐8核心)
  - 磁盘: >= 100GB 可用空间
  - 网络: 稳定网络连接
```

### 1.2 依赖检查
```bash
# 验证Python环境
python --version

# 检查必要依赖
pip check

# 验证配置文件
python -m pktmask.core.trim.migration.config_validator
```

### 1.3 备份现有系统
```bash
# 备份配置文件
cp -r configs configs_backup_$(date +%Y%m%d)

# 备份数据库（如果有）
# 根据实际情况调整

# 创建系统快照
# 根据实际基础设施调整
```

## 2. 迁移执行流程

### 2.1 阶段1：基线验证（第1天）
```python
# 启动迁移管理器
from pktmask.core.trim.migration.strategy_migrator import StrategyMigrator

migrator = StrategyMigrator()

# 执行基线验证
result = await migrator.execute_phase_1()
print(f"基线验证结果: {result.success}")
```

**验证清单：**
- [ ] Legacy策略功能正常
- [ ] 扫描策略基础功能正常
- [ ] 双策略配置加载正确
- [ ] 监控系统运行正常

### 2.2 阶段2：小规模A/B测试（第2-3天）
```yaml
# 配置A/B测试
ab_test:
  scanning_ratio: 0.10  # 10%流量使用扫描策略
  duration_hours: 48
  success_criteria:
    error_rate_threshold: 0.05
    performance_degradation_threshold: 0.20
```

**监控重点：**
- 错误率对比
- 性能指标对比
- 内存使用对比
- CPU使用率

### 2.3 阶段3：渐进推广（第4-10天）
```yaml
# 渐进增加扫描策略使用比例
推广计划:
  第4天: 25%
  第6天: 50%
  第8天: 75%
  第10天: 90%
```

**每次推广前检查：**
- [ ] 前一阶段指标正常
- [ ] 无严重告警
- [ ] 系统资源充足

### 2.4 阶段4：完全迁移（第11-12天）
```yaml
# 完全切换到扫描策略
strategy_mode: scanning  # 100%使用扫描策略
legacy_fallback: true    # 保持legacy备用
```

### 2.5 阶段5：清理Legacy（第13-14天）
```yaml
# 移除legacy代码（谨慎操作）
cleanup:
  remove_legacy_code: false  # 建议保留一段时间
  archive_legacy_configs: true
```

## 3. 监控和告警配置

### 3.1 关键指标监控
```yaml
监控指标:
  性能指标:
    - HTTP处理延迟 (< 100ms)
    - 吞吐量 (维持或提升)
    - 内存使用率 (< 80%)
    - CPU使用率 (< 70%)
  
  业务指标:
    - 处理成功率 (> 95%)
    - 错误率 (< 5%)
    - 数据包丢失率 (< 0.1%)
    - 载荷裁切准确性 (> 90%)
```

### 3.2 告警配置
```yaml
告警级别:
  CRITICAL: 
    - 错误率 > 10%
    - 性能下降 > 50%
    - 系统不可用
    - 内存使用 > 95%
  
  WARNING:
    - 错误率 > 5%
    - 性能下降 > 20%
    - 内存使用 > 80%
    - CPU使用 > 70%
  
  INFO:
    - 迁移阶段变更
    - 配置更新
    - 正常维护操作
```

### 3.3 告警渠道配置
```yaml
# 配置文件: config/production/dual_strategy_deployment.yaml
alerts:
  email:
    enabled: true
    smtp_server: "smtp.company.com"
    recipients: 
      - "ops-team@company.com"
      - "dev-team@company.com"
  
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/..."
    channel: "#pktmask-alerts"
  
  logging:
    enabled: true
    level: "WARNING"
    file: "/var/log/pktmask/alerts.log"
```

## 4. 故障处理操作手册

### 4.1 常见问题处理

#### 问题1：扫描策略错误率过高
```bash
# 症状：错误率 > 5%
# 原因：扫描窗口配置不当、内存不足、并发过高

# 处理步骤：
1. 检查当前配置
python -m pktmask.core.trim.monitoring.health_monitor --check-config

2. 降低扫描窗口大小
# 编辑配置文件，将scan_window_size从8192减少到4096

3. 如果问题持续，执行紧急回退
python -m pktmask.core.trim.migration.emergency_rollback
```

#### 问题2：性能下降超过阈值
```bash
# 症状：处理延迟 > 200ms
# 原因：资源竞争、算法效率、数据倾斜

# 处理步骤：
1. 检查资源使用
top -p $(pgrep python)
free -h

2. 分析性能热点
python -m cProfile -o profile.stats main.py

3. 临时降低并发度
# 修改max_concurrent_files配置

4. 如需要，切换回legacy策略
python -m pktmask.core.trim.migration.strategy_migrator --emergency-legacy
```

#### 问题3：内存泄漏
```bash
# 症状：内存使用持续增长
# 原因：对象未释放、缓存过大

# 处理步骤：
1. 监控内存增长趋势
python -m pktmask.core.trim.monitoring.memory_monitor

2. 强制垃圾回收
python -c "import gc; gc.collect(); print('GC completed')"

3. 重启服务（如果内存使用 > 90%）
systemctl restart pktmask

4. 分析内存转储
python -m pktmask.core.trim.debugging.memory_profiler
```

### 4.2 紧急回退流程

#### 自动回退触发条件
- 错误率 > 15%
- 性能下降 > 60%
- 系统无响应 > 30秒
- 内存使用 > 98%

#### 手动回退操作
```bash
# 立即回退到legacy策略
python -m pktmask.core.trim.migration.emergency_rollback \
  --strategy legacy \
  --notify-ops \
  --reason "Manual rollback due to production issue"

# 验证回退成功
python -m pktmask.core.trim.testing.strategy_validator \
  --strategy legacy \
  --quick-test

# 通知团队
python -m pktmask.core.trim.notifications.send_alert \
  --level CRITICAL \
  --message "Emergency rollback completed - legacy strategy active"
```

### 4.3 故障排查工具

#### 健康检查工具
```bash
# 全面健康检查
python -m pktmask.core.trim.monitoring.health_monitor --full-check

# 策略对比测试
python -m pktmask.core.trim.testing.strategy_comparison \
  --input-file test_sample.pcap \
  --compare-strategies legacy,scanning

# 配置验证
python -m pktmask.core.trim.config.validator \
  --config-file config/production/dual_strategy_deployment.yaml
```

#### 诊断日志收集
```bash
# 收集诊断信息
python -m pktmask.core.trim.diagnostics.collect_logs \
  --output-dir /tmp/pktmask_diagnostics \
  --include-config \
  --include-metrics \
  --last-hours 24

# 生成诊断报告
python -m pktmask.core.trim.diagnostics.generate_report \
  --input-dir /tmp/pktmask_diagnostics \
  --output-file diagnostic_report.html
```

## 5. 维护操作

### 5.1 定期检查清单（每周）
- [ ] 检查错误日志
- [ ] 验证监控指标
- [ ] 更新配置（如需要）
- [ ] 清理临时文件
- [ ] 检查磁盘空间
- [ ] 验证备份完整性

### 5.2 性能优化
```yaml
# 根据实际使用情况调整配置
optimization:
  scan_window_size: 8192      # 根据内存调整
  max_concurrent_files: 4     # 根据CPU核心数调整
  cache_size_mb: 256         # 根据可用内存调整
  gc_threshold: 1000         # 根据处理量调整
```

### 5.3 配置更新流程
```bash
# 1. 在测试环境验证新配置
python -m pktmask.core.trim.config.validator \
  --config-file new_config.yaml \
  --test-mode

# 2. 备份当前配置
cp config/production/dual_strategy_deployment.yaml \
   config/production/dual_strategy_deployment.yaml.backup

# 3. 应用新配置
cp new_config.yaml config/production/dual_strategy_deployment.yaml

# 4. 重启服务
systemctl restart pktmask

# 5. 验证配置生效
python -m pktmask.core.trim.config.validator --verify-active
```

## 6. 安全考虑

### 6.1 配置文件安全
```bash
# 设置适当的文件权限
chmod 600 config/production/dual_strategy_deployment.yaml
chown pktmask:pktmask config/production/dual_strategy_deployment.yaml

# 加密敏感配置（如果需要）
python -m pktmask.core.security.config_encryption \
  --encrypt config/production/dual_strategy_deployment.yaml
```

### 6.2 日志安全
```yaml
# 确保敏感信息不被记录
logging:
  sanitize_logs: true
  redact_patterns:
    - "password"
    - "secret"
    - "token"
  max_log_size_mb: 100
  retention_days: 30
```

## 7. 联系信息

### 7.1 支持团队
- **开发团队**: dev-team@company.com
- **运维团队**: ops-team@company.com
- **紧急联系**: emergency-contact@company.com

### 7.2 文档和资源
- **API文档**: [internal-docs/api-reference]
- **架构文档**: [internal-docs/architecture]
- **故障案例库**: [internal-docs/troubleshooting]

## 附录

### A. 配置模板
参考：`config/production/dual_strategy_deployment.yaml`

### B. 监控仪表板
- Grafana: [monitoring-dashboard-url]
- Prometheus: [metrics-endpoint-url]

### C. 测试用例
参考：`tests/integration/test_deployment_validation.py`

---

**最后更新**: 2025年1月
**版本**: 1.0
**维护者**: PktMask开发团队 