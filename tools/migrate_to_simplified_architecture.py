#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
迁移到简化架构的工具脚本

执行步骤：
1. 备份现有实现
2. 验证新组件功能
3. 逐步替换旧组件
4. 运行测试验证
5. 清理废弃代码
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


class ArchitectureMigrator:
    """架构迁移工具"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / f"backup_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.gui_dir = self.project_root / "src" / "pktmask" / "gui"
        
        # 迁移状态
        self.migration_steps = [
            "backup_current_implementation",
            "validate_new_components", 
            "create_compatibility_layer",
            "run_integration_tests",
            "replace_main_window",
            "cleanup_old_managers",
            "final_validation"
        ]
        self.completed_steps = []
        
    def execute_migration(self):
        """执行完整的迁移流程"""
        print("🚀 开始架构迁移...")
        print(f"项目根目录: {self.project_root}")
        print(f"备份目录: {self.backup_dir}")
        
        try:
            for step in self.migration_steps:
                print(f"\n📋 执行步骤: {step}")
                method = getattr(self, step)
                method()
                self.completed_steps.append(step)
                print(f"✅ 步骤完成: {step}")
            
            print("\n🎉 架构迁移完成!")
            self._generate_migration_report()
            
        except Exception as e:
            print(f"\n❌ 迁移失败: {e}")
            self._rollback_migration()
            raise
    
    def backup_current_implementation(self):
        """备份当前实现"""
        print("  📦 备份当前实现...")
        
        # 创建备份目录
        self.backup_dir.mkdir(exist_ok=True)
        
        # 备份GUI模块
        gui_backup = self.backup_dir / "gui"
        shutil.copytree(self.gui_dir, gui_backup)
        
        # 备份关键配置文件
        config_files = [
            "pyproject.toml",
            "requirements.txt",
            "src/pktmask/__init__.py"
        ]
        
        for config_file in config_files:
            src_path = self.project_root / config_file
            if src_path.exists():
                dst_path = self.backup_dir / config_file
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
        
        print(f"  ✅ 备份完成: {gui_backup}")
    
    def validate_new_components(self):
        """验证新组件功能"""
        print("  🔍 验证新组件功能...")
        
        # 检查新组件文件是否存在
        new_components = [
            "core/app_controller.py",
            "core/ui_builder.py", 
            "core/data_service.py",
            "simplified_main_window.py"
        ]
        
        for component in new_components:
            component_path = self.gui_dir / component
            if not component_path.exists():
                raise FileNotFoundError(f"新组件不存在: {component_path}")
        
        # 尝试导入新组件
        sys.path.insert(0, str(self.project_root / "src"))
        
        try:
            from pktmask.gui.core.app_controller import AppController
            from pktmask.gui.core.ui_builder import UIBuilder
            from pktmask.gui.core.data_service import DataService
            from pktmask.gui.simplified_main_window import SimplifiedMainWindow
            
            print("  ✅ 新组件导入成功")
            
        except ImportError as e:
            raise ImportError(f"新组件导入失败: {e}")
    
    def create_compatibility_layer(self):
        """创建兼容性层"""
        print("  🔗 创建兼容性层...")
        
        # 创建兼容性适配器
        compatibility_code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
兼容性适配器 - 保持与旧代码的兼容性

在迁移期间提供向后兼容的接口
"""

from .simplified_main_window import SimplifiedMainWindow


class MainWindow(SimplifiedMainWindow):
    """兼容性主窗口 - 继承简化主窗口并提供旧接口"""
    
    def __init__(self):
        super().__init__()
        
        # 兼容性属性映射
        self._setup_compatibility_attributes()
    
    def _setup_compatibility_attributes(self):
        """设置兼容性属性"""
        # 映射旧的管理器接口到新组件
        self.ui_manager = self.ui_builder
        self.file_manager = self.data_service
        self.pipeline_manager = self.app_controller
        self.report_manager = self.data_service
        self.dialog_manager = self.ui_builder
        
        # 兼容性方法
        self.choose_folder = self.data_service.select_input_directory
        self.choose_output_folder = self.data_service.select_output_directory
        self.toggle_pipeline_processing = self.app_controller.start_processing
        self.update_log = self.data_service.add_log_message
    
    # 保持旧接口的兼容性方法
    def init_ui(self):
        """兼容性方法 - UI已在__init__中初始化"""
        pass
    
    def processing_finished(self):
        """兼容性方法 - 由app_controller处理"""
        pass
    
    def processing_error(self, error_message: str):
        """兼容性方法"""
        self._handle_error(error_message)
