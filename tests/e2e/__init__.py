#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask End-to-End Testing Package

This package contains end-to-end tests using the Golden File Testing approach
to ensure processing consistency across refactoring and updates.

Test Categories:
- Core Functionality Combinations (E2E-001 to E2E-007)
- Protocol Coverage (E2E-101 to E2E-106)
- Encapsulation Types (E2E-201 to E2E-203)

Usage:
    # Generate golden baselines (once on stable version)
    python tests/e2e/generate_golden_baseline.py

    # Run validation tests
    pytest tests/e2e/test_e2e_golden_validation.py -v
"""

__version__ = "1.0.0"
__author__ = "PktMask Development Team"
