#!/bin/bash

# Git Hooks Installation Script for PktMask
# Installs pre-commit hooks to enforce English-Only Coding Policy

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo -e "${BLUE}🔧 Installing Git Hooks for PktMask${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if we're in a git repository
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo -e "${RED}❌ Error: Not in a Git repository${NC}"
    echo -e "Please run this script from the PktMask project root"
    exit 1
fi

# Create hooks directory if it doesn't exist
if [ ! -d "$HOOKS_DIR" ]; then
    echo -e "${YELLOW}📁 Creating hooks directory...${NC}"
    mkdir -p "$HOOKS_DIR"
fi

# Install pre-commit hook for Chinese text checking
PRE_COMMIT_HOOK="$HOOKS_DIR/pre-commit"
CHINESE_CHECK_HOOK="$SCRIPT_DIR/pre-commit-chinese-check"

echo -e "${BLUE}📋 Installing pre-commit hook...${NC}"

if [ -f "$PRE_COMMIT_HOOK" ]; then
    echo -e "${YELLOW}⚠️  Existing pre-commit hook found${NC}"
    echo -e "Creating backup: $PRE_COMMIT_HOOK.backup"
    cp "$PRE_COMMIT_HOOK" "$PRE_COMMIT_HOOK.backup"
fi

# Copy and make executable
cp "$CHINESE_CHECK_HOOK" "$PRE_COMMIT_HOOK"
chmod +x "$PRE_COMMIT_HOOK"

echo -e "${GREEN}✅ Pre-commit hook installed successfully${NC}"

# Test the hook
echo -e "\n${BLUE}🧪 Testing hook installation...${NC}"

if [ -x "$PRE_COMMIT_HOOK" ]; then
    echo -e "${GREEN}✅ Hook is executable${NC}"
else
    echo -e "${RED}❌ Hook is not executable${NC}"
    exit 1
fi

# Show hook status
echo -e "\n${BLUE}📊 Hook Status:${NC}"
echo -e "Hook location: $PRE_COMMIT_HOOK"
echo -e "Hook permissions: $(ls -l "$PRE_COMMIT_HOOK" | cut -d' ' -f1)"

# Provide usage instructions
echo -e "\n${GREEN}🎉 Installation Complete!${NC}"
echo -e "${GREEN}=========================${NC}"
echo -e "\n${YELLOW}📋 What happens now:${NC}"
echo -e "• Every commit will be checked for Chinese characters"
echo -e "• Commits with Chinese text will be rejected"
echo -e "• You'll get helpful translation suggestions"
echo -e "\n${YELLOW}🔧 Manual testing:${NC}"
echo -e "• Run: git commit (with staged files containing Chinese text)"
echo -e "• The hook should prevent the commit and show guidance"
echo -e "\n${YELLOW}🛠️  Additional tools:${NC}"
echo -e "• Check entire codebase: python scripts/maintenance/check_chinese_text.py"
echo -e "• Generate report: python scripts/maintenance/check_chinese_text.py --report"
echo -e "• Policy documentation: docs/dev/ENGLISH_ONLY_CODING_POLICY.md"
echo -e "\n${YELLOW}🔄 To uninstall:${NC}"
echo -e "• Remove: rm $PRE_COMMIT_HOOK"
echo -e "• Restore backup: mv $PRE_COMMIT_HOOK.backup $PRE_COMMIT_HOOK (if exists)"

echo -e "\n${GREEN}Happy coding with English-only documentation! 🚀${NC}"
