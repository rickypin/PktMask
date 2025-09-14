# HTTP Masking E2E Report (Draft)

- Scope: Verify HTTP header preservation + body zero-masking, and TLS behavior unchanged
- Samples: /Users/ricky/Downloads/samples/mixed/ (5 HTTP + 5 TLS)

## Setup
- CLI: `python -m pktmask process /Users/ricky/Downloads/samples/mixed -o /tmp/mixed_out --mask --mask-protocol auto -v`
- Expect: Auto protocol marker combines TLS + HTTP

## Checks (Tshark examples)
- HTTP headers recognized:
  - `tshark -r /tmp/mixed_out/<file> -Y http -T fields -e http.request -e http.request.uri -e http.response.code`
- HTTP body masked to zeros (spot-check):
  - Locate TCP segments carrying `http.file_data`; ensure payload bytes differ from input and contain only 00s in output
- TLS behavior preserved:
  - `tshark -r /tmp/mixed_out/<file> -Y tls` shows handshake/control; application data masked

## Results Summary (2025-09-13, rerun with PCAP only)
- Total files: 10
- Output dir: `output/e2e_http_auto_mixed_v2`
- Outcome: 10 processed, 0 failed
- Runtime: ~24.23s

### TLS samples
- OK: TLS marker active; handshake/control preserved; application data masked
  - `tls_1_2_plainip.pcap`: processed_packets=22, modified_packets=2
  - `google-https-cachedlink_plus_sitelink.pcap`: processed_packets=1030, modified_packets=473

### HTTP samples (converted to .pcap)
- tshark HTTP detection on outputs (lines with request/URI/status):
  - `TC-002-1-20211208.pcap`: 8
  - `http-chappellu2011.pcap`: 40
  - `http-download-good.pcap`: 1
  - `http-proxy-problem.pcap`: 4
  - `http-500error.pcap`: 0 (likely no decodable HTTP fields by filter in this file)

Notes:
- Some TLS captures still show incidental `http` matches (e.g. `tls_1_0_multi_segment_google-https.pcap:27`) due to mixed/clear segments in sample.
- For `http-500error.pcap`，过滤条件 `-e http.request -e http.request.uri -e http.response.code` 可能未命中该文件中的具体字段布局，需针对该样本调整验证字段或以 Wireshark GUI 复核。

### HTTP zero-body spot check
- Script: `scripts/verify_http_zero_body.py`
- Command: `PYTHONPATH=src python3 scripts/verify_http_zero_body.py --input output/e2e_http_auto_mixed_v2`
- Result: PASS (no non-zero body bytes found in checked segments)
- Per-file checked segments and violations:
  - `TC-002-1-20211208.pcap`: checked=8, violations=0
  - `http-chappellu2011.pcap`: checked=20, violations=0
  - `http-download-good.pcap`: checked=1, violations=0
  - `http-proxy-problem.pcap`: checked=2, violations=0
  - `http-500error.pcap`: checked=0, violations=0 (no header+body-in-same-segment case detected by heuristic)
  - TLS files: either 0 or incidental checks, all zero violations

## Follow-ups
- PCAPNG support（可选）
  - DataValidator: 识别 pcapng 魔数，按格式选择 Reader/Writer
  - Masker/Marker: 动态选择 `PcapReader/PcapWriter` 或 `PcapNgReader/PcapNgWriter`
- 交叉分段 Header 的增强（少见场景）
- 根据需要，扩展 chunked 编码保留块长度行（可选）
