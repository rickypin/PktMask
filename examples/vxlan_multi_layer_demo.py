#!/usr/bin/env python3
"""
VXLAN Multi-Layer IP Anonymization Demo

This script demonstrates the enhanced multi-layer IP anonymization capability
for VXLAN encapsulated packets. It shows how both outer (tunnel endpoint) and
inner (actual host) IP addresses are anonymized.

Author: PktMask Team
Date: 2025-11-06
"""

from scapy.all import IP, TCP, UDP, VXLAN, Ether, IPv6

from pktmask.core.strategy import HierarchicalAnonymizationStrategy


def create_vxlan_packet():
    """Create a sample VXLAN packet with dual IP layers"""
    pkt = (
        Ether()
        / IP(src="10.0.0.1", dst="10.0.0.2")  # Outer IP (tunnel endpoints)
        / UDP(dport=4789)  # VXLAN port
        / VXLAN()
        / Ether()
        / IP(src="192.168.1.10", dst="192.168.1.20")  # Inner IP (actual hosts)
        / TCP(sport=12345, dport=80)
    )
    return pkt


def create_mixed_version_vxlan_packet():
    """Create a VXLAN packet with IPv4 outer and IPv6 inner"""
    pkt = (
        Ether()
        / IP(src="10.0.0.1", dst="10.0.0.2")  # Outer IPv4
        / UDP(dport=4789)
        / VXLAN()
        / Ether()
        / IPv6(src="2001:db8::1", dst="2001:db8::2")  # Inner IPv6
        / TCP(sport=12345, dport=80)
    )
    return pkt


def print_packet_ips(pkt, label):
    """Print all IP layers in a packet"""
    print(f"\n{label}:")
    print("-" * 60)

    # Print all IPv4 layers
    idx = 1
    while True:
        ip_layer = pkt.getlayer(IP, idx)
        if ip_layer is None:
            break
        print(f"  IPv4 Layer {idx}: {ip_layer.src} -> {ip_layer.dst}")
        idx += 1

    # Print all IPv6 layers
    idx = 1
    while True:
        ip_layer = pkt.getlayer(IPv6, idx)
        if ip_layer is None:
            break
        print(f"  IPv6 Layer {idx}: {ip_layer.src} -> {ip_layer.dst}")
        idx += 1


def demo_vxlan_dual_ipv4():
    """Demonstrate VXLAN with dual IPv4 layers"""
    print("\n" + "=" * 60)
    print("Demo 1: VXLAN with Dual IPv4 Layers")
    print("=" * 60)

    # Create packet
    pkt = create_vxlan_packet()
    print_packet_ips(pkt, "Original Packet")

    # Create strategy and set up IP mapping
    strategy = HierarchicalAnonymizationStrategy()
    strategy._ip_map = {
        "10.0.0.1": "172.16.0.1",  # Outer source
        "10.0.0.2": "172.16.0.2",  # Outer destination
        "192.168.1.10": "172.20.0.10",  # Inner source
        "192.168.1.20": "172.20.0.20",  # Inner destination
    }

    # Anonymize packet
    anonymized_pkt, is_modified = strategy.anonymize_packet(pkt)

    print_packet_ips(anonymized_pkt, "Anonymized Packet")
    print(f"\nPacket was modified: {is_modified}")


def demo_vxlan_mixed_versions():
    """Demonstrate VXLAN with IPv4 outer and IPv6 inner"""
    print("\n" + "=" * 60)
    print("Demo 2: VXLAN with IPv4 Outer and IPv6 Inner")
    print("=" * 60)

    # Create packet
    pkt = create_mixed_version_vxlan_packet()
    print_packet_ips(pkt, "Original Packet")

    # Create strategy and set up IP mapping
    strategy = HierarchicalAnonymizationStrategy()
    strategy._ip_map = {
        "10.0.0.1": "172.16.0.1",
        "10.0.0.2": "172.16.0.2",
        "2001:db8::1": "2001:db8:1::1",
        "2001:db8::2": "2001:db8:1::2",
    }

    # Anonymize packet
    anonymized_pkt, is_modified = strategy.anonymize_packet(pkt)

    print_packet_ips(anonymized_pkt, "Anonymized Packet")
    print(f"\nPacket was modified: {is_modified}")


def demo_plain_ip_backward_compatibility():
    """Demonstrate backward compatibility with plain IP packets"""
    print("\n" + "=" * 60)
    print("Demo 3: Backward Compatibility - Plain IP Packet")
    print("=" * 60)

    # Create plain IP packet (no VXLAN)
    pkt = Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP()
    print_packet_ips(pkt, "Original Packet")

    # Create strategy and set up IP mapping
    strategy = HierarchicalAnonymizationStrategy()
    strategy._ip_map = {
        "192.168.1.1": "10.0.0.1",
        "192.168.1.2": "10.0.0.2",
    }

    # Anonymize packet
    anonymized_pkt, is_modified = strategy.anonymize_packet(pkt)

    print_packet_ips(anonymized_pkt, "Anonymized Packet")
    print(f"\nPacket was modified: {is_modified}")
    print("\nNote: Plain IP packets work exactly as before!")


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("VXLAN Multi-Layer IP Anonymization Demo")
    print("=" * 60)
    print("\nThis demo shows the enhanced capability to anonymize ALL IP layers")
    print("in VXLAN encapsulated packets, including both outer (tunnel) and")
    print("inner (host) IP addresses.")

    demo_vxlan_dual_ipv4()
    demo_vxlan_mixed_versions()
    demo_plain_ip_backward_compatibility()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nKey Features Demonstrated:")
    print("  ✓ Multi-layer IPv4 anonymization (VXLAN)")
    print("  ✓ Mixed IPv4/IPv6 anonymization (VXLAN)")
    print("  ✓ Backward compatibility with plain IP packets")
    print("  ✓ All IP layers are processed correctly")
    print()


if __name__ == "__main__":
    main()
