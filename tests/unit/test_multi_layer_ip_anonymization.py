"""
Unit tests for multi-layer IP anonymization functionality.

Tests the enhanced IP extraction and anonymization logic that supports
multi-layer encapsulation scenarios such as VXLAN.
"""

import pytest
from scapy.all import IP, TCP, UDP, VXLAN, Ether, IPv6

from pktmask.core.strategy import HierarchicalAnonymizationStrategy


@pytest.mark.unit
class TestMultiLayerIPExtraction:
    """Test multi-layer IP extraction functionality"""

    def test_extract_single_layer_ipv4(self):
        """Test single layer IPv4 extraction (backward compatibility)"""
        pkt = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
        strategy = HierarchicalAnonymizationStrategy()
        ips = strategy._extract_ips_from_packet(pkt)

        assert len(ips) == 1
        assert ips[0] == ("192.168.1.1", "192.168.1.2", "ipv4")

    def test_extract_single_layer_ipv6(self):
        """Test single layer IPv6 extraction (backward compatibility)"""
        pkt = Ether() / IPv6(src="2001:db8::1", dst="2001:db8::2") / TCP()
        strategy = HierarchicalAnonymizationStrategy()
        ips = strategy._extract_ips_from_packet(pkt)

        assert len(ips) == 1
        assert ips[0] == ("2001:db8::1", "2001:db8::2", "ipv6")

    def test_extract_vxlan_dual_ipv4(self):
        """Test VXLAN dual-layer IPv4 extraction"""
        pkt = (
            Ether()
            / IP(src="10.0.0.1", dst="10.0.0.2")
            / UDP(dport=4789)
            / VXLAN()
            / Ether()
            / IP(src="192.168.1.10", dst="192.168.1.20")
            / TCP()
        )

        strategy = HierarchicalAnonymizationStrategy()
        ips = strategy._extract_ips_from_packet(pkt)

        assert len(ips) == 2
        assert ("10.0.0.1", "10.0.0.2", "ipv4") in ips
        assert ("192.168.1.10", "192.168.1.20", "ipv4") in ips

    def test_extract_vxlan_ipv4_outer_ipv6_inner(self):
        """Test VXLAN with IPv4 outer and IPv6 inner"""
        pkt = (
            Ether()
            / IP(src="10.0.0.1", dst="10.0.0.2")
            / UDP(dport=4789)
            / VXLAN()
            / Ether()
            / IPv6(src="2001:db8::1", dst="2001:db8::2")
            / TCP()
        )

        strategy = HierarchicalAnonymizationStrategy()
        ips = strategy._extract_ips_from_packet(pkt)

        assert len(ips) == 2
        assert ("10.0.0.1", "10.0.0.2", "ipv4") in ips
        assert ("2001:db8::1", "2001:db8::2", "ipv6") in ips

    def test_extract_no_ip_layer(self):
        """Test packet without IP layer"""
        pkt = Ether() / TCP()
        strategy = HierarchicalAnonymizationStrategy()
        ips = strategy._extract_ips_from_packet(pkt)

        assert len(ips) == 0


