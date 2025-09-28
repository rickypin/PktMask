"""
HTTP Protocol Marker

Best-effort HTTP header detector that generates keep-rules for headers only
and leaves bodies to be fully masked by the generic PayloadMasker.

Design goals:
- Pragmatic, low-dependency implementation using scapy for streaming
- Preserve only HTTP headers (request/status line + headers up to CRLFCRLF)
- Fallback: if full header is not found, keep at least the start line
- Produce absolute TCP sequence ranges as KeepRule entries with
  preserve_strategy = "header_only"

Limitations (intentional to avoid over-engineering):
- Minimal reassembly: only up to header terminator per message; does not
  re-order out-of-order segments; assumes typical ordered captures
- Chunked/body internals are not preserved (body is masked by Masker)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from scapy.all import IP, TCP, IPv6, PcapReader

    SCAPY_AVAILABLE = True
except Exception:  # pragma: no cover - scapy may be unavailable in some envs
    IP = IPv6 = TCP = PcapReader = None
    SCAPY_AVAILABLE = False

from .types import KeepRule, KeepRuleSet

# Common HTTP method tokens and response prefix for quick heuristics
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


SENSITIVE_HEADER_NAMES = {b"cookie", b"authorization", b"referer"}


@dataclass
class _MessageState:
    collecting: bool = False
    start_seq: Optional[int] = None
    buffer: bytearray = field(default_factory=bytearray)
    max_scan_bytes: int = 16 * 1024  # safety cap for header scan


class HTTPProtocolMarker:
    """HTTP marker implementation.

    Builds header-only keep rules per TCP flow-direction. Uses a best-effort
    recognition strategy that is robust on common captures and safe by default.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Flow bookkeeping (must mirror Masker to align stream_id + direction)
        self.flow_id_counter = 0
        self.tuple_to_stream_id: Dict[str, str] = {}
        self.flow_directions: Dict[str, Dict[str, Any]] = {}
        # Per-direction message scan state
        self.states: Dict[Tuple[str, str], _MessageState] = {}

        # Ports heuristic (common HTTP ports)
        self.http_ports: Tuple[int, ...] = tuple(
            self.config.get("ports", [80, 8080, 8000, 8888])
        )

        self._sensitive_header_names = SENSITIVE_HEADER_NAMES

    def initialize(self) -> bool:
        return True

    def cleanup(self) -> None:  # symmetry with other markers
        self.states.clear()
        self.tuple_to_stream_id.clear()
        self.flow_directions.clear()

    # --- Public API ---
    def analyze_file(self, pcap_path: str, config: Dict[str, Any]) -> KeepRuleSet:
        ruleset = KeepRuleSet()
        debug = False
        try:
            import os

            debug = os.environ.get("PKTMASK_HTTP_DEBUG", "").lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        except Exception:
            debug = False

        if not SCAPY_AVAILABLE:
            self.logger.warning("Scapy unavailable, HTTP marker disabled")
            ruleset.metadata = {
                "analyzer": "HTTPProtocolMarker",
                "error": "scapy_unavailable",
                "analysis_failed": True,
                "pcap_path": pcap_path,
            }
            return ruleset

        try:
            total_tcp = 0
            total_with_payload = 0
            found_candidates = 0
            with PcapReader(pcap_path) as reader:
                for pkt in reader:
                    try:
                        if not pkt or not pkt.haslayer(TCP):
                            continue

                        # Find innermost IP/TCP
                        ip = self._get_ip_layer(pkt)
                        tcp = pkt[TCP]
                        payload: bytes = bytes(tcp.payload) if tcp.payload else b""
                        total_tcp += 1
                        if not payload:
                            continue
                        total_with_payload += 1

                        stream_id = self._build_stream_id(ip, tcp)
                        tuple_key = self._build_tuple_key(ip, tcp)
                        direction = self._determine_flow_direction(ip, tcp, stream_id)

                        # Heuristic: is likely HTTP?
                        if not self._is_likely_http(ip, tcp, payload):
                            continue
                        found_candidates += 1

                        seg_start = int(tcp.seq)
                        seg_start + len(payload)
                        state_key = (stream_id, direction)
                        state = self.states.setdefault(state_key, _MessageState())

                        # If not collecting, try to detect start line (lenient)
                        if not state.collecting:
                            start_off = 0
                            if self._looks_like_http_start(payload):
                                start_off = 0
                            else:
                                # Find token anywhere in this segment
                                idx = payload.find(b"HTTP/1.")
                                if idx < 0:
                                    # find earliest method occurrence
                                    idxs = [
                                        i
                                        for i in [payload.find(m) for m in HTTP_METHODS]
                                        if i >= 0
                                    ]
                                    idx = min(idxs) if idxs else -1
                                if idx >= 0:
                                    start_off = idx
                                else:
                                    # No recognizable start in this segment
                                    continue
                            state.collecting = True
                            state.start_seq = seg_start + start_off
                            state.buffer = bytearray()
                            # Skip bytes before detected start
                            if start_off:
                                payload = payload[start_off:]

                        # Append to buffer (cap)
                        if len(state.buffer) < state.max_scan_bytes:
                            need = state.max_scan_bytes - len(state.buffer)
                            state.buffer.extend(payload[:need])

                        # Search for CRLFCRLF
                        hdr_end_off = self._find_header_terminator(state.buffer)
                        if hdr_end_off is not None and state.start_seq is not None:
                            # Found full header: generate keep ranges excluding sensitive values
                            header_bytes = bytes(state.buffer[:hdr_end_off])
                            seq_start = state.start_seq
                            keep_ranges = self._compute_header_keep_ranges(
                                header_bytes, seq_start
                            )
                            for rng_start, rng_end in keep_ranges:
                                rule = self._make_header_rule(
                                    stream_id, direction, rng_start, rng_end, tuple_key
                                )
                                ruleset.add_rule(rule)
                            # Reset for next message
                            self.states[state_key] = _MessageState()
                        else:
                            # Fallback: if buffer nearly full with start-line detected but no terminator,
                            # try to at least keep the start line up to first CRLF
                            if (
                                len(state.buffer)
                                >= min(1024, state.max_scan_bytes // 2)
                                and state.start_seq is not None
                            ):
                                first_line_end = self._find_first_crlf(state.buffer)
                                if first_line_end is not None and first_line_end > 0:
                                    header_bytes = bytes(state.buffer[:first_line_end])
                                    seq_start = state.start_seq
                                    keep_ranges = self._compute_header_keep_ranges(
                                        header_bytes, seq_start
                                    )
                                    for rng_start, rng_end in keep_ranges:
                                        rule = self._make_header_rule(
                                            stream_id,
                                            direction,
                                            rng_start,
                                            rng_end,
                                            tuple_key,
                                        )
                                        ruleset.add_rule(rule)
                                    # Reset
                                    self.states[state_key] = _MessageState()

                        # Record simple tcp_flow metadata (optional)
                        ruleset.tcp_flows.setdefault(
                            stream_id, {"directions": {"forward": {}, "reverse": {}}}
                        )

                    except Exception as e:  # per-packet resilience
                        self.logger.debug(f"HTTP marker packet error: {e}")
                        continue

            ruleset.metadata.update(
                {
                    "analyzer": "HTTPProtocolMarker",
                    "pcap_path": pcap_path,
                    "stats": {
                        "tcp_packets": total_tcp,
                        "tcp_with_payload": total_with_payload,
                        "http_candidates": found_candidates,
                        "rules": len(ruleset.rules),
                    },
                }
            )
            if debug:
                self.logger.info(
                    f"HTTPMarker stats: tcp={total_tcp}, with_payload={total_with_payload}, candidates={found_candidates}, rules={len(ruleset.rules)}"
                )
            return ruleset

        except Exception as e:
            self.logger.error(f"HTTP analysis failed: {e}")
            ruleset = KeepRuleSet()
            ruleset.metadata = {
                "analyzer": "HTTPProtocolMarker",
                "error": str(e),
                "analysis_failed": True,
                "pcap_path": pcap_path,
            }
            return ruleset

    # --- helpers ---
    def _get_ip_layer(self, pkt):
        if pkt.haslayer(IP):
            return pkt[IP]
        if pkt.haslayer(IPv6):
            return pkt[IPv6]
        return None

    def _build_tuple_key(self, ip_layer, tcp_layer) -> str:
        """Construct a stable tuple key string independent of encounter order."""
        src_ip = str(getattr(ip_layer, "src", ""))
        dst_ip = str(getattr(ip_layer, "dst", ""))
        try:
            src_port = int(tcp_layer.sport)
            dst_port = int(tcp_layer.dport)
        except Exception:
            src_port = getattr(tcp_layer, "sport", 0)
            dst_port = getattr(tcp_layer, "dport", 0)
        if (src_ip, src_port) < (dst_ip, dst_port):
            return f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
        else:
            return f"{dst_ip}:{dst_port}-{src_ip}:{src_port}"

    def _is_likely_http(self, ip, tcp, payload: bytes) -> bool:
        try:
            # Port heuristic
            if int(tcp.sport) in self.http_ports or int(tcp.dport) in self.http_ports:
                return True
        except Exception:
            pass

        # Payload prefix heuristic (strict)
        if payload.startswith(b"HTTP/1."):
            return True
        for m in HTTP_METHODS:
            if payload.startswith(m):
                return True
        # Lenient: look for token anywhere to tolerate segmentation or dedup shifts
        if b"HTTP/1." in payload:
            return True
        for m in HTTP_METHODS:
            if m in payload:
                return True
        return False

    def _looks_like_http_start(self, payload: bytes) -> bool:
        if payload.startswith(b"HTTP/1."):
            return True
        for m in HTTP_METHODS:
            if payload.startswith(m):
                return True
        return False

    def _find_header_terminator(self, buf: bytearray) -> Optional[int]:
        # look for \r\n\r\n ; return end offset (exclusive)
        idx = bytes(buf).find(b"\r\n\r\n")
        if idx >= 0:
            return idx + 4
        return None

    def _find_first_crlf(self, buf: bytearray) -> Optional[int]:
        idx = bytes(buf).find(b"\r\n")
        if idx >= 0:
            return idx + 2
        return None

    def _make_header_rule(
        self,
        stream_id: str,
        direction: str,
        seq_start: int,
        seq_end: int,
        tuple_key: Optional[str] = None,
    ) -> KeepRule:
        meta = {"preserve_strategy": "header_only"}
        if tuple_key:
            meta["tuple_key"] = tuple_key
        return KeepRule(
            stream_id=stream_id,
            direction=direction,
            seq_start=seq_start,
            seq_end=seq_end,
            rule_type="http_header",
            metadata=meta,
        )

    def _compute_header_keep_ranges(
        self, header_bytes: bytes, base_seq: int
    ) -> List[Tuple[int, int]]:
        """Split header into keep ranges while stripping sensitive values."""

        keep_ranges: List[Tuple[int, int]] = []
        length = len(header_bytes)
        pos = 0
        continuation_sensitive = False

        while pos <= length:
            eol = header_bytes.find(b"\r\n", pos)
            if eol < 0:
                eol = length
                crlf_len = 0
                next_pos = length + 1  # exit loop
            else:
                crlf_len = 2
                next_pos = eol + crlf_len

            line = header_bytes[pos:eol]
            is_blank_line = len(line) == 0
            is_continuation = len(line) > 0 and line[:1] in (b" ", b"\t")

            sensitive = False
            prefix_len = len(line)

            if is_blank_line:
                continuation_sensitive = False
            elif is_continuation:
                sensitive = continuation_sensitive
                if sensitive:
                    prefix_len = 0
                else:
                    prefix_len = len(line)
            else:
                colon_idx = line.find(b":")
                if colon_idx >= 0:
                    header_name = line[:colon_idx].strip().lower()
                    if header_name in self._sensitive_header_names:
                        sensitive = True
                        prefix_len = colon_idx + 1
                        while prefix_len < len(line) and line[
                            prefix_len : prefix_len + 1
                        ] in (b" ", b"\t"):
                            prefix_len += 1
                    else:
                        prefix_len = len(line)
                else:
                    prefix_len = len(line)

                continuation_sensitive = sensitive

            if prefix_len > 0:
                rng_start = base_seq + pos
                rng_end = base_seq + pos + prefix_len
                if rng_start < rng_end:
                    keep_ranges.append((rng_start, rng_end))

            if crlf_len:
                rng_start = base_seq + eol
                rng_end = base_seq + eol + crlf_len
                if rng_start < rng_end:
                    keep_ranges.append((rng_start, rng_end))

            pos = next_pos
            if pos > length:
                break

        return keep_ranges

    def _build_stream_id(self, ip_layer, tcp_layer) -> str:
        # Keep consistent with Masker
        src_ip = str(getattr(ip_layer, "src", ""))
        dst_ip = str(getattr(ip_layer, "dst", ""))
        src_port = int(tcp_layer.sport)
        dst_port = int(tcp_layer.dport)

        if (src_ip, src_port) < (dst_ip, dst_port):
            tuple_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
        else:
            tuple_key = f"{dst_ip}:{dst_port}-{src_ip}:{src_port}"

        if tuple_key in self.tuple_to_stream_id:
            return self.tuple_to_stream_id[tuple_key]

        stream_id = str(self.flow_id_counter)
        self.tuple_to_stream_id[tuple_key] = stream_id
        self.flow_id_counter += 1
        return stream_id

    def _determine_flow_direction(self, ip_layer, tcp_layer, stream_id: str) -> str:
        """确定流方向，与TLS Marker保持一致的逻辑

        使用字典序确定canonical方向，确保与TLS Marker的一致性。
        """
        src_ip = str(getattr(ip_layer, "src", ""))
        dst_ip = str(getattr(ip_layer, "dst", ""))
        src_port = int(tcp_layer.sport)
        dst_port = int(tcp_layer.dport)

        # 使用与_build_tuple_key完全相同的字典序逻辑
        # 确定canonical forward方向：字典序较小的端点作为源
        if (src_ip, src_port) < (dst_ip, dst_port):
            # 当前连接的字典序：src < dst，所以forward是src->dst
            canonical_forward = {
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
            }
        else:
            # 当前连接的字典序：src > dst，所以forward是dst->src
            canonical_forward = {
                "src_ip": dst_ip,
                "dst_ip": src_ip,
                "src_port": dst_port,
                "dst_port": src_port,
            }

        # 存储canonical方向信息（如果还没有存储）
        if stream_id not in self.flow_directions:
            self.flow_directions[stream_id] = {
                "forward": canonical_forward,
                "reverse": {
                    "src_ip": canonical_forward["dst_ip"],
                    "dst_ip": canonical_forward["src_ip"],
                    "src_port": canonical_forward["dst_port"],
                    "dst_port": canonical_forward["src_port"],
                },
            }

        # 判断当前包的方向
        fwd = self.flow_directions[stream_id]["forward"]
        if (
            src_ip == fwd["src_ip"]
            and src_port == fwd["src_port"]
            and dst_ip == fwd["dst_ip"]
            and dst_port == fwd["dst_port"]
        ):
            return "forward"
        return "reverse"
