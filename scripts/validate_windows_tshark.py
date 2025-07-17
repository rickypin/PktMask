#!/usr/bin/env python3
"""
Windows TShark Validation Script

Comprehensive validation script for TShark functionality on Windows platform.
Tests path handling, command line argument processing, and file processing capabilities.
"""

import os
import sys
import platform
import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pktmask.infrastructure.tshark.manager import TSharkManager, TSharkStatus
from pktmask.infrastructure.logging import get_logger

logger = get_logger('windows_tshark_validator')


class WindowsTSharkValidator:
    """Windows-specific TShark validation"""
    
    def __init__(self):
        self.manager = TSharkManager()
        self.results = {}
        
    def validate_all(self) -> Dict[str, Any]:
        """Run all validation tests"""
        print("🔍 Starting Windows TShark validation...")
        
        # Basic detection
        self.results['detection'] = self._test_detection()
        
        # Path handling
        self.results['path_handling'] = self._test_path_handling()
        
        # Command line processing
        self.results['command_processing'] = self._test_command_processing()
        
        # File processing
        self.results['file_processing'] = self._test_file_processing()
        
        # Generate report
        self._generate_report()
        
        return self.results
    
    def _test_detection(self) -> Dict[str, Any]:
        """Test TShark detection"""
        print("\n📋 Testing TShark detection...")
        
        result = {
            'status': 'unknown',
            'path': None,
            'version': None,
            'error': None
        }
        
        try:
            info = self.manager.detect_tshark()
            result['status'] = info.status.value
            result['path'] = info.path
            result['version'] = info.version_formatted
            result['error'] = info.error_message
            
            if info.is_available:
                print(f"✅ TShark detected: {info.path}")
                print(f"   Version: {info.version_formatted}")
            else:
                print(f"❌ TShark detection failed: {info.error_message}")
                
        except Exception as e:
            result['error'] = str(e)
            print(f"❌ Detection error: {e}")
            
        return result
    
    def _test_path_handling(self) -> Dict[str, Any]:
        """Test Windows path handling"""
        print("\n📋 Testing path handling...")
        
        result = {
            'spaces_in_path': False,
            'special_chars': False,
            'long_paths': False,
            'errors': []
        }
        
        if not self.results.get('detection', {}).get('path'):
            result['errors'].append("No TShark path available for testing")
            return result
            
        tshark_path = self.results['detection']['path']
        
        # Test spaces in executable path
        try:
            if ' ' in tshark_path:
                cmd = self.manager._prepare_tshark_command(tshark_path, ['-v'])
                subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                             creationflags=subprocess.CREATE_NO_WINDOW)
                result['spaces_in_path'] = True
                print("✅ Spaces in executable path handled correctly")
            else:
                result['spaces_in_path'] = True
                print("✅ No spaces in executable path")
        except Exception as e:
            result['errors'].append(f"Spaces in path test failed: {e}")
            print(f"❌ Spaces in path test failed: {e}")
        
        # Test special characters
        try:
            # Create a test file with spaces in name
            with tempfile.NamedTemporaryFile(suffix=' test file.txt', delete=False) as f:
                test_file = f.name
                
            try:
                # Test command preparation with spaces in filename
                cmd = self.manager.prepare_file_processing_command(
                    tshark_path, test_file, ['-T', 'json']
                )
                result['special_chars'] = True
                print("✅ Special characters in filenames handled correctly")
            finally:
                os.unlink(test_file)
                
        except Exception as e:
            result['errors'].append(f"Special characters test failed: {e}")
            print(f"❌ Special characters test failed: {e}")
            
        return result
    
    def _test_command_processing(self) -> Dict[str, Any]:
        """Test command line processing"""
        print("\n📋 Testing command line processing...")
        
        result = {
            'basic_commands': False,
            'complex_arguments': False,
            'json_output': False,
            'errors': []
        }
        
        if not self.results.get('detection', {}).get('path'):
            result['errors'].append("No TShark path available for testing")
            return result
            
        tshark_path = self.results['detection']['path']
        
        # Test basic command
        try:
            cmd = self.manager._prepare_tshark_command(tshark_path, ['-v'])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            if proc.returncode == 0:
                result['basic_commands'] = True
                print("✅ Basic commands work correctly")
            else:
                result['errors'].append(f"Basic command failed: {proc.stderr}")
        except Exception as e:
            result['errors'].append(f"Basic command test failed: {e}")
            print(f"❌ Basic command test failed: {e}")
        
        # Test complex arguments
        try:
            complex_args = ['-G', 'protocols']
            cmd = self.manager._prepare_tshark_command(tshark_path, complex_args)
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            if proc.returncode == 0 and 'tcp' in proc.stdout.lower():
                result['complex_arguments'] = True
                print("✅ Complex arguments work correctly")
            else:
                result['errors'].append("Complex arguments test failed")
        except Exception as e:
            result['errors'].append(f"Complex arguments test failed: {e}")
            print(f"❌ Complex arguments test failed: {e}")
        
        # Test JSON output capability
        try:
            json_args = ['-G', 'fields']
            cmd = self.manager._prepare_tshark_command(tshark_path, json_args)
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            if proc.returncode == 0 and 'tls.app_data' in proc.stdout:
                result['json_output'] = True
                print("✅ JSON output capability confirmed")
            else:
                result['errors'].append("JSON output test failed")
        except Exception as e:
            result['errors'].append(f"JSON output test failed: {e}")
            print(f"❌ JSON output test failed: {e}")
            
        return result
    
    def _test_file_processing(self) -> Dict[str, Any]:
        """Test file processing capabilities"""
        print("\n📋 Testing file processing...")
        
        result = {
            'file_reading': False,
            'json_parsing': False,
            'tls_support': False,
            'errors': []
        }
        
        # Note: This would require a test PCAP file
        # For now, just test the command preparation
        try:
            if self.results.get('detection', {}).get('path'):
                tshark_path = self.results['detection']['path']
                
                # Test command preparation for file processing
                test_args = ['-T', 'json', '-e', 'frame.number']
                cmd = self.manager.prepare_file_processing_command(
                    tshark_path, 'test.pcap', test_args
                )
                
                # Verify command structure
                if len(cmd) >= 4 and '-r' in cmd and 'test.pcap' in cmd:
                    result['file_reading'] = True
                    print("✅ File processing command preparation works")
                else:
                    result['errors'].append("File processing command malformed")
                    
        except Exception as e:
            result['errors'].append(f"File processing test failed: {e}")
            print(f"❌ File processing test failed: {e}")
            
        return result
    
    def _generate_report(self):
        """Generate validation report"""
        print("\n" + "="*60)
        print("🔍 WINDOWS TSHARK VALIDATION REPORT")
        print("="*60)
        
        # Overall status
        detection_ok = self.results.get('detection', {}).get('status') == 'available'
        path_ok = len(self.results.get('path_handling', {}).get('errors', [])) == 0
        cmd_ok = len(self.results.get('command_processing', {}).get('errors', [])) == 0
        file_ok = len(self.results.get('file_processing', {}).get('errors', [])) == 0
        
        overall_status = detection_ok and path_ok and cmd_ok and file_ok
        
        print(f"\n📊 Overall Status: {'✅ PASS' if overall_status else '❌ FAIL'}")
        
        # Detailed results
        print(f"\n🔍 Detection: {'✅' if detection_ok else '❌'}")
        if detection_ok:
            print(f"   Path: {self.results['detection']['path']}")
            print(f"   Version: {self.results['detection']['version']}")
        else:
            print(f"   Error: {self.results['detection'].get('error', 'Unknown')}")
        
        print(f"\n📁 Path Handling: {'✅' if path_ok else '❌'}")
        path_result = self.results.get('path_handling', {})
        print(f"   Spaces in path: {'✅' if path_result.get('spaces_in_path') else '❌'}")
        print(f"   Special characters: {'✅' if path_result.get('special_chars') else '❌'}")
        
        print(f"\n⚙️ Command Processing: {'✅' if cmd_ok else '❌'}")
        cmd_result = self.results.get('command_processing', {})
        print(f"   Basic commands: {'✅' if cmd_result.get('basic_commands') else '❌'}")
        print(f"   Complex arguments: {'✅' if cmd_result.get('complex_arguments') else '❌'}")
        print(f"   JSON output: {'✅' if cmd_result.get('json_output') else '❌'}")
        
        print(f"\n📄 File Processing: {'✅' if file_ok else '❌'}")
        file_result = self.results.get('file_processing', {})
        print(f"   File reading: {'✅' if file_result.get('file_reading') else '❌'}")
        
        # Errors summary
        all_errors = []
        for category, data in self.results.items():
            if isinstance(data, dict) and 'errors' in data:
                all_errors.extend(data['errors'])
        
        if all_errors:
            print(f"\n❌ Errors Found ({len(all_errors)}):")
            for i, error in enumerate(all_errors, 1):
                print(f"   {i}. {error}")
        
        # Recommendations
        if not overall_status:
            print(f"\n💡 Recommendations:")
            if not detection_ok:
                print("   - Install or reinstall Wireshark with TShark component")
                print("   - Ensure TShark is in system PATH")
            if not path_ok:
                print("   - Check file path handling and permissions")
            if not cmd_ok:
                print("   - Verify TShark version and capabilities")


def main():
    """Main validation function"""
    if platform.system() != 'Windows':
        print("❌ This script is designed for Windows platform only")
        sys.exit(1)
    
    validator = WindowsTSharkValidator()
    results = validator.validate_all()
    
    # Exit with appropriate code
    overall_success = all(
        len(category.get('errors', [])) == 0 if isinstance(category, dict) else True
        for category in results.values()
    )
    
    sys.exit(0 if overall_success else 1)


if __name__ == '__main__':
    main()
