import os
import sys

def resource_path(filename: str) -> str:
    """
    获取资源文件的绝对路径，兼容 PyInstaller 打包和开发环境，适配 Windows/macOS 路径结构
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'resources', filename)
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources'))
    return os.path.join(base_path, filename) 