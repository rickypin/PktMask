#!/usr/bin/env python3
"""
Windows Platform Specific Fixes for PktMask

This module contains fixes for Windows-specific issues identified during diagnosis.
"""

import os
import sys
import platform
from pathlib import Path
from typing import Optional, List

def apply_windows_fixes():
    """Apply all Windows-specific fixes"""
    if platform.system() != "Windows":
        print("Not running on Windows, skipping Windows-specific fixes")
        return
    
    print("Applying Windows-specific fixes...")
    
    # Fix 1: Path normalization
    apply_path_normalization_fix()
    
    # Fix 2: Directory creation permissions
    apply_directory_creation_fix()
    
    # Fix 3: File dialog improvements
    apply_file_dialog_fix()
    
    # Fix 4: Thread handling improvements
    apply_thread_handling_fix()
    
    print("Windows-specific fixes applied successfully")

def apply_path_normalization_fix():
    """Fix path normalization issues on Windows"""
    print("Applying path normalization fix...")
    
    # Patch file_ops.py safe_join function
    try:
        import pktmask.utils.file_ops as file_ops
        
        original_safe_join = file_ops.safe_join
        
        def windows_safe_join(*paths) -> str:
            """Windows-compatible path joining"""
            # Use pathlib for cross-platform compatibility
            result = Path(*[str(p) for p in paths if p])
            # Normalize path separators for Windows
            return str(result).replace('/', os.sep)
        
        file_ops.safe_join = windows_safe_join
        print("✓ Path normalization fix applied")
        
    except Exception as e:
        print(f"✗ Failed to apply path normalization fix: {e}")

def apply_directory_creation_fix():
    """Fix directory creation permission issues on Windows"""
    print("Applying directory creation fix...")
    
    try:
        import pktmask.utils.file_ops as file_ops
        
        original_ensure_directory = file_ops.ensure_directory
        
        def windows_ensure_directory(path, create_if_missing: bool = True) -> bool:
            """Windows-compatible directory creation"""
            path = Path(path)
            
            if path.exists():
                if not path.is_dir():
                    raise file_ops.FileError(f"Path exists but is not a directory: {path}", file_path=str(path))
                return True
            
            if create_if_missing:
                try:
                    # Use more permissive creation on Windows
                    path.mkdir(parents=True, exist_ok=True, mode=0o755)
                    print(f"Created directory: {path}")
                    return True
                except PermissionError as e:
                    # Try alternative approach for Windows
                    try:
                        os.makedirs(str(path), exist_ok=True)
                        print(f"Created directory (fallback): {path}")
                        return True
                    except Exception as fallback_e:
                        raise file_ops.FileError(f"Failed to create directory: {path}", file_path=str(path)) from fallback_e
                except Exception as e:
                    raise file_ops.FileError(f"Failed to create directory: {path}", file_path=str(path)) from e
            
            return False
        
        file_ops.ensure_directory = windows_ensure_directory
        print("✓ Directory creation fix applied")
        
    except Exception as e:
        print(f"✗ Failed to apply directory creation fix: {e}")

def apply_file_dialog_fix():
    """Fix file dialog issues on Windows"""
    print("Applying file dialog fix...")
    
    try:
        # Patch file manager to use Windows-specific dialog options
        import pktmask.gui.managers.file_manager as file_manager_module
        
        # Get the FileManager class
        FileManager = file_manager_module.FileManager
        
        original_choose_folder = FileManager.choose_folder
        
        def windows_choose_folder(self):
            """Windows-compatible folder selection"""
            from PyQt6.QtWidgets import QFileDialog
            
            # Use native Windows dialog with specific options
            options = QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
            
            dir_path = QFileDialog.getExistingDirectory(
                self.main_window,
                "Select Input Folder",
                self.main_window.last_opened_dir,
                options=options
            )
            
            if dir_path:
                # Normalize path for Windows
                dir_path = str(Path(dir_path).resolve())
                
                self.main_window.base_dir = dir_path
                self.main_window.last_opened_dir = dir_path
                self.main_window.dir_path_label.setText(os.path.basename(dir_path))

                # Auto-generate default output path
                self.generate_default_output_path()
                self.main_window.ui_manager._update_start_button_state()

                self._logger.info(f"Selected input directory: {dir_path}")
        
        FileManager.choose_folder = windows_choose_folder
        print("✓ File dialog fix applied")
        
    except Exception as e:
        print(f"✗ Failed to apply file dialog fix: {e}")

def apply_thread_handling_fix():
    """Fix thread handling issues on Windows"""
    print("Applying thread handling fix...")
    
    try:
        # Patch ServicePipelineThread for better Windows compatibility
        import pktmask.gui.main_window as main_window_module
        
        ServicePipelineThread = main_window_module.ServicePipelineThread
        
        original_run = ServicePipelineThread.run
        
        def windows_run(self):
            """Windows-compatible thread execution"""
            try:
                # Add Windows-specific thread initialization
                if platform.system() == "Windows":
                    # Set thread priority for better responsiveness
                    import threading
                    current_thread = threading.current_thread()
                    if hasattr(current_thread, 'setDaemon'):
                        current_thread.setDaemon(True)
                
                # Call original run method
                original_run(self)
                
            except Exception as e:
                from pktmask.services.pipeline_service import PipelineServiceError
                from pktmask.core.events import PipelineEvents
                
                error_msg = f"Windows thread execution error: {str(e)}"
                
                if isinstance(e, PipelineServiceError):
                    self.progress_signal.emit(PipelineEvents.ERROR, {'message': str(e)})
                else:
                    self.progress_signal.emit(PipelineEvents.ERROR, {'message': error_msg})
        
        ServicePipelineThread.run = windows_run
        print("✓ Thread handling fix applied")
        
    except Exception as e:
        print(f"✗ Failed to apply thread handling fix: {e}")

def create_windows_diagnostic_report():
    """Create a diagnostic report for Windows platform"""
    print("\n=== Windows Platform Diagnostic Report ===")
    
    print(f"Platform: {platform.platform()}")
    print(f"Python version: {sys.version}")
    print(f"Architecture: {platform.architecture()}")
    
    # Check PyQt6 version
    try:
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        print(f"Qt version: {QT_VERSION_STR}")
        print(f"PyQt6 version: {PYQT_VERSION_STR}")
    except ImportError:
        print("PyQt6 not available")
    
    # Check file system permissions
    temp_dir = Path.cwd() / "temp_test"
    try:
        temp_dir.mkdir(exist_ok=True)
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        test_file.unlink()
        temp_dir.rmdir()
        print("✓ File system permissions: OK")
    except Exception as e:
        print(f"✗ File system permissions: {e}")
    
    # Check available disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(Path.cwd())
        print(f"Disk space: {free // (1024**3)} GB free of {total // (1024**3)} GB total")
    except Exception as e:
        print(f"✗ Disk space check failed: {e}")

def main():
    """Main function to apply Windows fixes"""
    print("PktMask Windows Platform Fixes")
    print("=" * 40)
    
    # Create diagnostic report
    create_windows_diagnostic_report()
    
    # Apply fixes if on Windows
    if platform.system() == "Windows":
        apply_windows_fixes()
    else:
        print("\nRunning diagnostic on non-Windows platform for testing purposes")
        print("Fixes would be applied if running on Windows")
    
    print("\n" + "=" * 40)
    print("Windows platform fixes completed")

if __name__ == "__main__":
    main()
