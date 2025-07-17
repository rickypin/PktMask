#!/usr/bin/env python3
"""
Unit tests for TShark Manager

Tests for cross-platform TShark detection, validation, and TLS functionality.
"""

import unittest
import platform
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from pktmask.infrastructure.tshark import TSharkManager, TSharkInfo, TSharkStatus
from pktmask.infrastructure.tshark.tls_validator import TLSMarkerValidator


class TestTSharkManager(unittest.TestCase):
    """Test cases for TSharkManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = TSharkManager()
    
    def test_init_default(self):
        """Test default initialization"""
        manager = TSharkManager()
        self.assertIsNone(manager.custom_path)
        self.assertEqual(manager._system, platform.system())
    
    def test_init_custom_path(self):
        """Test initialization with custom path"""
        custom_path = "/custom/tshark"
        manager = TSharkManager(custom_path=custom_path)
        self.assertEqual(manager.custom_path, custom_path)
    
    def test_platform_paths_exist(self):
        """Test that platform paths are defined"""
        current_system = platform.system()
        self.assertIn(current_system, TSharkManager.PLATFORM_PATHS)
        
        paths = TSharkManager.PLATFORM_PATHS[current_system]
        self.assertIsInstance(paths, list)
        self.assertGreater(len(paths), 0)
    
    @patch('subprocess.run')
    def test_check_tshark_path_success(self, mock_run):
        """Test successful TShark path check"""
        # Mock successful tshark -v execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "TShark (Wireshark) 4.2.0"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Mock Path.exists
        with patch('pathlib.Path.exists', return_value=True):
            info = self.manager._check_tshark_path("/usr/bin/tshark")
        
        self.assertEqual(info.status, TSharkStatus.AVAILABLE)
        self.assertEqual(info.path, "/usr/bin/tshark")
        self.assertEqual(info.version, (4, 2, 0))
    
    @patch('subprocess.run')
    def test_check_tshark_path_version_too_low(self, mock_run):
        """Test TShark path check with version too low"""
        # Mock tshark -v with old version
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "TShark (Wireshark) 3.6.0"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        with patch('pathlib.Path.exists', return_value=True):
            info = self.manager._check_tshark_path("/usr/bin/tshark")
        
        self.assertEqual(info.status, TSharkStatus.VERSION_TOO_LOW)
        self.assertEqual(info.version, (3, 6, 0))
    
    @patch('subprocess.run')
    def test_check_tshark_path_execution_error(self, mock_run):
        """Test TShark path check with execution error"""
        # Mock subprocess execution failure
        mock_run.side_effect = FileNotFoundError("Command not found")
        
        with patch('pathlib.Path.exists', return_value=True):
            info = self.manager._check_tshark_path("/nonexistent/tshark")
        
        self.assertEqual(info.status, TSharkStatus.EXECUTION_ERROR)
    
    def test_check_tshark_path_missing_file(self):
        """Test TShark path check with missing file"""
        with patch('pathlib.Path.exists', return_value=False):
            info = self.manager._check_tshark_path("/nonexistent/tshark")
        
        self.assertEqual(info.status, TSharkStatus.MISSING)
    
    def test_parse_version_valid(self):
        """Test version parsing with valid output"""
        test_cases = [
            ("TShark (Wireshark) 4.2.0", (4, 2, 0)),
            ("TShark 4.4.1", (4, 4, 1)),
            ("wireshark version 3.6.8", (3, 6, 8)),
        ]
        
        for output, expected in test_cases:
            with self.subTest(output=output):
                version = self.manager._parse_version(output)
                self.assertEqual(version, expected)
    
    def test_parse_version_invalid(self):
        """Test version parsing with invalid output"""
        invalid_outputs = [
            "No version found",
            "TShark invalid",
            "",
        ]
        
        for output in invalid_outputs:
            with self.subTest(output=output):
                version = self.manager._parse_version(output)
                self.assertIsNone(version)
    
    def test_get_installation_guide(self):
        """Test installation guide generation"""
        guide = self.manager.get_installation_guide()
        
        self.assertIsInstance(guide, dict)
        self.assertIn('platform', guide)
        self.assertIn('methods', guide)
        self.assertIn('common_paths', guide)
        
        # Check methods structure
        methods = guide.get('methods', [])
        if methods:
            method = methods[0]
            self.assertIn('name', method)
            self.assertIn('description', method)
    
    @patch('subprocess.run')
    def test_verify_tls_capabilities(self, mock_run):
        """Test TLS capabilities verification"""
        # Mock successful protocol check
        protocol_result = Mock()
        protocol_result.returncode = 0
        protocol_result.stdout = "tcp\ntls\nssl\n"
        
        # Mock successful JSON check
        json_result = Mock()
        json_result.returncode = 0
        
        # Mock successful fields check
        fields_result = Mock()
        fields_result.returncode = 0
        fields_result.stdout = "tcp.stream\ntls.record.content_type\ntls.app_data\n"
        
        # Mock successful reassembly check
        reassembly_result = Mock()
        reassembly_result.returncode = 0
        
        mock_run.side_effect = [
            protocol_result, json_result, fields_result, json_result, reassembly_result
        ]
        
        capabilities = self.manager.verify_tls_capabilities("/usr/bin/tshark")
        
        self.assertIsInstance(capabilities, dict)
        self.assertTrue(capabilities.get('tls_protocol_support', False))
        self.assertTrue(capabilities.get('json_output_support', False))
    
    @patch('subprocess.run')
    def test_verify_tls_marker_requirements(self, mock_run):
        """Test TLS marker requirements verification"""
        # Mock all successful checks
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "tcp\ntls\nssl\ntcp.stream\ntls.record.content_type\ntls.app_data\n"
        mock_run.return_value = mock_result
        
        requirements_met, missing = self.manager.verify_tls_marker_requirements("/usr/bin/tshark")
        
        # This test depends on the mocked responses, so we mainly check the structure
        self.assertIsInstance(requirements_met, bool)
        self.assertIsInstance(missing, list)
    
    def test_set_custom_path_valid(self):
        """Test setting valid custom path"""
        with patch.object(self.manager, 'detect_tshark') as mock_detect:
            mock_info = TSharkInfo(
                path="/custom/tshark",
                status=TSharkStatus.AVAILABLE,
                version=(4, 2, 0)
            )
            mock_detect.return_value = mock_info
            
            result = self.manager.set_custom_path("/custom/tshark")
            self.assertTrue(result)
            self.assertEqual(self.manager.custom_path, "/custom/tshark")
    
    def test_set_custom_path_invalid(self):
        """Test setting invalid custom path"""
        with patch.object(self.manager, 'detect_tshark') as mock_detect:
            mock_info = TSharkInfo(
                path="/custom/tshark",
                status=TSharkStatus.MISSING,
                error_message="File not found"
            )
            mock_detect.return_value = mock_info
            
            result = self.manager.set_custom_path("/custom/tshark")
            self.assertFalse(result)


class TestTLSMarkerValidator(unittest.TestCase):
    """Test cases for TLSMarkerValidator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_manager = Mock(spec=TSharkManager)
        self.validator = TLSMarkerValidator(tshark_manager=self.mock_manager)
    
    def test_init_default(self):
        """Test default initialization"""
        validator = TLSMarkerValidator()
        self.assertIsInstance(validator.tshark_manager, TSharkManager)
    
    def test_init_with_manager(self):
        """Test initialization with custom manager"""
        manager = Mock(spec=TSharkManager)
        validator = TLSMarkerValidator(tshark_manager=manager)
        self.assertEqual(validator.tshark_manager, manager)
    
    def test_validate_tls_marker_support_success(self):
        """Test successful TLS marker validation"""
        # Mock successful TShark detection
        mock_info = TSharkInfo(
            path="/usr/bin/tshark",
            status=TSharkStatus.AVAILABLE,
            version=(4, 2, 0)
        )
        self.mock_manager.detect_tshark.return_value = mock_info
        
        # Mock successful requirements check
        self.mock_manager.verify_tls_marker_requirements.return_value = (True, [])
        
        # Mock successful capabilities check
        self.mock_manager.verify_tls_capabilities.return_value = {
            'tls_protocol_support': True,
            'json_output_support': True,
        }
        
        result = self.validator.validate_tls_marker_support()
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.missing_capabilities), 0)
        self.assertEqual(len(result.error_messages), 0)
    
    def test_validate_tls_marker_support_tshark_missing(self):
        """Test TLS marker validation with missing TShark"""
        # Mock TShark not available
        mock_info = TSharkInfo(
            status=TSharkStatus.MISSING,
            error_message="TShark not found"
        )
        self.mock_manager.detect_tshark.return_value = mock_info
        
        result = self.validator.validate_tls_marker_support()
        
        self.assertFalse(result.success)
        self.assertIn('tshark_executable', result.missing_capabilities)
        self.assertGreater(len(result.error_messages), 0)
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        from pktmask.infrastructure.tshark.tls_validator import TLSValidationResult
        
        # Create mock validation result
        result = TLSValidationResult(
            success=True,
            missing_capabilities=[],
            error_messages=[],
            detailed_results={'tls_protocol_support': True},
            tshark_path="/usr/bin/tshark"
        )
        
        report = self.validator.generate_validation_report(result)
        
        self.assertIsInstance(report, str)
        self.assertIn("TLS Marker Functionality Validation Report", report)
        self.assertIn("PASSED", report)


