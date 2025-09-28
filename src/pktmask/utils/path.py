import os
import sys


def resource_path(filename: str) -> str:
    """
    获取资源文件的绝对路径，兼容 PyInstaller 打包和开发环境，适配 Windows/macOS 路径结构
    """
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller 打包环境：资源文件在 _MEIPASS/resources/ 目录
        return os.path.join(sys._MEIPASS, "resources", filename)
    else:
        # 开发环境：资源文件在项目根目录的 config/templates/ 目录
        # 从当前文件位置向上找到项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # src/pktmask/utils -> src/pktmask -> src -> project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        templates_path = os.path.join(project_root, "config", "templates", filename)

        # 如果模板文件存在，返回该路径
        if os.path.exists(templates_path):
            return templates_path

        # 回退到原来的逻辑（兼容性）
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources"))
        return os.path.join(base_path, filename)
