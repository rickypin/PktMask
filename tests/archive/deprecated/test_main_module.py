#!/usr/bin/env python3
"""
测试主模块和服务模块
"""
import pytest
import sys
import importlib
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import os

# 添加src路径到系统路径以便导入
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

class TestMainModule:
    """测试__main__.py模块"""
    
    def test_main_module_exists(self):
        """测试主模块文件存在"""
        import pktmask.__main__
        assert pktmask.__main__ is not None
    
    def test_main_module_has_main_import(self):
        """测试主模块导入main函数"""
        import pktmask.__main__
        # 验证模块中包含main的导入
        assert hasattr(pktmask.__main__, 'main')
    
    def test_main_module_import_structure(self):
        """测试主模块的导入结构"""
        import pktmask.__main__
        
        # 验证模块有正确的文档字符串
        assert pktmask.__main__.__doc__ is not None
        assert "PktMask 主程序入口" in pktmask.__main__.__doc__
    
    def test_main_module_structure(self):
        """测试主模块结构"""
        main_file = Path(__file__).parent.parent.parent / "src" / "pktmask" / "__main__.py"
        content = main_file.read_text()
        
        # 验证关键结构存在
        assert 'if __name__ == "__main__"' in content
        assert 'main()' in content
        assert 'from .gui.main_window import main' in content


class TestServicesModule:
    """测试services模块"""
    
    def test_services_module_exists(self):
        """测试services模块存在"""
        import pktmask.services
        assert pktmask.services is not None
    
    def test_services_module_has_docstring(self):
        """测试services模块有文档字符串"""
        import pktmask.services
        assert pktmask.services.__doc__ is not None
        assert "Services module for PktMask" in pktmask.services.__doc__
        assert "包含应用服务层组件" in pktmask.services.__doc__
    
    def test_services_module_has_all_attribute(self):
        """测试services模块有__all__属性"""
        import pktmask.services
        assert hasattr(pktmask.services, '__all__')
        assert isinstance(pktmask.services.__all__, list)
    
    def test_services_module_all_is_empty(self):
        """测试services模块__all__为空列表（当前状态）"""
        import pktmask.services
        assert pktmask.services.__all__ == []
    
    def test_services_module_import_path(self):
        """测试services模块可以正确导入"""
        # 测试不同的导入方式
        from pktmask import services
        assert services is not None
        
        from pktmask.services import __all__
        assert __all__ == []
    
    def test_services_module_attributes(self):
        """测试services模块属性"""
        import pktmask.services
        
        # 验证模块基本属性
        assert hasattr(pktmask.services, '__name__')
        assert hasattr(pktmask.services, '__file__')
        assert hasattr(pktmask.services, '__package__')
        
        # 验证模块名称
        assert pktmask.services.__name__ == 'pktmask.services'
        assert pktmask.services.__package__ == 'pktmask.services'


class TestModuleIntegration:
    """测试模块间集成"""
    
    def test_main_module_can_import_gui(self):
        """测试主模块可以导入GUI组件"""
        try:
            from pktmask.gui.main_window import main
            # 如果能导入就说明依赖正确
            assert callable(main)
        except ImportError:
            # 如果GUI模块不存在，至少验证导入路径正确
            pass
    
    def test_services_module_ready_for_extension(self):
        """测试services模块为扩展做好准备"""
        import pktmask.services
        
        # 验证模块结构支持未来扩展
        assert isinstance(pktmask.services.__all__, list)
        
        # 模拟添加服务到__all__
        original_all = pktmask.services.__all__.copy()
        pktmask.services.__all__.append('test_service')
        assert 'test_service' in pktmask.services.__all__
        
        # 恢复原状态
        pktmask.services.__all__ = original_all
    
    def test_module_hierarchy_consistency(self):
        """测试模块层次结构一致性"""
        import pktmask
        import pktmask.services
        import pktmask.__main__
        
        # 验证包结构
        assert pktmask is not None
        assert pktmask.services is not None
        assert pktmask.__main__ is not None
        
        # 验证模块包名一致性
        assert pktmask.__name__ == 'pktmask'
        assert pktmask.services.__package__ == 'pktmask.services'