class TestCrossPlatformIntegration(unittest.TestCase):
    """Integration tests for cross-platform functionality"""
    
    @unittest.skipIf(platform.system() not in ['Darwin', 'Windows', 'Linux'], 
                     "Unsupported platform")
    def test_platform_specific_paths(self):
        """Test platform-specific path detection"""
        manager = TSharkManager()
        current_system = platform.system()
        
        # Check that platform paths are defined
        self.assertIn(current_system, manager.PLATFORM_PATHS)
        
        paths = manager.PLATFORM_PATHS[current_system]
        self.assertIsInstance(paths, list)
        self.assertGreater(len(paths), 0)
        
        # Check path format is appropriate for platform
        for path in paths:
            if current_system == 'Windows':
                self.assertTrue(path.endswith('.exe') or '\\' in path)
            else:
                self.assertTrue(path.startswith('/'))
    
    def test_installation_guide_platform_specific(self):
        """Test that installation guide is platform-specific"""
        manager = TSharkManager()
        guide = manager.get_installation_guide()
        
        current_system = platform.system()
        expected_platform_names = {
            'Darwin': 'macOS',
            'Windows': 'Windows',
            'Linux': 'Linux'
        }
        
        if current_system in expected_platform_names:
            expected_name = expected_platform_names[current_system]
            self.assertEqual(guide.get('platform'), expected_name)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
