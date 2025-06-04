# PktMask

PktMask 是一个用于处理网络数据包文件中 IP 地址替换的图形界面工具。它可以帮助网络管理员和安全研究人员在分享网络数据包文件时保护敏感信息。

## 功能特点

- 图形用户界面，操作简单直观
- 支持 pcap 和 pcapng 文件格式
- 智能 IP 地址替换算法
  - 保持网络结构
  - 局部随机替换
  - 分层一致性替换
- 支持 IPv4 和 IPv6 地址
- 实时处理进度显示
- 详细的处理日志
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

1. 启动 PktMask
2. 点击"选择目录"按钮，选择包含 pcap/pcapng 文件的目录
3. 点击"开始处理"按钮
4. 等待处理完成
5. 查看处理日志和结果

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

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过以下方式联系：

- 提交 Issue
- 发送邮件至：ricky.wang@netis.com 