@pytest.mark.unit
class TestMultiLayerIPAnonymization:
    """Test multi-layer IP anonymization functionality"""

    def test_anonymize_single_layer_ipv4(self):
        """Test single layer IPv4 anonymization (backward compatibility)"""
        pkt = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {
            "192.168.1.1": "10.0.0.1",
            "192.168.1.2": "10.0.0.2",
        }

        modified_pkt, is_modified = strategy.anonymize_packet(pkt)

        assert is_modified is True
        assert modified_pkt.getlayer(IP).src == "10.0.0.1"
        assert modified_pkt.getlayer(IP).dst == "10.0.0.2"

    def test_anonymize_single_layer_ipv6(self):
        """Test single layer IPv6 anonymization (backward compatibility)"""
        pkt = Ether() / IPv6(src="2001:db8::1", dst="2001:db8::2") / TCP()

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {
            "2001:db8::1": "2001:db8:1::1",
            "2001:db8::2": "2001:db8:1::2",
        }

        modified_pkt, is_modified = strategy.anonymize_packet(pkt)

        assert is_modified is True
        assert modified_pkt.getlayer(IPv6).src == "2001:db8:1::1"
        assert modified_pkt.getlayer(IPv6).dst == "2001:db8:1::2"

    def test_anonymize_vxlan_all_layers(self):
        """Test VXLAN all layers IPv4 anonymization"""
        pkt = (
            Ether()
            / IP(src="10.0.0.1", dst="10.0.0.2")
            / UDP(dport=4789)
            / VXLAN()
            / Ether()
            / IP(src="192.168.1.10", dst="192.168.1.20")
            / TCP()
        )

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {
            "10.0.0.1": "172.16.0.1",
            "10.0.0.2": "172.16.0.2",
            "192.168.1.10": "172.20.0.10",
            "192.168.1.20": "172.20.0.20",
        }

        modified_pkt, is_modified = strategy.anonymize_packet(pkt)

        assert is_modified is True

        # Verify outer IP layer (Scapy index starts from 1)
        outer_ip = modified_pkt.getlayer(IP, 1)
        assert outer_ip.src == "172.16.0.1"
        assert outer_ip.dst == "172.16.0.2"

        # Verify inner IP layer
        inner_ip = modified_pkt.getlayer(IP, 2)
        assert inner_ip.src == "172.20.0.10"
        assert inner_ip.dst == "172.20.0.20"

    def test_anonymize_vxlan_mixed_ip_versions(self):
        """Test VXLAN with IPv4 outer and IPv6 inner anonymization"""
        pkt = (
            Ether()
            / IP(src="10.0.0.1", dst="10.0.0.2")
            / UDP(dport=4789)
            / VXLAN()
            / Ether()
            / IPv6(src="2001:db8::1", dst="2001:db8::2")
            / TCP()
        )

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {
            "10.0.0.1": "172.16.0.1",
            "10.0.0.2": "172.16.0.2",
            "2001:db8::1": "2001:db8:1::1",
            "2001:db8::2": "2001:db8:1::2",
        }

        modified_pkt, is_modified = strategy.anonymize_packet(pkt)

        assert is_modified is True

        # Verify outer IPv4 layer (Scapy index starts from 1)
        outer_ip = modified_pkt.getlayer(IP, 1)
        assert outer_ip.src == "172.16.0.1"
        assert outer_ip.dst == "172.16.0.2"

        # Verify inner IPv6 layer
        inner_ip = modified_pkt.getlayer(IPv6, 1)
        assert inner_ip.src == "2001:db8:1::1"
        assert inner_ip.dst == "2001:db8:1::2"

    def test_anonymize_partial_mapping(self):
        """Test partial IP mapping (only some IPs in mapping table)"""
        pkt = (
            Ether()
            / IP(src="10.0.0.1", dst="10.0.0.2")
            / UDP(dport=4789)
            / VXLAN()
            / Ether()
            / IP(src="192.168.1.10", dst="192.168.1.20")
            / TCP()
        )

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {
            "10.0.0.1": "172.16.0.1",
            # Only outer source IP is in mapping table
        }

        modified_pkt, is_modified = strategy.anonymize_packet(pkt)

        assert is_modified is True

        # Verify outer IP - only source should be changed (Scapy index starts from 1)
        outer_ip = modified_pkt.getlayer(IP, 1)
        assert outer_ip.src == "172.16.0.1"
        assert outer_ip.dst == "10.0.0.2"  # Unchanged

        # Verify inner IP - should remain unchanged
        inner_ip = modified_pkt.getlayer(IP, 2)
        assert inner_ip.src == "192.168.1.10"  # Unchanged
        assert inner_ip.dst == "192.168.1.20"  # Unchanged

    def test_anonymize_no_mapping(self):
        """Test anonymization with empty mapping table"""
        pkt = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {}

        modified_pkt, is_modified = strategy.anonymize_packet(pkt)

        assert is_modified is False
        assert modified_pkt.getlayer(IP).src == "192.168.1.1"
        assert modified_pkt.getlayer(IP).dst == "192.168.1.2"

    def test_anonymize_no_ip_layer(self):
        """Test anonymization of packet without IP layer"""
        pkt = Ether() / TCP()

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {"192.168.1.1": "10.0.0.1"}

        modified_pkt, is_modified = strategy.anonymize_packet(pkt)

        assert is_modified is False


@pytest.mark.unit
class TestBackwardCompatibility:
    """Test backward compatibility with existing functionality"""

    def test_plain_ip_packet_unchanged_behavior(self):
        """Test that plain IP packets behave exactly as before"""
        pkt = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {
            "192.168.1.1": "10.0.0.1",
            "192.168.1.2": "10.0.0.2",
        }

        # Extract IPs
        ips = strategy._extract_ips_from_packet(pkt)
        assert len(ips) == 1

        # Anonymize
        modified_pkt, is_modified = strategy.anonymize_packet(pkt)
        assert is_modified is True
        assert modified_pkt.getlayer(IP).src == "10.0.0.1"
        assert modified_pkt.getlayer(IP).dst == "10.0.0.2"

    def test_vlan_packet_unchanged_behavior(self):
        """Test that VLAN packets (single IP layer) behave as before"""
        from scapy.all import Dot1Q

        pkt = Ether() / Dot1Q(vlan=100) / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()

        strategy = HierarchicalAnonymizationStrategy()
        strategy._ip_map = {
            "192.168.1.1": "10.0.0.1",
            "192.168.1.2": "10.0.0.2",
        }

        # Extract IPs - should still find only one IP layer
        ips = strategy._extract_ips_from_packet(pkt)
        assert len(ips) == 1

        # Anonymize
        modified_pkt, is_modified = strategy.anonymize_packet(pkt)
        assert is_modified is True
        assert modified_pkt.getlayer(IP).src == "10.0.0.1"
        assert modified_pkt.getlayer(IP).dst == "10.0.0.2"
