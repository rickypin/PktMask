# PktMask

PktMask 是一个用于处理网络数据包文件的图形界面工具，专注于IP地址匿名化、载荷裁切和数据包去重功能。它可以帮助网络管理员和安全研究人员在分享网络数据包文件时保护敏感信息。

## 功能特性

### 支持的处理功能
- ✅ **IP地址匿名化**: 分层匿名化算法，支持多层封装
  - 保持网络结构
  - 局部随机替换
  - 分层一致性替换
  - 支持 IPv4 和 IPv6 地址
- ✅ **载荷裁切**: 智能TLS载荷处理，保护TLS握手信令
  - TLS握手信令保护
  - 应用数据智能裁切
  - 支持复杂网络流量
- ✅ **数据包去重**: 高效去除重复数据包
- ❌ **HTTP协议处理**: 已在v3.0版本中移除

### 支持的网络协议
- ✅ TLS/SSL协议智能处理
- ✅ TCP/UDP流处理
- ✅ 多层网络封装（VLAN、MPLS、VXLAN、GRE）
- ✅ 支持 pcap 和 pcapng 文件格式
- ❌ HTTP/HTTPS协议处理（v3.0移除）

### 界面特性
- 图形用户界面，操作简单直观
- 实时处理进度显示
- 详细的处理日志和统计报告
- 跨平台支持（Windows 和 macOS）

## 安装

### Windows

1. 从 [Releases](https://github.com/yourusername/pktmask/releases) 页面下载最新的 Windows 安装包
2. 双击安装包进行安装
3. 从开始菜单或桌面快捷方式启动 PktMask

### macOS

1. 从 [Releases](https://github.com/yourusername/pktmask/releases) 页面下载最新的 macOS 安装包
2. 双击安装包进行安装
3. 从应用程序文件夹启动 PktMask

## 使用方法

### 启动 GUI
```bash
# 推荐方式
./pktmask

# Windows 用户
python pktmask.py

# 使用 Python 模块
python -m pktmask
```

### 使用 CLI
```bash
# 掩码处理
./pktmask mask input.pcap -o output.pcap --dedup --anon

# 仅去重
./pktmask dedup input.pcap -o output.pcap

# 仅 IP 匿名化
./pktmask anon input.pcap -o output.pcap

# 查看帮助
./pktmask --help
./pktmask mask --help
```

### GUI 操作步骤

1. 启动 PktMask GUI
2. 点击"选择目录"按钮，选择包含 pcap/pcapng 文件的目录
3. 选择所需的处理功能：
   - IP地址匿名化
   - 载荷裁切（TLS智能处理）
   - 数据内包去重
4. 点击"开始处理"按钮
5. 等待处理完成
6. 查看处理日志和结果

## 版本说明

### v3.1 适配器架构重构（2025-01）
- **统一适配器目录**: 所有适配器迁移到 `src/pktmask/adapters/` 目录
  - 简化导入路径，提高代码可维护性
  - 保持向后兼容，旧导入路径仍然可用
- **统一异常处理**: 新增完整的异常层次结构
  - 12 个专门的异常类，覆盖各种场景
  - 支持上下文信息和格式化输出
- **命名规范**: 制定统一的适配器命名规范
- **性能优化**: 代理文件开销 <10%，对性能影响可忽略

### v3.0 重大变更
- **移除HTTP协议支持**: 完全移除了HTTP/HTTPS协议的特化处理功能
  - 移除HTTP头部保留和智能裁切
  - 移除HTTP相关的配置项
  - 界面保持100%兼容，HTTP功能显示为"已移除"状态
- **保持功能**: TLS处理、IP匿名化、数据包去重功能完全保留
- **技术改进**: 简化代码架构，提升系统稳定性

## 开发

### 环境要求

- Python 3.8 或更高版本
- pip

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
```

### 项目结构

PktMask 采用模块化设计，主要组件包括：

```
src/pktmask/
├── adapters/          # 统一的适配器模块（v3.1 重构）
├── core/              # 核心处理逻辑
├── domain/            # 业务数据模型
├── gui/               # 图形用户界面
├── infrastructure/    # 基础设施
└── cli.py             # 命令行接口
```

#### 适配器架构（v3.1 新增）

从 v3.1 版本开始，所有适配器统一存放在 `src/pktmask/adapters/` 目录下，提供：

- **处理器适配**：将传统处理器适配为新的管道接口
- **数据格式转换**：事件和统计数据的格式转换
- **向后兼容**：保持旧接口的兼容性
- **统一异常处理**：提供一致的异常层次结构

详细文档请参考 [docs/development/adapters_usage_guide.md](docs/development/adapters_usage_guide.md)

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过以下方式联系：

- 提交 Issue
- 发送邮件至：ricky.wang@netis.com 