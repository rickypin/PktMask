#!/usr/bin/env python3
"""
Standalone E2E runner for HTTP masking (protocol=auto) without Typer dependency.

Usage:
  PYTHONPATH=src python3 scripts/run_http_auto_e2e.py \
    --input /Users/ricky/Downloads/samples/mixed \
    --output output/e2e_http_auto_mixed
"""

import argparse
import os
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Late import from src
    from pktmask.core.consistency import ConsistentProcessor

    files = []
    for root, _, fnames in os.walk(input_dir):
        for f in fnames:
            if f.lower().endswith((".pcap", ".pcapng")):
                files.append(Path(root) / f)

    if not files:
        print("No pcap/pcapng files found")
        return 2

    print(f"Processing {len(files)} files -> {output_dir}")
    processed = 0
    failed = 0
    total_ms = 0.0

    for i, fpath in enumerate(files, 1):
        out = output_dir / fpath.name
        print(f"[{i}/{len(files)}] {fpath.name}")
        try:
            start = time.time()
            result = ConsistentProcessor.process_file(
                fpath, out, dedup=False, anon=False, mask=True, mask_protocol="auto"
            )
            total_ms += (time.time() - start) * 1000
            if result.success:
                processed += 1
                # Count http_header rules if present
                # We cannot expose rule count directly from ProcessResult, keep placeholder
            else:
                failed += 1
                print("  ERR:", "; ".join(result.errors))
        except Exception as e:
            failed += 1
            print("  EXC:", e)

    print("--- Summary ---")
    print("Processed:", processed)
    print("Failed:", failed)
    print(f"Total duration: {total_ms/1000:.2f}s")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
