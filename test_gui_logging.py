#!/usr/bin/env python3
"""
Simple GUI test to verify logging functionality
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_gui_logging():
    """Test GUI logging functionality"""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        
        # Create QApplication
        app = QApplication(sys.argv)
        
        # Import GUI components
        from pktmask.gui.main_window import MainWindow
        
        # Create main window
        window = MainWindow()
        window.show()
        
        # Test log updates
        def add_test_logs():
            window.update_log("🧪 GUI Logging Test Started")
            window.update_log("📝 This is a test log message")
            window.update_log("✅ If you can see this, GUI logging is working")
            window.update_log("❌ This is an error message test")
            window.update_log("⚠️ This is a warning message test")
            
            # Test different log levels
            for i in range(5):
                window.update_log(f"📊 Test message {i+1}/5")
        
        # Add logs after a short delay
        QTimer.singleShot(1000, add_test_logs)
        
        # Show instructions
        print("=" * 60)
        print("GUI Logging Test")
        print("=" * 60)
        print("1. A PktMask window should have opened")
        print("2. Check the Log panel for test messages")
        print("3. You should see colorful emoji messages")
        print("4. Close the window when done testing")
        print("=" * 60)
        
        # Run the application
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"❌ GUI import failed: {e}")
        print("This is expected if PyQt6 is not installed or GUI dependencies are missing")
    except Exception as e:
        print(f"❌ GUI test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gui_logging()
