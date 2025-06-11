# PktMask — Key Features

## Mask IPs
   - Replaces every IPv4 and IPv6 address with a synthetic one.
   - Keeps subnet boundaries and host relationships so traffic still “looks” the same.
   - Produces identical replacements for the same IP across all files, ensuring consistency.
   - Re-computes checksums automatically.

## Remove Dupes
   - Detects byte-for-byte identical packets inside a capture.
   - Keeps the first copy, drops the rest, preserving original order.
   - Quickly reduces file size and analytic noise.

## Trim Payloads
   - Scans TLS streams and keeps only handshake, alert and control records.
   - Discards bulk TLS application data while leaving TCP control packets intact.
   - Greatly shrinks captures without hiding session establishment details.

## Processing Flow
   - Input pcap → [Remove Dupes] → [Mask IPs] → [Trim Payloads] → Sanitized pcap
   - Middle actions are optional — use any combination as needed.

## Key Benefits
   - Protects privacy by removing real addresses and sensitive content.
   - Retains timing, protocol flags and network structure for accurate analysis.