#!/bin/bash
# PktMask Virtual Environment Activation Script
# Usage: source activate.sh

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         PktMask Development Environment Activation          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found!${NC}"
    echo -e "   Creating .venv..."
    python3 -m venv .venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
    echo ""
fi

# Activate virtual environment
echo -e "${BLUE}🔄 Activating virtual environment...${NC}"
source .venv/bin/activate

# Display environment info
echo -e "${GREEN}✅ Virtual environment activated!${NC}"
echo ""
echo -e "${BLUE}📊 Environment Information:${NC}"
echo -e "   Python:  $(python --version)"
echo -e "   Pip:     $(pip --version | cut -d' ' -f1-2)"
echo -e "   Location: $(which python)"
echo ""

# Check if pktmask is installed
if python -c "import pktmask" 2>/dev/null; then
    echo -e "${GREEN}✅ pktmask package is installed${NC}"
else
    echo -e "${YELLOW}⚠️  pktmask package not installed${NC}"
    echo -e "   Run: ${BLUE}pip install -e \".[dev,build,performance]\"${NC}"
fi

echo ""
echo -e "${BLUE}🚀 Quick Commands:${NC}"
echo -e "   ${GREEN}pktmask${NC}                    - Launch GUI"
echo -e "   ${GREEN}pktmask process --help${NC}     - CLI help"
echo -e "   ${GREEN}pytest${NC}                     - Run tests"
echo -e "   ${GREEN}black src/ tests/${NC}          - Format code"
echo -e "   ${GREEN}mypy src/${NC}                  - Type check"
echo -e "   ${GREEN}deactivate${NC}                 - Exit venv"
echo ""
echo -e "${GREEN}🎉 Ready to develop!${NC}"
echo ""

