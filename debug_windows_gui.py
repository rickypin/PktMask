#!/usr/bin/env python3
"""
Windows GUI Event Handling Diagnostic Script for PktMask

This script specifically tests GUI event handling, signal-slot connections,
and thread management on Windows platform.

Usage:
    python debug_windows_gui.py
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path

def setup_test_environment():
    """Setup test environment and paths"""
    print("=== Setting up test environment ===")
    
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
        print(f"✓ Added to Python path: {src_path}")
    else:
        print(f"✗ Source path not found: {src_path}")
        return False
    
    return True

def test_pyqt6_imports():
    """Test PyQt6 imports and basic functionality"""
    print("\n=== Testing PyQt6 Imports ===")
    
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
        from PyQt6.QtCore import QThread, pyqtSignal, QTimer
        print("✓ PyQt6 basic imports successful")
        
        # Test QApplication creation
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        print("✓ QApplication created successfully")
        
        return True, app
        
    except ImportError as e:
        print(f"✗ PyQt6 import failed: {e}")
        return False, None
    except Exception as e:
        print(f"✗ PyQt6 initialization failed: {e}")
        return False, None

def test_pktmask_gui_imports():
    """Test PktMask GUI module imports"""
    print("\n=== Testing PktMask GUI Imports ===")
    
    modules_to_test = [
        "pktmask.gui.main_window",
        "pktmask.gui.managers.pipeline_manager",
        "pktmask.gui.managers.ui_manager",
        "pktmask.gui.managers.file_manager",
        "pktmask.core.events",
        "pktmask.services.pipeline_service"
    ]
    
    failed_imports = []
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✓ {module}")
        except Exception as e:
            print(f"✗ {module}: {e}")
            failed_imports.append((module, str(e)))
    
    return len(failed_imports) == 0, failed_imports

def create_test_window(app):
    """Create a test window to verify GUI functionality"""
    print("\n=== Creating Test Window ===")
    
    try:
        from PyQt6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QTextEdit
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class TestThread(QThread):
            progress_signal = pyqtSignal(str)
            
            def run(self):
                import time
                for i in range(5):
                    self.progress_signal.emit(f"Test progress: {i+1}/5")
                    time.sleep(0.5)
                self.progress_signal.emit("Test thread completed!")
        
        class TestWindow(QMainWindow):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("PktMask Windows GUI Test")
                self.setGeometry(100, 100, 600, 400)
                
                # Create central widget
                central_widget = QWidget()
                self.setCentralWidget(central_widget)
                layout = QVBoxLayout(central_widget)
                
                # Create test components
                self.status_label = QLabel("Ready for testing")
                self.test_button = QPushButton("Test Signal Connection")
                self.thread_button = QPushButton("Test Thread Processing")
                self.log_text = QTextEdit()
                self.log_text.setMaximumHeight(200)
                
                # Add to layout
                layout.addWidget(self.status_label)
                layout.addWidget(self.test_button)
                layout.addWidget(self.thread_button)
                layout.addWidget(self.log_text)
                
                # Connect signals
                self.test_button.clicked.connect(self.test_signal_connection)
                self.thread_button.clicked.connect(self.test_thread_processing)
                
                # Thread management
                self.test_thread = None
                
                self.log("Test window created successfully")
            
            def log(self, message):
                self.log_text.append(f"[{self.get_timestamp()}] {message}")
            
            def get_timestamp(self):
                from datetime import datetime
                return datetime.now().strftime("%H:%M:%S")
            
            def test_signal_connection(self):
                self.log("✓ Signal connection test successful!")
                self.status_label.setText("Signal connection working")
            
            def test_thread_processing(self):
                if self.test_thread and self.test_thread.isRunning():
                    self.log("Thread already running, please wait...")
                    return
                
                self.log("Starting test thread...")
                self.test_thread = TestThread()
                self.test_thread.progress_signal.connect(self.handle_thread_progress)
                self.test_thread.finished.connect(self.handle_thread_finished)
                self.test_thread.start()
                
                self.thread_button.setEnabled(False)
                self.status_label.setText("Thread processing...")
            
            def handle_thread_progress(self, message):
                self.log(f"Thread: {message}")
            
            def handle_thread_finished(self):
                self.log("✓ Thread processing completed!")
                self.thread_button.setEnabled(True)
                self.status_label.setText("Thread test completed")
        
        window = TestWindow()
        print("✓ Test window created successfully")
        return window
        
    except Exception as e:
        print(f"✗ Failed to create test window: {e}")
        traceback.print_exc()
        return None

def test_pktmask_main_window():
    """Test PktMask main window creation"""
    print("\n=== Testing PktMask Main Window ===")
    
    try:
        # Set test mode to avoid full initialization
        os.environ['PKTMASK_TEST_MODE'] = 'true'
        
        from pktmask.gui.main_window import MainWindow
        
        print("Attempting to create MainWindow...")
        window = MainWindow()
        print("✓ MainWindow created successfully")
        
        # Test key attributes
        required_attrs = [
            'start_proc_btn', 'dir_path_label', 'output_path_label',
            'anonymize_ips_cb', 'remove_dupes_cb', 'mask_payloads_cb',
            'pipeline_manager', 'file_manager', 'ui_manager'
        ]
        
        missing_attrs = []
        for attr in required_attrs:
            if not hasattr(window, attr):
                missing_attrs.append(attr)
            else:
                print(f"✓ {attr} exists")
        
        if missing_attrs:
            print(f"✗ Missing attributes: {missing_attrs}")
            return False, None
        
        # Test signal connections
        try:
            # Check if start button is connected
            if hasattr(window.start_proc_btn, 'clicked'):
                print("✓ Start button has clicked signal")
            else:
                print("✗ Start button missing clicked signal")
                return False, None
            
            # Test pipeline manager
            if hasattr(window.pipeline_manager, 'toggle_pipeline_processing'):
                print("✓ Pipeline manager has toggle_pipeline_processing method")
            else:
                print("✗ Pipeline manager missing toggle_pipeline_processing method")
                return False, None
            
        except Exception as e:
            print(f"✗ Signal connection test failed: {e}")
            return False, None
        
        return True, window
        
    except Exception as e:
        print(f"✗ Failed to create PktMask main window: {e}")
        traceback.print_exc()
        return False, None
    finally:
        # Clean up test mode
        if 'PKTMASK_TEST_MODE' in os.environ:
            del os.environ['PKTMASK_TEST_MODE']

def test_button_click_simulation(window):
    """Test simulated button click on PktMask window"""
    print("\n=== Testing Button Click Simulation ===")
    
    try:
        # Create a temporary test directory with PCAP file
        with tempfile.TemporaryDirectory(prefix="pktmask_gui_test_") as temp_dir:
            # Create test PCAP file
            test_pcap = os.path.join(temp_dir, "test.pcap")
            pcap_header = bytes([
                0xD4, 0xC3, 0xB2, 0xA1,  # Magic number
                0x02, 0x00, 0x04, 0x00,  # Version
                0x00, 0x00, 0x00, 0x00,  # Timezone
                0x00, 0x00, 0x00, 0x00,  # Timestamp accuracy
                0xFF, 0xFF, 0x00, 0x00,  # Max packet length
                0x01, 0x00, 0x00, 0x00   # Data link type
            ])
            
            with open(test_pcap, 'wb') as f:
                f.write(pcap_header)
            
            print(f"✓ Created test PCAP file: {test_pcap}")
            
            # Set up window state
            window.base_dir = temp_dir
            window.anonymize_ips_cb.setChecked(True)  # Enable at least one option
            
            print("✓ Window state configured")
            
            # Test button state
            window.ui_manager._update_start_button_state()
            button_enabled = window.start_proc_btn.isEnabled()
            print(f"Button enabled: {button_enabled}")
            
            if not button_enabled:
                print("✗ Start button is not enabled")
                return False
            
            # Simulate button click
            print("Simulating button click...")
            try:
                window.start_proc_btn.clicked.emit()
                print("✓ Button click signal emitted successfully")
                
                # Check if processing started
                import time
                time.sleep(0.1)  # Give time for signal processing
                
                # Check thread state
                thread = getattr(window.pipeline_manager, 'processing_thread', None)
                if thread:
                    print(f"✓ Processing thread created: {thread}")
                    print(f"  - Thread running: {thread.isRunning()}")
                else:
                    print("✗ No processing thread created")
                    return False
                
                return True
                
            except Exception as e:
                print(f"✗ Button click simulation failed: {e}")
                traceback.print_exc()
                return False
    
    except Exception as e:
        print(f"✗ Button click test setup failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Main diagnostic function"""
    print("PktMask Windows GUI Diagnostic Tool")
    print("=" * 50)
    
    # Setup environment
    if not setup_test_environment():
        return 1
    
    # Test PyQt6
    pyqt_ok, app = test_pyqt6_imports()
    if not pyqt_ok:
        print("✗ PyQt6 test failed")
        return 1
    
    # Test PktMask GUI imports
    imports_ok, failed_imports = test_pktmask_gui_imports()
    if not imports_ok:
        print(f"✗ PktMask GUI import failures: {len(failed_imports)}")
        for module, error in failed_imports:
            print(f"  - {module}: {error}")
        return 1
    
    # Create test window
    test_window = create_test_window(app)
    if test_window:
        print("✓ Basic GUI test window created successfully")
        test_window.show()
    else:
        print("✗ Failed to create basic test window")
        return 1
    
    # Test PktMask main window
    pktmask_ok, pktmask_window = test_pktmask_main_window()
    if not pktmask_ok:
        print("✗ PktMask main window test failed")
        return 1
    
    # Test button click simulation
    if not test_button_click_simulation(pktmask_window):
        print("✗ Button click simulation failed")
        return 1
    
    print("\n" + "=" * 50)
    print("✓ All GUI tests passed successfully!")
    print("\nTest window is displayed. You can:")
    print("1. Click 'Test Signal Connection' to verify signal handling")
    print("2. Click 'Test Thread Processing' to verify thread management")
    print("3. Close the window when done")
    
    # Run event loop for interactive testing
    if app:
        print("\nStarting GUI event loop for interactive testing...")
        app.exec()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
