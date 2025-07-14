# 配置对比分析报告

## ⚠️ 一般配置差异

**路径**: `marker_config.tls`
- GUI 值: `None`
- 脚本值: `{'preserve_handshake': True, 'preserve_application_data': False}`
- 影响: GUI 缺少配置项

**路径**: `marker_config.preserve`
- GUI 值: `{'handshake': True, 'application_data': False, 'alert': True, 'change_cipher_spec': True, 'heartbeat': True}`
- 脚本值: `None`
- 影响: Script-Pipeline 缺少配置项

**路径**: `enabled`
- GUI 值: `True`
- 脚本值: `None`
- 影响: Script-Direct 缺少配置项

**路径**: `marker_config.tls`
- GUI 值: `None`
- 脚本值: `{'preserve_handshake': True, 'preserve_application_data': False}`
- 影响: GUI 缺少配置项

**路径**: `marker_config.preserve`
- GUI 值: `{'handshake': True, 'application_data': False, 'alert': True, 'change_cipher_spec': True, 'heartbeat': True}`
- 脚本值: `None`
- 影响: Script-Direct 缺少配置项
