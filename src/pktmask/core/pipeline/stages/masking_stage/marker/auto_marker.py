"""
Auto Protocol Marker

Combines multiple protocol markers (currently TLS + HTTP) and merges
their KeepRuleSets. Used when MaskingStage.protocol == 'auto'.
"""

from __future__ import annotations

from typing import Any, Dict

from .types import KeepRuleSet


class AutoProtocolMarker:
    def __init__(self, marker_config: Dict[str, Any]):
        self.marker_config = marker_config or {}
        self.tls_marker = None
        self.http_marker = None

    def initialize(self) -> bool:
        try:
            from .tls_marker import TLSProtocolMarker
            from .http_marker import HTTPProtocolMarker

            self.tls_marker = TLSProtocolMarker(self.marker_config)
            self.http_marker = HTTPProtocolMarker(self.marker_config)
            self.tls_marker.initialize()
            self.http_marker.initialize()
            return True
        except Exception:
            return False

    def cleanup(self) -> None:
        try:
            if self.tls_marker and hasattr(self.tls_marker, "cleanup"):
                self.tls_marker.cleanup()
            if self.http_marker and hasattr(self.http_marker, "cleanup"):
                self.http_marker.cleanup()
        except Exception:
            pass

    def analyze_file(self, pcap_path: str, config: Dict[str, Any]) -> KeepRuleSet:
        ruleset = KeepRuleSet()
        # TLS first (more deterministic), then HTTP
        if self.tls_marker:
            tls_rs = self.tls_marker.analyze_file(pcap_path, config)
            ruleset.rules.extend(tls_rs.rules)
            ruleset.tcp_flows.update(tls_rs.tcp_flows)
            ruleset.statistics.update(tls_rs.statistics)
        if self.http_marker:
            http_rs = self.http_marker.analyze_file(pcap_path, config)
            ruleset.rules.extend(http_rs.rules)
            ruleset.tcp_flows.update(http_rs.tcp_flows)
            ruleset.statistics.update(http_rs.statistics)

        ruleset.metadata = {
            "analyzer": "AutoProtocolMarker",
            "pcap_path": pcap_path,
        }
        return ruleset

