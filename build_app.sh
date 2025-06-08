#!/bin/bash
# PktMask 应用打包脚本
# 自动化PyInstaller打包过程，包含依赖检查和错误处理

set -e  # 遇到错误时退出

echo "🚀 开始 PktMask 应用打包过程..."

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ 检测到虚拟环境: $VIRTUAL_ENV"
else
    echo "⚠️  警告: 没有检测到虚拟环境，建议在虚拟环境中打包"
fi

# 检查必要的依赖是否安装
echo "🔍 检查打包依赖..."
python -c "import PyInstaller; print('✅ PyInstaller 已安装')" 2>/dev/null || {
    echo "❌ PyInstaller 未安装，正在安装..."
    pip install pyinstaller
}

python -c "import pydantic; print('✅ Pydantic 已安装')" 2>/dev/null || {
    echo "❌ Pydantic 未安装，请运行: pip install -r requirements.txt"
    exit 1
}

python -c "import yaml; print('✅ PyYAML 已安装')" 2>/dev/null || {
    echo "❌ PyYAML 未安装，请运行: pip install -r requirements.txt"
    exit 1
}

# 清理之前的构建文件
echo "🧹 清理之前的构建文件..."
if [ -d "build" ]; then
    rm -rf build/
    echo "   已删除 build/ 目录"
fi

if [ -d "dist" ]; then
    rm -rf dist/
    echo "   已删除 dist/ 目录"
fi

# 确保钩子目录存在
if [ ! -d "hooks" ]; then
    echo "❌ 错误: hooks/ 目录不存在"
    exit 1
fi

echo "✅ hooks/ 目录存在"

# 开始打包
echo "📦 开始使用 PyInstaller 打包..."
pyinstaller PktMask.spec

# 检查打包结果
if [ -f "dist/PktMask.app/Contents/MacOS/PktMask" ]; then
    echo "✅ 打包成功！"
    echo "📍 应用位置: dist/PktMask.app"
    
    # 获取应用大小
    APP_SIZE=$(du -sh dist/PktMask.app | cut -f1)
    echo "📊 应用大小: $APP_SIZE"
    
    echo ""
    echo "🎉 打包完成！"
    echo "💡 您可以运行以下命令启动应用:"
    echo "   ./dist/PktMask.app/Contents/MacOS/PktMask"
    echo ""
    echo "💡 或者直接在 Finder 中双击 dist/PktMask.app"
    
else
    echo "❌ 打包失败！请检查错误信息"
    exit 1
fi 