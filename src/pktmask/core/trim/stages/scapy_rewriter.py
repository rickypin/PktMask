#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scapy回写器 - Phase 3 重构版

该文件当前仅作为适配器，将对 `ScapyRewriter` 的调用重定向到
`TcpPayloadMaskerAdapter`，以保证向后兼容性。

原始的 ScapyRewriter 类定义已被移除。
"""

import logging

# ---- Phase 2-B 系统集成：重定义 ScapyRewriter 为 TcpPayloadMaskerAdapter ----
# 这一行是此文件的核心，它确保所有导入 ScapyRewriter 的旧代码
# 实际上得到的是新的、功能正确的 TcpPayloadMaskerAdapter 类。
from .tcp_payload_masker_adapter import TcpPayloadMaskerAdapter as _TPMAdapter
ScapyRewriter = _TPMAdapter  # type: ignore

__all__ = ['ScapyRewriter']


     
   