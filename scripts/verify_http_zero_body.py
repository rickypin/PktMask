#!/usr/bin/env python3
"""
Verify that HTTP bodies are zero-masked in processed pcaps.

Heuristic:
- For each TCP packet payload, search for CRLFCRLF (\r\n\r\n).
- If the payload also contains an HTTP start token (method or 'HTTP/1.'),
  treat bytes after the first CRLFCRLF as body bytes and assert all are 0x00.
- This is a best-effort spot check; it will catch same-segment header+body.

Usage:
  PYTHONPATH=src python3 scripts/verify_http_zero_body.py --input output/e2e_http_auto_mixed_v2
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from scapy.all import IP, TCP, PcapReader

HTTP_METHODS = (
    b"GET ",
    b"POST ",
    b"PUT ",
    b"DELETE ",
    b"HEAD ",
    b"OPTIONS ",
    b"PATCH ",
    b"TRACE ",
    b"CONNECT ",
)


def looks_like_http_segment(payload: bytes) -> bool:
    if b"HTTP/1." in payload:
        return True
    return any(m in payload for m in HTTP_METHODS)


def check_file(pcap_path: Path) -> dict:
    total_packets = 0
    checked_segments = 0
    violations = 0
    first_violations = []

    with PcapReader(str(pcap_path)) as rd:
        for idx, pkt in enumerate(rd, 1):
            if not pkt.haslayer(TCP):
                continue
            tcp = pkt[TCP]
            payload = bytes(tcp.payload) if tcp.payload else b""
            if not payload:
                continue
            total_packets += 1

            # require HTTP hint in this segment to avoid false positives
            if not looks_like_http_segment(payload):
                continue

            pos = payload.find(b"\r\n\r\n")
            if pos < 0:
                continue
            body = payload[pos + 4 :]
            if not body:
                continue
            checked_segments += 1
            if any(b != 0 for b in body):
                violations += 1
                if len(first_violations) < 5:
                    first_violations.append(
                        {"packet_index": idx, "body_sample": body[:32].hex()}
                    )

    return {
        "file": str(pcap_path.name),
        "total_packets": total_packets,
        "checked_segments": checked_segments,
        "violations": violations,
        "examples": first_violations,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Processed pcap directory")
    args = ap.parse_args()

    base = Path(args.input)
    files = [
        base / f for f in os.listdir(base) if f.lower().endswith((".pcap", ".pcapng"))
    ]
    files.sort()

    summary = []
    total_violations = 0
    for f in files:
        res = check_file(f)
        summary.append(res)
        total_violations += res["violations"]

    print("HTTP zero-body spot check summary")
    for res in summary:
        print(
            f"- {res['file']}: checked_segments={res['checked_segments']}, violations={res['violations']}"
        )
        if res["violations"] and res["examples"]:
            print(f"  examples: {res['examples']}")

    if total_violations == 0:
        print("Result: PASS (no body bytes found non-zero in checked segments)")
        return 0
    else:
        print(f"Result: FAIL ({total_violations} violation segments)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