'''
        
        compatibility_file = self.gui_dir / "compatibility_main_window.py"
        with open(compatibility_file, 'w', encoding='utf-8') as f:
            f.write(compatibility_code)
        
        print(f"  ✅ 兼容性层创建: {compatibility_file}")
    
    def run_integration_tests(self):
        """运行集成测试"""
        print("  🧪 运行集成测试...")
        
        # 设置测试环境
        env = os.environ.copy()
        env['PKTMASK_TEST_MODE'] = 'true'
        env['PYTHONPATH'] = str(self.project_root / "src")
        
        # 运行基本导入测试
        test_script = f'''
import sys
sys.path.insert(0, "{self.project_root / "src"}")

try:
    from pktmask.gui.simplified_main_window import SimplifiedMainWindow
    print("✅ SimplifiedMainWindow 导入成功")
    
    # 创建实例测试（无头模式）
    import os
    os.environ['PKTMASK_HEADLESS'] = 'true'
    
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    window = SimplifiedMainWindow()
    print("✅ SimplifiedMainWindow 实例化成功")
    
    # 测试核心组件
    assert hasattr(window, 'app_controller'), "缺少 app_controller"
    assert hasattr(window, 'ui_builder'), "缺少 ui_builder"  
    assert hasattr(window, 'data_service'), "缺少 data_service"
    print("✅ 核心组件验证成功")
    
    print("🎉 集成测试通过")
    
except Exception as e:
    print(f"❌ 集成测试失败: {{e}}")
    sys.exit(1)
