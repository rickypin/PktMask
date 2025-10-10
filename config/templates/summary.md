# PktMask — Key Features

## Remove Dupes
* Detects byte-for-byte identical packets inside a capture.
* Keeps the first copy, drops the rest, preserving original order.
* Quickly reduces file size and analytic noise.

## Anonymize IPs
* Replaces every IPv4 and IPv6 address with a synthetic one.
* Keeps subnet boundaries and host relationships so traffic still “looks” the same.
* Produces identical replacements for the same IP across all files, ensuring consistency.
* Re-computes checksums automatically.

## Mask Payloads
* Masks all TCP payload data to zeros by default.
* Preserves TLS handshakes and HTTP headers for troubleshooting.
* TLS encrypted data (ApplicationData) and HTTP bodies are fully masked.
* For HTTP: Cookie/Authorization/Referer header values are also masked (only names kept).
* Notice: The masking algorithm isn't perfect, so double-check it.

## Processing Flow
* Input pcap → **\[Remove Dupes]** → **\[Anonymize IPs]** → **\[Mask Payloads]** → Sanitized pcap
* Middle actions are optional — use any combination as needed.

## Key Benefits
* Protects privacy by removing real addresses and sensitive content.
* Retains timing, protocol flags and network structure for accurate analysis.