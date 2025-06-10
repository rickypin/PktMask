#!/bin/bash

# PktMask macOS 应用修复脚本
# 此脚本用于解决未签名应用的运行问题

echo "🔧 PktMask macOS 应用修复工具"
echo "================================"

# 检查参数
if [ "$#" -ne 1 ]; then
    echo "用法: $0 <PktMask应用路径>"
    echo "例如: $0 /Users/ricky/Downloads/PktMask-macOS"
    echo ""
    echo "请提供PktMask应用文件夹的完整路径"
    exit 1
fi

APP_PATH="$1"

# 检查路径是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "❌ 错误: 路径不存在: $APP_PATH"
    exit 1
fi

# 检查是否为PktMask应用
if [ ! -f "$APP_PATH/PktMask" ]; then
    echo "❌ 错误: 在指定路径中未找到PktMask可执行文件"
    echo "请确保路径指向包含PktMask可执行文件的文件夹"
    exit 1
fi

echo "📂 找到应用路径: $APP_PATH"

# 移除隔离属性 (quarantine)
echo "🔓 正在移除应用的隔离属性..."
if xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null; then
    echo "✅ 成功移除隔离属性"
else
    echo "⚠️  隔离属性可能已经被移除或不存在"
fi

# 检查并移除其他可能的安全属性
echo "🔍 检查其他安全属性..."
QUARANTINE_ATTRS=$(xattr -l "$APP_PATH" 2>/dev/null | grep -E "(quarantine|gatekeeper)" || true)
if [ -n "$QUARANTINE_ATTRS" ]; then
    echo "发现额外的安全属性，正在移除..."
    xattr -c "$APP_PATH" 2>/dev/null
    echo "✅ 已清除所有安全属性"
fi

# 递归处理内部文件
echo "🔄 正在处理应用内部文件..."
find "$APP_PATH" -type f \( -name "*.dylib" -o -name "*.so" -o -perm +111 \) -exec xattr -c {} \; 2>/dev/null

# 设置可执行权限
echo "🔐 设置可执行权限..."
chmod +x "$APP_PATH/PktMask" 2>/dev/null

# 处理_internal目录下的Python文件
PYTHON_PATH="$APP_PATH/_internal/Python"
if [ -f "$PYTHON_PATH" ]; then
    echo "🐍 处理Python共享库..."
    xattr -c "$PYTHON_PATH" 2>/dev/null
    chmod +x "$PYTHON_PATH" 2>/dev/null
    echo "✅ Python共享库处理完成"
fi

echo ""
echo "🎉 修复完成!"
echo ""
echo "现在您可以尝试运行PktMask了。有以下几种方式："
echo ""
echo "方式1 - 直接运行:"
echo "cd '$APP_PATH' && ./PktMask"
echo ""
echo "方式2 - 双击运行:"
echo "在Finder中双击PktMask文件"
echo ""
echo "方式3 - 如果仍有问题，使用右键菜单:"
echo "在Finder中右键点击PktMask文件，选择'打开'"
echo ""

# 尝试测试运行
echo "🧪 正在测试应用是否可以启动..."
cd "$APP_PATH"
if timeout 5s ./PktMask --help >/dev/null 2>&1; then
    echo "✅ 应用可以正常启动!"
else
    echo "⚠️  应用可能需要GUI环境或额外的步骤"
    echo "请尝试上述方式手动运行"
fi

echo ""
echo "如果仍然遇到问题，请尝试以下步骤:"
echo "1. 打开'系统偏好设置' -> '安全性与隐私'"
echo "2. 在'通用'选项卡中查找关于PktMask的消息"
echo "3. 点击'仍要打开'按钮"
echo ""
echo "或者联系开发者获取已签名的版本。" 