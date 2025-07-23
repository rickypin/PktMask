"""
Pytest configuration and fixtures for PktMask tests
"""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_pcap_data():
    """Provide sample PCAP data for testing"""
    # This is a minimal PCAP file header + one packet
    # In a real implementation, you'd want actual PCAP data
    return b"\xd4\xc3\xb2\xa1\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\x01\x00\x00\x00"


@pytest.fixture
def mock_config():
    """Provide a mock configuration for testing"""
    return {
        "remove_dupes": {"enabled": True},
        "anonymize_ips": {"enabled": True, "method": "prefix_preserving"},
        "mask_payloads": {"enabled": True, "protocol": "tls", "mode": "enhanced"},
    }
