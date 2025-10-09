#!/bin/bash
# -*- coding: utf-8 -*-

###############################################################################
# PktMask E2E Test Runner with HTML Report
#
# This script runs end-to-end tests and generates comprehensive HTML reports
#
# Usage:
#   ./tests/e2e/run_e2e_tests.sh [options]
#
# Options:
#   --all           Run all tests (default)
#   --core          Run only core functionality tests
#   --protocol      Run only protocol coverage tests
#   --encap         Run only encapsulation tests
#   --parallel      Run tests in parallel
#   --open          Open HTML report in browser after completion
#   --help          Show this help message
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_SCOPE="all"
PARALLEL=false
OPEN_REPORT=false
REPORT_DIR="tests/e2e"
REPORT_FILE="report.html"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            TEST_SCOPE="all"
            shift
            ;;
        --core)
            TEST_SCOPE="core"
            REPORT_FILE="report_core.html"
            shift
            ;;
        --protocol)
            TEST_SCOPE="protocol"
            REPORT_FILE="report_protocol.html"
            shift
            ;;
        --encap)
            TEST_SCOPE="encap"
            REPORT_FILE="report_encap.html"
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --open)
            OPEN_REPORT=true
            shift
            ;;
        --help)
            echo "PktMask E2E Test Runner"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --all           Run all tests (default)"
            echo "  --core          Run only core functionality tests"
            echo "  --protocol      Run only protocol coverage tests"
            echo "  --encap         Run only encapsulation tests"
            echo "  --parallel      Run tests in parallel"
            echo "  --open          Open HTML report in browser after completion"
            echo "  --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                          # Run all tests"
            echo "  $0 --core --open            # Run core tests and open report"
            echo "  $0 --all --parallel         # Run all tests in parallel"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Print header
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         PktMask E2E Test Runner with HTML Report          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Please install it with: pip install pytest pytest-html"
    exit 1
fi

# Check if pytest-html is installed
if ! python -c "import pytest_html" &> /dev/null; then
    echo -e "${YELLOW}Warning: pytest-html is not installed${NC}"
    echo "Installing pytest-html..."
    pip install pytest-html
fi

# Determine test path
TEST_PATH="tests/e2e/test_e2e_golden_validation.py"
case $TEST_SCOPE in
    core)
        TEST_PATH="${TEST_PATH}::TestE2EGoldenValidation::test_core_functionality_consistency"
        echo -e "${GREEN}Running Core Functionality Tests${NC}"
        ;;
    protocol)
        TEST_PATH="${TEST_PATH}::TestE2EGoldenValidation::test_protocol_coverage_consistency"
        echo -e "${GREEN}Running Protocol Coverage Tests${NC}"
        ;;
    encap)
        TEST_PATH="${TEST_PATH}::TestE2EGoldenValidation::test_encapsulation_consistency"
        echo -e "${GREEN}Running Encapsulation Tests${NC}"
        ;;
    all)
        echo -e "${GREEN}Running All E2E Tests${NC}"
        ;;
esac

echo ""

# Build pytest command
PYTEST_CMD="pytest ${TEST_PATH} -v"
PYTEST_CMD="${PYTEST_CMD} --html=${REPORT_DIR}/${REPORT_FILE}"
PYTEST_CMD="${PYTEST_CMD} --self-contained-html"
PYTEST_CMD="${PYTEST_CMD} --junitxml=${REPORT_DIR}/junit.xml"

# Add parallel execution if requested
if [ "$PARALLEL" = true ]; then
    if python -c "import xdist" &> /dev/null; then
        PYTEST_CMD="${PYTEST_CMD} -n auto"
        echo -e "${YELLOW}Parallel execution enabled${NC}"
    else
        echo -e "${YELLOW}Warning: pytest-xdist not installed, running sequentially${NC}"
        echo "Install with: pip install pytest-xdist"
    fi
fi

echo ""
echo -e "${BLUE}Command: ${PYTEST_CMD}${NC}"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Run tests
START_TIME=$(date +%s)

if eval $PYTEST_CMD; then
    TEST_RESULT=0
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    TEST_RESULT=$?
    echo ""
    echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ Some tests failed!${NC}"
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Print summary
echo -e "${BLUE}Test Summary:${NC}"
echo -e "  Duration: ${DURATION}s"
echo -e "  HTML Report: ${REPORT_DIR}/${REPORT_FILE}"
echo -e "  JUnit XML: ${REPORT_DIR}/junit.xml"
echo -e "  JSON Results: ${REPORT_DIR}/test_results.json"
echo ""

# Open report if requested
if [ "$OPEN_REPORT" = true ]; then
    echo -e "${GREEN}Opening HTML report in browser...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "${REPORT_DIR}/${REPORT_FILE}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        xdg-open "${REPORT_DIR}/${REPORT_FILE}" 2>/dev/null || echo "Please open ${REPORT_DIR}/${REPORT_FILE} manually"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        # Windows
        start "${REPORT_DIR}/${REPORT_FILE}"
    else
        echo -e "${YELLOW}Cannot auto-open browser on this platform${NC}"
        echo "Please open ${REPORT_DIR}/${REPORT_FILE} manually"
    fi
else
    echo -e "${YELLOW}To view the report, open: ${REPORT_DIR}/${REPORT_FILE}${NC}"
    echo -e "${YELLOW}Or run with --open flag to auto-open in browser${NC}"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

exit $TEST_RESULT