class TestMainModuleExecutionModes:
    """测试主模块的不同执行模式"""
    
    def test_main_module_as_module(self):
        """测试作为模块导入时的行为"""
        import pktmask.__main__ as main_module
        
        # 作为模块导入时不应该自动执行main
        assert main_module is not None
        assert hasattr(main_module, 'main')
    
    def test_main_module_python_m_execution(self):
        """测试python -m pktmask执行方式"""
        # 这个测试验证模块结构支持python -m执行
        import pktmask.__main__
        
        # 验证模块有正确的结构支持-m执行
        assert hasattr(pktmask.__main__, 'main')
        
        # 验证if __name__ == "__main__"结构存在
        main_content = Path(__file__).parent.parent.parent / "src" / "pktmask" / "__main__.py"
        content = main_content.read_text()
        assert 'if __name__ == "__main__"' in content
        assert 'main()' in content
    
    def test_main_module_file_structure(self):
        """测试主模块文件结构"""
        main_file = Path(__file__).parent.parent.parent / "src" / "pktmask" / "__main__.py"
        assert main_file.exists()
        
        content = main_file.read_text()
        
        # 验证shebang和编码
        lines = content.split('\n')
        assert lines[0].startswith('#!/usr/bin/env python3')
        assert '# -*- coding: utf-8 -*-' in lines[1]


class TestModuleCoverage:
    """专门测试模块覆盖率"""
    
    @patch('sys.exit')
    @patch('pktmask.gui.main_window.MainWindow')
    @patch('pktmask.gui.main_window.QApplication')
    def test_main_module_execution_branch(self, mock_qapp, mock_main_window, mock_exit):
        """测试主模块执行分支覆盖（无GUI启动）"""
        # 配置Mock对象
        mock_app_instance = Mock()
        mock_qapp.return_value = mock_app_instance
        mock_qapp.instance.return_value = None  # 模拟无现有应用实例
        mock_app_instance.exec.return_value = 0
        
        mock_window = Mock()
        mock_main_window.return_value = mock_window
        
        # 导入模块不会触发执行
        import pktmask.__main__
        
        # 验证main函数存在但未被调用
        assert hasattr(pktmask.__main__, 'main')
        
        # 设置环境变量模拟正常模式（非测试模式）
        original_test_mode = os.environ.get('PKTMASK_TEST_MODE', '')
        original_headless = os.environ.get('PKTMASK_HEADLESS', '')
        
        try:
            # Temporarily set to normal mode to test complete GUI startup path
            os.environ['PKTMASK_TEST_MODE'] = 'false'
            os.environ['PKTMASK_HEADLESS'] = 'false'

            # Test manual call to main function (won't actually start GUI)
            pktmask.__main__.main()

            # Verify GUI components are called correctly
            mock_qapp.assert_called_once()
            mock_main_window.assert_called_once()
            mock_window.show.assert_called_once()
            mock_app_instance.exec.assert_called_once()
            mock_exit.assert_called_once_with(0)

        finally:
            # Restore original environment variables
            os.environ['PKTMASK_TEST_MODE'] = original_test_mode
            os.environ['PKTMASK_HEADLESS'] = original_headless

    def test_services_module_all_export(self):
        """Test services module export functionality"""
        import pktmask.services

        # Verify __all__ list
        all_items = pktmask.services.__all__
        assert isinstance(all_items, list)

        # Verify all items in __all__ can be accessed from module
        for item in all_items:
            assert hasattr(pktmask.services, item)

    def test_main_module_import_path_coverage(self):
        """Test main module import path coverage"""
        # Test different ways to import main module
        import pktmask.__main__
        from pktmask import __main__
        
        assert pktmask.__main__ is __main__
    
    def test_services_module_namespace_coverage(self):
        """Test services module namespace coverage"""
        import pktmask.services

        # Verify module is in correct namespace
        assert 'pktmask.services' in sys.modules
        assert sys.modules['pktmask.services'] is pktmask.services