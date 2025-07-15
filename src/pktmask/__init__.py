"""
PktMask - IP Address Replacement Tool
"""

__version__ = "0.1.0" 

# ---------------------------------------------------------------------------
# Optional runtime stub for PyQt6 (used by limited unit-tests).
# The real GUI version depends on actual PyQt6; but can be missing in CI / headless environments.
# We inject a minimal placeholder module on import failure to avoid ImportError.
# ---------------------------------------------------------------------------
import sys
import types

if "PyQt6" not in sys.modules:
    try:
        import importlib
        importlib.import_module("PyQt6")  # noqa: F401
    except ModuleNotFoundError:
        # 构造占位模块结构: PyQt6, PyQt6.QtCore, PyQt6.QtWidgets, PyQt6.QtGui
        pyqt6_stub = types.ModuleType("PyQt6")

        qtcore_stub = types.ModuleType("PyQt6.QtCore")
        qtwidgets_stub = types.ModuleType("PyQt6.QtWidgets")
        qtgui_stub = types.ModuleType("PyQt6.QtGui")

        # ---- QtCore minimal stubs ----
        class _QTime:  # noqa: D401
            def __init__(self, *args, **kwargs):
                pass

            def __repr__(self):
                return "<stub QTime>"

        def _dummy(*_a, **_kw):  # placeholder for pyqtSignal/slots
            return lambda *a, **kw: None

        qtcore_stub.QTime = _QTime
        qtcore_stub.pyqtSignal = _dummy
        qtcore_stub.Qt = object  # generic placeholder
        qtcore_stub.QThread = object
        qtcore_stub.QTimer = object
        qtcore_stub.QEvent = object
        qtcore_stub.QObject = object
        qtcore_stub.QPropertyAnimation = object
        qtcore_stub.QEasingCurve = object

        # ---- QtWidgets minimal stubs ----
        qtwidgets_stub.QApplication = object
        qtwidgets_stub.QFileDialog = object
        qtwidgets_stub.QMessageBox = object
        qtwidgets_stub.QAction = object

        # ---- QtGui minimal stubs ----
        qtgui_stub.QFont = object
        qtgui_stub.QIcon = object
        qtgui_stub.QTextCursor = object
        qtgui_stub.QFontMetrics = object
        qtgui_stub.QColor = object

        # 注册到sys.modules
        sys.modules.update({
            "PyQt6": pyqt6_stub,
            "PyQt6.QtCore": qtcore_stub,
            "PyQt6.QtWidgets": qtwidgets_stub,
            "PyQt6.QtGui": qtgui_stub,
        })

        # 还需要让主包引用子模块
        pyqt6_stub.QtCore = qtcore_stub
        pyqt6_stub.QtWidgets = qtwidgets_stub
        pyqt6_stub.QtGui = qtgui_stub 