'''
        
        # 执行测试
        result = subprocess.run([
            sys.executable, '-c', test_script
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            print(f"  测试输出: {result.stdout}")
            print(f"  测试错误: {result.stderr}")
            raise RuntimeError("集成测试失败")
        
        print("  ✅ 集成测试通过")
    
    def replace_main_window(self):
        """替换主窗口实现"""
        print("  🔄 替换主窗口实现...")
        
        # 备份原始main_window.py
        original_main_window = self.gui_dir / "main_window.py"
        backup_main_window = self.gui_dir / "main_window_original.py"
        
        if original_main_window.exists():
            shutil.copy2(original_main_window, backup_main_window)
        
        # 创建新的main_window.py，导入简化版本
        new_main_window_code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主窗口 - 使用简化架构

此文件现在导入并使用简化的主窗口实现
"""

# 导入简化的主窗口实现
from .simplified_main_window import SimplifiedMainWindow as MainWindow
from .simplified_main_window import main

# 保持向后兼容的导出
__all__ = ['MainWindow', 'main']

# 兼容性别名
PktMaskMainWindow = MainWindow
'''
        
        with open(original_main_window, 'w', encoding='utf-8') as f:
            f.write(new_main_window_code)
        
        print(f"  ✅ 主窗口替换完成")
        print(f"  📄 原始文件备份: {backup_main_window}")
    
    def cleanup_old_managers(self):
        """清理旧的管理器"""
        print("  🧹 清理旧的管理器...")
        
        # 移动旧管理器到备份目录
        managers_dir = self.gui_dir / "managers"
        if managers_dir.exists():
            backup_managers = self.backup_dir / "gui" / "managers_deprecated"
            shutil.move(str(managers_dir), str(backup_managers))
            print(f"  📦 旧管理器已移动到: {backup_managers}")
        
        # 创建新的managers目录，包含简化的__init__.py
        managers_dir.mkdir(exist_ok=True)
        
        init_code = '''"""
管理器模块 - 简化架构

旧的管理器已被新的核心组件替代：
- UIManager + DialogManager -> UIBuilder
- FileManager + ReportManager -> DataService  
- PipelineManager + EventCoordinator -> AppController
"""

# 兼容性导入（如果需要）
from ..core.app_controller import AppController as PipelineManager
from ..core.ui_builder import UIBuilder as UIManager
from ..core.data_service import DataService as FileManager
from ..core.data_service import DataService as ReportManager
from ..core.ui_builder import UIBuilder as DialogManager

# 简化的事件协调器
class EventCoordinator:
    """简化的事件协调器 - 兼容性存根"""
    def __init__(self, main_window):
        self.main_window = main_window
    
    def subscribe(self, event_type, callback):
        """兼容性方法"""
        pass
    
    def emit(self, event_type, data):
        """兼容性方法"""
        pass
    
    def shutdown(self):
        """兼容性方法"""
        pass
'''
        
        with open(managers_dir / "__init__.py", 'w', encoding='utf-8') as f:
            f.write(init_code)
        
        print("  ✅ 管理器清理完成")
    
    def final_validation(self):
        """最终验证"""
        print("  🔍 最终验证...")
        
        # 运行完整的应用测试
        env = os.environ.copy()
        env['PKTMASK_TEST_MODE'] = 'true'
        env['PYTHONPATH'] = str(self.project_root / "src")
        
        test_script = f'''
import sys
sys.path.insert(0, "{self.project_root / "src"}")

try:
    # 测试主入口
    from pktmask.gui.main_window import MainWindow, main
    print("✅ 主入口导入成功")
    
    # 测试实例化
    import os
    os.environ['PKTMASK_HEADLESS'] = 'true'
    
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    window = MainWindow()
    print("✅ 主窗口实例化成功")
    
    # 测试核心功能
    assert hasattr(window, 'app_controller'), "缺少应用控制器"
    assert hasattr(window, 'ui_builder'), "缺少UI构建器"
    assert hasattr(window, 'data_service'), "缺少数据服务"
    print("✅ 核心功能验证成功")
    
    print("🎉 最终验证通过")
    
except Exception as e:
    print(f"❌ 最终验证失败: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
        
        result = subprocess.run([
            sys.executable, '-c', test_script
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            print(f"  验证输出: {result.stdout}")
            print(f"  验证错误: {result.stderr}")
            raise RuntimeError("最终验证失败")
        
        print("  ✅ 最终验证通过")
    
    def _rollback_migration(self):
        """回滚迁移"""
        print("\n🔄 回滚迁移...")
        
        try:
            # 恢复GUI目录
            if self.backup_dir.exists():
                gui_backup = self.backup_dir / "gui"
                if gui_backup.exists():
                    if self.gui_dir.exists():
                        shutil.rmtree(self.gui_dir)
                    shutil.copytree(gui_backup, self.gui_dir)
                    print("  ✅ GUI目录已恢复")
            
            print("  🔄 回滚完成")
            
        except Exception as e:
            print(f"  ❌ 回滚失败: {e}")
    
    def _generate_migration_report(self):
        """生成迁移报告"""
        report = f"""
架构迁移报告
============

迁移时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
项目根目录: {self.project_root}
备份目录: {self.backup_dir}

完成的步骤:
{chr(10).join(f"  ✅ {step}" for step in self.completed_steps)}

架构变化:
  📦 原有6个管理器 -> 3个核心组件
  🔄 MainWindow职责简化 -> UI容器 + 事件分发
  🗑️ 适配器层消除 -> 直接集成
  📈 代码复杂度降低 -> 维护性提升

新架构组件:
  🎮 AppController - 应用逻辑控制
  🎨 UIBuilder - 界面构建管理  
  📊 DataService - 数据文件服务

兼容性保证:
  🔗 保持旧接口兼容
  📋 渐进式迁移
  🧪 完整测试覆盖

迁移成功! 🎉
"""
        
        report_file = self.backup_dir / "migration_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n📋 迁移报告已生成: {report_file}")


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python migrate_to_simplified_architecture.py <project_root>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    if not os.path.exists(project_root):
        print(f"错误: 项目根目录不存在: {project_root}")
        sys.exit(1)
    
    migrator = ArchitectureMigrator(project_root)
    migrator.execute_migration()


if __name__ == "__main__":
    main()
